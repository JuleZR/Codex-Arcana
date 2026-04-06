"""Regression tests for VW-specific positive attribute suppression flags."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from charsheet.engine.character_combat import vw


class VwPositiveBonusFlagTests(SimpleTestCase):
    """Ensure positive GE/WA contributions to VW can be suppressed by rule flag."""

    def test_vw_suppresses_only_positive_attribute_bonuses_when_flag_is_set(self):
        engine = SimpleNamespace(
            attribute_modifier=lambda slug: {"GE": 3, "WA": -1}[slug],
            resolve_flags=lambda: {"suppress_positive_vw_attribute_bonuses": True},
            _resolve_stat_modifiers=lambda slug: 0,
        )

        self.assertEqual(vw(engine), 13)
