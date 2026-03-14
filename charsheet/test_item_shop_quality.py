"""Regression tests for shop purchases with quality-aware item handling."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import QUALITY_FINE, QUALITY_LEGENDARY
from charsheet.models import Character, CharacterItem, Item, Race


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
