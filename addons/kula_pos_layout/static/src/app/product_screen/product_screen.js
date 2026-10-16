import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { CategoryHome } from "../category_home/category_home";

// The kiosk landing view is rendered by the ProductScreen template, so the class
// has to know about it. `components` is a static, hence patching the class
// itself rather than its prototype (same as navbar.js does for its dropdown).
patch(ProductScreen, {
    components: { ...ProductScreen.components, CategoryHome },
});

/**
 * Quantity-only numpad.
 *
 * NOTE: this pad is currently NOT rendered on the ProductScreen — the template
 * extension removes it (see product_screen.xml, which explains why). This patch
 * is kept so that deleting that one xpath restores the pad in its 12-key form
 * rather than core's 4x4 pad with the Qty / % / Price mode column.
 *
 * Core builds a 4x4 pad whose right-hand column switches the entry mode between
 * Qty / % / Price. Discount and price control are off on this POS, so two of
 * those three modes are dead UI. Returning 12 plain keys makes the Numpad
 * template compute `numpad-3-cols`, for which Odoo 19 already ships a rule.
 *
 * Safe because `pos.numpadMode` defaults to "quantity" (pos_store.js), so with
 * no mode buttons the pad cannot be stranded in "price" or "discount".
 *
 * The o_colorlist_item_numpad_color_* classes core puts on the decimal point and
 * backspace are intentionally not applied: they paint those two keys red/pink,
 * which is noisy for a keypad that is almost always used for quantities.
 */
patch(ProductScreen.prototype, {
    /**
     * Kiosk mode: the pane's landing view is the category tiles, and the
     * product grid stays out of the way until it is asked for.
     *
     * The grid is asked for by searching: a search word is the one case where
     * a flat list of matches beats a category tree, so this getter hands the
     * pane back to the grid then (and core's search already flat-lists the
     * catalogue). Same small-screen and scanner conditions as core's own
     * category chips, so the kiosk view cannot appear on the phone pane the
     * scanner or the cart is using.
     */
    get kulaShowCategoryHome() {
        return (
            this.pos.config.kula_category_nav === "kiosk" &&
            !this.searchWord &&
            this.pos.productsToDisplay.length > 0 &&
            (!this.pos.isSmallProductScreen || !this.pos.scanning)
        );
    },

    getNumpadButtons() {
        const decimalPoint = this.env.services.localization.decimalPoint;
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
            { value: decimalPoint },
            { value: "Backspace", text: "⌫" },
        ];
    },
});
