/**
 * Kiosk-only access for the cashier and barista roles.
 *
 * One mechanism, not two: signing in lands a cashier or barista in the register,
 * and loading the backend at any later point sends them back to it. Both are the
 * same rule -- "a member of group_kiosk_only has no business in the backend" --
 * so they are the same code.
 *
 * Why a client-side guard rather than groups. An Odoo group can grant a menu but
 * never take one away, and `base.group_user` (which these roles must have to load
 * the register at all, since /pos/ui is a backend route) already pulls in implied
 * groups carrying dozens of menus. There is no group-only way to leave a member
 * with a working register and an empty backend, so the rule is enforced where the
 * decision is actually made: the web client will not stay open for them. That is
 * also why the role groups still carry `group_pos_user` -- its access rights are
 * what the register needs to create a session and take orders.
 *
 * The boundary this draws: it is a UI guard. The members' model rights are POS
 * User's, so a crafted RPC is still possible. If the counter ever needs a hard
 * boundary, the next step is a dedicated group with hand-rolled ACLs rather than
 * `group_pos_user`, not a bigger guard.
 */
import { onMounted } from "@odoo/owl";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

const KIOSK_ONLY_GROUP = "kula_security.group_kiosk_only";

patch(WebClient.prototype, {
    setup() {
        super.setup();
        // Not in setup itself: `user` is a module singleton and safe to read
        // immediately, but the RPC below needs the orm service, and services are
        // not on `env.services` yet while the web client is being constructed
        // (reaching for them there throws, and takes the whole client down).
        onMounted(() => this.kulaOpenKioskForKioskOnlyUsers());
    },

    /**
     * Send the browser to the register.
     *
     * A full navigation, not a client action: the register is its own page
     * (/pos/ui/<config>), so whatever the web client was about to render is
     * discarded rather than left mounted behind it.
     *
     * The config is resolved here rather than configured: a database may have
     * more than one, and a counter is a single register in practice, so the first
     * one is the right answer until someone says otherwise. With no config at all
     * there is nowhere to send them, and leaving them in the backend would be
     * worse than leaving them where they are, so nothing happens.
     */
    async kulaOpenKioskForKioskOnlyUsers() {
        if (!user.userId || !(await user.hasGroup(KIOSK_ONLY_GROUP))) {
            return;
        }
        const [config] = await this.env.services.orm.searchRead(
            "pos.config",
            [],
            ["id"],
            { limit: 1 }
        );
        if (config) {
            window.location.assign(`/pos/ui/${config.id}`);
        }
    },
});
