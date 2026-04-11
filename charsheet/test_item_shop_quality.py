"""Regression tests for shop purchases with quality-aware item handling."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import DEADLY, DEFENSE_SR, QUALITY_FINE, QUALITY_LEGENDARY
from charsheet.engine import ItemEngine
from charsheet.constants import DEFENSE_VW
from charsheet.models import Character, CharacterItem, DamageSource, Item, MagicItemStats, Modifier, Race, Rune, WeaponStats


class ShopQualityPurchaseTests(TestCase):
    """Verify buy_shop_cart uses quality pricing and quality-aware inventory rows."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="shopper", password="secret")
        self.race = Race.objects.create(name="Human")
        self.character = Character.objects.create(
            owner=self.user,
            name="Nora",
            race=self.race,
            money=10_000,
        )
        self.client.force_login(self.user)

    def test_create_shop_item_persists_weapon_damage_source_and_runes(self):
        """Custom shop creation should support weapon damage sources and base runes."""
        rune = Rune.objects.create(name="Feuer", description="Setzt Klingen in Brand.")
        damage_source = DamageSource.objects.create(name="Stärke", short_name="ST", slug="st")

        response = self.client.post(
            reverse("create_shop_item", kwargs={"character_id": self.character.id}),
            {
                "name": "Runenklinge",
                "price": "250",
                "item_type": Item.ItemType.WEAPON,
                "default_quality": "common",
                "weight": "2",
                "size_class": "M",
                "weapon_damage_dice_amount": "1",
                "weapon_damage_dice_faces": "8",
                "weapon_damage_flat_operator": "-",
                "weapon_damage_flat_bonus": "1",
                "weapon_wield_mode": "1h",
                "weapon_damage_source": str(damage_source.id),
                "weapon_damage_type": DEADLY,
                "weapon_min_st": "2",
                "runes": [str(rune.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Runenklinge")
        self.assertEqual(list(item.runes.values_list("name", flat=True)), ["Feuer"])
        weapon_stats = WeaponStats.objects.get(item=item)
        self.assertEqual(weapon_stats.damage_source, damage_source)
        self.assertEqual(weapon_stats.damage_flat_operator, "-")
        self.assertEqual(weapon_stats.damage_flat_bonus, 1)
        self.assertEqual(ItemEngine(item).get_one_handed_damage_label(), "1w8-1")

    def test_item_engine_formats_division_operator_damage(self):
        """Damage labels should support slash operators such as 1w10/2."""
        damage_source = DamageSource.objects.create(name="Wucht", short_name="W", slug="wucht_test")
        item = Item.objects.create(
            name="Testnetz",
            price=50,
            item_type=Item.ItemType.WEAPON,
            stackable=False,
            default_quality="common",
        )
        WeaponStats.objects.create(
            item=item,
            min_st=1,
            damage_source=damage_source,
            damage_dice_amount=1,
            damage_dice_faces=10,
            damage_flat_bonus=2,
            damage_flat_operator="/",
            damage_type="B",
            wield_mode="1h",
        )

        self.assertEqual(ItemEngine(item).get_one_handed_damage_label(), "1w10/2")

    def test_create_shop_item_allows_two_handed_weapon_without_extra_profile(self):
        """Pure 2H weapons should use the base damage fields without requiring a second profile."""
        damage_source = DamageSource.objects.create(name="Schnitt Test", short_name="SCH", slug="schnitt_test")

        response = self.client.post(
            reverse("create_shop_item", kwargs={"character_id": self.character.id}),
            {
                "name": "Zweihand-Testwaffe",
                "price": "250",
                "item_type": Item.ItemType.WEAPON,
                "default_quality": "common",
                "weight": "3",
                "size_class": "G",
                "weapon_damage_dice_amount": "2",
                "weapon_damage_dice_faces": "10",
                "weapon_damage_flat_operator": "+",
                "weapon_damage_flat_bonus": "4",
                "weapon_wield_mode": "2h",
                "weapon_damage_source": str(damage_source.id),
                "weapon_damage_type": DEADLY,
                "weapon_min_st": "6",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Zweihand-Testwaffe")
        weapon_stats = WeaponStats.objects.get(item=item)
        self.assertEqual(weapon_stats.wield_mode, "2h")
        self.assertEqual(ItemEngine(item).get_one_handed_damage_label(), "2w10+4")
        self.assertIsNone(ItemEngine(item).get_two_handed_damage_label())

    def test_create_shop_item_creates_magic_item_stats_from_magic_checkbox(self):
        """Custom shop creation should create dedicated magic-item stats rows for magic-marked items."""
        response = self.client.post(
            reverse("create_shop_item", kwargs={"character_id": self.character.id}),
            {
                "name": "Amulett der Asche",
                "price": "500",
                "item_type": Item.ItemType.MISC,
                "is_magic": "on",
                "default_quality": "fine",
                "weight": "1",
                "size_class": "K",
                "magic_effect_summary": "+2 VW gegen Feuerzauber",
                "stackable": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Amulett der Asche")
        self.assertFalse(item.stackable)
        self.assertTrue(item.is_magic)
        magic_stats = MagicItemStats.objects.get(item=item)
        self.assertEqual(magic_stats.effect_summary, "+2 VW gegen Feuerzauber")

    def test_create_shop_item_creates_magic_item_modifier(self):
        """Magic-item creation should allow one direct flat modifier from the form."""
        response = self.client.post(
            reverse("create_shop_item", kwargs={"character_id": self.character.id}),
            {
                "name": "Amulett der Wachsamkeit",
                "price": "650",
                "item_type": Item.ItemType.MAGIC_ITEM,
                "default_quality": "fine",
                "weight": "1",
                "size_class": "K",
                "magic_effect_summary": "+2 VW",
                "magic_modifier_target_kind": Modifier.TargetKind.STAT,
                "magic_modifier_target_stat": DEFENSE_VW,
                "magic_modifier_value": "2",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Amulett der Wachsamkeit")
        modifier = Modifier.objects.get(source_object_id=item.id, source_content_type__model="item")
        self.assertEqual(modifier.target_kind, Modifier.TargetKind.STAT)
        self.assertEqual(modifier.target_slug, DEFENSE_VW)
        self.assertEqual(modifier.value, 2)
        self.assertEqual(modifier.effect_description, "")

    def test_create_shop_item_creates_multiple_magic_item_modifiers(self):
        """Magic-item creation should allow multiple direct modifiers from the form."""
        response = self.client.post(
            reverse("create_shop_item", kwargs={"character_id": self.character.id}),
            {
                "name": "Amulett der Doppelkraft",
                "price": "900",
                "item_type": Item.ItemType.MAGIC_ITEM,
                "default_quality": "fine",
                "weight": "1",
                "size_class": "K",
                "magic_effect_summary": "+2 VW und +1 SR",
                "magic_modifier_payloads": json.dumps(
                    [
                        {
                            "target_kind": Modifier.TargetKind.STAT,
                            "target_stat": DEFENSE_VW,
                            "value": 2,
                            "effect_description": "Wachsamkeit des Amuletts",
                        },
                        {
                            "target_kind": Modifier.TargetKind.STAT,
                            "target_stat": DEFENSE_SR,
                            "value": 1,
                            "effect_description": "Schutz des Amuletts",
                        },
                    ]
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Amulett der Doppelkraft")
        modifiers = list(
            Modifier.objects.filter(source_object_id=item.id, source_content_type__model="item")
            .order_by("target_slug")
            .values_list("target_slug", "value", "effect_description")
        )
        self.assertEqual(
            modifiers,
            [
                (DEFENSE_SR, 1, "Schutz des Amuletts"),
                (DEFENSE_VW, 2, "Wachsamkeit des Amuletts"),
            ],
        )

    def test_create_shop_item_allows_magic_weapon(self):
        """Weapons should be markable as magic items without changing their base category."""
        damage_source = DamageSource.objects.create(name="Geschick", short_name="GE", slug="geschick_test")

        response = self.client.post(
            reverse("create_shop_item", kwargs={"character_id": self.character.id}),
            {
                "name": "Klinge der Funken",
                "price": "700",
                "item_type": Item.ItemType.WEAPON,
                "is_magic": "on",
                "default_quality": "fine",
                "weight": "2",
                "size_class": "M",
                "weapon_damage_dice_amount": "1",
                "weapon_damage_dice_faces": "6",
                "weapon_damage_flat_operator": "+",
                "weapon_damage_flat_bonus": "2",
                "weapon_wield_mode": "1h",
                "weapon_damage_source": str(damage_source.id),
                "weapon_damage_type": DEADLY,
                "weapon_min_st": "2",
                "magic_modifier_payloads": json.dumps(
                    [
                        {
                            "target_kind": Modifier.TargetKind.STAT,
                            "target_stat": DEFENSE_VW,
                            "value": 1,
                            "effect_description": "Funkenhafter Schutz",
                        }
                    ]
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(name="Klinge der Funken")
        self.assertEqual(item.item_type, Item.ItemType.WEAPON)
        self.assertTrue(item.is_magic)
        self.assertTrue(MagicItemStats.objects.filter(item=item).exists())
        self.assertTrue(WeaponStats.objects.filter(item=item).exists())
        modifier = Modifier.objects.get(source_object_id=item.id, source_content_type__model="item")
        self.assertEqual(modifier.target_slug, DEFENSE_VW)
        self.assertEqual(modifier.value, 1)

    def test_buy_shop_cart_uses_quality_price_and_persists_quality(self):
        """Legendary quality should multiply price and be stored on CharacterItem."""
        item = Item.objects.create(
            name="Arcane Rope",
            price=100,
            item_type=Item.ItemType.MISC,
            stackable=True,
            default_quality="common",
        )
        payload = {
            "items": [
                {
                    "id": item.id,
                    "qty": 2,
                    "quality": QUALITY_LEGENDARY,
                }
            ],
            "discount": 0,
        }

        response = self.client.post(
            reverse("buy_shop_cart", kwargs={"character_id": self.character.id}),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.money, 6_000)
        purchased = CharacterItem.objects.get(owner=self.character, item=item, quality=QUALITY_LEGENDARY)
        self.assertEqual(purchased.amount, 2)

    def test_buy_shop_cart_creates_multiple_rows_for_non_stackable_items(self):
        """Two non-stackable purchases of the same quality should create two rows."""
        item = Item.objects.create(
            name="Short Sword",
            price=100,
            item_type=Item.ItemType.WEAPON,
            stackable=False,
            default_quality="common",
        )
        payload = {
            "items": [
                {"id": item.id, "qty": 1, "quality": QUALITY_FINE},
                {"id": item.id, "qty": 1, "quality": QUALITY_FINE},
            ],
            "discount": 0,
        }

        response = self.client.post(
            reverse("buy_shop_cart", kwargs={"character_id": self.character.id}),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertEqual(self.character.money, 9_600)
        self.assertEqual(
            CharacterItem.objects.filter(owner=self.character, item=item, quality=QUALITY_FINE).count(),
            2,
        )
