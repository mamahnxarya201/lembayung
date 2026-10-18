import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * The Customer form of the payment screen: name, email, WhatsApp.
 *
 * Core's Customer button opens the partner list, which is the wrong first tap at
 * this counter: the shop takes a name and a number from the person standing
 * there, not a partner record that already exists. Three fields, one Save, and
 * the close button the dialog carries (the ✗ in the header, plus Cancel) are the
 * whole screen.
 *
 * The layout is the Save Order popup's, deliberately — same form, same field
 * labels, same button sizes — because both are the same kind of step: a small
 * form a cashier fills in on a tablet, mid-sale. The dialog service injects
 * `close`, `makeAwaitable` injects `getPayload`, and resolving before `close()`
 * is what makes the caller see the values instead of "cancelled".
 *
 * Saving is the caller's job (payment_screen.js): this component knows nothing
 * about partners, orders or the register.
 */
export class KulaCustomerPopup extends Component {
    static template = "kula_pos_layout.CustomerPopup";
    static components = { Dialog };
    static props = {
        close: Function,
        getPayload: Function,
        // Prefilled from the customer the order already has, if any.
        name: { type: String, optional: true },
        email: { type: String, optional: true },
        whatsapp: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            name: this.props.name || "",
            email: this.props.email || "",
            whatsapp: this.props.whatsapp || "",
        });
        this.nameInput = useRef("nameInput");
        onMounted(() => this.nameInput.el?.focus());
    }

    /**
     * The name is the one field that cannot be empty: it is what the receipt and
     * the Orders list show, and a customer with only a number is not a customer
     * anybody can find again. Email and WhatsApp are optional, one of them being
     * the useful one depending on how the shop talks to people.
     */
    get canSave() {
        return Boolean(this.state.name.trim());
    }

    confirm() {
        if (!this.canSave) {
            return;
        }
        this.props.getPayload({
            name: this.state.name.trim(),
            email: this.state.email.trim(),
            whatsapp: this.state.whatsapp.trim(),
        });
        this.props.close();
    }
}
