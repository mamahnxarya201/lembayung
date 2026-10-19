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
            ('kiosk', "Kiosk: category tiles, products in a popup"),
            ('dropdown', "Navbar dropdown"),
            ('tiles', "In-pane tiles (core)"),
        ],
        string="Category navigation",
        default='kiosk',
        help="Kiosk shows the categories as picture tiles filling the pane, and "
             "opens the products of one category in a popup — the pane never "
             "scrolls, so the whole menu is one tap away on a wall-mounted "
             "tablet. Dropdown moves the categories next to the search bar and "
             "frees the whole pane width for products. Tiles is Odoo's core "
             "behaviour: one tap per category instead of two.",
    )
    kula_addon_category_id = fields.Many2one(
        'pos.category',
        string="Add-on category",
        help="The 'Add on' button on the kiosk product screen lists this "
             "category's products, and one tap drops one onto the current "
             "order — the upsell a customer asks for at the counter (extra "
             "shot, take-away cup). Leave empty to hide the button.",
    )
    kula_show_more_button = fields.Boolean(
        string="Keep the actions (...) button",
        default=True,
        help="In Odoo 19 the (...) popup is the only place 'Cancel Order', "
             "'Pricelist' and 'Refund' can be reached from the product screen. "
             "Leave this on unless you genuinely do not need them at the "
             "counter.",
    )

    def kula_app_version(self):
        """The asset version of the POS client this server is serving, per bundle.

        Asked by the register (static/src/app/update_app/update_app.js) to know
        whether the app it is running is still the app the server would hand it.
        One entry per POS bundle, the light one and the dark one, because the
        page picks between them by the `pos_color_scheme` cookie
        (point_of_sale.index) and the register reads back the bundle it actually
        loaded, hash and all, from its own <script> and <link> tags.

        `_get_asset_bundle` is core's own answer to "which files, and which
        version" (t-call-assets builds the page links from it), and the version
        is a hash of those files' paths and last-modified stamps, so it moves
        when — and only when — a file in the bundle changes. That call is the
        private one on purpose: the public entry points render a bundle, they do
        not report its version. It reads `ir.asset` through a process-wide
        ormcache, which is exactly what makes the answer agree with the links the
        running server is serving; a *restarted* server computes both afresh,
        which is what a deploy is (see §25 of the design doc).
        """
        versions = {}
        for bundle_name in ("point_of_sale.assets_prod", "point_of_sale.assets_prod_dark"):
            assets = self.env["ir.qweb"]._get_asset_bundle(bundle_name)
            versions[bundle_name] = {
                "js": assets.get_version("js"),
                "css": assets.get_version("css"),
            }
        return versions
