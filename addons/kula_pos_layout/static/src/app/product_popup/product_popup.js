import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

/**
 * The popup a kiosk tile opens: the products of one category, as the same cards
 * the product grid uses.
 *
 * It stays open while products are added, so a customer ordering a kopi and two
 * snacks taps the tile once, then the products, and closes it once -- the
 * reference kiosk behaves the same way. The order itself is visible behind the
 * backdrop, and the footer repeats its total, so the running bill is never out
 * of sight while the panel is up.
 *
 * Adding goes through `pos.addLineToCurrentOrder`, the store method the product
 * grid ends up in too (ProductScreen.addProductToOrder calls it): same merge
 * rules, same tax handling, same variant configurator for a product that needs
 * one. The only thing skipped is the "optional products" popup, which this
 * deployment does not use.
 */
export class ProductPopup extends Component {
    static template = "kula_pos_layout.ProductPopup";
    static components = { Dialog, ProductCard };
    static props = {
        // `close` is injected by the dialog service.
        close: Function,
        title: String,
        products: Array,
    };

    setup() {
        this.pos = usePos();
    }

    get products() {
        return this.props.products;
    }

    imageUrl(product) {
        return this.pos.config.show_product_images && product.getImageUrl();
    }

    /**
     * How many of this product the current order already holds -- the badge
     * core prints on a grid card, so a tap that did something is visible.
     *
     * Combo children are skipped because a combo is counted on its parent, the
     * same rule ProductScreen uses for its own badges.
     */
    quantityFor(product) {
        return this.quantityByProductTmplId[product.id];
    }

    get quantityByProductTmplId() {
        const quantities = {};
        for (const line of this.pos.getOrder()?.lines || []) {
            if (line.combo_parent_id) {
                continue;
            }
            const id = line.product_id.product_tmpl_id.id;
            quantities[id] = (quantities[id] || 0) + line.qty;
        }
        return quantities;
    }

    get orderTotal() {
        return this.pos.getOrder()?.currencyDisplayPriceIncl || "";
    }

    async addProduct(product) {
        await this.pos.addLineToCurrentOrder({ product_tmpl_id: product }, {});
    }
}
