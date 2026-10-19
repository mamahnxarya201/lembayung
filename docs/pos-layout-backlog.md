# KULA POS — backlog

Open work, ordered by value. Each item says what "done" looks like and how to check it, because the
verification method has been the hard part on this project (see §9 of
[the design doc](pos-layout-design.md) for six ways a change has silently done nothing).

Status of the module as committed: `addons/kula_pos_layout` — ProductScreen, PaymentScreen and
ReceiptScreen themed; IDR renders without decimals; order-line stepper; navbar sidebar; **kiosk mode**
(category picture tiles → products popup → add-ons, §15 of the design doc); **Save Order** (park an
order under a name, then find it in the Orders list, §16); **closing the register** (a
"close shift?" confirmation with Close Shift / Close Store, and a close that works for every role,
§19); **every sale and shift names its operator** (§20: the Orders list's Cashier column was empty
for every sale made with the cashier login off, an administrator's included — issue #9); **a 24-hour
clock** (§22: the list cells and the receipt render from the locale, which no language setting
reaches — issue #7); **rounded cash suggestions** on the payment screen, following what the second
payer still owes on a split bill (§23); settings
under **Settings → Point of Sale → KULA counter layout**.

---

## P1 — The layout is running half-blind without this

### 1. Create the POS product categories

**Why:** the navbar category dropdown is the headline piece of the ProductScreen layout, and it
currently offers exactly one option: *All*. There are **zero `pos_category` records** in the
database, so the feature is inert.

**Do:** create the categories the menu needs (Coffee / Tea / Juice …) and assign the existing
products (Kopi 10.000, Es Teh 5.000, Sinom 7.000). In Odoo: *Point of Sale → Products → POS
Product Categories*, then set each product's POS category. A category with no products is filtered
out of the dropdown by core (`hasProductsToShow`), so partial work is safe.

**Done when:** opening the dropdown lists the categories, selecting one filters the grid, and
`All` restores it.

**Status 2026-10-16:** done by the seeder. `seed/menu.csv` carries the POS category for each
product, so `seed/seed.py --apply` creates Coffee / Tea / Juice and files Kopi 10.000, Es Teh
5.000 and Sinom 7.000 under them — verified live in the register (the dropdown lists all three).

**Status 2026-10-16 (kiosk mode):** the categories are now load-bearing rather than cosmetic: the
register's landing view is one tile per category, so a product with no POS category has no route to
it at all. `seed/menu.csv` therefore also carries the **Add On** category (the counter's extras), and
`seed.py` reports on every run whether any POS-available product is uncategorised
(`report_uncategorized` — currently `none`). A product holds a single POS category in this dataset;
the code follows core and accepts several.

**Effort:** 15 min. **Risk:** none — pure data.

---

## P2 — Visible defects a customer would notice

### 2. Product images, or switch the setting off

**Why:** `show_product_images` is on, and **no product has an image uploaded**, so every card renders
Odoo's broken-image placeholder above the name. Confirmed on the live screen.

**Do:** either upload `image_128` for each product, or turn off *Show Product Images* in
Settings → Point of Sale. The cards are laid out to work either way (the price sits in flow, so it
never overlaps the name).

**Done when:** no placeholder graphic appears on any card.

**Status 2026-10-16:** done, with a caveat. `seed/images/` now holds one generated placeholder per
menu item and per category (flat category colour, the item's name on it), and `seed.py` uploads them
for any record that has **no** image yet — it never replaces one, so a real photo is safe from a
re-seed. What the register shows today is therefore a *menu that looks like a menu*, not the shop's
photographs: replace `seed/images/products/<slug>.png` with the real picture, or upload it on the
product in Odoo, and delete nothing else. Colours, naming and the one-liner that generates a new
placeholder are in `seed/images/README.md`.

**Effort:** 5 min to toggle, longer for real photos. **Risk:** none.

### 3. The company is still called "My Company"

**Why:** it is printed on receipts and any report. Cheap to fix now, annoying to fix on historical
documents later.

**Do:** Settings → Companies → rename, and set the address/logo. The receipt in the POS uses
`res.company.logo` and the company name.

**Done when:** the POS receipt header shows the real trading name, not "My Company" / "Your logo".

**Status 2026-10-16:** the name, phone and address come from `seed/company.csv` (Kula, Jakarta), so
the seeder renames the company on a fresh database. The **logo** is still unset — the receipt shows
the placeholder for it.

**Effort:** 10 min.

---

## P3 — Consistency: the last stock screen

### 4. TicketScreen (Orders) is the only POS screen still stock

**Why:** the ProductScreen, PaymentScreen and ReceiptScreen are all themed now. Tapping **Orders**
in the navbar lands on a screen that looks like a different application. See §11.4.

**Do:** it is the same technique — core renders `.ticket-screen` with its own pane structure
(`ticket_screen.scss` already references `.leftpane`/`.rightpane`), so decide the intent first:
should the ticket list mirror the other screens (list left, detail right) or its own thing? A
mockup first, as with the PaymentScreen, is the established process here.

**Done when:** a design is agreed and the screen no longer reads as a different product.

**Status 2026-10-16:** partly addressed by §16, not closed. The list now prints the **order title** the
cashier typed into Save Order as the first line of the name cell (the reason this screen matters at
all now — it is where a parked order is found), and its rows were sized for a tablet (taller cells,
15px type, legible status badge). The panes, the toolbar and the columns are still core's, so the
"looks like a different application" part of the complaint stands.

**Effort:** half a day including a mockup. **Risk:** medium — this screen has more interactive state
than the others.

---

## P4 — Money entry leftovers

### 5. The payment-amount popup numpad still has `+10 / +20 / +50`

**Why:** those keys **add ten, twenty and fifty rupiah**
(`number_buffer_service` whitelists `+1/+2/+5/+10/+20/+50`). The main tender pad had them removed
(§10.4), but `payment_lines.js` calls `enhancedButtons()` too, for the popup you get when editing a
payment amount — so the useless keys survive there.

**Do:** patch that component's numpad the same way, replacing the column with `00` (or dropping it).
Check first whether the popup is reachable at all in this configuration.

**Done when:** no IDR-meaningless quick-add key appears anywhere in the POS.

**Effort:** 30 min. **Risk:** low.

### 6. Negative change reads `Rp -29,000`

**Why:** tendering 50,000 against a 21,000 order shows `Change  Rp -29,000`. It is core's sign
convention rather than a layout bug, but it reads as a loss to a cashier.

**Do:** decide whether to leave it (core behaviour, less upgrade risk) or display the absolute value
with a "Change" label. If changing, do it in the display layer only — never in the stored amount.

**Effort:** 30 min once decided. **Risk:** low, but decide deliberately.

---

## P5 — Verification debt

### 7. The ReceiptScreen was never verified on screen

**Why:** reaching the live ReceiptScreen means validating an order, which creates a `paid` record the
ORM refuses to delete (`_unlink_except_draft_or_cancel`). It was verified by injecting core's exact
class list into the live page and reading computed styles (§11.3) — good evidence, but not the real
screen.

**Do:** now that deleting data is authorised, validate one throwaway order, look at the real
ReceiptScreen (receipt should be on the **left**), then delete the order and its session if you do not
want it. Confirm the border is on the left of the action pane and the receipt is the left-hand pane
at ≥992px, and that below that the panes still stack.

**Done when:** the real screen matches, or a screenshot in the doc proves it.

**Effort:** 20 min. **Risk:** creates data — clean up after.

**Status 2026-10-19:** done, on the real screen, at both ends of the layout range — 1280×800 (DPR
1.5) and 412×915 (DPR 2.6). At 1280×800 the receipt is the left-hand pane with the action pane on the
right and `New Order` at the bottom; on the phone the panes stack (actions above the receipt) and
`New Order` stays pinned at the bottom, with no scrolling. One sale was validated per size and both
were deleted afterwards, with their POS pickings; the seeded day (7 orders) and the open session are
back exactly as the seeder left them. Still: `.amp/in/artifacts/kiosk-responsive/keep/11-phone-receipt.png`
(the 1280×800 render was measured, not kept).

---

### 8. The phone/tablet layouts were verified in Chromium, not on the tablet

**Why:** the responsive work (§26 of the design doc) was driven in the orb's Chromium with a touch
emulation profile (`hasTouch`, `(pointer: coarse)` asserted), at the MatePad T10s' CSS viewports
(1280×800 and 800×1280 at DPR 1.5, 960×600 and 600×960 at DPR 2), on a phone (412×915, 915×412) and
on a small phone (320×480 at DPR 3). The soft keyboard cannot be raised in a headless browser, so it
was covered two ways: the viewport was shrunk by the keyboard's height (what Chrome's
`interactive-widget=resizes-content` does) and, separately, `window.visualViewport` was replaced with
one reporting a covered slice (what the older `resizes-visual` behaviour reports). Both pass, but
neither is the same thing as the device's own keyboard and its animation.

**Do:** on the T10s, in both orientations: open Save Order and the Customer form with the keyboard up
and confirm the field being typed in is visible and Cancel/Save stay on screen; open a 12-line order
and confirm the list scrolls while Payment / Save Order stay put; rotate with the keyboard open and
with a dialog open.

**Done when:** the device shows what §26.3 measured, or the difference is written down here.

**Effort:** 15 min on the device. **Risk:** none — read-only.

---

## Environment recipes (these cost real time to re-derive)

### Getting a POS session in a headless browser

The POS lands on its own *Unlock Register* screen, which blocks any automated check. Two things get
past it:

1. Create a throwaway user with `point_of_sale.group_pos_manager` + `base.group_system`, and log in
   as it (an admin session is needed for the asset APIs below).
2. `pos.config.module_pos_hr = False` on config 1 — with HR on, the login needs a cashier PIN.
3. On the login screen, click `.open-register-btn`; it just selects the current user as cashier.
4. **Restore `module_pos_hr = True` and delete the throwaway user afterwards.**

### Why this module's own data files cannot touch pos_hr's fields

`kula_pos_layout` sorts **before** `pos_hr` in the load order (§17.2 relies on it for template
inheritance), so while this module is being loaded, pos_hr's Python is not in the registry yet and
`pos.order` has **no `employee_id`** field. A `<function>` in a data file, a `migrations/` script and
`post_init_hook` all run at that moment: they execute, see no field, and do nothing — silently. The
same method from `odoo shell` works, because the registry is complete there. Anything that has to
touch pos_hr's fields has to run after the registry is up: from the register itself, from the
seeder, or from a shell. (Found on issue #9; the full evidence is in §20.3 of the design doc.)

### Making a static change actually reach the browser

Editing `static/**` needs no module update, but the running server caches the asset *links* in memory,
so the page keeps pointing at the old bundle hash and the change appears to do nothing (§9.5, §13.6).
Either restart the service, or invalidate in-process:

```python
env['ir.attachment'].regenerate_assets_bundles()
env.registry.signal_changes()      # the part that actually reaches the running process
```

Then confirm by grepping the bundle the page references, not by trusting the command:

```bash
curl -s -b cookies "http://localhost:8069$(curl -s -b cookies http://localhost:8069/pos/ui/1/product \
  | grep -o '/web/assets/[^"]*assets_prod.min.js' | head -1)" | grep -c '<your-new-identifier>'
```

### Deleting a verified sale

The ORM refuses to delete a `paid` order (`_unlink_except_draft_or_cancel`) and refuses to set it back
to `draft` or `cancel` ("This order has already been paid"), so a throwaway sale created to check a
screen cannot be removed through the ORM at all. The row can:

```sql
delete from pos_order where id = <id>;   -- lines and payments cascade (FKs are ON DELETE CASCADE)
```

Check first that nothing else points at it (`account_move.reversed_pos_order_id`, `account_payment`,
`payment_transaction`, `stock_picking` all restrict), and that it has no account move of its own — one
exists only once the session is closed. Delete the throwaway session too
(`env['pos.session'].browse(id).unlink()`), and never leave a session in `closed` state without
`stop_at` (see the note about writing `pos.session.state`).

### Reaching the ProductScreen's controls in a probe

Two false negatives already paid for: the Pay button only renders once the cart is **non-empty**
(`showActionButton="!currentOrder?.isEmpty()"`), and core's Customer button carries the class
`set-partner`, not `select-partner-button`.

---

## Deliberately not doing

- **Receipt/PDF report layout** beyond the POS receipt screen — separate QWeb mechanism, out of scope
  so far.
- **A layout Model instead of a Module** — see
  [the reasoning doc](pos-layout-module-vs-model.md); revisit only if a non-developer must rearrange
  the screen at runtime, or this goes multi-tenant.
- **`devenv.lock`** is now tracked; leave it alone.
