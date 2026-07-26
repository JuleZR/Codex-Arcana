from django.test import TestCase

from charsheet.admin import CreatureTraitSemanticEffectAdminForm
from charsheet.constants import QUALITY_COMMON
from charsheet.engine.creature_engine import CreatureEngine
from charsheet.models import (
    Creature,
    CreatureTrait,
    CreatureTraitDefinition,
    CreatureTraitSemanticEffect,
    Quality,
)


class CreatureSemanticEffectMultiplierTests(TestCase):
    def test_simple_value_accepts_decimal_comma(self):
        field = CreatureTraitSemanticEffectAdminForm.base_fields["simple_value"]

        self.assertEqual(field.clean("0,6666667"), 0.6666667)

    def test_movement_multiply_effect_uses_creature_value_as_its_base(self):
        quality, _created = Quality.objects.get_or_create(
            code=QUALITY_COMMON,
            defaults={"name": "Common"},
        )
        creature = Creature.objects.create(
            name="Schwimmer",
            slug="schwimmer",
            quality=quality,
            combat_speed=8,
            march_speed=20,
            sprint_speed=40,
            swimming_speed=30,
        )
        trait = CreatureTraitDefinition.objects.create(
            name="Langsamer Schwimmer",
            slug="langsamer-schwimmer",
            trait_type=CreatureTraitDefinition.TraitType.DIS,
        )
        CreatureTrait.objects.create(creature=creature, trait=trait)
        CreatureTraitSemanticEffect.objects.create(
            trait=trait,
            target_domain="movement",
            target_key="swim",
            operator="multiply",
            value="0.6666667",
        )

        engine = CreatureEngine(creature)

        self.assertAlmostEqual(engine.movement()["swim"], 20, places=5)
        self.assertEqual(engine.movement_display_text()["swim"], "20")
