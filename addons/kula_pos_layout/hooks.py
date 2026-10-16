# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Install-time data for this module, kept out of the XML on purpose: the rule
below is several steps (find or create a method, then rewrite a many2many on
every config) and reads far better as Python than as nested <function> tags.
"""
from odoo import Command

import logging

_logger = logging.getLogger(__name__)

QRIS_NAME = "QRIS"


def post_init_hook(env):
    """Make the payment methods match the counter's rules.

    Cash and QRIS only. Card and Customer Account are taken off every config --
    what the payment screen offers is `pos.config.payment_method_ids`, so
    unlinking them is what removes them -- and a QRIS method is created when the
    database has none.

    QRIS is deliberately a *non-cash* method: Odoo computes change for cash
    methods only, so leaving `is_cash_count` off is what makes "QRIS has no
    change" true rather than merely intended. It is also left without a payment
    terminal type, because the QR itself is handled outside Odoo and this
    register only has to record the payment.

    Idempotent: an existing QRIS method is reused and never reconfigured beyond
    the flag, so a database that already has one keeps whatever was set on it.
    """
    method_model = env["pos.payment.method"]
    qris = method_model.search([("name", "=", QRIS_NAME)], limit=1)
    if not qris:
        # A bank journal, not the cash one: the journal decides `type`, and
        # `type = 'cash'` is what switches change on.
        journal = env["account.journal"].search([("type", "=", "bank")], limit=1)
        qris = method_model.create(
            {
                "name": QRIS_NAME,
                "journal_id": journal.id,
                "kula_is_qris": True,
            }
        )
    elif not qris.kula_is_qris:
        qris.kula_is_qris = True

    # Cash has to be *ensured*, not assumed. A database with no cash journal has
    # no cash payment method, and the first version of this hook only created
    # QRIS -- so a fresh database came out with a till that could not take cash
    # at all, which is the opposite of the cash-and-QRIS it was written for. A
    # cash journal is what makes `is_cash_count` true, and `is_cash_count` is
    # what makes Odoo compute change; a cash method on a bank journal would take
    # money and give none back.
    cash = method_model.search([("is_cash_count", "=", True)], limit=1)
    if not cash:
        cash_journal = env["account.journal"].search([("type", "=", "cash")], limit=1)
        if not cash_journal:
            cash_journal = env["account.journal"].create({
                "name": "Cash",
                "type": "cash",
                "code": "CSH",
                "company_id": env.company.id,
            })
        cash = method_model.create({"name": "Cash", "journal_id": cash_journal.id})

    for config in env["pos.config"].search([]):
        # Odoo refuses to touch a config's payment methods while one of its
        # sessions is open, and that refusal is a UserError -- which, raised
        # from an init hook, would abort the whole module install. Skipping is
        # the right answer: an install must not fail because a till was left
        # open, and closing somebody's register is not this hook's business.
        if config.current_session_id and config.current_session_id.state != "closed":
            _logger.warning(
                "kula_pos_layout: %s has an open session, so its payment "
                "methods were left alone; close the session and reinstall or "
                "upgrade the module to apply Cash + QRIS.",
                config.display_name,
            )
            continue
        keep = config.payment_method_ids.filtered(
            lambda method: method.is_cash_count or method == qris
        )
        if qris not in keep:
            keep |= qris
        config.write({"payment_method_ids": [Command.set(keep.ids)]})
