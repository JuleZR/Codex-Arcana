"""Regression tests for editable skill specifications on the character sheet."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import ATTR_CHA, SKILL_KNOWLEDGE
from charsheet.models import Attribute, Character, CharacterSkill, Race, Skill, SkillCategory


class SkillSpecificationTests(TestCase):
    """Keep specification editing for skills such as Beruf simple and server-driven."""

    def setUp(self):
        """Create a minimal learned-skill fixture with one editable specification."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="skilltester", password="secret")
        self.race = Race.objects.create(name="Mensch")
        self.attribute = Attribute.objects.create(name="Charisma", short_name=ATTR_CHA)
        self.category = SkillCategory.objects.create(name="Wissen", slug=SKILL_KNOWLEDGE)
        self.skill = Skill.objects.create(
            name="Beruf",
            slug="beruf",
            category=self.category,
            attribute=self.attribute,
            requires_specification=True,
        )
        self.character = Character.objects.create(owner=self.user, name="Toma", race=self.race)
        self.character_skill = CharacterSkill.objects.create(
            character=self.character,
            skill=self.skill,
            level=3,
        )
        self.client.force_login(self.user)

    def test_character_sheet_context_marks_specification_skill_as_editable(self):
        """Prepared skill rows should expose the edit state without template-side logic."""
        response = self.client.get(reverse("character_sheet", args=[self.character.id]))

        self.assertEqual(response.status_code, 200)
        skill_rows = response.context["skill_rows"]
        self.assertEqual(len(skill_rows), 1)
        self.assertTrue(skill_rows[0]["can_edit_specification"])
        self.assertEqual(skill_rows[0]["display_name"], "Beruf: *")

    def test_update_skill_specification_persists_single_word_value(self):
        """The sheet should save the job label through the backend view, not client storage."""
        response = self.client.post(
            reverse("update_skill_specification", args=[self.character.id, self.character_skill.id]),
            {"specification": "Schmied"},
        )

        self.assertRedirects(response, reverse("character_sheet", args=[self.character.id]))
        self.character_skill.refresh_from_db()
        self.assertEqual(self.character_skill.specification, "Schmied")
        response = self.client.get(reverse("character_sheet", args=[self.character.id]))
        self.assertEqual(response.context["skill_rows"][0]["display_name"], "Beruf: Schmied")

    def test_update_skill_specification_rejects_multiple_words(self):
        """The helper form should keep the field easy to read by accepting one word only."""
        response = self.client.post(
            reverse("update_skill_specification", args=[self.character.id, self.character_skill.id]),
            {"specification": "Stadt Wache"},
        )

        self.assertRedirects(response, reverse("character_sheet", args=[self.character.id]))
        self.character_skill.refresh_from_db()
        self.assertEqual(self.character_skill.specification, "*")

    def test_update_skill_specification_allows_empty_value_as_star(self):
        """An empty entry should fall back to the default marker instead of failing."""
        response = self.client.post(
            reverse("update_skill_specification", args=[self.character.id, self.character_skill.id]),
            {"specification": ""},
        )

        self.assertRedirects(response, reverse("character_sheet", args=[self.character.id]))
        self.character_skill.refresh_from_db()
        self.assertEqual(self.character_skill.specification, "*")
        response = self.client.get(reverse("character_sheet", args=[self.character.id]))
        self.assertEqual(response.context["skill_rows"][0]["display_name"], "Beruf: *")
