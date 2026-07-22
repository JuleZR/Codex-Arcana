from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.constants import SCHOOL_ARCANE, SCHOOL_DIVINE
from charsheet.learning import process_learning_submission
from charsheet.models import Character, CharacterSchool, DruidCult, Race, School, SchoolType
from charsheet.sheet_context import build_character_sheet_context


class DruidPriestSchoolLockTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="druid-lock-user", password="pw")
        self.character = Character.objects.create(
            owner=user,
            race=Race.objects.create(name="Mensch"),
            name="Eiche",
            current_experience=100,
        )
        divine_type, _ = SchoolType.objects.get_or_create(slug=SCHOOL_DIVINE, defaults={"name": "Klerikal"})
        arcane_type, _ = SchoolType.objects.get_or_create(slug=SCHOOL_ARCANE, defaults={"name": "Arkan"})
        self.druid_school = School.objects.create(name="Druide", type=divine_type)
        self.priest_school = School.objects.create(name="Sonnenpriester", type=divine_type)
        self.arcane_school = School.objects.create(name="Feuermagie", type=arcane_type)
        DruidCult.objects.create(name="Steinkreis", slug="steinkreis-lock", school=self.druid_school)

    def test_active_druid_hides_priest_but_keeps_arcane_school_in_learning_menu(self):
        CharacterSchool.objects.create(character=self.character, school=self.druid_school, level=1)

        context = build_character_sheet_context(self.character)
        visible_school_ids = {
            row["id"]
            for group in context["learn_school_groups"]
            for row in group["rows"]
        }

        self.assertNotIn(self.priest_school.id, visible_school_ids)
        self.assertIn(self.arcane_school.id, visible_school_ids)

    def test_server_rejects_priest_school_when_druid_is_active(self):
        CharacterSchool.objects.create(character=self.character, school=self.druid_school, level=1)

        result, message = process_learning_submission(
            self.character,
            {f"learn_school_add_{self.priest_school.id}": "1"},
        )

        self.assertEqual(result, "error")
        self.assertIn("Priester-Schulen", message)
        self.assertFalse(CharacterSchool.objects.filter(character=self.character, school=self.priest_school).exists())

    def test_server_rejects_learning_druid_and_priest_school_together(self):
        result, message = process_learning_submission(
            self.character,
            {
                f"learn_school_add_{self.druid_school.id}": "1",
                f"learn_school_add_{self.priest_school.id}": "1",
            },
        )

        self.assertEqual(result, "error")
        self.assertIn("Priester-Schulen", message)

    def test_server_allows_arcane_school_when_druid_is_active(self):
        CharacterSchool.objects.create(character=self.character, school=self.druid_school, level=1)

        result, _message = process_learning_submission(
            self.character,
            {f"learn_school_add_{self.arcane_school.id}": "1"},
        )

        self.assertEqual(result, "success")
        self.assertTrue(CharacterSchool.objects.filter(character=self.character, school=self.arcane_school).exists())
