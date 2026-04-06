"""Regression tests for non-linear trait cost curves."""

from django.test import SimpleTestCase

from charsheet.models import Trait
from charsheet.modifiers import CharacterBuildValidator, TraitBuildRule


class TraitCostCurveTests(SimpleTestCase):
    """Verify explicit per-level trait cost curves override linear costs."""

    def test_trait_cost_curve_is_used_for_cumulative_costs(self):
        trait = Trait(
            name="Verwoehnt",
            slug="verwoehnt",
            trait_type=Trait.TraitType.DIS,
            description="",
            min_level=1,
            max_level=2,
            points_per_level=1,
            points_by_level="1,3",
        )

        self.assertEqual(trait.cost_curve(), (1, 3))
        self.assertEqual(trait.level_cost(1), 1)
        self.assertEqual(trait.level_cost(2), 3)
        self.assertEqual(trait.cost_for_level(2), 4)
        self.assertEqual(trait.cost_display(), "1,3")

    def test_build_validator_uses_explicit_refund_curve(self):
        validator = CharacterBuildValidator(
            rules={
                "verwoehnt": TraitBuildRule(
                    slug="verwoehnt",
                    cp_refund=1,
                    cp_refund_by_rank=(1, 3),
                    min_rank=1,
                    max_rank=2,
                    repeatable=True,
                ),
            },
            max_disadvantage_cp=3,
        )

        issues = validator.validate({"verwoehnt": 2})

        self.assertTrue(any(issue.code == "disadvantage_cap_exceeded" for issue in issues))
