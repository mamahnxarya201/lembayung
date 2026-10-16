# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    "name": "KULA Workspace",
    "summary": "Left navigation sidebar and the KULA blue backend palette",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "license": "LGPL-3",
    "author": "KULA",
    # The Kiosk row opens the register, which is the whole point of the sidebar
    # here: POS must be installed for the row to go anywhere.
    "depends": ["point_of_sale"],
    "application": False,
    "installable": True,
    "auto_install": False,
    "assets": {
        "web.assets_backend": [
            # Templates are listed before the JS that renders them: the template
            # service must have registered the names before a component tries to
            # render. sidebar_state.js precedes sidebar.js for the same reason.
            "kula_workspace/static/src/sidebar/sidebar.xml",
            "kula_workspace/static/src/sidebar/sidebar_state.js",
            "kula_workspace/static/src/sidebar/sidebar.js",
            "kula_workspace/static/src/sidebar/sidebar.scss",
            # The stock Odoo chrome (control panel, buttons, inputs) and the
            # resource surfaces (kanbans, lists) wear the same palette; last so
            # they win ties against the others.
            # The top bar itself (blue 800, white on blue).
            "kula_workspace/static/src/theme/navbar.scss",
            # Chat and the Activities button, removed.
            "kula_workspace/static/src/theme/mail-ui.scss",
            "kula_workspace/static/src/theme/controls.scss",
            "kula_workspace/static/src/theme/surfaces.scss",
            "kula_workspace/static/src/theme/forms.scss",
        ],
        # The sign-in page: the same palette, in the bundle the login page loads
        # (the backend bundle never reaches it).
        "web.assets_frontend": [
            "kula_workspace/static/src/theme/login.scss",
        ],
    },
}
