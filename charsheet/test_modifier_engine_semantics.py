"""Tests for the new semantic modifier engine layer."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from charsheet.engine.character_combat import fame_total
from charsheet.engine.character_creation_engine import CharacterCreationEngine
from charsheet.models import Attribute, CharacterTraitChoice, Trait, TraitChoiceDefinition, TraitSemanticEffect
from charsheet.modifiers import (
    CombatModifier,
    CharacterBuildValidator,
    EconomyModifier,
    ModifierEngine,
    ModifierOperator,
    MovementModifier,
    PerceptionModifier,
    ResistanceModifier,
    RuleFlagModifier,
    SocialModifier,
    TargetDomain,
    TraitBuildRule,
)
from charsheet.modifiers.registry import build_trait_semantic_modifiers, riches_gold_value, riches_internal_money_value


class ModifierEngineSemanticTests(SimpleTestCase):
    """Verify semantic modifier domains beyond the legacy numeric system."""

    def test_rule_flag_and_capability_modifiers_resolve(self):
        engine = ModifierEngine(
            modifiers=[
                PerceptionModifier(
                    source_type="trait",
                    source_id="blind",
                    target_key="vision_dependent_actions",
                    operator=ModifierOperator.FLAT_SUB,
                    value=6,
                ),
                RuleFlagModifier(
                    source_type="trait",
                    source_id="blind",
                    target_key="blind",
                    operator=ModifierOperator.SET_FLAG,
                    value=True,
                ),
                RuleFlagModifier(
                    source_type="trait",
                    source_id="blind",
                    target_domain=TargetDomain.CAPABILITY,
                    target_key="can_see",
                    operator=ModifierOperator.REMOVE_CAPABILITY,
                    value=False,
                ),
            ]
        )

        self.assertEqual(engine.resolve_flags(), {"blind": True})
        self.assertEqual(engine.resolve_capabilities(), {"can_see": False})
        self.assertEqual(engine.resolve_perception_value("vision_dependent_actions"), -6)

    def test_resistance_and_movement_profiles_resolve(self):
        engine = ModifierEngine(
            modifiers=[
                ResistanceModifier(
                    source_type="trait",
                    source_id="heat_vulnerability",
                    target_key="natural_heat",
                    operator=ModifierOperator.GRANT_VULNERABILITY,
                    value=6,
                ),
                MovementModifier(
                    source_type="trait",
                    source_id="gehbehinderung",
                    target_key="ground_combat",
                    operator=ModifierOperator.FLAT_SUB,
                    value=2,
                ),
            ]
        )

        resistances = engine.resolve_resistances()
        movement = engine.resolve_movement()

        self.assertEqual(resistances.vulnerabilities["natural_heat"], 6)
        self.assertEqual(movement.values["ground_combat"], -2)

    def test_movement_multiplier_and_combat_profile_value_resolve(self):
        engine = ModifierEngine(
            modifiers=[
                MovementModifier(
                    source_type="trait",
                    source_id="beidseitige_laehmung",
                    target_key="ground_combat",
                    operator=ModifierOperator.MULTIPLY,
                    value=0.25,
                ),
                CombatModifier(
                    source_type="trait",
                    source_id="beidseitige_laehmung",
                    target_key="melee_maneuvers",
                    operator=ModifierOperator.FLAT_SUB,
                    value=6,
                ),
            ]
        )

        movement = engine.resolve_movement()

        self.assertEqual(movement.multipliers["ground_combat"], 0.25)
        self.assertEqual(engine.resolve_combat_value("melee_maneuvers"), -6)

    def test_resource_modifier_can_increase_personal_fame_points_for_fame_total(self):
        modifier_engine = ModifierEngine(
            modifiers=[
                EconomyModifier(
                    source_type="trait",
                    source_id="adel",
                    target_domain=TargetDomain.RESOURCE,
                    target_key="personal_fame_point",
                    operator=ModifierOperator.FLAT_ADD,
                    value=3,
                ),
            ]
        )
        engine = SimpleNamespace(
            character=SimpleNamespace(
                personal_fame_point=2,
                personal_fame_rank=1,
                sacrifice_rank=0,
                artefact_rank=0,
            ),
            resolve_resource=lambda key: modifier_engine.resolve_resource(key),
        )

        self.assertEqual(fame_total(engine), 6)

    def test_social_profile_and_behavioral_tags_resolve(self):
        engine = ModifierEngine(
            modifiers=[
                SocialModifier(
                    source_type="trait",
                    source_id="adel",
                    target_key="status",
                    operator=ModifierOperator.CHANGE_SOCIAL_STATUS,
                    value=4,
                ),
                SocialModifier(
                    source_type="trait",
                    source_id="gesucht",
                    target_key="legal_status",
                    operator=ModifierOperator.ADD_TAG,
                    value="wanted",
                ),
            ]
        )

        profile = engine.resolve_social_profile()

        self.assertEqual(profile.statuses["status"], 4)
        self.assertIn("wanted", profile.tags)

    def test_creation_only_riches_modifier_uses_table_and_only_applies_during_creation(self):
        modifiers = build_trait_semantic_modifiers(
            trait_slug="adv_riches",
            level=9,
            trait=Trait(name="Reichtuemer", slug="adv_riches", trait_type=Trait.TraitType.ADV, description=""),
        )

        self.assertEqual(len(modifiers), 1)
        self.assertIsInstance(modifiers[0], EconomyModifier)
        self.assertEqual(riches_gold_value(9), 12000)
        self.assertEqual(riches_internal_money_value(9), 1200000)

        engine = ModifierEngine(modifiers=modifiers)

        self.assertEqual(
            engine.resolve_numeric_total(
                TargetDomain.ECONOMY,
                "starting_funds",
                context={"during_character_creation": True},
            ),
            1200000,
        )
        self.assertEqual(
            engine.resolve_numeric_total(TargetDomain.ECONOMY, "starting_funds"),
            0,
        )

    @patch("charsheet.engine.character_creation_engine.Trait.objects.filter")
    def test_character_creation_engine_resolves_starting_funds_from_new_modifier_system(self, filter_mock):
        filter_mock.return_value.first.return_value = None
        draft = SimpleNamespace(
            race=SimpleNamespace(),
            state={
                "phase_3": {"disadvantages": {}},
                "phase_4": {"advantages": {"adv_riches": 8}},
            },
        )

        engine = CharacterCreationEngine(draft)

        self.assertEqual(engine.resolve_creation_starting_funds(), 800000)

    def test_persisted_trait_semantic_effect_materializes_typed_modifier(self):
        trait = Trait(name="Arm", slug="arm", trait_type=Trait.TraitType.DIS, description="")
        effect = TraitSemanticEffect(
            trait=trait,
            target_domain=TargetDomain.ECONOMY,
            target_key="starting_funds",
            operator=ModifierOperator.OVERRIDE,
            value="0",
            condition_set={"applies_during_character_creation": True},
            metadata={"currency": "KM"},
        )

        modifier = effect.to_modifier()

        self.assertIsInstance(modifier, EconomyModifier)
        self.assertEqual(modifier.target_key, "starting_funds")
        self.assertEqual(modifier.value, 0)
        self.assertTrue(modifier.condition_set.applies_during_character_creation)
        self.assertEqual(modifier.metadata["currency"], "KM")

    def test_choice_bound_trait_semantic_effect_materializes_choice_binding_and_resolves_selected_attribute(self):
        attribute = Attribute(name="Willenskraft", short_name="WILL")
        trait = Trait(name="Erbaermliche Eigenschaft", slug="erbaermliche_eigenschaft", trait_type=Trait.TraitType.DIS, description="")
        definition = TraitChoiceDefinition(
            id=7,
            trait=trait,
            name="Waehle Eigenschaft",
            target_kind=TraitChoiceDefinition.TargetKind.ATTRIBUTE,
        )
        effect = TraitSemanticEffect(
            trait=trait,
            target_choice_definition=definition,
            target_domain=TargetDomain.ATTRIBUTE,
            target_key="",
            operator=ModifierOperator.FLAT_SUB,
            value="1",
        )

        modifier = effect.to_modifier()

        self.assertEqual(modifier.metadata["choice_binding"], {"kind": "trait_choice_definition", "id": 7})

        choice = CharacterTraitChoice(
            definition=definition,
            selected_attribute=attribute,
        )
        engine = ModifierEngine(modifiers=[modifier])
        engine.character_engine = SimpleNamespace(_all_modifiers=[], _trait_choices_by_definition_id={7: [choice]})
        engine.__dict__["_active_trait_modifiers"] = []

        self.assertEqual(engine.resolve_numeric_total(TargetDomain.ATTRIBUTE, "WILL"), -1)

    def test_choice_bound_trait_attribute_cap_effect_resolves_selected_attribute(self):
        attribute = Attribute(name="Willenskraft", short_name="WILL")
        trait = Trait(name="Legendaere Eigenschaft", slug="adv_legendary_attribute", trait_type=Trait.TraitType.ADV, description="")
        definition = TraitChoiceDefinition(
            id=8,
            trait=trait,
            name="Waehle Eigenschaft",
            target_kind=TraitChoiceDefinition.TargetKind.ATTRIBUTE,
        )
        effect = TraitSemanticEffect(
            trait=trait,
            target_choice_definition=definition,
            target_domain=TargetDomain.ATTRIBUTE_CAP,
            target_key="",
            operator=ModifierOperator.FLAT_ADD,
            value="1",
        )

        modifier = effect.to_modifier()
        choice = CharacterTraitChoice(
            definition=definition,
            selected_attribute=attribute,
        )
        engine = ModifierEngine(modifiers=[modifier])
        engine.character_engine = SimpleNamespace(_all_modifiers=[], _trait_choices_by_definition_id={8: [choice]})
        engine.__dict__["_active_trait_modifiers"] = []

        self.assertEqual(engine.resolve_numeric_total(TargetDomain.ATTRIBUTE_CAP, "WILL"), 1)


class CharacterBuildValidatorTests(SimpleTestCase):
    """Validate build-time exclusion and CP cap rules."""

    def test_disadvantage_cp_cap_is_enforced(self):
        validator = CharacterBuildValidator(
            rules={
                "blind": TraitBuildRule(slug="blind", cp_refund=20, min_rank=1, max_rank=1),
                "phobie": TraitBuildRule(slug="phobie", cp_refund=3, min_rank=1, max_rank=1),
            },
            max_disadvantage_cp=20,
        )

        issues = validator.validate({"blind": 1, "phobie": 1})

        self.assertTrue(any(issue.code == "disadvantage_cap_exceeded" for issue in issues))

    def test_overlap_group_blocks_double_dipping(self):
        validator = CharacterBuildValidator(
            rules={
                "blind": TraitBuildRule(slug="blind", cp_refund=20, overlap_groups=("sight",)),
                "kurzsichtig": TraitBuildRule(slug="kurzsichtig", cp_refund=2, overlap_groups=("sight",)),
            }
        )

        issues = validator.validate({"blind": 1, "kurzsichtig": 1})

        self.assertTrue(any(issue.code == "overlap_group_conflict" for issue in issues))
