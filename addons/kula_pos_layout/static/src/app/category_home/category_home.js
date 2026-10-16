import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { CategorySelector } from "@point_of_sale/app/components/category_selector/category_selector";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductPopup } from "../product_popup/product_popup";

/**
 * The kiosk landing view: the whole menu as picture tiles, one tile per
 * category, plus the Add on tile.
 *
 * It extends core's CategorySelector for the same reason the navbar dropdown
 * does -- that parent already resolves the category tree (root categories only,
 * ordering, the hasProductsToShow filter, nesting, and the `/web/image` URL for
 * a category picture) and none of it is reimplemented here. Only the rendering
 * and what a tap does are different: a tile opens that category's products in a
 * popup instead of filtering the grid in place.
 */
export class CategoryHome extends CategorySelector {
    static template = "kula_pos_layout.CategoryHome";
    static props = {};

    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    /**
     * One tile per category that has products to sell.
     *
     * The add-on category is deliberately not among them: it already has its own
     * tile below, and a tile that opens the same list twice would read as two
     * different things to a customer. Its products stay reachable — through the
     * Add on tile, which is the only place an add-on belongs on this screen.
     */
    get tiles() {
        const addonId = this.addonCategory?.id;
        return this.getCategoriesAndSub().filter((tile) => tile.id !== addonId);
    }

    get addonCategory() {
        return this.pos.kulaAddonCategory;
    }

    openCategory(tile) {
        this.showProducts(tile.name, this.pos.kulaProductsOfCategory(tile.id));
    }

    openAddons() {
        this.showProducts(
            _t("Add on"),
            this.pos.kulaProductsOfCategory(this.addonCategory?.id)
        );
    }

    openOther() {
        this.showProducts(_t("Other"), this.pos.kulaUncategorizedProducts);
    }

    showProducts(title, products) {
        this.dialog.add(ProductPopup, { title, products });
    }
}

/**
 * Products per category, resolved from the store's own list.
 *
 * `productsToDisplay` is the list the product grid renders from: already
 * filtered (active, available in POS, not excluded, the category limits) and
 * already ordered the way the counter wants it (favourites first, then
 * pos_sequence, then name). Building the popup from it, rather than from
 * `product.template` or `category.associatedProducts`, is what keeps the popup
 * and the grid from ever disagreeing about what the menu contains.
 */
patch(PosStore.prototype, {
    /**
     * The category the "Add on" tile stands for, as a record, or undefined when
     * the config has none.
     *
     * The POS model layer turns a many2one into its record, but this accepts a
     * plain id too: the value arrives through the config's loaded data, and a
     * raw id is what it would be before the model resolves it.
     */
    get kulaAddonCategory() {
        const value = this.config?.kula_addon_category_id;
        if (!value) {
            return undefined;
        }
        return this.models["pos.category"].get(value.id ?? value);
    },

    /**
     * Products filed under no POS category at all. Core keeps them in the grid
     * (under "Without category"); a category-first screen would otherwise make
     * them unreachable, so they get a tile of their own -- shown only when there
     * are any, which on a seeded database is never.
     */
    get kulaUncategorizedProducts() {
        return this.productsToDisplay.filter((product) => !product.pos_categ_ids?.length);
    },

    /** What the till shows for one category: its products and its children's. */
    kulaProductsOfCategory(categoryId) {
        const category = this.models["pos.category"].get(categoryId);
        if (!category) {
            return [];
        }
        const wanted = new Set(category.getAllChildren().map((child) => child.id));
        return this.productsToDisplay.filter((product) =>
            product.pos_categ_ids?.some((categ) => wanted.has(categ.id))
        );
    },
});
