import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

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
});
