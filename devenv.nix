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
      description = "Prepare ./container-data and ./addons (idempotent, optional)";
      exec = ''
        set -euo pipefail
        cd "''${DEVENV_ROOT:-.}"

        command -v podman >/dev/null 2>&1 || { echo "init: podman not found in PATH" >&2; exit 1; }
        [ -f docker-compose.yaml ] || { echo "init: docker-compose.yaml not found" >&2; exit 1; }

        # The compose file bind-mounts these two; the containers do the rest:
        # the web service chowns /var/lib/odoo and creates the database on its
        # first start, so there is no config to seed and no host-side chown.
        echo "==> creating container-data/ tree"
        mkdir -p container-data/odoo-web-data container-data/odoo-db-data addons
        chmod 0755 container-data addons

        echo "==> ready -- run 'podman-compose up -d', then 'python3 seed/seed.py --apply'"
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
      description = "Seed the Kula dataset -- dry run unless --apply";
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
    echo "  init   prepare container-data/ (optional; the stack does it too)"
    echo "  up     podman-compose up -d  (then: python3 seed/seed.py --apply)"
    echo "  down   podman-compose down"
    echo "  seed   python3 seed/seed.py [--apply]  (reads .env: ODOO_*)"
    echo "  psql   psql on development-odoo"
    echo "  mail   Mailpit at http://localhost:8025"
    echo
    echo "  Odoo: http://localhost:8069   Mailpit: http://localhost:8025"
    echo
  '';
}
