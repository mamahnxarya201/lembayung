/**
 * KULA Workspace -- the Dashboard.
 *
 * The page a non-kiosk user lands on at log on (res.users.action_id points
 * here, see the module's hooks) and the first row in the sidebar. It is
 * deliberately empty: the owner will decide what it shows.
 *
 * A client action rather than a model view, because there is nothing to
 * display yet and nothing to load: no ORM round trip, no control panel, just
 * the title over an empty canvas.
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class KulaDashboard extends Component {
    static template = "kula_workspace.Dashboard";

    get title() {
        return _t("Dashboard");
    }
}

registry.category("actions").add("kula_workspace.dashboard", KulaDashboard);
