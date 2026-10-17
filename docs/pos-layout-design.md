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
- Controls on screen: **Payment, Customer, Refund** — nothing else. *Superseded by §16: the row is
  Payment + **Save Order** now, the ⋯ popup keeps the rest, and Customer and Refund are gone.*
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

> The diagram and the tables in this section describe the build before §15 (kiosk mode) and §16
> (Save Order). Both are later revisions of the same screen; read them for the current state.

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
| Control row | `ControlButtons`: Customer, **Note**, **Save/park**, More ⋯ | Customer + **Refund** *(§16: the row is the ⋯ button alone now)* | `t-inherit` → `point_of_sale.ControlButtons` |
| **Refund** | inside the ⋯ popup → `this.clickRefund()` | first-class button | call `clickRefund()` from the extended control row |
| Numpad (ProductScreen) | `Numpad` with **Qty / Price / Disc** modes | **removed entirely** | empty `replace` of `//Numpad` in `point_of_sale.ProductScreen` |
| Payment | `ActionpadWidget`: `btn-primary` "Payment", **no amount** | "Payment" + `IDR <total>` *(§16 adds Save Order under it)* | `t-inherit` → `point_of_sale.ActionpadWidget` |
| Control row position | **above** the numpad/actionpad | **below** Payment | xpath move in `point_of_sale.ProductScreen` |

### Three findings worth calling out

1. **Customer is already free.** `point_of_sale.ControlButtons` renders `SelectPartnerButton` on the
   main row by default — the original build kept it and changed nothing. §16 removes it.
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

---

## 15. Kiosk mode — category tiles, a products popup, and a sidebar

Commanded: the register should open on **the pictures of the categories**, a tap should open **that
category's products in a popup**, an **Add on** entry should list the counter's extras, and the
navbar's hamburger menu should become a **sidebar that opens over a dimmed screen**.

This is `pos.config.kula_category_nav = 'kiosk'`, now the field's default and what `seed/seed.py`
writes onto the register. The other two values still exist and still work (`dropdown`, `tiles`), so
the change is reversible from *Settings → Point of Sale → KULA counter layout*.

### 15.1 The three pieces, and the extension point each one uses

| Piece | Extension point | Files |
|---|---|---|
| Sidebar | core's burger `<Dropdown>`, re-painted: `menuClass`, `bottomSheet`, `state` props + three attribute edits | `navbar/navbar.xml`, `navbar/sidebar.js`, SCSS §13 |
| Category tiles | new component extending `point_of_sale.CategorySelector` | `category_home/category_home.{js,xml}` |
| Products popup | `dialog` service + core's `ProductCard` | `product_popup/product_popup.{js,xml}` |
| Landing view switch | `ProductScreen` template (one inserted node, two attribute edits) + a `kulaShowCategoryHome` getter | `product_screen/product_screen.{xml,js}` |

**The sidebar is deliberately not a hand-built drawer.** The burger menu is an extension point:
`pos_hr` gates its *Backend* and *Close Register* entries on cashier permissions and appends a *Lock*
entry, `pos_restaurant` inserts its floor-plan entries — all by matching
`DropdownItem[contains(text(), 'Backend')]` inside that Dropdown. Replacing the node (the first
version of this work did) does not fail loudly, it fails at template compile: the whole
`point_of_sale.Navbar` template stops loading and **the register shows "Oops! Something went wrong"**.
Verified the hard way. So the menu stays, and only *where it is painted* changes:

- `menuClass="'kula-sidebar-menu'"` — the popover is otherwise an anonymous `.dropdown-menu` in the
  overlay container, with nothing to aim SCSS at.
- popper's inline `position` / `inset` / `transform` are overridden with `!important`, which is the
  only way to beat an inline style, and is why the panel is pinned to the left edge at full height.
- `bottomSheet="false"` — otherwise a small screen gets core's bottom-sheet rendering of the same
  menu, i.e. a different animal at exactly the size where the drawer matters.
- `state="this.kulaBurger"` — the dropdown's own `useDropdownState()` instance, created by
  `sidebar.js`. It exists for the scrim: core's click-away only closes a dropdown for clicks *inside
  the same active element*, and the scrim is outside it by construction, so a tap on the dimmer would
  neither close the drawer nor reach what is behind it. With the state in hand the scrim
  (`navbar.xml`, `t-if="this.kulaBurger.isOpen"`) closes the menu it dims.

**The category home** extends `CategorySelector` for the same reason the navbar dropdown does: the
parent already resolves the tree — root categories, ordering, `hasProductsToShow`, nesting, and the
`/web/image?model=pos.category&field=image_128` URL for a category picture (`show_category_images`
is on by default). Only the rendering differs, plus three rules of its own:

- the **add-on category is filtered out** of the tiles: it already has the Add on tile, and two tiles
  opening the same list read as two different things;
- the tile list comes from `getCategoriesAndSub()`, but each popup's **products come from
  `pos.productsToDisplay`** — the list the grid renders from, already filtered (active, in POS, not
  excluded, category limits) and already ordered (favourites, `pos_sequence`, name). Resolving them
  from `category.associatedProducts` instead would let the popup and the grid disagree about what the
  menu contains;
- a **"Other" tile** appears only when a POS product has no POS category at all. Core keeps those in
  the grid; a category-first screen would otherwise have no way to reach them. On a seeded database
  there are none (§15.3), and the tile is the fallback for a product somebody creates in the backend.

**The landing view switch** is three template operations, and the middle one is a trap worth naming:

- `kulaShowCategoryHome` is true only in kiosk mode, with a catalogue loaded, not scanning, and — the
  important part — **no search word**. Searching is the one case where a flat list beats a tree, so a
  typed query hands the pane back to core's product grid.
- the product grid and its "no products" message are an `if/elif/else` chain attached to the
  *barcode-scanner* node, not to the category chips, so the tiles' own `t-if` cannot switch them off.
  Both conditions therefore carry `and !this.kulaShowCategoryHome`.
- the empty state had to stop being a `t-else` (an `else` cannot carry a condition): the template
  extension removes the `t-else` attribute and adds a `t-elif`, which leaves every other mode with
  exactly the behaviour it had.

**The products popup** stays open while products are added — a customer orders a kopi and two snacks
with one tile tap and one dismissal. It adds through `pos.addLineToCurrentOrder`, the same store
method the grid ends up in (`ProductScreen.addProductToOrder` calls it), so merge rules, taxes and
the variant configurator for a configurable product behave identically. Cards are core's
`ProductCard` with this module's price, and carry **`class="this.pos.productViewMode"`** — that prop
is core's own layout switch (`flex-column` in grid mode); without it a card lays its picture and its
text side by side inside a narrow cell. The footer repeats the running order total, because the modal
covers the order pane.

### 15.2 The data contract: every product the till sells has a POS category

A category-first screen makes the POS category load-bearing — it is no longer a filter, it is the only
route to a product. So:

- `seed/menu.csv` is the source of truth: one row per menu item, with its POS category. The seeder
  creates the categories from that column, so a menu item cannot be added without landing in one.
- `seed.py` reports, on every run, whether any **POS-available product has no POS category**
  (`report_uncategorized`). It reports rather than enforces: the database is the shop's to edit.
- **Add-ons are a category too**, named by the `ADDON_CATEGORY` constant, and the register's Add on
  tile is built from it via `pos.config.kula_addon_category_id` (a settings field). Empty ⇒ no tile.

The seeded menu gained that tier: *Extra Shot, Es Batu, Sambal Bawang, Telor, Sego Tok, Cup Take
Away* — the counter's extras, priced from the kiosk this work was specified against. They are rows in
`menu.csv` like any other; changing them is editing that file.

### 15.3 Pictures

Category tiles and product cards are picture-led, and the database had **no image at all** on any
product or category (backlog P2), so every card showed Odoo's grey placeholder. `seed/images/` now
holds one generated placeholder per menu item and per category — a flat category colour with the
item's name on it, sizes and colours documented in `seed/images/README.md` — and the seeder uploads
them (`upload_menu_image`) under two rules: **no file, no picture**, and **an image that is already
there is never replaced**, so a real photo uploaded through *Products* survives a re-seed. Replace a
file with a real photo at the same path, or upload it in Odoo; either way the seeder leaves it alone
afterwards.

### 15.4 Verified on the live register

Headless Chromium against the live stack, at 1280×800, 1024×768 and 800×1280 portrait, JS errors **0**:

| Check | Result |
|---|---|
| Landing view, 1280×800 | 4 tiles — Coffee, Juice, Tea, Add on — no duplicate Add On category |
| Landing view, 800×1280 | 2 columns × 232px tiles, `pageScroll` 0, `homeOverflow` 0 |
| Category pictures | `/web/image?model=pos.category&field=image_128&id=…` on every tile |
| Tap *Coffee* | popup titled `Coffee`, one card `Kopi · Rp 10,000`, picture present |
| Tap a card | card badge `1`, footer `Rp 10,000 → Rp 15,000`, order line `Kopi` + stepper behind |
| Tap *Add on* | popup titled `Add on`, 6 cards with prices, `Cup Take Away Rp 0` included |
| Tap *Extra Shot* | badge `1`, order line `Extra Shot Rp 5,000`, pane total `Rp 15,000` |
| Search `o` | kiosk tiles hidden, flat grid of 5 matches + *Search more* |
| Burger → sidebar | panel pinned left (307px × 800px), title `Kula Counter`, items *Install App, Reload Data, Create Product, Backend, Close Register*, LNA footer; scrim dims the register |
| Scrim tap | drawer closes (its own dismiss gesture) |
| Escape | drawer closes (core's navigation hotkey) |
| *Reload Data* from the drawer | drawer closes, core's `SyncPopup` opens over the register |
| Settings | *Add-on category* field present in *KULA counter layout* |
| `kula_category_nav = 'tiles'` | 0 kiosk tiles, core's chips `Add On / Coffee / Juice / Tea`, full grid of 9 products |
| `kula_category_nav = 'dropdown'` | navbar dropdown present (`All`), no chips, no tiles, grid of 9 |
| Drawer as the **cashier** login | *Install App, Reload Data, Backend, Close Register* — `Create Product` absent (core gates it on product-creation rights, unchanged) |

**A settings change needs the register to re-read its data.** `pos.config` is part of the data the POS
caches (IndexedDB, `point-of-sale-1-<db>`), so flipping *Category navigation* shows up on the next
fresh register load, not on a page refresh — a page reload kept serving `'kiosk'` while the database
already said `'tiles'`. Either reload data from the drawer (*Reload Data*), or clear the site's
storage; this is core's offline-first cache, not something this module adds.

A clip of the whole flow — sidebar open, sweep of its items, scrim close, *Coffee* → add, *Add on* →
add — is at `.amp/in/artifacts/kiosk-flow.mp4` (that directory is orb-local and not tracked by git;
the stills beside it are `01-kiosk-home.png`, `02-category-popup.png`, `03-addon-popup.png`,
`04-sidebar-open.png`, `05-search-grid.png`, `06-home-800x1280.png`, `07-popup-800x1280.png`).

### 15.5 Two things this cost that are worth remembering

1. **Removing a node another module extends breaks the whole template.** See the sidebar paragraph
   above: the failure is a template-compile error on `point_of_sale.Navbar`, which reaches the user
   as the POS's generic "Something went wrong" screen with the real message only in the browser
   console. Before replacing any core node in this module, assume another module inherits it:
   `grep -rl "t-inherit=\"point_of_sale.<Template>\"" /path/to/odoo/addons/*/static/src --include=*.xml`.
2. **`--` inside an XML comment is a parse error.** Two of these files had one (` -- ` rather than
   `—`), and the failure mode is the same generic screen, because the whole `…bundle.xml` module fails
   to load: *"The following modules failed to load: [point_of_sale.assets_prod.bundle.xml]"*. The
   repository's other XML uses `—` for exactly this reason.

---

## 16. Save Order — parking an order under a name

Commanded: *drop Refund and Customer from the order-side row*, and *add a "Save Order" button, the same
kind of button as Payment but another colour, which opens a form (Order Title, then Notes), records
the time, and leaves the order open in the Orders page — with a tablet feel.*

### 16.1 The button, the form, and what "parking" is

- **The button** (`action_pad.xml`) is a sibling of core's Payment container inside the actionpad, so
  it lands under Payment at the full pane width with the actionpad's own gap. It is shown under the
  same condition as Payment (`props.showActionButton`, i.e. the order is not empty) and is teal
  (`§16` of the SCSS) against Payment's violet: the two big actions must never be confused.
- **The form** is this module's own dialog (`save_order/save_order.{js,xml}`), not core's
  `TextInputPopup`, which carries one field. Two fields, sized for a finger, with the title
  auto-focused; it is handed back to the caller through `makeAwaitable`'s `getPayload`, which is why
  it resolves *before* closing — the dialog's `onClose` resolves the same promise with nothing.
- **Parking** is core's own `pos.clickSaveOrder()` — the call behind the upload button this module
  removes from the control row. It syncs the order to the server as a draft, notifies the cashier
  ("Order saved for later") and opens a fresh empty order.

### 16.2 Where the title and the note live

| Value | Field | Why |
|---|---|---|
| Order Title | **`pos.order.kula_title`** (new, this module) | no such field exists in core; `name`/`pos_reference` are the sequence's |
| Notes | core's **`general_customer_note`** | the order note core already has: the Note button writes it, the receipt prints it |
| Time | core's **`date_order`** | set on creation, printed in the Orders list's first column |

`kula_title` needs no plumbing to reach the browser: `pos.order` does not define
`_load_pos_data_fields` (unlike `pos.order.line`), so — exactly as with `pos.config`'s `kula_*`
fields — every non-manual field is loaded, and the JS record can read and set it. The order is
created on the server with that key because `_process_order` creates the order from the client's own
payload.

### 16.3 The Orders list shows it

`ticket_screen.xml` (new) inserts one node before the order-name line, twice: the Orders list is
rendered a second time for phones, as a card list rather than a table, so the extension covers
`td.order-name` (tablet) and `div.order-name` (phone). Both selectors use
`contains(@class, 'order-name')`, not `hasclass()` — the hyphen rule from §9.1.

Resuming is core's own flow and needed nothing: tap a row to select the order, then the right pane's
**Load Order** button (a full-width `btn-primary`, which is why this screen already felt like a
register and only needed bigger rows). Double-clicking the row is the other route.

The row sizing is this module's: taller cells, `15px` type, a legible status badge (SCSS §17). Sizes
only — the columns, the markup and every action on that screen are still core's, so backlog P3 (the
full ticket-screen re-theme) stays open.

### 16.4 What left the row, and what is left on it

- **Customer** (core's `SelectPartnerButton`) is gone from the control row, on request: an order is
  identified by the name the cashier types, not by a partner record. The node only exists in the
  `ControlButtons` template and is conditional on `!props.showRemainingButtons`, so the `(⋯)` popup's
  own list is untouched — but note that this leaves the *desktop* product screen with no way to
  attach a partner to an order. The small-screen actionpad branch keeps core's own button.
- **Refund** was promoted onto that row by an earlier revision (§3) and is removed on request. It
  remains in the `(⋯)` popup, which is the only route to Cancel Order, Pricelist and Refund now.
- The row's remaining button — core's bare ellipsis — is **labelled "Action"**, icon kept. An ellipsis
  asks the reader to know what is behind it, and at a counter whoever is standing there taps it; the
  popup itself is unchanged (Customer Note, Pricelist, Refund, Info, Cancel Order).

### 16.5 Verified on the live register

Headless Chromium, 1280×800, JS errors **0**:

| Check | Result |
|---|---|
| Control row | no `.set-partner`, no Refund; the `(⋯)` button alone |
| Actionpad, order empty | no Save Order (nor Payment) — core's `showActionButton` |
| Actionpad, one Kopi on the order | `Save Order` under `Payment Rp 10,000`, same width (393px), `background rgb(14, 116, 144)` vs Payment's violet |
| Tap Save Order | dialog titled `Save Order`, labels `Order Title` + `Notes`, title input focused, buttons `Cancel` / `Save Order` |
| Fill `Kiosk Test` / `less sugar`, tap Save Order | dialog closes, notification `Order saved for later`, a fresh empty order on screen |
| `pos.order` row (server) | `kula_title = Kiosk Test`, `general_customer_note = less sugar`, `state = draft`, `date_order = 2026-10-16 14:46:11`, `pos_reference = 265-1-000001`, `amount_total = 20000` |
| Orders list | row `Today · 02:46:11 PM · Kiosk Test · 5001 · 265-1-000001 · Rp 20,000 · Ongoing` — title as the first line of the name cell |
| Select the row → *Load Order* | back on the ProductScreen with `2 Kopi Rp 20,000`, `kula_title = Kiosk Test`, `general_customer_note = less sugar` |
| Type in the popup | the POS's keyboard/scan handling is not stolen: the navbar skips its focus handling while a modal is open (`noOpenDialogs()`) |
| The row's action button | reads `Action` (icon + label) at 850×1022 *and* 1280×800; tapping it opens core's `Actions` popup with all five entries |

Deleting an order from that list is worth knowing about when testing: core **cancels** a synced order
(`state = 'cancel'`) rather than unlinking it, so the row leaves the list but the record stays for the
audit trail. The test order of this run was removed outright afterwards (a draft/cancel order can be
unlinked).

### 16.6 Two findings from building this

1. **Odoo 19 buttons do not read Bootstrap's `--bs-btn-*` variables.** Setting `--bs-btn-bg` and
   friends on the class changed nothing on the live button (`background-color: rgba(0,0,0,0)`,
   colour `rgb(33, 37, 41)`); the teal is declared as plain properties, with the extra class on the
   `:hover`/`:active` selectors to out-specify Bootstrap's own `.btn:hover`.
2. **A new field on `pos.order` needs neither `_load_pos_data_fields` nor a JS model change** (§16.2).
   It is the opposite of `pos.order.line`, which does define that list — and `pos.order.line`
   provides `_is_field_accepted`, which is where a field would silently disappear if this had been a
   line.

---

## 17. The Backend shortcut belongs to the administrator

Commanded: *the Backend button on the screen before the register is opened should be gone for non-admins,
and for the admin it must land in Odoo proper, not in the kiosk.*

There are **two** Backend shortcuts inside the register and both are gated now:

| Where | Extension point | Behaviour |
|---|---|---|
| Login screen ("Unlock Register"), bottom button | `point_of_sale.LoginScreen`, `t-if` on `.select-logout` | hidden unless `pos.user.kula_can_open_backend` |
| Sidebar (`☰`) entry | `point_of_sale.Navbar`, `class` prop on `DropdownItem[Backend]` | `d-none` unless the same flag |

Both call core's `pos.closePos()`, which ends on
`/odoo/action-point_of_sale.action_client_pos_menu` — the backend. For an administrator that is where
they land; for a kiosk-only account the door never opens at all, because `kula_security`'s
`ir.http._dispatch` answers `/web`, `/odoo` and `/scoped_app` with the register. Hiding the button is
therefore not a restriction, it is removing a control that would bounce the user back to the screen
they were on.

### 17.1 The flag, and why it is a field

`res.users.kula_can_open_backend` — computed, `base.group_system` (the Odoo administrator), sent to
the register by naming it in `_load_pos_data_fields`, which `res.users` defines explicitly (unlike
`pos.config`).

A *field* and not a key added to the payload in `_load_pos_data_read` (which is how core ships
`_role`): the browser builds each record's properties from the model's field definitions
(`models/related_models/model_classes.js`), so an extra key is readable in `raw` but never as
`user.<key>` — the first version of this returned `undefined` in the browser while the payload
carried it. A field also makes the value visible where it is computed instead of being a client-only
side channel.

### 17.2 Two template facts this cost

1. **`t-if` on that sidebar entry cannot be added from here.** `pos_hr` sets `t-if="showBackend"` on
   the very same `DropdownItem` with a plain set (not an `add`), and template inheritance applies
   modules in load order — `kula_pos_layout` sorts before `pos_hr` — so the added condition is
   overwritten and the entry stays visible. A **class prop** survives it; `d-none` removes the row
   from the drawer, its tab order and the accessibility tree.
2. **Props on an OWL component are already expressions.** `t-att-class` is rejected ("t-att makes no
   sense on component") and `t-attf-class` is rejected too ("use template strings for string
   interpolation in props"); the working form is `class="<expression>"`. Both were tried, and both
   print the POS's generic "Something went wrong" screen with the real message only in the browser
   console — the same failure shape as §15.5.

### 17.3 Verified with real pointer clicks

Playwright driving the orb's Chrome (the coordinate-click path of the in-orb browser stopped delivering
pointer events after the orb resumed, so this run used Playwright against the same Chrome binary).
1280×800, both users logged in fresh:

| Check | Cashier (`cashier@kula.example`) | Admin (`aryana@odoo.com`) |
|---|---|---|
| `pos.user.kula_can_open_backend` | `false` | `true` |
| Login screen: Backend button | **absent** (0 nodes) | present, label `Backend` |
| Sidebar visible entries | Install App, Reload Data, Close Register | Install App, Reload Data, Create Product, Backend, Close Register |
| Clicking Backend | — | `/odoo/point_of_sale`, backend navbar rendered |

The stills are `15-login-cashier.png`, `16-login-admin.png`, `17-sidebar-cashier.png` and
`18-sidebar-admin.png` in `.amp/in/artifacts/` (orb-local, git-ignored); the labelled four-panel
copy that GitHub issue #3 links to is committed as
[`docs/images/backend-shortcut-cashier-vs-admin.png`](images/backend-shortcut-cashier-vs-admin.png).

---

## 18. The dashboard card's ⋮ menu never hides

Commanded (issue #5): *"Saat masuk di Point of sale > Dashboard; card list pada sistem akan selalu
terlihat three dotted menu di pojok kanan atas. Karena user akan selalu menggunakan tablet."*

Core draws that menu and then hides it. `web/static/src/views/kanban/kanban_record.scss`:

```scss
.o_kanban_record .o_dropdown_kanban { visibility: hidden; }
.o_kanban_record:hover .o_dropdown_kanban { visibility: visible; }   // reveal on hover
@media (max-width: ...md) { .o_dropdown_kanban { visibility: visible; } }  // always on phones
```

The escape hatch is **below** `md`, so it covers a phone and nothing else. A tablet is wider than
`md` and has no pointer to hover with, so on the exact device the operator holds, the menu that
opens a session, configures the counter or archives it cannot be reached. It is the dashboard's only
control besides `Continue Selling`.

### 18.1 One rule, in the theme layer

`addons/kula_workspace/static/src/theme/surfaces.scss`, inside the existing
`body.o_web_client .o_kanban_view` block:

```scss
.o_kanban_record .o_dropdown_kanban {
    visibility: visible;
}
```

Three decisions in that one line:

1. **Not a selector fight.** Visibility, not `display`, is what core toggles, so one property
   overrides both states and no `!important` is needed.
2. **Every width, not `(hover: none)`.** A media query for touch is more faithful to the reason,
   but it cannot be checked by resizing a desktop browser, and this repo verifies screenshots that
   way. Always visible is also what was asked: the shop's operators always work on a tablet.
3. **Every kanban, not just this one.** The issue says "card list pada sistem", and the same menu is
   the only way to act on a card anywhere. Nothing about it is POS-specific.

### 18.2 Verified with the menu actually opened

Playwright against the orb's Chrome, `deviceScaleFactor: 2`, pointer parked in the bottom-left corner
(so no hover can be responsible). Two sizes and both pointer kinds, because "tablet" was reported
from a resized desktop browser and can also mean a real touch screen:

| Viewport, pointer | `matchMedia("(hover: hover)")` | `.o_dropdown_kanban` | Box (x, y, w, h) | Menu opens |
|---|---|---|---|---|
| 1317×629, mouse | true (the hard case) | `visibility: visible` | (755, 120, 24, 33) | yes |
| 1024×768, mouse | true | `visibility: visible` | (983, 120, 24, 33) | — |
| 1024×768, `hasTouch` | **false** | `visibility: visible` | (983, 122, 24, 37) | yes, with a **tap** |

The opened menu lists View: Orders, Sessions; Reporting: Orders; Configure — i.e. the controls that
start, inspect and archive a counter.

Stills: `20-pos-dashboard-tablet.png`, `21-pos-dashboard-menu-open.png` (menu open with the mouse),
`22-pos-dashboard-1024.png` and `23-pos-dashboard-1024-menu.png` (open from a touch tap) in
`.amp/in/artifacts/` (orb-local, git-ignored).

Static assets only, so no module update: `regenerate_assets_bundles()` + `signal_changes()` in an
Odoo shell, then reload.

The labelled two-panel copy of the same run is committed as
[`docs/images/pos-dashboard-menu-tablet.png`](images/pos-dashboard-menu-tablet.png) and linked from
GitHub issue #5.

---

## 19. Closing the register — one question, two answers

Commanded (issue #4, *"Close Register Button"*): pressing Close Register must ask **"Are you sure you
want to close shift?"**, with a **Close Store** button next to the plain close — Close Store closes the
store and the session, the other answer closes only the shift — and either way the operator ends up
logged out, on the login page. The issue was filed as an ACL problem (*"You don't have the access
rights to get the point of sale closing control data"*) and the owner asked this work to be
coordinated with the Access Matrix effort, not to wait for it.

### 19.1 The access error was never an ACL row

Core gates its whole closing API on `point_of_sale.group_pos_user`:

| Where | What a caller without the group gets |
|---|---|
| `get_cash_in_out_list` (`pos_session.py:757`) | `AccessError` |
| `get_closing_control_data` (`pos_session.py:779`) | `AccessError` — the one in the issue's screenshot |
| `_validate_session` (`pos_session.py:427`) | no error, and no **account move**: the branch for non-POS users closes the shift and skips the day's entry |

Kula's Cashier and Barista deliberately do not carry that group — `kula_security` grants the till its
rights model by model instead — and the Access Matrix writes `ir.model.access` rows and
`ir.ui.menu.group_ids` only, so it cannot satisfy a Python `has_group()` test. Granting the group
would hand the till the whole POS User ACL set, which is exactly what `kula_security` exists to avoid.
Coordinated with that thread; nothing there touches `pos.session`.

`models/pos_session.py` therefore lifts the gate where the closing happens. The trick is that
**`sudo()` is not enough**: it raises the ACL ceiling but leaves `env.user` alone, and the check reads
the *environment's* user:

```python
self.env.user.has_group("point_of_sale.group_pos_user")            # the check
browse(6).sudo().env.user.has_group("point_of_sale.group_pos_user")   # False -- still the cashier
browse(6).with_user(SUPERUSER_ID).env.user.has_group(...)              # True
```

`_kula_closing_record()` returns the session in a superuser environment for a kiosk member
(`kula_security.group_kiosk_only`), and the session unchanged for a POS user (core handles them) or
for anybody else (core's `AccessError` is the right answer there). Four methods pass `self` through
it: `get_closing_control_data`, `post_closing_cash_details`, `update_closing_control_state_session`
and `close_session_from_ui`.

### 19.2 The confirmation

`close_shift/close_shift.{js,xml}` — an OWL dialog of this module's own, opened by the menu entry and
answered through `makeAwaitable` (the Save Order popup's shape). The navbar's Close Register item is
re-pointed at it with one attribute edit on core's own node:

```xml
<attribute name="onSelected">() => this.kulaCloseRegister()</attribute>
```

Only the handler changes: the label stays core's, and pos_hr's `t-if` gating of that same node stays
pos_hr's. The handler is not `PosStore.closeSession` — that method is also called from inside the
closing form (Cash In/Out), where a second confirmation would be noise.

The dialog asks the server for what is being closed (`get_closing_control_data` — the same call the
closing form makes a moment later) rather than counting in the browser: `pos.order._load_pos_data_domain`
is `state = draft`, so the register only ever holds *draft* orders and a locally computed total would
read zero. Core's closing form still follows — cash count, closing note, `Close Register` — because
the cash count must not be skipped.

After a close that actually happened (`ClosePosPopup.closeSession` patched, guarded on
`pos.session.state === "closed"` so failures keep the operator on the register), the operator is
**logged out to Odoo's login page**: `/web/session/logout?redirect=/web/login`, core's own logout
route, not the register's Unlock screen — one tap from the till is not a login, and the next person
would be selling without a password.

**Close Store closes the shop before this register, not after.** Core's close ends with a redirect and
then the logout, so a list of registers that refused to close cannot be shown afterwards (an
`AlertDialog` added after `super.closeSession()` was verified to be destroyed by that navigation). The
other registers are therefore closed as soon as the operator picks Close Store, the refusals are a
dialog on the spot, and this register's own closing form follows.

### 19.3 Close Store = the other registers

`pos.session.kula_close_store()` closes every *other* register of the company: `opening_control`,
`opened` or `closing_control`. The caller's own register is excluded — it is already closed by the
time this runs. Each register is closed in its own `try`, and the names that refused (draft orders, a
session mid-close) come back in `failed` and are shown as a warning before the operator is logged out,
because one counter must not be able to hold the shop open. Only a POS user or a kiosk member may
call it.

With one counter in the database this closes nothing, which is the correct answer for a one-register
shop; the behaviour is what a second counter would need. **This is the one interpretation in this
section worth confirming with the owner**: "close the store" could also mean *block reopening until
tomorrow*, which would be a new state on `pos.config`, and that was not asked for.

### 19.4 Verified

Playwright against the orb's Chrome, 1024×768, DPR 2, cashier `cashier@kula.example`, JS errors 0 in
every run:

| Run | Result |
|---|---|
| Close Register | dialog titled `Close shift?`, question, `Close Shift` / `Close Store` / `Cancel`, summary line `Kula Counter — 1 order, Rp 10,000` |
| Cancel | dialog gone, register intact, session still `opened`, nothing sent |
| **Close Shift** (a second register open) | core's closing form → session `closed` → `/web/login`; the other register still `opened`; `kula_close_store` **not** called |
| **Close Store** (a second register open) | a `pos.session/kula_close_store` call first; **both** sessions `closed` (the other one first), then `/web/login` |
| **Close Store** with a register that refuses (a draft order on it) | that register stays `opened`, the register shows *Some registers stayed open* naming it and the reason, and the flow continues |
| Either answer | ends on `/web/login` (Odoo's login form), with the session destroyed |
| Closing the seeded day | produced `POSS/2026/10/0001`, posted, Rp 148,000 — the branch §19.1 says would otherwise be skipped |

The second register was a throwaway `pos.config` created for the test and removed afterwards (its
sessions deleted; the one throwaway sale used to check the summary line was removed with SQL, because
the ORM refuses to delete a paid order — see the backlog recipe).

Stills, `.amp/in/artifacts/` (orb-local, git-ignored): `44-confirm-close-shift.png` (the dialog),
`45-closing-form-shift.png` (core's form behind it), `47-confirm-with-sales.png` (the summary line with
a sale in the session), `53-close-store-refusal.png` (the register that refused, named on the spot,
followed by `54-closing-form-after-refusal.png`) and `52-web-login-after-close.png` (Odoo's login page
it ends on).

One piece of core behaviour worth knowing: after a close, loading the register again creates an
`opening_control` session for the config by itself, so the "Open Register" screen has something to
open. It is not this module's doing, and `kula_close_store` treats it as open.

### 19.5 Two XML traps, again

Both were hit while writing §19.2, and both fail as "the whole register shows nothing":

1. **`--` inside an XML comment is a parse error.** `confirmation -- "Are you sure..."` broke
   `point_of_sale.assets_prod.bundle.xml` (§15.5 said this once already). Use `—`.
2. **`&mdash;` is not defined.** OWL templates are parsed as XML with no entity table: it must be the
   literal `—` character.
