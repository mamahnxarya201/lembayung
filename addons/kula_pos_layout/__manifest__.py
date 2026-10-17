{
    'name': "KULA POS Layout",
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'author': "KULA",
    'summary': "Kiosk counter layout: category tiles, product popup, add-ons, sidebar",
    'description': """
KULA POS Layout
===============

Re-arranges the Odoo 19 Point of Sale product screen for a counter-service cafe,
and keeps it usable on any tablet regardless of resolution or orientation.

* Menu pane on the left, order pane on the right (panes swapped via CSS, so no
  core markup is duplicated).
* **Kiosk mode** (the default): the pane opens as picture tiles, one per POS
  category; tapping one lists that category's products in a popup, where a tap
  puts one on the order. An **Add on** tile lists the counter's extras, from the
  category named in Settings. Category dropdown and core's in-pane tiles are kept
  as the two other values of the same setting.
* The navbar's burger menu becomes a **sidebar** with a scrim: core's own menu,
  re-painted, so pos_hr's permission-gated entries and pos_restaurant's floor
  entries keep working.
* The **Backend** shortcut (login screen and sidebar) is the administrator's:
  hidden for everyone else, because a kiosk-only account cannot open the backend
  anyway (kula_security sends /odoo back to the register).
* Product cards carry their price (core prints none).
* Product grid column count is derived from the viewport, never hardcoded.
* Two controls on the order side: **Payment** and **Save Order** — the first
  commits, the second parks the order under a name the cashier types (a title
  and a note) and leaves it open in the Orders list, where the title is what the
  row is scanned for. Everything else (Cancel Order, Pricelist, Refund) lives in
  the (⋯) popup.
* **Closing the register** is a question with two answers: *Close Shift* closes
  this register, *Close Store* closes the shop as well (every other register
  still open). Either way the operator ends on the register's login screen, and
  either way the closing itself is still core's: cash count, closing note, and
  the day's account move. A cashier or barista can close at all — core's closing
  API asks for `point_of_sale.group_pos_user`, which the kiosk roles deliberately
  do not carry, so the closing methods are opened for kiosk members here
  (models/pos_session.py) rather than by widening the roles.
* Numpad reduced to quantity entry, since Price/Disc modes are disabled here.
* Every order line carries its own -/+ stepper and a delete button, so a line can
  be decremented or removed in one tap instead of select-then-numpad, and can be
  deselected by tapping it again (core behaviour).

All sizes are expressed with clamp() and one ``auto-fill`` grid rule, so there
are no per-model breakpoints to maintain.
    """,
    'depends': ['point_of_sale'],
    'data': [
        'data/res_currency_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'kula_pos_layout/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    # Cash + QRIS payment methods, and no Card or Customer Account: see
    # hooks.py for why this is Python rather than module data.
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
}
