# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Marks the access rows the Access Matrix owns.

The matrix writes real `ir.model.access` rows, because that is what Odoo
enforces. This flag is how it tells its own rows from everyone else's: it only
ever changes a row it wrote, so what Odoo and the other modules declare is never
touched by a save. The column is offered in the stock Access Rights list as an
optional column (optional="hide"), which is where an admin goes looking when a
row appears out of nowhere.
"""
from odoo import fields, models


class IrModelAccess(models.Model):
    _inherit = "ir.model.access"

    kula_managed = fields.Boolean(
        string="Set by the access matrix",
        index=True,
        copy=False,
        help="Written by the KULA Access Matrix page. The matrix only ever changes rows "
             "carrying this flag; the access rights declared by Odoo and by the other "
             "modules are left alone.",
    )
