import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * The form the Save Order button opens: a name for the order, and a note.
 *
 * A dialog of this module's own rather than core's TextInputPopup, which
 * carries one field: the point of this screen is that both are asked for at the
 * same time, and that they are big enough to hit on a wall-mounted tablet. The
 * dialog service injects `close`; `getPayload` is injected by `makeAwaitable`
 * and is what hands the values back to the caller — resolving through it before
 * `close()` matters, because the dialog's own onClose resolves the same promise
 * with nothing, and closing first would answer "cancelled".
 */
export class KulaSaveOrderPopup extends Component {
    static template = "kula_pos_layout.SaveOrderPopup";
    static components = { Dialog };
    static props = {
        close: Function,
        getPayload: Function,
        // Prefilled when an order that already has a title is saved again.
        title: { type: String, optional: true },
        notes: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            title: this.props.title || "",
            notes: this.props.notes || "",
        });
        this.titleInput = useRef("titleInput");
        onMounted(() => this.titleInput.el?.focus());
    }

    confirm() {
        this.props.getPayload({
            title: this.state.title.trim(),
            notes: this.state.notes.trim(),
        });
        this.props.close();
    }
}
