"""Regression tests for signed encumbrance handling in sheet context values."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.constants import ATTR_GE, SKILL_COMBAT
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import Attribute, Character, CharacterAttribute, CharacterSkill, Race, Skill, SkillCategory
from charsheet.sheet_context import build_character_sheet_context


class LoadPenaltyContextTests(TestCase):
    """Keep encumbrance penalties consistent across skills and initiative displays."""

    def setUp(self):
        """Create a minimal character with one agility-based skill."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="loadtester", password="secret")
        self.race = Race.objects.create(name="Mensch")
        self.attribute = Attribute.objects.create(name="Geschick", short_name=ATTR_GE)
        self.category = SkillCategory.objects.create(name="Kampf", slug=SKILL_COMBAT)
        self.skill = Skill.objects.create(
            name="Ausweichen",
            slug="ausweichen",
            category=self.category,
            attribute=self.attribute,
        )
        self.character = Character.objects.create(owner=self.user, name="Toma", race=self.race)
        CharacterAttribute.objects.create(character=self.character, attribute=self.attribute, base_value=7)
        CharacterSkill.objects.create(character=self.character, skill=self.skill, level=5)

    def test_context_normalizes_load_penalty_for_positive_and_negative_raw_values(self):
        """The sheet should always subtract encumbrance from displayed derived values."""
        for raw_bel in (2, -2):
            with self.subTest(raw_bel=raw_bel), patch.object(CharacterEngine, "get_bel", return_value=raw_bel):
                self.character.__dict__.pop("_character_engine", None)

                context = build_character_sheet_context(self.character)
                skill_row = context["skill_rows"][0]

                self.assertEqual(context["core_stats"]["load_value"], -2)
                self.assertEqual(context["core_stats"]["initiative_display"], "+2")
                self.assertEqual(context["core_stats"]["initiative_with_load_display"], "0")
                self.assertEqual(skill_row["misc_mod"], "0")
                self.assertEqual(skill_row["total"], 7)
                self.assertEqual(skill_row["with_load_total"], 5)
