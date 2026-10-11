# lembayung

An [Odoo 19](https://www.odoo.com) development stack — Postgres + Odoo + a
Mailpit mail catcher — run with `podman-compose`, with the toolchain supplied by
[devenv](https://devenv.sh) (Nix).

```
docker-compose.yaml   the stack (Odoo 19, Postgres 18, Mailpit)
seed/                 the "Suaraloka" demo dataset (seed.py + CSVs)
devenv.nix/.yaml      the dev environment + helper scripts
.env                  compose variables (git-ignored)
```

| Service | URL | Notes |
|---|---|---|
| Odoo | http://localhost:8069 | admin `aryana@odoo.com` / `admin`, db `development-odoo` |
| Mailpit | http://localhost:8025 | catches every email Odoo sends (in-memory) |
| Postgres | internal only | user `admin` (see `.env`) |

Demo logins after seeding: `<first>.<last>@suaraloka.example` / `admin`
(66 of them). Company `Suaraloka`, Indonesia / IDR.

---

## 1. Prerequisites

- **podman** (rootless) with `podman-compose`
- **nix** + **devenv** — <https://devenv.sh/getting-started/>
- Rootless podman + SELinux: the compose file uses `:Z` on every bind mount, so
  no extra setup is needed.

> `nix`/`devenv` are **not** installed for you. If you already have
> `podman-compose` on the host and don't want Nix, skip to
> [§4 Running without devenv](#4-running-without-devenv).

---

## 2. Run it (devenv)

```bash
cd lembayung
devenv shell          # builds the environment on first run, then drops you in
init                  # prepare ./container-data and ./addons (once, idempotent)
up                    # podman-compose up -- foreground, watch the logs
```

Then open <http://localhost:8069>. Create a database if Odoo asks (name it
`development-odoo` to match the seed's default), or use the pre-created one.

To stop: `Ctrl-C` in the `up` shell, then

```bash
down                  # podman-compose down (also clears Mailpit's mailbox)
```

### Helper scripts (available inside `devenv shell`)

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

The seed writes nothing unless you pass `--apply`.

```bash
seed --password admin                 # dry run: reports what it would do
seed --password admin --apply         # write
seed --password admin --purge --apply # delete everything it created
```

It is idempotent (natural keys, re-running reports `updated`, never duplicates)
and talks to Odoo over XML-RPC on `http://localhost:8069`.

> **Heads-up:** the users' roles resolve to `suaraloka_security.group_*`, and
> the CPM demo network needs `suaraloka_cpm`. Neither module is in this folder,
> so `--apply` fails loudly on role resolution until you drop the module(s) into
> `./addons/`, e.g.:
>
> ```bash
> cp -r ../odoo-compose/addons/suaraloka_security addons/
> ```
>
> Without any addons the rest of the seed (company, departments, employees,
> lunch, …) is fine; only the login/role step needs the module.

---

## 4. Running without devenv

The stack itself is plain `podman-compose`; devenv only supplies the tools and
the `init`/`up`/`seed` wrappers. If `nix` is unavailable but you have
`podman-compose`, do the one-time prep by hand:

```bash
# 1. the two dirs the compose file bind-mounts
mkdir -p container-data/odoo-web-data container-data/odoo-db-data container-data/config addons

# 2. /etc/odoo is masked by the bind mount, so seed it from the image
podman run --rm --entrypoint cat docker.io/library/odoo:19.0 /etc/odoo/odoo.conf \
  > container-data/config/odoo.conf
chmod 0644 container-data/config/odoo.conf

# 3. a bind mount does not inherit image ownership (odoo runs as uid 100/gid 101)
podman unshare chown -R 100:101 container-data/odoo-web-data

# 4. run
podman-compose up
```

Everything else — URLs, seeding, `down` — is identical to §2/§3.

---

## 5. Notes & gotchas

- **Ports clash with `../odoo-compose`.** Both stacks publish `8069`, `8025`
  and `1025`; don't run them at the same time (or edit the published ports in
  `docker-compose.yaml`).
- **`container-data/` is disposable and owned by podman subuids**, so deleting
  it needs `podman unshare rm -rf container-data`, not plain `rm`. Re-run
  `init` afterwards.
- **Never `podman restart` a compose-managed container** — use
  `down` + `up`; restarting corrupts crun's state.
- **A new addon directory needs a full restart** — the addons path is scanned
  at process start.
- `devenv.lock` is generated on the first `devenv` command (it pins the exact
  nixpkgs revision).
- Container logs are UTC; a host shell in WIB is +07.
