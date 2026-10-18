# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""The customer a cashier writes down at the payment screen.

Three fields, and only three: the name, an email and a WhatsApp number. The
register's Customer popup asks for exactly those (customer_popup), and this is
where they land.

Why a method and not a plain `create` from the browser: `res.partner` is
read-only for a plain internal user, and a cashier is one — the write is allowed
for Partner Managers only. Rather than widen the role (kula_security keeps the
till's rights model by model, on purpose), the write happens here on the
operator's behalf: sudo, but for these three fields and nothing else, and only
through this one entry point.

The number goes to `res.partner.phone`, the field Odoo prints and exports. There
is no WhatsApp field in core; "WhatsApp" is the label this shop puts on that
number.
"""
from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def kula_find_or_create_customer(self, name, email, whatsapp):
        """Find the customer by email or phone, or create one, and return it.

        Matching on those two before creating is what keeps a repeat customer
        from being duplicated on every visit: the cashier types the same phone
        number, and the order lands on the same partner. An existing customer is
        only completed, never overwritten — a field the shop already filled in is
        the shop's, not the register's.

        Returns the partner id and name, so the caller can read the record into
        the register's own models and put it on the order.
        """
        self = self.sudo()
        name = (name or "").strip()
        email = (email or "").strip()
        whatsapp = (whatsapp or "").strip()

        partner = self.browse()
        for field, value in (("email", email), ("phone", whatsapp)):
            if value:
                partner = self.search([(field, "=", value)], limit=1)
                if partner:
                    break

        if not partner:
            partner = self.create(
                {
                    # A customer with no name is still a customer: the number (or
                    # the email) is what identifies them on the order.
                    "name": name or whatsapp or email,
                    "email": email,
                    "phone": whatsapp,
                }
            )
            return {"id": partner.id, "name": partner.name}

        blanks = {}
        if name and not partner.name:
            blanks["name"] = name
        if email and not partner.email:
            blanks["email"] = email
        if whatsapp and not partner.phone:
            blanks["phone"] = whatsapp
        if blanks:
            partner.write(blanks)
        return {"id": partner.id, "name": partner.name}
