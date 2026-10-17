# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Closing the register belongs to whoever is operating it.

Core's closing API asks for ``point_of_sale.group_pos_user``:

* ``get_cash_in_out_list`` and ``get_closing_control_data`` raise ``AccessError``
  without it, which the register shows as *"You don't have the access rights to
  get the point of sale closing control data."* -- GitHub issue #4;
* ``_validate_session`` keeps a second branch for callers without it, and that
  branch skips the session's account move: the shift would close, and the day's
  sales would never be posted.

Kula's Cashier and Barista deliberately do not carry that group -- kula_security
grants the till its rights model by model instead -- so on this database nobody
at the counter can close a register, and an administrator who did would close it
without the closing entry.

The check reads the user of the *environment*, so ``sudo()`` does not change the
answer: it raises the ACL ceiling, it does not make the caller a POS user. What
does change it is running the closing API in an environment whose user is the
technical superuser -- which is where ``_validate_session`` roughly arrives on
its own when it decides the caller is a POS user (``record = record.sudo()``).
That is what these overrides do, and only for the register's own operators: a
caller who is neither a POS user nor a kiosk member reaches core untouched and
still gets core's answer.
"""
from odoo import SUPERUSER_ID, _, models
from odoo.exceptions import AccessError, UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    def _kula_closing_record(self):
        """This session, in the environment core's closing API is written for.

        Nothing is elevated for a POS user (core already handles them) or for a
        caller outside the kiosk roles (core's AccessError is then the right
        answer). The kiosk group comes from kula_security; when that module is
        not installed the XML id resolves to nothing and this returns the
        session unchanged.
        """
        self.ensure_one()
        if self.env.user.has_group("point_of_sale.group_pos_user"):
            return self
        if not self.env.user.has_group("kula_security.group_kiosk_only"):
            return self
        return self.with_user(SUPERUSER_ID)

    def get_closing_control_data(self):
        return super(PosSession, self._kula_closing_record()).get_closing_control_data()

    def post_closing_cash_details(self, counted_cash):
        return super(PosSession, self._kula_closing_record()).post_closing_cash_details(counted_cash)

    def update_closing_control_state_session(self, notes):
        return super(PosSession, self._kula_closing_record()).update_closing_control_state_session(notes)

    def close_session_from_ui(self, bank_payment_method_diff_pairs=None):
        return super(PosSession, self._kula_closing_record()).close_session_from_ui(
            bank_payment_method_diff_pairs
        )

    def kula_close_store(self):
        """Close the shop: every *other* register that is still open.

        The "Close Store" answer of the register's confirmation (issue #4). The
        register the operator is standing at is already closed by the time this
        runs -- the client closes it through core's closing form, then asks for
        the rest of the shop -- so this one is deliberately excluded.

        Best effort per register: a counter that refuses (draft orders left on
        it, a session another cashier is mid-way through closing) is reported
        back by name instead of stopping the others, because the shop is closing
        and one register cannot be allowed to hold the day open. The caller
        shows the names before the operator is logged out.

        `opening_control` counts as open: it is the session the register creates
        for itself on load, before anyone has confirmed the opening cash, and a
        shop that is closing should not leave one of those behind either.
        """
        self.ensure_one()
        if not (
            self.env.user.has_group("point_of_sale.group_pos_user")
            or self.env.user.has_group("kula_security.group_kiosk_only")
        ):
            raise AccessError(_("Only a register's operator can close the store."))

        closed, failed = [], []
        others = self.search(
            [
                ("id", "!=", self.id),
                ("company_id", "=", self.company_id.id),
                ("state", "in", ("opening_control", "opened", "closing_control")),
            ]
        )
        for session in others:
            try:
                session._kula_closing_record().action_pos_session_closing_control()
            except (AccessError, UserError) as error:
                failed.append(f"{session.name}: {error.args[0] if error.args else error}")
            else:
                closed.append(session.name)
        return {"closed": closed, "failed": failed}
