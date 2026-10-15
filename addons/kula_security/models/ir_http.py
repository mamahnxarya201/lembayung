# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Kiosk-only access, enforced before the backend page is ever built.

The rule is one sentence: a member of group_kiosk_only has no business in the
backend. This enforces it on the way in, so there is nothing to get around by
bookmarking a URL, disabling JavaScript, or asking the browser for a page by
hand -- which is what the client-side guard this replaces could not promise.

What is gated is the backend *shell* and nothing else. The register is its own
page (/pos/ui/<config>) and the calls it makes are /web/dataset/*, so both are
left alone; /web/login is also left alone, or nobody could sign in. A member is
therefore free to work the till and has no way to open the backend around it.
"""
from odoo import models
from odoo.http import request

# The backend shell. Matched exactly for /web, so the many sub-trees that live
# under it (/web/assets, /web/dataset, /web/login) are untouched.
BACKEND_SHELL_PATHS = ("/web", "/odoo", "/scoped_app")


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
