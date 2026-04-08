"""Regression tests for server-rendered character-sheet partial updates."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.models import ArmorStats, Character, CharacterItem, DamageSource, Item, Race, Rune, WeaponStats


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
        self.assertIn("damage_gauge", payload["partials"][0]["html"])
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

    def test_core_stats_partial_renders_breakdown_tooltips(self):
        """Core stat pills should expose the server-rendered breakdown tooltip text."""
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
        core_html = next(entry["html"] for entry in payload["partials"] if entry["target"] == "sheetCoreStatsPanel")
        self.assertIn("tooltip_target", core_html)
        self.assertIn("data-tooltip-side=\"right\"", core_html)
        self.assertIn("GE-Bonus/Malus", core_html)
        self.assertIn("Belastung", core_html)
        self.assertIn("Stufen in Schulen", core_html)

    def test_locked_equipment_cannot_be_unequipped(self):
        armor = Item.objects.create(
            name="Startpanzer",
            price=50,
            item_type=Item.ItemType.ARMOR,
            stackable=False,
            default_quality="common",
        )
        ArmorStats.objects.create(item=armor, rs_total=1, encumbrance=1, min_st=1)
        owned_item = CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            amount=1,
            equipped=True,
            equip_locked=True,
            quality="common",
        )

        response = self.client.post(
            reverse("toggle_equip", args=[owned_item.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        owned_item.refresh_from_db()
        self.assertTrue(owned_item.equipped)
        payload = response.json()
        armor_html = next(entry["html"] for entry in payload["partials"] if entry["target"] == "sheetArmorPanel")
        self.assertIn("disabled", armor_html)

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

    def test_update_character_item_runes_returns_equipment_partials(self):
        """Rune retrofit should persist on CharacterItem and refresh the visible panels."""
        armor = Item.objects.create(
            name="Schuppenpanzer",
            price=90,
            item_type=Item.ItemType.ARMOR,
            stackable=False,
            default_quality="common",
        )
        ArmorStats.objects.create(item=armor, rs_total=2, encumbrance=1, min_st=1)
        base_rune = Rune.objects.create(name="Basisrune", description="Schon am Gegenstand.")
        extra_rune = Rune.objects.create(name="Nachrüstrune", description="Wird separat eingesetzt.")
        armor.runes.add(base_rune)
        owned_item = CharacterItem.objects.create(owner=self.character, item=armor, amount=1, equipped=False, quality="common")

        response = self.client.post(
            reverse("update_character_item_runes", args=[owned_item.id]),
            {"runes": [str(base_rune.id), str(extra_rune.id)]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        targets = {entry["target"] for entry in payload["partials"]}
        self.assertEqual(targets, {"sheetInventoryPanel", "sheetArmorPanel", "sheetWeaponPanel"})
        owned_item.refresh_from_db()
        self.assertEqual(list(owned_item.runes.values_list("name", flat=True)), ["Nachrüstrune"])
        inventory_html = next(entry["html"] for entry in payload["partials"] if entry["target"] == "sheetInventoryPanel")
        self.assertIn("[[RUNE:Basisrune||]]", inventory_html)
        self.assertIn("[[RUNE:Nachr", inventory_html)

    def test_update_character_item_runes_allows_misc_items(self):
        """Misc items should also support rune retrofits and keep their tooltip content."""
        misc_item = Item.objects.create(
            name="Arkaner Fokus",
            price=40,
            item_type=Item.ItemType.MISC,
            stackable=False,
            default_quality="common",
            weight=2.5,
            description="Ein seltsamer Gegenstand.",
        )
        rune = Rune.objects.create(name="Speicherrune", description="Bindet Energie.")
        owned_item = CharacterItem.objects.create(owner=self.character, item=misc_item, amount=1, equipped=False, quality="common")

        response = self.client.post(
            reverse("update_character_item_runes", args=[owned_item.id]),
            {"runes": [str(rune.id)]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        owned_item.refresh_from_db()
        self.assertEqual(list(owned_item.runes.values_list("name", flat=True)), ["Speicherrune"])
        inventory_html = next(entry["html"] for entry in response.json()["partials"] if entry["target"] == "sheetInventoryPanel")
        self.assertIn("Arkaner Fokus", inventory_html)
        self.assertIn("[[RUNE:Speicherrune||]]", inventory_html)

    def test_weapon_panel_does_not_render_action_menu_for_equipped_weapons(self):
        """Equipped weapons should not show the inventory burger menu in the weapon panel."""
        damage_source = DamageSource.objects.create(name="Klinge", short_name="Kli", slug="klinge")
        weapon = Item.objects.create(
            name="Langschwert",
            price=80,
            item_type=Item.ItemType.WEAPON,
            stackable=False,
            default_quality="common",
        )
        WeaponStats.objects.create(
            item=weapon,
            damage_source=damage_source,
            damage_dice_amount=1,
            damage_dice_faces=8,
            damage_flat_bonus=0,
            min_st=1,
            wield_mode="1h",
        )
        owned_item = CharacterItem.objects.create(
            owner=self.character,
            item=weapon,
            amount=1,
            equipped=False,
            quality="common",
        )

        response = self.client.post(
            reverse("toggle_equip", args=[owned_item.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        weapon_html = next(entry["html"] for entry in response.json()["partials"] if entry["target"] == "sheetWeaponPanel")
        self.assertIn("Langschwert", weapon_html)
        self.assertNotIn("Waffen-Aktionen", weapon_html)
        self.assertNotIn("data-open-rune-window", weapon_html)
        self.assertIn("data-tooltip", weapon_html)
        self.assertIn("ST-Bonus/Malus", weapon_html)
        self.assertNotIn("= Basis-Mod.", weapon_html)

    def test_armor_panel_does_not_render_action_menu_for_equipped_armor(self):
        """Equipped armor should not show the inventory burger menu in the armor panel."""
        armor = Item.objects.create(
            name="Schuppenpanzer",
            price=90,
            item_type=Item.ItemType.ARMOR,
            stackable=False,
            default_quality="common",
        )
        ArmorStats.objects.create(item=armor, rs_total=2, encumbrance=1, min_st=1)
        owned_item = CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            amount=1,
            equipped=False,
            quality="common",
        )

        response = self.client.post(
            reverse("toggle_equip", args=[owned_item.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        armor_html = next(entry["html"] for entry in response.json()["partials"] if entry["target"] == "sheetArmorPanel")
        self.assertIn("Schuppenpanzer", armor_html)
        self.assertNotIn("Rüstungs-Aktionen", armor_html)
        self.assertNotIn("data-open-rune-window", armor_html)

    def test_equipped_armor_renders_working_unequip_form(self):
        """Equipped armor rows should render the active unequip form when not locked."""
        armor = Item.objects.create(
            name="Kettenhemd",
            price=120,
            item_type=Item.ItemType.ARMOR,
            stackable=False,
            default_quality="common",
        )
        ArmorStats.objects.create(item=armor, rs_total=3, encumbrance=2, min_st=2)
        owned_item = CharacterItem.objects.create(
            owner=self.character,
            item=armor,
            amount=1,
            equipped=False,
            quality="common",
        )

        response = self.client.post(
            reverse("toggle_equip", args=[owned_item.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        armor_html = next(entry["html"] for entry in response.json()["partials"] if entry["target"] == "sheetArmorPanel")
        self.assertIn(f'action="/character-item/{owned_item.id}/toggle-equip/"', armor_html)
        self.assertNotIn("disabled", armor_html)

    def test_equipped_clothing_renders_in_armor_panel_without_armor_stats(self):
        """Equipped clothing should be wearable and listed without affecting armor stats."""
        clothing = Item.objects.create(
            name="Reisekleidung",
            price=220,
            item_type=Item.ItemType.CLOTHING,
            stackable=False,
            default_quality="common",
            description="Unterwaesche, Hemd, Hose oder Rock, Struempfe, Kapuzenmantel, Lederstiefel und Guertel.",
        )
        owned_item = CharacterItem.objects.create(
            owner=self.character,
            item=clothing,
            amount=1,
            equipped=False,
            quality="common",
        )

        response = self.client.post(
            reverse("toggle_equip", args=[owned_item.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        inventory_html = next(entry["html"] for entry in payload["partials"] if entry["target"] == "sheetInventoryPanel")
        armor_html = next(entry["html"] for entry in payload["partials"] if entry["target"] == "sheetArmorPanel")
        self.assertNotIn("Reisekleidung", inventory_html)
        self.assertIn("Reisekleidung (Kleidung)", armor_html)
        self.assertIn('<span class="pill">0</span>', armor_html)
