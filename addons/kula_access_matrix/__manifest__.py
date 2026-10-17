# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    "name": "KULA Access Matrix",
    "summary": (
        "The ACL/RBAC configuration as a table: every installed menu by role, "
        "with the degree each role has"
    ),
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "license": "LGPL-3",
    "author": "KULA",
    # Nothing of Kula's own is required: the page reads the menus, the roles and
    # the access rows out of Odoo itself, and writes only the access rows it
    # marked as its own. It is installed everywhere (auto_install) because it
    # shows itself to nobody but the administrator, and in this repository it
    # opens on the shop's own roles because they exist here (kula_security);
    # without them it opens with no column and the admin ticks one in the
    # header.
    "depends": ["base"],
    "application": False,
    "installable": True,
    "auto_install": True,
    # The matrix writes access rows of its own, and Odoo would not know to take
    # them away with the module: hooks.py does.
    "uninstall_hook": "uninstall_hook",
    "data": [
        # The access rights on the rule model: the administrator, and nobody
        # else. The page enforces the same thing on its own calls.
        "security/ir.model.access.csv",
        # The Access Matrix menu, its page, and the marker in Odoo's own
        # Access Rights list.
        "views/access_matrix_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # The Access Matrix page. The template is listed before the JS that
            # renders it: the template service has to have registered the name
            # before a component tries to render.
            "kula_access_matrix/static/src/access_matrix/access_matrix.xml",
            "kula_access_matrix/static/src/access_matrix/access_matrix.js",
            "kula_access_matrix/static/src/access_matrix/access_matrix.scss",
        ],
    },
}
