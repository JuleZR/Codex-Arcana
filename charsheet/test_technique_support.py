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
    CharacterSpecialization,
    CharacterSkill,
    CharacterTechnique,
    CharacterTechniqueChoice,
    Modifier,
    Race,
    School,
    SchoolType,
    Specialization,
    Skill,
    SkillCategory,
    SkillFamily,
    Item,
    Technique,
    TechniqueChoiceBlock,
    TechniqueChoiceDefinition,
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

    def test_choice_definitions_drive_completion_for_multiple_decisions(self):
        """Explicit choice definitions can require multiple different stored decisions for one technique."""
        technique = Technique.objects.create(
            school=self.school,
            name="Composer's Discipline",
            level=1,
            technique_type=Technique.TechniqueType.PASSIVE,
            support_level=Technique.SupportLevel.COMPUTED,
            selection_notes="Pick a practiced skill and name the composition style.",
        )
        skill_definition = TechniqueChoiceDefinition.objects.create(
            technique=technique,
            name="Skill Focus",
            target_kind=Technique.ChoiceTargetKind.SKILL,
            description="Choose one practiced performance skill.",
        )
        text_definition = TechniqueChoiceDefinition.objects.create(
            technique=technique,
            name="Style Name",
            target_kind=Technique.ChoiceTargetKind.TEXT,
            description="Write down the named style of the composition.",
        )

        engine = CharacterEngine(self.character)
        self.assertFalse(engine.is_technique_choice_complete(technique))

        CharacterTechniqueChoice.objects.create(
            character=self.character,
            technique=technique,
            definition=skill_definition,
            selected_skill=self.music,
        )
        self.assertFalse(CharacterEngine(self.character).is_technique_choice_complete(technique))

        CharacterTechniqueChoice.objects.create(
            character=self.character,
            technique=technique,
            definition=text_definition,
            selected_text="Kriegslied",
        )
        self.assertTrue(CharacterEngine(self.character).is_technique_choice_complete(technique))

    def test_choice_block_state_tracks_open_fulfilled_and_violated(self):
        """Generic choice blocks should report whether required technique picks are still open or already broken."""
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

        block_state = CharacterEngine(self.character).technique_choice_blocks(self.school)[0]
        self.assertTrue(block_state["active"])
        self.assertTrue(block_state["open"])
        self.assertFalse(block_state["fulfilled"])
        self.assertFalse(block_state["violated"])

        CharacterTechnique.objects.create(character=self.character, technique=first)
        block_state = CharacterEngine(self.character).technique_choice_blocks(self.school)[0]
        self.assertFalse(block_state["open"])
        self.assertTrue(block_state["fulfilled"])
        self.assertFalse(block_state["violated"])

        CharacterTechnique.objects.create(character=self.character, technique=second)
        block_state = CharacterEngine(self.character).technique_choice_blocks(self.school)[0]
        self.assertFalse(block_state["open"])
        self.assertFalse(block_state["fulfilled"])
        self.assertTrue(block_state["violated"])

    def test_choice_definition_accepts_school_specialization_targets(self):
        """Specialization targets stay generic but still validate against the technique school."""
        other_school = School.objects.create(name="Blade College", type=self.school_type)
        allowed_specialization = Specialization.objects.create(
            school=self.school,
            name="Heroic Ballad",
            slug="heroic-ballad",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        blocked_specialization = Specialization.objects.create(
            school=other_school,
            name="Blade Choir",
            slug="blade-choir",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        technique = Technique.objects.create(
            school=self.school,
            name="Awakened Talent",
            level=2,
            support_level=Technique.SupportLevel.DESCRIPTIVE,
            selection_notes="Choose one school specialization.",
        )
        definition = TechniqueChoiceDefinition.objects.create(
            technique=technique,
            name="School Specialization",
            target_kind=Technique.ChoiceTargetKind.SPECIALIZATION,
        )

        valid_choice = CharacterTechniqueChoice(
            character=self.character,
            technique=technique,
            definition=definition,
            selected_specialization=allowed_specialization,
        )
        valid_choice.full_clean()

        invalid_choice = CharacterTechniqueChoice(
            character=self.character,
            technique=technique,
            definition=definition,
            selected_specialization=blocked_specialization,
        )
        with self.assertRaises(ValidationError):
            invalid_choice.full_clean()

    def test_engine_resolves_generic_modifier_targets(self):
        """Item, item-category, specialization, and generic entity modifier targets should resolve through the engine."""
        school_ct = ContentType.objects.get_for_model(School, for_concrete_model=False)
        item_ct = ContentType.objects.get_for_model(Item, for_concrete_model=False)
        lute = Item.objects.create(name="Battle Lute", item_type=Item.ItemType.MISC)
        specialization = Specialization.objects.create(
            school=self.school,
            name="Silver Voice",
            slug="silver-voice",
            support_level=Specialization.SupportLevel.STRUCTURED,
        )
        CharacterSpecialization.objects.create(
            character=self.character,
            specialization=specialization,
        )
        Modifier.objects.create(
            source_content_type=school_ct,
            source_object_id=self.school.id,
            target_kind=Modifier.TargetKind.ITEM,
            target_item=lute,
            mode=Modifier.Mode.FLAT,
            value=2,
        )
        Modifier.objects.create(
            source_content_type=school_ct,
            source_object_id=self.school.id,
            target_kind=Modifier.TargetKind.ITEM_CATEGORY,
            target_slug=Item.ItemType.MISC,
            mode=Modifier.Mode.FLAT,
            value=3,
        )
        Modifier.objects.create(
            source_content_type=school_ct,
            source_object_id=self.school.id,
            target_kind=Modifier.TargetKind.SPECIALIZATION,
            target_specialization=specialization,
            mode=Modifier.Mode.FLAT,
            value=4,
        )
        Modifier.objects.create(
            source_content_type=school_ct,
            source_object_id=self.school.id,
            target_kind=Modifier.TargetKind.ENTITY,
            target_content_type=item_ct,
            target_object_id=lute.id,
            mode=Modifier.Mode.FLAT,
            value=5,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.modifier_total_for_item(lute), 2)
        self.assertEqual(engine.modifier_total_for_item_category(Item.ItemType.MISC), 3)
        self.assertEqual(engine.modifier_total_for_specialization(specialization), 4)
        self.assertEqual(engine.modifier_total_for_entity(lute), 5)
