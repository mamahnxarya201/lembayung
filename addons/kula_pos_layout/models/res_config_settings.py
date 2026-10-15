# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # `related=... readonly=False` is how res.config.settings writes back to the
    # selected pos.config — same pattern core uses for pos_iface_* fields.
    pos_kula_card_min_width = fields.Integer(
        related='pos_config_id.kula_card_min_width', readonly=False)
    pos_kula_show_card_price = fields.Boolean(
        related='pos_config_id.kula_show_card_price', readonly=False)
    pos_kula_category_nav = fields.Selection(
        related='pos_config_id.kula_category_nav', readonly=False)
    pos_kula_show_more_button = fields.Boolean(
        related='pos_config_id.kula_show_more_button', readonly=False)
