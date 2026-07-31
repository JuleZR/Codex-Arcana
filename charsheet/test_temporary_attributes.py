import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from charsheet.constants import ATTRIBUTE_ORDER, ATTR_KON, ATTR_ST, ATTR_WILL
from charsheet.engine import CharacterEngine
from charsheet.game_groups import add_game_master, create_group
from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterSkill,
    GameGroupMembership,
    Race,
    Skill,
    SkillCategory,
)
from charsheet.sheet_context import build_character_sheet_context


class TemporaryAttributeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="temp-owner", password="secret")
        self.leader = user_model.objects.create_user(username="temp-leader", password="secret")
        self.gm = user_model.objects.create_user(username="temp-gm", password="secret")
        self.outsider = user_model.objects.create_user(username="temp-outsider", password="secret")
        self.race = Race.objects.create(name="Temporärtest-Volk")
        self.character = Character.objects.create(owner=self.owner, name="Tara", race=self.race)
        self.attributes = {}
        for short_name, label in ATTRIBUTE_ORDER:
            attribute = Attribute.objects.create(name=label, short_name=short_name)
            CharacterAttribute.objects.create(
                character=self.character,
                attribute=attribute,
                base_value=10,
            )
            self.attributes[short_name] = attribute
        self.skill_category = SkillCategory.objects.create(name="Temporärtest", slug="temporary-test")
        self.skill = Skill.objects.create(
            name="Kraftprobe",
            slug="temporary-strength-check",
            category=self.skill_category,
            attribute=self.attributes[ATTR_ST],
        )
        CharacterSkill.objects.create(character=self.character, skill=self.skill, level=2)

        self.group = create_group(creator=self.leader, name="Temporärtest-Runde")
        GameGroupMembership.objects.create(group=self.group, character=self.character)
        add_game_master(group_id=self.group.id, actor=self.leader, user=self.gm)

    def post_operation(self, client, url, attribute, operation, *, amount=1):
        return client.post(
            url,
            data=json.dumps({"attribute": attribute, "operation": operation, "amount": amount}),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )

    def test_runtime_engine_adjustments_change_derived_values_without_changing_base(self):
        base_engine = CharacterEngine(self.character)
        runtime_engine = CharacterEngine(
            self.character,
            runtime_attribute_adjustments={ATTR_ST: 2, ATTR_KON: -1, ATTR_WILL: 2},
        )

        self.assertEqual(base_engine.attributes()[ATTR_ST], 10)
        self.assertEqual(runtime_engine.attributes()[ATTR_ST], 12)
        self.assertEqual(runtime_engine.attribute_modifier(ATTR_ST), 7)
        self.assertEqual(runtime_engine.skill_total(self.skill.slug), base_engine.skill_total(self.skill.slug) + 2)
        self.assertEqual(sorted(runtime_engine.wound_thresholds())[0], 9)
        self.assertEqual(runtime_engine.calculate_arcane_power(), base_engine.calculate_arcane_power() + 2)
        self.assertEqual(runtime_engine.calculate_potential(), base_engine.calculate_potential() + 1)

        persisted = CharacterAttribute.objects.get(
            character=self.character,
            attribute=self.attributes[ATTR_ST],
        )
        self.assertEqual(persisted.base_value, 10)

    def test_learning_context_uses_persisted_attribute_while_sheet_uses_runtime_value(self):
        self.character.get_engine(refresh=True, runtime_attribute_adjustments={ATTR_ST: 3})
        context = build_character_sheet_context(self.character)

        sheet_row = next(row for row in context["attribute_rows"] if row["short_name"] == ATTR_ST)
        learning_row = next(row for row in context["learn_attr_rows"] if row["short_name"] == ATTR_ST)
        self.assertEqual(sheet_row["value"], 13)
        self.assertEqual(sheet_row["runtime_adjustment"], 3)
        self.assertEqual(learning_row["base_value"], 10)

    def test_owner_adjustment_persists_in_session_and_reset_never_updates_character(self):
        self.client.force_login(self.owner)
        url = reverse("update_temporary_attribute", args=[self.character.id])

        first = self.post_operation(self.client, url, ATTR_ST, "increment")
        second = self.post_operation(self.client, url, ATTR_ST, "increment")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json()["adjustments"], {ATTR_ST: 2})
        self.assertEqual(
            {partial["target"] for partial in second.json()["partials"]},
            {
                "sheetAttributePanel",
                "sheetSkillsPanel",
                "sheetCoreStatsPanel",
                "sheetDamagePanel",
                "sheetWeaponPanel",
            },
        )

        batched = self.post_operation(self.client, url, ATTR_ST, "decrement", amount=2)
        self.assertEqual(batched.status_code, 200)
        self.assertEqual(batched.json()["adjustments"], {})

        with patch(
            "charsheet.views._build_sheet_context_for_request",
            side_effect=AssertionError("temporary updates must use the lightweight context"),
        ):
            lightweight = self.post_operation(self.client, url, ATTR_ST, "increment")
        self.assertEqual(lightweight.status_code, 200)

        sheet = self.client.get(reverse("character_sheet", args=[self.character.id]))
        self.assertContains(sheet, 'data-temporary-adjustment="1"')
        self.assertContains(sheet, 'class="is-temporary-positive"')
        self.assertContains(sheet, 'data-operation="decrement"')
        self.assertContains(sheet, 'data-operation="reset"')
        self.assertContains(sheet, 'data-operation="increment"')

        reset = self.post_operation(self.client, url, ATTR_ST, "reset")
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json()["adjustments"], {})
        persisted = CharacterAttribute.objects.get(
            character=self.character,
            attribute=self.attributes[ATTR_ST],
        )
        self.assertEqual(persisted.base_value, 10)

    def test_sessions_are_isolated_and_the_sl_card_auto_refresh_signature_changes(self):
        owner_client = Client()
        gm_client = Client()
        owner_client.force_login(self.owner)
        gm_client.force_login(self.gm)
        owner_url = reverse("update_temporary_attribute", args=[self.character.id])
        gm_url = reverse(
            "update_game_master_temporary_attribute",
            args=[self.group.id, self.character.id],
        )

        self.post_operation(owner_client, owner_url, ATTR_ST, "increment")
        baseline_refresh_signature = gm_client.get(
            reverse("group_inventory_transfer_state", args=[self.group.id])
        ).json()["signature"]
        gm_response = self.post_operation(gm_client, gm_url, ATTR_ST, "decrement")

        self.assertEqual(gm_response.status_code, 200)
        self.assertEqual(gm_response.json()["adjustments"], {ATTR_ST: -1})
        owner_sheet = owner_client.get(reverse("character_sheet", args=[self.character.id]))
        gm_sheet = gm_client.get(
            reverse("game_master_character_sheet", args=[self.group.id, self.character.id])
        )
        self.assertContains(owner_sheet, 'data-temporary-adjustment="1"')
        self.assertContains(gm_sheet, 'data-temporary-adjustment="-1"')
        self.assertContains(gm_sheet, 'class="is-temporary-negative"')
        self.assertContains(gm_sheet, "data-temporary-attribute-control")

        gm_screen = gm_client.get(reverse("game_master_screen", args=[self.group.id]))
        self.assertContains(gm_screen, 'class="is-temporary-negative"')
        self.assertContains(gm_screen, '<dd>9 <small>(+4)</small></dd>', html=True)
        self.assertContains(gm_screen, "ST=-1")
        refresh_state = gm_client.get(reverse("group_inventory_transfer_state", args=[self.group.id]))
        self.assertEqual(refresh_state.status_code, 200)
        self.assertIn("ST=-1", refresh_state.json()["signature"])
        self.assertNotEqual(refresh_state.json()["signature"], baseline_refresh_signature)

    def test_invalid_and_unauthorized_requests_are_rejected(self):
        self.client.force_login(self.owner)
        owner_url = reverse("update_temporary_attribute", args=[self.character.id])
        invalid_attribute = self.post_operation(self.client, owner_url, "NOPE", "increment")
        invalid_operation = self.post_operation(self.client, owner_url, ATTR_ST, "replace")
        invalid_amount = self.post_operation(self.client, owner_url, ATTR_ST, "increment", amount=101)
        self.assertEqual(invalid_attribute.status_code, 400)
        self.assertEqual(invalid_operation.status_code, 400)
        self.assertEqual(invalid_amount.status_code, 400)

        outsider_client = Client()
        outsider_client.force_login(self.outsider)
        gm_url = reverse(
            "update_game_master_temporary_attribute",
            args=[self.group.id, self.character.id],
        )
        forbidden = self.post_operation(outsider_client, gm_url, ATTR_ST, "increment")
        self.assertEqual(forbidden.status_code, 403)
