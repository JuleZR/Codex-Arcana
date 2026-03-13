"""Regression tests for generic school-bound specializations."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from charsheet.constants import SCHOOL_COMBAT
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import (
    Character,
    CharacterSchool,
    CharacterSpecialization,
    CharacterTechnique,
    Race,
    School,
    SchoolType,
    Specialization,
    Technique,
)


class SchoolSpecializationTests(TestCase):
    """Verify specialization models and engine helpers work without seeded data."""

    def setUp(self):
        """Create a minimal character and school fixture without any skills."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="specialist", password="secret")
        self.race = Race.objects.create(name="Human")
        self.school_type = SchoolType.objects.create(name="Combat", slug=SCHOOL_COMBAT)
        self.bard_school = School.objects.create(name="Bardic Combat", type=self.school_type)
        self.other_school = School.objects.create(name="Blade College", type=self.school_type)
        self.character = Character.objects.create(
            owner=self.user,
            name="Lyra",
            race=self.race,
        )
        CharacterSchool.objects.create(character=self.character, school=self.bard_school, level=5)

        self.awakened_auto = Technique.objects.create(
            school=self.bard_school,
            name="Erwachte Begabung",
            level=2,
            support_level=Technique.SupportLevel.DESCRIPTIVE,
            is_choice_placeholder=True,
            choice_group="bard_level_2",
            selection_notes="Unlock one school specialization slot.",
            specialization_slot_grants=1,
        )
        self.rescue = Technique.objects.create(
            school=self.bard_school,
            name="Rettung der Jungfrau",
            level=5,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.STRUCTURED,
            choice_group="bard_level_5",
        )
        self.awakened_choice = Technique.objects.create(
            school=self.bard_school,
            name="Erwachte Begabung",
            level=5,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.DESCRIPTIVE,
            is_choice_placeholder=True,
            choice_group="bard_level_5",
            selection_notes="Unlock one additional school specialization slot.",
            specialization_slot_grants=1,
        )
        self.other_school_technique = Technique.objects.create(
            school=self.other_school,
            name="Blade Insight",
            level=1,
            support_level=Technique.SupportLevel.STRUCTURED,
        )

    def test_specialization_slug_is_unique_per_school(self):
        """The same specialization slug must not be duplicated within one school."""
        Specialization.objects.create(
            school=self.bard_school,
            name="Voice of Legends",
            slug="voice-of-legends",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Specialization.objects.create(
                    school=self.bard_school,
                    name="Echo of Legends",
                    slug="voice-of-legends",
                    support_level=Specialization.SupportLevel.DESCRIPTIVE,
                )

        duplicate_slug_other_school = Specialization(
            school=self.other_school,
            name="Voice of Legends",
            slug="voice-of-legends",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        duplicate_slug_other_school.full_clean()

    def test_character_specialization_cannot_be_saved_twice_for_one_character(self):
        """A character must not store the same specialization more than once."""
        specialization = Specialization.objects.create(
            school=self.bard_school,
            name="Ballad Mastery",
            slug="ballad-mastery",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        CharacterSpecialization.objects.create(
            character=self.character,
            specialization=specialization,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CharacterSpecialization.objects.create(
                    character=self.character,
                    specialization=specialization,
                )

    def test_character_specialization_validates_school_and_source_technique(self):
        """Specializations must belong to a learned school and match the source technique school."""
        specialization = Specialization.objects.create(
            school=self.bard_school,
            name="Stage Presence",
            slug="stage-presence",
            support_level=Specialization.SupportLevel.DESCRIPTIVE,
        )
        invalid_entry = CharacterSpecialization(
            character=self.character,
            specialization=specialization,
            source_technique=self.other_school_technique,
        )

        with self.assertRaises(ValidationError):
            invalid_entry.full_clean()

        stranger = Character.objects.create(owner=self.user, name="Mira", race=self.race)
        missing_school_entry = CharacterSpecialization(
            character=stranger,
            specialization=specialization,
        )

        with self.assertRaises(ValidationError):
            missing_school_entry.full_clean()

    def test_engine_handles_empty_specialization_definitions_without_errors(self):
        """The engine must stay stable when neither slots nor specialization definitions exist."""
        engine = CharacterEngine(self.character)

        self.assertEqual(engine.specialization_slot_count(self.bard_school), 0)
        self.assertEqual(engine.character_specializations(self.bard_school), [])
        self.assertEqual(engine.open_specialization_slot_count(self.bard_school), 0)
        self.assertEqual(engine.available_specializations(self.bard_school), [])

    def test_engine_counts_open_specialization_slots_from_learned_techniques(self):
        """Learned techniques with specialization grants should open matching slots."""
        specialization = Specialization.objects.create(
            school=self.bard_school,
            name="Epic Chorus",
            slug="epic-chorus",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        CharacterTechnique.objects.create(character=self.character, technique=self.awakened_auto)
        CharacterSpecialization.objects.create(
            character=self.character,
            specialization=specialization,
            source_technique=self.awakened_auto,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.specialization_slot_count(self.bard_school), 1)
        self.assertEqual(len(engine.character_specializations(self.bard_school)), 1)
        self.assertEqual(engine.open_specialization_slot_count(self.bard_school), 0)

    def test_available_but_unlearned_techniques_do_not_grant_specialization_slots(self):
        """Techniques only shown as available must not create slots before CharacterTechnique exists."""
        engine = CharacterEngine(self.character)

        self.assertTrue(engine.technique_state(self.awakened_choice)["available"])
        self.assertFalse(engine.technique_state(self.awakened_choice)["learned"])
        self.assertEqual(engine.specialization_slot_count(self.bard_school), 0)
        self.assertEqual(engine.open_specialization_slot_count(self.bard_school), 0)

    def test_engine_returns_only_active_unlearned_specializations(self):
        """Inactive or already learned specializations must not show up as available options."""
        learned_specialization = Specialization.objects.create(
            school=self.bard_school,
            name="Heroic Ballad",
            slug="heroic-ballad",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        available_specialization = Specialization.objects.create(
            school=self.bard_school,
            name="Silver Voice",
            slug="silver-voice",
            support_level=Specialization.SupportLevel.COMPUTED,
            sort_order=1,
        )
        Specialization.objects.create(
            school=self.bard_school,
            name="Silent Echo",
            slug="silent-echo",
            support_level=Specialization.SupportLevel.DESCRIPTIVE,
            is_active=False,
            sort_order=2,
        )
        CharacterTechnique.objects.create(character=self.character, technique=self.awakened_auto)
        CharacterSpecialization.objects.create(
            character=self.character,
            specialization=learned_specialization,
            source_technique=self.awakened_auto,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(
            [specialization.slug for specialization in engine.available_specializations(self.bard_school)],
            ["silver-voice"],
        )

    def test_bard_level_choices_stay_separate_from_specialization_slots(self):
        """Available choice techniques must not count as specialization slots before they are learned."""
        engine = CharacterEngine(self.character)

        self.assertTrue(engine.technique_state(self.awakened_choice)["available"])
        self.assertFalse(engine.technique_state(self.awakened_choice)["learned"])
        self.assertEqual(engine.technique_state(self.awakened_choice)["specialization_slot_grants"], 1)
        self.assertEqual(engine.specialization_slot_count(self.bard_school), 0)

        CharacterTechnique.objects.create(character=self.character, technique=self.awakened_choice)
        refreshed_engine = CharacterEngine(self.character)

        self.assertEqual(refreshed_engine.specialization_slot_count(self.bard_school), 1)
        self.assertEqual(refreshed_engine.open_specialization_slot_count(self.bard_school), 1)
