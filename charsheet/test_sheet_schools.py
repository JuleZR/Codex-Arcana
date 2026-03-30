"""Regression tests for school panel rows on the character sheet."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from charsheet.constants import SCHOOL_COMBAT
from charsheet.models import (
    Character,
    CharacterSchool,
    CharacterSpecialization,
    CharacterTechnique,
    CharacterTechniqueChoice,
    Race,
    RaceTechnique,
    School,
    SchoolType,
    Specialization,
    Technique,
)


class SchoolPanelTests(TestCase):
    """Keep school techniques and learned specializations visible in one sheet panel."""

    def setUp(self):
        """Create one learned school with one technique and one specialization."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="schoolpanel", password="secret")
        self.race = Race.objects.create(name="Mensch")
        self.school_type = SchoolType.objects.create(name="Kampf", slug=SCHOOL_COMBAT)
        self.school = School.objects.create(name="Bardenkampf", type=self.school_type)
        self.technique = Technique.objects.create(
            school=self.school,
            level=2,
            name="Klingenlied",
            description="Eine erlernte Technik.",
        )
        self.specialization = Specialization.objects.create(
            school=self.school,
            name="Duellant",
            slug="duellant",
            description="Eine gewaehlte Spezialisierung.",
        )
        self.character = Character.objects.create(owner=self.user, name="Toma", race=self.race)
        CharacterSchool.objects.create(character=self.character, school=self.school, level=3)
        CharacterSpecialization.objects.create(character=self.character, specialization=self.specialization)
        self.client.force_login(self.user)

    def test_character_sheet_context_lists_school_specializations(self):
        """Learned school specializations should appear in the school panel rows."""
        response = self.client.get(reverse("character_sheet", args=[self.character.id]))

        self.assertEqual(response.status_code, 200)
        rows = response.context["school_technique_rows"]
        self.assertEqual(
            [(row["kind"], row["school_name"], row["entry_name"]) for row in rows],
            [
                ("technique", "Bardenkampf", "Klingenlied"),
                ("specialization", "Bardenkampf", "Duellant"),
            ],
        )

    def test_character_sheet_context_lists_race_techniques_first(self):
        """Race techniques should be shown in the panel before school-based entries."""
        race_technique = Technique.objects.create(
            name="Nachtsicht",
            description="Eine angeborene Rassenfaehigkeit.",
        )
        RaceTechnique.objects.create(race=self.race, technique=race_technique)

        response = self.client.get(reverse("character_sheet", args=[self.character.id]))

        self.assertEqual(response.status_code, 200)
        rows = response.context["school_technique_rows"]
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(
            (rows[0]["kind"], rows[0]["level"], rows[0]["school_name"], rows[0]["entry_name"]),
            ("race_technique", "", "Mensch", "Nachtsicht"),
        )

    def test_character_sheet_context_lists_technique_specialization_choices(self):
        """Technique choices that store a specialization should also surface in the school panel."""
        choice_technique = Technique.objects.create(
            school=self.school,
            level=3,
            name="Bardenfokus",
            choice_target_kind=Technique.ChoiceTargetKind.SPECIALIZATION,
            choice_limit=1,
        )
        CharacterTechnique.objects.create(character=self.character, technique=choice_technique)
        CharacterTechniqueChoice.objects.create(
            character=self.character,
            technique=choice_technique,
            selected_specialization=self.specialization,
        )

        response = self.client.get(reverse("character_sheet", args=[self.character.id]))

        self.assertEqual(response.status_code, 200)
        rows = response.context["school_technique_rows"]
        self.assertIn(
            ("technique_specialization", "Bardenkampf", "Duellant (Bardenfokus)"),
            [(row["kind"], row["school_name"], row["entry_name"]) for row in rows],
        )

    def test_character_sheet_context_marks_specification_techniques_as_editable(self):
        """Technique rows should expose editable specification state for learned techniques."""
        self.technique.has_specification = True
        self.technique.save(update_fields=["has_specification"])

        response = self.client.get(reverse("character_sheet", args=[self.character.id]))

        self.assertEqual(response.status_code, 200)
        row = next(
            row
            for row in response.context["school_technique_rows"]
            if row["kind"] == "technique" and row["entry_name"] == "Klingenlied: *"
        )
        self.assertTrue(row["can_edit_specification"])
        self.assertEqual(row["technique_id"], self.technique.id)

    def test_update_technique_specification_persists_single_word_value(self):
        """The sheet should save the technique specification through the backend view."""
        self.technique.has_specification = True
        self.technique.save(update_fields=["has_specification"])

        response = self.client.post(
            reverse("update_technique_specification", args=[self.character.id, self.technique.id]),
            {"specification_value": "Feuerschwert"},
        )

        self.assertRedirects(response, reverse("character_sheet", args=[self.character.id]))
        learned_technique = CharacterTechnique.objects.get(character=self.character, technique=self.technique)
        learned_technique.refresh_from_db()
        self.assertEqual(learned_technique.specification_value, "Feuerschwert")

        response = self.client.get(reverse("character_sheet", args=[self.character.id]))
        row = next(
            row
            for row in response.context["school_technique_rows"]
            if row["kind"] == "technique" and row["entry_name"] == "Klingenlied: Feuerschwert"
        )
        self.assertEqual(row["technique_id"], self.technique.id)
