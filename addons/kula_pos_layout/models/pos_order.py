# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Every sale at the register names the person who rang it up.

A sale carries two links to a person, and pos_hr changes which one the Orders
list shows:

* ``user_id`` -- core's own field (labelled *Employee*), the user who was logged
  in. The browser fills it on every order it creates, cashier login or not.
* ``employee_id`` -- pos_hr's field (labelled *Cashier*). The browser only sets
  it when ``pos.config.module_pos_hr`` is on, because that is the mode in which
  ``hr.employee`` is loaded and a cashier is picked on the register's login
  screen. With the cashier login off there is no employee in the browser at all.

pos_hr's list view replaces ``user_id`` with ``employee_id``
(``widget="many2one_avatar_employee"``), so on a register whose cashier login is
*off* -- the default of a fresh database, and this database's setting -- the
Cashier column is empty for every sale the register makes, an administrator's
included, while rows written by anything that does set the field (the seeder's
day of takings) show a name. That is GitHub issue #9: *"when Administrator
issues a product, the log is found but there is no credential of who issued
it."*

The rule below closes the gap at the record, not at the view: a sale the
register did not attribute to an employee is attributed to the employee of the
user who rang it up. With the cashier login off that user *is* the cashier, so
their own employee record is the truthful answer rather than a guess; with the
cashier login on the browser has already sent the cashier it asked for, and
this changes nothing.

``employee_id`` is pos_hr's field (pos_hr depends on ``hr``), so its presence on
the model is the test for "pos_hr is installed" -- and the only case in which
there is anything to fill.
"""
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # No _load_pos_data_fields on pos.order (unlike pos.order.line), so this
    # field reaches the browser the same way pos.config's kula_* fields do:
    # pos.load.mixin returns [] and pos_session._load_pos_data_relations() then
    # includes every non-manual field of the model. The register reads it to
    # prefill the Save Order form, and shows it as the order's name in the
    # Orders list.
    kula_title = fields.Char(
        string="Order title",
        help="The name the counter gives an order when it parks it ('Aryana', "
             "'Table 3'), so the order can be found again in the Orders list. "
             "Written by the Save Order button on the register; empty on an "
             "order that was never parked.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._kula_attribute_cashier(vals)
        return super().create(vals_list)

    @api.model
    def _kula_attribute_cashier(self, vals):
        """Give ``vals`` a cashier when the register did not send one.

        ``vals`` is modified in place; nothing is written and nothing is looked
        up when it already names an employee, so pos_hr's own behaviour (the
        cashier picked on the login screen) is left exactly as it is.

        The operator is ``user_id`` -- core's field, and what the browser fills
        in -- falling back to the caller, which is what core's own default on
        the field does. sudo(): the till needs no right to read an employee,
        only the link between the two records, and a kiosk member would
        otherwise be denied their own.
        """
        if "employee_id" not in self._fields or vals.get("employee_id"):
            return
        operator = self.env["res.users"].browse(vals.get("user_id") or self.env.uid)
        if employee := operator.sudo().employee_id:
            vals["employee_id"] = employee.id

    def _kula_backfill_cashier(self):
        """Attribute the sales that predate this rule, from their own operator.

        Not called automatically: the repair of what is already in the database
        belongs to the seeder, which walks the day of takings it created and
        repairs the attribution a ``--purge`` emptied (``seed/seed.py``,
        ``rebind_the_day``). It is here because the rule is here, and because a
        migration cannot do it: **kula_pos_layout sorts before pos_hr in the
        load order**, so every hook that runs while this module is being loaded
        -- its data files, a ``migrations/`` script, ``post_init_hook`` -- sees
        a registry in which pos_hr has not been loaded and ``pos.order`` has no
        ``employee_id`` field at all. Verified in an upgrade: the same method
        called from the finished registry fills the sales, and inside the
        update ``'employee_id' in env['pos.order']._fields`` is ``False`` (a
        ``<function>`` in a data file therefore ran, found nothing to fill, and
        returned silently).

        Safe to re-run from a shell: only sales with no employee are touched,
        and the value comes from the sale's own ``user_id``, so an attributed
        sale is never rewritten.
        """
        for order in self.filtered(lambda o: o.user_id and not o.employee_id):
            if employee := order.user_id.sudo().employee_id:
                order.employee_id = employee.id
