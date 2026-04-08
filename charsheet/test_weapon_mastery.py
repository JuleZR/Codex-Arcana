"""Regression tests for Waffenmeister progression and automatic bonus resolution."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.constants import SCHOOL_COMBAT
from charsheet.engine import CharacterEngine
from charsheet.models import (
    Character,
    CharacterItem,
    CharacterSchool,
    CharacterWeaponMastery,
    CharacterWeaponMasteryArcana,
    DamageSource,
    Item,
    Race,
    Rune,
    School,
    SchoolType,
    WeaponStats,
)


class WeaponMasteryEngineTests(TestCase):
    """Verify non-situational Waffenmeister state resolves automatically."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="weaponmaster", password="secret")
        self.race = Race.objects.create(name="Human")
        self.school_type = SchoolType.objects.create(name="Combat", slug=SCHOOL_COMBAT)
        self.school = School.objects.create(name="Waffenmeister", type=self.school_type)
        self.character = Character.objects.create(
            owner=self.user,
            name="Aerlon",
            race=self.race,
            current_experience=50,
        )
        CharacterSchool.objects.create(character=self.character, school=self.school, level=10)
        self.damage_source = DamageSource.objects.create(name="Strength", short_name="ST", slug="ST")

    def _create_weapon(self, name: str) -> Item:
        weapon = Item.objects.create(name=name, item_type=Item.ItemType.WEAPON, stackable=False, price=10)
        WeaponStats.objects.create(
            item=weapon,
            min_st=5,
            damage_source=self.damage_source,
            damage_dice_amount=1,
            damage_dice_faces=10,
        )
        return weapon

    def test_weapon_mastery_progress_curve_resolves_from_pick_order_and_start_kind(self):
        """Stored order and first side should reproduce the rulebook's static bonus curve."""
        longsword = self._create_weapon("Langschwert")
        spear = self._create_weapon("Speer")
        quarterstaff = self._create_weapon("Kampfstab")

        CharacterWeaponMastery.objects.create(
            character=self.character,
            school=self.school,
            weapon_item=longsword,
            pick_order=1,
            first_bonus_kind=CharacterWeaponMastery.FirstBonusKind.MANEUVER,
        )
        CharacterWeaponMastery.objects.create(
            character=self.character,
            school=self.school,
            weapon_item=spear,
            pick_order=5,
            first_bonus_kind=CharacterWeaponMastery.FirstBonusKind.MANEUVER,
        )
        CharacterWeaponMastery.objects.create(
            character=self.character,
            school=self.school,
            weapon_item=quarterstaff,
            pick_order=10,
            first_bonus_kind=CharacterWeaponMastery.FirstBonusKind.MANEUVER,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.weapon_mastery_bonus_for_item(longsword), (5, 5))
        self.assertEqual(engine.weapon_mastery_bonus_for_item(spear), (3, 3))
        self.assertEqual(engine.weapon_mastery_bonus_for_item(quarterstaff), (1, 0))
        self.assertEqual(engine.weapon_mastery_quality_bonus_for_item(longsword), 1)

    def test_equipped_weapon_rows_include_weapon_mastery_bonuses(self):
        """Equipment display rows should surface computed maneuver and damage mastery bonuses."""
        claymore = self._create_weapon("Claymore")
        CharacterItem.objects.create(owner=self.character, item=claymore, equipped=True)
        CharacterWeaponMastery.objects.create(
            character=self.character,
            school=self.school,
            weapon_item=claymore,
            pick_order=2,
            first_bonus_kind=CharacterWeaponMastery.FirstBonusKind.DAMAGE,
        )

        engine = CharacterEngine(self.character)
        row = engine.equipped_weapon_rows()[0]

        self.assertEqual(row["weapon_mastery_maneuver_bonus"], 4)
        self.assertEqual(row["weapon_mastery_damage_bonus"], 5)
        self.assertEqual(row["weapon_mastery_quality_bonus"], 1)
        self.assertEqual(row["total_maneuver_modifier"], row["quality_maneuver_bonus"] + row["trait_maneuver_modifier"] + 4)
        self.assertEqual(row["dmg_mod"], row["base_dmg_mod"] + 5)

    def test_weapon_master_arcana_counts_bonus_capacity_and_learned_runes(self):
        """Rune and +1/+1 progress should remain queryable even beyond level 10 semantics."""
        rune_a = Rune.objects.create(name="Feuer")
        rune_b = Rune.objects.create(name="Licht")

        CharacterWeaponMasteryArcana.objects.create(
            character=self.character,
            school=self.school,
            kind=CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY,
        )
        CharacterWeaponMasteryArcana.objects.create(
            character=self.character,
            school=self.school,
            kind=CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY,
        )
        CharacterWeaponMasteryArcana.objects.create(
            character=self.character,
            school=self.school,
            kind=CharacterWeaponMasteryArcana.ArcanaKind.RUNE,
            rune=rune_a,
        )
        CharacterWeaponMasteryArcana.objects.create(
            character=self.character,
            school=self.school,
            kind=CharacterWeaponMasteryArcana.ArcanaKind.RUNE,
            rune=rune_b,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.weapon_mastery_arcana_bonus_capacity(), 2)
        self.assertEqual([rune.name for rune in engine.weapon_mastery_arcana_runes()], ["Feuer", "Licht"])
