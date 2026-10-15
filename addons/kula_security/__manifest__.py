# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    "name": "KULA Security",
    "summary": "Cashier and barista roles, kiosk-only: sign in and land in the register",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "author": "KULA",
    # point_of_sale for the register and group_pos_user; the role groups also
    # imply base.group_user, which is core.
    "depends": ["point_of_sale"],
    "application": False,
    "installable": True,
    "auto_install": False,
    "data": [
        "security/kula_security.xml",
        # The filename is load-bearing: Odoo derives a generic CSV's model from
        # the file's name, so access rights must be called ir.model.access.csv.
        # It loads after the groups it grants rights to.
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "kula_security/static/src/kiosk_guard.js",
        ],
    },
}
