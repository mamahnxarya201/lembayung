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
 */
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/** How long the cashier has to confirm. */
const CONFIRM_SECONDS = 20;

export class QrisConfirmationDialog extends Component {
    static template = "kula_pos_layout.QrisConfirmationDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        // The amount and method name, so the dialog says what is being
        // confirmed rather than only asking in the abstract.
        methodName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ seconds: CONFIRM_SECONDS });
        onMounted(() => {
            this.timer = setInterval(() => {
                this.state.seconds -= 1;
                if (this.state.seconds <= 0) {
                    this.cancel();
                }
            }, 1000);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    confirm() {
        clearInterval(this.timer);
        this.props.close(true);
    }

    cancel() {
        clearInterval(this.timer);
        this.props.close(false);
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
            const confirmed = await this.env.services.dialog.add(QrisConfirmationDialog, {
                methodName: qrisLine.payment_method_id.name,
            });
            if (!confirmed) {
                return;
            }
        }
        return super.validateOrder(isForceValidate);
    },
});
