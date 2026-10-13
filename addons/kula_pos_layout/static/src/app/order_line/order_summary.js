import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";

/**
 * Per-line quantity stepper and delete button for the order pane.
 *
 * The three handlers live here, on OrderSummary, and not on a component of
 * their own, because OrderSummary is where core already keeps the rules for
 * changing a line: it owns `pos`, `numberBuffer` and the number buffer
 * registration, and `_setValue` / `updateQuantityNumber` are the same code paths
 * the quantity numpad goes through. Putting the buttons on that instance means
 * the stepper cannot drift from the numpad.
 *
 * The buttons themselves are rendered by kula_pos_layout.OrderSummary, which
 * fills the "kula-controls" slot added to core's order line template.
 */
patch(OrderSummary.prototype, {
    /** Line quantity, formatted exactly as the line itself prints it. */
    kulaLineQty(line) {
        return this.env.utils.formatProductQty(line.getQuantity(), false);
    },

    /**
     * One tap on − or +.
     *
     * `direction` is -1 or +1 and is applied to the quantity as displayed, so on
     * a negative (refund) line − makes the number smaller (a bigger refund) and +
     * walks it back up to zero. A step that would reach or cross zero removes the
     * line instead of leaving a 0-qty one behind — that is what core's ⌫ does,
     * and it is also what keeps a fractional line (0.5 kg) from flipping sign.
     */
    async kulaStepQuantity(line, direction) {
        const order = this.currentOrder;
        if (!order || !line) {
            return;
        }
        // Combo children are display-only; the quantity lives on the parent.
        const target = line.combo_parent_id || line;
        const current = target.getQuantity();
        const next = current + direction;

        if (next === 0 || (current > 0) !== (next > 0)) {
            this.kulaRemoveLine(target);
            return;
        }

        if (this.pos.disallowLineQuantityChange()) {
            // A decrease on a line already sent to the kitchen may not simply
            // rewrite the quantity (it is what the customer was served), so core
            // splits it into a separate negative line. That machinery works off
            // the *selected* line and off uiState.savedQuantity, hence the
            // selection. Base point_of_sale always returns false here; the branch
            // exists so a module that overrides it keeps working.
            this.pos.selectOrderLine(order, target);
            await this.updateQuantityNumber(next);
            return;
        }

        // Same call, same arguments and same error handling as OrderSummary's
        // own _setValue() in "quantity" mode.
        const result = target.setQuantity(next, Boolean(target.combo_line_ids?.length));
        if (result !== true) {
            this.dialog.add(AlertDialog, result);
            this.numberBuffer.reset();
        }
    },

    /**
     * Delete the whole line, and its combo children with it:
     * Order.removeOrderline() goes through getAllLinesInCombo() and re-selects
     * the last remaining line, so the numpad is never left pointing at a line
     * that no longer exists.
     */
    kulaRemoveLine(line) {
        const order = this.currentOrder;
        if (!order || !line) {
            return;
        }
        const target = line.combo_parent_id || line;
        this.numberBuffer.reset();
        order.removeOrderline(target);
    },
});
