#!/usr/bin/env python3
"""
seed.py -- seed the "Kula" dataset into a local Odoo 19 instance from the CSV
files next to this script.

    ./seed.py                 # dry run: report only, writes nothing
    ./seed.py --apply         # actually write
    ./seed.py --purge --apply # delete what this script created

Talking to Odoo over XML-RPC (stdlib only, no pip installs).

The dataset is one small cafe: three people (owner, cashier, barista), the menu
they sell and the pantry it comes from, and one day of takings in the register.
Those are the three things the owner opens Odoo for -- what is in stock, what
came in, who works here -- so they are the three axes the files cover:

    company.csv      the trading name, address and contact details
    departments.csv  which departments exist for this shop, and who runs them
    employees.csv    the people: badge number, name, job, contact, wage, manager
    users.csv        one login per person, and the role that login holds
    menu.csv         what the counter sells: POS category, price, description,
                     serving temperature and whether it is a best seller
    images/          one picture per menu item and category (placeholders)
    inventory.csv    what the menu is made from: cost and quantity on hand
    sales.csv        one day of takings: the orders, their lines and their times

Where a record belongs to a module rather than to the demo, the seed only looks
it up and fails loudly when it is missing: the role groups, the Counter
department and the Cashier/Barista job positions all come from
addons/kula_security, which owns the structure. The seed staffs it.

Notes for Odoo 19, which is what makes this script non-obvious:

  * hr.employee no longer stores department_id / job_id / job_title / wage. They
    are `related` fields forwarding to hr.version via hr.employee.version_id.
    They are still writable, so this script writes them on hr.employee and Odoo
    routes them to the version row. Never write them with raw SQL.
  * res.users.groups_id was renamed to group_ids.
  * hr.department.name is a translated (jsonb) column, so it must go through the
    ORM, never psql.
  * A pos.order and its lines carry their own totals. They are required columns
    that the *browser* computes before saving, so a seeded order has to send
    them, and `amount_tax = 0` is only true because the menu is tax-free.
  * A paid pos.order is permanent: Odoo refuses to write or unlink it. The day
    of takings therefore survives --purge, and so do the menu it sold and the
    register it was sold on. See step_purge.
"""

from __future__ import annotations

import argparse
import base64
import csv
import getpass
import os
import re
import sys
import urllib.error
import urllib.request
import xmlrpc.client
from datetime import date, datetime, time, timedelta, timezone
from time import monotonic, sleep

HERE = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(path):
    """.env -> os.environ, without overriding what the shell already set.

    Compose reads the same file for the containers (POSTGRES_*, ODOO_DB); the
    RPC side reads the ODOO_* keys, so `python3 seed/seed.py --apply` needs no
    flags on a local clone. The parser is deliberately the simple case the file
    is: KEY=VALUE per line, `#` comments, optional quotes. A missing .env is
    fine -- the environment or the flags then decide.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip().strip("'\""))


load_dotenv(os.path.join(os.path.dirname(HERE), ".env"))
DEFAULT_URL = os.environ.get("ODOO_URL", "http://localhost:8069")
DEFAULT_DB = os.environ.get("ODOO_DB", "development-odoo")
DEFAULT_USER = os.environ.get("ODOO_USER", "aryana@odoo.com")


def wait_for_odoo(url, timeout=600):
    """Wait until Odoo answers, because the first `podman-compose up` installs.

    The web container creates the database and installs the apps before it
    serves HTTP, so a seed run straight after `up -d` would otherwise fail on
    the first XML-RPC call. Poll the login page every few seconds.
    """
    print(f"waiting for Odoo on {url} ...", flush=True)
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/web/login", timeout=5) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        sleep(3)
    sys.exit(f"Odoo did not answer on {url} within {timeout}s")

# kula_security owns the org chart this dataset staffs: the three role groups,
# the Counter department and the two job positions. The seed installs it when it
# is missing and otherwise only reads it (see step_structure).
SEED_MODULES = ["kula_security"]

# The register. Not data: one shop has one counter, and the day of takings below
# is a day of *its* sessions. Created only when the database has no config.
COUNTER_CONFIG = "Kula Counter"

# The add-ons: the menu's second tier (the take-away plastic charge). One
# category holds them, and the register's "Add on" tile is built from it -- which
# is why this name is a constant and not just another row in menu.csv.
ADDON_CATEGORY = "Add On"

# menu.csv's `temperature` column becomes a product tag, so the serving
# temperature is visible in the backend even though no product variant is made
# for it. The menu's hot/ice items are the ones the counter can serve either way.
TEMPERATURE_TAGS = {
    "hot": "Hot",
    "ice": "Ice",
    "hot/ice": "Hot / Ice",
}

# One-time migration: the menu the CSVs carried before the printed card. Editing
# menu.csv stops a row being seeded, but a database that already has it keeps it
# -- and the register keeps selling it. These names are retired on every run, so
# an already-seeded database stops showing the old menu. Drop this list once
# every seeded database has been re-seeded with the card's menu.
RETIRED_MENU_PRODUCTS = [
    "Kopi", "Es Teh", "Sinom",
    "Extra Shot", "Es Batu", "Sambal Bawang", "Telor", "Sego Tok", "Cup Take Away",
]
RETIRED_MENU_CATEGORIES = ["Coffee", "Tea", "Juice"]

# Placeholder pictures for the menu, one file per product and per category,
# named after the record (see upload_menu_image).
IMAGES_DIR = os.path.join(HERE, "images")

MIN_WAGE = 4_800_000          # user's floor: Indonesian minimum wage
TZ_OFFSET = 7                 # Asia/Jakarta -- no DST, so a fixed offset is exact
TZ = "Asia/Jakarta"

# The one record with no natural key is the shift (a pos.session), so it is
# pinned by an ir.model.data marker instead: a re-run finds the day it already
# wrote and says `kept`.
MARKER_MODULE = "kula_seed"
SHIFT_MARKER = "shift"

# users.csv gives every login exactly one role. The groups themselves live in
# addons/kula_security; the seed never invents access rules of its own.
ROLE_GROUPS = {
    "owner": "kula_security.group_owner",
    "cashier": "kula_security.group_cashier",
    "barista": "kula_security.group_barista",
}

# Groups the seed is allowed to take back, on a re-run whose users.csv changed:
# the three roles, plus the kiosk marker both operators' roles imply.
# kula_security grants the marker *through* the roles, so moving somebody from
# cashier to owner has to take it back explicitly -- otherwise the owner would
# still be sent to the register on sign-in.
SEED_MANAGED_GROUPS = [*ROLE_GROUPS.values(), "kula_security.group_kiosk_only"]


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

    def ensure(self, model, key, values, active=True):
        """Look a record up by its natural key; create it if absent.

        Returns (record_id, 'created'|'updated'|'would-create'). In dry-run a
        brand new record gets a placeholder id, which never reaches Odoo
        because nothing is sent in dry-run.

        `active=False` looks among archived records too, which is what --purge
        leaves behind for the pantry (a product that has had stock cannot be
        deleted, only archived).
        """
        ids = self.search(model, [(k, "=", v) for k, v in key.items()], active=active)
        if ids:
            if self.apply:
                self.call(model, "write", [ids, values])
            return ids[0], "updated"
        if not self.apply:
            return f"<new {model} {key}>", "would-create"
        return self.call(model, "create", [{**key, **values}]), "created"

    def call_void(self, model, method, args=None):
        """Call a model method that returns nothing.

        Some of the methods the seed needs -- `pos.session.set_opening_control`,
        `pos.order.add_payment`, `stock.quant.action_apply_inventory` -- return
        None, and Odoo 19's XML-RPC marshaller rejects a None result *after* the
        call has run: the fault says the call worked, not that it failed. Any
        other fault is re-raised. Callers verify the effect afterwards, which is
        the only proof that the write landed.
        """
        try:
            return self.call(model, method, args)
        except xmlrpc.client.Fault as exc:
            if "cannot marshal None" not in str(exc):
                raise

    def marker(self, name):
        """The ir.model.data row a name points at, or None.

        Records with no natural key (the shift) are pinned this way: the marker
        is what a re-run finds, and what --purge leaves in place when it keeps
        the record the marker points at.
        """
        found = self.call(
            "ir.model.data", "search_read",
            [[("module", "=", MARKER_MODULE), ("name", "=", name)], ["model", "res_id"]],
        )
        return found[0] if found else None

    def set_marker(self, name, model, res_id):
        found = self.marker(name)
        if found:
            self.call("ir.model.data", "write", [[found["id"]], {"model": model, "res_id": res_id}])
        else:
            self.call("ir.model.data", "create",
                      [{"module": MARKER_MODULE, "name": name, "model": model, "res_id": res_id}])


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


def orders_from(rows):
    """Group sales.csv into orders: [(label, 'HH:MM', [(product, qty), ...])].

    Rows sharing the `order` label are one order, in file order -- which is also
    the order the lines reach the till in.
    """
    orders = []
    by_label = {}
    for r in rows:
        key = r["order"]
        if key not in by_label:
            by_label[key] = (r["time"], [])
            orders.append((key, by_label[key]))
        by_label[key][1].append((r["product"], float(r["qty"])))
    return orders


def jakarta_datetime(day, hhmm):
    """A CSV time ("08:40", Jakarta) as the naive UTC datetime Odoo stores."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    local = datetime.combine(day, time(hour, minute), tzinfo=timezone(timedelta(hours=TZ_OFFSET)))
    return local.astimezone(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def today_in_jakarta():
    return (datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET)).date()


def validate(employees, departments):
    """Fail loudly before touching the database."""
    problems = []
    dept_names = {d["name"] for d in departments}
    codes = {e["code"] for e in employees}

    for what, seen in (("badge number", [e["code"] for e in employees]),
                       ("work email", [e["work_email"] for e in employees]),
                       ("name", [e["name"] for e in employees])):
        # Names are unique because an employee is adopted by name when the badge
        # number is not on file yet (see step_employees): two rows called the
        # same thing would make that ambiguous.
        dupes = {v for v in seen if seen.count(v) > 1}
        if dupes:
            problems.append(f"duplicate {what}: {sorted(dupes)}")

    for e in employees:
        tag = f"{e['code']} ({e['name']})"
        if not e["code"] or not e["name"]:
            problems.append(f"{tag}: badge number and name are both required")
        if not e["department"]:
            problems.append(f"{tag}: department is required")
        if e["department"] and e["department"] not in dept_names:
            problems.append(f"{tag}: {e['department']!r} is not in departments.csv")
        if e["manager_code"] and e["manager_code"] not in codes:
            problems.append(f"{tag}: unknown manager {e['manager_code']!r}")
        if e["manager_code"] == e["code"]:
            problems.append(f"{tag}: cannot manage themselves")
        try:
            wage = int(e["wage"])
        except ValueError:
            problems.append(f"{tag}: wage {e['wage']!r} is not a number")
            continue
        if wage < MIN_WAGE:
            problems.append(f"{tag}: wage Rp {wage:,} is below the Rp {MIN_WAGE:,} floor")

    for d in departments:
        if not d["name"]:
            problems.append("department row with an empty name")
        if d["manager_code"] and d["manager_code"] not in codes:
            problems.append(f"department {d['name']!r}: unknown manager {d['manager_code']!r}")
        if d["name"] and d["name"] not in {e["department"] for e in employees}:
            problems.append(f"department {d['name']!r}: nobody in employees.csv sits in it")

    if problems:
        print("VALIDATION FAILED -- no changes made:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


def validate_sales(sales, menu):
    """Cross-check the day of takings before anything is written.

    A typo in the product column would otherwise fail at write time with a
    message about a missing product id instead of about the CSV row.
    """
    problems = []
    menu_names = {r["name"] for r in menu}
    seen_lines = set()
    for r in sales:
        tag = f"order {r['order']!r} line {r['product']!r}"
        if not r["order"]:
            problems.append("sale line with an empty order label")
        if r["product"] not in menu_names:
            problems.append(f"{tag}: not in menu.csv")
        try:
            if float(r["qty"]) <= 0:
                problems.append(f"{tag}: qty must be > 0")
        except ValueError:
            problems.append(f"{tag}: qty {r['qty']!r} is not a number")
        try:
            hour, minute = (int(part) for part in r["time"].split(":"))
            datetime.combine(date.today(), time(hour, minute))
        except ValueError:
            problems.append(f"{tag}: time {r['time']!r} is not HH:MM")
        line = (r["order"], r["product"])
        if line in seen_lines:
            problems.append(f"{tag}: the same product twice in one order")
        seen_lines.add(line)

    for label, (at_time, _lines) in orders_from(sales):
        times = {r["time"] for r in sales if r["order"] == label}
        if len(times) > 1:
            problems.append(f"order {label!r}: one order has one time, found {sorted(times)}")

    if problems:
        print("SALES VALIDATION FAILED -- no changes made:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


def validate_menu(menu):
    """Cross-check the menu before anything is written.

    A category typo or a price that is not a whole rupiah would otherwise reach
    Odoo as a product with the wrong shape. The take-away plastic charge is the
    reason the Add On category is required: the register's Add on tile is built
    from it, and no menu item may land outside a category.
    """
    problems = []
    names = [r["name"] for r in menu]
    dupes = {name for name in names if names.count(name) > 1}
    if dupes:
        problems.append(f"duplicate product name: {sorted(dupes)}")
    if ADDON_CATEGORY not in {r["pos_category"] for r in menu}:
        problems.append(f"no {ADDON_CATEGORY!r} category row")

    for r in menu:
        tag = f"{r['name'] or '<unnamed>'!r}"
        if not r["name"]:
            problems.append("a menu row has no name")
        if not r["pos_category"]:
            problems.append(f"{tag}: POS category is required")
        try:
            if int(r["price"]) < 0:
                problems.append(f"{tag}: price must not be negative")
        except ValueError:
            problems.append(f"{tag}: price {r['price']!r} is not a whole number")
        if r["temperature"].lower() not in {*TEMPERATURE_TAGS, ""}:
            problems.append(f"{tag}: unknown temperature {r['temperature']!r} "
                            f"(expected {', '.join(sorted(TEMPERATURE_TAGS))} or empty)")
        if r["best_seller"].lower() not in {"yes", "no"}:
            problems.append(f"{tag}: best_seller {r['best_seller']!r} is not yes/no")

    if problems:
        print("MENU VALIDATION FAILED -- no changes made:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)


def resolve_groups(o, xmlids):
    """Map 'module.name' group xmlids to res.groups ids, failing loudly."""
    out = {}
    for x in sorted(xmlids):
        mod, _, name = x.partition(".")
        found = o.call(
            "ir.model.data", "search_read",
            [[("module", "=", mod), ("name", "=", name), ("model", "=", "res.groups")],
             ["res_id"]],
        )
        if not found:
            sys.exit(f"users.csv references unknown group xmlid {x!r}")
        out[x] = found[0]["res_id"]
    return out


# --------------------------------------------------------------------------- #
# steps
# --------------------------------------------------------------------------- #
def step_company(o, rep):
    row = load_csv("company.csv")[0]
    if o.apply:
        o.call("res.company", "write", [[1], {
            "name": row["name"], "email": row["email"], "phone": row["phone"],
        }])
    # company name is related to partner_id.name; set the address on the partner.
    # The timezone goes there too: it is the shop's, and Odoo reads it as the
    # company default wherever a record has no timezone of its own.
    partner_id = o.call("res.company", "read", [[1], ["partner_id"]])[0]["partner_id"][0]
    if o.apply:
        o.call("res.partner", "write", [[partner_id],
                                        {"city": row["city"], "street": row["street"], "tz": TZ}])
    rep.add("company", "updated" if o.apply else "would-update")


def step_localization(o, rep):
    """Kula's country and currency, for a database the stack installed without
    localizing.

    A database created by the compose command has no country and a USD company,
    which makes kula_pos_layout's whole-rupiah data file a silent no-op (it
    searches an *active* IDR). This is what the orb's setup does before the
    addons load; on a database that is already Indonesian it writes nothing.
    """
    country = o.search("res.country", [("code", "=", "ID")], limit=1)
    if not country:
        sys.exit("no Indonesia (ID) country record -- is base installed?")
    idr = o.search("res.currency", [("name", "=", "IDR")], limit=1, active=False)
    if not idr:
        sys.exit("no IDR currency record -- is base installed?")
    country_id, idr_id = country[0], idr[0]

    currency = o.call("res.currency", "read",
                      [[idr_id], ["active", "rounding", "decimal_places"]])[0]
    if not currency["active"]:
        if o.apply:
            o.call("res.currency", "write", [[idr_id], {"active": True}])
        rep.add("IDR", "activated" if o.apply else "would-activate")
    if float(currency["rounding"]) != 1 or int(currency["decimal_places"]) != 0:
        if o.apply:
            o.call("res.currency", "write",
                   [[idr_id], {"rounding": 1, "decimal_places": 0}])
        rep.add("IDR rounding", "whole rupiah" if o.apply else "would-set")

    company = o.call("res.company", "read", [[1], ["country_id", "currency_id"]])[0]
    if ((company["country_id"] or [None])[0] != country_id
            or (company["currency_id"] or [None])[0] != idr_id):
        if o.apply:
            o.call("res.company", "write",
                   [[1], {"country_id": country_id, "currency_id": idr_id}])
        rep.add("company localization", "Indonesia / IDR" if o.apply else "would-set")

    admin = o.search("res.users", [("login", "=", o.user)], limit=1)
    if admin:
        tz = o.call("res.users", "read", [[admin[0]], ["tz"]])[0]["tz"]
        if tz != TZ:
            if o.apply:
                o.call("res.users", "write", [[admin[0]], {"tz": TZ}])
            rep.add("admin timezone", TZ if o.apply else "would-set")


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


def step_structure(o, employees, departments):
    """Resolve the org chart kula_security owns: the department each person sits
    in and the job position they hold.

    The seed never creates either. A second "Counter", or a "Cashier" outside
    the one the module defines, would be a different chart than the role groups
    are wired to, and the Employees app would show two of everything.
    """
    dept_ids = {}
    for name in sorted({e["department"] for e in employees} | {d["name"] for d in departments}):
        ids = o.search("hr.department", [("name", "=", name)])
        if not ids:
            sys.exit(f"no {name!r} department -- is kula_security installed?")
        dept_ids[name] = ids[0]

    job_ids = {}
    for e in employees:
        if not e["job"] or e["job"] in job_ids:
            continue
        ids = o.search("hr.job", [("name", "=", e["job"]),
                                  ("department_id", "=", dept_ids[e["department"]])])
        if not ids:
            sys.exit(f"no {e['job']!r} job position in {e['department']!r} "
                     "-- is kula_security installed?")
        job_ids[e["job"]] = ids[0]
    return dept_ids, job_ids


def step_employees(o, rep, rows, dept_ids, job_ids):
    """One employee per row, keyed on the badge number.

    A row whose *name* is already on file without a badge number is adopted
    instead of duplicated: .agents/setup staffed this counter by name before
    the seeder existed, and a warm orb would otherwise grow a second Kula Owner.
    """
    ids = {}
    for r in rows:
        values = {
            "name": r["name"],
            "work_email": r["work_email"],
            "mobile_phone": r["mobile_phone"],
            "job_title": r["title"],
            "department_id": dept_ids[r["department"]],
            "tz": TZ,
            "wage": int(r["wage"]),
        }
        if r["job"]:
            values["job_id"] = job_ids[r["job"]]
        if not o.search("hr.employee", [("barcode", "=", r["code"])], active=False):
            on_file = o.search("hr.employee", [("name", "=", r["name"])], active=False)
            barcodeless = [e for e in on_file
                           if not o.call("hr.employee", "read", [[e], ["barcode"]])[0]["barcode"]]
            if barcodeless:
                if o.apply:
                    o.call("hr.employee", "write", [barcodeless, {"barcode": r["code"]}])
                rep.add("employees adopted (name already on file)",
                        "adopted" if o.apply else "would-adopt", len(barcodeless))
        rid, st = o.ensure("hr.employee", {"barcode": r["code"]}, values)
        ids[r["code"]] = rid
        rep.add("employees", st)

    for r in rows:
        if not r["manager_code"]:
            continue
        if o.apply:
            o.call("hr.employee", "write", [[ids[r["code"]]], {"parent_id": ids[r["manager_code"]]}])
        rep.add("reporting lines", "set" if o.apply else "would-set")
    return ids


def step_department_managers(o, rep, rows, dept_ids, emp_ids):
    for r in rows:
        if not r["manager_code"]:
            continue
        if o.apply:
            o.call("hr.department", "write",
                   [[dept_ids[r["name"]]], {"manager_id": emp_ids[r["manager_code"]]}])
        rep.add("department managers", "set" if o.apply else "would-set")


def step_users(o, rep, rows, emp_names, emp_ids):
    """Create a login per employee and bind it to the existing HR record.

    hr's res.users.create only spawns a *new* employee when you pass
    create_employee / create_employee_id. We pass create_employee_id with the
    employee we already seeded, so the user binds to it instead of duplicating it.

    Each row carries one `role`, not a list of groups: the three roles in
    addons/kula_security are the access model, and the seed reconciles what it
    handed out before (SEED_MANAGED_GROUPS) so a role that changed on a re-run
    takes its old grants away instead of leaving them behind.
    """
    group_ids = resolve_groups(o, set(SEED_MANAGED_GROUPS))
    managed_ids = {group_ids[x] for x in SEED_MANAGED_GROUPS}

    for r in rows:
        code, login = r["employee_code"], r["login"]
        emp_id = emp_ids[code]
        real_emp = not isinstance(emp_id, str)
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
            uid = o.call("res.users", "create", [{
                "name": name, "login": login, "email": login,
                "password": r["password"], "tz": TZ,
                "create_employee_id": emp_id if real_emp else False,
                "group_ids": [(6, 0, [group_ids[ROLE_GROUPS[r["role"]]]])],
            }])
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

        # The role and everything it implies is the whole desired set; any other
        # seed-managed group still on the user is a stale grant.
        role_id = group_ids[ROLE_GROUPS[r["role"]]]
        role_implied = set(o.call(
            "res.groups", "read", [[role_id], ["all_implied_ids"]],
        )[0]["all_implied_ids"])
        keep = {role_id} | role_implied
        cur_groups = set(o.call("res.users", "read", [[uid], ["group_ids"]])[0]["group_ids"])
        stale = (cur_groups & managed_ids) - keep
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


def retire_old_menu(o, rep):
    """Take the previous seed's menu off the till, on a database that has it.

    A product is archived rather than deleted: a paid pos.order line points at
    it, and Odoo refuses to unlink a product with history. Archiving takes it
    out of the register (`available_in_pos` and `active` both go false), which
    is what "no longer sold" means here. The old categories are then empty and
    are deleted, unless a register session is open -- Odoo refuses to unlink a
    POS category while one is, and an empty category does not show on the kiosk
    anyway (core filters out categories with no products).
    """
    for name in RETIRED_MENU_PRODUCTS:
        ids = o.search("product.template", [("name", "=", name)], active=False)
        if not ids:
            continue
        fields = o.call("product.template", "read",
                        [ids, ["available_in_pos", "sale_ok", "active", "pos_categ_ids"]])
        stale = [row for row in fields
                 if row["available_in_pos"] or row["sale_ok"] or row["active"]
                 or row["pos_categ_ids"]]
        if not stale:
            rep.add("retired menu products", "already-retired", len(ids))
            continue
        if o.apply:
            o.call("product.template", "write", [ids, {
                "pos_categ_ids": [(5, 0, 0)],
                "available_in_pos": False,
                "sale_ok": False,
                "active": False,
            }])
        rep.add("retired menu products", "archived" if o.apply else "would-archive", len(stale))

    for name in RETIRED_MENU_CATEGORIES:
        ids = o.search("pos.category", [("name", "=", name)])
        if not ids:
            continue
        if not o.apply:
            rep.add("retired menu categories", "would-delete", len(ids))
            continue
        try:
            o.call("pos.category", "unlink", [ids])
            rep.add("retired menu categories", "deleted", len(ids))
        except xmlrpc.client.Fault as exc:
            if "while a session is still opened" not in str(exc):
                raise
            rep.add("retired menu categories", "kept (open session)", len(ids))
            print(f"  note: {name} is empty but could not be deleted while a register "
                  "session is open; the kiosk does not show it")


def step_menu(o, rep, rows):
    """The counter's menu: a product per row, filed under its POS category.

    Prices are what the customer pays, so the menu carries no sales tax. The
    chart this database starts on puts a 15% US tax on new products, and leaving
    it on would charge Rp 11.500 for the Rp 10.000 kopi the card shows. (A
    price-included tax is the other honest answer; dropping it keeps the receipt
    equal to the menu, which is what a counter's price list means here.)

    The POS category column is a contract, not a convenience: the register opens
    on a grid of category tiles, so a product with no category has no tile to be
    tapped and cannot be sold. The categories are created from that same column,
    in first-appearance order, which is why `menu.csv` is the only place a menu
    item has to be registered. `sequence` and `pos_sequence` preserve the order
    the menu is printed in, rather than letting Odoo fall back to the alphabet.

    The menu's other columns are presentation, not inventory: `description`
    becomes `public_description` (the product popup on the register shows it),
    `best_seller` becomes `is_favorite` (the star Odoo already renders), and
    `temperature` becomes a product tag -- a tag rather than a variant, so hot
    and iced drinks stay one product at one price.

    Each product and category is also given a picture, when it has none yet and
    a file for it exists under seed/images/. Pictures are optional and never
    overwritten -- see upload_menu_image.
    """
    category_names = list(dict.fromkeys(r["pos_category"] for r in rows))
    cat_ids = {}
    for index, name in enumerate(category_names, start=1):
        rid, st = o.ensure("pos.category", {"name": name}, {"sequence": index * 10})
        cat_ids[name] = rid
        rep.add("menu categories", st)
        upload_menu_image(o, rep, "pos.category", rid, "image_512",
                          f"categories/{slug(name)}.png")

    tag_ids = {}
    for label in sorted({TEMPERATURE_TAGS[r["temperature"].lower()]
                         for r in rows if r["temperature"]}):
        rid, _st = o.ensure("product.tag", {"name": label}, {})
        tag_ids[label] = rid

    ids = {}
    for index, r in enumerate(rows, start=1):
        tags = [tag_ids[TEMPERATURE_TAGS[r["temperature"].lower()]]] if r["temperature"] else []
        tmpl, st = o.ensure("product.template", {"name": r["name"]}, {
            "type": "consu",
            "list_price": float(r["price"]),
            "available_in_pos": True,
            "sale_ok": True,
            "public_description": r["description"] or False,
            "is_favorite": r["best_seller"].lower() == "yes",
            "pos_sequence": index * 10,
            "pos_categ_ids": [(6, 0, [cat_ids[r["pos_category"]]])],
            "product_tag_ids": [(6, 0, tags)],
            "taxes_id": [(6, 0, [])],
        })
        rep.add("menu products", st)
        if isinstance(tmpl, str):
            # dry run: ensure() returned a placeholder id, nothing exists yet
            ids[r["name"]] = tmpl
            continue
        upload_menu_image(o, rep, "product.template", tmpl, "image_1920",
                          f"products/{slug(r['name'])}.png")
        variants = o.search("product.product", [("product_tmpl_id", "=", tmpl)])
        if not variants:
            sys.exit(f"menu product {r['name']!r}: template {tmpl} has no variant")
        # the till sells the variant, not the template -- a pos.order.line wants
        # a product.product id
        ids[r["name"]] = variants[0]
    return ids, cat_ids


def slug(name):
    """A record's name as the file name its picture is looked up under."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def upload_menu_image(o, rep, model, record_id, field, relative_path):
    """Give a record its picture, once.

    `field` is the model's own image field -- product.template.image_1920
    (every smaller size is derived from it) and pos.category.image_512, which is
    what the register's `/web/image` URLs read.

    Two rules:

    * No file, no picture. The record keeps whatever Odoo shows for an image-less
      product, and a card with a placeholder is a better lie than a card with
      somebody else's photo.
    * An image that is already there is never replaced. The shop's own photo,
      uploaded through Products, is not something a demo seeder gets to
      overwrite -- and this is what makes re-running the seed safe.
    """
    if not o.apply or not isinstance(record_id, int):
        rep.add("menu images", "would-upload")
        return
    path = os.path.join(IMAGES_DIR, relative_path)
    if not os.path.isfile(path):
        rep.add("menu images", "no file")
        return
    if o.call(model, "read", [[record_id], [field]])[0][field]:
        rep.add("menu images", "kept")
        return
    with open(path, "rb") as fh:
        payload = base64.b64encode(fh.read()).decode()
    o.call(model, "write", [[record_id], {field: payload}])
    rep.add("menu images", "uploaded")


def report_uncategorized(o, rep):
    """Say whether every product the till can sell has a POS category.

    The register's landing view is a grid of categories, so a POS-available
    product without one is reachable only through the fallback "Other" tile
    (see category_home.xml). Reported rather than enforced: the database is the
    shop's to edit, and refusing to seed because somebody added a product in the
    backend would be the wrong trade. Silence here is the "no such product"
    answer, which is what a correct menu looks like.
    """
    rows = o.call("product.template", "search_read",
                  [[("available_in_pos", "=", True), ("pos_categ_ids", "=", False)],
                   ["name"]])
    if not rows:
        rep.add("uncategorized POS products", "none")
        return
    rep.add("uncategorized POS products", "found", len(rows))
    print("\n  POS products with no POS category -- they show under 'Other' on the")
    print("  register. File them in a category (menu.csv does it for seeded items):")
    for row in rows:
        print(f"    - {row['name']}")


def step_register(o, rep, category_ids):
    """The register's own layout: the kiosk home, and which category is add-ons.

    A step of its own rather than a line in step_sales, where the config is
    otherwise created: step_sales returns early once the day of takings exists,
    and a database seeded before this layout did is exactly that case -- it would
    keep whatever the field held before, since a changed default only reaches
    records created afterwards.
    """
    addon_id = category_ids.get(ADDON_CATEGORY)
    if addon_id is None:
        sys.exit(f"menu.csv has no {ADDON_CATEGORY!r} category: the register's "
                 "'Add on' tile is built from that category")
    _, st = o.ensure("pos.config", {"name": COUNTER_CONFIG}, {
        "kula_category_nav": "kiosk",
        "kula_addon_category_id": addon_id,
    })
    rep.add("register layout (pos.config)", st)


def step_pantry(o, rep, rows):
    """The pantry: a storable product per row, with its cost and the quantity on
    hand at WH/Stock.

    On-hand is set the way a stocktake sets it -- an inventory adjustment on the
    quant (`inventory_quantity` + action_apply_inventory) -- because a stock move
    would have to pretend a delivery arrived, from a vendor this dataset does not
    have.
    """
    uom_ids = {}
    for name in sorted({r["unit"] for r in rows}):
        ids = o.search("uom.uom", [("name", "=", name)])
        if not ids:
            sys.exit(f"inventory.csv: unknown unit {name!r}")
        uom_ids[name] = ids[0]

    loc = o.search("ir.model.data", [("module", "=", "stock"),
                                     ("name", "=", "stock_location_stock")])
    if not loc:
        sys.exit("stock.stock_location_stock not found -- is the stock app installed?")
    location_id = o.call("ir.model.data", "read", [loc, ["res_id"]])[0]["res_id"]

    for r in rows:
        tmpl, st = o.ensure("product.template", {"name": r["name"]}, {
            "type": "consu",
            "is_storable": True,
            "uom_id": uom_ids[r["unit"]],
            # The pantry is what the shop buys, not what it sells: cost is the
            # number that matters, and the sales price is left at zero rather
            # than Odoo's default of 1.00.
            "standard_price": float(r["cost"]),
            "list_price": 0.0,
            "sale_ok": False,
            "available_in_pos": False,
            # A purge can only archive a pantry item (see step_purge), so a
            # later --apply adopts it by name and puts it back on the shelf.
            "active": True,
        }, active=False)
        rep.add("pantry products", st)
        if isinstance(tmpl, str) or not o.apply:
            # dry run: nothing is written, and an on-hand figure that is already
            # on file is left alone -- setting it is a stocktake, not a report
            rep.add("pantry stock on hand", "would-set")
            continue

        pids = o.search("product.product", [("product_tmpl_id", "=", tmpl)])
        if not pids:
            sys.exit(f"pantry product {r['name']!r}: template {tmpl} has no variant")
        pid = pids[0]
        qty = float(r["stock"])
        quant = o.search("stock.quant", [("product_id", "=", pid),
                                         ("location_id", "=", location_id)])
        if quant:
            on_hand = o.call("stock.quant", "read", [quant, ["quantity"]])[0]["quantity"]
            if abs(on_hand - qty) <= 1e-6:
                # Already counted. Re-applying the same figure would write a
                # zero-quantity inventory move every run, which is noise in the
                # product's history rather than a correction.
                rep.add("pantry stock on hand", "already-counted")
                continue
            o.call("stock.quant", "write", [quant, {"inventory_quantity": qty}])
        else:
            o.call("stock.quant", "create", [{
                "product_id": pid, "location_id": location_id, "inventory_quantity": qty,
            }])
            quant = o.search("stock.quant", [("product_id", "=", pid),
                                             ("location_id", "=", location_id)])
        o.call_void("stock.quant", "action_apply_inventory", [quant])
        applied = o.call("stock.quant", "read", [quant, ["quantity"]])
        if any(abs(row["quantity"] - qty) > 1e-6 for row in applied):
            sys.exit(f"pantry product {r['name']!r}: on hand is "
                     f"{applied[0]['quantity']}, expected {qty}")
        rep.add("pantry stock on hand", "set")


def rebind_the_day(o, rep, session_id, cashier_login):
    """Repair the kept day's attribution when the people were re-created.

    The day cannot be deleted -- Odoo refuses a paid order -- but the people can:
    a --purge deletes them and Odoo nulls the orders' cashier columns along with
    them, so a later --apply would leave a day of takings rung up by nobody. The
    write changes no state, only who the sales are attributed to.

    Only *missing* attribution is repaired, never a sale that names somebody
    else. The register attributes every sale to the person operating it (issue
    #9, kula_pos_layout's models/pos_order.py), so an administrator's or the
    owner's sale can sit in the same session as the day's, and handing it to the
    cashier would be a lie about who rang it up. Two rows need the repair: a row
    the purge emptied (user_id nulled) is the day's, i.e. the cashier's; a row
    with an operator but no employee -- a sale made before the register
    attributed one, and the module cannot repair those itself, see
    pos_order.py -- gets that operator's employee.

    The shift itself is repaired the same way, and only when it is empty: it is
    the day's shift because this seed created it, but pos_hr's employee_id is
    what the sales reports group by, and the account that ran the seed is not
    who worked the counter.
    """
    if not cashier_login:
        return
    cashier = o.search("res.users", [("login", "=", cashier_login)], limit=1)
    if not cashier:
        return
    values = {"user_id": cashier[0]}
    has_pos_hr = bool(o.search("ir.module.module", [("name", "=", "pos_hr"),
                                                  ("state", "=", "installed")]))
    if has_pos_hr:
        employee = o.search("hr.employee", [("user_id", "=", cashier[0])], limit=1)
        if employee:
            values["employee_id"] = employee[0]
            session = o.call("pos.session", "read", [[session_id], ["employee_id"]])[0]
            if session["employee_id"]:
                rep.add("the shift's cashier", "already-set")
            else:
                if o.apply:
                    o.call("pos.session", "write", [[session_id], {"employee_id": employee[0]}])
                rep.add("the shift's cashier", "re-bound" if o.apply else "would-rebind")

    order_ids = o.search("pos.order", [("session_id", "=", session_id)])
    rows = o.call("pos.order", "read", [order_ids, ["user_id", "employee_id"]])
    plan = {}
    for row in rows:
        if not row["user_id"]:
            plan[row["id"]] = values
        elif not row["employee_id"]:
            employee = o.search("hr.employee", [("user_id", "=", row["user_id"][0])], limit=1)
            if employee:
                plan[row["id"]] = {"employee_id": employee[0]}
    if not plan:
        rep.add("the day's cashier", "already-set")
        return
    if o.apply:
        for order_id, order_values in plan.items():
            o.call("pos.order", "write", [[order_id], order_values])
    rep.add("the day's cashier", "re-bound" if o.apply else "would-rebind", len(plan))


def step_sales(o, rep, rows, menu_ids, cashier_login=None):
    """The day's takings: one shift, the orders in it, and their payments.

    The shift is left *open*, the way a shop's day is while it is trading: the
    register resumes it, POS reporting already counts it, and closing it --
    which the cashier does at the end of the day anyway -- is what posts the
    accounting entries. Both are core actions (set_opening_control,
    action_pos_session_closing_control), never a state write: a session whose
    state was written by hand has no stop_at, and Odoo reads that field when it
    computes the config's last session.

    The day is dated today in Jakarta, at the times sales.csv names, so the day
    on screen is the day the shop is having, and the orders carry the cashier's
    name rather than the account that ran the seed -- the till's sales are the
    cashier's work, and that is what the Orders list shows.

    Nothing here reconciles: a paid pos.order cannot be written or deleted
    afterwards, so a re-run reports `kept` and leaves the day as it is. Changing
    sales.csv only shows up on a database that has not got the day yet.
    """
    orders = orders_from(rows)
    marker = o.marker(SHIFT_MARKER)
    if marker and marker["res_id"]:
        rebind_the_day(o, rep, marker["res_id"], cashier_login)
        rep.add("the day's takings (shift, orders)", "kept", len(orders))
        return

    config_id, st = o.ensure("pos.config", {"name": COUNTER_CONFIG}, {})
    rep.add("register (pos.config)", st)
    if not o.apply or isinstance(config_id, str):
        rep.add("the day's takings (shift, orders)", "would-create", len(orders))
        return

    config = o.call("pos.config", "read", [[config_id], ["payment_method_ids"]])[0]
    methods = config["payment_method_ids"]
    if not methods:
        sys.exit(f"{COUNTER_CONFIG} has no payment method -- install kula_pos_layout, or "
                 "set one in Point of Sale / Configuration / Payment Methods")

    prices = {name: o.call("product.product", "read", [[pid], ["lst_price"]])[0]["lst_price"]
              for name, pid in menu_ids.items()}
    cashier = o.search("res.users", [("login", "=", cashier_login)], limit=1) if cashier_login else []
    # pos_hr swaps the Orders list's Cashier column for pos.order.employee_id, so
    # the day carries the employee too when that module is in. `employee_id` is
    # the module's field: writing it on a database without pos_hr is an error,
    # hence the check.
    cashier_employee = []
    if cashier and o.search("ir.module.module", [("name", "=", "pos_hr"),
                                                 ("state", "=", "installed")]):
        cashier_employee = o.search("hr.employee", [("user_id", "=", cashier[0])], limit=1)

    session_values = {"config_id": config_id}
    # The shift is the cashier's, like the orders in it. Odoo attributes a
    # session to the user that created it (user_id, "Opened By"), and the
    # account that runs the seed is the administrator's, so the employee has to
    # be named for the day to read as the cashier's work.
    if cashier_employee:
        session_values["employee_id"] = cashier_employee[0]
    session_id = o.call("pos.session", "create", [session_values])
    # Opening the register is what sets start_at and the session's name; 0 is
    # the cash in the drawer before the first sale. It returns nothing, so the
    # state afterwards is what says it worked.
    o.call_void("pos.session", "set_opening_control", [[session_id], 0, ""])
    state = o.call("pos.session", "read", [[session_id], ["state"]])[0]["state"]
    if state != "opened":
        sys.exit(f"the register did not open: session {session_id} is {state!r}")
    rep.add("the shift (pos.session)", "opened")

    day = today_in_jakarta()
    for index, (label, (at_time, lines)) in enumerate(orders):
        total = 0.0
        commands = []
        for product, qty in lines:
            subtotal = qty * prices[product]
            total += subtotal
            commands.append((0, 0, {
                "product_id": menu_ids[product],
                "qty": qty,
                "price_unit": prices[product],
                "price_subtotal": subtotal,
                "price_subtotal_incl": subtotal,
            }))
        values = {
            "session_id": session_id,
            "date_order": jakarta_datetime(day, at_time),
            "user_id": cashier[0] if cashier else False,
            "lines": commands,
            # the browser computes these; they are required, so we send them
            "amount_total": total,
            "amount_tax": 0.0,
            "amount_paid": total,
            "amount_return": 0.0,
        }
        if cashier_employee:
            values["employee_id"] = cashier_employee[0]
        order_id = o.call("pos.order", "create", [values])
        # One payment per order, cycling through whatever the register accepts:
        # which methods exist is kula_pos_layout's business, not the seed's.
        method_id = methods[index % len(methods)]
        o.call_void("pos.order", "add_payment", [[order_id], {
            "amount": total, "payment_method_id": method_id, "pos_order_id": order_id,
        }])
        paid = o.call("pos.order", "read", [[order_id], ["amount_paid"]])[0]["amount_paid"]
        if abs(paid - total) > 1e-6:
            sys.exit(f"order {label}: the payment did not land "
                     f"(paid {paid}, expected {total})")
        o.call("pos.order", "action_pos_order_paid", [[order_id]])
        rep.add("orders", "created")
    o.set_marker(SHIFT_MARKER, "pos.session", session_id)


def step_purge(o, rep, data):
    """Take back what this seed created, as far as Odoo allows.

    The people go first: their employees are deleted before their users, because
    hr_employee.user_id is RESTRICT -- a user an employee still points at will
    not unlink, and would silently survive.

    Three things stay, and the report prints the reason:

      * the register's config -- a shop has one counter, and the shift's session
        points at it;
      * the pantry items, archived rather than deleted: a product that has ever
        had stock keeps its quants (product_id is RESTRICT on a quant, and no
        group is allowed to unlink one), and those quants are what stop the
        delete. They are counted to zero on the way out, and a later --apply
        adopts them by name and counts them back in;
      * the day of takings, with the menu it sold and the categories it sold
        under: a paid pos.order is permanent (Odoo refuses to write or unlink
        one), and the orders reference the menu rather than owning it.

    The shift's marker stays with the day, so a later --apply adds nothing
    beside the history that survived.
    """
    def drop(model, domain, label):
        ids = o.search(model, domain, active=False)
        if ids:
            if o.apply:
                o.call(model, "unlink", [ids])
            rep.add(label, "deleted" if o.apply else "would-delete", len(ids))

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
        if still and o.apply:
            o.call("hr.employee", "write", [still, {"user_id": False}])
        if not o.apply:
            rep.add("users (logins)", "would-delete", len(ids))
            continue
        try:
            o.call("res.users", "unlink", [ids])
            rep.add("users (logins)", "deleted")
        except Exception as exc:
            # a user owning records cannot be deleted (ir_cron, utm_campaign, ...)
            o.call("res.users", "write", [ids, {"active": False}])
            rep.add("users (logins)", "deactivated")
            print(f"  note: could not delete {r['login']}, deactivated instead: "
                  f"{str(exc).splitlines()[0][:120]}")

    # The pantry: what the shop buys. A product that has ever had stock cannot
    # be deleted -- product_id on a quant is RESTRICT and no group is allowed to
    # unlink a quant at all ("Quants are auto-deleted when appropriate", says
    # Odoo) -- so the take-back is Odoo's own answer for it: count the stock to
    # zero, drop the finished moves, and archive the item. A later --apply
    # adopts it by name (archived or not) and counts it back in.
    for r in data["inventory"]:
        tids = o.search("product.template", [("name", "=", r["name"])], active=False)
        if not tids:
            continue
        pids = o.search("product.product", [("product_tmpl_id", "in", tids)], active=False)
        quants = o.search("stock.quant", [("product_id", "in", pids)])
        if quants:
            if o.apply:
                o.call("stock.quant", "write", [quants, {"inventory_quantity": 0}])
                o.call_void("stock.quant", "action_apply_inventory", [quants])
            rep.add("pantry stock on hand", "counted to zero" if o.apply else "would-zero",
                    len(quants))
        moves = o.search("stock.move", [("product_id", "in", pids)], active=False)
        if moves:
            if o.apply:
                # a done move will not unlink ("going back in time"); draft is
                # the one state it will let go of
                o.call("stock.move", "write", [moves, {"state": "draft"}])
                o.call("stock.move", "unlink", [moves])
            rep.add("pantry stock moves", "deleted" if o.apply else "would-delete", len(moves))
        if o.apply:
            o.call("product.template", "write", [tids, {"active": False}])
        rep.add("pantry products", "archived" if o.apply else "would-archive", len(tids))

    print("  kept: the register's config, the pantry items (archived, not deleted), and the "
          "day of takings with the menu it sold (Odoo refuses to delete a paid order)")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Seed the Kula dataset into Odoo.")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--password", default=os.environ.get("ODOO_PASSWORD"))
    ap.add_argument("--apply", action="store_true", help="actually write (default is a dry run)")
    ap.add_argument("--purge", action="store_true", help="delete what this script created")
    ap.add_argument("--no-modules", action="store_true", help="do not install kula_security")
    args = ap.parse_args()

    if not args.password:
        args.password = getpass.getpass(f"password for {args.user}: ")

    data = {
        "company": load_csv("company.csv"),
        "departments": load_csv("departments.csv"),
        "employees": load_csv("employees.csv"),
        "users": load_csv("users.csv"),
        "menu": load_csv("menu.csv"),
        "inventory": load_csv("inventory.csv"),
        "sales": load_csv("sales.csv"),
    }

    validate(data["employees"], data["departments"])

    # users.csv must line up with employees.csv
    codes = {e["code"] for e in data["employees"]}
    unknown = sorted({u["employee_code"] for u in data["users"]} - codes)
    if unknown:
        sys.exit(f"users.csv references unknown badge numbers: {unknown}")
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

    validate_menu(data["menu"])
    validate_sales(data["sales"], data["menu"])
    categories = len({r["pos_category"] for r in data["menu"]})
    print(f"validated {len(data['employees'])} employees, {len(data['departments'])} departments, "
          f"{len(data['menu'])} menu products in {categories} categories, "
          f"{len(data['inventory'])} pantry items, "
          f"{len(orders_from(data['sales']))} orders -- all wages >= Rp {MIN_WAGE:,}")

    wait_for_odoo(args.url)
    o = Odoo(args.url, args.db, args.user, args.password, args.apply)
    print(f"connected to {args.db} as {args.user} (uid {o.uid})\n")
    rep = Report()

    if args.purge:
        step_purge(o, rep, data)
        rep.show(args.apply)
        return

    if not args.no_modules:
        step_modules(o, rep, SEED_MODULES)
    step_company(o, rep)
    step_localization(o, rep)

    dept_ids, job_ids = step_structure(o, data["employees"], data["departments"])
    emp_ids = step_employees(o, rep, data["employees"], dept_ids, job_ids)
    step_department_managers(o, rep, data["departments"], dept_ids, emp_ids)
    step_users(o, rep, data["users"],
               {e["code"]: e["name"] for e in data["employees"]}, emp_ids)

    retire_old_menu(o, rep)
    menu_ids, category_ids = step_menu(o, rep, data["menu"])
    report_uncategorized(o, rep)
    step_register(o, rep, category_ids)
    step_pantry(o, rep, data["inventory"])
    # The till's sales are the cashier's work: the person on users.csv with that
    # role gets the credit for the day, not the account that ran the seed.
    cashiers = [u["login"] for u in data["users"] if u["role"] == "cashier"]
    step_sales(o, rep, data["sales"], menu_ids, cashiers[0] if cashiers else None)

    rep.show(args.apply)
    if not args.apply:
        print("re-run with --apply to write these changes.")


if __name__ == "__main__":
    main()
