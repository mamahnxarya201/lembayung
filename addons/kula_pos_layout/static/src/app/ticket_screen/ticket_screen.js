import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

/**
 * Two things about the Orders list.
 *
 * **The empty order is not an order.** Core lists every order that is not
 * finalized (`activeOrderFilter`), and the register always keeps one empty order
 * open — the cart being rung up. It lands in the list as "Rp 0 / Ongoing", even
 * when nothing was ever put on it, which reads like an order somebody left
 * behind. An order with no lines and no payments is filtered out here; the
 * moment a line is added, or a payment is started, it is in the list again. The
 * row also loses its delete button for the same reason core gives it one (there
 * is nothing to delete).
 *
 * **The row's name.** `kula_title` is the title typed when parking an order: the
 * cashier typed it *for this row*, so it stays what the row is scanned by.
 *
 * The customer from the payment screen's Customer form (customer_popup) is the
 * fallback, but only in the card layout. The tablet's table already prints
 * `order.partner_id.name` in its own column, so repeating it above the order
 * number would print the same name twice on one row; the phone card has no such
 * column, and there the name is the only thing that identifies the customer.
 */
patch(TicketScreen.prototype, {
    kulaOrderLabel(order) {
        return order.kula_title || "";
    },

    kulaMobileOrderLabel(order) {
        return order.kula_title || order.getPartner()?.name || "";
    },

    activeOrderFilter(order) {
        if (!order.getOrderlines().length && !order.payment_ids.length) {
            return false;
        }
        return super.activeOrderFilter(order);
    },
});
