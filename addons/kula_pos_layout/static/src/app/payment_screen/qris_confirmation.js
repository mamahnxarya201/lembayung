/**
 * QRIS confirmation, the buffer before a QRIS payment becomes permanent.
 *
 * The QR itself is settled on the customer's own phone, so the register cannot
 * observe it: by the time the cashier validates, Odoo is only recording what
 * already happened elsewhere. That is exactly why this prompt exists -- it
 * forces a pause between "the customer says they paid" and the ledger entry,
 * and it cancels itself when nobody answers.
 *
 * The rules, from the counter's spec:
 *   - only when a QRIS line is on the order (cash still validates in one tap);
 *   - 20 seconds to answer, then the validation is abandoned;
 *   - Cancel abandons it too, and leaves the cashier on the payment screen
 *     with the payment lines intact -- nothing is recorded either way.
 *
 * "Abandon" and not "void the order": the spec offers exactly two outcomes,
 * proceeding or cancelling, and the timeout is described as doing the same
 * thing as the Cancel button. A timeout that voided the order would destroy
 * the cashier's work at a moment nobody chose.
 */
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/** How long the cashier has to confirm. */
const CONFIRM_SECONDS = 20;

export class QrisConfirmationDialog extends Component {
    static template = "kula_pos_layout.QrisConfirmationDialog";
    static components = { Dialog };
    static props = {
        // `close` is injected by the dialog service; `confirm` and `cancel` are
        // added by make_awaitable_dialog's `ask`, which is what turns a button
        // press into the value the caller is awaiting.
        close: Function,
        confirm: Function,
        cancel: Function,
        methodName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ seconds: CONFIRM_SECONDS });
        onMounted(() => {
            this.timer = setInterval(() => {
                this.state.seconds -= 1;
                if (this.state.seconds <= 0) {
                    this.answer(false);
                }
            }, 1000);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    confirm() {
        this.answer(true);
    }

    cancel() {
        this.answer(false);
    }

    /**
     * Resolve before closing. `ask` resolves `false` from the dialog's
     * onClose, so closing first would answer "cancelled" even when the cashier
     * pressed the confirm button.
     */
    answer(confirmed) {
        clearInterval(this.timer);
        if (confirmed) {
            this.props.confirm();
        } else {
            this.props.cancel();
        }
        this.props.close();
    }
}

patch(PaymentScreen.prototype, {
    /**
     * Intercepting `validateOrder` rather than the Validate button itself: the
     * button, the Enter key and a barcode all land here, and a payment terminal
     * can call it too (payment_screen.js calls validateOrder(false) after a
     * terminal transaction). Guarding the one method guards all of them.
     */
    async validateOrder(isForceValidate = false) {
        const qrisLine = this.currentOrder.payment_ids.find(
            (line) => line.payment_method_id.kula_is_qris
        );
        if (qrisLine) {
            // `ask`, not `dialog.add`: `add` returns the function that removes
            // the dialog, so awaiting it yields a truthy value and every answer
            // would read as "confirmed". `ask` resolves a real boolean, and
            // resolves false when the dialog is dismissed without an answer.
            const confirmed = await ask(
                this.env.services.dialog,
                { methodName: qrisLine.payment_method_id.name },
                {},
                QrisConfirmationDialog
            );
            if (!confirmed) {
                return;
            }
        }
        return super.validateOrder(isForceValidate);
    },
});
