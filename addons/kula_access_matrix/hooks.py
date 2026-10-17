# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""What has to be taken back when this module goes.

The Access Matrix writes `ir.model.access` rows at runtime. They are not module
data -- no xmlid -- so an uninstall would leave them behind: grants with no page
left to manage them. The rules themselves go with the model, and the roles come
off the menus on their own, because the group records are module data and Odoo
clears the relations when it deletes them.
"""


def uninstall_hook(env):
    """Drop the access rows the matrix wrote, so no grant outlives the page."""
    env["ir.model.access"].sudo().search([("kula_managed", "=", True)]).unlink()
