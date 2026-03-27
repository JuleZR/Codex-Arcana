"""Regression tests for server-rendered character-sheet partial updates."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.models import ArmorStats, Character, CharacterItem, Item, Race


class CharacterSheetPartialTests(TestCase):
    """Ensure sheet actions return rendered partials instead of forcing reloads."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="partialtester", password="secret")
        self.race = Race.objects.create(name="Mensch")
        self.character = Character.objects.create(owner=self.user, name="Iria", race=self.race, money=500)
        self.client.force_login(self.user)

    def test_adjust_current_damage_returns_damage_partial(self):
        response = self.client.post(
            reverse("adjust_current_damage", args=[self.character.id]),
            {"action": "damage", "amount": "3"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["partials"][0]["target"], "sheetDamagePanel")
        self.assertIn("damage_current_value", payload["partials"][0]["html"])
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_damage, 3)

    def test_toggle_equip_returns_all_affected_sheet_partials(self):
        armor = Item.objects.create(
            name="Lederharnisch",
            price=50,
            item_type=Item.ItemType.ARMOR,
            stackable=False,
            default_quality="common",
        )
        ArmorStats.objects.create(item=armor, rs_total=1, encumbrance=1, min_st=1)
        owned_item = CharacterItem.objects.create(owner=self.character, item=armor, amount=1, equipped=False, quality="common")

        response = self.client.post(
            reverse("toggle_equip", args=[owned_item.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        targets = {entry["target"] for entry in payload["partials"]}
        self.assertEqual(
            targets,
            {"sheetLoadPanel", "sheetCoreStatsPanel", "sheetInventoryPanel", "sheetArmorPanel", "sheetWeaponPanel"},
        )
        owned_item.refresh_from_db()
        self.assertTrue(owned_item.equipped)

    def test_buy_shop_cart_returns_wallet_and_inventory_partials(self):
        item = Item.objects.create(
            name="Heilkraut",
            price=25,
            item_type=Item.ItemType.CONSUM,
            stackable=True,
            default_quality="common",
        )
        payload = {
            "items": [{"id": item.id, "qty": 2, "quality": "common"}],
            "discount": 0,
        }

        response = self.client.post(
            reverse("buy_shop_cart", kwargs={"character_id": self.character.id}),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        targets = {entry["target"] for entry in data["partials"]}
        self.assertEqual(targets, {"sheetWalletPanel", "sheetInventoryPanel"})
        inventory_html = next(entry["html"] for entry in data["partials"] if entry["target"] == "sheetInventoryPanel")
        self.assertIn("Heilkraut", inventory_html)

    def test_adjust_money_returns_wallet_partial(self):
        response = self.client.post(
            reverse("adjust_money", args=[self.character.id]),
            {"delta": "25"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["partials"][0]["target"], "sheetWalletPanel")
        self.character.refresh_from_db()
        self.assertEqual(self.character.money, 525)

    def test_adjust_experience_returns_experience_and_learning_budget_partials(self):
        response = self.client.post(
            reverse("adjust_experience", args=[self.character.id]),
            {"delta": "30"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        targets = {entry["target"] for entry in payload["partials"]}
        self.assertEqual(targets, {"sheetExperiencePanel", "learnBudgetPanel"})
        budget_html = next(entry["html"] for entry in payload["partials"] if entry["target"] == "learnBudgetPanel")
        self.assertIn("30 EP", budget_html)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 30)
        self.assertEqual(self.character.overall_experience, 30)

    def test_adjust_personal_fame_point_returns_fame_partial(self):
        response = self.client.post(
            reverse("adjust_personal_fame_point", args=[self.character.id]),
            {"delta": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["partials"][0]["target"], "sheetFamePanel")
        self.character.refresh_from_db()
        self.assertEqual(self.character.personal_fame_point, 1)
