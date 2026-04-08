"""Regression tests for signed encumbrance handling in sheet context values."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from charsheet.constants import ATTR_GE, INITIATIVE, SKILL_COMBAT
from charsheet.engine.character_engine import CharacterEngine
from charsheet.models import Attribute, Character, CharacterAttribute, CharacterSkill, Modifier, Race, Skill, SkillCategory, Trait, CharacterTrait
from charsheet.sheet_context import build_character_sheet_context


class LoadPenaltyContextTests(TestCase):
    """Keep encumbrance penalties consistent across skills and initiative displays."""

    def setUp(self):
        """Create a minimal character with one agility-based skill."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="loadtester", password="secret")
        self.race = Race.objects.create(name="Mensch")
        self.attribute = Attribute.objects.create(name="Geschick", short_name=ATTR_GE)
        self.category = SkillCategory.objects.create(name="Kampf", slug=SKILL_COMBAT)
        self.skill = Skill.objects.create(
            name="Ausweichen",
            slug="ausweichen",
            category=self.category,
            attribute=self.attribute,
        )
        self.character = Character.objects.create(owner=self.user, name="Toma", race=self.race)
        CharacterAttribute.objects.create(character=self.character, attribute=self.attribute, base_value=7)
        CharacterSkill.objects.create(character=self.character, skill=self.skill, level=5)

    def test_context_normalizes_load_penalty_for_positive_and_negative_raw_values(self):
        """The sheet should always subtract encumbrance from displayed derived values."""
        for raw_bel in (2, -2):
            with self.subTest(raw_bel=raw_bel), patch.object(CharacterEngine, "get_bel", return_value=raw_bel):
                self.character.__dict__.pop("_character_engine", None)

                context = build_character_sheet_context(self.character)
                skill_row = context["skill_rows"][0]

                self.assertEqual(context["core_stats"]["load_value"], -2)
                self.assertEqual(context["core_stats"]["initiative_display"], "+2")
                self.assertEqual(context["core_stats"]["initiative_with_load_display"], "0")
                self.assertEqual(skill_row["misc_mod"], "0")
                self.assertEqual(skill_row["total"], 7)
                self.assertEqual(skill_row["with_load_total"], 5)
                self.assertIn("| Eigenschaft | `+2` | GE |", skill_row["calculation_tooltip"])
                self.assertIn("| Belastung | `-2` |", skill_row["calculation_tooltip"])
                self.assertIn("| **= Gesamt** | `5` |", skill_row["calculation_tooltip"])

    def test_core_stat_tooltips_include_breakdown_rows(self):
        """Derived stat tooltips should expose their numeric composition."""
        race_ct = ContentType.objects.get_for_model(Race, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=race_ct,
            source_object_id=self.race.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=2,
        )
        self.character.__dict__.pop("_character_engine", None)
        context = build_character_sheet_context(self.character)
        core_stats = context["core_stats"]

        self.assertIn("| Posten | Wert | Herkunft |", core_stats["initiative_tooltip"])
        self.assertIn("| GE-Bonus/Malus | `+2` |", core_stats["initiative_tooltip"])
        self.assertIn("| **Mensch** | `+2` | Rasse |", core_stats["initiative_tooltip"])
        self.assertIn("| Belastung | `0` |", core_stats["initiative_with_load_tooltip"])
        self.assertIn("| Basis | `14` |", core_stats["vw_tooltip"])
        self.assertIn("| ST-Bonus/Malus | `-5` |", core_stats["sr_tooltip"])
        self.assertIn("| WILL-Bonus/Malus | `-5` |", core_stats["gw_tooltip"])
        self.assertIn("| Will | `0` |", core_stats["arcane_power_tooltip"])

    def test_core_stat_tooltips_resolve_numeric_trait_sources_to_names(self):
        """Legacy-style trait source ids should render the trait name instead of the raw id."""
        trait = Trait.objects.create(name="Schnell", slug="schnell", trait_type=Trait.TraitType.ADV, points=1)
        CharacterTrait.objects.create(character=self.character, trait=trait, trait_level=1)
        trait_ct = ContentType.objects.get_for_model(Trait, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=trait_ct,
            source_object_id=trait.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=2,
        )

        self.character.__dict__.pop("_character_engine", None)
        context = build_character_sheet_context(self.character)
        tooltip = context["core_stats"]["initiative_tooltip"]

        self.assertIn("Schnell", tooltip)
        self.assertNotIn("| **16** |", tooltip)

    def test_core_stat_tooltips_group_duplicate_sources(self):
        """Repeated source rows should collapse into one summarized ledger entry."""
        trait = Trait.objects.create(name="Schnell", slug="schnell_ii", trait_type=Trait.TraitType.ADV, points=2)
        CharacterTrait.objects.create(character=self.character, trait=trait, trait_level=2)
        trait_ct = ContentType.objects.get_for_model(Trait, for_concrete_model=False)
        Modifier.objects.create(
            source_content_type=trait_ct,
            source_object_id=trait.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=2,
        )
        Modifier.objects.create(
            source_content_type=trait_ct,
            source_object_id=trait.id,
            target_kind=Modifier.TargetKind.STAT,
            target_slug=INITIATIVE,
            mode=Modifier.Mode.FLAT,
            value=2,
        )

        self.character.__dict__.pop("_character_engine", None)
        tooltip = build_character_sheet_context(self.character)["core_stats"]["initiative_tooltip"]

        self.assertIn("Schnell II", tooltip)
        self.assertIn("| **Schnell II** | `+4` | Merkmal |", tooltip)
