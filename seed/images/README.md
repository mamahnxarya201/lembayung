# Menu pictures

One file per menu item and per POS category, named after the record:
`products/<slug>.png` for a `product.template` (the names in `menu.csv`) and
`categories/<slug>.png` for a `pos.category`. The slug is the name lower-cased
with every run of non-alphanumerics turned into `-` — `Es Teh` is
`es-teh.png`, `Cup Take Away` is `cup-take-away.png`.

`seed/seed.py` uploads them (`upload_menu_image`): a file is applied to a record
that has **no** image yet, and never to a record that already has one. That is
what makes a re-seed safe — a real photo uploaded through *Products* is not
something the seed gets to overwrite.

These are generated, not photographed. What they are is a flat category colour
with the item's name on it, which is the difference between a register that
looks like a menu and one showing Odoo's grey placeholder on every card while
the real pictures are still being taken.

**Replace them with real photos.** Drop a photo in at the same path (any size;
Odoo resizes it) and it is uploaded for every record that does not have an
image yet. For an item added to `menu.csv`, generate a matching placeholder
with:

```bash
magick -size 512x512 xc:"#6F4E37" \
  \( -background none -fill white -font DejaVu-Sans-Bold -pointsize 88 \
     -size 440x440 -gravity center caption:"New Item" \) \
  -gravity center -composite seed/images/products/new-item.png
```

The category colours: Coffee `#6F4E37`, Tea `#2E7D5B`, Juice `#D98324`,
Add On `#5B4BC4` — the same indigo the register's Add on tile uses, so the
picture and the tile read as one thing.
