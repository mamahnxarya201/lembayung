# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    kula_can_open_backend = fields.Boolean(
        string="Can open the backend from the register",
        compute="_compute_kula_can_open_backend",
        help="Whether the register's login screen offers its Backend button to "
             "this user. Administrators only: a kiosk-only account (cashier, "
             "barista) cannot open the backend at all — kula_security sends "
             "/odoo back to the register — so for them the button would be a "
             "door that does not open.",
    )

    @api.depends_context("uid")
    def _compute_kula_can_open_backend(self):
        for user in self:
            user.kula_can_open_backend = user.has_group("base.group_system")

    @api.model
    def _load_pos_data_fields(self, config):
        """Send the flag to the register.

        A *field* and not a free key added to the payload: the browser builds
        each record's properties from the model's field definitions
        (models/related_models/model_classes.js), so a key that is not a field
        is readable in `raw` but never as `user.<key>`. res.users defines this
        list explicitly (unlike pos.config), which is why the field has to be
        named here.
        """
        return [*super()._load_pos_data_fields(config), "kula_can_open_backend"]
