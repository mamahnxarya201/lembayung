/**
 * KULA Security -- the Access Matrix.
 *
 * The page the owner asked for: a table, one row per installed menu, one
 * column per role, and in every cell the degree that role has -- no access,
 * read only, or read & write -- with the roles chosen from the table header's
 * column control, the way a list view offers its optional columns.
 *
 * A cell shows the *current* situation, not this page's intent. What a role may
 * do is the sum of every access row that applies to it: the groups it implies
 * (Role / User above all), the ACLs the other apps declare (in this repository,
 * the kiosk rights kula_security hands the two POS roles), and this page's own
 * rows. So the cell shows the access the
 * role actually has, the tooltip says where it comes from, and the degrees a
 * role already holds from elsewhere are locked in the control -- because the
 * page only adds (models/kula_access_rule.py owns that rule): what it wrote
 * itself it can take back, on the cell's own column or on an implied group's,
 * and what another group grants it never touches.
 *
 * It wears Odoo's own chrome rather than its own: the control panel's
 * breadcrumb is the page title, the standard search bar (over `ir.ui.menu`,
 * because the rows *are* menus) searches the tree, Save and Discard sit where
 * a form puts them, and the view-level actions live in the cog menu. Only the
 * table in the middle is this module's own.
 *
 * The page is a view *over* Odoo's security rather than a second copy of it:
 * the roles, the menu tree and the degrees all come out of the database, and
 * Save hands the changed cells back for the server to write onto the menu and
 * the model behind it. The whole table is one round trip; a search is one more,
 * with the domain the search bar built.
 *
 * One thing the page refuses to hide: a page is only reachable when the menus
 * above it are offered to the role too, and a cell whose access cannot be
 * reached yet is marked as such.
 */
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { WithSearch } from "@web/search/with_search/with_search";

/** The three degrees, weakest first -- the order they are offered in. */
const LEVELS = ["none", "read", "write"];
const LEVEL_RANK = { none: 0, read: 1, write: 2 };
const LEVEL_LABELS = {
    none: _t("No access"),
    read: _t("Read only"),
    write: _t("Read & write"),
};
const LEVEL_HELP = {
    none: _t("Nothing from this page: it grants no access right here. Whatever other groups give the role is left as it is."),
    read: _t("May open the page and look at records."),
    write: _t("May open the page, look at, add and change records. Deleting is never granted here."),
};

/** Where the chosen roles are remembered, like the sidebar remembers its shape. */
const ROLES_STORAGE_KEY = "kula_access_matrix_roles";

/**
 * The page itself, inside the search bar's slot.
 *
 * It is a separate component from the action because that is what it takes to
 * be *inside* the `WithSearch`: the domain the search bar builds arrives here
 * as a prop, and a new one is a new set of rows.
 */
export class KulaAccessMatrixBody extends Component {
    static template = "kula_access_matrix.AccessMatrixBody";
    static components = { CheckBox, Dropdown, DropdownItem, Layout, SearchBar };
    static props = {
        domain: { type: Array, optional: true },
        display: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            saving: false,
            groups: [],
            candidates: [],
            menus: [],
            nodes: {},
            pending: {},
            collapsed: {},
        });
        this.domainKey = this.domainString(this.props.domain);
        // null rather than []: nothing stored means "the roles this module
        // defines", while an empty list means the admin removed every column.
        onWillStart(() => this.load(readRoleIds(), this.props.domain));
        onWillUpdateProps(async (nextProps) => {
            const key = this.domainString(nextProps.domain);
            if (key !== this.domainKey) {
                this.domainKey = key;
                // A search is a look at the same rules through a narrower window:
                // cells already changed but not saved stay changed.
                await this.load(this.roleIds, nextProps.domain, { keepPending: true });
            }
        });
    }

    domainString(domain) {
        return JSON.stringify(domain || []);
    }

    // ------------------------------------------------------------------ //
    // Data
    // ------------------------------------------------------------------ //
    async load(groupIds, domain, { keepPending = false } = {}) {
        this.state.loading = true;
        try {
            const data = await this.orm.call("kula.access.rule", "kula_matrix_data", [
                groupIds === null ? false : groupIds,
                domain && domain.length ? domain : false,
            ]);
            this.state.groups = data.groups;
            this.state.candidates = data.candidates;
            this.state.nodes = {};
            this.state.menus = this.prepare(data.menus);
            if (!keepPending) {
                this.state.pending = {};
            }
            const searching = !!(domain && domain.length);
            if (!this.initialised || (this.searched && !searching)) {
                // Open on the apps, with everything below them folded: nine
                // rows to choose from instead of three hundred. Also what comes
                // back when a search is cleared.
                this.initialised = true;
                this.state.collapsed = {};
                this.collapseDeep(data.menus, 0);
            }
            if (searching) {
                // A search opens what it found: a match three levels down is no
                // use folded away.
                this.state.collapsed = {};
            }
            this.searched = searching;
            writeRoleIds(this.roleIds);
        } finally {
            this.state.loading = false;
        }
    }

    /** Index every menu by id, so a cell can be looked up from its key. */
    prepare(nodes) {
        return nodes.map((node) => {
            const prepared = {
                id: node.id,
                name: node.name,
                model: node.model,
                open: node.open,
                cells: node.cells,
                children: this.prepare(node.children),
            };
            this.state.nodes[node.id] = prepared;
            return prepared;
        });
    }

    collapseDeep(nodes, depth) {
        for (const node of nodes) {
            if (depth > 0 && node.children.length) {
                this.state.collapsed[node.id] = true;
            }
            this.collapseDeep(node.children, depth + 1);
        }
    }

    get roleIds() {
        return this.state.groups.map((group) => group.id);
    }

    /**
     * Every role in Odoo, under the app it belongs to, with the ones shown as
     * columns ticked -- the shape of a list view's optional-columns control.
     */
    get roleChoices() {
        const shown = new Set(this.roleIds);
        const byPrivilege = new Map();
        for (const group of this.state.candidates) {
            const privilege = group.privilege || _t("Other");
            if (!byPrivilege.has(privilege)) {
                byPrivilege.set(privilege, []);
            }
            byPrivilege.get(privilege).push({
                id: group.id,
                name: group.name,
                shown: shown.has(group.id),
            });
        }
        return [...byPrivilege].map(([privilege, groups]) => ({ privilege, groups }));
    }

    isRoleShown(group) {
        return this.roleIds.includes(group.id);
    }

    async toggleRole(group) {
        const ids = this.isRoleShown(group)
            ? this.roleIds.filter((id) => id !== group.id)
            : [...this.roleIds, group.id];
        await this.load(ids, this.props.domain, { keepPending: true });
    }

    /**
     * The cells that really changed. A cell put back to what it was drops out,
     * so Save only carries differences and Discard has nothing to undo.
     */
    get changes() {
        const changes = [];
        for (const [key, level] of Object.entries(this.state.pending)) {
            const [menuId, groupId] = key.split(":").map(Number);
            const stored = this.cellById(menuId, groupId).level || "none";
            if (level !== stored) {
                changes.push({ menu_id: menuId, group_id: groupId, level });
            }
        }
        return changes;
    }

    get dirty() {
        return this.changes.length > 0;
    }

    get dirtyMenuIds() {
        return new Set(this.changes.map((change) => change.menu_id));
    }

    get levels() {
        return LEVELS;
    }

    // ------------------------------------------------------------------ //
    // Labels, tooltips and hints
    // ------------------------------------------------------------------ //
    get tooltipRoles() {
        return _t("Roles: tick the ones to show as columns");
    }

    get tooltipActions() {
        return _t("Actions");
    }

    get expandLabel() {
        return _t("Expand all");
    }

    get collapseLabel() {
        return _t("Collapse all");
    }

    // ------------------------------------------------------------------ //
    // One cell
    // ------------------------------------------------------------------ //
    /** The stored cell of a (menu id, role id) pair, wherever the row is. */
    cellById(menuId, groupId) {
        const node = this.state.nodes[menuId];
        return ((node && node.cells) || {})[groupId] || {};
    }

    /**
     * The stored cell for a row: the role's access today (`effective`), the
     * part of it that comes from other groups (`floor`), what this page grants
     * on its own (`level`), and whether the page can be reached at all.
     */
    cell(node, group) {
        return this.cellById(node.id, group.id);
    }

    /**
     * What the role would have if the page were saved -- which is what the cell
     * shows, since the table is about the access a role has, not about this
     * page's intent. The intent is what the page adds: a degree at or below the
     * floor would add nothing (the server drops the rule in that case), so the
     * cell shows the floor itself.
     */
    cellLevel(node, group) {
        const floor = this.cellFloor(node, group);
        const intent = this.cellIntent(node, group);
        return LEVEL_RANK[intent] > LEVEL_RANK[floor] ? intent : floor;
    }

    /** What this page would grant here: the pending choice, or the stored rule. */
    cellIntent(node, group) {
        const key = `${node.id}:${group.id}`;
        return key in this.state.pending
            ? this.state.pending[key]
            : this.cell(node, group).level || "none";
    }

    /** What the role already has from anywhere but this page's own row. */
    cellFloor(node, group) {
        return this.cell(node, group).floor || "none";
    }

    cellDirty(node, group) {
        const key = `${node.id}:${group.id}`;
        return key in this.state.pending && this.state.pending[key] !== this.cellStored(node, group);
    }

    cellStored(node, group) {
        return this.cell(node, group).level || "none";
    }

    /**
     * An option the matrix cannot honour, because the role has it already from
     * another group: the page only adds, so a lower degree is not a choice it
     * can make -- it would be a claim the ACL would contradict.
     */
    levelLocked(node, group, level) {
        return LEVEL_RANK[level] < LEVEL_RANK[this.cellFloor(node, group)];
    }

    /**
     * "Read & write" says nothing about a menu that only groups pages: there is
     * no model behind it to write to, so its degree is the page's visibility and
     * "read" is all of it.
     */
    levelApplicable(node, level) {
        return level !== "write" || !!node.model;
    }

    /** True when the cell's access cannot be reached: a menu above it is closed. */
    cellBlocked(node, group) {
        return !!this.cell(node, group).blocked && this.cellLevel(node, group) !== "none";
    }

    levelLabel(level) {
        return LEVEL_LABELS[level] || level;
    }

    levelHelp(level) {
        return LEVEL_HELP[level] || "";
    }

    /**
     * Where the cell's degree comes from, when there is something to say: the
     * access other groups already give the role, and what this page adds to it.
     * Nothing to say means an untouched cell -- nothing to explain.
     */
    cellHelp(node, group) {
        const floor = this.cellFloor(node, group);
        const own = this.cell(node, group).level || "none";
        const parts = [];
        if (!node.model) {
            // A grouping menu: the degree is who is offered the group of pages.
            if (floor !== "none" && node.open) {
                parts.push(
                    _t("This menu only groups pages and has no group restriction: Odoo offers it to everyone, so this page cannot keep it from a role.")
                );
            } else if (floor !== "none") {
                parts.push(
                    _t("Offered to this role through another group that is already on this menu, and this page only adds -- it cannot take that back.")
                );
            }
        } else if (floor !== "none") {
            parts.push(
                _t("Already granted: other groups give this role %(level)s here (Odoo's own groups, like Role / User, and the ACLs the other apps declare), and this page only adds: it cannot take that back.", {
                    level: this.levelLabel(floor),
                })
            );
        }
        if (own !== "none") {
            parts.push(_t("This page grants %(level)s on top of that.", { level: this.levelLabel(own) }));
        }
        return parts.length ? parts.join(" ") : null;
    }

    lockedHelp(node, group) {
        if (!node.model && node.open) {
            return _t(
                "Not available: this menu has no group restriction, so every role already has it."
            );
        }
        return _t(
            "Not available: this role already has %(level)s here from another group. This page only adds rights, so picking this would change nothing.",
            { level: this.levelLabel(this.cellFloor(node, group)) }
        );
    }

    blockedHelp() {
        return _t(
            "Out of reach: the role has the access, but a menu above this one is not granted to it, so nobody gets to this page yet."
        );
    }

    // ------------------------------------------------------------------ //
    // Rows on screen
    // ------------------------------------------------------------------ //
    /** The tree flattened, with the folds applied. */
    get visibleRows() {
        const rows = [];
        const walk = (nodes, depth) => {
            for (const node of nodes) {
                rows.push({ node, depth });
                if (!this.state.collapsed[node.id]) {
                    walk(node.children, depth + 1);
                }
            }
        };
        walk(this.state.menus, 0);
        return rows;
    }

    folded(node) {
        return !!this.state.collapsed[node.id];
    }

    indent(depth) {
        return `${8 + depth * 20}px`;
    }

    onToggle(node) {
        if (!node.children.length) {
            // A leaf has nothing to fold, and clicking its row should not do
            // anything -- tables are where people select text.
            return;
        }
        this.state.collapsed[node.id] = !this.state.collapsed[node.id];
    }

    expandAll() {
        this.state.collapsed = {};
    }

    collapseAll() {
        const collapsed = {};
        const walk = (nodes) => {
            for (const node of nodes) {
                if (node.children.length) {
                    collapsed[node.id] = true;
                }
                walk(node.children);
            }
        };
        walk(this.state.menus);
        this.state.collapsed = collapsed;
    }

    // ------------------------------------------------------------------ //
    // Editing
    // ------------------------------------------------------------------ //
    onLevelChange(node, group, level) {
        const key = `${node.id}:${group.id}`;
        const stored = this.cellStored(node, group);
        if (level === stored) {
            // Put back the way it was: the key goes with it, so the cell stops
            // being dirty and Save no longer carries it.
            delete this.state.pending[key];
        } else {
            this.state.pending[key] = level;
        }
    }

    discard() {
        this.state.pending = {};
    }

    async save() {
        const changes = this.changes;
        if (!changes.length || this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const summary = await this.orm.call("kula.access.rule", "kula_apply_matrix", [changes]);
            await this.load(this.roleIds, this.props.domain);
            this.notification.add(
                _t("Saved %(cells)s change(s). This page now grants %(rules)s rule(s) and writes %(access)s access right(s).", {
                    cells: summary.cells,
                    rules: summary.rules,
                    access: summary.access,
                }),
                { type: "success" }
            );
        } finally {
            this.state.saving = false;
        }
    }
}

/**
 * The action: Odoo's search over the menus.
 *
 * The rows of this page are `ir.ui.menu` records, so the page can borrow the
 * whole search apparatus -- the search bar, its facets, the domain they build
 * -- by declaring that as the model. The arch is this module's own rather than
 * the Menu Items screen's: that one offers an "Archived" filter, and an
 * archived menu is not in the table to begin with.
 */
export class KulaAccessMatrix extends Component {
    static template = "kula_access_matrix.AccessMatrix";
    static components = { KulaAccessMatrixBody, WithSearch };

    setup() {
        this.searchProps = {
            resModel: "ir.ui.menu",
            searchViewId: false,
            searchViewArch:
                '<search><field name="name" string="Menu"/><field name="parent_id"/></search>',
            searchViewFields: {
                name: { name: "name", string: _t("Menu"), type: "char" },
                parent_id: {
                    name: "parent_id",
                    string: _t("Parent Menu"),
                    type: "many2one",
                    relation: "ir.ui.menu",
                },
            },
            // Facets filter the menus; there is nothing to group or to
            // favourite in a table whose rows are the tree itself.
            searchMenuTypes: ["filter"],
        };
        this.display = { controlPanel: true };
    }
}

registry.category("actions").add("kula_access_matrix.access_matrix", KulaAccessMatrix);

/**
 * The roles shown, remembered per browser.
 *
 * null is a real answer here: it means the admin never chose, and the server
 * then opens the page on the roles this module defines.
 */
function readRoleIds() {
    const stored = browser.localStorage.getItem(ROLES_STORAGE_KEY);
    if (!stored) {
        return null;
    }
    try {
        const ids = JSON.parse(stored);
        return Array.isArray(ids) ? ids : null;
    } catch {
        // A corrupted entry is not worth failing the page over: fall back to
        // the roles this module defines.
        return null;
    }
}

function writeRoleIds(ids) {
    browser.localStorage.setItem(ROLES_STORAGE_KEY, JSON.stringify(ids));
}
