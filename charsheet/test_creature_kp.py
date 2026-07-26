from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import ATTR_WILL, QUALITY_COMMON
from charsheet.engine.creature_engine import CreatureEngine
from charsheet.models import Attribute, Creature, CreatureAttribute, Quality


class CreatureKpTests(TestCase):
    def setUp(self):
        self.creature = Creature.objects.create(
            name="Arkaner Wolf",
            slug="arkaner-wolf",
            quality=Quality.objects.get(code=QUALITY_COMMON),
            combat_speed=8,
            march_speed=16,
            sprint_speed=32,
        )
        willpower = Attribute.objects.create(name="Willenskraft", short_name=ATTR_WILL)
        CreatureAttribute.objects.update_or_create(
            creature=self.creature,
            attribute=willpower,
            defaults={"base_value": 7},
        )

    def test_creature_uses_name_without_a_separate_card_name_field(self):
        self.assertNotIn(
            "card_name",
            {field.name for field in Creature._meta.get_fields()},
        )
        self.assertEqual(self.creature.display_name, self.creature.name)

    def test_debug_card_renders_creature_without_card_name_field(self):
        response = self.client.get(
            reverse("debug_creature_card"),
            {"card": self.creature.slug},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.creature.name)

    def test_kp_and_potential_are_hidden_and_not_calculated_without_flag(self):
        engine = CreatureEngine(self.creature)

        self.assertIsNone(engine.kp())
        self.assertIsNone(engine.potential())
        html = render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": engine.card_context()},
        )
        self.assertNotIn("<strong>KP</strong>", html)
        self.assertNotIn("<strong>Pot</strong>", html)
        self.assertNotIn("creature-card__core-grid--two-rows", html)

    def test_kp_and_potential_use_formulas_and_render_on_creature_card(self):
        self.creature.has_kp = True
        self.creature.save(update_fields=["has_kp"])
        engine = CreatureEngine(self.creature)

        self.assertEqual(engine.kp(), 7)
        self.assertEqual(engine.potential(), 3)
        html = render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": engine.card_context()},
        )
        self.assertIn("<strong>KP</strong>", html)
        self.assertIn("<strong>Pot</strong>", html)
        self.assertIn("creature-card__core-grid--two-rows", html)
        self.assertIn("creature-card__core-row--arcane", html)
        self.assertLess(html.index("<strong>GW</strong>"), html.index("<strong>KP</strong>"))
        self.assertLess(html.index("<strong>KP</strong>"), html.index("<strong>Pot</strong>"))

    def test_kp_and_potential_overrides_replace_the_attribute_formulas(self):
        self.creature.has_kp = True
        self.creature.kp_override = 12
        self.creature.potential_override = 7
        self.creature.save(
            update_fields=["has_kp", "kp_override", "potential_override"]
        )

        engine = CreatureEngine(self.creature)

        self.assertEqual(engine.kp(), 12)
        self.assertEqual(engine.potential(), 7)
