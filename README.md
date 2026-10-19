# lembayung

An [Odoo 19](https://www.odoo.com) development stack — Postgres + Odoo + a
Mailpit mail catcher — run with `podman-compose`. A devenv (Nix) toolchain and
helper scripts are included, but the stack and the quick start do not need Nix.

```
docker-compose.yaml   the stack (Odoo 19, Postgres 18, Mailpit)
seed/                 the "Kula" demo dataset (seed.py + CSVs)
devenv.nix/.yaml      the optional dev environment + helper scripts
.env.example          compose + seed variables (copy to .env)
```

| Service | URL | Notes |
|---|---|---|
| Odoo | http://localhost:8069 | admin `admin` / `admin`, db `development-odoo` |
| Mailpit | http://localhost:8025 | catches every email Odoo sends (in-memory) |
| Postgres | internal only | user `admin` (see `.env`) |

> In an Amp orb this stack is pre-provisioned and its admin login is
> `aryana@odoo.com` / `admin`; a clean local clone uses the plain `admin`.

Demo logins after seeding: `owner@kula.example`, `cashier@kula.example`,
`barista@kula.example` / `kiosk`. Company `Kula`, Indonesia / IDR.

---

## 1. Prerequisites

- **podman** (rootless) with `podman-compose`
- **python3** (runs `seed/seed.py`; standard library only)
- Optional: **curl** (to poll Odoo yourself), **nix** + **devenv**
  (<https://devenv.sh/getting-started/>) for the §2.2 path and its helpers.

Rootless podman + SELinux needs nothing extra: the compose file uses `:Z` on
every bind mount.

---

## 2. Run it from a clean clone

Two paths, same three commands. The stack provisions itself on its first start:
the web container fixes the data-dir ownership, creates `development-odoo`
without demo data, and installs the Odoo apps. The seed then reads `.env`, waits
for Odoo, localizes the company to Indonesia/IDR, and writes the Kula demo.

```bash
cp .env.example .env       # admin/admin locally; edit the ODOO_* block if you like
podman-compose up -d       # first boot installs the apps; takes a few minutes
python3 seed/seed.py --apply
```

- Watch the first install with `podman-compose logs -f web`, if you like.
- The seed is idempotent: re-run it after editing `seed/*.csv`; it reports
  `updated` / `kept`.
- The seed takes its defaults from `.env`: `ODOO_DB`, `ODOO_URL`, `ODOO_USER`,
  `ODOO_PASSWORD`. Pass `--db` / `--user` / `--password` to override.

Open <http://localhost:8069>: `admin` / `admin`, or the demo logins
`owner@kula.example`, `cashier@kula.example`, `barista@kula.example` / `kiosk`.

Stop and start without losing anything: `podman-compose down`, then
`podman-compose up -d`.

### 2.1 Podman only (no Nix)

Use the three commands above. Nothing else is needed on a clean clone. If a
previous attempt left a broken stack, run `podman-compose down` first
([§4](#4-reset-a-broken-stack)); it removes only this stack's containers.

### 2.2 devenv (Nix)

devenv supplies podman, podman-compose, python3, curl and the helper scripts
below. Nothing in §2.1 needs Nix.

1. Install nix + devenv — <https://devenv.sh/getting-started/>.
2. From the repository root, enter the environment with `devenv shell`; the
   first run builds it, then drops you into a shell where `podman`,
   `podman-compose` and `python3` are on `PATH`.
3. Run the same three commands from [§2.1](#21-podman-only-no-nix) inside that
   shell. `init` is optional: it only creates `container-data/` + `addons/`,
   which `podman-compose up` does anyway.
4. Open <http://localhost:8069>. The helper scripts now work too:

| Script | Does |
|---|---|
| `init` | creates `container-data/` + `addons/` (optional) |
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
`--apply`:

```bash
python3 seed/seed.py                 # dry run: reports what it would do
python3 seed/seed.py --apply         # write
python3 seed/seed.py --purge --apply # take back what it created
```

Inside `devenv shell`, the `seed` helper runs the same script. Credentials come
from `.env`; the flags override it.

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
are **module data** from `addons/kula_security`. The stack installs all four
repository apps on first start; the seed also installs `kula_security` if it is
missing, and sets the company's country and whole-rupiah IDR itself for
databases the stack created without localizing.

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
database and Odoo's data directory; the next `up` recreates the database and
the apps, and you re-run the seed):

```bash
podman unshare rm -rf container-data
```

Then run §2 again.

---

## 5. Notes & gotchas

- **Ports clash with `../odoo-compose`.** Both stacks publish `8069`, `8025`
  and `1025`; don't run them at the same time (or edit the published ports in
  `docker-compose.yaml`).
- **`container-data/` is disposable and owned by podman subuids**, so deleting
  it needs `podman unshare rm -rf container-data`, not plain `rm`. It holds the
  Postgres data (`odoo-db-data`) and Odoo's data directory (`odoo-web-data`);
  `podman-compose down` leaves both in place.
- **The web container starts as root once**, chowns `container-data/odoo-web-data`
  and drops to the `odoo` user (`setpriv`). That is why CLI work runs as
  `podman-compose exec -T -u 100 web ...`.
- **Module changes need `-u` and a restart.** `-i` on an already installed
  module is a silent no-op, and a new addon *directory* also needs a full
  restart because the addons path is scanned at process start. Example (the
  password is the one in `.env`):
  ```bash
  podman-compose exec -T -u 100 web odoo -u <module> -d development-odoo \
    --without-demo=True --stop-after-init --no-http \
    --db_host=db --db_user=admin --db_password=admin
  podman-compose down && podman-compose up -d
  ```
- **Never `podman restart` a compose-managed container** — use `down` + `up`;
  restarting corrupts crun's state.
- **`.env` is shared:** `POSTGRES_*` feeds the containers, `ODOO_*` feeds the
  seed. If `container-data/odoo-db-data` was initialized with a different
  Postgres password, keep that password in `.env` or remove `container-data`
  (destructive) and start again; it only applies at first initialization.
- **An existing database keeps its admin login.** If you set it up with the old
  walkthrough (which renamed the admin to `aryana@odoo.com`), put
  `ODOO_USER=aryana@odoo.com` in `.env` or pass `--user`.
- **The image's own `/etc/odoo/odoo.conf` is used now.** The old
  `container-data/config` directory, if you still have one, is ignored.
- `devenv.lock` is generated on the first `devenv` command (it pins the exact
  nixpkgs revision).
- Container logs are UTC; a host shell in WIB is +07.
