import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { KulaSaveOrderPopup } from "../save_order/save_order";

/**
 * The Save Order button (action_pad.xml): ask for a title and a note, write
 * them on the order, then park it.
 *
 * The handler lives here, with the button and not on the popup, because
 * ActionpadWidget is what owns `pos` and `currentOrder` — the popup is handed
 * nothing but the two strings.
 *
 * Parking itself is core's `pos.clickSaveOrder()`: the same call behind the
 * upload button this module removes from the control row. It syncs the order to
 * the server as a draft, notifies the cashier, and opens a fresh empty order.
 * That draft is what puts it in the Orders list — the TicketScreen shows
 * non-finalized orders by default (`activeOrderFilter`) — and what makes the
 * Load Order button appear once the row is selected, which is how the order is
 * resumed.
 *
 * `kula_title` is this module's field on pos.order; `general_customer_note` is
 * core's own order note, the one the Note button writes and the receipt prints.
 */
patch(ActionpadWidget.prototype, {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    },

    async kulaSaveOrder() {
        const order = this.currentOrder;
        if (!order || order.isEmpty()) {
            return;
        }
        const payload = await makeAwaitable(this.dialog, KulaSaveOrderPopup, {
            title: order.kula_title || "",
            notes: order.general_customer_note || "",
        });
        if (!payload) {
            // Dismissed: the order stays on screen exactly as it was.
            return;
        }
        order.kula_title = payload.title;
        order.setGeneralCustomerNote(payload.notes);
        this.pos.clickSaveOrder();
    },
});
