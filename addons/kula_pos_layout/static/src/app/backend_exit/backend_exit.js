import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * The way out of the register, for the accounts that have no way out.
 *
 * Core leaves the register by going to the backend:
 * `redirectToBackend()` sends the browser to
 * `/odoo/action-point_of_sale.action_client_pos_menu`, and every exit ends
 * there -- the Backend entry (hidden for these accounts, see navbar.xml and
 * login_screen.xml), closing a register that could not be closed (core's
 * closing popup, "you will be redirected to the back-end to manually close the
 * session"), and `closePos()`, which is how one register leaves when another
 * one takes the session over: a register that boots calls `closeOtherTabs()`,
 * and the tab that was already open answers with `closePos()`.
 *
 * For a member of kula_security's Kiosk Only group there is no backend to go
 * to: `ir.http._dispatch` answers /odoo with the register. So the exit came
 * back as a *boot*, and a boot claims the session and closes the other tab --
 * which is a loop, not an exit:
 *
 *   tab A (register)  <- close_tabs --  tab B (register boots)
 *     | closePos -> /odoo -> 303 /pos/ui/<config> -> boots -> close_tabs ->
 *   tab B closes -> /odoo -> 303 -> boots -> close_tabs -> ...
 *
 * Two tabs of a kiosk rebound between /pos/ui/<config> and /pos/ui/<config>/login
 * every couple of seconds, each pass resetting the cashier, so the till ends up
 * parked on Unlock Register with neither tab usable. It is what the register's
 * own "Install App" entry produced: the app-install page boots the register once
 * the app is installed, which is exactly the second tab above (that entry is
 * why the install page itself is no longer gated server-side; the two halves go
 * together).
 *
 * The exit is not removed, it is translated: for these accounts leaving the
 * register is core's own `showLoginScreen()` -- the Unlock screen, which is the
 * only place a kiosk account can be sent, and the one the server-side redirect
 * was aiming at. Nothing is skipped: `closePos()` still resets the cashier and
 * still runs its push of unsynced orders before it calls this, and nothing
 * navigates any more, so the register is not reloaded either -- a cart that was
 * mid-order is still on it when the operator unlocks again.
 *
 * The flag comes from res.users (models/res_users.py) and is False whenever
 * kula_security is not installed, which leaves core's behaviour alone.
 */
patch(PosStore.prototype, {
    redirectToBackend() {
        if (this.user.kula_kiosk_only) {
            this.showLoginScreen();
            return;
        }
        super.redirectToBackend();
    },
});
