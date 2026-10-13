# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # NOTE: pos.config deliberately does NOT define `_load_pos_data_fields`
    # (unlike pos.session, product.template, ...). pos.load.mixin returns [] in
    # that case, and pos_session._load_pos_data_relations() then includes *every*
    # non-manual field of the model. So these fields reach `pos.config` in the
    # browser with no further plumbing — no _load_pos_data_fields override and no
    # JS-side field declaration are needed (the frontend Base class exposes raw
    # fields through a lazy-getter proxy).

    kula_card_min_width = fields.Integer(
        string="Product card minimum width (px)",
        default=150,
        help="Lower bound, in pixels, for a product card. The grid fits as many "
             "columns as the screen allows, so this single value controls density "
             "on every tablet. 150 gives roughly 5 columns at 1280px wide, "
             "4 at 1024px and 7 at 1920px.",
    )
    kula_show_card_price = fields.Boolean(
        string="Show price on product cards",
        default=True,
        help="Odoo core never prints a price on a product card, which forces the "
             "cashier to build an order just to quote one.",
    )
    kula_category_nav = fields.Selection(
        selection=[
            ('dropdown', "Navbar dropdown"),
            ('tiles', "In-pane tiles (core)"),
        ],
        string="Category navigation",
        default='dropdown',
        help="Dropdown moves the categories next to the search bar and frees the "
             "whole pane width for products. Tiles is Odoo's core behaviour: "
             "one tap per category instead of two.",
    )
    kula_show_more_button = fields.Boolean(
        string="Keep the actions (...) button",
        default=True,
        help="In Odoo 19 the (...) popup is the only place 'Cancel Order' and "
             "'Pricelist' can be reached from the product screen. Leave this on "
             "unless you genuinely do not need them at the counter.",
    )
