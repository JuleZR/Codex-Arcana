"""Regression tests for progression-aware learning submissions."""

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.test import TestCase

from charsheet.constants import SCHOOL_COMBAT, SKILL_SOCIAL
from charsheet.learning import process_learning_submission
from charsheet.learning_progression import build_learning_progression_context, choice_field_name, race_choice_field_name
from charsheet.models import (
    Attribute,
    Character,
    CharacterSkill,
    CharacterRaceChoice,
    CharacterSchool,
    CharacterSchoolPath,
    CharacterSpecialization,
    CharacterTechnique,
    CharacterTechniqueChoice,
    Modifier,
    RaceChoiceDefinition,
    TechniqueChoiceBlock,
    TechniqueChoiceDefinition,
    Race,
    School,
    SchoolPath,
    SchoolType,
    Skill,
    SkillCategory,
    Specialization,
    Technique,
    Trait,
)


class LearningProgressionSubmissionTests(TestCase):
    """Verify the learning panel can persist new progression-side decisions."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="learner", password="secret")
        self.race = Race.objects.create(name="Human")
        self.school_type = SchoolType.objects.create(name="Combat", slug=SCHOOL_COMBAT)
        self.school = School.objects.create(name="Bardic Combat", type=self.school_type)
        self.character = Character.objects.create(
            owner=self.user,
            name="Lyra",
            race=self.race,
            current_experience=20,
        )
        CharacterSchool.objects.create(character=self.character, school=self.school, level=5)

        self.attribute = Attribute.objects.create(name="Charisma", short_name="CHA")
        self.skill_category = SkillCategory.objects.create(name="Performance", slug=SKILL_SOCIAL)
        self.music = Skill.objects.create(
            name="Music",
            slug="music",
            category=self.skill_category,
            family="performance",
            attribute=self.attribute,
        )

    def test_learning_submission_unlocks_path_then_learns_path_bound_technique(self):
        """Path selection and a newly available path-bound technique should work in one submit."""
        school_path = SchoolPath.objects.create(school=self.school, name="Choir")
        technique = Technique.objects.create(
            school=self.school,
            path=school_path,
            name="Chorus Discipline",
            level=2,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.STRUCTURED,
        )

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_school_path_{self.school.id}": str(school_path.id),
                f"learn_take_technique_{technique.id}": "1",
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("Pfadwahl", message)
        self.assertTrue(
            CharacterSchoolPath.objects.filter(
                character=self.character,
                school=self.school,
                path=school_path,
            ).exists()
        )
        self.assertTrue(CharacterTechnique.objects.filter(character=self.character, technique=technique).exists())

    def test_learning_submission_can_learn_slot_technique_and_pick_specialization(self):
        """A newly learned technique should open a specialization slot usable in the same submit."""
        technique = Technique.objects.create(
            school=self.school,
            name="Awakened Gift",
            level=2,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.DESCRIPTIVE,
            specialization_slot_grants=1,
            selection_notes="Unlock one school specialization slot.",
        )
        specialization = Specialization.objects.create(
            school=self.school,
            name="Silver Voice",
            slug="silver-voice",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_take_technique_{technique.id}": "1",
                f"learn_specialization_pick_{self.school.id}_0": str(specialization.id),
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("Spezialisierung", message)
        self.assertTrue(CharacterTechnique.objects.filter(character=self.character, technique=technique).exists())
        self.assertTrue(
            CharacterSpecialization.objects.filter(
                character=self.character,
                specialization=specialization,
            ).exists()
        )

    def test_learning_submission_can_store_missing_skill_choice(self):
        """Missing skill choices should be writable through the learning submission."""
        technique = Technique.objects.create(
            school=self.school,
            name="Signature Piece",
            level=1,
            support_level=Technique.SupportLevel.COMPUTED,
            choice_target_kind=Technique.ChoiceTargetKind.SKILL,
            choice_limit=1,
            choice_bonus_value=2,
            selection_notes="Choose one performance skill.",
        )
        CharacterTechnique.objects.create(character=self.character, technique=technique)

        level, message = process_learning_submission(
            self.character,
            {
                choice_field_name(Technique.ChoiceTargetKind.SKILL, technique.id): str(self.music.id),
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("Auswahl", message)
        choice = CharacterTechniqueChoice.objects.get(character=self.character, technique=technique)
        self.assertEqual(choice.selected_skill_id, self.music.id)

    def test_learning_submission_applies_zero_cost_skill_swap(self):
        """A zero-sum skill reallocation should still be persisted."""
        second_skill = Skill.objects.create(
            name="Singing",
            slug="singing",
            category=self.skill_category,
            family="performance",
            attribute=self.attribute,
        )
        CharacterSkill.objects.create(character=self.character, skill=self.music, level=2)
        CharacterSkill.objects.create(character=self.character, skill=second_skill, level=1)

        level, message = process_learning_submission(
            self.character,
            {
                "learn_skill_add_music": "-1",
                "learn_skill_add_singing": "1",
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("Aenderungen gespeichert", message)
        self.assertEqual(CharacterSkill.objects.get(character=self.character, skill=self.music).level, 1)
        self.assertEqual(CharacterSkill.objects.get(character=self.character, skill=second_skill).level, 2)

    def test_learning_submission_can_store_missing_specialization_choice(self):
        """Technique choices that point at school specializations should also be supported."""
        technique = Technique.objects.create(
            school=self.school,
            name="Focused Muse",
            level=1,
            support_level=Technique.SupportLevel.STRUCTURED,
            choice_target_kind=Technique.ChoiceTargetKind.SPECIALIZATION,
            choice_limit=1,
            selection_notes="Choose one school specialization.",
        )
        specialization = Specialization.objects.create(
            school=self.school,
            name="Echo Verse",
            slug="echo-verse",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        CharacterTechnique.objects.create(character=self.character, technique=technique)

        level, message = process_learning_submission(
            self.character,
            {
                choice_field_name(Technique.ChoiceTargetKind.SPECIALIZATION, technique.id): str(specialization.id),
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("Auswahl", message)
        choice = CharacterTechniqueChoice.objects.get(character=self.character, technique=technique)
        self.assertEqual(choice.selected_specialization_id, specialization.id)

    def test_learning_submission_can_store_race_skill_choice(self):
        """Race choices should persist required skill picks through the learning form."""
        craft = SkillCategory.objects.create(name="Craft", slug="craft")
        leatherwork = Skill.objects.create(
            name="Leatherwork",
            slug="leatherwork",
            category=craft,
            attribute=self.attribute,
            family="craft",
        )
        definition = RaceChoiceDefinition.objects.create(
            race=self.race,
            name="Craft Focus",
            target_kind=Technique.ChoiceTargetKind.SKILL,
            description="Choose one craft skill.",
            allowed_skill_category=craft,
        )
        race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=race_ct,
            source_object_id=self.race.id,
            target_kind=Modifier.TargetKind.SKILL,
            target_race_choice_definition=definition,
            mode=Modifier.Mode.FLAT,
            value=2,
        )

        level, message = process_learning_submission(
            self.character,
            {
                race_choice_field_name(Technique.ChoiceTargetKind.SKILL, definition.id): str(leatherwork.id),
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("Auswahl", message)
        choice = CharacterRaceChoice.objects.get(
            character=self.character,
            definition=definition,
        )
        self.assertEqual(choice.selected_skill_id, leatherwork.id)
        self.assertEqual(self.character.get_engine(refresh=True)._resolve_choice_skill_modifiers(leatherwork.id), 2)

    def test_learning_submission_can_learn_advantage_via_ep(self):
        """Advantages should be learnable via EP using engine-backed trait costs."""
        advantage = Trait.objects.create(
            name="Wealthy",
            slug="wealthy",
            trait_type=Trait.TraitType.ADV,
            description="Own more than most.",
            min_level=1,
            max_level=2,
            points_per_level=3,
        )

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_trait_add_{advantage.slug}": "1",
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("3 EP ausgegeben", message)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 17)
        self.assertEqual(self.character.charactertrait_set.get(trait=advantage).trait_level, 1)

    def test_learning_submission_can_learn_and_unlearn_disadvantage_via_ep(self):
        """Disadvantages should also cost EP in post-creation learning."""
        disadvantage = Trait.objects.create(
            name="Debt",
            slug="debt",
            trait_type=Trait.TraitType.DIS,
            description="You owe dangerous people money.",
            min_level=1,
            max_level=2,
            points_per_level=4,
        )

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_trait_add_{disadvantage.slug}": "1",
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("4 EP ausgegeben", message)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 16)

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_trait_add_{disadvantage.slug}": "-1",
            },
        )

        self.assertEqual(level, "success")
        self.assertIn("4 EP ausgegeben", message)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_experience, 12)
        self.assertFalse(self.character.charactertrait_set.filter(trait=disadvantage).exists())


    def test_learning_context_exposes_pending_school_path_decision(self):
        """Open path choices should be exposed as dedicated pending decisions."""
        school_path = SchoolPath.objects.create(school=self.school, name="Choir")

        context = build_learning_progression_context(self.character, engine=self.character.get_engine(refresh=True))

        self.assertEqual(context["learn_pending_choice_count"], 1)
        decision = context["learn_pending_decisions"][0]
        self.assertEqual(decision["kind"], "school_path")
        self.assertEqual(decision["options"][0]["submit_name"], f"learn_school_path_{self.school.id}")
        self.assertEqual(decision["options"][0]["submit_value"], str(school_path.id))

    def test_learning_context_exposes_pending_race_choice(self):
        """Race choices with missing required selections should appear in the learning context."""
        craft = SkillCategory.objects.create(name="Craft", slug="craft")
        Skill.objects.create(
            name="Stonework",
            slug="stonework",
            category=craft,
            attribute=self.attribute,
            family="craft",
        )
        definition = RaceChoiceDefinition.objects.create(
            race=self.race,
            name="Craft Focus",
            target_kind=Technique.ChoiceTargetKind.SKILL,
            description="Choose one craft skill.",
            allowed_skill_category=craft,
        )

        context = build_learning_progression_context(self.character, engine=self.character.get_engine(refresh=True))

        race_rows = [row for row in context["learn_choice_rows"] if row.get("choice_scope") == "race"]
        self.assertEqual(len(race_rows), 1)
        self.assertEqual(race_rows[0]["definition_id"], definition.id)
        self.assertEqual(race_rows[0]["race_name"], self.race.name)

    def test_learning_context_groups_open_technique_block_as_single_pending_decision(self):
        """Technique choice blocks should arrive as one grouped modal decision with multiple options."""
        block = TechniqueChoiceBlock.objects.create(
            school=self.school,
            name="Stufe-2-Wahl",
            level=2,
            min_choices=1,
            max_choices=1,
            description="Waehle genau eine Technik aus diesem Block.",
        )
        first = Technique.objects.create(
            school=self.school,
            name="Verse A",
            level=2,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.STRUCTURED,
            choice_block=block,
        )
        second = Technique.objects.create(
            school=self.school,
            name="Verse B",
            level=2,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.STRUCTURED,
            choice_block=block,
        )

        context = build_learning_progression_context(self.character, engine=self.character.get_engine(refresh=True))

        pending = [decision for decision in context["learn_pending_decisions"] if decision["kind"] == "technique_pick"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["selection_group_id"], f"technique-block:{block.id}")
        self.assertCountEqual(
            [option["submit_name"] for option in pending[0]["options"]],
            [f"learn_take_technique_{first.id}", f"learn_take_technique_{second.id}"],
        )

    def test_reducing_school_resets_dependent_paths_choices_and_specializations(self):
        """Lowering a school back to zero should remove dependent progression state."""
        school_path = SchoolPath.objects.create(school=self.school, name="Choir")
        path_technique = Technique.objects.create(
            school=self.school,
            path=school_path,
            name="Chorus Discipline",
            level=5,
            support_level=Technique.SupportLevel.STRUCTURED,
        )
        choice_technique = Technique.objects.create(
            school=self.school,
            name="Focused Muse",
            level=1,
            support_level=Technique.SupportLevel.STRUCTURED,
            choice_target_kind=Technique.ChoiceTargetKind.SPECIALIZATION,
            choice_limit=1,
        )
        specialization = Specialization.objects.create(
            school=self.school,
            name="Echo Verse",
            slug="echo-verse",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        CharacterSchoolPath.objects.create(character=self.character, school=self.school, path=school_path)
        CharacterTechnique.objects.create(character=self.character, technique=path_technique)
        CharacterTechnique.objects.create(character=self.character, technique=choice_technique)
        CharacterSpecialization.objects.create(character=self.character, specialization=specialization)
        CharacterTechniqueChoice.objects.create(
            character=self.character,
            technique=choice_technique,
            selected_specialization=specialization,
        )

        level, message = process_learning_submission(
            self.character,
            {
                f"learn_school_add_{self.school.id}": "-5",
            },
        )

        self.assertEqual(level, "info")
        self.assertFalse(CharacterSchool.objects.filter(character=self.character, school=self.school).exists())
        self.assertFalse(CharacterSchoolPath.objects.filter(character=self.character, school=self.school).exists())
        self.assertFalse(CharacterTechnique.objects.filter(character=self.character, technique=path_technique).exists())
        self.assertFalse(CharacterTechnique.objects.filter(character=self.character, technique=choice_technique).exists())
        self.assertFalse(CharacterTechniqueChoice.objects.filter(character=self.character, technique=choice_technique).exists())
        self.assertFalse(CharacterSpecialization.objects.filter(character=self.character, specialization=specialization).exists())
