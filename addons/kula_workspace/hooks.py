# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""Where a KULA user lands after signing in.

Odoo's landing page is `res.users.action_id` -- "Home Action", opened at log on
in addition to the standard menu. With none set, the web client falls back to
the first app it can reach, which on a fresh database is Discuss: that is why
this project kept opening on the chat.

So the Dashboard (views/dashboard_views.xml) is handed out as the home action
of every backend user, once at install and once for each user created later
(models/res_users.py). Kiosk-only staff are not filtered out on purpose --
they never reach the backend at all, kula_security sends them to the register,
so their home action is never read.
"""

DASHBOARD_ACTION_XMLID = "kula_workspace.action_dashboard"


def dashboard_action(env):
    """The Dashboard action, or an empty recordset while it is still being installed."""
    return env.ref(DASHBOARD_ACTION_XMLID, raise_if_not_found=False)


def apply_home_action(env):
    """Point every backend user who has no home action of their own at the Dashboard.

    Only users with none are touched: a home action set deliberately on someone
    is a choice, and re-running this must not overwrite it.
    """
    action = dashboard_action(env)
    if not action:
        return
    users = (
        env["res.users"]
        .with_context(active_test=False)
        .search([("share", "=", False), ("action_id", "=", False)])
    )
    if users:
        users.write({"action_id": action.id})


def post_init_hook(env):
    apply_home_action(env)
