#!/usr/bin/env python3
"""
seed.py -- seed the "Suaraloka" demo dataset into a local Odoo 19 instance
from the CSV files next to this script.

    ./seed.py                 # dry run: report only, writes nothing
    ./seed.py --apply         # actually write
    ./seed.py --purge --apply # delete everything this script created

Talking to Odoo over XML-RPC (stdlib only, no pip installs).

Notes for Odoo 19, which is what makes this script non-obvious:

  * hr.employee no longer stores department_id / job_id / job_title. They are
    `related` fields forwarding to hr.version via hr.employee.version_id.
    They are still writable, so this script writes them on hr.employee and
    Odoo routes them to the version row. Never write them with raw SQL.
  * res.users.groups_id was renamed to group_ids.
  * hr.department.name is a translated (jsonb) column, so it must go through
    the ORM, never psql.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import os
import sys
import xmlrpc.client

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_URL = "http://localhost:8069"
DEFAULT_DB = "development-odoo"
DEFAULT_USER = "aryana@odoo.com"
SEED_MODULES = ["event", "suaraloka_security"]
MIN_WAGE = 4_800_000          # user's floor: Indonesian minimum wage
TZ = "Asia/Jakarta"

# users.csv gives every login exactly one role. The groups themselves live in
# addons/suaraloka_security; the seed never invents access rules of its own.
ROLE_GROUPS = {
    "project_admin": "suaraloka_security.group_project_admin",
    "assignee": "suaraloka_security.group_assignee",
    "inventory_manager": "suaraloka_security.group_inventory_manager",
    "hr": "suaraloka_security.group_hr",
}

# Groups Odoo grants from the org chart: hr_holidays gives the leave approver
# group to an employee's leave manager, hr_attendance the officer group to an
# attendance manager. Their record rules scope them to the people the user
# manages, so they widen nothing for a user without reports -- and the seed
# must not take them back from the users who hold them functionally.
FUNCTIONAL_GROUPS = [
    "hr_holidays.group_hr_holidays_responsible",
    "hr_attendance.group_hr_attendance_officer",
]

# Groups the seed is allowed to take back, in two families:
#  * what earlier revisions handed out (the old users.csv `groups` column), and
#  * the four role groups themselves -- new users are born as Assignees
#    (suaraloka_security/models/res_users.py), and a user must end up with
#    exactly one role, so the seed has to be able to remove the default.
# Anything outside this list is left alone: the seed only reconciles what the
# seed itself wrote.
SEED_MANAGED_GROUPS = [
    "suaraloka_security.group_project_admin",
    "suaraloka_security.group_assignee",
    "suaraloka_security.group_inventory_manager",
    "suaraloka_security.group_hr",
    "project.group_project_manager",
    "project.group_project_user",
    "hr.group_hr_user",
    "event.group_event_user",
    "lunch.group_lunch_manager",
    "account.group_account_invoice",
]


# --------------------------------------------------------------------------- #
# tiny RPC layer
# --------------------------------------------------------------------------- #
class Odoo:
    def __init__(self, url, db, user, password, apply):
        self.url, self.db, self.user, self.password = url, db, user, password
        self.apply = apply
        self.uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(
            db, user, password, {}
        )
        if not self.uid:
            sys.exit("authentication failed -- check --db / --user / --password")
        self._models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(self, model, method, args=None, kwargs=None):
        return self._models.execute_kw(
            self.db, self.uid, self.password, model, method, args or [], kwargs or {}
        )

    def search(self, model, domain, limit=None, active=True):
        kw = {}
        if limit:
            kw["limit"] = limit
        if not active:
            # Odoo hides inactive records by default (active_test); a purged
            # res.users is inactive but still occupies its UNIQUE(login), so
            # lookups that can meet a stale record must opt out of this.
            kw["context"] = {"active_test": False}
        return self.call(model, "search", [domain], kw)

    def ensure(self, model, key, values, label):
        """Look a record up by its natural key; create it if absent.

        Returns (record_id, 'created'|'updated'|'would-create'). In dry-run a
        brand new record gets a placeholder id, which never reaches Odoo
        because nothing is sent in dry-run.
        """
        ids = self.search(model, [(k, "=", v) for k, v in key.items()])
        if ids:
            if self.apply:
                self.call(model, "write", [ids, values])
            return ids[0], "updated"
        if not self.apply:
            return f"<new {model} {key}>", "would-create"
        return self.call(model, "create", [{**key, **values}]), "created"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_csv(name):
    path = os.path.join(HERE, name)
    if not os.path.isfile(path):
        sys.exit(f"missing data file: {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        rows = []
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            # csv.DictReader silently stashes surplus columns under key None,
            # which is what an unescaped comma in a value looks like.
            if None in row:
                sys.exit(
                    f"{name}: line {lineno} has more fields than the header "
                    f"(unescaped comma?): {row[None]!r}"
                )
            if any(v is None for v in row.values()):
                sys.exit(f"{name}: line {lineno} has fewer fields than the header")
            rows.append({k: v.strip() for k, v in row.items()})
    if not rows:
        sys.exit(f"{name} is empty")
    return rows


class Report:
    def __init__(self):
        self.counts = {}

    def add(self, what, status, n=1):
        self.counts.setdefault(what, {}).setdefault(status, 0)
        self.counts[what][status] += n

    def show(self, apply):
        print("\n" + "=" * 62)
        print("APPLIED" if apply else "DRY RUN -- nothing written")
        print("=" * 62)
        for what in sorted(self.counts):
            bits = ", ".join(f"{n} {s}" for s, n in sorted(self.counts[what].items()))
            print(f"  {what:<26} {bits}")
        print()


def validate(employees, departments, jobs, locations):
    """Fail loudly before touching the database."""
    problems = []
    dept_names = {d["name"] for d in departments}
    job_keys = {(j["name"], j["department"]) for j in jobs}
    loc_names = {l["name"] for l in locations}
    codes = {e["code"] for e in employees}

    for what, seen in (("employee code", [e["code"] for e in employees]),
                       ("work_email", [e["work_email"] for e in employees])):
        dupes = {v for v in seen if seen.count(v) > 1}
        if dupes:
            problems.append(f"duplicate {what}: {sorted(dupes)}")

    for e in employees:
        tag = f"{e['code']} ({e['name']})"
        if e["department"] not in dept_names:
            problems.append(f"{tag}: unknown department {e['department']!r}")
        if (e["job"], e["department"]) not in job_keys:
            problems.append(f"{tag}: job {e['job']!r} not defined for {e['department']!r}")
        if e["work_location"] not in loc_names:
            problems.append(f"{tag}: unknown work location {e['work_location']!r}")
        for fld in ("manager_code", "coach_code"):
            if e[fld] and e[fld] not in codes:
                problems.append(f"{tag}: unknown {fld} {e[fld]!r}")
        if not e["employee_type"]:
            problems.append(f"{tag}: employee_type is required")
        if e["code"] in (e["manager_code"], e["coach_code"]):
            problems.append(f"{tag}: cannot manage/coach themselves")
        try:
            wage = int(e["wage"])
        except ValueError:
            problems.append(f"{tag}: wage {e['wage']!r} is not a number")
            continue
        if wage < MIN_WAGE:
            problems.append(f"{tag}: wage Rp {wage:,} is below the Rp {MIN_WAGE:,} floor")

    for d in departments:
        if d["parent"] and d["parent"] not in dept_names:
            problems.append(f"department {d['name']!r}: unknown parent {d['parent']!r}")
        if d["manager_code"] and d["manager_code"] not in codes:
            problems.append(f"department {d['name']!r}: unknown manager {d['manager_code']!r}")

    # a department cannot manage itself through the tree
    for d in departments:
        if d["parent"] == d["name"]:
            problems.append(f"department {d['name']!r} is its own parent")

    if problems:
        print("VALIDATION FAILED -- no changes made:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


def validate_cpm(tasks, dependencies, users):
    """Cross-check the CPM CSVs before anything is written.

    The engine refuses a link whose predecessor lives in another project, so a
    typo in the project column would fail at write time with a message about a
    dependency instead of about the CSV.
    """
    problems = []
    task_keys = [(t["project"], t["name"]) for t in tasks]
    for key in {k for k in task_keys if task_keys.count(k) > 1}:
        problems.append(f"duplicate task {key[1]!r} in project {key[0]!r}")

    seen_edges = []
    for d in dependencies:
        tag = f"{d['predecessor']!r} -> {d['successor']!r} ({d['project']})"
        for side in ("predecessor", "successor"):
            if (d["project"], d[side]) not in task_keys:
                problems.append(f"{tag}: unknown {side} {d[side]!r} in {d['project']!r}")
        if d["predecessor"] == d["successor"]:
            problems.append(f"{tag}: a task cannot depend on itself")
        if d["type"] not in ("FS", "SS", "FF", "SF"):
            problems.append(f"{tag}: unknown dependency type {d['type']!r}")
        try:
            float(d["lag"])
        except ValueError:
            problems.append(f"{tag}: lag {d['lag']!r} is not a number")
        edge = (d["project"], d["predecessor"], d["successor"])
        if edge in seen_edges:
            problems.append(f"{tag}: duplicate link")
        seen_edges.append(edge)

    for t in tasks:
        if t["supervisor_login"] not in {u["login"] for u in users}:
            problems.append(
                f"task {t['name']!r}: supervisor {t['supervisor_login']!r} "
                "is not a seeded user"
            )
        if t["assignee_login"] not in {u["login"] for u in users}:
            problems.append(
                f"task {t['name']!r}: assignee {t['assignee_login']!r} "
                "is not a seeded user"
            )
        try:
            if float(t["duration"]) <= 0:
                problems.append(
                    f"task {t['name']!r}: duration {t['duration']!r} must be > 0"
                )
        except ValueError:
            problems.append(f"task {t['name']!r}: duration {t['duration']!r} is not a number")

        if t.get("status") not in ("", "open", "done"):
            problems.append(
                f"task {t['name']!r}: unknown status {t['status']!r} "
                "(expected 'open' or 'done')"
            )
        estimates = [t.get("optimistic"), t.get("most_likely"), t.get("pessimistic")]
        if any(estimates) and not all(estimates):
            problems.append(
                f"task {t['name']!r}: PERT takes all three estimates or none"
            )
        elif all(estimates):
            try:
                optimistic, likely, pessimistic = (float(v) for v in estimates)
            except ValueError:
                problems.append(
                    f"task {t['name']!r}: PERT estimates must be numbers"
                )
            else:
                if not optimistic <= likely <= pessimistic:
                    problems.append(
                        f"task {t['name']!r}: PERT estimates must be ordered "
                        "optimistic <= most likely <= pessimistic"
                    )

    if problems:
        print("CPM VALIDATION FAILED -- no changes made:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


def validate_cpm_resources(tasks, users, contractors, materials, lines, vendors=()):
    """Cross-check the resource CSVs before anything is written.

    Resources hang off seeded tasks and reference contractors/materials by
    name, so a typo would otherwise fail deep inside a write with a message
    about a foreign key instead of pointing at the CSV row.
    """
    problems = []
    task_keys = {(t["project"], t["name"]) for t in tasks}
    contractor_names = [c["name"] for c in contractors]
    material_names = [m["name"] for m in materials]
    vendor_names = [v["name"] for v in vendors]
    logins = {u["login"] for u in users}

    for c in contractors:
        if not c["name"]:
            problems.append("contractor row with empty name")
        try:
            if float(c["day_rate"]) <= 0:
                problems.append(f"contractor {c['name']!r}: day_rate must be > 0")
        except ValueError:
            problems.append(f"contractor {c['name']!r}: day_rate is not a number")

    for v in vendors:
        if not v["name"]:
            problems.append("vendor row with empty name")

    for m in materials:
        try:
            if float(m["cost"]) < 0:
                problems.append(f"material {m['name']!r}: cost must be >= 0")
        except ValueError:
            problems.append(f"material {m['name']!r}: cost is not a number")
        if m.get("vendor") and m["vendor"] not in vendor_names:
            problems.append(
                f"material {m['name']!r}: unknown vendor {m['vendor']!r}")

    seen = set()
    for r in lines:
        tag = f"{r['task']!r} / {r['type']!r} / {r['product'] or r['contractor']!r}"
        if (r["project"], r["task"]) not in task_keys:
            problems.append(f"{tag}: unknown task {r['task']!r} in {r['project']!r}")
        if r["type"] not in ("material", "contractor"):
            problems.append(f"{tag}: type must be material or contractor")
        if r["type"] == "material":
            if r["product"] not in material_names:
                problems.append(f"{tag}: unknown material {r['product']!r}")
            if r["contractor"]:
                problems.append(f"{tag}: contractor set on a material line")
        if r["type"] == "contractor":
            if r["contractor"] not in contractor_names:
                problems.append(f"{tag}: unknown contractor {r['contractor']!r}")
            if r["product"]:
                problems.append(f"{tag}: product set on a contractor line")
        if tag in seen:
            problems.append(f"{tag}: duplicate resource line")
        seen.add(tag)
        for col in ("planned_qty", "planned_days"):
            if r[col]:
                try:
                    if float(r[col]) <= 0:
                        problems.append(f"{tag}: {col} must be > 0")
                except ValueError:
                    problems.append(f"{tag}: {col} {r[col]!r} is not a number")

    if problems:
        print("CPM RESOURCES VALIDATION FAILED -- no changes made:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


# --------------------------------------------------------------------------- #
# steps
# --------------------------------------------------------------------------- #
def step_company(o, rep):
    row = load_csv("company.csv")[0]
    vals = {
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
    }
    if o.apply:
        o.call("res.company", "write", [[1], vals])
    # company name is related to partner_id.name; set the address on the partner
    partner_id = o.call("res.company", "read", [[1], ["partner_id"]])[0]["partner_id"][0]
    if o.apply:
        o.call("res.partner", "write", [[partner_id], {"city": row["city"], "street": row["street"]}])
    rep.add("company", "updated" if o.apply else "would-update")


def step_modules(o, rep, modules):
    for name in modules:
        found = o.search("ir.module.module", [("name", "=", name), ("state", "=", "uninstalled")])
        if not found:
            print(f"  module {name}: already installed")
            continue
        print(f"  module {name}: installing (this can take a moment)")
        if o.apply:
            o.call("ir.module.module", "button_immediate_install", [found])
        rep.add("modules installed", "installed" if o.apply else "would-install")


def step_fold_admin(o, rep):
    """Fold the auto-created 'Administration' department into 'Executive'."""
    if o.search("hr.department", [("name", "=", "Executive")]):
        return
    ids = o.search("hr.department", [("name", "=", "Administration")])
    if not ids:
        print("  fold: no 'Administration' department to fold")
        return
    print("  fold: renaming 'Administration' -> 'Executive' (keeps the existing employee attached)")
    if o.apply:
        o.call("hr.department", "write", [ids, {"name": "Executive"}])
    rep.add("fold administration", "renamed" if o.apply else "would-rename")


def step_work_locations(o, rep, rows, country_id):
    ids = {}
    for r in rows:
        # hr.work.location.address_id is mandatory, so each location needs its
        # own res.partner address record first.
        pid, pst = o.ensure(
            "res.partner",
            {"name": r["name"]},
            {"city": r["city"], "country_id": country_id, "company_type": "company"},
            r["name"],
        )
        rep.add("work location addresses", pst)
        rid, st = o.ensure(
            "hr.work.location",
            {"name": r["name"]},
            {
                "location_type": r["location_type"],
                "location_number": r["location_number"],
                "address_id": pid,
            },
            r["name"],
        )
        ids[r["name"]] = rid
        rep.add("work locations", st)
    return ids


def step_calendars(o, rep, rows):
    ids = {}
    for r in rows:
        rid, st = o.ensure(
            "resource.calendar",
            {"name": r["name"]},
            {
                "tz": r["tz"],
                "schedule_type": r["schedule_type"],
                "hours_per_week": float(r["hours_per_week"]),
                "hours_per_day": float(r["hours_per_day"]),
                "full_time_required_hours": float(r["full_time_required_hours"]),
                "flexible_hours": r["flexible_hours"].lower() == "true",
            },
            r["name"],
        )
        ids[r["name"]] = rid
        rep.add("calendars", st)
    return ids


def step_departments(o, rep, rows):
    ids = {}
    pending = list(rows)
    # two passes so CSV row order does not matter
    for attempt in range(2):
        still = []
        for r in pending:
            parent = r["parent"]
            if parent and parent not in ids:
                still.append(r)
                continue
            rid, st = o.ensure(
                "hr.department",
                {"name": r["name"]},
                {"parent_id": ids.get(parent) or False},
                r["name"],
            )
            ids[r["name"]] = rid
            rep.add("departments", st)
        pending = still
        if not pending:
            break
    if pending:
        sys.exit(f"could not resolve parents for: {[r['name'] for r in pending]}")
    return ids


def step_jobs(o, rep, rows, dept_ids):
    ids = {}
    for r in rows:
        dept = dept_ids[r["department"]]
        rid, st = o.ensure(
            "hr.job",
            {"name": r["name"], "department_id": dept},
            {
                "no_of_recruitment": int(r["no_of_recruitment"] or 0),
                "description": f"<p>{r['description']}</p>",
                "requirements": r["requirements"],
            },
            r["name"],
        )
        ids[(r["name"], r["department"])] = rid
        rep.add("jobs", st)
    return ids


def step_employees(o, rep, rows, dept_ids, job_ids, loc_ids, cal_ids, country_id):
    """Pass 1 creates everyone; pass 2 wires up manager/coach so CSV order is free."""
    ids = {}
    for r in rows:
        cal = "Office Hours (Jakarta)" if r["employee_type"] == "employee" else "Festival Crew (Flexible)"
        values = {
            "work_email": r["work_email"],
            "mobile_phone": r["mobile_phone"],
            "job_title": r["job"],
            "employee_type": r["employee_type"],
            "department_id": dept_ids[r["department"]],
            "job_id": job_ids[(r["job"], r["department"])],
            "work_location_id": loc_ids[r["work_location"]],
            "resource_calendar_id": cal_ids[cal],
            "tz": TZ,
            "private_street": r["private_street"],
            "private_city": r["private_city"],
            "private_zip": r["private_zip"],
            "private_country_id": country_id,
            "wage": int(r["wage"]),
            "contract_date_start": r["contract_date_start"] or False,
            "birthday": r["birthday"] or False,
        }
        rid, st = o.ensure("hr.employee", {"barcode": r["code"]}, {"name": r["name"], **values}, r["name"])
        ids[r["code"]] = rid
        rep.add("employees", st)

    for r in rows:
        links = {}
        if r["manager_code"]:
            links["parent_id"] = ids[r["manager_code"]]
        if r["coach_code"]:
            links["coach_id"] = ids[r["coach_code"]]
        if not links:
            continue
        if o.apply:
            o.call("hr.employee", "write", [[ids[r["code"]]], links])
        rep.add("reporting lines", "set" if o.apply else "would-set")
    return ids


def step_dept_managers(o, rep, rows, dept_ids, emp_ids):
    for r in rows:
        if not r["manager_code"]:
            continue
        if o.apply:
            o.call("hr.department", "write", [[dept_ids[r["name"]]], {"manager_id": emp_ids[r["manager_code"]]}])
        rep.add("department managers", "set" if o.apply else "would-set")


def step_lunch(o, rep, cats, sups, prods, locs):
    cat_ids = {}
    for r in cats:
        rid, st = o.ensure("lunch.product.category", {"name": r["name"]}, {}, r["name"])
        cat_ids[r["name"]] = rid
        rep.add("lunch categories", st)

    sup_ids = {}
    for r in sups:
        pid, st = o.ensure(
            "res.partner",
            {"name": r["name"]},
            {"email": r["email"], "supplier_rank": 1, "company_type": "company"},
            r["name"],
        )
        rep.add("lunch suppliers (partner)", st)
        sid, st2 = o.ensure(
            "lunch.supplier",
            {"partner_id": pid},
            {"moment": r["moment"], "delivery": r["delivery"], "tz": TZ},
            r["name"],
        )
        sup_ids[r["name"]] = sid
        rep.add("lunch suppliers", st2)

    for r in prods:
        rid, st = o.ensure(
            "lunch.product",
            {"name": r["name"]},
            {
                "category_id": cat_ids[r["category"]],
                "supplier_id": sup_ids[r["supplier"]],
                "price": float(r["price"]),
                "description": f"<p>{r['description']}</p>",
            },
            r["name"],
        )
        rep.add("lunch products", st)

    for r in locs:
        rid, st = o.ensure("lunch.location", {"name": r["name"]}, {"address": r["address"]}, r["name"])
        rep.add("lunch locations", st)


def resolve_groups(o, xmlids):
    """Map 'module.name' group xmlids to res.groups ids, failing loudly."""
    out = {}
    for x in sorted(xmlids):
        mod, _, name = x.partition(".")
        found = o.call(
            "ir.model.data", "search_read",
            [[("module", "=", mod), ("name", "=", name), ("model", "=", "res.groups")], ["res_id"]],
        )
        if not found:
            sys.exit(f"users.csv references unknown group xmlid {x!r}")
        out[x] = found[0]["res_id"]
    return out


def step_users(o, rep, rows, emp_names, emp_ids):
    """Create a login per employee and bind it to the existing HR record.

    hr's res.users.create only spawns a *new* employee when you pass
    create_employee / create_employee_id. We pass create_employee_id with the
    employee we already seeded, so the user binds to it instead of duplicating it.

    Each row carries one `role`, not a list of groups: the four roles in
    addons/suaraloka_security are the access model. A re-run reconciles the
    groups earlier revisions of this seed handed out (SEED_MANAGED_GROUPS) and
    the demo defaults a new user is born with (see below), so a changed role
    takes the old grants away instead of leaving them behind.
    """
    all_xmlids = (
        {ROLE_GROUPS[r["role"]] for r in rows}
        | set(SEED_MANAGED_GROUPS)
        | set(FUNCTIONAL_GROUPS)
    )
    group_ids = resolve_groups(o, all_xmlids)
    managed_ids = {group_ids[x] for x in SEED_MANAGED_GROUPS}
    # In a --with-demo database every new user is a manager in every app: each
    # app's demo data extends base.default_user_group (hr_demo.xml,
    # stock_demo.xml, account_demo.xml, ...). Users created without an explicit
    # group list inherit that, so the seed revokes those demo defaults too --
    # otherwise a role would mean "role plus whatever the demo left behind".
    default_group = o.call(
        "ir.model.data", "search_read",
        [[("module", "=", "base"), ("name", "=", "default_user_group"),
          ("model", "=", "res.groups")], ["res_id"]],
    )
    demo_default_ids = set()
    if default_group:
        demo_default_ids = set(o.call(
            "res.groups", "read",
            [[default_group[0]["res_id"]], ["all_implied_ids"]],
        )[0]["all_implied_ids"])
    # ... except the org-chart groups, which Odoo re-grants anyway.
    demo_default_ids -= {group_ids[x] for x in FUNCTIONAL_GROUPS}
    revocable_ids = managed_ids | demo_default_ids

    for r in rows:
        code, login = r["employee_code"], r["login"]
        emp_id = emp_ids.get(code)
        real_emp = emp_id is not None and not isinstance(emp_id, str)
        name = emp_names.get(code, login)

        ids = o.search("res.users", [("login", "=", login)], limit=1, active=False)
        if ids:
            uid = ids[0]
            was_active = o.call("res.users", "read", [[uid], ["active"]])[0]["active"]
            # deliberately do not touch the password on a re-run
            vals = {"name": name, "email": login, "tz": TZ}
            if not was_active:
                vals["active"] = True
            if o.apply:
                o.call("res.users", "write", [[uid], vals])
            rep.add("users (logins)", "updated" if was_active else "reactivated")
        elif not o.apply:
            uid = f"<new res.users {login}>"
            rep.add("users (logins)", "would-create")
        else:
            vals = {"name": name, "login": login, "email": login,
                    "password": r["password"], "tz": TZ}
            if real_emp:
                vals["create_employee_id"] = emp_id
            uid = o.call("res.users", "create", [vals])
            rep.add("users (logins)", "created")

        if isinstance(uid, str) or not real_emp:
            continue

        # belt-and-braces: verify the HR link landed, repair it if not
        cur = o.call("hr.employee", "read", [[emp_id], ["user_id"]])[0]["user_id"]
        if not cur or cur[0] != uid:
            if o.apply:
                o.call("hr.employee", "write", [[emp_id], {"user_id": uid}])
            rep.add("employee<->user links", "linked" if o.apply else "would-link")
        else:
            rep.add("employee<->user links", "already-linked")

        # The role group and everything it implies is the whole desired set;
        # any other seed-managed group still on the user is a stale grant.
        role_id = group_ids[ROLE_GROUPS[r["role"]]]
        role_implied = set(o.call(
            "res.groups", "read", [[role_id], ["all_implied_ids"]],
        )[0]["all_implied_ids"])
        keep = {role_id} | role_implied
        cur_groups = set(o.call("res.users", "read", [[uid], ["group_ids"]])[0]["group_ids"])
        stale = (cur_groups & revocable_ids) - keep
        missing = {role_id} - cur_groups
        if missing or stale:
            if o.apply:
                cmds = [(3, g) for g in sorted(stale)] + [(4, g) for g in sorted(missing)]
                o.call("res.users", "write", [[uid], {"group_ids": cmds}])
            if missing:
                rep.add("group grants", "added")
            if stale:
                rep.add("group grants", "revoked")
        else:
            rep.add("group grants", "already-set")


# --------------------------------------------------------------------------- #
# CPM demo network
#
# The project is NOT owned by the seed. "Home Construction" is Odoo demo data,
# so it is looked up by name and reused -- never created with values and never
# deleted by --purge. The seed owns the tasks and links it adds, which is what
# makes the CPM Network view worth opening on a fresh database.
# --------------------------------------------------------------------------- #
def step_cpm_installed(o, rep):
    """The CPM steps need suaraloka_cpm; skip them cleanly when it is absent."""
    found = o.search(
        "ir.module.module",
        [("name", "=", "suaraloka_cpm"), ("state", "=", "installed")],
    )
    if found:
        return True
    print("  cpm: suaraloka_cpm is not installed -- skipping the CPM demo network")
    return False


def step_cpm_purchase_installed(o):
    """The material vendors need product.supplierinfo, i.e. purchase."""
    return bool(o.search(
        "ir.module.module",
        [("name", "=", "purchase"), ("state", "=", "installed")],
    ))


def step_cpm_projects(o, rep, rows):
    ids = {}
    for r in rows:
        name = r["project"]
        if name in ids:
            continue
        rid, st = o.ensure("project.project", {"name": name}, {}, name)
        ids[name] = rid
        rep.add("cpm projects", st)
    return ids


def step_cpm_tasks(o, rep, rows, project_ids, user_ids_by_login):
    """Keyed by (project, name): a task name is unique inside its project, so
    two projects may each have their own "Survey" without colliding.

    Each row also carries the PERT three-point estimate (all three or none: the
    model refuses a partial set) and a completion status, so the dashboard has
    a probabilistic view and a partly finished network to draw. The estimates
    are *analysis* input only -- cpm_duration stays the committed schedule --
    and `done` closes the task with a completion date taken from its own
    planned end, which is what the weekly burndown reads.
    """
    ids = {}
    for r in rows:
        supervisor = user_ids_by_login.get(r["supervisor_login"])
        assignee = user_ids_by_login.get(r["assignee_login"])
        vals = {
            "cpm_duration": float(r["duration"]),
            # required on the model: supervisor audits the task and signs
            # off its resources
            "supervisor_id": supervisor,
        }
        if r.get("optimistic"):
            vals.update({
                "pert_optimistic": float(r["optimistic"]),
                "pert_most_likely": float(r["most_likely"]),
                "pert_pessimistic": float(r["pessimistic"]),
            })
        if r.get("status") == "done":
            # Closed state, and the project's own Done stage. In Odoo 19 state
            # and stage are independent axes -- a task can be "1_done" in the
            # New column -- and the kanban reads the stage, so the seed sets
            # both. The stage is looked up by name among the stages linked to
            # this project, and simply left alone when the project has none.
            vals["state"] = "1_done"
            stage_ids = o.search(
                "project.task.type",
                [("name", "=", "Done"),
                 ("project_ids", "in", [project_ids[r["project"]]])],
                limit=1,
            )
            if stage_ids:
                vals["stage_id"] = stage_ids[0]
        if assignee:
            # The assignee does the work. The Assignee role sees exactly the
            # tasks this field points at (see suaraloka_security's rules).
            vals["user_ids"] = [(4, assignee)]
        rid, st = o.ensure(
            "project.task",
            {"project_id": project_ids[r["project"]], "name": r["name"]},
            vals,
            r["name"],
        )
        if r.get("status") == "done" and o.apply and not isinstance(rid, str):
            # The completion date must be written after the close: writing the
            # state runs Odoo's update_date_end(), which stamps "now", and the
            # burndown needs the seeded history instead.
            planned_end = o.call("project.task", "read", [rid, ["date_planned_end"]])
            if planned_end and planned_end[0]["date_planned_end"]:
                o.call("project.task", "write", [rid, {
                    "date_end": planned_end[0]["date_planned_end"],
                }])
                rep.add("cpm task completion dates", "set")
        ids[(r["project"], r["name"])] = rid
        rep.add("cpm tasks", st)
    return ids


def step_cpm_contractors(o, rep, rows):
    """Contractor partners keyed by name."""
    ids = {}
    for r in rows:
        rid, st = o.ensure(
            "res.partner",
            {"name": r["name"]},
            {
                "is_contractor": True,
                "supplier_rank": 1,
                "email": r["email"],
                "phone": r["phone"],
                "contractor_day_rate": float(r["day_rate"]),
            },
            r["name"],
        )
        ids[r["name"]] = rid
        rep.add("cpm contractors", st)
    return ids


def step_cpm_vendors(o, rep, rows):
    """Material vendors, keyed by name.

    Plain partners flagged as vendors (`supplier_rank`), *not* contractors:
    they sell the materials a task consumes, and the Restock request reads
    them from the product's vendor list. HR owns the contact book, so this is
    the only place the seed creates them.
    """
    ids = {}
    for r in rows:
        rid, st = o.ensure(
            "res.partner",
            {"name": r["name"]},
            {
                "supplier_rank": 1,
                "company_type": "company",
                "email": r["email"],
                "phone": r["phone"],
            },
            r["name"],
        )
        ids[r["name"]] = rid
        rep.add("cpm vendors", st)
    return ids


def step_cpm_materials(o, rep, rows, vendor_ids=None):
    """Storable products the tasks consume, keyed by name.

    Storable + consu so the Reserve button produces a real quant reservation.
    Each material also gets its vendor (`product.supplierinfo`), which is what
    the Restock button on a short material line reads to raise its draft RFQ;
    the vendor price is the material's cost, the lead time a week.
    """
    vendor_ids = vendor_ids or {}
    ids = {}
    for r in rows:
        # resolve the template's default variant; product.template name is
        # the natural key
        tmpl, st = o.ensure(
            "product.template",
            {"name": r["name"]},
            {
                "type": "consu",
                "is_storable": True,
                "standard_price": float(r["cost"]),
                "list_price": float(r["cost"]),
            },
            r["name"],
        )
        rep.add("cpm materials (templates)", st)
        if isinstance(tmpl, str):
            # dry run: ensure() returned a placeholder id, nothing exists yet
            ids[r["name"]] = f"<new product.product {r['name']}>"
            continue
        if r.get("vendor"):
            vendor_id = vendor_ids.get(r["vendor"])
            if not vendor_id:
                if o.apply:
                    raise SystemExit(
                        f"material {r['name']!r}: unknown vendor {r['vendor']!r}")
            elif isinstance(vendor_id, str):
                # dry run: the vendor itself is still a placeholder
                rep.add("cpm material vendors", "would-create")
            else:
                _sid, st = o.ensure(
                    "product.supplierinfo",
                    {"product_tmpl_id": tmpl, "partner_id": vendor_id},
                    {
                        "price": float(r["cost"]),
                        "min_qty": 0.0,
                        "delay": 7,
                    },
                    f"{r['name']} / {r['vendor']}",
                )
                rep.add("cpm material vendors", st)
        pids = o.search("product.product", [("product_tmpl_id", "=", tmpl)])
        if not pids:
            raise SystemExit(f"material {r['name']!r}: template {tmpl} has no variant")
        pid = pids[0]
        ids[r["name"]] = pid
        # initial inventory on hand at WH/Stock (stock.stock_location_stock) --
        # without a quant the Reserve button confirms a move that can never
        # assign, so reserved_qty stays 0 (found live 2026-10-02)
        loc = o.search("ir.model.data", [("module", "=", "stock"),
                                         ("name", "=", "stock_location_stock")])
        loc_id = o.call("ir.model.data", "read", [loc, ["res_id"]])[0]["res_id"] if loc else None
        if not loc_id:
            raise SystemExit("stock.stock_location_stock not found -- stock module missing?")
        q = o.search("stock.quant", [("product_id", "=", pid),
                                     ("location_id", "=", loc_id)])
        qty = float(r["stock_qty"] or 0)
        if not q:
            o.call("stock.quant", "create", [{
                "product_id": pid, "location_id": loc_id, "inventory_quantity": qty}])
            q = o.search("stock.quant", [("product_id", "=", pid),
                                         ("location_id", "=", loc_id)])
        else:
            o.call("stock.quant", "write", [q, {"inventory_quantity": qty}])
        try:
            o.call("stock.quant", "action_apply_inventory", q)
        except xmlrpc.client.Fault as e:
            # action_apply_inventory returns None and Odoo 19's XML-RPC
            # marshaller rejects it AFTER the transaction committed; ignore
            # that fault only, then verify below
            if "cannot marshal None" not in str(e):
                raise
        applied = o.call("stock.quant", "read", [q, ["quantity"]])
        if any(abs(r["quantity"] - qty) > 1e-6 for r in applied):
            raise SystemExit(f"material {r['name']!r}: on-hand is "
                             f"{applied[0]['quantity']}, expected {qty}")
        rep.add("cpm material stock (WH/Stock)", st)
    return ids


def step_cpm_resources(o, rep, rows, task_ids, contractor_ids, material_ids,
                       contractors, materials):
    """Resource lines keyed by (task, type, product-or-contractor)."""
    for r in rows:
        key = (r["project"], r["task"])
        if key not in task_ids:
            continue
        task_id = task_ids[key]
        if r["type"] == "material":
            ensure_key = {
                "task_id": task_id,
                "resource_type": "material",
                "product_id": material_ids[r["product"]],
            }
            vals = {
                "planned_qty": float(r["planned_qty"]),
                # the product's seeded cost; the UI suggests the same value
                "rate_cost": float(next(
                    m["cost"] for m in materials
                    if m["name"] == r["product"])),
            }
        else:
            ensure_key = {
                "task_id": task_id,
                "resource_type": "contractor",
                "contractor_id": contractor_ids[r["contractor"]],
            }
            vals = {
                # one field for all three types: material qty, labor hours,
                # contractor days
                "planned_qty": float(r["planned_days"]),
                "rate_cost": float(next(
                    c["day_rate"] for c in contractors
                    if c["name"] == r["contractor"])),
            }
            # the model constraint requires the contractor to be on the task's
            # Contractors field first. Skipped in dry runs, where task_id is a
            # placeholder string rather than a database id.
            if o.apply:
                o.call("project.task", "write", [task_id, {
                    "contractor_partner_ids": [(4, ensure_key["contractor_id"])]}])
        _rid, st = o.ensure("project.task.resource.line", ensure_key, vals,
                            f"{r['task']} / {r['type']}")
        rep.add("cpm resource lines", st)


def step_cpm_dependencies(o, rep, rows, task_ids):
    """Links last, so both endpoints exist. Keyed by (predecessor, successor),
    which is exactly the model's UNIQUE constraint."""
    for r in rows:
        _rid, st = o.ensure(
            "project.task.dependency",
            {
                "predecessor_id": task_ids[(r["project"], r["predecessor"])],
                "task_id": task_ids[(r["project"], r["successor"])],
            },
            {"dependency_type": r["type"], "lag": float(r["lag"])},
            f"{r['predecessor']} -> {r['successor']}",
        )
        rep.add("cpm dependencies", st)


def step_purge(o, rep, data):
    """Delete only records whose natural key appears in the CSVs."""
    def drop(model, domain, label):
        ids = o.search(model, domain, active=False)
        if ids:
            if o.apply:
                o.call(model, "unlink", [ids])
            rep.add(label, "deleted" if o.apply else "would-delete", len(ids))

    if not o.apply:
        print("  purge: dry run, nothing deleted")
        return
    # CPM demo: the links cascade from the tasks (ondelete='cascade' on both
    # ends), so dropping the tasks is enough. The PROJECT is left alone -- it is
    # Odoo demo data the seed reuses by name.
    by_project = {}
    for r in data["cpm_tasks"]:
        by_project.setdefault(r["project"], []).append(r["name"])
    for project, names in by_project.items():
        pids = o.search("project.project", [("name", "=", project)])
        if not pids:
            continue
        # resource lines before tasks: the o2m would cascade too, but explicit
        # drops keep the report honest about what got removed
        drop("project.task.resource.line",
             [("task_id", "in", o.search("project.task",
                                          [("project_id", "in", pids),
                                           ("name", "in", names)]))],
             "cpm resource lines")
        drop("project.task", [("project_id", "in", pids), ("name", "in", names)], "cpm tasks")
    # contractors and materials are plain m2o targets, no cascade: drop after
    # the lines are gone. Quants hold product_id and must go first or the
    # product unlink raises a restrict error.
    drop("res.partner", [("name", "in", [r["name"] for r in data["cpm_contractors"]])],
         "cpm contractors")
    for r in data["cpm_materials"]:
        tids = o.search("product.template", [("name", "=", r["name"])], active=False)
        if tids:
            pids = o.search("product.product",
                            [("product_tmpl_id", "in", tids)], active=False)
            mids = o.search("stock.move", [("product_id", "in", pids)], active=False)
            if mids:
                # RESTRICT on stock_move.product_id: cancel whatever is open,
                # then unlink the moves themselves (done ones included -- the
                # dev seed may leave validated consumption behind).
                # Odoo 19 removed the public action_cancel; state write is the
                # teardown-safe equivalent.
                o.call("stock.move", "write", [mids, {"state": "cancel"}])
                o.call("stock.move", "unlink", [mids])
                rep.add("cpm material stock moves", "deleted", len(mids))
            drop("stock.quant", [("product_id", "in", pids)], "cpm material quants")
        drop("product.template", [("name", "=", r["name"])], "cpm materials")
    # after the materials: their supplierinfo rows (the vendor link) cascade
    # with the template, so the partners are safe to delete by then
    drop("res.partner", [("name", "in", [r["name"] for r in data["cpm_vendors"]])],
         "cpm vendors")
    for r in data["lunch_products"]:
        drop("lunch.product", [("name", "=", r["name"])], "lunch products")
    for r in data["lunch_suppliers"]:
        pid = o.search("res.partner", [("name", "=", r["name"])])
        drop("lunch.supplier", [("partner_id", "in", pid)], "lunch suppliers")
        drop("res.partner", [("id", "in", pid)], "lunch supplier partners")
    for r in data["lunch_categories"]:
        drop("lunch.product.category", [("name", "=", r["name"])], "lunch categories")
    for r in data["lunch_locations"]:
        drop("lunch.location", [("name", "=", r["name"])], "lunch locations")
    # Employees MUST go before users: hr_employee.user_id is a RESTRICT foreign
    # key, so unlinking a user that an employee still points at raises and the
    # user survives. Deleting the employee first removes that reference.
    drop("hr.employee", [("barcode", "in", [r["code"] for r in data["employees"]])], "employees")
    for r in data["users"]:
        ids = o.search("res.users", [("login", "=", r["login"])], active=False)
        if not ids:
            continue
        # defensive: detach anything still pointing at these users
        still = o.search("hr.employee", [("user_id", "in", ids)], active=False)
        if still:
            o.call("hr.employee", "write", [still, {"user_id": False}])
        try:
            o.call("res.users", "unlink", [ids])
            rep.add("users (logins)", "deleted")
        except Exception as exc:
            # a user owning records cannot be deleted (ir_cron, utm_campaign, ...)
            o.call("res.users", "write", [ids, {"active": False}])
            rep.add("users (logins)", "deactivated")
            print(f"  note: could not delete {r['login']}, deactivated instead: "
                  f"{str(exc).splitlines()[0][:120]}")
    for r in data["jobs"]:
        drop("hr.job", [("name", "=", r["name"])], "jobs")
    # Executive is the folded pre-existing department -- never delete it
    names = [r["name"] for r in data["departments"] if r["name"] != "Executive"]
    drop("hr.department", [("name", "in", names)], "departments")
    drop("hr.work.location", [("name", "in", [r["name"] for r in data["work_locations"]])], "work locations")
    drop("res.partner", [("name", "in", [r["name"] for r in data["work_locations"]])], "work location addresses")
    drop("resource.calendar", [("name", "in", [r["name"] for r in data["calendars"]])], "calendars")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Seed the Suaraloka demo dataset into Odoo.")
    ap.add_argument("--url", default=os.environ.get("ODOO_URL", DEFAULT_URL))
    ap.add_argument("--db", default=os.environ.get("ODOO_DB", DEFAULT_DB))
    ap.add_argument("--user", default=os.environ.get("ODOO_USER", DEFAULT_USER))
    ap.add_argument("--password", default=os.environ.get("ODOO_PASSWORD"))
    ap.add_argument("--apply", action="store_true", help="actually write (default is a dry run)")
    ap.add_argument("--purge", action="store_true", help="delete what this script created")
    ap.add_argument("--no-modules", action="store_true", help="do not install the event app")
    args = ap.parse_args()

    if not args.password:
        args.password = getpass.getpass(f"password for {args.user}: ")

    data = {
        "company": load_csv("company.csv"),
        "departments": load_csv("departments.csv"),
        "jobs": load_csv("jobs.csv"),
        "work_locations": load_csv("work_locations.csv"),
        "calendars": load_csv("calendars.csv"),
        "employees": load_csv("employees.csv"),
        "lunch_categories": load_csv("lunch_categories.csv"),
        "lunch_suppliers": load_csv("lunch_suppliers.csv"),
        "lunch_products": load_csv("lunch_products.csv"),
        "lunch_locations": load_csv("lunch_locations.csv"),
        "users": load_csv("users.csv"),
        "cpm_tasks": load_csv("cpm_tasks.csv"),
        "cpm_dependencies": load_csv("cpm_dependencies.csv"),
        "cpm_contractors": load_csv("cpm_contractors.csv"),
        "cpm_materials": load_csv("cpm_materials.csv"),
        "cpm_vendors": load_csv("cpm_vendors.csv"),
        "cpm_resources": load_csv("cpm_resources.csv"),
    }

    validate(data["employees"], data["departments"], data["jobs"], data["work_locations"])

    # users.csv must line up with employees.csv
    ecodes = {e["code"] for e in data["employees"]}
    unknown = sorted({u["employee_code"] for u in data["users"]} - ecodes)
    if unknown:
        sys.exit(f"users.csv references unknown employee codes: {unknown}")
    logins = [u["login"] for u in data["users"]]
    dupes = {x for x in logins if logins.count(x) > 1}
    if dupes:
        sys.exit(f"users.csv has duplicate logins: {sorted(dupes)}")
    for u in data["users"]:
        if not u["password"]:
            sys.exit(f"users.csv: {u['login']} has no password")
        if u["role"] not in ROLE_GROUPS:
            sys.exit(f"users.csv: {u['login']} has unknown role {u['role']!r} "
                     f"(expected one of {', '.join(sorted(ROLE_GROUPS))})")
    print(f"validated {len(data['employees'])} employees, {len(data['departments'])} departments, "
          f"{len(data['jobs'])} jobs -- all wages >= Rp {MIN_WAGE:,}")

    validate_cpm(data["cpm_tasks"], data["cpm_dependencies"], data["users"])
    print(f"validated {len(data['cpm_tasks'])} CPM tasks and "
          f"{len(data['cpm_dependencies'])} CPM dependencies")
    validate_cpm_resources(data["cpm_tasks"], data["users"],
                           data["cpm_contractors"], data["cpm_materials"],
                           data["cpm_resources"], data["cpm_vendors"])
    print(f"validated {len(data['cpm_contractors'])} contractors, "
          f"{len(data['cpm_materials'])} materials, "
          f"{len(data['cpm_vendors'])} vendors, "
          f"{len(data['cpm_resources'])} resource lines")

    o = Odoo(args.url, args.db, args.user, args.password, args.apply)
    print(f"connected to {args.db} as {args.user} (uid {o.uid})\n")
    rep = Report()

    country_id = o.search("res.country", [("code", "=", "ID")])[0]

    if args.purge:
        step_purge(o, rep, data)
        rep.show(args.apply)
        return

    if not args.no_modules:
        step_modules(o, rep, SEED_MODULES)
    step_company(o, rep)
    step_fold_admin(o, rep)

    loc_ids = step_work_locations(o, rep, data["work_locations"], country_id)
    cal_ids = step_calendars(o, rep, data["calendars"])
    dept_ids = step_departments(o, rep, data["departments"])
    job_ids = step_jobs(o, rep, data["jobs"], dept_ids)

    emp_ids = step_employees(o, rep, data["employees"], dept_ids, job_ids, loc_ids, cal_ids, country_id)
    step_dept_managers(o, rep, data["departments"], dept_ids, emp_ids)
    step_users(o, rep, data["users"], {e["code"]: e["name"] for e in data["employees"]}, emp_ids)

    step_lunch(o, rep, data["lunch_categories"], data["lunch_suppliers"],
               data["lunch_products"], data["lunch_locations"])

    if step_cpm_installed(o, rep):
        cpm_project_ids = step_cpm_projects(o, rep, data["cpm_tasks"])
        user_ids_by_login = {}
        for r in data["users"]:
            uids = o.search("res.users", [("login", "=", r["login"])], active=False)
            if uids:
                user_ids_by_login[r["login"]] = uids[0]
        cpm_task_ids = step_cpm_tasks(o, rep, data["cpm_tasks"], cpm_project_ids,
                                      user_ids_by_login)
        step_cpm_dependencies(o, rep, data["cpm_dependencies"], cpm_task_ids)
        cpm_contractor_ids = step_cpm_contractors(o, rep, data["cpm_contractors"])
        cpm_vendor_ids = {}
        if step_cpm_purchase_installed(o):
            cpm_vendor_ids = step_cpm_vendors(o, rep, data["cpm_vendors"])
        else:
            print("  cpm: purchase is not installed -- skipping the material vendors")
        cpm_material_ids = step_cpm_materials(o, rep, data["cpm_materials"],
                                              cpm_vendor_ids)
        step_cpm_resources(o, rep, data["cpm_resources"], cpm_task_ids,
                           cpm_contractor_ids, cpm_material_ids,
                           data["cpm_contractors"], data["cpm_materials"])

    rep.show(args.apply)
    if not args.apply:
        print("re-run with --apply to write these changes.")


if __name__ == "__main__":
    main()
