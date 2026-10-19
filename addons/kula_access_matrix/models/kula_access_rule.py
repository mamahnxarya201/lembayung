# Part of the Odoo 19.0 Community series.
# Copyright 2026 KULA
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""The Access Matrix: every installed menu, and what one role may do in it.

The page (static/src/access_matrix/) is a table -- one row per installed menu,
one column per role, and a degree in every cell: no access, read only, or read &
write. The degree a cell shows is what the role has *today*, because that is the
question the table is asked: what a role may do is the sum of every access row
that applies to it -- the groups it implies (``base.group_user`` above all), the
ACLs the other apps declare (in this repository, the kiosk rights
``kula_security`` hands the POS roles), and this page's own rows. So a cell shows
the role's whole access, and carries the two parts it is made of: the floor
whatever else gives it (``floor``, which this page cannot take back) and what
this page adds on top (``level``, the rule).

This model is where the rules are kept: one per (menu, role) the matrix adds
something for. A rule is applied to Odoo rather than held beside it, in the two
places Odoo itself reads:

  * the role goes on (or comes off) ``ir.ui.menu.group_ids``, which is what
    decides whether the menu is offered to that role at all;
  * the model behind the menu's action gets an ``ir.model.access`` row for the
    role, carrying ``kula_managed``. That marker is how the matrix recognizes
    the rows it wrote -- it writes nothing else, ever. The perms each degree
    stands for are in LEVEL_PERMS: "read only" is read, "read & write" is read
    + write + create, and neither ever grants unlink, because deleting is not
    something a menu-level degree should hand out.

Two limits are real, and the page reports them instead of hiding them:

  * the matrix only adds, and it can only take back what it added. A rule is
    stored only when the degree is *above* the floor, so what the page owns is
    exactly its own additions, and setting a cell back down to its floor removes
    the rule again. What another group grants -- base.group_user's read on half
    of Odoo, or a module's own declared ACLs -- cannot be revoked from here, and
    revoking it by editing a module's CSV row would not survive the next `-u`
    anyway. Such a cell shows that degree and says where it comes from.
  * a page is only reachable when the menus above it are offered to the role
    too. Granting a page does not grant its parents, so a granted cell under a
    menu the role cannot reach is marked as still out of reach.
"""
from collections import defaultdict

from odoo import _, api, fields, models

# What each degree writes on the model behind the menu's action.
LEVEL_PERMS = {
    "read": {
        "perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False,
    },
    "write": {
        "perm_read": True, "perm_write": True, "perm_create": True, "perm_unlink": False,
    },
}
# Weakest first: how two degrees compare when several rules bear on one model.
LEVEL_RANK = {"none": 0, "read": 1, "write": 2}


class KulaAccessRule(models.Model):
    _name = "kula.access.rule"
    _description = "Access matrix rule: what one role may do in one menu"
    _order = "menu_id, group_id"

    _menu_group_unique = models.Constraint(
        "unique(menu_id, group_id)",
        "A role has one access level per menu.",
    )

    menu_id = fields.Many2one(
        "ir.ui.menu", "Menu", required=True, ondelete="cascade", index=True
    )
    group_id = fields.Many2one(
        "res.groups", "Role", required=True, ondelete="cascade", index=True
    )
    level = fields.Selection(
        [
            ("none", "No access"),
            ("read", "Read only"),
            ("write", "Read & write"),
        ],
        required=True,
        default="read",
    )

    # ------------------------------------------------------------------ #
    # What the page reads
    # ------------------------------------------------------------------ #
    # The roles the page opens with, by xmlid. Nothing of this module depends on
    # them: if the module that defines them is installed (in this repository,
    # kula_security and its shop roles) those are the columns it starts on, and
    # if it is not, the page opens with no column and the admin ticks one in the
    # header. The choice is remembered in the browser either way.
    DEFAULT_ROLE_XMLIDS = (
        "kula_security.group_cashier",
        "kula_security.group_barista",
        "kula_security.group_owner",
    )

    @api.model
    def kula_matrix_data(self, group_ids=None, domain=None):
        """Everything the page renders, in one round trip.

        The page is a table over every installed menu, so asking per row would
        be a request storm. A cell carries the degree this page grants for the
        (menu, role) pair, the floor under it -- what every other access row in
        the database already gives that role, which the page cannot take back --
        and ``blocked``, from the group gating on the menus above the row. The
        degree the page *shows* is the one the role has today, which is not the
        server's to decide: it depends on what is unsaved in the page.

        ``domain`` is the search bar's own: the rows are menus, so the page
        hands the standard search over `ir.ui.menu` straight to this method.
        """
        # Empty recordset: this is the model-level check, which is what the
        # page needs (and the model's own ACL is admin-only, so the page is one).
        self.check_access("read")
        groups = self._kula_matrix_groups(group_ids)
        implied = {group.id: set(group.all_implied_ids.ids) for group in groups}
        levels = defaultdict(dict)
        for rule in self.search([]):
            levels[rule.menu_id.id][rule.group_id.id] = rule.level
        external, matrix = self._kula_acl_levels()
        models_by_name = {model.model: model for model in self.env["ir.model"].sudo().search([])}

        menus = self.env["ir.ui.menu"].sudo().search(
            [("active", "=", True)], order="parent_path, sequence, id"
        )
        if domain:
            menus = self._kula_matching_branches(menus, domain)
        nodes, roots = {}, []
        for menu in menus:
            model = self._kula_action_model(menu, models_by_name)
            nodes[menu.id] = {
                "id": menu.id,
                "name": menu.name,
                "model": model.model if model else False,
                # A menu with no groups is offered to every user in Odoo. It is
                # carried along by the page so a cell can say so: the degree
                # then decides what the role may do with the records, not
                # whether the page appears.
                "open": not menu.group_ids,
                "_sequence": (menu.sequence, menu.id),
                "_gated": set(menu.group_ids.ids),
                "_model": model.id if model else False,
                "children": [],
            }
        for menu in menus:
            parent = nodes.get(menu.parent_id.id)
            (parent["children"] if parent else roots).append(nodes[menu.id])

        # Siblings in Odoo's own order. The parent_path walk above sorts the
        # tree by menu id, which would put Settings before Point of Sale and a
        # child above its parent whenever the parent's sequence is the larger
        # one; the page should read like the menu tree the admin knows.
        for node in nodes.values():
            node["children"].sort(key=lambda child: child["_sequence"])
        roots.sort(key=lambda node: node["_sequence"])

        def fill(node, unreachable):
            """Give a menu its cells, and hand its children what it closes off.

            A cell carries the degree this page grants for the pair (`level`),
            the floor under it (`floor`: what every other access row already
            gives the role -- the part this page cannot take back, and therefore
            the lowest degree the cell can be set to), and `blocked`.
            """
            gated = node.pop("_gated")
            model_id = node.pop("_model")
            node.pop("_sequence")
            node["cells"] = {}
            next_unreachable = {}
            for group in groups:
                here = implied[group.id]
                if model_id:
                    floor, _effective = self._kula_cell_grants(
                        external, matrix, model_id, group, here
                    )
                else:
                    # A menu that only groups pages has no model to grant on, so
                    # its degree *is* the page's visibility: "read" means the role
                    # is offered the group. An ungated menu is offered to
                    # everyone -- there is nothing to give it -- and a gated one
                    # is already there for a role another of its groups is on.
                    offered = not gated or bool(gated & (here - {group.id}))
                    floor = "read" if offered else "none"
                node["cells"][group.id] = {
                    "level": levels[node["id"]].get(group.id, False),
                    "floor": floor,
                    "blocked": unreachable[group.id],
                }
                next_unreachable[group.id] = unreachable[group.id] or bool(
                    gated and not gated & here
                )
            for child in node["children"]:
                fill(child, next_unreachable)

        for root in roots:
            fill(root, dict.fromkeys((group.id for group in groups), False))

        return {
            "groups": [{"id": group.id, "name": group.name} for group in groups],
            "candidates": self._kula_matrix_candidates(),
            "menus": roots,
        }

    @api.model
    def _kula_matching_branches(self, menus, domain):
        """The menus a search matched, and the branches they hang from.

        The path is kept on purpose: a match three levels down has no branch to
        hang from otherwise, and the page is a tree -- a row without its parents
        would be a lie about where the page lives. Matches on menus that are not
        in the table (an archived one, say) are dropped with everything else.
        """
        matched = self.env["ir.ui.menu"].sudo().search(domain)
        keep = set(matched.ids)
        for menu in matched:
            parent = menu.parent_id
            while parent and parent.id not in keep:
                keep.add(parent.id)
                parent = parent.parent_id
        return menus.filtered(lambda menu: menu.id in keep)

    @api.model
    def _kula_matrix_groups(self, group_ids=None):
        """The roles to show as columns: those asked for, or this shop's own.

        ``None`` and ``False`` both mean "nothing was chosen" -- a JSON null
        arrives as ``False`` over RPC -- while an empty list is a real answer:
        the admin removed every column and the page shows no role at all.
        """
        Groups = self.env["res.groups"].sudo()
        if group_ids is None or group_ids is False:
            groups = Groups.browse([])
            for xmlid in self.DEFAULT_ROLE_XMLIDS:
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if group:
                    groups |= group
            return groups
        return Groups.browse([int(group_id) for group_id in group_ids]).exists()

    @api.model
    def _kula_matrix_candidates(self):
        """The roles the page can add as a column: every real group in Odoo."""
        groups = self.env["res.groups"].sudo().search(
            [("share", "=", False)], order="privilege_id, name"
        )
        return [
            {
                "id": group.id,
                "name": group.name,
                "privilege": group.privilege_id.name or "",
            }
            for group in groups
        ]

    @api.model
    def _kula_action_model(self, menu, models_by_name=None):
        """The model behind a menu's action, when it opens a page of its own.

        ``models_by_name`` is the whole `ir.model` table, when the caller
        already has it: the page needs the model of a few hundred menus and one
        lookup each would be a few hundred searches.
        """
        action = menu.action
        if not action or action._name != "ir.actions.act_window":
            return None
        if models_by_name is not None:
            return models_by_name.get(action.res_model)
        return self.env["ir.model"].sudo().search([("model", "=", action.res_model)], limit=1)

    @api.model
    def _kula_acl_levels(self):
        """What every (model, role) can do today, split by who wrote the row.

        Read once for the whole page rather than per cell. ``external`` is
        everything Odoo itself and the other modules declare -- the floor a role
        stands on whatever this page says, and the part the matrix cannot take
        back. ``matrix`` is what the Access Matrix wrote (its rows carry
        `kula_managed`), the only part it can. A row with no group is filed under
        ``False``: those apply to everyone, so they count for every role.
        """
        external, matrix = defaultdict(dict), defaultdict(dict)
        for access in self.env["ir.model.access"].sudo().search([]):
            if access.perm_write or access.perm_create or access.perm_unlink:
                level = "write"
            elif access.perm_read:
                level = "read"
            else:
                continue
            where = matrix if access.kula_managed else external
            model, group = access.model_id.id, access.group_id.id
            if LEVEL_RANK[level] > LEVEL_RANK[where[model].get(group, "none")]:
                where[model][group] = level
        return external, matrix

    @api.model
    def _kula_strongest(self, levels, model_id, group_ids):
        """The strongest degree any of these roles has on this model, by these rows."""
        level = "none"
        for group_id in list(group_ids) + [False]:
            current = levels.get(model_id, {}).get(group_id, "none")
            if LEVEL_RANK[current] > LEVEL_RANK[level]:
                level = current
        return level

    @api.model
    def _kula_cell_grants(self, external, matrix, model_id, group, implied):
        """A cell's floor and its effective degree, for one (menu, role).

        The floor is what the role is given from anywhere *but* this page's own
        row for this role: everything Odoo and the other modules declare for the
        role or for any group it implies, plus what the matrix itself granted to
        one of those implied groups (that grant is real for this role, and it can
        only be changed on the implied group's own column). The effective degree
        is the role's whole access today -- the floor, and this page's own row.
        """
        if not model_id:
            return "none", "none"
        floor = self._kula_strongest(external, model_id, implied)
        inherited = self._kula_strongest(matrix, model_id, set(implied) - {group.id})
        if LEVEL_RANK[inherited] > LEVEL_RANK[floor]:
            floor = inherited
        own = self._kula_strongest(matrix, model_id, {group.id})
        return floor, (own if LEVEL_RANK[own] > LEVEL_RANK[floor] else floor)

    @api.model
    def _kula_floor_for(self, external, matrix, menu, group):
        """What a role already has on a menu's model from any other source."""
        model = self._kula_action_model(menu)
        if not model:
            return "none"
        return self._kula_cell_grants(
            external, matrix, model.id, group, set(group.all_implied_ids.ids)
        )[0]

    # ------------------------------------------------------------------ #
    # What the page writes
    # ------------------------------------------------------------------ #
    @api.model
    def kula_apply_matrix(self, changes):
        """Save the cells the page changed, and make Odoo match them.

        A change is ``{"menu_id", "group_id", "level"}``, where the level is the
        degree the page showed -- the role's *actual* access after the change.
        Two consequences, both on purpose:

        * a degree the role already has from somewhere else stores no rule at
          all. The matrix only adds, so a rule for what another group grants
          would grant nothing and only clutter what it owns;
        * "none" -- or any degree at or below that floor -- removes the rule,
          which is how the matrix takes back its own grant: the sync below then
          takes the role back off the menu and drops the access row it wrote.
        """
        self.check_access("write")
        rules = self.env["kula.access.rule"]
        roles = self.env["res.groups"]
        external, matrix = self._kula_acl_levels()
        for change in changes:
            level = change.get("level") or "none"
            if level not in LEVEL_RANK:
                raise ValueError(f"Unknown access level: {level!r}")
            menu = self.env["ir.ui.menu"].browse(int(change["menu_id"])).exists()
            group = self.env["res.groups"].browse(int(change["group_id"])).exists()
            if not menu or not group:
                continue
            if level != "none" and LEVEL_RANK[level] <= LEVEL_RANK[
                self._kula_floor_for(external, matrix, menu, group)
            ]:
                level = "none"
            if level == "write" and not self._kula_action_model(menu):
                # A menu that only groups pages has no records to write: the
                # degree is the page's visibility, and "read" is all of it.
                level = "read"
            rule = rules.search(
                [("menu_id", "=", menu.id), ("group_id", "=", group.id)], limit=1
            )
            if level == "none":
                rule.unlink()
            elif rule:
                rule.level = level
            else:
                rules.create({"menu_id": menu.id, "group_id": group.id, "level": level})
            roles |= group
        return {
            "cells": len(changes),
            "rules": rules.search_count([]),
            "roles": len(roles),
            "access": self.env["ir.model.access"].sudo().search_count(
                [("kula_managed", "=", True)]
            ),
        }

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        self.env["kula.access.rule"]._kula_resync(rules._kula_pairs())
        return rules

    def write(self, vals):
        # The pairs from *before* the write matter as much as the ones after
        # it: a rule moved to another role has to come off the role it left.
        pairs = self._kula_pairs()
        result = super().write(vals)
        self.env["kula.access.rule"]._kula_resync(pairs + self._kula_pairs())
        return result

    def unlink(self):
        # The rules are gone once they are unlinked, so the sync works from the
        # model rather than from a recordset that no longer exists.
        pairs = self._kula_pairs()
        result = super().unlink()
        self.env["kula.access.rule"]._kula_resync(pairs)
        return result

    def _kula_pairs(self):
        """The (menu, role) cells these rules stand for."""
        return [(rule.menu_id, rule.group_id) for rule in self if rule.menu_id and rule.group_id]

    def _kula_resync(self, pairs):
        """Make Odoo's own records match the rules for these (menu, role) pairs."""
        for menu, group in pairs:
            granted = bool(
                self.search_count([("menu_id", "=", menu.id), ("group_id", "=", group.id)])
            )
            self._kula_sync_menu(menu, group, granted)
            self._kula_sync_access(menu, group)

    def _kula_sync_menu(self, menu, group, granted):
        """Offer the menu to the role, or stop offering it.

        A menu with no groups is offered to everyone already, so putting a role
        on it would change nothing except to *gate* the page for everybody else
        -- an unrelated user would lose a page nobody asked to restrict. An
        ungated menu is therefore left exactly as it is, and the page says so
        (the ``open`` flag) instead of pretending the degree hid it.
        """
        gated = menu.group_ids
        if granted:
            if gated and group not in gated:
                menu.group_ids = gated | group
        elif group in gated:
            menu.group_ids = gated - group

    def _kula_sync_access(self, menu, group):
        """Write the access row for the model behind this menu, for this role."""
        model = self._kula_action_model(menu)
        if not model:
            return
        access = self.env["ir.model.access"].sudo()
        owned = access.search(
            [
                ("model_id", "=", model.id),
                ("group_id", "=", group.id),
                ("kula_managed", "=", True),
            ]
        )
        level = self._kula_level_for_model(group, model)
        if level == "none":
            owned.unlink()
            return
        if owned:
            # One row per (model, role): a second menu opening the same model
            # must not add a second row, it raises the level of this one.
            owned.write(LEVEL_PERMS[level])
            if len(owned) > 1:
                owned[1:].unlink()
        else:
            access.create(
                {
                    "name": _("access matrix: %(model)s for %(role)s",
                              model=model.model, role=group.name),
                    "model_id": model.id,
                    "group_id": group.id,
                    "kula_managed": True,
                    **LEVEL_PERMS[level],
                }
            )

    def _kula_level_for_model(self, group, model):
        """The strongest degree this role's rules ask for on this model."""
        level = "none"
        for rule in self.search([("group_id", "=", group.id)]):
            action = rule.menu_id.action
            if not action or action._name != "ir.actions.act_window":
                continue
            if action.res_model != model.model:
                continue
            if LEVEL_RANK[rule.level] > LEVEL_RANK[level]:
                level = rule.level
        return level
