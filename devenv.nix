{ pkgs, ... }:

# --------------------------------------------------------------------------- #
# lembayung -- Odoo 19 development environment, built with devenv (nix).
#
# This is the whole point of the folder: devenv supplies the toolchain
# (podman, podman-compose, python, psql client) so the stack runs the same way
# everywhere, and the helper scripts below are the one entry point.
#
# NOTE: nix + devenv are prerequisites and are deliberately NOT installed by
# this project. If `devenv` is not on your PATH, `devenv shell` cannot run;
# install nix first (https://devenv.sh/getting-started/) and then
#   $ devenv shell
# The container side (docker-compose.yaml + seed/) is plain podman-compose and
# does not depend on devenv at all -- the scripts here just wrap it.
# --------------------------------------------------------------------------- #

{
  # ------------------------------------------------------------------------ #
  # Toolchain                                                                 #
  # ------------------------------------------------------------------------ #
  packages = [
    pkgs.podman            # rootless container engine
    pkgs.podman-compose    # the `podman-compose` entry point
    pkgs.python3           # runs seed/seed.py (stdlib only, no pip installs)
    pkgs.jq                # reads the Mailpit API
    pkgs.curl
    pkgs.git
  ];

  # The container writes __pycache__ into the module tree; keep the host tidy.
  env.PYTHONDONTWRITEBYTECODE = "1";

  # ------------------------------------------------------------------------ #
  # Helper scripts -- available inside `devenv shell`.                        #
  #                                                                           #
  # The compose file bind-mounts ./container-data and ./addons, both of which #
  # must exist and be prepared before the stack can boot, so `init` is the    #
  # first thing to run (it is the devenv-native replacement for the sibling   #
  # repo's init.sh).                                                          #
  # ------------------------------------------------------------------------ #
  scripts = {
    init = {
      description = "Prepare ./container-data and ./addons (idempotent)";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"

        DATA_DIR=container-data
        COMPOSE_FILE=docker-compose.yaml
        # Must match the odoo user inside the image.
        ODOO_UID=100
        ODOO_GID=101

        command -v podman >/dev/null 2>&1 || { echo "init: podman not found in PATH" >&2; exit 1; }
        [ -f "$COMPOSE_FILE" ] || { echo "init: $COMPOSE_FILE not found" >&2; exit 1; }

        echo "==> creating $DATA_DIR tree"
        mkdir -p "$DATA_DIR/odoo-web-data" "$DATA_DIR/odoo-db-data" "$DATA_DIR/config" addons
        # odoo runs as uid 100, so these dirs must be traversable.
        chmod 0755 "$DATA_DIR" "$DATA_DIR/config" addons

        # /etc/odoo is bind-mounted from container-data/config, which MASKS the
        # odoo.conf baked into the image. Without it the entrypoint dies with
        # `configparser.NoSectionError: No section: 'options'`, so seed it from
        # the image. Image pin is read from the compose file, not duplicated.
        conf="$DATA_DIR/config/odoo.conf"
        if [ -s "$conf" ]; then
            echo "==> $conf already present, leaving it alone"
        else
            image=$(awk '
                /^[[:space:]]*image:/ { line=$0
                                        sub(/^[[:space:]]*image:[[:space:]]*/, "", line)
                                        gsub(/"/, "", line); print line; exit }
            ' "$COMPOSE_FILE")
            [ -n "$image" ] || { echo "init: could not determine the web image from $COMPOSE_FILE" >&2; exit 1; }
            echo "==> seeding $conf from $image (pulls the image if needed)"
            tmp=$(mktemp)
            trap 'rm -f "$tmp"' EXIT
            podman run --rm --entrypoint cat "$image" /etc/odoo/odoo.conf > "$tmp"
            [ -s "$tmp" ] || { echo "init: extracted odoo.conf is empty" >&2; exit 1; }
            mv -- "$tmp" "$conf"
            # mktemp is 0600 and mv preserves it; odoo (uid 100) must read it.
            chmod 0644 "$conf"
            trap - EXIT
        fi

        # A bind mount does NOT inherit image ownership; has to be chowned
        # inside the userns (uid 100/gid 101 are subuids, not host users).
        echo "==> chowning $DATA_DIR/odoo-web-data to $ODOO_UID:$ODOO_GID (in userns)"
        podman unshare chown -R "$ODOO_UID:$ODOO_GID" "$DATA_DIR/odoo-web-data"

        echo "==> ready -- run 'up' (podman-compose up) so you can watch the logs"
      '';
    };

    up = {
      description = "Start the stack in the foreground (watch the logs)";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"
        exec podman-compose up "$@"
      '';
    };

    down = {
      description = "Stop and remove the containers (also clears Mailpit)";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"
        exec podman-compose down "$@"
      '';
    };

    logs = {
      description = "Tail the container logs";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"
        exec podman-compose logs -f --tail=200 "$@"
      '';
    };

    psql = {
      description = "Open psql on the Odoo database (read-only recon)";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"
        exec podman-compose exec db psql -U "''${POSTGRES_USER:-admin}" -d "''${ODOO_DB:-development-odoo}" "$@"
      '';
    };

    seed = {
      description = "Seed the Suaraloka dataset -- dry run unless --apply";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"
        exec python3 seed/seed.py "$@"
      '';
    };

    mail = {
      description = "Open the Mailpit UI, or count captured emails with --count";
      exec = ''
        set -euo pipefail
        if [ "''${1:-}" = "--count" ]; then
            curl -s localhost:8025/api/v1/messages | jq '.total'
        else
            echo "Mailpit web UI: http://localhost:8025"
        fi
      '';
    };
  };

  # ------------------------------------------------------------------------ #
  # Shell banner                                                             #
  # ------------------------------------------------------------------------ #
  enterShell = ''
    echo
    echo "lembayung -- Odoo 19 dev environment"
    echo
    echo "  init   prepare container-data/ (run once, before the first 'up')"
    echo "  up     podman-compose up   (foreground; Ctrl-C stops)"
    echo "  down   podman-compose down"
    echo "  seed   python3 seed/seed.py --password admin [--apply]"
    echo "  psql   psql on development-odoo"
    echo "  mail   Mailpit at http://localhost:8025"
    echo
    echo "  Odoo: http://localhost:8069   Mailpit: http://localhost:8025"
    echo
  '';
}
