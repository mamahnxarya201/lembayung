import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { LoginScreen } from "@point_of_sale/app/screens/login_screen/login_screen";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

/**
 * Closing the register, one question earlier.
 *
 * Core's Close Register entry runs straight into the closing form (cash count,
 * closing note, Close Register), which is the wrong first tap at a counter:
 * there is no way back from it except Discard, and no way to say *what* is being
 * closed. GitHub issue #4 asks for a confirmation, and for the two answers a
 * shop actually has:
 *
 *   * **Close Shift** -- this register closes; the store stays open, so another
 *     shift can be opened today (core's normal behaviour);
 *   * **Close Store** -- the shop closes: this register and every other counter
 *     still open (pos.session.kula_close_store, server side).
 *
 * Either answer ends on the register's login screen, as the issue asks. Both go
 * through core's closing form afterwards, so the cash count and the closing note
 * still happen and core still owns the closing: this dialog decides what is
 * being closed, nothing else. It answers its caller through `makeAwaitable`, the
 * same shape the Save Order popup uses.
 */
export class KulaCloseShiftPopup extends Component {
    static template = "kula_pos_layout.CloseShiftPopup";
    static components = { Dialog };
    static props = {
        // `close` is injected by the dialog service, `getPayload` by
        // `makeAwaitable`; resolving before close() matters, because the
        // dialog's own onClose resolves the same promise with nothing.
        close: Function,
        getPayload: Function,
        // The register being closed.
        register: String,
    };

    setup() {
        this.pos = usePos();
        this.state = useState({ summary: "" });
        onWillStart(async () => {
            this.state.summary = await this.shiftSummary();
        });
    }

    /**
     * What is being closed: "8 orders, Rp 148,000", core's own numbers.
     *
     * Asked of the server (get_closing_control_data, the call the closing form
     * itself makes a moment later) and not counted in the browser: the register
     * only carries the *draft* orders of the session
     * (pos.order._load_pos_data_domain), so a total computed here would always
     * be zero. A failure is not worth reporting twice — the closing form behind
     * this dialog is the one that has to handle it.
     */
    async shiftSummary() {
        try {
            const data = await this.pos.data.call("pos.session", "get_closing_control_data", [
                [this.pos.session.id],
            ]);
            const { quantity, amount } = data.orders_details;
            return quantity
                ? `${quantity} order${quantity > 1 ? "s" : ""}, ${this.env.utils.formatCurrency(amount)}`
                : "";
        } catch {
            return "";
        }
    }

    choose(closeStore) {
        this.props.getPayload({ closeStore });
        this.props.close();
    }
}

patch(Navbar.prototype, {
    /**
     * The burger menu's Close Register entry, with the confirmation in front.
     *
     * The handler lives on the Navbar and not on the store because the dialog
     * service is the navbar's, and because only the *entry* is confirmed:
     * `pos.closeSession()` is also reached from inside the closing form itself
     * (Cash In/Out), and a second confirmation there would be noise.
     */
    async kulaCloseRegister() {
        const payload = await makeAwaitable(this.dialog, KulaCloseShiftPopup, {
            register: this.pos.config.name,
        });
        if (!payload) {
            // Dismissed: the register stays exactly as it was.
            return;
        }
        this.pos.kulaCloseStore = payload.closeStore;
        this.pos.closeSession();
    },
});

/** Where a "Close Store" leaves the registers it could not close. */
const STORE_CLOSE_FAILURES = "kula.store_close_failures";

patch(PosStore.prototype, {
    /** Set by the confirmation: also close the shop's other registers. */
    kulaCloseStore: false,

    /**
     * Close every other register the shop still has open (kula_close_store).
     *
     * Best effort, and after the operator's own register is already closed: the
     * shop is closing, and a register that refuses (draft orders, a session
     * another cashier is mid-way through closing) must not keep this one open.
     * Whatever refused comes back by name, and the caller carries it to the one
     * screen that survives this flow.
     */
    async kulaCloseOtherRegisters() {
        try {
            return await this.data.call("pos.session", "kula_close_store", [[this.session.id]]);
        } catch (error) {
            // The shop is closing either way: a register that cannot even be
            // asked about is reported like one that refused, and the operator
            // still leaves the register.
            return { closed: [], failed: [error.message || String(error)] };
        }
    },

    /** The register's login screen, which is where a closed shift ends. */
    kulaLeaveToLogin() {
        window.location.replace(`/pos/ui/${odoo.pos_config_id}/login`);
    },
});

patch(ClosePosPopup.prototype, {
    /**
     * What happens after a register has actually closed.
     *
     * Core's own close ends on `pos.router.close()`, i.e. `/pos/ui/<config>`,
     * which the login screen then takes over because no session is open. The
     * extra step here is the store (the other registers), and landing on the
     * login route explicitly rather than on whatever the loader happens to do
     * with a config that has no open session.
     *
     * Guarded on `session.state === "closed"`: the base method also returns
     * after a failed close -- a closing error, a wizard, a rejected cash count
     * -- and in those cases the operator stays on the register with the error.
     */
    async closeSession() {
        await super.closeSession();
        if (this.pos.session?.state !== "closed") {
            return;
        }
        if (this.pos.kulaCloseStore) {
            this.pos.kulaCloseStore = false;
            const result = await this.pos.kulaCloseOtherRegisters();
            if (result.failed.length) {
                // Core's close has already sent this page to `/pos/ui/<config>`,
                // so a dialog opened here would be destroyed by that navigation.
                // The list rides to the login screen instead: see the LoginScreen
                // patch below.
                sessionStorage.setItem(STORE_CLOSE_FAILURES, JSON.stringify(result.failed));
            }
        }
        this.pos.kulaLeaveToLogin();
    },
});

patch(LoginScreen.prototype, {
    /**
     * The one screen a "Close Store" can still be honest on.
     *
     * The closing flow ends with a page navigation, and both a dialog and a
     * notification die with it. This is where the operator actually lands, so
     * the registers that refused to close are reported here, once.
     */
    setup() {
        super.setup();
        onMounted(() => {
            const failures = JSON.parse(sessionStorage.getItem(STORE_CLOSE_FAILURES) || "null");
            if (!failures) {
                return;
            }
            sessionStorage.removeItem(STORE_CLOSE_FAILURES);
            this.dialog.add(AlertDialog, {
                title: _t("Some registers stayed open"),
                body: _t("These registers could not be closed: %s", failures.join(", ")),
            });
        });
    },
});
