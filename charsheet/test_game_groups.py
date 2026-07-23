from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

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
from charsheet.models import (
    Character,
    CharacterItem,
    GameGroup,
    GameGroupInvitation,
    GameGroupMembership,
    GameGroupRole,
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
