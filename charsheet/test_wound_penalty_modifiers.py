"""Regression tests for wound-penalty-affecting stat modifiers."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from charsheet.constants import ATTR_KON, WOUND_PENALTY_MOD
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import Attribute, Character, CharacterAttribute, Modifier, Race


class WoundPenaltyModifierTests(TestCase):
    """Ensure wound penalty modifiers affect the effective wound malus."""

    def test_wound_penalty_modifier_increases_effective_wound_malus(self):
        user = get_user_model().objects.create_user(username="woundtester", password="secret")
        race = Race.objects.create(name="Mensch")
        kon = Attribute.objects.create(name="Konstitution", short_name=ATTR_KON)
        character = Character.objects.create(owner=user, name="Iven", race=race, current_damage=14)
        CharacterAttribute.objects.create(character=character, attribute=kon, base_value=7)

        race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=race_ct,
            source_object_id=race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=WOUND_PENALTY_MOD,
            mode=Modifier.Mode.FLAT,
            value=-2,
        )

        engine = CharacterEngine(character)

        self.assertEqual(engine.current_wound_stage(), ("Verletzt", -2))
        self.assertEqual(engine.current_wound_penalty_raw(), -4)
        self.assertEqual(engine.current_wound_penalty(), -4)
