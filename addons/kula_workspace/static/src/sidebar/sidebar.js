/**
 * KULA Workspace -- the left navigation sidebar.
 *
 * A trimmed descendant of suaraloka_workspace's sidebar (odoo-skripsi). The
 * mechanism is the same and deliberately so: the tree is built from Odoo's own
 * menu service, not from a hand-written list of links, so it follows installed
 * modules, user groups and translations on its own, and the curated allow-list
 * below only decides *which* apps appear.
 *
 * What changed for this repo: the curated list is the five apps this project is
 * about, the project/CPM machinery (project nodes, "My Projects", boards, the
 * task panel) is gone, and the POS register gets a row of its own -- it is a
 * client route, not a menu, so it cannot come out of the menu service.
 */
import { Component, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { WebClient } from "@web/webclient/webclient";
import {
    SIDEBAR_STATE_EVENT,
    SIDEBAR_TOGGLE_EVENT,
    SMALL_SCREEN_QUERY,
    readSidebarShape,
} from "./sidebar_state";

/**
 * The sidebar's apps, in display order, by menu xmlid.
 *
 * Everything this project needs and nothing else: the mid-transaction apps
 * (kiosk register, point of sale, inventory, employees, invoicing). Anything
 * missing, uninstalled or hidden from the current user is skipped, so the same
 * list stays valid on another database. Edit this list to change what the
 * sidebar shows; nothing else has to move.
 */
const CURATED_APP_XMLIDS = [
    "point_of_sale.menu_point_root",
    "stock.menu_stock_root",
    "hr.menu_hr_root",
    "account.menu_finance",
];

/**
 * The Dashboard row, first in the sidebar.
 *
 * The Dashboard page is a client action with a path (`/odoo/dashboard`), and a
 * client action has no `ir.ui.menu` behind it, so like the Kiosk row below it
 * this row is synthetic: the click handler opens the action by xmlid and the
 * route is what lights the row up. Negative id, kept out of the menu service's
 * id space like the Kiosk row's.
 */
const DASHBOARD_NODE_ID = -2;
const DASHBOARD_MENU_XMLID = "kula_workspace.menu_dashboard";
const DASHBOARD_PATH = "dashboard";
/** The Dashboard's client-action tag: what the loaded action identifies itself by. */
const DASHBOARD_TAG = "kula_workspace.dashboard";

/**
 * The Kiosk row.
 *
 * The register is `/pos/ui/<config_id>`, a client route with no `ir.ui.menu`
 * behind it, so it cannot be curated like the others: this row is synthetic and
 * its click handler resolves the config and opens it. Negative id, like every
 * other non-menu row, to keep it out of the menu service's id space.
 */
const KIOSK_NODE_ID = -1;
const KIOSK_MENU_XMLID = "kula_workspace.menu_kiosk";

const HIDDEN_APP_XMLIDS = [
    // Chat, removed (see theme/chat.scss): the Discuss app must not be offered
    // as a destination either, so it is filtered out even when it is the app the
    // user happens to be in.
    "mail.menu_root_discuss",
];

/** Children the sidebar never shows: stock Odoo dumps its config here. */
const HIDDEN_CHILD_NAMES = ["Configuration"];

const HIDDEN_CHILD_XMLIDS = [
    "point_of_sale.menu_point_config_product",
    "stock.menu_stock_config_settings",
    "hr.menu_human_resources_configuration",
    "account.menu_finance_configuration",
];

/**
 * Icons for the tree's children.
 *
 * An app shows its own artwork (`webIconData`); a child row gets a glyph on a
 * tinted tile instead -- the same tile shape, an icon of its own, so a subtree
 * does not read as the parent's logo repeated. `[keywords, glyph, tone]`,
 * first match wins, matched against the lowercased menu name.
 */
const CHILD_ICON_RULES = [
    [["order", "session"], "fa-shopping-cart", "blue"],
    [["product"], "fa-cube", "orange"],
    [["report", "analytic", "statistic"], "fa-bar-chart", "purple"],
    [["employee", "staff", "human", "department"], "fa-users", "green"],
    [["invoice", "bill", "payment", "journal", "account"], "fa-file-text-o", "teal"],
    [["stock", "inventor", "warehouse", "operation", "transfer"], "fa-exchange", "blue"],
    [["customer", "partner", "contact"], "fa-address-book-o", "green"],
    [["pricelist", "setting", "config"], "fa-sliders", "red"],
];

const CHILD_ICON_FALLBACK = ["fa-circle-o", "blue"];

// --------------------------------------------------------------------------- #
// Tree nodes
//
// Two mutually recursive components rather than one self-referencing one: a
// class cannot list itself in its own static `components`, and assigning the
// properties after both declarations keeps the definitions readable.
// --------------------------------------------------------------------------- #
export class SidebarNode extends Component {
    static template = "kula_workspace.SidebarNode";
    static props = {
        node: Object,
        depth: Number,
        version: Number,
        activeMenuId: Number,
        // The app's own artwork and the glyph that stands in for it (the Kiosk
        // row has no artwork). Both are handed down the tree so a child row
        // carries the same icon as the app it belongs to.
        iconSrc: { type: [String, Boolean], optional: true },
        iconGlyph: { type: String, optional: true },
        isExpanded: Function,
        onSelect: Function,
        onToggle: Function,
    };

    setup() {
        this.labelRef = useRef("labelRef");
        // The panel is 260px wide and menu names are not: measure the label once
        // it is in the DOM (and again whenever the tree re-renders) and let the
        // CSS scroll the ones that do not fit.
        useEffect(
            () => this.measureLabel(),
            () => [this.props.node.name, this.props.version]
        );
    }

    /**
     * Marquee for a label the panel cannot fit.
     *
     * The distance is *measured*: CSS cannot know how far a text overflows its
     * box, so the row hands the overflow over in a custom property and the
     * keyframes read it. `alternate` plus the flat ends of the keyframes give
     * the pause at both ends, and the duration grows with the distance so a long
     * name does not scroll faster than a short one.
     */
    measureLabel() {
        const label = this.labelRef.el;
        if (!label) {
            return;
        }
        const distance = label.scrollWidth - label.clientWidth;
        if (distance > 2) {
            label.style.setProperty("--o-sw-marquee-distance", `${-distance}px`);
            label.style.setProperty(
                "--o-sw-marquee-duration",
                `${(distance / 12 + 6).toFixed(1)}s`
            );
            label.classList.add("o_sw_scrolls");
        } else {
            label.classList.remove("o_sw_scrolls");
        }
    }

    get hasChildren() {
        return (this.props.node.childrenTree || []).length > 0;
    }

    get expanded() {
        return this.hasChildren && this.props.isExpanded(this.props.node);
    }

    get active() {
        return this.props.node.id === this.props.activeMenuId;
    }

    /** A child row's icon: a glyph on a colour-filled tile, from CHILD_ICON_RULES. */
    get childIcon() {
        const name = (this.props.node.name || "").toLowerCase();
        const rule = CHILD_ICON_RULES.find(([keywords]) =>
            keywords.some((keyword) => name.includes(keyword))
        );
        const [glyph, tone] = rule ? [rule[1], rule[2]] : CHILD_ICON_FALLBACK;
        return { glyph, tone };
    }
}

export class SidebarChildren extends Component {
    static template = "kula_workspace.SidebarChildren";
    static props = {
        nodes: Array,
        depth: Number,
        version: Number,
        activeMenuId: Number,
        isExpanded: Function,
        onSelect: Function,
        onToggle: Function,
    };
}

SidebarNode.components = { SidebarChildren };
SidebarChildren.components = { SidebarNode };

// --------------------------------------------------------------------------- #
// Sidebar
// --------------------------------------------------------------------------- #
export class KulaSidebar extends Component {
    static template = "kula_workspace.Sidebar";

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.navRef = useRef("navRef");

        const shape = readSidebarShape();
        this.state = useState({
            expanded: {},
            // Bumped on every expand/collapse. The tree nodes are child
            // components, and OWL skips re-rendering a child whose props did not
            // change; the expansion map is never a prop, so without this counter
            // a toggle would update the state and repaint nothing.
            expansionVersion: 0,
            activeMenuId: 0,
            activeAppId: 0,
            // Several menus can share one action, so this is what keeps the
            // highlight on the row that was clicked instead of a duplicate.
            preferredMenuId: 0,
            mobileOpen: shape.mobileOpen,
            closed: shape.closed,
        });

        const updateActive = () => this.updateActiveMenu();
        const onToggle = () => this.toggleSidebar();
        // The action manager announces every mounted action on the environment
        // bus, and it does so after the controller is in place, so the action is
        // readable from the handler. This is the event the sidebar needs: the
        // router's own ROUTE_CHANGE (see the import note above) fires for
        // back/forward and anchor clicks only, never for the programmatic pushes
        // that menus, the home action and the Dashboard row all go through --
        // which is why the highlight used to sit still after the first render.
        this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", updateActive);
        this.env.bus.addEventListener(SIDEBAR_TOGGLE_EVENT, onToggle);
        onWillUnmount(() => {
            this.env.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", updateActive);
            this.env.bus.removeEventListener(SIDEBAR_TOGGLE_EVENT, onToggle);
        });

        onMounted(() => {
            this.applyBodyClasses();
            this.updateActiveMenu();
        });
    }

    /**
     * The layout classes the stylesheet keys off. The sidebar is part of the
     * layout rather than an overlay, so `o_kula_sidebar_on` reserves its width
     * and the action manager shifts over.
     */
    applyBodyClasses() {
        // `document`, not `browser.document`: Odoo's browser object carries
        // location/localStorage/matchMedia and friends, but not the document.
        const body = document.body;
        body.classList.add("o_kula_sidebar_on");
        body.classList.toggle("o_sw_sidebar_closed", this.state.closed);
        body.classList.toggle("o_sw_sidebar_mobile_open", this.state.mobileOpen);
    }

    toggleSidebar() {
        this.state.closed = !this.state.closed;
        this.applyBodyClasses();
        this.env.bus.dispatchEvent(SIDEBAR_STATE_EVENT, {
            closed: this.state.closed,
            pinned: true,
            mobileOpen: this.state.mobileOpen,
        });
    }

    closeMobile() {
        this.state.mobileOpen = false;
        this.applyBodyClasses();
    }

    /** The Dashboard row, which the menu service cannot provide either. */
    dashboardNode() {
        return {
            id: DASHBOARD_NODE_ID,
            name: _t("Dashboard"),
            xmlid: DASHBOARD_MENU_XMLID,
            childrenTree: [],
            kula_dashboard: true,
        };
    }

    /** The Kiosk row, which the menu service cannot provide. */
    kioskNode() {
        return {
            id: KIOSK_NODE_ID,
            name: _t("Kiosk"),
            xmlid: KIOSK_MENU_XMLID,
            childrenTree: [],
            kula_kiosk: true,
        };
    }

    get apps() {
        const byXmlid = new Map(this.menuService.getAll().map((menu) => [menu.xmlid, menu]));
        const nodes = CURATED_APP_XMLIDS.map((xmlid) => byXmlid.get(xmlid))
            .filter(Boolean)
            .map((menu) => this.menuService.getMenuAsTree(menu.id));
        // The app the user is in is always part of the tree, curated or not. The
        // sidebar *is* the navigation now (the top bar's own app switcher and
        // section menus are hidden by sidebar.scss), so an app outside the
        // curated list would otherwise have no way to reach its own submenus.
        const current = this.menuService.getCurrentApp();
        if (
            current &&
            !CURATED_APP_XMLIDS.includes(current.xmlid) &&
            !HIDDEN_APP_XMLIDS.includes(current.xmlid)
        ) {
            nodes.push(this.menuService.getMenuAsTree(current.id));
        }
        // The Dashboard and the Kiosk row lead the list, in that order: the
        // owner asked for the Dashboard above the Kiosk menu.
        return [this.dashboardNode(), this.kioskNode(), ...nodes.map((node) => this.curate(node))];
    }

    /**
     * Fold away the levels the stock menus only repeat.
     *
     * A tree that repeats itself says nothing, so:
     *   - a hidden row goes, and takes its subtree with it -- dissolving a
     *     hidden branch instead would resurrect the Configuration pages this
     *     list exists to keep out;
     *   - a child branch carrying its parent's name is hoisted, its own children
     *     taking its place: "Inventory > Products > Products" loses one level;
     *   - a leaf child carrying its parent's name is absorbed into the parent
     *     row, which then opens that page itself.
     *
     * A branch that absorbed a page carries that page's action, or the row would
     * still not navigate; the ids it absorbed are kept in `kula_page_ids`, which
     * is how the highlight finds a row that now stands for a page the tree no
     * longer shows.
     */
    curate(node) {
        const children = [];
        let result = node;
        for (const child of node.childrenTree || []) {
            if (this.isHiddenChild(child)) {
                continue;
            }
            const curated = this.curate(child);
            const grandChildren = curated.childrenTree || [];
            if (this.sameName(child, node) && grandChildren.length) {
                children.push(...grandChildren);
            } else if (this.sameName(child, node) && child.actionID) {
                result = {
                    ...result,
                    actionID: result.actionID || child.actionID,
                    kula_page_ids: [...(result.kula_page_ids || []), child.id],
                };
            } else {
                children.push(curated);
            }
        }
        return { ...result, childrenTree: children };
    }

    isHiddenChild(node) {
        return (
            HIDDEN_CHILD_NAMES.includes(node.name) || HIDDEN_CHILD_XMLIDS.includes(node.xmlid)
        );
    }

    sameName(child, parent) {
        return !!child.name && child.name === parent.name;
    }

    /** Every menu id the tree currently shows, absorbed pages included. */
    get visibleMenuIds() {
        const ids = new Set();
        const walk = (node) => {
            ids.add(node.id);
            for (const id of node.kula_page_ids || []) {
                ids.add(id);
            }
            for (const child of node.childrenTree || []) {
                walk(child);
            }
        };
        for (const app of this.apps) {
            walk(app);
        }
        return ids;
    }

    /** The route the browser is on, without Odoo's `/odoo` prefix. */
    get currentPath() {
        return (browser.location.pathname || "").replace(/^\/odoo\/?/, "");
    }

    /**
     * The menu whose action path is the page's route, if any.
     *
     * Several menus can point at the same action (a parent and its page often
     * do), so the row the user *clicked* wins (`preferredMenuId`), then the
     * first one the tree actually shows. Without this the highlight lands on
     * whichever duplicate the menu service lists first and the row just clicked
     * never lights up.
     */
    menuFromLocation() {
        const path = this.currentPath;
        if (!path) {
            return null;
        }
        return this.pickVisibleRow(
            this.menuService.getAll().filter((menu) => menu.actionPath === path)
        );
    }

    /** The menu that opens the action currently on screen, if any. */
    menuForAction(action) {
        if (!action) {
            return null;
        }
        return this.pickVisibleRow(
            this.menuService.getAll().filter((menu) => menu.actionID === action.id)
        );
    }

    /** Of several candidate rows, the one to highlight (the clicked one wins). */
    pickVisibleRow(matches) {
        const visible = this.visibleMenuIds;
        return (
            matches.find(
                (menu) => menu.id === this.state.preferredMenuId && visible.has(menu.id)
            ) ||
            matches.find((menu) => visible.has(menu.id)) ||
            matches[0] ||
            null
        );
    }

    /**
     * Mark the row that stands for what is on screen.
     *
     * The action decides, not the URL. The router writes the URL in a debounced
     * push and then announces the action (action_service's `_updateUI`: it calls
     * pushState and only then triggers the announcement), so at this point the
     * URL still names the page the user just left -- matching on it would light
     * the row they came from. The URL is what the *mount* has to go on, before
     * any action exists, which is the deep-link case.
     */
    updateActiveMenu() {
        const action = this.actionService.currentController?.action;
        // The Dashboard is a client action with no menu behind it: its tag
        // lights the synthetic row up, or its route while no action is loaded
        // yet (a reload straight onto /odoo/dashboard).
        const onDashboard = action
            ? action.tag === DASHBOARD_TAG
            : this.currentPath === DASHBOARD_PATH;
        if (onDashboard) {
            this.state.activeMenuId = DASHBOARD_NODE_ID;
            this.state.activeAppId = 0;
            return;
        }
        const menu = this.menuForAction(action) || this.menuFromLocation();
        this.state.activeMenuId = menu ? menu.id : 0;
        this.state.activeAppId =
            (menu && menu.appID) || this.menuService.getCurrentApp()?.id || 0;
        if (menu) {
            this.expandPathTo(menu.id);
        }
    }

    /** Open the branches above the active row, so the highlight is visible. */
    expandPathTo(targetId) {
        const walk = (node, ancestors) => {
            const hit =
                node.id === targetId || (node.kula_page_ids || []).includes(targetId);
            if (hit) {
                for (const id of ancestors) {
                    this.state.expanded[id] = true;
                }
                return true;
            }
            for (const child of node.childrenTree || []) {
                if (walk(child, [...ancestors, node.id])) {
                    return true;
                }
            }
            return false;
        };
        for (const app of this.apps) {
            if (walk(app, [])) {
                this.state.expansionVersion++;
                return;
            }
        }
    }

    /**
     * Bound as properties, not methods: the template hands them to child
     * components as values (`isExpanded="isExpanded"`), and a plain method
     * arrives unbound, so `this` would be undefined inside the child.
     */
    isExpanded = (node) => {
        return !!this.state.expanded[node.id];
    };

    /** The row's own icon: the Kiosk and Dashboard rows have none of their own. */
    appIconGlyph = (node) => {
        if (node.kula_dashboard) {
            return "fa-th-large";
        }
        return node.kula_kiosk ? "fa-shopping-basket" : "";
    };

    onNodeSelect = async (node) => {
        const small = browser.matchMedia(SMALL_SCREEN_QUERY).matches;
        if (node.kula_dashboard) {
            await this.openDashboard();
        } else if (node.kula_kiosk) {
            await this.openKiosk();
        } else if ((node.childrenTree || []).length) {
            // Like a tree view: clicking a branch opens it, the caret closes it.
            this.state.expanded[node.id] = true;
            this.state.expansionVersion++;
            if (node.actionID) {
                this.state.preferredMenuId = node.id;
                await this.menuService.selectMenu(node);
            }
        } else if (node.actionID) {
            this.state.preferredMenuId = node.id;
            await this.menuService.selectMenu(node);
        }
        if (small) {
            this.closeMobile();
        }
    };

    onNodeToggle = (node) => {
        this.state.expanded[node.id] = !this.isExpanded(node);
        this.state.expansionVersion++;
    };

    /**
     * Open the Dashboard.
     *
     * By xmlid rather than by id: the action is the module's own record, so
     * there is nothing to resolve and nothing that can be missing.
     * `clearBreadcrumbs` mirrors what the menu service does for a menu row, so
     * the Dashboard replaces the page (and the breadcrumb) instead of stacking
     * on top of it.
     */
    async openDashboard() {
        await this.actionService.doAction("kula_workspace.action_dashboard", {
            clearBreadcrumbs: true,
        });
    }

    /**
     * Open the register.
     *
     * `pos.config` is resolved here rather than at render time: the row exists
     * for every user, but most of them never click it, and a database with no
     * POS configured should leave the row inert instead of failing to load.
     */
    async openKiosk() {
        const [config] = await this.orm.searchRead("pos.config", [], ["id"], { limit: 1 });
        if (!config) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_url",
            url: `/pos/ui/${config.id}`,
            target: "self",
        });
    }
}

KulaSidebar.components = { SidebarNode };

// The sidebar is injected by kula_workspace.WebClientSidebar (sidebar.xml). An
// OWL template can only use components its host component declares, so the web
// client has to be told about this one.
patch(WebClient, {
    components: { ...WebClient.components, KulaSidebar },
});
