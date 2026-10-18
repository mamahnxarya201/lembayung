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

The file also carries one attribution rule -- ``create``, below: the shift
belongs to the person who opened it. The whole story is in models/pos_order.py,
whose rule for a sale is the same one.
"""
from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import AccessError, UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model_create_multi
    def create(self, vals_list):
        """Record who opened the shift when the register did not.

        The same rule as a sale's cashier (models/pos_order.py), on the record
        that is the shift itself: with the cashier login off, nothing ever
        writes pos_hr's ``employee_id`` here either -- the browser only does it
        when a cashier is picked at the login screen -- so the shift of a
        register whose cashier login is off belongs to nobody.

        Core creates the session for the register with the opener already on it
        (``pos.config._action_to_open_ui``: ``{'user_id': self.env.uid, ...}``),
        so the employee comes from ``user_id``, not from the environment. A
        caller that names an employee (the seeder's day of takings, pos_hr
        itself) is left alone.
        """
        if "employee_id" in self._fields:
            for vals in vals_list:
                if vals.get("employee_id"):
                    continue
                opener = self.env["res.users"].browse(vals.get("user_id") or self.env.uid)
                if employee := opener.sudo().employee_id:
                    vals["employee_id"] = employee.id
        return super().create(vals_list)

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

    def kula_unpaid_orders(self, whole_store=False):
        """The orders that must be paid before a shift (or the store) can close.

        One readable line per order. Core already refuses to close a session that
        still has draft orders (`_cannot_close_session`: "You cannot close the
        POS while there are still draft orders for the day."), but that refusal
        comes *after* the operator has filled in the closing form; the
        confirmation asks first, so the orders are named here instead.

        `whole_store` widens the question to every register still open, which is
        what the Close Store answer needs: a shop cannot close while another
        counter still has an order to settle.
        """
        self.ensure_one()
        if not whole_store:
            return self._kula_unpaid_order_lines(self)
        sessions = self.search(
            [
                ("company_id", "=", self.company_id.id),
                ("state", "in", ("opening_control", "opened", "closing_control")),
            ]
        )
        return self._kula_unpaid_order_lines(sessions)

    def _kula_unpaid_order_lines(self, sessions):
        """A draft order is an unpaid order: it is what blocks the close."""
        lines = []
        for session in sessions:
            for order in session.order_ids.filtered(lambda order: order.state == "draft"):
                # "/" is the name of an order that has not been written by the
                # register yet; "Unpaid order" reads better than a slash.
                title = order.kula_title or order.name
                if not title or title == "/":
                    title = _("Unpaid order")
                lines.append(
                    f"{session.config_id.name} — {title} — "
                    f"{session.currency_id.format(order.amount_total)}"
                )
        return lines

    def kula_close_store(self):
        """Close the shop: every *other* register that is still open.

        The "Close Store" answer of the register's confirmation (issue #4). The
        register the operator is standing at is closed through core's closing
        form, so this one is deliberately excluded.

        Refused outright while any *other* register still has an unpaid order:
        the answer then carries those in `blocked` and nothing is closed, because
        "the store closes" cannot be true while a counter still has money to
        take. Past that, best effort per register -- a session another cashier is
        mid-way through closing is reported in `failed` instead of stopping the
        others.

        Every answer carries all three lists -- `closed`, `failed` and `blocked`
        -- empty ones included, because the register reads all three when it
        reports what happened (issue #11: `blocked` used to appear only on the
        refusal, and the successful answer made the caller iterate `undefined`,
        which killed the close before core's form was ever reached).

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
        blocked = self._kula_unpaid_order_lines(others)
        if blocked:
            return {"closed": [], "failed": [], "blocked": blocked}
        for session in others:
            try:
                session._kula_closing_record().action_pos_session_closing_control()
            except (AccessError, UserError) as error:
                failed.append(f"{session.name}: {error.args[0] if error.args else error}")
            else:
                closed.append(session.name)
        # `blocked` is empty by now -- the refusal above returned early -- and it
        # is named anyway: the answer has the same shape every time.
        return {"closed": closed, "failed": failed, "blocked": blocked}
