"""Regression tests for race-based starting items."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from charsheet.engine.character_creation_engine import CharacterCreationEngine
from charsheet.models import Character, Item, Race, RaceStartingItem


class RaceStartingItemTests(TestCase):
    """Ensure equippable race starting items are auto-equipped and locked."""

    def test_equippable_race_starting_item_is_auto_equipped_and_locked(self):
        user = get_user_model().objects.create_user(username="racestarter", password="secret")
        race = Race.objects.create(name="Bestie")
        bite = Item.objects.create(
            name="Bissattacke",
            price=0,
            item_type=Item.ItemType.WEAPON,
            stackable=False,
            default_quality="common",
        )
        RaceStartingItem.objects.create(race=race, item=bite, amount=1, equipped=False)
        character = Character.objects.create(owner=user, name="Raka", race=race)

        CharacterCreationEngine.grant_race_starting_items(character)

        owned_item = character.characteritem_set.get(item=bite)
        self.assertTrue(owned_item.equipped)
        self.assertTrue(owned_item.equip_locked)

    def test_race_starting_item_clean_rejects_non_equippable_items(self):
        race = Race.objects.create(name="Bestie")
        herb = Item.objects.create(
            name="Heilkraut",
            price=0,
            item_type=Item.ItemType.CONSUM,
            stackable=True,
            default_quality="common",
        )
        starter = RaceStartingItem(race=race, item=herb, amount=1)

        with self.assertRaisesMessage(ValidationError, "always equipped"):
            starter.full_clean()
