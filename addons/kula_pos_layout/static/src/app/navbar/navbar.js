import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { CategoryDropdown } from "./category_dropdown";

// The navbar template is extended to render <CategoryDropdown/>, so the class
// has to know about it. `components` is a static, hence patching the class
// itself rather than its prototype.
patch(Navbar, {
    components: { ...Navbar.components, CategoryDropdown },
});
