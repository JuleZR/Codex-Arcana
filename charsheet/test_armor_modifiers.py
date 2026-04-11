"""Regression tests for armor-related stat modifiers."""

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.constants import DEFENSE_RS
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import ArmorStats, Character, CharacterItem, Item, Modifier, Race, RaceTechnique, Technique


class ArmorModifierTests(TestCase):
    """Ensure RS stat modifiers affect the derived total armor rating."""

    def test_rs_modifier_is_applied_to_total_armor_rating(self):
        user = get_user_model().objects.create_user(username="armortester", password="secret")
        race = Race.objects.create(name="Mensch")
        character = Character.objects.create(owner=user, name="Iria", race=race)
        armor = Item.objects.create(
            name="Kettenhemd",
            price=50,
            item_type=Item.ItemType.ARMOR,
            stackable=False,
            default_quality="common",
        )
        ArmorStats.objects.create(item=armor, rs_total=2, encumbrance=1, min_st=1)
        CharacterItem.objects.create(owner=character, item=armor, amount=1, equipped=True, quality="common")

        race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=race_ct,
            source_object_id=race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=DEFENSE_RS,
            mode=Modifier.Mode.FLAT,
            value=2,
        )

        self.assertEqual(CharacterEngine(character).get_grs(), 4)

    def test_race_technique_modifier_is_applied_to_total_armor_rating(self):
        user = get_user_model().objects.create_user(username="racers", password="secret")
        race = Race.objects.create(name="Krask")
        character = Character.objects.create(owner=user, name="TESTrik", race=race)
        technique = Technique.objects.create(
            name="Schuppenhaut",
            description="Natuerlicher Ruestungsschutz.",
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
        )
        RaceTechnique.objects.create(race=race, technique=technique)

        technique_ct = ContentType.objects.get_for_model(Technique, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=technique_ct,
            source_object_id=technique.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=DEFENSE_RS,
            mode=Modifier.Mode.FLAT,
            value=1,
        )

        engine = CharacterEngine(character)
        self.assertEqual(engine.modifier_total_for_stat(DEFENSE_RS), 1)
        self.assertEqual(engine.get_grs(), 1)

    def test_equipped_clothing_does_not_affect_armor_values(self):
        user = get_user_model().objects.create_user(username="clothestester", password="secret")
        race = Race.objects.create(name="Mensch")
        character = Character.objects.create(owner=user, name="Talea", race=race)
        clothing = Item.objects.create(
            name="Reisekleidung",
            price=220,
            item_type=Item.ItemType.CLOTHING,
            stackable=False,
            default_quality="common",
        )
        CharacterItem.objects.create(owner=character, item=clothing, amount=1, equipped=True, quality="common")

        engine = CharacterEngine(character)
        self.assertEqual(engine.get_grs(), 0)
        self.assertEqual(engine.get_bel(), 0)
        self.assertEqual(engine.get_ms(), 0)

    def test_equipped_magic_item_modifier_is_applied(self):
        user = get_user_model().objects.create_user(username="magictester", password="secret")
        race = Race.objects.create(name="Mensch")
        character = Character.objects.create(owner=user, name="Selene", race=race)
        magic_item = Item.objects.create(
            name="Amulett des Schutzes",
            price=500,
            item_type=Item.ItemType.MAGIC_ITEM,
            stackable=False,
            default_quality="common",
        )
        CharacterItem.objects.create(owner=character, item=magic_item, amount=1, equipped=True, quality="common")

        item_ct = ContentType.objects.get_for_model(Item, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=item_ct,
            source_object_id=magic_item.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=DEFENSE_RS,
            mode=Modifier.Mode.FLAT,
            value=3,
        )

        self.assertEqual(CharacterEngine(character).get_grs(), 3)
