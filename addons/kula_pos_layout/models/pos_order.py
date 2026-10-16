# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # No _load_pos_data_fields on pos.order (unlike pos.order.line), so this
    # field reaches the browser the same way pos.config's kula_* fields do:
    # pos.load.mixin returns [] and pos_session._load_pos_data_relations() then
    # includes every non-manual field of the model. The register reads it to
    # prefill the Save Order form, and shows it as the order's name in the
    # Orders list.
    kula_title = fields.Char(
        string="Order title",
        help="The name the counter gives an order when it parks it ('Aryana', "
             "'Table 3'), so the order can be found again in the Orders list. "
             "Written by the Save Order button on the register; empty on an "
             "order that was never parked.",
    )
