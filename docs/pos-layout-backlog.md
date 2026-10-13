# KULA POS — backlog

Open work, ordered by value. Each item says what "done" looks like and how to check it, because the
verification method has been the hard part on this project (see §9 of
[the design doc](pos-layout-design.md) for six ways a change has silently done nothing).

Status of the module as committed: `addons/kula_pos_layout` — ProductScreen, PaymentScreen and
ReceiptScreen themed; IDR renders without decimals; order-line stepper; settings under
**Settings → Point of Sale → KULA counter layout**.

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

**Effort:** 5 min to toggle, longer for real photos. **Risk:** none.

### 3. The company is still called "My Company"

**Why:** it is printed on receipts and any report. Cheap to fix now, annoying to fix on historical
documents later.

**Do:** Settings → Companies → rename, and set the address/logo. The receipt in the POS uses
`res.company.logo` and the company name.

**Done when:** the POS receipt header shows the real trading name, not "My Company" / "Your logo".

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
