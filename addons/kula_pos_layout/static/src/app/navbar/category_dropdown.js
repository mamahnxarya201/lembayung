import { _t } from "@web/core/l10n/translation";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { CategorySelector } from "@point_of_sale/app/components/category_selector/category_selector";

/**
 * Category navigation, rendered in the navbar next to the search field.
 *
 * This extends CategorySelector rather than reimplementing it: the parent
 * already resolves the category tree correctly (ordering, "All", sub-categories,
 * the hasProductsToShow filter and the colour to use). Only the template differs,
 * so none of that logic is duplicated or can drift from core.
 */
export class CategoryDropdown extends CategorySelector {
    static template = "kula_pos_layout.CategoryDropdown";
    static components = { Dropdown, DropdownItem };
    static props = {};

    /** Selected category, or "All" when nothing is selected. */
    get currentName() {
        return this.pos.selectedCategory?.name || _t("All");
    }

    get currentColor() {
        return this.pos.selectedCategory?.color || 0;
    }

    /** "All" first, then the regular categories. */
    get categories() {
        return this.getCategoriesAndSub();
    }

    selectCategory(categoryId) {
        this.pos.setSelectedCategory(categoryId);
    }
}
