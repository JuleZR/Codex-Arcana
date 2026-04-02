"""Regression tests for skill-based modifier scaling on derived stats."""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from charsheet.constants import ATTR_GE, INITIATIVE, SKILL_COMBAT
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterSkill,
    Modifier,
    Race,
    Skill,
    SkillCategory,
)


class ModifierSkillScalingTests(TestCase):
    """Verify stats can scale from one concrete skill without recursive side effects."""

    def setUp(self):
        """Create a minimal character with one learned skill."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="tester", password="secret")
        self.race = Race.objects.create(name="Human")
        self.character = Character.objects.create(owner=self.user, name="Tarin", race=self.race)
        self.ge = Attribute.objects.create(name="Geschicklichkeit", short_name=ATTR_GE)
        CharacterAttribute.objects.create(character=self.character, attribute=self.ge, base_value=8)
        self.skill_category = SkillCategory.objects.create(name="Combat", slug=SKILL_COMBAT)
        self.evade = Skill.objects.create(
            name="Evade",
            slug="evade",
            category=self.skill_category,
            attribute=self.ge,
        )
        CharacterSkill.objects.create(character=self.character, skill=self.evade, level=4)
        self.race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)

    def test_scaled_stat_modifier_can_use_skill_level(self):
        """Skill-level scaling should use only the learned ranks of the selected skill."""
        Modifier.objects.create(
            source_content_type=self.race_ct,
            source_object_id=self.race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.SCALED,
            value=1,
            scale_source=Modifier.ScaleSource.SKILL_LEVEL,
            scale_skill=self.evade,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.modifier_total_for_stat(INITIATIVE), 4)

    def test_scaled_stat_modifier_can_use_skill_total(self):
        """Skill-total scaling should use the full resolved skill value including attribute mod."""
        Modifier.objects.create(
            source_content_type=self.race_ct,
            source_object_id=self.race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.SCALED,
            value=1,
            scale_source=Modifier.ScaleSource.SKILL_TOTAL,
            scale_skill=self.evade,
        )

        engine = CharacterEngine(self.character)

        self.assertEqual(engine.modifier_total_for_stat(INITIATIVE), 7)
        self.assertEqual(engine.calculate_initiative(), 10)

    def test_skill_based_scaling_requires_scale_skill(self):
        """Skill-based scale sources must declare which skill provides the numeric value."""
        modifier = Modifier(
            source_content_type=self.race_ct,
            source_object_id=self.race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.SCALED,
            value=1,
            scale_source=Modifier.ScaleSource.SKILL_TOTAL,
        )

        with self.assertRaises(ValidationError) as ctx:
            modifier.full_clean()

        self.assertIn("scale_skill", ctx.exception.message_dict)

    def test_skill_based_scaling_is_limited_to_stat_targets(self):
        """Skill-based scaling is intentionally restricted to stat targets to avoid recursion."""
        modifier = Modifier(
            source_content_type=self.race_ct,
            source_object_id=self.race.id,
            target_kind=Modifier.TargetKind.SKILL,
            target_skill=self.evade,
            mode=Modifier.Mode.SCALED,
            value=1,
            scale_source=Modifier.ScaleSource.SKILL_TOTAL,
            scale_skill=self.evade,
        )

        with self.assertRaises(ValidationError) as ctx:
            modifier.full_clean()

        self.assertIn("target_kind", ctx.exception.message_dict)
