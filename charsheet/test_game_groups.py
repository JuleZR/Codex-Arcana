from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal

from charsheet.game_groups import (
    accept_invitation,
    add_game_master,
    archive_group,
    create_group,
    create_invitation,
    delete_group,
    end_membership,
    GroupError,
    require_game_master,
    require_sl_character_access,
    rename_group,
    revoke_game_master,
    transfer_leadership,
)
from charsheet.item_transfers import (
    TransferError,
    accept_transfer,
    create_gm_edit_transfer,
    create_group_transfer,
)
from charsheet.templatetags.card_markdown import (
    compact_number_de,
    compact_number_fraction_de,
    compact_number_integer_de,
    standard_markdown,
)
from charsheet.models import (
    Character,
    CharacterCreature,
    CharacterItem,
    Creature,
    GameGroup,
    GameGroupCreature,
    GameGroupInvitation,
    GameGroupMembership,
    GameGroupRole,
    GameGroupTable,
    GameGroupTableCell,
    Item,
    ItemTransfer,
    Quality,
    Race,
)


class GameGroupTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.leader = user_model.objects.create_user(username="leader", password="secret")
        self.gm = user_model.objects.create_user(username="gm", password="secret")
        self.player = user_model.objects.create_user(username="player", password="secret")
        self.other = user_model.objects.create_user(username="other", password="secret")
        self.race = Race.objects.create(name="Gruppentest-Volk")
        self.character = Character.objects.create(owner=self.player, name="Ari", race=self.race)
        self.other_character = Character.objects.create(owner=self.other, name="Bea", race=self.race)
        self.group = create_group(creator=self.leader, name="Die Runde")
        self.membership = GameGroupMembership.objects.create(group=self.group, character=self.character)
        self.definition = Item.objects.create(
            name="Gruppentest-Trank",
            price=10,
            item_type=Item.ItemType.CONSUM,
            stackable=True,
        )

    def group_item(self, **overrides):
        values = {
            "item": self.definition,
            "group_owner": self.group,
            "original_owner_group": self.group,
            "amount": 1,
        }
        values.update(overrides)
        return CharacterItem.objects.create(**values)

    def test_group_table_numbers_use_compact_decimal_comma_parts(self):
        self.assertEqual(compact_number_de(Decimal("0.0000")), "0")
        self.assertEqual(compact_number_de(Decimal("-4.0000")), "-4")
        self.assertEqual(compact_number_de(Decimal("12.5000")), "12,5")
        self.assertEqual(compact_number_integer_de(Decimal("-12.5000")), "-12")
        self.assertEqual(compact_number_fraction_de(Decimal("-12.5000")), "5")
        self.assertEqual(compact_number_fraction_de(Decimal("-12.0000")), "")

    def test_table_markdown_requires_period_for_ordered_lists(self):
        self.assertIn("<ol start=\"2\">", standard_markdown("2. Zusatzaktionen"))
        self.assertEqual(
            standard_markdown("2 Zusatzaktionen"),
            "<p>2 Zusatzaktionen</p>\n",
        )
        self.assertEqual(
            standard_markdown("2) Zusatzaktionen"),
            "<p>2) Zusatzaktionen</p>\n",
        )

    def test_group_table_creation_uses_default_dimensions(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Neue Tabelle"},
        )

        self.assertEqual(response.status_code, 302)
        data_table = GameGroupTable.objects.get(group=self.group)
        self.assertEqual(data_table.creator, self.leader)
        self.assertFalse(data_table.is_shared)
        self.assertEqual(data_table.columns.count(), 3)
        self.assertEqual(data_table.rows.count(), 3)
        self.assertEqual(
            GameGroupTableCell.objects.filter(row__table=data_table).count(),
            9,
        )
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_hidden_table_picker_marks_shared_and_private_tables(self):
        self.client.force_login(self.leader)
        for title in ("Private Übersicht", "Geteilte Übersicht"):
            self.client.post(
                reverse("create_group_table", args=[self.group.id]),
                {"title": title},
            )
        GameGroupTable.objects.filter(
            group=self.group,
            title="Private Übersicht",
        ).update(is_visible=False, is_shared=False)
        GameGroupTable.objects.filter(
            group=self.group,
            title="Geteilte Übersicht",
        ).update(is_visible=False, is_shared=True)

        screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )

        self.assertEqual(
            [
                data_table.title
                for data_table in screen.context["hidden_data_tables"]
            ],
            ["Geteilte Übersicht", "Private Übersicht"],
        )
        self.assertContains(screen, "Private Übersicht")
        self.assertContains(screen, "Geteilte Übersicht")
        self.assertContains(
            screen,
            'data-table-sharing-state="private"',
            count=1,
        )
        self.assertContains(
            screen,
            'data-table-sharing-state="shared"',
            count=1,
        )
        self.assertContains(screen, "Freigegeben")
        self.assertContains(screen, "Privat")

    def test_game_master_can_replace_table_from_clipboard_markdown(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Armverletzungen"},
        )
        data_table = GameGroupTable.objects.get(group=self.group)
        old_column_ids = set(data_table.columns.values_list("id", flat=True))
        old_row_ids = set(data_table.rows.values_list("id", flat=True))
        markdown_table = """
```markdown
| Schaden auf einmal          | Auswirkung                                                                       |
| --------------------------- | -------------------------------------------------------------------------------- |
| Mindestens 1 × Konstitution | Arm für eine Anzahl Runden in Höhe des Schadens betäubt und nutzlos              |
| Mindestens 2 × Konstitution | Getragene Gegenstände fallen zu Boden; Arm bleibt bis zur Behandlung verkrüppelt |
| Mindestens 3 × Konstitution | Arm zerstört oder abgetrennt; Blutverlust von 1 LP pro Runde                     |
```
"""

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "_sl_screen": "1",
                "_sl_anchor": "sl-tabellen",
                "_edit_table_id": data_table.id,
                "_table_action": "import_markdown",
                "title": data_table.title,
                "markdown_table": markdown_table,
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('game_master_screen', args=[self.group.id])}"
            f"?edit_table={data_table.id}#sl-tabellen",
        )
        data_table.refresh_from_db()
        columns = list(data_table.columns.all())
        rows = list(data_table.rows.all())
        self.assertEqual(data_table.title, "Armverletzungen")
        self.assertEqual(
            [column.heading for column in columns],
            ["Schaden auf einmal", "Auswirkung"],
        )
        self.assertEqual(len(rows), 3)
        self.assertTrue(old_column_ids.isdisjoint(column.id for column in columns))
        self.assertTrue(old_row_ids.isdisjoint(row.id for row in rows))
        self.assertEqual(
            [
                [
                    GameGroupTableCell.objects.get(
                        row=row,
                        column=column,
                    ).text_value
                    for column in columns
                ]
                for row in rows
            ],
            [
                [
                    "Mindestens 1 × Konstitution",
                    "Arm für eine Anzahl Runden in Höhe des Schadens betäubt und nutzlos",
                ],
                [
                    "Mindestens 2 × Konstitution",
                    "Getragene Gegenstände fallen zu Boden; Arm bleibt bis zur Behandlung verkrüppelt",
                ],
                [
                    "Mindestens 3 × Konstitution",
                    "Arm zerstört oder abgetrennt; Blutverlust von 1 LP pro Runde",
                ],
            ],
        )

    def test_invalid_clipboard_markdown_keeps_existing_table_structure(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Bleibt erhalten"},
        )
        data_table = GameGroupTable.objects.get(group=self.group)
        old_column_ids = list(data_table.columns.values_list("id", flat=True))
        old_row_ids = list(data_table.rows.values_list("id", flat=True))

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "_sl_screen": "1",
                "_sl_anchor": "sl-tabellen",
                "_edit_table_id": data_table.id,
                "_table_action": "import_markdown",
                "title": data_table.title,
                "markdown_table": "| Keine | gültige Tabelle |",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(data_table.columns.values_list("id", flat=True)),
            old_column_ids,
        )
        self.assertEqual(
            list(data_table.rows.values_list("id", flat=True)),
            old_row_ids,
        )
        self.assertIn(
            "keine vollständige Markdown-Tabelle",
            " ".join(str(message) for message in get_messages(response.wsgi_request)),
        )

    def test_game_master_can_reorder_visible_group_tables(self):
        first = GameGroupTable.objects.create(
            group=self.group,
            title="Erste",
            position=0,
        )
        hidden = GameGroupTable.objects.create(
            group=self.group,
            title="Verdeckt",
            position=1,
            is_visible=False,
        )
        third = GameGroupTable.objects.create(
            group=self.group,
            title="Dritte",
            position=2,
        )
        self.client.force_login(self.leader)

        response = self.client.post(
            reverse("reorder_group_tables", args=[self.group.id]),
            {
                "ordered_ids": [
                    f"table:{third.id}",
                    "note",
                    f"table:{first.id}",
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True})
        self.assertEqual(
            list(
                self.group.data_tables.order_by("position", "id").values_list(
                    "id",
                    flat=True,
                )
            ),
            [third.id, hidden.id, first.id],
        )
        self.group.refresh_from_db()
        self.assertEqual(self.group.screen_note_position, 2)

    def test_game_master_can_reorder_tables_while_note_is_hidden(self):
        first = GameGroupTable.objects.create(
            group=self.group,
            title="Erste",
            position=0,
        )
        second = GameGroupTable.objects.create(
            group=self.group,
            title="Zweite",
            position=1,
        )
        self.group.screen_note_is_visible = False
        self.group.save(update_fields=["screen_note_is_visible"])
        self.client.force_login(self.leader)

        response = self.client.post(
            reverse("reorder_group_tables", args=[self.group.id]),
            {
                "ordered_ids": [
                    f"table:{second.id}",
                    f"table:{first.id}",
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True})
        self.assertEqual(
            list(
                self.group.data_tables.order_by("position", "id").values_list(
                    "id",
                    flat=True,
                )
            ),
            [second.id, first.id],
        )

    def test_game_master_can_hide_and_show_group_note(self):
        self.client.force_login(self.leader)
        screen_url = reverse("game_master_screen", args=[self.group.id])

        response = self.client.post(
            reverse("hide_group_note", args=[self.group.id]),
        )

        self.assertRedirects(
            response,
            f"{screen_url}#sl-tabellen",
        )
        self.group.refresh_from_db()
        self.assertFalse(self.group.screen_note_is_visible)
        screen = self.client.get(screen_url)
        self.assertEqual(screen.context["hidden_screen_item_count"], 1)
        self.assertNotContains(screen, "data-note-editor")
        self.assertContains(
            screen,
            reverse("show_group_note", args=[self.group.id]),
        )

        response = self.client.post(
            reverse("show_group_note", args=[self.group.id]),
        )

        self.assertRedirects(
            response,
            f"{screen_url}#sl-tabellen",
        )
        self.group.refresh_from_db()
        self.assertTrue(self.group.screen_note_is_visible)

    def test_game_master_can_edit_rich_text_group_note(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("update_group_note", args=[self.group.id]),
            {
                "note_html": (
                    "<h2>Plan</h2><p><strong>Wichtig</strong>"
                    '<img src="x" onerror="alert(1)"></p>'
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(
            self.group.screen_note_html,
            "<h2>Plan</h2><p><strong>Wichtig</strong></p>",
        )
        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(screen, 'data-note-editor')
        self.assertContains(screen, "<h2>Plan</h2>", html=True)
        self.assertNotContains(screen, "onerror")

    def test_game_master_can_resize_and_detach_group_note(self):
        self.group.screen_note_html = "<p>Bleibt erhalten</p>"
        self.group.save(update_fields=["screen_note_html"])
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("update_group_note", args=[self.group.id]),
            {
                "note_is_wide": "1",
                "note_is_detached": "1",
                "note_x": "-15",
                "note_y": "12000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.group.refresh_from_db()
        self.assertTrue(self.group.screen_note_is_wide)
        self.assertTrue(self.group.screen_note_is_detached)
        self.assertEqual(self.group.screen_note_x, 0)
        self.assertEqual(self.group.screen_note_y, 10000)
        self.assertEqual(self.group.screen_note_html, "<p>Bleibt erhalten</p>")
        self.assertEqual(response.json()["is_wide"], True)
        self.assertEqual(response.json()["is_detached"], True)

        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(screen, "gm-note-card--wide")
        self.assertContains(screen, "gm-note-card--detached")
        self.assertContains(screen, "data-note-width-toggle")
        self.assertContains(screen, "data-note-detach-toggle")

    def test_game_master_can_reorder_character_cards(self):
        second_membership = GameGroupMembership.objects.create(
            group=self.group,
            character=self.other_character,
        )
        self.client.force_login(self.leader)

        response = self.client.post(
            reverse("reorder_group_memberships", args=[self.group.id]),
            {"ordered_ids": [second_membership.id, self.membership.id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True})
        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertEqual(
            [row["membership"].id for row in screen.context["roster"]],
            [second_membership.id, self.membership.id],
        )
        state_response = self.client.get(
            reverse("group_inventory_transfer_state", args=[self.group.id])
        )
        self.assertEqual(state_response.status_code, 200)
        self.assertEqual(
            state_response.json()["signature"],
            screen.context["sl_inventory_groups"][0]["screen_state_signature"],
        )

    def test_game_master_can_collapse_and_restore_character_card(self):
        self.client.force_login(self.leader)
        state_url = reverse(
            "set_group_membership_screen_state",
            args=[self.group.id, self.membership.id],
        )

        response = self.client.post(state_url, {"is_collapsed": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "membership_id": self.membership.id,
                "is_collapsed": True,
            },
        )
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.screen_is_collapsed)
        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertTrue(screen.context["has_collapsed_roster"])
        self.assertContains(screen, "data-collapsed-roster")
        self.assertContains(
            screen,
            f'data-collapsed-card-id="character:{self.membership.id}"',
        )

        response = self.client.post(state_url, {"is_collapsed": "0"})

        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.screen_is_collapsed)

    def test_game_master_can_collapse_and_restore_inventory(self):
        self.client.force_login(self.leader)
        state_url = reverse(
            "set_group_inventory_screen_state",
            args=[self.group.id],
        )

        response = self.client.post(state_url, {"is_collapsed": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "is_collapsed": True,
            },
        )
        self.group.refresh_from_db()
        self.assertTrue(self.group.screen_inventory_is_collapsed)
        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(
            screen,
            'class="gm-workspace is-inventory-collapsed"',
        )
        self.assertContains(screen, 'aria-expanded="false"')
        self.assertContains(screen, "Inventar ausklappen")

        response = self.client.post(state_url, {"is_collapsed": "0"})

        self.assertEqual(response.status_code, 200)
        self.group.refresh_from_db()
        self.assertFalse(self.group.screen_inventory_is_collapsed)

    def test_game_master_can_add_duplicate_creature_cards_and_manage_them_independently(self):
        creature = Creature.objects.create(
            name="Testwolf",
            slug="testwolf",
            combat_speed=8,
            march_speed=16,
            sprint_speed=32,
        )
        self.client.force_login(self.leader)
        add_url = reverse("add_group_creature", args=[self.group.id])

        first_response = self.client.post(add_url, {"creature_id": creature.id})
        second_response = self.client.post(add_url, {"creature_id": creature.id})

        self.assertRedirects(
            first_response,
            f"{reverse('game_master_screen', args=[self.group.id])}#sl-charaktere",
        )
        self.assertEqual(second_response.status_code, 302)
        creature_cards = list(
            GameGroupCreature.objects.filter(
                group=self.group,
                creature=creature,
            ).order_by("id")
        )
        self.assertEqual(len(creature_cards), 2)

        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertEqual(screen.status_code, 200)
        self.assertContains(screen, "Testwolf")
        self.assertContains(
            screen,
            f'data-reorder-id="creature:{creature_cards[0].id}"',
        )
        self.assertContains(
            screen,
            reverse(
                "delete_group_creature",
                args=[self.group.id, creature_cards[0].id],
            ),
        )
        self.assertContains(screen, "<span>Kreatur</span>", count=2, html=True)
        self.assertContains(screen, "<span>Attribute</span>", count=3, html=True)
        self.assertContains(screen, "<dt>GK</dt>", count=2, html=True)
        self.assertContains(screen, "gm-character-sheet--creature")
        self.assertContains(screen, "data-creature-search")
        damage_url = reverse(
            "adjust_group_creature_damage",
            args=[self.group.id, creature_cards[0].id],
        )
        self.assertContains(screen, damage_url, count=4)

        self.client.post(
            damage_url,
            {"damage_type": "B", "action": "damage", "amount": "2"},
        )
        self.client.post(
            damage_url,
            {"damage_type": "T", "action": "damage", "amount": "1"},
        )
        creature_cards[0].refresh_from_db()
        self.assertEqual(creature_cards[0].current_stun_damage, 2)
        self.assertEqual(creature_cards[0].current_lethal_damage, 1)
        self.assertEqual(creature_cards[0].current_damage, 3)
        self.client.post(
            damage_url,
            {"damage_type": "B", "action": "heal", "amount": "1"},
        )
        creature_cards[0].refresh_from_db()
        self.assertEqual(creature_cards[0].current_stun_damage, 1)
        self.assertEqual(creature_cards[0].current_lethal_damage, 1)

        self.client.post(
            damage_url,
            {"damage_type": "T", "action": "damage", "amount": "5"},
        )
        creature_cards[0].refresh_from_db()
        self.assertEqual(creature_cards[0].current_damage, 7)
        dead_screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        dead_row = next(
            row
            for row in dead_screen.context["roster"]
            if row["card_id"] == f"creature:{creature_cards[0].id}"
        )
        self.assertEqual(dead_row["wound_stage"], "Tod")
        self.assertTrue(dead_row["is_dead"])
        self.assertFalse(dead_row["is_incapacitated"])
        self.assertContains(
            dead_screen,
            "gm-character-sheet--creature gm-character-sheet--dead",
        )

        state_url = reverse(
            "set_group_creature_screen_state",
            args=[self.group.id, creature_cards[0].id],
        )
        collapse_response = self.client.post(state_url, {"is_collapsed": "1"})
        self.assertEqual(collapse_response.status_code, 200)
        creature_cards[0].refresh_from_db()
        creature_cards[1].refresh_from_db()
        self.assertTrue(creature_cards[0].screen_is_collapsed)
        self.assertFalse(creature_cards[1].screen_is_collapsed)

        reorder_response = self.client.post(
            reverse("reorder_group_memberships", args=[self.group.id]),
            {
                "ordered_ids": [
                    f"creature:{creature_cards[1].id}",
                    f"character:{self.membership.id}",
                    f"creature:{creature_cards[0].id}",
                ]
            },
        )
        self.assertEqual(reorder_response.status_code, 200)
        self.membership.refresh_from_db()
        creature_cards[0].refresh_from_db()
        creature_cards[1].refresh_from_db()
        self.assertEqual(creature_cards[1].screen_position, 0)
        self.assertEqual(self.membership.screen_position, 1)
        self.assertEqual(creature_cards[0].screen_position, 2)

        delete_response = self.client.post(
            reverse(
                "delete_group_creature",
                args=[self.group.id, creature_cards[1].id],
            )
        )
        self.assertRedirects(
            delete_response,
            f"{reverse('game_master_screen', args=[self.group.id])}#sl-charaktere",
        )
        self.assertFalse(
            GameGroupCreature.objects.filter(pk=creature_cards[1].id).exists()
        )
        self.assertTrue(
            GameGroupCreature.objects.filter(pk=creature_cards[0].id).exists()
        )

    def test_group_creature_kp_are_rendered_and_adjustable(self):
        creature = Creature.objects.create(
            name="Arkaner Testwolf",
            slug="arkaner-testwolf",
            has_kp=True,
            kp_override=9,
            potential_override=4,
            combat_speed=8,
            march_speed=16,
            sprint_speed=32,
        )
        self.client.force_login(self.leader)
        self.client.post(
            reverse("add_group_creature", args=[self.group.id]),
            {"creature_id": creature.id},
        )
        creature_card = GameGroupCreature.objects.get(
            group=self.group,
            creature=creature,
        )
        self.assertEqual(creature_card.current_kp, 9)

        screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        row = next(
            entry
            for entry in screen.context["roster"]
            if entry["card_id"] == f"creature:{creature_card.id}"
        )
        self.assertTrue(row["show_arcane"])
        self.assertEqual(row["potential_label"], "Pot")
        self.assertEqual(row["potential"], 4)
        self.assertEqual(row["current_kp"], 9)
        self.assertEqual(row["max_kp"], 9)
        kp_url = reverse(
            "adjust_group_creature_kp",
            args=[self.group.id, creature_card.id],
        )
        self.assertContains(screen, kp_url, count=2)
        self.assertContains(screen, "<dt>Pot</dt>", html=True)

        self.client.post(kp_url, {"action": "spend", "amount": "3"})
        creature_card.refresh_from_db()
        self.assertEqual(creature_card.current_kp, 6)

        self.client.post(kp_url, {"action": "spend", "amount": "99"})
        creature_card.refresh_from_db()
        self.assertEqual(creature_card.current_kp, 0)

        self.client.post(kp_url, {"action": "restore", "amount": "99"})
        creature_card.refresh_from_db()
        self.assertEqual(creature_card.current_kp, 9)

    def test_group_creature_search_includes_group_character_creatures(self):
        creature = Creature.objects.create(
            name="Waldwolf",
            slug="waldwolf",
            combat_speed=8,
            march_speed=16,
            sprint_speed=32,
        )
        companion = CharacterCreature.objects.create(
            owner=self.character,
            creature=creature,
            name_override="Flocke",
            active=True,
            combat_speed_override=11,
        )
        outside_companion = CharacterCreature.objects.create(
            owner=self.other_character,
            creature=creature,
            name_override="Nicht in der Gruppe",
            active=True,
        )
        empty_form = CharacterCreature.objects.create(
            owner=self.character,
            creature=None,
            name_override="Unvollständig",
            active=True,
            source_selection_completed=False,
        )
        self.client.force_login(self.leader)

        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))

        self.assertEqual(screen.status_code, 200)
        self.assertContains(screen, f'data-creature-ref="character:{companion.id}"')
        self.assertContains(screen, f"{self.character.name} · Flocke")
        self.assertNotContains(
            screen,
            f'data-creature-ref="character:{outside_companion.id}"',
        )
        self.assertNotContains(
            screen,
            f'data-creature-ref="character:{empty_form.id}"',
        )
        response = self.client.post(
            reverse("add_group_creature", args=[self.group.id]),
            {"creature_ref": f"character:{companion.id}"},
        )

        self.assertRedirects(
            response,
            f"{reverse('game_master_screen', args=[self.group.id])}#sl-charaktere",
        )
        screen_card = GameGroupCreature.objects.get(group=self.group)
        self.assertEqual(screen_card.creature, creature)
        self.assertEqual(screen_card.character_creature, companion)
        rendered = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        self.assertContains(rendered, "Flocke")
        self.assertContains(
            rendered,
            f"<p>{self.character.name}</p>",
            html=True,
        )

    def test_game_master_can_create_and_edit_typed_group_table(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {
                "_sl_screen": "1",
                "_sl_anchor": "sl-tabellen",
                "title": "Initiative",
                "column_count": 2,
                "row_count": 2,
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('game_master_screen', args=[self.group.id])}#sl-tabellen",
        )

        data_table = GameGroupTable.objects.get(group=self.group)
        columns = list(data_table.columns.all())
        rows = list(data_table.rows.all())
        self.assertEqual(data_table.title, "Initiative")
        self.assertEqual(len(columns), 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(GameGroupTableCell.objects.filter(row__table=data_table).count(), 4)

        text_cell = GameGroupTableCell.objects.get(row=rows[0], column=columns[0])
        number_cell = GameGroupTableCell.objects.get(row=rows[0], column=columns[1])
        covered_cell = GameGroupTableCell.objects.get(row=rows[1], column=columns[0])
        suffix_cell = GameGroupTableCell.objects.get(row=rows[1], column=columns[1])
        covered_cell.text_value = "Bleibt verdeckt erhalten"
        covered_cell.save(update_fields=["text_value"])
        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "_sl_screen": "1",
                "_sl_anchor": "sl-tabellen",
                "title": "Kampf-Reihenfolge",
                "window_width": "780",
                f"column_{columns[0].id}_heading": "Name",
                f"column_{columns[1].id}_heading": "Wert",
                f"cell_{rows[0].id}_{columns[0].id}_alignment": "left",
                f"cell_{rows[0].id}_{columns[0].id}_value": "**Ari**",
                f"cell_{rows[0].id}_{columns[0].id}_rowspan": "2",
                f"cell_{rows[0].id}_{columns[0].id}_colspan": "1",
                f"cell_{rows[0].id}_{columns[1].id}_alignment": "center",
                f"cell_{rows[0].id}_{columns[1].id}_value": "+12,5",
                f"cell_{rows[1].id}_{columns[1].id}_alignment": "right",
                f"cell_{rows[1].id}_{columns[1].id}_value": "+4 CVW",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('game_master_screen', args=[self.group.id])}#sl-tabellen",
        )

        data_table.refresh_from_db()
        text_cell.refresh_from_db()
        number_cell.refresh_from_db()
        covered_cell.refresh_from_db()
        suffix_cell.refresh_from_db()
        self.assertEqual(data_table.title, "Kampf-Reihenfolge")
        self.assertEqual(data_table.window_width, 780)
        self.assertEqual(text_cell.value_type, GameGroupTableCell.ValueType.TEXT)
        self.assertEqual(text_cell.text_value, "**Ari**")
        self.assertIsNone(text_cell.number_value)
        self.assertEqual(text_cell.alignment, GameGroupTableCell.Alignment.LEFT)
        self.assertEqual(text_cell.row_span, 2)
        self.assertEqual(text_cell.column_span, 1)
        self.assertEqual(number_cell.value_type, GameGroupTableCell.ValueType.NUMBER)
        self.assertEqual(number_cell.number_value, Decimal("12.5"))
        self.assertTrue(number_cell.number_show_plus)
        self.assertEqual(number_cell.text_value, "")
        self.assertEqual(number_cell.alignment, GameGroupTableCell.Alignment.CENTER)
        self.assertEqual(covered_cell.text_value, "Bleibt verdeckt erhalten")
        self.assertEqual(suffix_cell.number_value, Decimal("4"))
        self.assertTrue(suffix_cell.number_show_plus)
        self.assertEqual(suffix_cell.number_suffix, "CVW")
        self.assertEqual(suffix_cell.alignment, GameGroupTableCell.Alignment.RIGHT)

        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(screen, "Kampf-Reihenfolge")
        self.assertContains(screen, "<strong>Ari</strong>", html=True)
        self.assertContains(screen, 'rowspan="2"', count=2)
        self.assertContains(screen, "data-table-editor-cell", count=4)
        self.assertContains(screen, "Bleibt verdeckt erhalten")
        self.assertContains(screen, "+12,5")
        self.assertContains(screen, 'aria-label="+12,5"')
        self.assertContains(screen, 'value="+12,5"')
        self.assertContains(screen, 'aria-label="+4 CVW"')
        self.assertContains(screen, 'value="+4 CVW"')
        self.assertContains(screen, "gm-data-table__align--center")
        self.assertContains(screen, "gm-data-table__align--right")
        self.assertContains(screen, 'aria-label="Zellenausrichtung"')
        rendered_table = screen.context["data_tables"][0]
        self.assertNotIn(
            covered_cell.id,
            [
                rendered_cell.id
                for rendered_row in rendered_table.render_rows
                for rendered_cell in rendered_row.render_display_cells
            ],
        )
        self.assertEqual(rendered_table.render_card_width, 780)
        self.assertEqual(rendered_table.render_editor_width, 780)
        self.assertContains(screen, 'name="window_width"')
        self.assertContains(screen, 'value="780"')
        self.assertContains(screen, 'data-table-width-input')

        hide_response = self.client.post(
            reverse("hide_group_table", args=[self.group.id, data_table.id]),
            {"_sl_screen": "1", "_sl_anchor": "sl-tabellen"},
        )
        self.assertEqual(hide_response.status_code, 302)
        data_table.refresh_from_db()
        self.assertFalse(data_table.is_visible)
        hidden_screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertEqual(list(hidden_screen.context["data_tables"]), [])
        self.assertEqual(list(hidden_screen.context["hidden_data_tables"]), [data_table])
        self.assertContains(hidden_screen, "data-table-picker-query")
        self.assertContains(hidden_screen, "data-table-picker-results")
        self.assertContains(
            hidden_screen,
            f'data-table-picker-name="{data_table.title}"',
        )
        self.assertNotContains(hidden_screen, "data-table-picker-select")

        show_response = self.client.post(
            reverse("show_group_table", args=[self.group.id, data_table.id]),
            {"_sl_screen": "1", "_sl_anchor": "sl-tabellen"},
        )
        self.assertEqual(show_response.status_code, 302)
        data_table.refresh_from_db()
        self.assertTrue(data_table.is_visible)

    def test_group_table_window_width_can_be_reset_to_automatic(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Breitentest", "column_count": 2, "row_count": 1},
        )
        data_table = GameGroupTable.objects.get(group=self.group)

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {"title": data_table.title, "window_width": "900"},
        )

        self.assertEqual(response.status_code, 302)
        data_table.refresh_from_db()
        self.assertEqual(data_table.window_width, 900)
        custom_screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        custom_table = custom_screen.context["data_tables"][0]
        self.assertEqual(custom_table.render_card_width, 900)
        self.assertEqual(custom_table.render_editor_width, 900)

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {"title": data_table.title, "window_width": ""},
        )

        self.assertEqual(response.status_code, 302)
        data_table.refresh_from_db()
        self.assertIsNone(data_table.window_width)
        automatic_screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        automatic_table = automatic_screen.context["data_tables"][0]
        self.assertEqual(automatic_table.render_card_width, 282)
        self.assertEqual(automatic_table.render_editor_width, 454)

    def test_group_table_column_widths_can_be_saved_and_reset(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Spaltenbreitentest", "column_count": 2, "row_count": 1},
        )
        data_table = GameGroupTable.objects.get(group=self.group)
        columns = list(data_table.columns.all())

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "title": data_table.title,
                f"column_{columns[0].id}_heading": "Charaktergeschwindigkeit{CG}",
                f"column_{columns[0].id}_width": "40",
                f"column_{columns[1].id}_heading": "Widerstandsfähigkeit",
                f"column_{columns[1].id}_width": "357",
            },
        )

        self.assertEqual(response.status_code, 302)
        for column in columns:
            column.refresh_from_db()
        self.assertEqual(columns[0].width, 60)
        self.assertEqual(columns[1].width, 357)
        self.assertEqual(columns[0].heading, "Charaktergeschwindigkeit{CG}")
        custom_screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        rendered_table = custom_screen.context["data_tables"][0]
        self.assertTrue(rendered_table.has_custom_column_widths)
        self.assertEqual(rendered_table.render_preview_table_width, 417)
        self.assertEqual(rendered_table.render_editor_table_width, 629)
        self.assertEqual(rendered_table.render_card_width, 419)
        self.assertEqual(rendered_table.render_editor_width, 631)
        self.assertContains(custom_screen, 'data-table-column-width-input')
        self.assertContains(custom_screen, 'min="60"')
        self.assertNotContains(custom_screen, 'step="10"')
        self.assertContains(
            custom_screen,
            'class="gm-data-table__table--custom-widths"',
        )
        self.assertContains(
            custom_screen,
            (
                '<abbr class="gm-data-table__heading-abbreviation" '
                'title="Charaktergeschwindigkeit">CG</abbr>'
            ),
            html=True,
        )
        self.assertContains(
            custom_screen,
            'value="Charaktergeschwindigkeit{CG}"',
        )

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "title": data_table.title,
                f"column_{columns[0].id}_heading": columns[0].heading,
                f"column_{columns[0].id}_width": "",
                f"column_{columns[1].id}_heading": columns[1].heading,
                f"column_{columns[1].id}_width": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        for column in columns:
            column.refresh_from_db()
            self.assertIsNone(column.width)
        automatic_screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        automatic_table = automatic_screen.context["data_tables"][0]
        self.assertFalse(automatic_table.has_custom_column_widths)
        self.assertEqual(automatic_table.render_card_width, 282)
        self.assertEqual(automatic_table.render_editor_width, 454)

    def test_game_master_can_detach_and_position_group_table(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Freie Tabelle", "column_count": 1, "row_count": 1},
        )
        data_table = GameGroupTable.objects.get(group=self.group)

        stack_response = self.client.post(
            reverse(
                "update_group_table_layout",
                args=[self.group.id, data_table.id],
            ),
            {"is_stacked": "1"},
        )
        self.assertEqual(stack_response.status_code, 200)
        self.assertTrue(stack_response.json()["is_stacked"])
        data_table.refresh_from_db()
        self.assertTrue(data_table.is_stacked)
        stacked_screen = self.client.get(
            reverse("game_master_screen", args=[self.group.id])
        )
        self.assertContains(stacked_screen, "gm-data-table--stacked")
        self.assertContains(stacked_screen, "gm-data-tables--has-stacked")

        response = self.client.post(
            reverse(
                "update_group_table_layout",
                args=[self.group.id, data_table.id],
            ),
            {
                "is_detached": "1",
                "x": "-15",
                "y": "12000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "is_detached": True,
                "x": 0,
                "y": 10000,
                "is_stacked": True,
            },
        )
        data_table.refresh_from_db()
        self.assertTrue(data_table.is_detached)
        self.assertEqual(data_table.detached_x, 0)
        self.assertEqual(data_table.detached_y, 10000)

        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(screen, "gm-data-table--detached")
        self.assertContains(screen, "data-table-detach-toggle")
        self.assertContains(screen, "data-table-layout-url")
        self.assertContains(screen, 'aria-pressed="true"')
        self.assertContains(screen, "left: 0px; top: 10000px;")

        self.client.force_login(self.other)
        forbidden_response = self.client.post(
            reverse(
                "update_group_table_layout",
                args=[self.group.id, data_table.id],
            ),
            {"is_detached": "0", "x": "30", "y": "40"},
        )
        self.assertEqual(forbidden_response.status_code, 403)
        data_table.refresh_from_db()
        self.assertTrue(data_table.is_detached)
        self.assertEqual(data_table.detached_x, 0)
        self.assertEqual(data_table.detached_y, 10000)

    def test_group_tables_are_limited_to_game_masters_and_their_own_group(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Nicht erlaubt", "column_count": 1, "row_count": 1},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GameGroupTable.objects.filter(group=self.group).exists())

        self.client.force_login(self.leader)
        create_response = self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Erlaubt", "column_count": 1, "row_count": 1},
        )
        self.assertEqual(create_response.status_code, 302)
        data_table = GameGroupTable.objects.get(group=self.group)

        other_group = create_group(creator=self.other, name="Andere Runde")
        response = self.client.post(
            reverse("update_group_table", args=[other_group.id, data_table.id]),
            {"title": "Verschoben"},
        )
        self.assertEqual(response.status_code, 403)
        data_table.refresh_from_db()
        self.assertEqual(data_table.title, "Erlaubt")

    def test_personal_and_shared_tables_follow_creator_access(self):
        owner_overview_group = create_group(
            creator=self.leader,
            name="Persönliche Übersicht",
        )
        other_overview_group = create_group(
            creator=self.other,
            name="Andere Übersicht",
        )
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Persönliche Tabelle", "column_count": 1, "row_count": 1},
        )
        data_table = GameGroupTable.objects.get(
            group=self.group,
            title="Persönliche Tabelle",
        )

        owner_screen = self.client.get(
            reverse("game_master_screen", args=[owner_overview_group.id])
        )
        self.assertContains(owner_screen, "Persönliche Tabelle")
        self.assertContains(owner_screen, 'name="is_shared"')
        self.assertNotContains(owner_screen, 'name="is_shared" value="1" checked')

        self.client.force_login(self.other)
        other_screen = self.client.get(
            reverse("game_master_screen", args=[other_overview_group.id])
        )
        self.assertNotContains(other_screen, "Persönliche Tabelle")
        private_update = self.client.post(
            reverse(
                "update_group_table",
                args=[other_overview_group.id, data_table.id],
            ),
            {"title": "Nicht erlaubt", "is_shared": "0"},
        )
        self.assertEqual(private_update.status_code, 403)

        self.client.force_login(self.leader)
        share_response = self.client.post(
            reverse(
                "update_group_table",
                args=[owner_overview_group.id, data_table.id],
            ),
            {"title": data_table.title, "is_shared": "1"},
        )
        self.assertEqual(share_response.status_code, 302)
        data_table.refresh_from_db()
        self.assertTrue(data_table.is_shared)

        self.client.force_login(self.other)
        shared_screen = self.client.get(
            reverse("game_master_screen", args=[other_overview_group.id])
        )
        self.assertContains(shared_screen, "Persönliche Tabelle")
        self.assertContains(shared_screen, "data-table-sharing-toggle")
        self.assertContains(
            shared_screen,
            "nur der Originalersteller kann dies ändern",
        )
        shared_update = self.client.post(
            reverse(
                "update_group_table",
                args=[other_overview_group.id, data_table.id],
            ),
            {"title": "Gemeinsam bearbeitet", "is_shared": "0"},
        )
        self.assertEqual(shared_update.status_code, 302)
        data_table.refresh_from_db()
        self.assertEqual(data_table.title, "Gemeinsam bearbeitet")
        self.assertTrue(data_table.is_shared)

        self.client.force_login(self.leader)
        unshare_response = self.client.post(
            reverse(
                "update_group_table",
                args=[owner_overview_group.id, data_table.id],
            ),
            {"title": data_table.title, "is_shared": "0"},
        )
        self.assertEqual(unshare_response.status_code, 302)
        data_table.refresh_from_db()
        self.assertFalse(data_table.is_shared)

        self.client.force_login(self.other)
        private_again_screen = self.client.get(
            reverse("game_master_screen", args=[other_overview_group.id])
        )
        self.assertNotContains(private_again_screen, "Gemeinsam bearbeitet")

    def test_personal_table_survives_creator_role_revocation(self):
        add_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)
        later_overview_group = create_group(
            creator=self.gm,
            name="Spätere SL-Übersicht",
        )
        self.client.force_login(self.gm)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Bleibt persönlich", "column_count": 1, "row_count": 1},
        )
        data_table = GameGroupTable.objects.get(title="Bleibt persönlich")
        self.assertEqual(data_table.creator, self.gm)

        revoke_game_master(
            group_id=self.group.id,
            actor=self.leader,
            user=self.gm,
        )

        later_screen = self.client.get(
            reverse("game_master_screen", args=[later_overview_group.id])
        )
        self.assertContains(later_screen, "Bleibt persönlich")

    def test_table_structure_actions_preserve_values_and_edit_mode(self):
        self.client.force_login(self.leader)
        self.client.post(
            reverse("create_group_table", args=[self.group.id]),
            {"title": "Offener Editor", "column_count": 1, "row_count": 1},
        )
        data_table = GameGroupTable.objects.get(group=self.group)
        column = data_table.columns.get()
        row = data_table.rows.get()

        response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "_sl_screen": "1",
                "_sl_anchor": "sl-tabellen",
                "_edit_table_id": data_table.id,
                "_table_action": "add_row",
                "title": data_table.title,
                f"column_{column.id}_heading": column.heading,
                f"cell_{row.id}_{column.id}_type": "text",
                f"cell_{row.id}_{column.id}_value": "**Bleibt erhalten**",
                f"cell_{row.id}_{column.id}_rowspan": "1",
                f"cell_{row.id}_{column.id}_colspan": "1",
            },
        )

        self.assertEqual(
            response.url,
            f"{reverse('game_master_screen', args=[self.group.id])}"
            f"?edit_table={data_table.id}#sl-tabellen",
        )
        self.assertEqual(data_table.rows.count(), 2)
        cell = GameGroupTableCell.objects.get(row=row, column=column)
        self.assertEqual(cell.text_value, "**Bleibt erhalten**")
        added_row = data_table.rows.exclude(pk=row.id).get()
        added_cell = GameGroupTableCell.objects.get(row=added_row, column=column)

        move_response = self.client.post(
            reverse("update_group_table", args=[self.group.id, data_table.id]),
            {
                "_sl_screen": "1",
                "_sl_anchor": "sl-tabellen",
                "_edit_table_id": data_table.id,
                "_table_action": f"move_row_up:{added_row.id}",
                "title": data_table.title,
                f"column_{column.id}_heading": column.heading,
                f"cell_{row.id}_{column.id}_type": "text",
                f"cell_{row.id}_{column.id}_value": cell.text_value,
                f"cell_{row.id}_{column.id}_rowspan": "1",
                f"cell_{row.id}_{column.id}_colspan": "1",
                f"cell_{added_row.id}_{column.id}_type": "text",
                f"cell_{added_row.id}_{column.id}_value": "Neue erste Zeile",
                f"cell_{added_row.id}_{column.id}_rowspan": "1",
                f"cell_{added_row.id}_{column.id}_colspan": "1",
            },
        )
        self.assertEqual(move_response.status_code, 302)
        self.assertEqual(
            list(data_table.rows.order_by("position", "id").values_list("id", flat=True)),
            [added_row.id, row.id],
        )
        added_cell.refresh_from_db()
        self.assertEqual(added_cell.text_value, "Neue erste Zeile")

        editor_screen = self.client.get(response.url)
        self.assertEqual(editor_screen.context["editing_table_id"], data_table.id)
        self.assertIn(
            b'<details class="gm-data-table__editor" open>',
            editor_screen.content,
        )

    def test_creation_has_exactly_one_leader_and_optional_gm_is_full_gm(self):
        leader_role = GameGroupRole.objects.get(group=self.group, role=GameGroupRole.Role.LEADER)
        self.assertEqual(leader_role.user, self.leader)
        self.assertIsNotNone(require_game_master(self.leader, self.group, write=True))

        gm_role = add_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)
        self.assertEqual(gm_role.role, GameGroupRole.Role.GM)
        self.assertIsNotNone(require_game_master(self.gm, self.group, write=True))

        with self.assertRaises(IntegrityError), transaction.atomic():
            GameGroupRole.objects.create(
                group=self.group,
                user=self.other,
                role=GameGroupRole.Role.LEADER,
            )

    def test_character_item_can_be_sent_directly_to_group_gms_for_editing(self):
        quality = Quality.objects.create(code="gm-edit", name="SL-Bearbeitung")
        item = CharacterItem.objects.create(
            item=self.definition,
            owner=self.character,
            original_owner_character=self.character,
            quality=quality,
            amount=2,
        )

        transfer = create_gm_edit_transfer(
            item_id=item.id,
            sender=self.character,
            group=self.group,
            message="Bitte anpassen",
        )

        item.refresh_from_db()
        self.assertEqual(transfer.transfer_kind, ItemTransfer.TransferKind.GM_EDIT)
        self.assertEqual(transfer.status, ItemTransfer.Status.PENDING)
        self.assertEqual(transfer.recipient_group, self.group)
        self.assertIsNone(transfer.recipient)
        self.assertEqual(item.owner, self.character)
        self.assertEqual(item.original_owner_character, self.character)

        self.client.force_login(self.player)
        character_sheet = self.client.get(reverse("character_sheet", args=[self.character.id]))
        self.assertEqual(character_sheet.status_code, 200)
        self.assertContains(character_sheet, "inv_row--gm-edit")
        self.assertContains(character_sheet, f"SL @ {self.group.name}")
        self.assertNotContains(character_sheet, "Übergabe zurückziehen")

        self.client.force_login(self.leader)
        screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(screen, self.definition.name)
        self.assertContains(screen, f"von {self.character.name}")

        response = self.client.post(
            reverse("edit_group_inventory_item", args=[self.group.id, item.id]),
            {
                "quality": quality.pk,
                "amount": 2,
                "name": "Vom SL angepasst",
                "description": "",
                "magic_modifier_payloads": "[]",
            },
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.owner, self.character)
        self.assertEqual(item.original_owner_character, self.character)
        self.assertEqual(item.name_override, "Vom SL angepasst")
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, ItemTransfer.Status.PENDING)

        response = self.client.post(
            reverse("complete_group_item_edit", args=[self.group.id, transfer.id])
        )
        self.assertEqual(response.status_code, 302)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, ItemTransfer.Status.ACCEPTED)

    def test_cached_transfer_dialog_group_id_is_not_treated_as_character_id(self):
        item = CharacterItem.objects.create(
            item=self.definition,
            owner=self.character,
            original_owner_character=self.character,
            amount=1,
        )
        self.client.force_login(self.player)
        response = self.client.post(
            reverse("create_item_transfer", args=[item.id]),
            {
                "sender_id": self.character.id,
                "recipient_id": -self.group.id,
                "quantity": 1,
                "message": "Aus altem Dialog",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        transfer = ItemTransfer.objects.get(item=item, transfer_kind=ItemTransfer.TransferKind.GM_EDIT)
        self.assertEqual(transfer.recipient_group, self.group)
        item.refresh_from_db()
        self.assertEqual(item.owner, self.character)

    def test_leadership_transfer_keeps_one_leader_and_demotes_old_leader_to_gm(self):
        add_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)
        transfer_leadership(group_id=self.group.id, actor=self.leader, new_leader=self.gm)
        roles = GameGroupRole.objects.filter(group=self.group, is_active=True)
        self.assertEqual(roles.filter(role=GameGroupRole.Role.LEADER).count(), 1)
        self.assertEqual(roles.get(user=self.gm).role, GameGroupRole.Role.LEADER)
        self.assertEqual(roles.get(user=self.leader).role, GameGroupRole.Role.GM)

    def test_group_names_are_case_insensitively_unique(self):
        with self.assertRaises(GroupError) as raised:
            create_group(creator=self.gm, name="  DIE   RUNDE ")
        self.assertEqual(raised.exception.code, "duplicate_name")
        with self.assertRaises(IntegrityError), transaction.atomic():
            GameGroup.objects.create(name="die runde", creator=self.gm)

    def test_blank_group_name_creates_unique_generic_names(self):
        first = create_group(creator=self.gm, name="")
        second = create_group(creator=self.other, name="")
        self.assertEqual(first.name, "Neue Spielgruppe")
        self.assertEqual(second.name, "Neue Spielgruppe 2")

    def test_leader_can_rename_group_but_duplicate_name_is_rejected(self):
        other_group = create_group(creator=self.gm, name="Andere Runde")
        renamed = rename_group(group_id=self.group.id, actor=self.leader, name="Neue Kampagne")
        self.assertEqual(renamed.name, "Neue Kampagne")
        with self.assertRaises(GroupError) as raised:
            rename_group(group_id=self.group.id, actor=self.leader, name=other_group.name.lower())
        self.assertEqual(raised.exception.code, "duplicate_name")

    def test_group_can_be_physically_deleted_with_management_relations(self):
        group_id = self.group.id
        delete_group(group_id=group_id, actor=self.leader)
        self.assertFalse(GameGroup.objects.filter(pk=group_id).exists())
        self.assertFalse(GameGroupMembership.objects.filter(group_id=group_id).exists())
        self.assertFalse(GameGroupRole.objects.filter(group_id=group_id).exists())

    def test_group_deletion_removes_group_inventory(self):
        item = self.group_item()
        delete_group(group_id=self.group.id, actor=self.leader)
        self.assertFalse(CharacterItem.objects.filter(pk=item.pk).exists())
        self.assertFalse(GameGroup.objects.filter(pk=self.group.id).exists())

    def test_group_deletion_protects_private_items_in_character_inventory(self):
        private = Item.objects.create(
            name="Übertragenes Gruppenitem",
            price=1,
            item_type=Item.ItemType.MISC,
            catalog_group=self.group,
        )
        CharacterItem.objects.create(
            item=private,
            owner=self.character,
            original_owner_character=self.character,
            group_origin_finalized=True,
        )
        with self.assertRaises(GroupError) as raised:
            delete_group(group_id=self.group.id, actor=self.leader)
        self.assertEqual(raised.exception.code, "group_catalog_item_in_character_inventory")
        self.assertTrue(GameGroup.objects.filter(pk=self.group.id).exists())

    def test_database_requires_exactly_one_current_and_origin_owner(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CharacterItem.objects.create(
                item=self.definition,
                owner=self.character,
                group_owner=self.group,
                original_owner_character=self.character,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CharacterItem.objects.create(
                item=self.definition,
                owner=self.character,
                original_owner_character=self.character,
                original_owner_group=self.group,
            )

    def test_group_offer_transfers_origin_exactly_once_on_acceptance(self):
        item = self.group_item()
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        item.refresh_from_db()
        self.assertEqual(item.group_owner, self.group)
        self.assertEqual(item.original_owner_group, self.group)

        accept_transfer(transfer_id=transfer.id, recipient=self.character)
        item.refresh_from_db()
        self.assertEqual(item.owner, self.character)
        self.assertIsNone(item.group_owner)
        self.assertEqual(item.original_owner_character, self.character)
        self.assertIsNone(item.original_owner_group)
        self.assertTrue(item.group_origin_finalized)

    def test_group_origin_cannot_be_transferred_again(self):
        item = self.group_item()
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        accept_transfer(transfer_id=transfer.id, recipient=self.character)
        from charsheet.item_transfers import create_transfer

        with self.assertRaises(TransferError) as raised:
            create_transfer(
                item_id=item.id,
                sender=self.character,
                recipient=self.other_character,
                quantity=1,
                transfer_original_ownership=True,
            )
        self.assertEqual(raised.exception.code, "group_origin_locked")

    def test_ending_membership_recalls_all_pending_group_offers_first(self):
        item = self.group_item()
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        end_membership(membership_id=self.membership.id, actor=self.leader)
        transfer.refresh_from_db()
        self.membership.refresh_from_db()
        self.assertEqual(transfer.status, ItemTransfer.Status.RECALLED)
        self.assertEqual(self.membership.status, GameGroupMembership.Status.REMOVED)

    def test_joining_another_group_recalls_offers_from_previous_group(self):
        item = self.group_item()
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        other_group = create_group(creator=self.gm, name="Andere Runde")
        invitation = create_invitation(
            group_id=other_group.id,
            actor=self.gm,
            character=self.character,
        )
        accept_invitation(invitation_id=invitation.id, user=self.player)
        transfer.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(transfer.status, ItemTransfer.Status.RECALLED)
        self.assertEqual(invitation.status, GameGroupInvitation.Status.ACCEPTED)

    def test_archiving_recalls_offers_and_blocks_late_acceptance(self):
        item = self.group_item()
        invitation = create_invitation(
            group_id=self.group.id,
            actor=self.leader,
            character=self.other_character,
        )
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        archive_group(group_id=self.group.id, actor=self.leader)
        self.group.refresh_from_db()
        transfer.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(self.group.is_archived)
        self.assertEqual(transfer.status, ItemTransfer.Status.RECALLED)
        self.assertEqual(invitation.status, GameGroupInvitation.Status.WITHDRAWN)
        with self.assertRaises(TransferError):
            accept_transfer(transfer_id=transfer.id, recipient=self.character)

    def test_acceptance_rechecks_membership_after_a_concurrent_membership_change(self):
        item = self.group_item()
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        GameGroupMembership.objects.filter(pk=self.membership.pk).update(
            status=GameGroupMembership.Status.REMOVED
        )
        with self.assertRaises(TransferError) as raised:
            accept_transfer(transfer_id=transfer.id, recipient=self.character)
        self.assertEqual(raised.exception.code, "group_membership_required")
        item.refresh_from_db()
        self.assertEqual(item.group_owner, self.group)
        self.assertEqual(item.original_owner_group, self.group)

    def test_acceptance_rechecks_archive_state_under_lock(self):
        item = self.group_item()
        transfer = create_group_transfer(
            item_id=item.id,
            group=self.group,
            actor=self.leader,
            recipient=self.character,
            quantity=1,
        )
        GameGroup.objects.filter(pk=self.group.pk).update(is_archived=True)
        with self.assertRaises(TransferError) as raised:
            accept_transfer(transfer_id=transfer.id, recipient=self.character)
        self.assertEqual(raised.exception.code, "group_archived")
        item.refresh_from_db()
        self.assertEqual(item.group_owner, self.group)

    def test_sl_authorization_uses_role_and_membership_not_character_owner(self):
        add_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)
        self.assertIsNotNone(require_sl_character_access(self.gm, self.group, self.character))
        with self.assertRaises(PermissionDenied):
            require_sl_character_access(self.gm, self.group, self.other_character)
        revoke_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)
        with self.assertRaises(PermissionDenied):
            require_sl_character_access(self.gm, self.group, self.character)

    def test_owner_route_stays_closed_to_gm_and_dedicated_route_is_read_only(self):
        add_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)
        self.client.force_login(self.gm)
        owner_response = self.client.get(reverse("character_sheet", args=[self.character.id]))
        self.assertEqual(owner_response.status_code, 404)
        with (
            patch("charsheet.views.expire_due_transfers") as expire_due,
            patch("charsheet.engine.magic_engine.MagicEngine.sync_character_magic") as magic_sync,
            patch("charsheet.sheet_context.sync_character_creatures") as creature_sync,
            patch("charsheet.sheet_context._sync_modifier_granted_skill_specifications") as skill_sync,
        ):
            read_response = self.client.get(
                reverse("game_master_character_sheet", args=[self.group.id, self.character.id])
            )
        expire_due.assert_not_called()
        magic_sync.assert_not_called()
        creature_sync.assert_not_called()
        skill_sync.assert_not_called()
        self.assertEqual(read_response.status_code, 200)
        self.assertContains(read_response, "SL-Leseansicht")
        diary_url = reverse(
            "game_master_character_diary", args=[self.group.id, self.character.id]
        )
        self.assertEqual(self.client.get(diary_url).status_code, 200)
        self.assertEqual(self.client.post(diary_url).status_code, 405)
        damage_before = self.character.current_damage
        blocked_change = self.client.post(
            reverse("adjust_current_damage", args=[self.character.id]),
            {"damage_type": "B", "action": "damage", "amount": 1},
        )
        self.assertEqual(blocked_change.status_code, 404)
        self.character.refresh_from_db()
        self.assertIsNone(self.character.last_opened_at)
        self.assertEqual(self.character.current_damage, damage_before)

    def test_stack_merge_is_blocked_by_any_instance_override_difference(self):
        first = self.group_item(description="Variante A")
        second = self.group_item(description="Variante B")
        for item in (first, second):
            transfer = create_group_transfer(
                item_id=item.id,
                group=self.group,
                actor=self.leader,
                recipient=self.character,
                quantity=1,
            )
            accept_transfer(transfer_id=transfer.id, recipient=self.character)
        self.assertEqual(
            CharacterItem.objects.filter(owner=self.character, item=self.definition).count(),
            2,
        )

    def test_fully_identical_group_instances_can_merge(self):
        first = self.group_item()
        second = self.group_item()
        for item in (first, second):
            transfer = create_group_transfer(
                item_id=item.id,
                group=self.group,
                actor=self.leader,
                recipient=self.character,
                quantity=1,
            )
            accept_transfer(transfer_id=transfer.id, recipient=self.character)
        merged = CharacterItem.objects.get(owner=self.character, item=self.definition)
        self.assertEqual(merged.amount, 2)

    def test_private_catalog_names_are_scoped_and_not_global(self):
        private = Item.objects.create(
            name=self.definition.name,
            price=1,
            item_type=Item.ItemType.MISC,
            catalog_group=self.group,
        )
        self.assertEqual(private.catalog_group, self.group)
        self.assertEqual(Item.objects.filter(catalog_group__isnull=True, name=self.definition.name).count(), 1)

    def test_group_and_dashboard_templates_render_for_gm_and_member(self):
        self.client.force_login(self.leader)
        gm_response = self.client.get(reverse("game_group_detail", args=[self.group.id]))
        self.assertEqual(gm_response.status_code, 200)
        self.assertNotContains(gm_response, "SL-Inventar")
        self.assertNotContains(gm_response, "SL-Screen öffnen")
        self.assertNotContains(gm_response, "← Dashboard")
        self.assertContains(gm_response, 'id="gameGroupNameEdit"')
        self.assertNotContains(gm_response, "<h2>Gruppeneinstellungen</h2>", html=True)
        self.assertContains(gm_response, "codex:group-dashboard-table-refresh")
        self.assertNotContains(gm_response, "window.parent.location.reload()")
        gm_dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(gm_dashboard.status_code, 200)
        self.assertNotContains(gm_dashboard, 'id="sl-inventar"')
        self.assertContains(gm_dashboard, 'id="dashboardGroupWindow"')
        self.assertContains(gm_dashboard, "data-open-group-window")
        self.assertContains(gm_dashboard, "dashboard_table_group_heading")
        gm_screen = self.client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertEqual(gm_screen.status_code, 200)
        self.assertContains(gm_screen, 'id="sl-inventar"')
        self.assertContains(
            gm_screen,
            "<h2>Notizen &amp; Tabellen</h2>",
            html=True,
        )
        self.assertContains(gm_screen, "Gruppeneigenes Basisitem erstellen")

        self.client.force_login(self.player)
        member_response = self.client.get(reverse("game_group_detail", args=[self.group.id]))
        self.assertEqual(member_response.status_code, 200)
        self.assertNotContains(member_response, "SL-Inventar")
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, self.group.name)

    def test_group_character_search_uses_names_and_group_scope(self):
        self.client.force_login(self.leader)
        invite_search = self.client.get(
            reverse("group_character_search", args=[self.group.id]),
            {"q": "Be", "mode": "invite"},
        )
        self.assertEqual(invite_search.status_code, 200)
        self.assertEqual(invite_search.json()["results"][0]["name"], self.other_character.name)

        recipient_search = self.client.get(
            reverse("group_character_search", args=[self.group.id]),
            {"q": "Ar", "mode": "recipient"},
        )
        self.assertEqual(recipient_search.status_code, 200)
        self.assertEqual(recipient_search.json()["results"][0]["id"], self.character.id)

        outside_recipient = self.client.get(
            reverse("group_character_search", args=[self.group.id]),
            {"q": "Be", "mode": "recipient"},
        )
        self.assertEqual(outside_recipient.json()["results"], [])
