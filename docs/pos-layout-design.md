# KULA POS — ProductScreen layout specification

Companion to the mockup. Records **what the screen should be**, region by region, and the exact
Odoo 19 extension point that realises each change — so the module build is unambiguous.

- Status: **implemented and verified** — `addons/kula_pos_layout`, installed on `lentera-pagi`.
  See §9 for the five non-obvious things that bit during implementation.
- Target URL: `http://localhost:8069/pos/ui/1/product/[]`
- `pos.config` id **1**, name **KULA**, database **`lentera-pagi`**
- Device: **tablet** — **responsive, no fixed resolution or orientation** (verified 800×1280 portrait
  through 2560×1600; see §2.1)
- Mode: **drinks counter / café, counter service** (no floors, no tables)
- Controls on screen: **Payment, Customer, Refund** — nothing else
- Language: **English**

Artifacts: [layout mockup](pos-layout-mockup.html) · [payment mockup](pos-layout-payment-mockup.html)

> Both are self-contained HTML files: open one in a browser and it renders live at whatever size you
> give it, which is more useful than a fixed-size screenshot. The PNG renders and screen captures
> that used to sit beside them were removed to keep the repository light.

---

## 1. Verified starting point

Read from the live stack, not assumed:

| Fact | Value |
|---|---|
| Products in POS | 3 — Kopi 10.000, Es Teh 5.000, Sinom 7.000 |
| POS categories | **0** — the category dropdown in the mockup does not exist yet |
| Tax on those products | **0%** → totals are plain sums, no tax line |
| Company / currency | `My Company` (still default) / **IDR** |
| Payment methods | Cash (cash-count), Card, Customer Account |
| `pos_restaurant` | installed, but **off** on KULA |
| `pos_hr` | **on** → per-cashier PIN login; `Cashier` employee exists |
| Session | id 2 **open** |
| Discount / loyalty / notes / split-bill / tips | all **off** |

The mockup shows 15 products across 3 categories to prove the grid scales. **Only Kopi, Es Teh and
Sinom are yours**; the other 12 are placeholders. Categories are illustrative too — you have none.

---

## 2. Layout, region by region

```
┌─ NAVBAR 56px ───────────────────────────────────────────────────────────────┐
│ [☰] [Register|Orders] [● All ▾] [Search…]            [Cashier ▾]            │
├─ LEFT 860px ─────────────────────────────────┬─ RIGHT 420px ────────────────┤
│ All items        15 products                 │ Order #3          4 items    │
│ ┌────┐┌────┐┌────┐┌────┐┌────┐               │ ┌ Kopi    1×10.000  10.000 ┐ │
│ │    ││    ││    ││    ││    │               │ │ Es Teh  2×5.000   10.000 │ │
│ └────┘└────┘└────┘└────┘└────┘               │ │ Sinom   1×7.000    7.000 │ │
│ ┌────┐┌────┐┌────┐┌────┐┌────┐               │ └──────────────────────────┘ │
│ │    ││    ││    ││    ││    │               │ ┌ Subtotal      27.000 ────┐ │
│ └────┘└────┘└────┘└────┘└────┘               │ │ Total     IDR 27.000     │ │
│ ┌────┐┌────┐┌────┐┌────┐┌────┐               │ └──────────────────────────┘ │
│ │    ││    ││    ││    ││    │               │         (order list space)   │
│ └────┘└────┘└────┘└────┘└────┘               │ [ 7 ][ 8 ][ 9 ]              │
│   159×136 cards, 10px gap                    │ [ 4 ][ 5 ][ 6 ]  ← qty only  │
│                                              │ [ 1 ][ 2 ][ 3 ]              │
│                                              │ [ 0 ][ . ][ ⌫ ]              │
│                                              │ [ Payment      IDR 27.000 ]  │
│                                              │ [ Customer ][  Refund     ]  │
└──────────────────────────────────────────────┴──────────────────────────────┘
                    860px                              420px
```

**Panes.** Left = menu (grows). Right = order and actions. The menu takes the larger share because
the catalogue is the thing that grows; the order side is a bounded column whose contents are limited
by what one customer buys. The split is `clamp(300px, 32%, 430px)` for the order pane, with the menu
taking the remainder — proportional, but never so narrow that the numpad breaks or so wide that it
starves the menu on a large screen. *(The diagram above is the 1280×800 reference render; the real
layout is fluid — see §2.1.)*

**Category dropdown**, not core's horizontal chip grid or an in-pane rail. It sits in the navbar
beside the search, frees 104px of pane width for the grid (which is what paid for the 5th column),
and keeps the header to a single row. The cost is honest: category selection goes from **1 tap**
(always-visible tiles) to **2 taps** (open, then choose). That trade is worth it up to roughly a
dozen categories; beyond that an always-visible list earns its space back.

### 2.1 Responsiveness — why there are almost no breakpoints

Tablets vary wildly in resolution and orientation, so nothing is designed against a fixed canvas.
The stage fills the viewport (`100dvh`) and every size-critical value is fluid:

| Concern | Mechanism | Effect |
|---|---|---|
| Pane split | `clamp(300px, 32%, 430px)` | proportional, bounded at both ends |
| **Grid columns** | `repeat(auto-fill, minmax(clamp(150px,11vw,200px), 1fr))` | **column count is derived, never declared** |
| Card height | `clamp(100px, 16vh, 148px)` | short screens don't clip |
| Numpad keys / Pay button | `clamp(34px,5.6vh,48px)` / `clamp(48px,7.4vh,62px)` | pads stay reachable on a 768-tall screen |
| Total type | `clamp(17px, 2.4vh, 22px)` | scales with the ticket |

Measured, not asserted:

| Viewport | Columns | Card | Order pane |
|---|---|---|---|
| 800×1280 (portrait) | **3** | 154×148 | 300px |
| 1024×768 (iPad) | **4** | 162×123 | 328px |
| 1112×834 (iPad Air) | **4** | 176×133 | 356px |
| 1280×800 | **5** | 162×128 | 410px |
| 1920×1200 | **7** | 200×148 | 430px |
| 2560×1600 | **10** | 201×148 | 430px |

Only two media queries exist, and both are **shape changes**, never sizing:

- `max-width: 900px` — navbar drops its text labels to icons only (core POS does the same via
  `ui.isSmall`).
- `max-width: 760px` — panes stack into one column. Below tablet width; a non-breaking fallback,
  not a target.

Verified at every size above: no element overflows its box and the page never scrolls
(`orderOverflow = linesScroll = productsOverflow = pageScroll = 0`). A longer order scrolls inside
the ticket area rather than pushing the Pay button off-screen.

> **Note for the module:** the clamp bounds live in one `:root` block. Tuning a specific tablet means
> editing those values, not adding breakpoints.

---

## 3. Core → target, with the real extension point

Every row verified against `odoo:19.0` in the running container.

| Region | Core v19 does | Target | Extension point |
|---|---|---|---|
| **Pane order** | order left (fixed) / products right (`flex-grow-1`) | **menu left / order right** | swap the two blocks in `point_of_sale.ProductScreen`; pane divider `border-right` → `border-left` |
| Navbar tabs | Register/Orders + `OrderTabs` + barcode | Register/Orders; ☰ moved to far left; category dropdown added | `t-inherit` → `point_of_sale.Navbar` |
| Search / cashier | core | **keep as-is** | none |
| Category nav | `CategorySelector`, horizontal chip grid inside the pane | **navbar dropdown** beside the search | `t-inherit` → `point_of_sale.Navbar` + new dropdown component |
| Product card | `ProductCard`: name + qty badge, **no price** | + price line | `t-inherit` → `point_of_sale.ProductCard` |
| Grid | `d-grid gap-1 gap-lg-2`, auto-fill columns | `repeat(auto-fill, minmax(clamp(150px,11vw,200px), 1fr))` — **column count derived from width**, 10px gap | SCSS override on `.product-list` |
| Order lines | `OrderSummary` → `OrderDisplay`; a line is only editable after it is selected (numpad) | **− qty + stepper + delete on every line** | fill a new slot injected into `point_of_sale.Orderline` from `point_of_sale.OrderSummary` |
| Totals | total only | Subtotal + emphasised Total | SCSS |
| Control row | `ControlButtons`: Customer, **Note**, **Save/park**, More ⋯ | Customer + **Refund** | `t-inherit` → `point_of_sale.ControlButtons` |
| **Refund** | inside the ⋯ popup → `this.clickRefund()` | first-class button | call `clickRefund()` from the extended control row |
| Numpad (ProductScreen) | `Numpad` with **Qty / Price / Disc** modes | **removed entirely** | empty `replace` of `//Numpad` in `point_of_sale.ProductScreen` |
| Payment | `ActionpadWidget`: `btn-primary` "Payment", **no amount** | "Payment" + `IDR <total>` | `t-inherit` → `point_of_sale.ActionpadWidget` |
| Control row position | **above** the numpad/actionpad | **below** Payment | xpath move in `point_of_sale.ProductScreen` |

### Three findings worth calling out

1. **Customer is already free.** `point_of_sale.ControlButtons` renders `SelectPartnerButton` on the
   main row by default — we keep it and change nothing.
2. **Refund needs promoting.** In v19 it is *not* on the product screen; it sits in the
   `ControlButtonsPopup` (the ⋯ popup) and calls `this.clickRefund()`. Putting Refund where you want
   it means re-rendering that button inline. Note it is role-gated
   (`cashier._role != 'minimal'`) — relevant because `pos_hr` is on.
3. **Customers cost you two buttons.** Core's main row also carries **Note** (`InternalNoteButton`)
   and **Save/park** (upload). You didn't ask for either, so the extension drops both. That is the
   only place we remove core functionality on this screen.

---

## 4. Deviations from core (deliberate, and why)

| Deviation | Why | Risk |
|---|---|---|
| Panes swapped (menu left, order right) | the catalogue grows, the order does not; and the payment cluster lands bottom-right in the thumb zone | core's pane order is reversed, so `pos_restaurant` and other in-pane core extensions may need re-checking |
| Categories in a navbar dropdown instead of tiles/chips | frees 104px of pane width, which paid for the 5th column; keeps the header to one row | category selection costs **2 taps instead of 1**; stops paying off past roughly a dozen categories |
| Price printed on each card | a café menu without prices forces the cashier to build an order to quote one | core's `ProductCard` has no price prop; we read it from `props.product` |
| Total printed on the Payment button | the amount and the action that commits it belong together | must stay in sync with `OrderSummary` |
| Numpad reduced to quantity | Price override and Discount are off in your config, so those modes are dead UI | if you later enable `pos_discount`, restore the Disc mode |
| Control row moved below Payment | thumb zone on a counter-mounted tablet | core places it above; a one-line xpath difference |
| OrderTabs hidden in navbar | hold/park not requested | **see §6, item 5** |

---

## 5. Code vs data

Layout structure is **code** (templates + patches) — per the reasoning doc, no layout model.
The variations worth exposing per deployment go on `pos.config`:

```python
class PosConfig(models.Model):
    _inherit = 'pos.config'

    kula_card_min_width   = fields.Integer("Product card minimum width (px)", default=150)
    kula_show_card_price  = fields.Boolean("Show price on product cards", default=True)
    kula_category_nav     = fields.Selection(
        [('dropdown', "Navbar dropdown"), ('tiles', "In-pane tiles")],
        string="Category navigation", default='dropdown')
```

This is the level-2 pattern: code defines the shapes, `pos.config` picks between them, and no new
table or renderer is introduced.

---

## 6. Decisions I made on your behalf — please confirm

1. **Fluid sizing instead of per-model breakpoints.** Column count and pane split are derived from
   the viewport, so no specific tablet needs to be nominated and there is nothing to tune per model.
   If one device still looks wrong, the fix is adjusting the `clamp()` bounds in `:root` (§2.1) —
   not adding a media query.
2. **Products stay image-less.** No image column exists on your products, so cards are text +
   category colour. If photos are coming, card height and the image/text split change.
3. **Refund visible to all non-minimal roles.** Refund is a shrinkage risk at a counter. If it should
   be manager-only, that's a role gate, not a layout change.
4. **Numpad kept, and a stepper added to every line.** A café order is often "2 of the same", so
   quantity entry earns its space. Each order line additionally carries its own `− qty +` stepper and
   a delete button — see §13 — so a line can also be corrected or removed without selecting it first.
5. **The ⋯ More button.** The mockup omits it, but **Cancel Order** and **Pricelist** live only in
   that popup in v19. Cash In/Out and Reload are safely in the navbar ☰. Do you want a small ⋯ on
   the product screen to keep Cancel Order reachable, or is dropping it from this screen acceptable?

## 7. Open questions

- **Categories do not exist yet.** You have zero `pos_category` records, so step one of the real
  rollout is creating them (Coffee / Tea / Juice / …) and assigning the 3 products.
- **Company is still "My Company".** Worth setting before any receipt or report work.
- **Receipt layout** was explicitly out of scope for this pass (QWeb report, separate mechanism).

## 8. Implementation status

Built and installed as `addons/kula_pos_layout`. Verified in a real browser against the live POS
(not just "the files exist") at three viewports with zero JS errors:

| Viewport | Columns | Card | Order pane | Menu side |
|---|---|---|---|---|
| 1280×800 | 5 | 164px | 410px | left ✅ |
| 1024×768 | 4 | 164px | 328px | left ✅ |
| 800×1280 portrait | 3 | 159px | 300px | left ✅ |

Also confirmed: category dropdown present · in-pane chips suppressed · card price `Rp 10,000.00` ·
pay button carries the total · Refund present · Note / Save-park / barcode / parked-order tabs all
removed · 12-key 3-column numpad · ⋯ retained.

---

## 9. Implementation notes — what actually bit

Five non-obvious things cost real debugging time. They are recorded here because each one will
bite again on the next change to this module.

### 9.1 `hasclass()` silently fails on hyphenated class names

`<xpath expr="//button[hasclass('pay-order-button')]" .../>` **never matches**, while the equivalent
raw XPath matches fine. Template inheritance rewrites `hasclass()` itself (`getXpath` in
`web/static/src/core/template_inheritance.js`), and the hyphenated form comes out unmatchable. The
failure is silent: no error, the operation is simply not applied.

**Rule for this module:** for any class containing `-`, use `contains(@class, '...')` instead.
Non-hyphenated classes (`pay`, `actionpad`, `validation`) work normally.

### 9.2 A class set only by `t-attf-class` cannot be matched at all

`ProductCard`'s `<article>` gets its classes from `t-attf-class`, so at xpath-match time there is no
`class` attribute. `//article[hasclass('product')]` aborts inheritance with *"cannot be located in
element tree"* — and because `ProductCard` compiles lazily, the whole app renders blank on the
product grid. `//article` (unique in that template) is the fix.

### 9.3 `t-out` owns an element's content

Core's pay button carries `t-out="props.actionName"`. Anything inserted with `position="inside"` is
wiped at render, and `position="replace"` on that node did not take effect either. The working
approach is to **remove the attribute** — an empty `<attribute name="t-out"/>` calls
`removeAttribute` (see `modifyAttributes`) — then insert the children.

### 9.4 `ProductCard.props.product` is a product.template, not a product.product

`productToDisplayByCateg` holds templates, and `product.template._load_pos_data_fields` exposes
`list_price` — **not** `lst_price`. So `product.lst_price` and `product.product_tmpl_id.list_price`
are both `undefined`, and `getPrice()` returns `NaN` because it computes
`variant ? variant.lst_price : this.list_price`. Hence `getPrice(pricelist, 1, 0, false, false)`:
passing `variant = false` makes it use `this.list_price`, which exists. A pricelist rule based on
`standard_price` (the cost, 0 here) would otherwise print `Rp 0.00` on every card.

### 9.5 Installing via `odoo shell` leaves the server's asset cache stale

`_generate_asset_links_cache` is `ormcache(cache='assets')` — per-process memory. Installing the
module from a separate `odoo shell` process (necessary here, since the admin password was unknown)
updates the DB but **not** the running server, which keeps serving the pre-module bundle from
`ir.attachment` under an unchanged version URL. Symptom: the module is installed, the assets are in
the server-side bundle, and the browser still shows core's layout.

Fix: let the running process clear it — `ir.attachment.regenerate_assets_bundles()` over XML-RPC
(needs admin) — or simply restart the service with `down` + `up`, which is what the README
prescribes for a new addon directory anyway.

### 9.6 Two ways a core override silently does nothing

Both were hit on the PaymentScreen and ReceiptScreen. In each case the rule was present in the
compiled CSS, had higher specificity, and still had zero effect — the same silence as §9.1.

**(a) `min-width` beats `width`.** Core's `payment_screen.scss` pins the payment pane with two
properties:

```scss
.left-content { width: 450px; min-width: 450px; }   /* 400px at a narrower breakpoint */
```

Overriding only `width` (and `max-width`) leaves the pane at 450px. `min-width` wins over `width` in
CSS sizing, so the clamp never applied.

**(b) Bootstrap utilities are `!important`.** Core's ReceiptScreen puts `flex-lg-row` on
`.default-view`, and that utility is defined as `flex-direction: row !important`:

```css
.flex-lg-row { flex-direction: row !important; }
.border-end  { border-right: var(--border-width) var(--border-style) var(--border-color) !important; }
```

So `flex-direction: row-reverse` loses no matter how specific the selector is, and a flipped divider
needs `border-left: ... !important` to displace `border-end`. Worth noting why the first two flips
did **not** need this: neither `.product-screen` nor `.main-content` carries a flex-direction or
border utility. It depends entirely on which utility classes core happens to put on the element.

**(c) A `<record>` pointing at a `noupdate` record is skipped on upgrade.** Base wraps its currency
data in `<data noupdate="1">`, so the `ir_model_data` row for `base.IDR` has `noupdate = true`. A data
file containing `<record id="base.IDR"><field name="rounding">1</field></record>` therefore does
*nothing* on `-u kula_pos_layout` — it would only take effect on a fresh install. No error, no
warning; the module reports "installed" and the value is unchanged. `<function>` is not subject to
`noupdate`, so that is the correct tool for overriding base data.

Symptom to watch for in all three cases: a change that is *definitely* in place yet the measured value
never moves. When overriding a core property, grep core's own source for the selector first and reset
**every** declaration it sets, check the element's utility classes for `!important`, and check whether
the record being pointed at is `noupdate`.

### 9.7 Recommended, not yet done

- **Product images.** `show_product_images` is on, but no product has an image uploaded, so every
  card shows Odoo's broken-image placeholder. Either upload images or switch the setting off; the
  cards are laid out for both.
- **Categories still do not exist.** Zero `pos_category` records, so the dropdown currently offers
  only "All". Creating Coffee / Tea / Juice is the next real step.
- The **⋯ button is kept** (setting `Keep the actions (...) button`, default on) because it is the
  only route to Cancel Order and Pricelist. Turn it off in Settings → Point of Sale → *KULA counter
  layout* if the counter genuinely does not need them.
- During verification `module_pos_hr` was temporarily turned off to reach the product screen without
  a cashier PIN; it has been **restored to True**. The module itself never touches it.

---

## 10. PaymentScreen — implemented and verified

**Status: implemented and verified in the browser.** Mockup:
[payment mockup](pos-layout-payment-mockup.html).

### 10.1 The problem, measured

Pressing the KULA **Payment** button lands on the PaymentScreen, which is entirely stock Odoo.
Verified in the browser:

| Probe | Result |
|---|---|
| `.payment-screen` classes | `payment-screen screen d-flex flex-column h-100` — **no `product-screen`**, so none of the module's SCSS applies |
| Pane split | `.left-content` 450px / `.center-content` 822px (core `col-md-4`) |
| Numpad | 16 keys — `1 2 3 +10 / 4 5 6 +20 / 7 8 9 +50 / +/- 0 . ⌫` |
| Category dropdown | **present on the PaymentScreen** (leak) |

### 10.2 Bug found while testing: the category dropdown leaks

Core gates the product search on `pos.showSearchButton()`, which returns **false** on every screen
except `ProductScreen` (`pos_store.js`). The `CategoryDropdown` was inserted as a *sibling* of that
search field and gated only on `pos.config.kula_category_nav`, so it survives when the search does
not — a category filter on a payment screen, where there is nothing to browse.

**Fix (one line, do this regardless of the rest):** gate it exactly like the control it accompanies:

```xml
<CategoryDropdown t-if="pos.showSearchButton() and pos.config.kula_category_nav == 'dropdown'"/>
```

### 10.3 The layout principle, applied

§2 established: **data pane left, commit column right.** The ProductScreen is
`[ menu ] LEFT | [ order + numpad + Pay ] RIGHT`. The PaymentScreen should be the mirror of that:

```
[ amount + tenders ]  LEFT   |   [ methods + numpad + Validate ]  RIGHT
```

Core already has exactly these two panes — it simply puts them the other way round. So, as with the
ProductScreen, **the swap is CSS only**:

```scss
.payment-screen .main-content { flex-direction: row-reverse; }   /* left-content -> right, center-content -> left */
.payment-screen .left-content { width: clamp(300px, 32%, 430px); }  /* was col-md-4 */
.payment-screen .left-content { border-right: 0; border-left: 1px solid var(--border-color); }
```

The payoff: **Validate lands in the same bottom-right corner as Pay**, so the commit action never
moves between screens. No markup needs relocating.

### 10.4 Tender numpad — final shape

```
7  8  9
4  5  6
1  2  3
0  00 ⌫
```

Three things changed from core, and the reasoning for each:

1. **The `+10 / +20 / +50` column is gone.** Those keys **add ten, twenty and fifty rupiah**
   (`number_buffer_service.js` whitelists `+1 +2 +5 +10 +20 +50` and adds `parseFloat(slice(1))`) —
   meaningless at an Indonesian counter. 12 keys also yields a 3-column pad, for which core ships
   `.numpad-3-cols`.
2. **The decimal key beside `0` became `00`.** The decimal separator is useless now that IDR has no
   decimals (§12), while a double-zero key is what makes cash entry fast: for Rp 50,000 the cashier
   presses **5, 00, 00** rather than five keys. (An earlier revision put `000` and `00` on a separate
   row above the pad; that row was removed in favour of this single key.)
3. **`+/-` is gone** — a tendered amount is never negative.

> Implementation note: `sendKey("00")` is **rejected** by the number-buffer whitelist, so the pad
> takes an `onClick.bind="kulaNumpadClick"` (`payment_screen.xml`) and that handler expands `"00"`
> into two `sendKey("0")` calls, forwarding everything else to `numberBuffer.sendKey` unchanged.

Verified by driving the real screen: pressing `5` → `Rp 5`, `00` → `Rp 500`, `00` → `Rp 50,000`,
and the payment line reads `Cash Rp50,000 / Change Rp -40,000` against a Rp 10,000 order.

### 10.5 Implementation — done

All three tasks are in `addons/kula_pos_layout`:

1. `navbar.xml` — dropdown now gated on
   `pos.showSearchButton() and pos.config.kula_category_nav == 'dropdown'`.
2. `kula_pos_layout.scss` §9 — `row-reverse` on `.payment-screen .main-content`, plus the width
   clamp and inner divider on `.left-content` (see the `min-width` trap in §9.7), and a responsive
   amount size.
3. `payment_screen/payment_screen.{xml,js}` — 3-column numpad via `getNumpadButtons()`, and the
   `000` / `00` keys as a separate row wired to `kulaAppendZeros(n)`, which emits `sendKey("0")`
   n times (`sendKey("000")` is rejected by the number-buffer whitelist).

Verified on the live PaymentScreen at 1280×800, zero JS errors:

| Probe | Before | After |
|---|---|---|
| `.main-content` direction | `row` | **`row-reverse`** |
| Pay column side | left | **right** (`leftIsRight: true`) |
| Pay column width | 450px (core `min-width`) | **410px** (matches the mockup) |
| Numpad keys | 16 (`+10 +20 +50`) | **12** (`7 8 9 / 4 5 6 / 1 2 3 / 0 . ⌫`) |
| Numpad grid class | `numpad-4-cols` | **`numpad-3-cols`** |
| `000` / `00` keys | — | **present** |
| Amount font | fixed 125px | **`clamp(44px, 8.6vw, 118px)` → 110px at 1280** |
| Category dropdown | **present (leak)** | **absent** |

ProductScreen re-checked after the navbar change: still 5/4/3 columns, panes swapped, dropdown
present there, card price and Pay total intact, zero errors.

### 10.6 Open questions — resolved

- **Panes swapped** — done, so Validate sits in the same bottom-right corner as Pay.
- **`000` / `00` labels** — implemented as `000` / `00`, not `.000` / `.00`, for the reason in §10.4.
- **TicketScreen / ReceiptScreen** — still stock, still out of scope.

### 10.7 Still outstanding

- The **payment-amount popup numpad** (`payment_lines.js`, which also calls `enhancedButtons()`)
  still shows `+10 / +20 / +50`. Same IDR problem, different component; not changed here.
- A **negative Change** (`Rp -29,000.00` when tendering 50,000 against 21,000) is core behaviour —
  the change sign convention, not a layout issue.

---

## 11. ReceiptScreen — implemented and verified

Requested: the printed receipt (the "invoice") on the **left**, the order description/actions on the
**right**.

### 11.1 The flip

`.default-view`, inside `.receipt-screen`, holds the two panes — core renders `.actions` (the
payment-successful banner, print button, email field, New Order) first, then `.pos-receipt-container`
(the ticket). So it is the same CSS-only `row-reverse`, with the divider moving from `.actions`'
right edge to its left edge.

Two things this screen needed that the previous two did not:

1. **Scoped to `lg` and up.** Core renders `.default-view` as `flex-lg-row flex-column`, so below
   `lg` the two panes stack. An unscoped `row-reverse` would force a row on narrow screens and break
   that stacking, so the rule lives in `@include media-breakpoint-up(lg)`.
2. **`!important`** — because of Bootstrap's `flex-lg-row`, see §9.6(b).

### 11.2 Verified

Measured against core's exact class list at three viewports:

| Viewport | `flex-direction` | Receipt side | `.actions` border L / R |
|---|---|---|---|
| 1280×800 | `row-reverse` | **left** (x=0, actions at 640) | 1px / 0px |
| 1024×768 | `row-reverse` | **left** (x=0, actions at 512) | 1px / 0px |
| 800×1280 | `column` | stacked — core behaviour | 0px / 1px |

The 800px row is the one that matters: below `lg` the flip is correctly inert, so core's stacking and
its own divider are untouched.

### 11.3 How this was verified without touching your data

Reaching the live ReceiptScreen requires validating an order, and a validated order lands in
`pos.order` as `paid` — which the ORM refuses to delete (`_unlink_except_draft_or_cancel` in
`pos_order.py`). That would have left an unremovable test order in your database.

So the check injects a replica built from core's **exact class list** into the running POS page and
reads the computed styles back. That tests what is actually at risk — whether the compiled rule beats
Bootstrap's `!important` utilities, and whether the media query is scoped correctly — without writing
anything. Confirmed afterwards: `pos_order` still holds exactly the one order you created yourself.

### 11.4 Still outstanding

The **TicketScreen** (Orders list) is unchanged and is now the only POS screen still stock. It will
look inconsistent next to the other three.

---

## 12. Money format — IDR without decimals

Requested: amounts currently render as `Rp 200,000.00`; they should read `Rp 200,000`.

### 12.1 The knob is `rounding`, not `decimal_places`

`res.currency.decimal_places` is a stored **computed** field and is readonly:

```python
@api.depends('rounding')
def _compute_decimal_places(self):
    if 0 < currency.rounding < 1:
        currency.decimal_places = ceil(log10(1 / currency.rounding))
    else:
        currency.decimal_places = 0
```

Odoo ships IDR with `rounding = 0.01` (`base/data/res_currency_data.xml`), which yields
`decimal_places = 2` and therefore `Rp 200,000.00`. Setting `rounding = 1` yields
`decimal_places = 0` and `Rp 200,000`.

The POS loads `res.currency` including `decimal_places` (`res_currency._load_pos_data_fields`), so
this single value drives the POS, the receipt, invoices and reports alike.

### 12.2 Two traps hit on the way

1. **A `<record>` update is skipped.** `base.IDR` is `noupdate = true`, so
   `<record id="base.IDR"><field name="rounding">1</field></record>` silently did nothing on
   module upgrade. Rewritten as a `<function>` — see §9.6(c).
2. **Odoo actively blocks the change once the currency has been used.** `account` guards it:

   ```python
   if (rounding_val > record.rounding or rounding_val == 0) and record._has_accounting_entries():
       raise UserError("You cannot reduce the number of decimal places of a currency which has
                        already been used to make accounting entries.")
   ```

   `_has_accounting_entries()` is true if **any** `account.move.line` uses the currency as either its
   currency or its company currency.

### 12.3 What had to be deleted, and what did not

The block was two posted entries created by the account's own POS testing — not by this work:

| Move | Journal | Content |
|---|---|---|
| `POSS/2026/10/0001` | Point of Sale | session `KULA/00002` closing entry (Sales / Cash, 551,000) |
| `CSH2/2026/00001` | Cash | cash move (551,000) |

Only those two moves (4 lines) were removed, plus the `pos_session.move_id` back-link on session
`KULA/00002`. **The database was not deleted** — it was never necessary. Afterwards: 0 account
moves, sessions 1/2 closed and 4 open, all 6 `pos_order` records intact (all created by
`superuser@lentera.id`, including `KULA - 000008` for 200,000), 4 users intact.

Numerically this was a no-op: every stored amount is already whole rupiah, so dropping to 0 decimals
re-rounds nothing. `1234.56` now displays `Rp 1,235`.

### 12.4 Verified

Server-side (`formatLang` with the IDR record): `200000 -> Rp 200,000`, `7000 -> Rp 7,000`,
`21000 -> Rp 21,000`, `1234.56 -> Rp 1,235`.

Live POS, three viewports, zero JS errors:

| Viewport | Card price | Pay button total | Columns |
|---|---|---|---|
| 1280×800 | `Rp 10,000` | `Rp 20,000` | 5 |
| 1024×768 | `Rp 10,000` | `Rp 40,000` | 4 |
| 800×1280 | `Rp 10,000` | `Rp 60,000` | 3 |

### 12.5 Caveat

This is a **global** localisation change: the POS, invoices, reports and the accounting UI all lose
the decimals, and amounts round to whole rupiah. That is correct for IDR, but it is not a POS-only
display tweak. It is applied by `data/res_currency_data.xml` on install and on every module update,
so removing that file is what reverts it.

---

## 13. Order line stepper + delete — implemented

### 13.1 The problem

Core v19 lets you select an order line and tap it again to deselect it, but **delete and decrement
have no visible affordance**. With a line selected the quantity numpad appears (and ⌫ on an empty
buffer deletes the line), so the capability exists — nothing on screen says so. At a counter, where
the cashier is correcting an order mid-queue, that is the difference between one tap and a guess.

> **Update — see §14.** The quantity numpad has since been removed from this screen entirely, so the
> stepper below is now the *only* way to change a line's quantity, not merely the visible one. The
> handlers still work: they call `OrderSummary`'s own `_setValue` / `updateQuantityNumber`, which
> remain in place whether or not the pad is rendered.

### 13.2 Where it hooks in

Three files, all new, under `static/src/app/order_line/`:

| File | Does |
|---|---|
| `order_line.xml` | extends `point_of_sale.Orderline` with one empty slot, `<t t-slot="kula-controls"/>`, between `.line-details` and `ul.info-list` |
| `order_summary.xml` | extends `point_of_sale.OrderSummary` and fills that slot with `− qty +` and a trash button |
| `order_summary.js` | patches `OrderSummary.prototype` with the three handlers |

**Why a slot, and not markup straight into the core template.** An unfilled slot renders nothing, so
the receipt (`point_of_sale.OrderReceipt`) and the ticket screen — which reuse the same `Orderline`
template and fill neither `kula-controls` nor `pack-lot-icon` — are untouched. Only this module's
`OrderSummary` fills it, which is exactly the order pane of the product screen.

**Why the handlers live on `OrderSummary`.** It already owns `pos`, `numberBuffer` and
`this.dialog`, and its `_setValue()` / `updateQuantityNumber()` are the code paths the numpad itself
uses. The stepper calls the same `line.setQuantity(next, Boolean(line.combo_line_ids?.length))` with
the same `AlertDialog` error handling, so it cannot drift from the numpad. `removeOrderline()` is
core's own delete: it takes combo children with it and re-selects the last remaining line.

**Behaviour.** Applying a step that reaches or crosses zero removes the line (that is what ⌫ does, and
it also stops a fractional line — 0.5 kg — from flipping sign). Steps are applied to the number as
displayed, so on a negative refund line `+` walks back towards zero. Combo children get no stepper;
the quantity belongs to their parent.

### 13.3 The non-obvious part: `useTimedPress` is on the whole `<li>`

`Orderline.setup()` binds `pointerdown`/`pointerup` on the line root via `useTimedPress`, and tapping
is what selects/deselects. Those are real listeners on the `<li>` (OWL's `createElementHandler`
attaches per element), so a tap on a stepper button bubbles up and would toggle the selection as a
side effect. The wrapper carries `t-on-pointerdown.stop` / `t-on-pointerup.stop`; because it sits
between the buttons and the `<li>`, the line's handler never runs. `t-on-click.stop` alone would not
have been enough — `useTimedPress` does not listen for `click`.

### 13.4 Also

The line's own quantity badge (`.qty`, in front of the product name) is hidden with
`.orderline:has(.kula-line-controls) .line-details .qty`, so the quantity is not printed twice.
`:has()` is already a core dependency (`orderline.scss` uses it for `.has-change`) and it fails safe:
on a browser without it the badge simply stays.

### 13.5 Verified

- Bundle builds and contains every new file; the **live** server serves it at the exact URLs the POS
  page references (`/web/assets/c6dd4cb/…js`, `/web/assets/9d9eef4/…css`).
- Both XPaths match exactly one node in the core templates (`//div[contains(@class,'line-details')]`
  → its next sibling is `ul.info-list`; `//Orderline` → the one node, alongside core's
  `pack-lot-icon` slot), evaluated against `odoo:19.0`'s own template files.
- The POS boots identically **with and without** these files (A/B run in headless Chrome against the
  live database), so the added templates do not disturb the app's startup.
- **Click-through of all three buttons in the real UI — done** (by a later session, using the
  cashier-login workaround of §9.7's session: a temporary user plus `module_pos_hr` off, then
  `document.querySelector('.open-register-btn').click()`). Against two lines of Kopi / Es Teh:

  | Action | Result |
  |---|---|
  | `+` | line qty badge `1 → 2`, Pay total `Rp 10,000 → Rp 20,000` |
  | `+` again | `2 → 3`, total `Rp 30,000` |
  | `−` | `3 → 2`, total `Rp 20,000` |
  | `−` twice | `2 → 1 → 0`, **line removed** (0 lines) — the documented floor |
  | trash on line 1 of 2 | that line removed, `Es Teh` left |
  | JS errors | 0 |

- **§13.3's concern confirmed fixed.** The line stayed `selected` across four stepper clicks. A
  toggling side effect would have deselected it on the first one, so the
  `t-on-pointerdown.stop` / `t-on-pointerup.stop` wrapper does stop `useTimedPress` on the `<li>`.

### 13.6 Cache note

Adding files under an existing `static/src/**/*` glob needs no module update, but the running server
caches the asset *links* in memory. `ir.attachment.regenerate_assets_bundles()` alone is **not**
enough (§9.5) — the change only reaches the browser once the running process drops that cache, which
`env.registry.signal_changes()` does through the `orm_signaling_assets` table. Without it the page
keeps pointing at the old bundle hash and the new controls silently never load.

---

## 14. Numpads — final state across both screens

### 14.1 ProductScreen: the quantity pad is gone

The pad existed for two reasons: entering a quantity per line, and the Price/Disc entry modes —
both already dropped (price control and discount are off on this POS). At this counter the cashier
raises a quantity by tapping the product again, so the pad was only costing ~200px of vertical space
that the order lines can use.

Removed by an empty `replace` of `//Numpad` in `product_screen.xml`:

```xml
<xpath expr="//Numpad" position="replace"/>
```

`product_screen.js` still configures the pad (`getNumpadButtons()` returning 12 quantity-only keys),
so deleting that one xpath restores it in its 12-key form rather than core's 4×4 pad with the
Qty / % / Price column.

### 14.2 PaymentScreen: `00` replaces the decimal key

Full reasoning in §10.4. Short version: the tender pad is now

```
7  8  9
4  5  6
1  2  3
0  00 ⌫
```

so Rp 50,000 is entered as **5, 00, 00**. The separate `000` / `00` row that an earlier revision put
above the pad has been deleted — one `00` key inside the pad does the job.

### 14.3 Verified on the live POS

| Check | Result |
|---|---|
| ProductScreen `.numpad` present | **false** |
| ProductScreen Payment button | `Payment` / `Rp 20,000` (no decimals, §12) |
| ProductScreen Customer / Refund / ⋯ | all present, Note absent |
| PaymentScreen numpad keys | `7 8 9 4 5 6 1 2 3 0 00 ⌫` (`numpad-3-cols`) |
| PaymentScreen `.kula-quickkeys` row | **absent** |
| PaymentScreen decimal key | **absent** |
| Typing `5`, `00`, `00` | `Rp 5` → `Rp 500` → **`Rp 50,000`** |
| Payment line after entry | `Cash Rp50,000`, `Change Rp -40,000` |
| JS errors | 0 |

> Probe note: the ProductScreen's Pay button only renders once the cart is non-empty
> (`showActionButton="!currentOrder?.isEmpty()"`), and core's Customer button carries the class
> `set-partner` — not `select-partner-button`. Both cost a false negative before being spotted.
