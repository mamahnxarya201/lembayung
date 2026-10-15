# POS screen layout — Module vs Model

**Decision record for `suaraloka` POS screen composition (Odoo 19).**

- Status: proposed
- Scope decided: **POS screen layout** (product grid, order panel, actionpad/numpad, categories) — *not* the printed receipt/ticket
- Constraint given: **customization is done by me, in code, per deployment**
- All Odoo facts below were read from the running `lembayung_web_1` container (`odoo:19.0`), not from memory.

---

## 1. The decision, up front

**Use a Module. Do not create a layout Model.**

Layout lives in **code** (OWL templates + `patch()`), and per-deployment variation lives in a
**handful of `pos.config` fields** that the templates branch on. That is exactly how Odoo core
itself does it, and it costs you almost nothing beyond the module you have to write anyway.

Revisit this only when a trigger in §6 fires.

---

## 2. First, the question is a category error

"Module or Model" are not two options on the same axis:

| | What it is | Axis |
|---|---|---|
| **Module** | A deployable package (`__manifest__.py`, Python, JS, XML) | *Packaging / where code ships* |
| **Model** | An ORM class + DB table holding records | *Persistence / where data lives* |

Two consequences settle the framing:

1. **A Model never removes the need for a Module.** A layout model is inert — something must read
   it and render it. That reader is code in a module, and it must know how to draw every widget
   the model can name. So choosing "Model" means *Module + Model + renderer + widget contract*.
   It is strictly more work, never less.
2. **A Module works fine with no Model at all.** Templates and `patch()` need zero new tables.

So the real question is narrower and answerable:

> **Where does the layout variation live — in compiled code, or in database records?**

That is a *compile-time vs run-time* decision. Everything below is really about that.

---

## 3. What Odoo 19 actually gives you (verified)

### 3.1 The layout is code, and it is hardcoded

`point_of_sale.ProductScreen` is a plain OWL QWeb template that hardcodes the whole arrangement:

```
product_screen.xml
└── div.product-screen.d-flex.h-100
    ├── div.leftpane          → OrderSummary, ControlButtons, Numpad, ActionpadWidget
    └── div.rightpane         → CategorySelector, div.product-list.d-grid → ProductCard ×N
                                + div.switchpane  (small-screen "Pay / Cart" bar)
```

There is **no core `pos.layout` model, no `ir.ui.view`-style record, no layout table.** The
arrangement is markup. The only layout-ish state is on `pos.config`
(`models/pos_config.py`):

```python
iface_group_by_categ      = fields.Boolean("Group products by categories")
iface_big_scrollbars      = fields.Boolean('Large Scrollbars')
iface_available_categ_ids = fields.Many2many('pos.category', ...)
iface_tax_included        = fields.Selection([...], string="Tax Display")
show_product_images       = fields.Boolean("Show Product Images", default=True)
```

…and the templates branch on them, e.g. the product grid cell:

```xml
imageUrl="pos.config.show_product_images and this.getProductImage(product)"
class="pos.productViewMode"
```

**This is the important signal.** Odoo serves tens of thousands of merchants, faces far more layout
diversity than you do, and still chose: *structure in code, variation in a few Boolean/Selection
fields.* Nobody built a layout engine, because a layout engine is more expensive than the problem.
Your case is a strict subset of theirs.

### 3.2 The extension seams that do exist

| Seam | Mechanism | Where |
|---|---|---|
| Rearrange / swap markup | `t-inherit` + `t-inherit-mode="extension"` + `<xpath>` | any `*_assets_pos` XML |
| Change behavior | `patch()` from `@web/core/utils/patch` | component `.js` files |
| Add a whole screen | `registry.category("pos_pages").add(...)` | `pos_app.js` |
| Add a frontend model | `registry.category("pos_available_models").add(...)` | `models/*.js` |
| Inject global UI | `registry.category("main_components").add(...)` | `render_service.js` |
| Style / grid columns | SCSS in the same bundle | `product_screen.scss` |
| **Get a Model to the frontend** | `_load_pos_data_fields` / `_load_pos_data_domain` / `_load_pos_data_read` | `pos_config.py:263–281` |

The asset bundle is **`point_of_sale._assets_pos`** (`__manifest__.py` line 145), which
`point_of_sale.assets_prod` includes. Declare your files there.

### 3.3 Proof by precedent: `pos_restaurant`

A core module that substantially re-arranges the POS does it entirely with **template extension and
patches** — 18 `t-inherit` extensions, including one on the screen itself:

```xml
<t t-name="pos_restaurant.ProductScreen"
   t-inherit="point_of_sale.ProductScreen" t-inherit-mode="extension">
    <xpath expr="//div[hasclass('control-buttons')]" position="after">
        <div t-if="this.pos.numpadMode == 'table'" class="input"> ... </div>
    </xpath>
    <xpath expr="//ActionpadWidget" position="attributes">
        <attribute name="setTable">() => this.setTable()</attribute>
    </xpath>
    <xpath expr="//Numpad" position="attributes">
        <attribute name="t-if" add="this.pos.numpadMode=='table'" separator=" or "/>
    </xpath>
</t>
```

Note the selector style: **`hasclass()`**, not positional paths. That is what keeps this surviving
majors. Copy that discipline.

It is also how core gates a layout feature — a `module_*`-style flag on `pos.config`, branched in
the template:

```xml
<button t-if="pos.config.module_pos_restaurant and !this.currentOrder.isRefund" ...>
```

---

## 4. The decision rule

> **Who changes the layout, and when?**
> **At deploy time, by a developer → code (Module).**
> **At run time, by a non-developer → records (Model) + a renderer.**

Your answer is the first one, so the rule already resolves it. The cost gradient:

| | Layout lives in | You write | Runtime flexibility | Breakage at Odoo 20 |
|---|---|---|---|---|
| **L1** Patch markup | Template `xpath` | Least | None — redeploy to change | Loud (template not found) |
| **L2** Module + `pos.config` fields | Template + a few fields | A little more | Per-deployment toggles in Settings | Loud |
| **L3** Module + Model + renderer | Your own layout engine | Most, by far | Non-devs rearrange in a UI | **Silent** (renders empty / drifts) |

**Recommendation: L2.** It satisfies "customizable on my side" today without building an engine.

### Why not L3 now — the four real arguments

1. **You would be writing `ir.ui.view` for OWL.** That is the actual deliverable behind "a Model":
   a schema, a versioning story, validation, a renderer, and a widget registry. Odoo declined to
   build this for the POS. You would own it forever.
2. **The widget-contract problem.** A model can only name widget types that code registered. So the
   Model does not reduce code — it *adds* a layer that must keep those names stable while core
   renames components between majors.
3. **Failure-mode asymmetry — the strongest argument.** With L1/L2, an Odoo major that touches POS
   OWL fails **loudly**: your `t-inherit` target vanishes and the asset build errors. With L3,
   `ProductCard` becomes `ProductTile` and your renderer keeps "working" — drawing nothing, or
   silently dropping a slot. You want upgrade breakage you can see.
4. **Premature abstraction.** `addons/` is empty and there is one commit. You do not yet know the
   *second* layout variation. Designing a schema for variations you have not seen is how you get a
   schema that fits none of them.

---

## 5. Concrete shape of the recommended answer

One addon, e.g. `addons/suaraloka_pos_layout/`:

```
suaraloka_pos_layout/
├── __manifest__.py
├── models/pos_config.py            # the per-deployment toggles (L2)
├── views/res_config_settings.xml   # surface them in Settings → POS
└── static/src/
    ├── app/screens/product_screen.xml   # layout: t-inherit extension
    ├── app/screens/product_screen.js    # behavior: patch() if needed
    └── app/screens/product_screen.scss  # grid columns, spacing
```

```python
# __manifest__.py
{
    'name': 'Suaraloka POS Layout',
    'depends': ['point_of_sale'],
    'data': ['views/res_config_settings.xml'],
    'assets': {
        'point_of_sale._assets_pos': [
            'suaraloka_pos_layout/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
```

```python
# models/pos_config.py — the "customizable on my side" part, for free
class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_layout_compact   = fields.Boolean("Compact product grid", default=False)
    pos_layout_show_more = fields.Boolean("Show extra actionpad buttons", default=True)
```

```xml
<!-- static/src/app/screens/product_screen.xml -->
<templates id="template" xml:space="preserve">
    <t t-name="suaraloka_pos_layout.ProductScreen"
       t-inherit="point_of_sale.ProductScreen" t-inherit-mode="extension">

        <!-- stable selector: hasclass, never positional -->
        <xpath expr="//div[hasclass('subpads')]" position="after">
            <button t-if="pos.config.pos_layout_compact"
                    class="btn btn-secondary btn-lg mt-1"
                    t-on-click="() => this.pos.navigate('TicketScreen')">
                <span>Orders</span>
            </button>
        </xpath>

        <xpath expr="//div[hasclass('product-list')]" position="attributes">
            <attribute name="t-attf-class" add=" #{pos.config.pos_layout_compact ? 'grid-compact' : ''}"/>
        </xpath>
    </t>
</templates>
```

Then **restart the stack** after adding the directory — the addons path is scanned at process start
(README §5), and `down` + `up`, never `podman restart`.

### Climb to L3 only when a trigger fires

If the Model layer is ever genuinely needed, the migration is clean *because* L2 kept the schema in
`pos.config`: promote those fields to a `pos.layout` model, store the arrangement as JSON on the
layout record, ship it via `_load_pos_data_read`, and keep the same `suaraloka_pos_layout` module as
the renderer. You would be adding records to an existing seam, not rewriting the feature.

---

## 6. Triggers to switch to a Model (write these down; check them later)

Go to L3 **only** when at least one is true:

- [ ] A **second or third store** needs a materially different arrangement, and the alternative is
      forking the module per client.
- [ ] A **non-developer** must rearrange the screen at run time. (This is the real bar — note the
      deliverable is then a *layout editor UI*, not a model. Budget accordingly.)
- [ ] You are **selling this as multi-tenant** and each tenant configures its own POS.
- [ ] You need **A/B testing** of layouts across stores.

Absent these, a Model is cost with no buyer.

---

## 7. Gotchas specific to this repo

- **New addon directory ⇒ full restart.** `down` + `up`; never `podman restart` (README §5).
- **`--dev` for the inner loop.** `ODOO_DEV=xml,qweb` in `.env` reloads templates/assets without a
  restart; unset it for normal runs.
- **Two layout paths, not one.** The screen branches on `pos.isSmallProductScreen` and
  `pos.mobile_pane` and renders a different `switchpane` bar. Any layout you design must say what
  happens on the small-screen path, or touch terminals will look broken.
- **Extend the `t-name` exactly.** `t-inherit` must match the target's `t-name`
  (`point_of_sale.ProductScreen`); a typo fails at asset build.
- **Prefer `hasclass()` xpaths.** Positional selectors (`//div[3]`) break on every minor core tweak.
- **Don't fight `ProductCard`.** Grid density is `productViewMode` + CSS; reimplementing the card
  buys you a maintenance bill and loses upstream fixes.
- **The receipt is a separate problem.** Ticket/receipt layout is QWeb report templates, not the
  `_assets_pos` bundle — do not try to solve both in one module.

---

## 8. Summary

| Question | Answer |
|---|---|
| Module or Model? | Not alternatives. Every answer is a Module. |
| Does a layout Model remove the need for a Module? | No — it adds a renderer *and* a widget contract on top. |
| Where does the layout live? | **Code**: `t-inherit` extension of `point_of_sale.ProductScreen`. |
| Where does "customizable on my side" live? | **`pos.config` fields** + template branches. Cheap, and core's own pattern. |
| When is a Model right? | When a **non-developer** rearranges it at **run time**, or you go multi-tenant. |

The honest one-liner: **a Module is unavoidable, a Model is optional — and for code-only,
per-deployment screen layout, the Model is a liability you have not earned the need for yet.**
