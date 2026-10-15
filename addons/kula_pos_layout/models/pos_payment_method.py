# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    # The confirmation rule has to live on the method rather than be matched
    # against its name in the browser: `name` is translatable, so a translated
    # database would silently stop prompting.
    kula_is_qris = fields.Boolean(
        string="QRIS",
        help="Ask the cashier to confirm before a payment with this method is "
             "validated. QRIS settles on the customer's own phone, so the "
             "register only records it -- the confirmation is the buffer the "
             "cashier needs before that becomes permanent.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        # point_of_sale sends an explicit field list to the POS, so a field
        # that is not in it never reaches the browser.
        return super()._load_pos_data_fields(config) + ["kula_is_qris"]
