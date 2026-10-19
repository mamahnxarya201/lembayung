# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Kiosk-only access, enforced before the backend page is ever built.

The rule is one sentence: a member of group_kiosk_only has no business in the
backend. This enforces it on the way in, so there is nothing to get around by
bookmarking a URL, disabling JavaScript, or asking the browser for a page by
hand -- which is what the client-side guard this replaces could not promise.

What is gated is the backend *shell* and nothing else. The register is its own
page (/pos/ui/<config>) and the calls it makes are /web/dataset/*, so both are
left alone; /web/login is also left alone, or nobody could sign in; and so is
the bare /scoped_app, which is not the backend but core's app-install page --
the one the register's own "Install App" entry opens, and the only way a tablet
gets the till as an app. A member is therefore free to work the till, to
install it, and has no way to open the backend around either.
"""
from odoo import models
from odoo.http import request

# The backend shell. Matched exactly for /web, so the many sub-trees that live
# under it (/web/assets, /web/dataset, /web/login) are untouched.
#
# /scoped_app is matched by *prefix* and never by its bare path, because the two
# are different pages: /scoped_app/<path> is the backend client served under a
# scoped app's own alias (web.controllers.home), while the bare /scoped_app is
# core's app-install page (web.controllers.webmanifest), which is public and
# shows an icon, a name and an Install button -- and which is exactly where the
# register's own "Install App" entry sends the operator
# (point_of_sale Navbar: `/scoped_app?app_id=point_of_sale&path=pos/ui/<id>`).
# Gating the bare path kept cashiers and baristas -- the people whose tablets
# the app is for -- from ever seeing that page: their tap landed on the register
# again, which is a second register on the same session, and a second register
# is a loop rather than a page (the register's own exit path is /odoo, so the
# gate bounces it back into a boot; kula_pos_layout's backend_exit.js is the
# other half of this fix). Nothing on the page is backend data, and a PWA
# installed from it still asks the server for every page it opens: a backend
# path anywhere in that URL is answered by this guard like any other request.
BACKEND_SHELL_PATHS = ("/web", "/odoo")


def _is_backend_shell(path):
    return (
        path in BACKEND_SHELL_PATHS
        or path.startswith("/odoo/")
        or path.startswith("/scoped_app/")
    )


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, endpoint):
        # `_pre_dispatch` cannot short-circuit (it returns None), so this is the
        # first hook that can answer a request with something other than the
        # endpoint's own response.
        kiosk_url = cls._kula_kiosk_only_redirect()
        if kiosk_url:
            return request.redirect(kiosk_url)
        return super()._dispatch(endpoint)

    @classmethod
    def _kula_kiosk_only_redirect(cls):
        """The register's URL for a kiosk-only caller, otherwise None."""
        request_path = request.httprequest.path
        if not _is_backend_shell(request_path):
            return None

        # The shell is served auth="none", so request.env.user is the public
        # user; the session is what says who is signed in. sudo() only reads a
        # group membership and picks the register, so it grants nothing.
        uid = request.session.uid
        if not uid:
            return None
        user = request.env["res.users"].sudo().browse(uid)
        if not user.has_group("kula_security.group_kiosk_only"):
            return None

        config = request.env["pos.config"].sudo().search([], limit=1)
        return f"/pos/ui/{config.id}" if config else None
