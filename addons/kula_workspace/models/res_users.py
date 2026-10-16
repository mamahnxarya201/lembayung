# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models

from ..hooks import dashboard_action


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        """Land a new backend user on the Dashboard too.

        The install-time hook (hooks.py) only runs once, so every user created
        afterwards -- the next cashier, the next manager -- would otherwise open
        on Discuss. Portal users are left out: the Dashboard is a backend page
        and they never see it.
        """
        users = super().create(vals_list)
        action = dashboard_action(self.env)
        landing = users.filtered(lambda user: not user.share and not user.action_id)
        if action and landing:
            landing.write({"action_id": action.id})
        return users
