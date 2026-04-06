"""Regression tests for potential-affecting stat modifiers."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from charsheet.constants import ATTR_WILL, POTENTIAL
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import Attribute, Character, CharacterAttribute, Modifier, Race


class PotentialModifierTests(TestCase):
    """Ensure potential modifiers affect the calculated potential value."""

    def test_potential_modifier_reduces_effective_potential(self):
        user = get_user_model().objects.create_user(username="potentialtester", password="secret")
        race = Race.objects.create(name="Mensch")
        will = Attribute.objects.create(name="Willenskraft", short_name=ATTR_WILL)
        character = Character.objects.create(owner=user, name="Tarin", race=race)
        CharacterAttribute.objects.create(character=character, attribute=will, base_value=7)

        race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=race_ct,
            source_object_id=race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=POTENTIAL,
            mode=Modifier.Mode.FLAT,
            value=-2,
        )

        engine = CharacterEngine(character)

        self.assertEqual(engine.calculate_potential(), 1)
