import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { KulaCustomerPopup } from "../customer_popup/customer_popup";

/**
 * Cash amounts a customer is likely to hand over, in rupiah. Each one is a
 * round multiple of a note/coin the counter actually sees.
 */
const KULA_PAYMENT_INCREMENTS = [1000, 2000, 5000, 10000, 20000, 50000, 100000];

/** No suggestion above this: the point is a fast tap, not a second numpad. */
const KULA_MAX_SUGGESTION = 100000;

/**
 * Round `amountDue` up to the smallest multiple of each increment, drop
 * duplicates, and return the result ascending.
 *
 * `amountDue` is what the selected cash line still has to cover, not the
 * order's total: on a split bill the second payer hands over the remainder, so
 * a chip taken from the total would propose money that has already been paid
 * (see kulaSuggestedPayments).
 *
 * The amount due itself is deliberately not a suggestion: a new cash payment
 * line already starts at that amount, so a chip for it would only repeat what
 * is on screen. For a Rp 23.000 order this returns
 * 24.000 / 25.000 / 30.000 / 40.000 / 50.000 / 100.000.
 */
function kulaSuggestedPaymentAmounts(amountDue) {
    if (!Number.isFinite(amountDue) || amountDue <= 0) {
        return [];
    }
    const total = Math.ceil(amountDue);
    const amounts = new Set();
    for (const increment of KULA_PAYMENT_INCREMENTS) {
        const amount = Math.ceil(total / increment) * increment;
        if (amount > total && amount <= KULA_MAX_SUGGESTION) {
            amounts.add(amount);
        }
    }
    return [...amounts].sort((a, b) => a - b);
}

/**
 * Tender numpad, rebuilt for IDR.
 *
 * Layout:          7 8 9
 *                  4 5 6
 *                  1 2 3
 *                  0 00 ⌫
 *
 * Core uses enhancedButtons(): a 4x4 pad whose right-hand column is
 * +10 / +20 / +50, which ADD TEN, TWENTY AND FIFTY RUPIAH
 * (number_buffer_service INPUT_KEYS holds "+1","+2","+5","+10","+20","+50" and
 * the handler does parseFloat(input.slice(1))). At an Indonesian counter those
 * are three wasted keys, so the whole column is gone — 12 keys gives a
 * 3-column pad, for which core ships .numpad-3-cols.
 *
 * The decimal key beside 0 becomes **00**. That is the point of this pad: the
 * decimal separator is useless now that IDR renders with no decimals
 * (docs §12), while a double-zero key makes cash entry fast — for Rp 50,000 the
 * cashier presses 5, 00, 00 instead of five separate keys.
 *
 * The +/- key is gone too: a tendered amount is never negative.
 */
patch(PaymentScreen.prototype, {
    getNumpadButtons() {
        return [
            { value: "7" },
            { value: "8" },
            { value: "9" },
            { value: "4" },
            { value: "5" },
            { value: "6" },
            { value: "1" },
            { value: "2" },
            { value: "3" },
            { value: "0" },
            { value: "00" },
            { value: "Backspace", text: "⌫" },
        ];
    },

    /**
     * Numpad click handler (wired from payment_screen.xml).
     *
     * "00" is expanded into two "0" keypresses because the number buffer
     * whitelists single keys; everything else is forwarded unchanged, which is
     * exactly what the Numpad component's own default handler does.
     */
    kulaNumpadClick(value) {
        if (value === "00") {
            this.numberBuffer.sendKey("0");
            this.numberBuffer.sendKey("0");
            return;
        }
        this.numberBuffer.sendKey(value);
    },

    /**
     * The suggestions shown under the amount due (payment_screen.xml).
     *
     * Only once a *cash* payment line is selected: the cards have no change
     * and the QRIS amount is whatever the customer's phone is charged, so
     * rounding those up would propose money that is not being handed over.
     * Nothing is suggested before a method is chosen either — that is the
     * moment the cashier starts entering an amount.
     *
     * The amounts are rounded up from what the selected line still has to
     * carry — `remainingDue` plus the line's own amount, which is the
     * expression core uses for the largest tender that line may take — and not
     * from the order's total. On a split bill that is the whole point: a
     * Rp 12.000 order with Rp 5.000 already paid by QRIS leaves Rp 7.000 for
     * the second payer, so the chips are 8.000 / 10.000 / 20.000 / 50.000 /
     * 100.000 and the one that settles it is 10.000. Taken from the total they
     * were 15.000 / 20.000 / 50.000 / 100.000 — money the customer had already
     * paid part of.
     *
     * `remainingDue` on its own would be wrong here: it counts the selected
     * line's own amount too, so a cash line already carrying the remainder
     * reads zero and the chips would vanish at exactly the moment the cashier
     * needs them.
     */
    get kulaSuggestedPayments() {
        const line = this.selectedPaymentLine;
        if (!line || !line.payment_method_id.is_cash_count) {
            return [];
        }
        const amountDue = this.currentOrder.remainingDue + line.amount;
        return kulaSuggestedPaymentAmounts(amountDue);
    },

    /**
     * Put a suggested amount on the selected cash line, and on the number
     * buffer too: the buffer is what the next keypress edits, and `set()`
     * records the value as `lastSet`, so typing replaces the suggestion
     * instead of appending to it.
     */
    kulaApplySuggestedPayment(amount) {
        const line = this.selectedPaymentLine;
        if (!line || !line.payment_method_id.is_cash_count) {
            return;
        }
        this.numberBuffer.set(amount.toString());
        this.updateSelectedPaymentline(amount);
    },

    /**
     * The Customer button (payment_screen.xml): ask for a name, an email and a
     * WhatsApp number, then put that customer on the order.
     *
     * The record is found or created server-side
     * (res.partner.kula_find_or_create_customer -- a cashier may not write a
     * partner, and widening the role for this is not worth it), read back into
     * the register's own models so the order carries a real record, and set on
     * the order. That is what makes the name appear on the receipt, on the order
     * in the backend, and in the Orders list (ticket_screen.js).
     *
     * Dismissed means dismissed: the order keeps the customer it had.
     */
    async kulaEditCustomer() {
        const order = this.currentOrder;
        const partner = order.getPartner();
        const payload = await makeAwaitable(this.dialog, KulaCustomerPopup, {
            name: partner?.name || "",
            email: partner?.email || "",
            whatsapp: partner?.phone || "",
        });
        if (!payload) {
            return;
        }
        const { id } = await this.pos.data.call("res.partner", "kula_find_or_create_customer", [
            payload.name,
            payload.email,
            payload.whatsapp,
        ]);
        const [customer] = await this.pos.data.read("res.partner", [id]);
        order.setPartner(customer);
    },
});
