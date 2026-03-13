"""Focused regression tests for technique support levels and choice metadata."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from charsheet.constants import ATTR_GE, INITIATIVE, SCHOOL_COMBAT, SKILL_COMBAT
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterSchool,
    CharacterSkill,
    CharacterTechnique,
    CharacterTechniqueChoice,
    Modifier,
    Race,
    School,
    SchoolType,
    Skill,
    SkillCategory,
    SkillFamily,
    Technique,
)


class TechniqueSupportLevelTests(TestCase):
    """Verify technique support levels stay visible without forcing fake automation."""

    def setUp(self):
        """Create the shared minimum combat-school fixture."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="tester", password="secret")
        self.race = Race.objects.create(name="Human")
        self.school_type = SchoolType.objects.create(name="Combat", slug=SCHOOL_COMBAT)
        self.school = School.objects.create(name="Bardic Combat", type=self.school_type)
        self.character = Character.objects.create(
            owner=self.user,
            name="Lyra",
            race=self.race,
        )
        self.ge = Attribute.objects.create(name="Geschicklichkeit", short_name=ATTR_GE)
        CharacterAttribute.objects.create(character=self.character, attribute=self.ge, base_value=5)
        self.skill_category = SkillCategory.objects.create(name="Combat", slug=SKILL_COMBAT)
        self.skill_family = SkillFamily.objects.create(name="Songs", slug="songs")
        self.music = Skill.objects.create(
            name="Music",
            slug="music",
            category=self.skill_category,
            family=self.skill_family,
            attribute=self.ge,
        )
        self.oratory = Skill.objects.create(
            name="Oratory",
            slug="oratory",
            category=self.skill_category,
            family=self.skill_family,
            attribute=self.ge,
        )
        self.duel = Skill.objects.create(
            name="Duel",
            slug="duel",
            category=self.skill_category,
            attribute=self.ge,
        )
        CharacterSkill.objects.create(character=self.character, skill=self.music, level=4)
        CharacterSkill.objects.create(character=self.character, skill=self.oratory, level=3)
        CharacterSkill.objects.create(character=self.character, skill=self.duel, level=2)
        CharacterSchool.objects.create(character=self.character, school=self.school, level=3)

    def test_only_computed_passive_techniques_contribute_modifiers(self):
        """Structured technique rows must not leak passive stat bonuses into the engine."""
        computed = Technique.objects.create(
            school=self.school,
            name="Battle Rhythm",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
        )
        structured = Technique.objects.create(
            school=self.school,
            name="Crowd Pulse",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.STRUCTURED,
        )
        technique_ct = ContentType.objects.get_for_model(Technique, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=technique_ct,
            source_object_id=computed.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=2,
        )
        Modifier.objects.create(
            source_content_type=technique_ct,
            source_object_id=structured.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=99,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.calculate_initiative(), 2)
        self.assertEqual(
            [tech.name for tech in engine.effective_passive_techniques()],
            ["Battle Rhythm"],
        )

    def test_descriptive_and_choice_metadata_stay_visible_in_technique_state(self):
        """Technique states should expose support and choice metadata without computing effects."""
        technique = Technique.objects.create(
            school=self.school,
            name="Erwachte Begabung",
            level=2,
            technique_type=Technique.TechniqueType.ACTIVE,
            acquisition_type=Technique.AcquisitionType.CHOICE,
            support_level=Technique.SupportLevel.DESCRIPTIVE,
            is_choice_placeholder=True,
            choice_group="bard_awakened_gift_l2",
            selection_notes="Choose one fitting artistic focus or a school-specific variant.",
            action_type=Technique.ActionType.ACTION,
            usage_type=Technique.UsageType.PER_SCENE,
            activation_cost=2,
            activation_cost_resource="Focus",
        )

        state = CharacterEngine(self.character).technique_state(technique)

        self.assertTrue(state["available"])
        self.assertFalse(state["engine_resolves_effects"])
        self.assertEqual(state["support_level"], Technique.SupportLevel.DESCRIPTIVE)
        self.assertTrue(state["is_choice_placeholder"])
        self.assertEqual(state["choice_group"], "bard_awakened_gift_l2")
        self.assertIn("artistic focus", state["selection_notes"])
        self.assertIsNotNone(state["activation"])

    def test_choice_placeholders_require_non_computed_support_and_context(self):
        """Placeholder rows need explicit support semantics and editor guidance."""
        technique = Technique(
            school=self.school,
            name="Open Choice",
            level=1,
            is_choice_placeholder=True,
            support_level=Technique.SupportLevel.COMPUTED,
        )

        with self.assertRaises(ValidationError):
            technique.full_clean()

    def test_choice_model_rejects_non_choice_techniques(self):
        """Persistent technique choices must only exist for explicit choice techniques."""
        technique = Technique.objects.create(
            school=self.school,
            name="Fixed Rhythm",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
        )
        choice = CharacterTechniqueChoice(
            character=self.character,
            technique=technique,
            selected_skill=self.music,
        )

        with self.assertRaises(ValidationError):
            choice.full_clean()

    def test_choice_model_validates_without_engine_calls(self):
        """Choice validation should stay model-local and not depend on CharacterEngine access."""
        technique = Technique.objects.create(
            school=self.school,
            name="Focused Practice",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
            choice_target_kind=Technique.ChoiceTargetKind.SKILL,
            selection_notes="Choose one practiced skill.",
        )
        choice = CharacterTechniqueChoice(
            character=self.character,
            technique=technique,
            selected_skill=self.music,
        )

        with patch.object(Character, "get_engine", side_effect=AssertionError("clean() must not use CharacterEngine")):
            choice.full_clean()

    def test_choice_group_is_metadata_only(self):
        """Shared choice groups must not create hidden exclusivity or resolver logic."""
        first = Technique.objects.create(
            school=self.school,
            name="Verse A",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
            choice_group="bard_shared_l1",
        )
        second = Technique.objects.create(
            school=self.school,
            name="Verse B",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
            choice_group="bard_shared_l1",
        )
        technique_ct = ContentType.objects.get_for_model(Technique, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=technique_ct,
            source_object_id=first.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=1,
        )
        Modifier.objects.create(
            source_content_type=technique_ct,
            source_object_id=second.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=2,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.calculate_initiative(), 3)
        self.assertEqual(engine.technique_state(first)["choice_group"], "bard_shared_l1")
        self.assertEqual(engine.technique_state(second)["choice_group"], "bard_shared_l1")

    def test_engine_applies_choice_bonus_to_selected_skill(self):
        """Computed passive techniques can grant a fixed bonus to the chosen skill."""
        technique = Technique.objects.create(
            school=self.school,
            name="Signature Piece",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
            choice_target_kind=Technique.ChoiceTargetKind.SKILL,
            choice_bonus_value=3,
            selection_notes="Choose one performance skill.",
        )
        CharacterTechnique.objects.create(character=self.character, technique=technique)
        CharacterTechniqueChoice.objects.create(
            character=self.character,
            technique=technique,
            selected_skill=self.music,
        )

        engine = CharacterEngine(self.character)

        self.assertTrue(engine.is_technique_choice_complete(technique))
        self.assertEqual(engine.skill_total("music"), 7)
        self.assertEqual(engine.skill_total("oratory"), 3)

    def test_engine_applies_choice_bonus_to_selected_skill_family(self):
        """Computed passive techniques can grant a fixed bonus to a chosen skill family."""
        technique = Technique.objects.create(
            school=self.school,
            name="Inspired Discipline",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
            choice_target_kind=Technique.ChoiceTargetKind.SKILL_FAMILY,
            choice_bonus_value=2,
            selection_notes="Choose one skill family.",
        )
        CharacterTechnique.objects.create(character=self.character, technique=technique)
        CharacterTechniqueChoice.objects.create(
            character=self.character,
            technique=technique,
            selected_skill_family=self.skill_family,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.skill_total("music"), 6)
        self.assertEqual(engine.skill_total("oratory"), 5)
        self.assertEqual(engine.skill_total("duel"), 2)
