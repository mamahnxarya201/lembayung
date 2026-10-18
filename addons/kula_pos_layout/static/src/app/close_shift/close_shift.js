import { Component, onWillStart, useState } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
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
 *   * **Close Store** -- the shop closes: every *other* register still open goes
 *     down too (pos.session.kula_close_store, server side), then this one.
 *
 * Either answer ends logged out, on Odoo's own login page -- not on the
 * register's Unlock screen, which the next person could walk straight through.
 * That is `/web/session/logout?redirect=/web/login`, core's own logout route.
 *
 * Both answers go through core's closing form afterwards, so the cash count and
 * the closing note still happen and core still owns the closing: this dialog
 * decides what is being closed, nothing else. It answers its caller through
 * `makeAwaitable`, the same shape the Save Order popup uses.
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

/**
 * "These still have to be paid": the dialog that stops a close before it starts.
 *
 * Core has the same rule (`_cannot_close_session`), but it enforces it inside
 * the closing form, after the cash count; here it is the first thing the
 * operator meets, and the orders are named so there is something to act on.
 */
function kulaUnpaidOrdersDialog(dialog, opening, orders) {
    return new Promise((resolve) => {
        dialog.add(
            AlertDialog,
            {
                title: _t("Orders still unpaid"),
                body: `${opening}\n\n${orders.join("\n")}`,
            },
            { onClose: resolve }
        );
    });
}

patch(Navbar.prototype, {
    /**
     * The burger menu's Close Register entry, with the confirmation in front.
     *
     * The handler lives on the Navbar and not on the store because the dialog
     * service is the navbar's, and because only the *entry* is confirmed:
     * `pos.closeSession()` is also reached from inside the closing form itself
     * (Cash In/Out), and a second confirmation there would be noise.
     *
     * The shop's other registers are closed *here*, before the closing form of
     * this one, for one reason: the form ends with core's redirect and then the
     * logout, and a list of registers that refused to close cannot be shown
     * after that. Closing the shop is what the operator just asked for, so the
     * other registers go down first and this register follows with the usual
     * cash count and note.
     */
    async kulaCloseRegister() {
        // Every order has to be paid first -- this register's, and, for a Close
        // Store, every other register's too. Core would refuse later, inside the
        // closing form; here the operator is told before filling it in.
        const closingMessage = _t("Every order has to be paid before this shift can be closed.");
        // The cart first: an unsynced order is not in kula_unpaid_orders yet
        // (nothing has written it to the database), and it is the most common
        // unpaid order there is -- the one on screen.
        const cart = this.pos.kulaCartLine();
        if (cart) {
            await kulaUnpaidOrdersDialog(this.dialog, closingMessage, [cart]);
            return;
        }
        const unpaid = await this.pos.kulaUnpaidOrders();
        if (unpaid.length) {
            await kulaUnpaidOrdersDialog(this.dialog, closingMessage, unpaid);
            return;
        }

        const payload = await makeAwaitable(this.dialog, KulaCloseShiftPopup, {
            register: this.pos.config.name,
        });
        if (!payload) {
            // Dismissed: the register stays exactly as it was.
            return;
        }
        if (payload.closeStore) {
            const shopUnpaid = await this.pos.kulaUnpaidOrders(true);
            if (shopUnpaid.length) {
                await kulaUnpaidOrdersDialog(
                    this.dialog,
                    _t("Every order has to be paid before the store can be closed."),
                    shopUnpaid
                );
                return;
            }
            const result = await this.pos.kulaCloseStore();
            // `failed` is a register that refused to close, `blocked` is one
            // that may not be closed yet (an unpaid order appeared on it between
            // the check above and the call): both are worth naming.
            const refused = [...result.failed, ...result.blocked];
            if (refused.length) {
                await new Promise((resolve) => {
                    this.dialog.add(
                        AlertDialog,
                        {
                            title: _t("Some registers stayed open"),
                            body: _t(
                                "These registers could not be closed: %s",
                                refused.join(", ")
                            ),
                        },
                        { onClose: resolve }
                    );
                });
            }
        }
        this.pos.closeSession();
    },
});

patch(PosStore.prototype, {
    /**
     * The order in the cart, as one line, when it still has anything on it.
     *
     * The complement of kula_unpaid_orders: that one asks the database, and an
     * order the cashier has just been ringing up is not there yet. An empty or
     * already-paid cart answers "" so nothing blocks a normal close.
     */
    kulaCartLine() {
        const order = this.getOrder();
        if (!order || order.isEmpty() || order.finalized) {
            return "";
        }
        // "/" is what an order the register has not written yet is called.
        const title = order.kula_title || order.name;
        const label = title && title !== "/" ? title : _t("Unpaid order");
        return `${this.config.name} — ${label} — ${order.currencyDisplayPriceIncl}`;
    },

    /**
     * The orders that still have to be paid, as lines the operator can act on.
     *
     * `wholeStore` asks for every register still open instead of this one, which
     * is the question a Close Store has to answer first. A failure answers
     * "nothing unpaid" on purpose: core's own check inside the closing form is
     * still there, and a probe that cannot run must not lock the operator out of
     * the register.
     */
    async kulaUnpaidOrders(wholeStore = false) {
        try {
            return await this.data.call("pos.session", "kula_unpaid_orders", [
                [this.session.id],
                wholeStore,
            ]);
        } catch {
            return [];
        }
    },

    /**
     * Close every other register the shop still has open (kula_close_store).
     *
     * Best effort: a register that refuses (draft orders left on it, a session
     * another cashier is mid-way through closing) is reported by name and does
     * not stop the others, because the shop is closing and one counter cannot
     * be allowed to hold the day open. The caller shows the names.
     */
    async kulaCloseStore() {
        try {
            return await this.data.call("pos.session", "kula_close_store", [[this.session.id]]);
        } catch (error) {
            // The shop is closing either way: a register that cannot even be
            // asked about is reported like one that refused. The answer keeps
            // the server's shape, `blocked` included: the caller reads all three
            // lists, and a stand-in answer missing one is what broke Close Store
            // in issue #11.
            return { closed: [], failed: [error.message || String(error)], blocked: [] };
        }
    },

    /**
     * A real logout, on Odoo's login page.
     *
     * The register's own Unlock screen is not a login: it is one tap away from
     * the till, so "close the shift" would end with the next person selling
     * without a password. `/web/session/logout` is core's own logout route
     * (user menu); `redirect` is where it sends the browser after destroying
     * the session.
     */
    kulaLogout() {
        window.location.href = "/web/session/logout?redirect=/web/login";
    },
});

patch(ClosePosPopup.prototype, {
    /**
     * What happens after a register has actually closed.
     *
     * Core's own close ends on `pos.router.close()`, i.e. `/pos/ui/<config>`,
     * where the register would offer "Open Register" again. The logout replaces
     * that destination with Odoo's login page.
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
        this.pos.kulaLogout();
    },
});
