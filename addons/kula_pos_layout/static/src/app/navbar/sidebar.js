import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";

/**
 * The burger menu, as a sidebar the navbar can close.
 *
 * Core's dropdown state lives inside the Dropdown component, which is fine for
 * a menu that closes itself on an outside click but not for a drawer: the scrim
 * that dims the register is a click-catcher *outside* the POS's active element,
 * and core's click-away deliberately ignores those (so that clicking into
 * another dialog does not close a menu). Two consequences on the product screen:
 * a tap on the scrim would neither close the drawer nor reach what is behind it.
 *
 * `useDropdownState` is the Dropdown's own answer to that: the state is created
 * here and handed to it through the `state` prop, so the scrim (navbar.xml) can
 * close the menu with the same object the menu uses for everything else. Nothing
 * about the menu's contents changes — the items, their conditions and pos_hr's
 * gating all stay core's.
 */
patch(Navbar.prototype, {
    setup() {
        super.setup();
        this.kulaBurger = useDropdownState();
        // The drawer's "Update App" entry, and the dot on the burger that says
        // one exists (update_app.js): the service owns the polling and the
        // reload, the template only reads `available`.
        this.kulaUpdate = useService("kula_update");
    },
});
