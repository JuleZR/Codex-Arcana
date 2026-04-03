"""Integration tests for CharacterEngine delegating to ModifierEngine."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from charsheet.constants import DEFENSE_RS
from charsheet.models import Character, Modifier, Race


class ModifierEngineIntegrationTests(TestCase):
    """Ensure CharacterEngine delegates productive modifier totals to ModifierEngine."""

    def test_character_engine_stat_modifier_uses_central_modifier_engine(self):
        user = get_user_model().objects.create_user(username="modifier-engine", password="secret")
        race = Race.objects.create(name="Mensch")
        character = Character.objects.create(owner=user, name="Liora", race=race)
        race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=race_ct,
            source_object_id=race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=DEFENSE_RS,
            mode=Modifier.Mode.FLAT,
            value=3,
        )

        engine = character.engine

        self.assertEqual(engine.modifier_total_for_stat(DEFENSE_RS), 3)
        explanation = engine.explain_modifier_resolution("derived_stat", DEFENSE_RS)
        self.assertEqual(len(explanation), 1)
        self.assertEqual(explanation[0]["resolved_value"], 3)
