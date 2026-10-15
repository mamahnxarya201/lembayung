import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";

/**
 * Adds the product price to each cart-facing card.
 *
 * No setup() patch and no usePos() hook: the POS store is already available on
 * the component environment as the registered "pos" service, which avoids
 * having to override ProductCard's lifecycle.
 */
patch(ProductCard.prototype, {
    get kulaShowPrice() {
        return (
            this.env.services.pos?.config?.kula_show_card_price && !this.props.isComboPopup
        );
    },

    /**
     * The product's list price.
     *
     * ProductCard receives a **product.template** (productToDisplayByCateg holds
     * templates) and product.template loads `list_price` — NOT `lst_price`.
     * Reading `lst_price` (or `product_tmpl_id.list_price`) yields undefined,
     * which silently makes getPrice() return NaN and the card print "Rp 0.00".
     * Candidates are ordered cheapest-first.
     */
    get kulaBasePrice() {
        const product = this.props.product;
        if (!product) {
            return 0;
        }
        const candidates = [
            product.list_price,
            product.lst_price,
            product.raw?.list_price,
            product.raw?.lst_price,
        ];
        for (const value of candidates) {
            if (Number.isFinite(value)) {
                return value;
            }
        }
        return 0;
    },

    /**
     * Pricelist-aware when a pricelist is in play, list price otherwise.
     *
     * `variant` is deliberately false: getPrice() computes
     * `variant ? variant.lst_price : this.list_price`, and `this` is the
     * product.template, whose `list_price` is the value that actually exists.
     * A non-finite or zero result falls back to the list price, so a pricelist
     * rule based on cost (standard_price, often 0) cannot blank the card.
     */
    get kulaPrice() {
        const product = this.props.product;
        if (!product) {
            return "";
        }
        const pos = this.env.services.pos;
        const pricelist = pos?.getOrder()?.pricelist_id || pos?.config?.pricelist_id || null;
        let price = this.kulaBasePrice;
        if (pricelist && typeof product.getPrice === "function") {
            const computed = product.getPrice(pricelist, 1, 0, false, false);
            if (Number.isFinite(computed) && computed > 0) {
                price = computed;
            }
        }
        return this.env.utils.formatCurrency(price);
    },
});
