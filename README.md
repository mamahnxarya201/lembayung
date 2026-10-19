# lembayung

An [Odoo 19](https://www.odoo.com) development stack — Postgres + Odoo + a
Mailpit mail catcher — run with `podman-compose`. A devenv (Nix) toolchain and
helper scripts are included, but the stack and the quick start do not need Nix.

```
docker-compose.yaml   the stack (Odoo 19, Postgres 18, Mailpit)
seed/                 the "Kula" demo dataset (seed.py + CSVs)
devenv.nix/.yaml      the dev environment + helper scripts
.env                  compose variables (git-ignored)
```

| Service | URL | Notes |
|---|---|---|
| Odoo | http://localhost:8069 | admin `aryana@odoo.com` / `admin`, db `development-odoo` |
| Mailpit | http://localhost:8025 | catches every email Odoo sends (in-memory) |
| Postgres | internal only | user `admin` (see `.env`) |

Demo logins after seeding: `owner@kula.example`, `cashier@kula.example`,
`barista@kula.example` / `kiosk`. Company `Kula`, Indonesia / IDR.

---

## 1. Prerequisites

- **podman** (rootless) with `podman-compose`
- **python3** (runs `seed/seed.py`; standard library only)
- **curl** (the quick start waits for Odoo's HTTP port)
- Optional: **nix** + **devenv** — <https://devenv.sh/getting-started/> — for
  the devenv path in §2.2. Nothing in §2.1 needs it.

Rootless podman + SELinux: the compose file uses `:Z` on every bind mount, so
no extra setup is needed.

---

## 2. Run it from a clean clone

Two paths, same result. Pick the one that matches your machine:

- **[§2.1 Podman only (no Nix)](#21-podman-only-no-nix)** — podman and
  podman-compose are installed, and you do not want a Nix toolchain.
- **[§2.2 devenv (Nix)](#22-devenv-nix)** — devenv supplies the toolchain and
  the helper wrappers.

Both run the same provisioning block: it creates `development-odoo` without
demo data, installs the Odoo apps, localizes Indonesia/IDR, installs the Kula
addons, seeds the demo data, and restarts the stack.

### 2.1 Podman only (no Nix)

**Prerequisites:** podman (rootless) + podman-compose, python3, curl. Rootless
podman + SELinux needs nothing extra: the compose file uses `:Z` on every bind
mount.

This is the whole setup, in one sequence. Run it from the repository root on a
clean clone. It takes a few minutes; the database and modules live inside the
containers, not on the host.

If a previous attempt left a broken stack, run `podman-compose down` first
([§4](#4-reset-a-broken-stack)); it removes only this stack's containers.

```bash
set -euo pipefail

# 1. Local compose variables. .env is git-ignored; set POSTGRES_PASSWORD as you like.
cp -n .env.example .env

# 2. The bind mount masks /etc/odoo, so seed the config from the image.
#    container-data/ is git-ignored and starts empty on a clean clone.
mkdir -p container-data/odoo-web-data container-data/odoo-db-data container-data/config addons
podman run --rm --entrypoint cat docker.io/library/odoo:19.0 /etc/odoo/odoo.conf \
  > container-data/config/odoo.conf
chmod 0644 container-data/config/odoo.conf
podman unshare chown -R 100:101 container-data/odoo-web-data

# 3. Start the stack and wait for Odoo.
podman-compose up -d
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8069/web/login >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "Odoo did not start on :8069" >&2
    exit 1
  fi
  sleep 2
done

set -a; . ./.env; set +a
WEB=$(podman ps --filter label=com.docker.compose.service=web --format '{{.Names}}' | head -n1)
[ -n "$WEB" ] || { echo "web container not found" >&2; exit 1; }

# 4. Create development-odoo without demo data, then install the core apps.
#    --without-demo is required: kula_pos_layout raises IDR to whole-rupiah,
#    which Odoo refuses once demo accounting entries exist.
podman exec -i "$WEB" odoo -d development-odoo \
  -i point_of_sale,stock,hr,account,l10n_id \
  --without-demo=True --stop-after-init --no-http \
  --db_host=db --db_user="$POSTGRES_USER" --db_password="$POSTGRES_PASSWORD"

# 5. Match the documented admin login (a CLI-created DB starts with `admin`).
podman exec -i "$WEB" odoo shell -d development-odoo --no-http \
  --db_host=db --db_user="$POSTGRES_USER" --db_password="$POSTGRES_PASSWORD" <<'PY'
u = env.ref('base.user_admin')
u.write({'login': 'aryana@odoo.com'})
u.partner_id.write({'email': 'aryana@odoo.com'})
env.cr.commit()
PY

# 6. Localize the company: Indonesia, IDR, Asia/Jakarta.
podman exec -i "$WEB" odoo shell -d development-odoo --no-http \
  --db_host=db --db_user="$POSTGRES_USER" --db_password="$POSTGRES_PASSWORD" <<'PY'
company = env.company
idr = env['res.currency'].with_context(active_test=False).search([('name', '=', 'IDR')], limit=1)
country = env.ref('base.id')
if not idr.active:
    idr.active = True
company.write({'country_id': country.id, 'currency_id': idr.id})
env.cr.commit()
if not company.chart_template:
    env['account.chart.template'].try_loading('id', company)
    env.cr.commit()
admin = env.ref('base.user_admin', raise_if_not_found=False)
if admin and admin.tz != 'Asia/Jakarta':
    admin.partner_id.tz = 'Asia/Jakarta'
    env.cr.commit()
PY

# 7. The repository apps: roles, sidebar/dashboard, access matrix, kiosk POS.
podman exec -i "$WEB" odoo -d development-odoo \
  -i kula_security,kula_workspace,kula_access_matrix,kula_pos_layout \
  --without-demo=True --stop-after-init --no-http \
  --db_host=db --db_user="$POSTGRES_USER" --db_password="$POSTGRES_PASSWORD"

# 8. The Kula demo data: company, people, menu, pantry, a day of takings.
python3 seed/seed.py --db development-odoo --user aryana@odoo.com \
  --password admin --apply

# 9. Restart the web process so it loads the new registry and assets.
podman-compose down
podman-compose up -d
```

Open <http://localhost:8069> and sign in as `aryana@odoo.com` / `admin`.
The demo logins (`owner@kula.example`, `cashier@kula.example`,
`barista@kula.example` / `kiosk`) work too.

The seed is idempotent: re-running step 8 reports `updated`/`kept`. If you
change `seed/*.csv`, run it again; no module update is needed.

To stop the stack without losing anything, run `podman-compose down`; start it
again with `podman-compose up -d`.

### 2.2 devenv (Nix)

devenv supplies podman, podman-compose, python3, curl and the helper scripts
below. Nothing in §2.1 needs Nix; this path is for when you want the wrappers
and a pinned toolchain.

1. Install nix + devenv — <https://devenv.sh/getting-started/>.
2. From the repository root, enter the environment with `devenv shell`; the
   first run builds it, then drops you into a shell where `podman`,
   `podman-compose` and `python3` are on `PATH`.
3. Run the provisioning block from [§2.1](#21-podman-only-no-nix) inside that
   shell. It is idempotent. `init` is optional: it prepares `container-data/`
   + `addons/` (directories, `odoo.conf`, ownership), which the block also
   does, and it does not create the database or install apps. If you prefer
   the wrapper for the prep, run `init` before pasting the block.
4. Open <http://localhost:8069>. The helper scripts now work too:

| Script | Does |
|---|---|
| `init` | creates `container-data/` + `addons/`, seeds `odoo.conf` from the image, fixes ownership |
| `up` | `podman-compose up` (foreground) |
| `down` | `podman-compose down` |
| `logs` | `podman-compose logs -f --tail=200` |
| `psql` | `psql` into `development-odoo` |
| `seed` | runs `seed/seed.py` (dry run unless you pass `--apply`) |
| `mail` | prints the Mailpit URL; `mail --count` counts captured mails |

`devenv shell -- <cmd>` runs a single command in the environment and exits, e.g.
`devenv shell -- up`. With direnv installed, `.envrc` loads the environment
automatically on `cd` (run `direnv allow` once).

---

## 3. Seed the demo data

The quick start above already ran the seed. It writes nothing unless you pass
`--apply`.

```bash
python3 seed/seed.py --password admin                 # dry run: reports what it would do
python3 seed/seed.py --password admin --apply         # write
python3 seed/seed.py --password admin --purge --apply # take back what it created
```

Inside `devenv shell`, the `seed` helper runs the same script. The seed defaults
to `development-odoo` / `aryana@odoo.com`; pass `--db` and `--user` if yours
differ.

It is idempotent (natural keys: badge numbers, logins, names — re-running
reports `updated`, never duplicates) and talks to Odoo over XML-RPC on
`http://localhost:8069`.

What it writes is one small cafe — the scenario this repo is built for:

| File | What it seeds |
|---|---|
| `company.csv` | the trading name and address (the receipt header) |
| `employees.csv`, `users.csv` | owner, cashier and barista: an employee and a login each |
| `departments.csv` | the department they sit in, and who runs it |
| `menu.csv` | what the counter sells: POS category, price, description, temperature tag and best-seller star (including the add-ons) |
| `images/` | one picture per menu item and category — generated placeholders |
| `inventory.csv` | the pantry behind the menu: cost and quantity on hand |
| `sales.csv` | a day of takings: one shift, its orders, their times and payment |

The role groups, the `Counter` department and the Cashier/Barista job positions
are **module data** from `addons/kula_security`. The quick start installs it;
the seed also installs it if missing, but the full Kula UI additionally needs
`kula_workspace` and `kula_pos_layout`, which the quick start installs too.

Two Odoo rules bound what `--purge` can take back: a paid `pos.order` cannot be
deleted (so the day of takings, the menu it sold and the register stay), and a
`stock.quant` cannot be unlinked (so a pantry item is counted to zero and
archived, not deleted). The script prints what it kept and why.

---

## 4. Reset a broken stack

`podman-compose down` removes only the containers and network belonging to this
compose project. It does not touch other podman containers, images, or the
database files in `container-data/`.

```bash
# from the repository root
podman-compose down

# if podman-compose itself is wedged, remove just this stack's containers
podman rm -f lembayung_web_1 lembayung_db_1 lembayung_mail_1 2>/dev/null || true
podman network rm lembayung_default 2>/dev/null || true
```

The names use the compose project name, which defaults to the checkout directory
(`lembayung` here); `podman ps -a` shows yours if it differs. Do not use
`podman system prune` or `podman rm -a` for this: they remove unrelated
containers. Do not use `podman restart` on a compose container either; remove
and recreate it.

To go back to a truly clean clone, delete the runtime data too (this loses the
database and Odoo's data directory):

```bash
podman unshare rm -rf container-data
```

Then run [§2.1](#21-podman-only-no-nix) again (or §2.2 if you use devenv).

---

## 5. Notes & gotchas

- **Ports clash with `../odoo-compose`.** Both stacks publish `8069`, `8025`
  and `1025`; don't run them at the same time (or edit the published ports in
  `docker-compose.yaml`).
- **`container-data/` is disposable and owned by podman subuids**, so deleting
  it needs `podman unshare rm -rf container-data`, not plain `rm`. Re-run §2
  afterwards. `podman-compose down` only removes containers; the database stays
  in `container-data/odoo-db-data`.
- **Never `podman restart` a compose-managed container** — use
  `down` + `up`; restarting corrupts crun's state.
- **A new addon directory needs a full restart** — the addons path is scanned
  at process start.
- `devenv.lock` is generated on the first `devenv` command (it pins the exact
  nixpkgs revision).
- Container logs are UTC; a host shell in WIB is +07.
