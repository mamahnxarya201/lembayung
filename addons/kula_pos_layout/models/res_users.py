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

    kula_kiosk_only = fields.Boolean(
        string="Kiosk only",
        compute="_compute_kula_kiosk_only",
        help="Whether this user may only use the register (kula_security's "
             "Kiosk Only group). The register reads it to know that it has no "
             "backend to leave to: core's way out of the register is /odoo, "
             "which kula_security answers with the register again, so the exits "
             "end on the Unlock screen instead of bouncing back into a second "
             "register (static/src/app/backend_exit/backend_exit.js).",
    )

    @api.depends_context("uid")
    def _compute_kula_kiosk_only(self):
        # The group belongs to kula_security. When that module is not installed
        # the XML id resolves to nothing and has_group answers False, which
        # leaves the register on core's own behaviour -- the same degradation
        # models/pos_session.py relies on.
        for user in self:
            user.kula_kiosk_only = user.has_group("kula_security.group_kiosk_only")

    @api.model
    def _load_pos_data_fields(self, config):
        """Send the flags to the register.

        *Fields* and not free keys added to the payload: the browser builds
        each record's properties from the model's field definitions
        (models/related_models/model_classes.js), so a key that is not a field
        is readable in `raw` but never as `user.<key>`. res.users defines this
        list explicitly (unlike pos.config), which is why the fields have to be
        named here.
        """
        return [
            *super()._load_pos_data_fields(config),
            "kula_can_open_backend",
            "kula_kiosk_only",
        ]
