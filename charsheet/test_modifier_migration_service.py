"""Unit tests for legacy modifier migration and the new-only modifier engine modes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from charsheet.models import Modifier
from charsheet.modifiers import (
    LegacyModifierMigrationService,
    ModifierEngine,
    ModifierResolutionMode,
)


def _fake_modifier(**overrides):
    defaults = {
        "id": 1,
        "source_content_type": SimpleNamespace(model="race"),
        "source_object_id": 1,
        "target_kind": Modifier.TargetKind.SKILL,
        "target_slug": "",
        "target_skill_id": None,
        "target_skill_category_id": None,
        "target_item_id": None,
        "target_specialization_id": None,
        "target_choice_definition_id": None,
        "target_race_choice_definition_id": None,
        "target_content_type_id": None,
        "target_object_id": None,
        "mode": Modifier.Mode.FLAT,
        "value": 2,
        "scale_source": None,
        "scale_school_id": None,
        "scale_skill_id": None,
        "mul": 1,
        "div": 1,
        "round_mode": Modifier.RoundMode.FLOOR,
        "cap_mode": Modifier.CapMode.NONE,
        "cap_source": None,
        "min_school_level": None,
        "target_identifier": lambda: "skill_empathy",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class LegacyModifierMigrationServiceTests(SimpleTestCase):
    """Verify legacy modifier rows are classified into the new system correctly."""

    def test_skill_modifier_maps_to_skill_modifier(self):
        legacy_modifier = _fake_modifier(target_skill_id=7, target_identifier=lambda: "skill_empathy")

        record = LegacyModifierMigrationService([legacy_modifier]).migrate_modifier(legacy_modifier)

        self.assertEqual(record.new_modifier_type, "SkillModifier")
        self.assertEqual(record.new_target_domain, "skill")
        self.assertFalse(record.requires_manual_review)
        self.assertEqual(record.primary_modifier().metadata["legacy_modifier_id"], 1)

    def test_damage_stat_maps_to_combat_modifier(self):
        legacy_modifier = _fake_modifier(
            target_kind=Modifier.TargetKind.STAT,
            target_slug="dmg_slash",
            target_identifier=lambda: "dmg_slash",
        )

        record = LegacyModifierMigrationService([legacy_modifier]).migrate_modifier(legacy_modifier)

        self.assertEqual(record.new_modifier_type, "CombatModifier")
        self.assertEqual(record.new_target_domain, "combat")
        self.assertFalse(record.requires_manual_review)

    def test_misused_damage_skill_slug_maps_to_combat_modifier_without_blocking_production(self):
        legacy_modifier = _fake_modifier(
            target_kind=Modifier.TargetKind.SKILL,
            target_slug="dmg_slash",
            target_identifier=lambda: "dmg_slash",
        )

        record = LegacyModifierMigrationService([legacy_modifier]).migrate_modifier(legacy_modifier)

        self.assertEqual(record.new_modifier_type, "CombatModifier")
        self.assertFalse(record.requires_manual_review)
        self.assertEqual(record.migration_strategy, "auto_typed")

    def test_choice_bound_skill_modifier_gets_dynamic_target_key(self):
        legacy_modifier = _fake_modifier(
            target_choice_definition_id=4,
            target_identifier=lambda: "",
        )

        record = LegacyModifierMigrationService([legacy_modifier]).migrate_modifier(legacy_modifier)

        self.assertEqual(record.primary_modifier().target_key, "selected_skill:technique_choice_definition:4")
        self.assertEqual(record.primary_modifier().metadata["choice_binding"]["id"], 4)

    @patch("charsheet.modifiers.migration.Skill.objects.filter")
    def test_unknown_skill_slug_without_persisted_skill_requires_review(self, filter_mock):
        filter_mock.return_value.exists.return_value = False
        legacy_modifier = _fake_modifier(target_identifier=lambda: "unknown_slug", target_slug="unknown_slug")

        record = LegacyModifierMigrationService([legacy_modifier]).migrate_modifier(legacy_modifier)

        self.assertTrue(record.requires_manual_review)
        self.assertEqual(record.new_modifier_type, "SkillModifier")


class ModifierResolutionModeTests(SimpleTestCase):
    """Verify the new engine stays new-only in production and compare is debug-only."""

    def test_compare_mode_returns_new_result_and_logs_difference(self):
        class TestEngine(ModifierEngine):
            def _legacy_numeric_total(self, target_domain, target_key, context=None):
                return 5

            def _migrated_numeric_total(self, target_domain, target_key, context=None):
                return 7

        engine = TestEngine(resolution_mode=ModifierResolutionMode.COMPARE)

        resolved = engine.resolve_numeric_total("derived_stat", "initiative")

        self.assertEqual(resolved, 7)
        self.assertEqual(len(engine.comparison_log()), 1)
        self.assertFalse(engine.comparison_log()[0].matches)

    def test_new_only_mode_returns_new_result(self):
        class TestEngine(ModifierEngine):
            def _legacy_numeric_total(self, target_domain, target_key, context=None):
                return 5

            def _migrated_numeric_total(self, target_domain, target_key, context=None):
                return 7

        engine = TestEngine(resolution_mode=ModifierResolutionMode.NEW_ONLY)

        self.assertEqual(engine.resolve_numeric_total("derived_stat", "initiative"), 7)

    def test_new_only_is_default_and_does_not_call_legacy_fallback(self):
        class TestEngine(ModifierEngine):
            def _legacy_numeric_total(self, target_domain, target_key, context=None):
                raise AssertionError("legacy numeric fallback must not run in productive mode")

            def _migrated_numeric_total(self, target_domain, target_key, context=None):
                return 7

        engine = TestEngine()

        self.assertEqual(engine.resolve_numeric_total("derived_stat", "initiative"), 7)

    def test_legacy_only_mode_constant_is_removed(self):
        self.assertFalse(hasattr(ModifierResolutionMode, "LEGACY_ONLY"))

    def test_legacy_only_input_normalizes_to_new_only(self):
        self.assertEqual(
            ModifierResolutionMode.normalize("legacy_only"),
            ModifierResolutionMode.NEW_ONLY,
        )
