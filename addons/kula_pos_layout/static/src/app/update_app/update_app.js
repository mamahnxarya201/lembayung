import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

/** How often a till that stays open asks whether the app has changed. */
const CHECK_EVERY_MS = 2 * 60 * 1000;

/**
 * "Update App": the reload that brings a deployed version to a till that never
 * reloads.
 *
 * A kiosk is a page that stays open for days -- on a tablet it is an installed
 * PWA that gets resumed, not opened -- so the client it runs is the client it
 * loaded, whatever the server has served since. Amp's "reload to update" answers
 * the same problem, and this is that answer for the register: the drawer grows an
 * **Update App** entry while the server is serving a newer client than the page
 * that is running, and tapping it reloads.
 *
 * **What "newer" means.** The client *is* its asset bundles. Their URLs carry a
 * version hash (`/web/assets/<hash>/point_of_sale.assets_prod.min.js`), and that
 * hash is a digest of the files in the bundle, so it moves when -- and only when
 * -- a file in the client changes. The page reads its own hash back from its
 * <script> and <link> tags, the server reports the hash it would serve now
 * (pos.config.kula_app_version), and the two being equal is the whole test: no
 * clock to trust, no deployment bookkeeping to keep in step by hand.
 *
 * **A plain reload is enough.** The POS page is served `Cache-Control: no-store`
 * and its bundles live at hashed URLs, so reloading re-fetches both. What a
 * reload does not do is ask the service worker to look for a new version of
 * itself, which is the one thing this does first; the worker is a cache layer
 * here (network first), so the order is not load-bearing -- the reload is what
 * brings the new client either way.
 *
 * **Nothing is lost.** A reload comes back to the same route, with the same
 * cashier and the same cart: `connected_cashier_<config>` lives in
 * sessionStorage, which survives a reload, and the order lives in IndexedDB,
 * which is what the reload reads back. All three were checked on the live
 * register before this was written.
 *
 * The entry only exists while there is something to update, so the kiosk's menu
 * does not grow a reload button that does nothing; the dot on the burger is how
 * the drawer says so without being opened.
 */
function loadedApp() {
    const find = (nodes, attribute, extension) => {
        for (const node of nodes) {
            const url = new URL(node.getAttribute(attribute), browser.location.origin);
            const match = url.pathname.match(
                /^\/web\/assets\/([^/]+)\/(point_of_sale\.assets_prod(?:_dark)?)\.min\.(js|css)$/
            );
            if (match && match[3] === extension) {
                return { hash: match[1], bundle: match[2] };
            }
        }
        return null;
    };
    const js = find(document.querySelectorAll("script[src]"), "src", "js");
    const css = find(document.querySelectorAll('link[rel="stylesheet"]'), "href", "css");
    if (!js || !css || js.bundle !== css.bundle) {
        return null;
    }
    // `debug` in place of a hash means dev assets (`?debug=assets`): there is no
    // version to compare, so the feature stays quiet.
    if (!/^[0-9a-f]{7}$/.test(js.hash) || !/^[0-9a-f]{7}$/.test(css.hash)) {
        return null;
    }
    return { bundle: js.bundle, js: js.hash, css: css.hash };
}

export const kulaUpdateService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const state = reactive({
            available: false,
            check,
            update,
        });

        /**
         * Ask the server whether the client this page loaded is still the one it
         * would serve, and let the drawer say so.
         */
        async function check() {
            const mine = loadedApp();
            if (!mine) {
                return;
            }
            let versions;
            try {
                versions = await orm.call("pos.config", "kula_app_version", [[odoo.pos_config_id]]);
            } catch {
                // Offline, or a server in the middle of a restart: keep the answer
                // we had, the next tick asks again.
                return;
            }
            const server = versions?.[mine.bundle];
            if (!server) {
                // The server answered with bundles this page does not know -- a
                // rename on one side, a half-deployed build. There is nothing to
                // compare, so say nothing rather than "up to date".
                console.warn(`kula_update: no version reported for ${mine.bundle}`);
                return;
            }
            state.available = server.js !== mine.js || server.css !== mine.css;
        }

        /**
         * Update the app: let the service worker look for a new version of
         * itself, then reload into whatever the server is serving now.
         */
        async function update() {
            try {
                const registration = await browser.navigator.serviceWorker?.getRegistration?.();
                await registration?.update();
            } catch {
                // No worker, offline, or a browser that refuses to ask: the reload
                // below is still the update.
            }
            browser.location.reload();
        }

        setInterval(check, CHECK_EVERY_MS);
        browser.addEventListener("visibilitychange", () => {
            // A till resumed after hours is exactly the case this exists for, and
            // the interval may have been throttled while the page was hidden.
            if (document.visibilityState === "visible") {
                check();
            }
        });
        return state;
    },
};

registry.category("services").add("kula_update", kulaUpdateService);
