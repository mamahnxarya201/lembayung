/**
 * KULA POS Layout — the part of the page the user can actually see.
 *
 * Why this exists: on a phone or tablet the soft keyboard changes the usable
 * screen, and Chrome offers two behaviours for that. The register has to survive
 * both, because which one applies depends on the browser, not on this module:
 *
 *   * `interactive-widget=resizes-content` (the POS page's own viewport meta,
 *     Chrome 108 and up): the *layout* viewport shrinks, so `100dvh` follows and
 *     the whole screen re-lays itself out above the keyboard.
 *   * anything older, i.e. `resizes-visual`: only the *visual* viewport shrinks.
 *     The layout viewport — and with it every 100vh/100dvh box, which is the
 *     register's shell and every dialog in it — keeps its full height while the
 *     keyboard covers the lower half of it. That is the case where a text box
 *     ends up behind the keyboard with no way to scroll to it.
 *
 * `visualViewport` tells the truth under both: it is, by definition, the slice of
 * the page the user is looking at. Published as two custom properties, the
 * stylesheet can size the shell and the dialogs to that slice instead of to the
 * layout viewport:
 *
 *   --kula-viewport-h     height of the visible slice, in px
 *   --kula-viewport-top   how far the visible slice is scrolled into the layout
 *                         viewport (0 except when the browser moved the page for
 *                         the keyboard)
 *   --kula-viewport-bottom
 *                         how much of the layout viewport the keyboard (or any
 *                         other browser UI) covers at the bottom. Zero under
 *                         resizes-content, the keyboard's height under
 *                         resizes-visual — which is what a fixed element anchored
 *                         to `bottom: 0` has to move up by to stay in sight.
 *
 * The fallbacks in the stylesheet are `100dvh` / `0px`, which is exactly what
 * those properties mean under resizes-content, so nothing depends on this file
 * having run: on a desktop browser, or before the first keyboard, the layout is
 * the one the stylesheet describes on its own.
 *
 * The one behaviour that is not pure geometry: a focused field is scrolled back
 * into the visible slice. Chrome does that by itself when it can, but it cannot
 * when the field sits in a dialog whose scroll container has no room left — the
 * case this whole file is about — so the same thing is done here, once the
 * keyboard has finished moving (it animates, hence the repeated passes).
 */

const ROOT = document.documentElement;
const HEIGHT_PROPERTY = "--kula-viewport-h";
const TOP_PROPERTY = "--kula-viewport-top";
const BOTTOM_PROPERTY = "--kula-viewport-bottom";

/** Field types the soft keyboard is raised for. */
const EDITABLE_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/** When the keyboard animates, it is not at its final size yet. */
const SETTLE_DELAYS = [120, 320, 620];

function visibleBox() {
    const viewport = window.visualViewport;
    if (!viewport || !viewport.height) {
        return { height: window.innerHeight, top: 0 };
    }
    return { height: viewport.height, top: viewport.offsetTop };
}

/** Publish the visible slice, so the stylesheet can size to it. */
export function publishVisibleViewport() {
    const { height, top } = visibleBox();
    if (!height) {
        return;
    }
    // The initial containing block a `position: fixed` element is measured
    // against: with resizes-content it shrinks with the keyboard (so nothing is
    // covered), with resizes-visual it does not (so the keyboard's height shows
    // up here).
    const layoutHeight = ROOT.clientHeight;
    const covered = Math.max(0, Math.round(layoutHeight - (top + height)));
    ROOT.style.setProperty(HEIGHT_PROPERTY, `${Math.round(height)}px`);
    ROOT.style.setProperty(TOP_PROPERTY, `${Math.round(top)}px`);
    ROOT.style.setProperty(BOTTOM_PROPERTY, `${covered}px`);
    nudgeFocusedField();
}

/**
 * Re-centre the focused field after the visible slice changed.
 *
 * The keyboard can open *while* a field already has focus (the field was tapped,
 * then the keyboard animation resized the viewport), which is the common order of
 * events on a phone — and that is not a `focusin` event, so the handler below
 * never runs for it. Keeping the focused field in sight on every viewport change
 * covers it. The scroll happens on the next frame so the dialog has already been
 * resized to the new visible height.
 */
function nudgeFocusedField() {
    const field = document.activeElement;
    if (!field?.tagName || !EDITABLE_TAGS.has(field.tagName)) {
        return;
    }
    window.requestAnimationFrame(() => keepInSight(field));
}

/**
 * Bring a focused field back into the visible slice when the keyboard has
 * covered it. `scrollIntoView` scrolls the nearest scrollable ancestor — the
 * dialog body — and does nothing when the field is already in sight, so this is
 * safe to call on every pass.
 */
function keepInSight(field) {
    if (!field.isConnected) {
        return;
    }
    const rect = field.getBoundingClientRect();
    const { height } = visibleBox();
    const margin = 12;
    if (rect.top >= margin && rect.bottom <= height - margin) {
        return;
    }
    // Instant, not smooth: this also runs from `visualViewport.scroll`, and a
    // smooth scroll emits more of those, which would re-trigger this in a loop.
    field.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
}

function onFocusIn(event) {
    const field = event.target;
    if (!field?.tagName || !EDITABLE_TAGS.has(field.tagName)) {
        return;
    }
    const settle = () => {
        publishVisibleViewport();
        keepInSight(field);
    };
    settle();
    for (const delay of SETTLE_DELAYS) {
        setTimeout(settle, delay);
    }
}

const viewport = window.visualViewport;
if (viewport) {
    viewport.addEventListener("resize", publishVisibleViewport);
    viewport.addEventListener("scroll", publishVisibleViewport);
}
window.addEventListener("resize", publishVisibleViewport);
window.addEventListener("orientationchange", publishVisibleViewport);
document.addEventListener("focusin", onFocusIn, true);
document.addEventListener("focusout", publishVisibleViewport, true);
publishVisibleViewport();
