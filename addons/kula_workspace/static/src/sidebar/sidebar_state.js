/**
 * The sidebar's shape, shared by the sidebar and the top bar's control.
 *
 * The tree lives in the sidebar component; the open/close button lives in the
 * top bar (the owner asked for it there), so the two components share one
 * stored shape and broadcast every change on the env bus. localStorage is the
 * source of truth when a page loads; the event keeps the two in step
 * afterwards.
 *
 * There is one shape left: open or closed. The sidebar is **always pinned** --
 * an open tree is part of the layout and reserves its width -- because the
 * owner removed the unpin control and the floating-over-the-page behaviour it
 * switched on ("make it always pinned (remove the unpin autohide feature)").
 * `pinned` is still carried in the state so the CSS and the body classes read
 * the same shape they always did; nothing can turn it off.
 */

import { browser } from "@web/core/browser/browser";

/** Fired with `{ closed, pinned, mobileOpen }` whenever the shape changes. */
export const SIDEBAR_STATE_EVENT = "KULA:SIDEBAR-STATE";

/**
 * Fired by the top bar's control: "toggle the sidebar".
 *
 * It is a request, not state: the sidebar owns the behaviour (a phone opens a
 * drawer, a desktop slides the tree in or out), so the control only asks and
 * then reads the resulting shape back from SIDEBAR_STATE_EVENT.
 */
export const SIDEBAR_TOGGLE_EVENT = "KULA:SIDEBAR-TOGGLE";

const SHAPE_STORAGE_KEY = "kula_sidebar_shape";

export function readSidebarShape() {
    return {
        closed: browser.localStorage.getItem(SHAPE_STORAGE_KEY) === "closed",
        pinned: true,
        mobileOpen: false,
    };
}

export function writeSidebarShape({ closed }) {
    browser.localStorage.setItem(SHAPE_STORAGE_KEY, closed ? "closed" : "open");
}

/**
 * The phone breakpoint. Bootstrap 5's `media-breakpoint-down(md)` is
 * max-width 767.98px, and sidebar.scss's layout query has to stay in sync with
 * this -- `down(sm)` would only cover below 576px and leave 576-767 with a
 * hidden tree and no drawer.
 */
export const SMALL_SCREEN_QUERY = "(max-width: 767.98px)";
