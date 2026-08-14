"""Central modifier engine for numeric and semantic rule effects."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Any

from charsheet.modifiers.definitions import AttributeCapModifier, BaseModifier, ModifierOperator, RuleFlagModifier, StackBehavior, TargetDomain
from charsheet.constants import PROFICIENCY_GROUP_FOREIGN_LANGUAGES, RUNE_CRAFTER_LEVEL, SOURCE_ITEM_RUNE
from charsheet.modifiers.migration import ModifierResolutionMode, NumericResolutionComparison
from charsheet.modifiers.registry import build_trait_semantic_modifiers
from charsheet.modifiers.targets import TargetResolver
from charsheet.models import (
    CharacterDaemonicPower,
    CharacterItemSemanticEffect,
    DaemonicPowerSemanticEffect,
    ItemSemanticEffect,
    RaceSemanticEffect,
    RuneSemanticEffect,
    SchoolSemanticEffect,
    Skill,
    TechniqueSemanticEffect,
    VampireTraitSemanticEffect,
)


@dataclass(slots=True)
class ResistanceProfile:
    """Resolved immunity and vulnerability state."""

    modifiers: dict[str, int] = field(default_factory=dict)
    immunities: set[str] = field(default_factory=set)
    vulnerabilities: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class MovementProfile:
    """Resolved movement data from modifiers."""

    values: dict[str, int] = field(default_factory=dict)
    multipliers: dict[str, float] = field(default_factory=dict)
    blocked_modes: set[str] = field(default_factory=set)


@dataclass(slots=True)
class CombatProfile:
    """Resolved combat-affecting semantic state."""

    values: dict[str, int] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class SocialProfile:
    """Resolved social/legal state."""

    statuses: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)


class ModifierEngine:
    """Collect, resolve, and explain character modifiers in one place."""

    def __init__(
        self,
        character_engine=None,
        modifiers: list[BaseModifier] | None = None,
        *,
        resolution_mode: str | None = None,
        trait_levels_by_slug: dict[str, int] | None = None,
    ):
        self.character_engine = character_engine
        self._injected_modifiers = list(modifiers or [])
        self.trait_levels_by_slug = dict(trait_levels_by_slug or {})
        self.resolution_mode = ModifierResolutionMode.normalize(
            resolution_mode or os.getenv("CODEX_MODIFIER_MODE")
        )
        self._comparison_log: list[NumericResolutionComparison] = []
        self._active_modifiers_cache: list[BaseModifier] | None = None

    @cached_property
    def _active_race_semantic_modifiers(self) -> list[BaseModifier]:
        """Build semantic modifiers from the character's race."""
        if self.character_engine is None or not self.character_engine.character.race_id:
            return []
        effects = (
            RaceSemanticEffect.objects.filter(
                race_id=self.character_engine.character.race_id,
                active_flag=True,
            )
            .select_related("race")
            .order_by("race_id", "sort_order", "id")
        )
        return [effect.to_modifier() for effect in effects]

    @cached_property
    def _active_school_semantic_modifiers(self) -> list[BaseModifier]:
        """Build semantic modifiers from learned schools."""
        if self.character_engine is None:
            return []
        school_ids = list(self.character_engine._school_entries.keys())
        if not school_ids:
            return []
        effects = (
            SchoolSemanticEffect.objects.filter(
                school_id__in=school_ids,
                active_flag=True,
            )
            .select_related("school")
            .order_by("school_id", "sort_order", "id")
        )
        return [effect.to_modifier() for effect in effects]

    @cached_property
    def _active_trait_modifiers(self) -> list[BaseModifier]:
        """Build semantic trait modifiers from purchased character traits."""
        if self.character_engine is None:
            return []
        modifiers: list[BaseModifier] = []
        trait_entries = (
            self.character_engine.character.charactertrait_set.select_related("trait")
            .order_by("trait__slug")
        )
        for entry in trait_entries:
            modifiers.extend(
                build_trait_semantic_modifiers(
                    trait_slug=entry.trait.slug,
                    level=int(entry.trait_level),
                    trait=entry.trait,
                )
            )
        return modifiers

    @cached_property
    def _active_item_rune_modifiers(self) -> list[BaseModifier]:
        """Resolve active equipped ItemRune assignments into semantic modifiers."""
        if self.character_engine is None:
            return []
        modifiers: list[BaseModifier] = []
        first_item_id_by_rune_id: dict[int, int] = {}
        for item_rune in self.character_engine._equipped_item_runes:
            rune = item_rune.rune
            first_item_id = first_item_id_by_rune_id.get(rune.id)
            if first_item_id is None:
                first_item_id_by_rune_id[rune.id] = item_rune.item_id
            elif first_item_id != item_rune.item_id:
                continue
            for effect in rune.semantic_effects.filter(active_flag=True).order_by("sort_order", "id"):
                modifier = effect.to_modifier()
                scaling = dict(modifier.scaling)
                mode = modifier.mode
                if rune.is_level_scaled and str(mode or "flat") == "scaled":
                    scaling["scale_source"] = RUNE_CRAFTER_LEVEL
                elif scaling.get("scale_source") == RUNE_CRAFTER_LEVEL:
                    scaling["scale_source"] = None
                if not rune.is_level_scaled and scaling.get("cap_source") == RUNE_CRAFTER_LEVEL:
                    scaling["cap_source"] = None
                modifiers.append(
                    replace(
                        modifier,
                        source_type=SOURCE_ITEM_RUNE,
                        source_id=str(item_rune.id),
                        scaling=scaling,
                        metadata={
                            **modifier.metadata,
                            "rune_id": rune.id,
                            "rune_slug": rune.slug,
                            "rune_name": rune.name,
                            "item_rune_id": item_rune.id,
                            "crafter_level": item_rune.crafter_level,
                        },
                    )
                )
        return modifiers

    @cached_property
    def _active_item_semantic_modifiers(self) -> list[BaseModifier]:
        """Build semantic modifiers from equipped magic base items and item instances."""
        if self.character_engine is None:
            return []
        equipped_items = list(
            self.character_engine._equipped_items_for_semantic_effects
        )
        if not equipped_items:
            return []
        item_ids = {int(entry.item_id) for entry in equipped_items}
        character_item_ids = {int(entry.id) for entry in equipped_items}
        base_effects = (
            ItemSemanticEffect.objects.filter(
                item_id__in=item_ids,
                active_flag=True,
            )
            .select_related("item")
            .order_by("item_id", "sort_order", "id")
        )
        instance_effects = (
            CharacterItemSemanticEffect.objects.filter(
                character_item_id__in=character_item_ids,
                active_flag=True,
            )
            .select_related("character_item", "character_item__item")
            .order_by("character_item_id", "sort_order", "id")
        )
        character_item_ids_with_instance_effects = {
            int(effect.character_item_id)
            for effect in instance_effects
        }
        base_effects_by_item_id: dict[int, list[ItemSemanticEffect]] = {}
        for effect in base_effects:
            base_effects_by_item_id.setdefault(int(effect.item_id), []).append(effect)
        base_modifiers = []
        for character_item in equipped_items:
            if int(character_item.id) in character_item_ids_with_instance_effects:
                continue
            for effect in base_effects_by_item_id.get(int(character_item.item_id), []):
                base_modifiers.append(effect.to_modifier(invested_cp=character_item.invested_cp))
        return [
            *base_modifiers,
            *(effect.to_modifier() for effect in instance_effects),
        ]

    @cached_property
    def _active_technique_semantic_modifiers(self) -> list[BaseModifier]:
        """Build semantic modifiers from learned, available computed techniques."""
        if self.character_engine is None:
            return []

        technique_ids = [
            technique.id
            for technique in (
                list(self.character_engine._character_school_technique_list)
                + list(self.character_engine._race_technique_list)
            )
        ]
        if not technique_ids:
            return []

        learned_stack: set[int] = set()
        available_stack: set[int] = set()
        active_technique_ids = {
            technique_id
            for technique_id in technique_ids
            if self._modifier_source_is_active(
                BaseModifier(
                    source_type="technique",
                    source_id=str(technique_id),
                    target_domain=TargetDomain.METADATA,
                    target_key="active",
                ),
                learned_stack,
                available_stack,
            )
        }
        if not active_technique_ids:
            return []

        effects = (
            TechniqueSemanticEffect.objects.filter(
                technique_id__in=active_technique_ids,
                active_flag=True,
            )
            .select_related("technique", "target_choice_definition")
            .prefetch_related("target_skills")
            .order_by("technique_id", "sort_order", "id")
        )
        return [effect.to_modifier() for effect in effects]

    @cached_property
    def _active_daemonic_power_modifiers(self) -> list[BaseModifier]:
        """Build modifiers from valid power choices whose granting techniques are active."""
        if self.character_engine is None:
            return []
        active_power_ids: set[int] = set()
        ownerships = (
            CharacterDaemonicPower.objects.filter(character=self.character_engine.character)
            .select_related("power", "granting_technique")
            .order_by("granting_technique_id", "power_id", "id")
        )
        for ownership in ownerships:
            technique = ownership.granting_technique
            if (
                technique.granted_daemonic_power_tier_id != ownership.power.tier_id
            ):
                continue
            state = self.character_engine.technique_state(technique)
            if state["learned"] and state["available"]:
                active_power_ids.add(ownership.power_id)
        if not active_power_ids:
            return []
        effects = (
            DaemonicPowerSemanticEffect.objects.filter(
                power_id__in=active_power_ids,
                active_flag=True,
                application_scope__in=(
                    DaemonicPowerSemanticEffect.ApplicationScope.CHARACTER,
                    DaemonicPowerSemanticEffect.ApplicationScope.BOTH,
                ),
            )
            .select_related("power")
            .prefetch_related("target_skills")
            .order_by("power_id", "sort_order", "id")
        )
        return [effect.to_modifier() for effect in effects]

    @cached_property
    def _active_vampire_trait_modifiers(self) -> list[BaseModifier]:
        """Build passive modifiers from the shared vampire-trait catalogue."""
        if self.character_engine is None:
            return []
        from charsheet.engine.vampire_engine import VampireRules

        rules = VampireRules(self.character_engine.character)
        if not rules.is_vampire():
            return []
        modifiers: list[BaseModifier] = []
        age_cycle = rules.age_cycle()
        modifiers.append(
            RuleFlagModifier(
                source_type="vampire_status",
                source_id=str(self.character_engine.character.pk),
                target_key="can_act_while_out_of_action",
                operator=ModifierOperator.SET_FLAG,
                value=True,
            )
        )
        if rules.can_exceed_strength_race_maximum():
            modifiers.append(
                AttributeCapModifier(
                    source_type="vampire_status",
                    source_id=str(self.character_engine.character.pk),
                    target_key="ST",
                    operator=ModifierOperator.FLAT_ADD,
                    value=age_cycle,
                )
            )
        for ownership in rules.effective_traits(include_weaknesses=True):
            for effect in ownership.trait.semantic_effects.all():
                if (
                    effect.active_flag
                    and effect.application_scope
                    in {
                        VampireTraitSemanticEffect.ApplicationScope.CHARACTER,
                        VampireTraitSemanticEffect.ApplicationScope.BOTH,
                    }
                ):
                    modifiers.append(effect.to_modifier(rank=ownership.rank, age_cycle=age_cycle))
        for ownership in rules.effective_powers():
            for effect in ownership.power.semantic_effects.all():
                if (
                    effect.active_flag
                    and (
                        effect.power_component != VampireTraitSemanticEffect.PowerComponent.WEAKNESS
                        or ownership.weakness_is_active
                    )
                    and effect.application_scope
                    in {
                        VampireTraitSemanticEffect.ApplicationScope.CHARACTER,
                        VampireTraitSemanticEffect.ApplicationScope.BOTH,
                    }
                ):
                    effect_rank = (
                        1
                        if effect.power_component == VampireTraitSemanticEffect.PowerComponent.WEAKNESS
                        else ownership.rank
                    )
                    modifiers.append(effect.to_modifier(rank=effect_rank, age_cycle=age_cycle))
        return modifiers

    def collect_active_modifiers(self, character=None, context: dict[str, Any] | None = None) -> list[BaseModifier]:
        """Collect all active typed modifiers for the current character and context."""
        if not context:
            if self._active_modifiers_cache is not None:
                return self._active_modifiers_cache
        context = context or {}
        collected = list(self._injected_modifiers)
        if self.character_engine is not None:
            collected.extend(self._active_race_semantic_modifiers)
            collected.extend(self._active_school_semantic_modifiers)
            collected.extend(self._active_trait_modifiers)
            collected.extend(self._active_technique_semantic_modifiers)
            collected.extend(self._active_daemonic_power_modifiers)
            collected.extend(self._active_vampire_trait_modifiers)
            collected.extend(self._active_item_semantic_modifiers)
            collected.extend(self._active_item_rune_modifiers)
        expanded = self._expand_choice_bound_modifiers(collected)
        result = [
            modifier
            for modifier in expanded
            if modifier is not None and modifier.applies(context) and TargetResolver.matches_context(modifier, context)
        ]
        if not context:
            self._active_modifiers_cache = result
        return result

    def resolve_numeric_total(
        self,
        target_domain: str,
        target_key: str,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> int:
        """Resolve the summed numeric result for one target."""
        new_value = self._migrated_numeric_total(
            target_domain,
            target_key,
            context=context,
            specification=specification,
        )
        return new_value

    def resolve_choice_skill_modifier_total(
        self,
        skill_id: int,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> int:
        """Resolve choice-bound skill modifiers according to the active debug mode."""
        new_value = self._migrated_choice_skill_modifier_total(skill_id, context=context, specification=specification)
        return new_value

    def resolve_skill_rank_cap(
        self,
        skill_slug: str,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> int:
        """Resolve the learnable maximum rank for one skill row."""
        extra_cap = self._migrated_numeric_total(
            TargetDomain.SKILL_RANK_CAP,
            skill_slug,
            context=context,
            specification=specification,
        )
        return max(10, 10 + int(extra_cap))

    def resolve_skill_rank_bonus(
        self,
        skill_slug: str,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> int:
        """Resolve bonus ranks that count as skill ranks instead of misc modifiers."""
        return int(
            self._migrated_numeric_total(
                TargetDomain.SKILL_RANK,
                skill_slug,
                context=context,
                specification=specification,
            )
        )

    def skill_rank_cap_metadata(
        self,
        skill_slug: str,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> dict[str, Any]:
        """Return metadata for matching skill-rank-cap modifiers."""
        metadata: dict[str, Any] = {}
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.SKILL_RANK_CAP:
                continue
            if not self._modifier_matches_target_key(
                modifier,
                target_domain=TargetDomain.SKILL_RANK_CAP,
                target_key=skill_slug,
            ):
                continue
            if not self._modifier_matches_skill_specification(
                modifier,
                target_domain=TargetDomain.SKILL_RANK_CAP,
                specification=specification,
            ):
                continue
            metadata.update(modifier.metadata or {})
        return metadata

    def skill_modifier_specifications(self, skill_id: int, skill_slug: str, context: dict[str, Any] | None = None) -> list[str]:
        """Return non-generic skill specifications made visible by active skill modifiers."""
        if self.character_engine is None:
            return []

        specifications: set[str] = set()
        display_values: dict[str, str] = {}
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain not in {TargetDomain.SKILL, TargetDomain.SKILL_RANK, TargetDomain.SKILL_RANK_CAP}:
                continue

            expected = self._expected_skill_specification(modifier)
            if not expected:
                continue

            if self._modifier_matches_target_key(
                modifier,
                target_domain=modifier.target_domain,
                target_key=skill_slug,
            ):
                specifications.add(expected)
                display_values.setdefault(expected, self._display_skill_specification(modifier))
                continue

            choice_binding = modifier.metadata.get("choice_binding")
            if not choice_binding:
                continue
            if choice_binding["kind"] == "technique_choice_definition":
                choices = self.character_engine._technique_choices_by_definition_id.get(choice_binding["id"], [])
            else:
                choices = self.character_engine._race_choices_by_definition_id.get(choice_binding["id"], [])
            if any(choice.selected_skill_id == skill_id for choice in choices):
                specifications.add(expected)
                display_values.setdefault(expected, self._display_skill_specification(modifier))

        return sorted((display_values.get(specification) or specification for specification in specifications), key=str.casefold)

    def resolve_skill_value(self, skill_slug: str, context: dict[str, Any] | None = None) -> int:
        """Resolve one full skill value through the existing engine facade."""
        if self.character_engine is None:
            return self.resolve_numeric_total(TargetDomain.SKILL, skill_slug, context=context)
        return self.character_engine.skill_total(skill_slug)

    def resolve_attribute_bonus(self, attribute_slug: str, context: dict[str, Any] | None = None) -> int:
        """Resolve attribute bonus modifiers that target one base attribute."""
        return self.resolve_numeric_total(TargetDomain.ATTRIBUTE, attribute_slug, context=context)

    def resolve_derived_stat(self, stat_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve one derived stat from the central engine."""
        if self.character_engine is None:
            return self.resolve_numeric_total(TargetDomain.DERIVED_STAT, stat_key, context=context)
        if stat_key == "initiative":
            return self.character_engine.calculate_initiative()
        if stat_key == "arcane_power":
            return self.character_engine.calculate_arcane_power()
        if stat_key == "potential":
            return self.character_engine.calculate_potential()
        if stat_key == "vw":
            return self.character_engine.vw()
        if stat_key == "gw":
            return self.character_engine.gw()
        if stat_key == "sr":
            return self.character_engine.sr()
        if stat_key == "rs":
            return self.character_engine.get_grs()
        return self.resolve_numeric_total(TargetDomain.DERIVED_STAT, stat_key, context=context)

    def resolve_resource(self, resource_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve resource modifiers for one resource key."""
        return self.resolve_numeric_total(TargetDomain.RESOURCE, resource_key, context=context)

    def resolve_resistances(self, context: dict[str, Any] | None = None) -> ResistanceProfile:
        """Resolve immunities, vulnerabilities, and numeric resistance modifiers."""
        profile = ResistanceProfile()
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.RESISTANCE:
                continue
            if modifier.operator == ModifierOperator.GRANT_IMMUNITY:
                profile.immunities.add(modifier.target_key)
            elif modifier.operator == ModifierOperator.GRANT_VULNERABILITY:
                profile.vulnerabilities[modifier.target_key] = abs(int(self._resolve_numeric_modifier(modifier) or 0))
            else:
                profile.modifiers[modifier.target_key] = (
                    profile.modifiers.get(modifier.target_key, 0) + int(self._resolve_numeric_modifier(modifier) or 0)
                )
        return profile

    def resolve_movement(self, context: dict[str, Any] | None = None) -> MovementProfile:
        """Resolve movement values and blocked movement modes."""
        profile = MovementProfile()
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.MOVEMENT:
                continue
            if modifier.operator == ModifierOperator.UNSET_FLAG:
                profile.blocked_modes.add(modifier.target_key)
                continue
            if modifier.operator == ModifierOperator.MULTIPLY:
                profile.multipliers[modifier.target_key] = (
                    profile.multipliers.get(modifier.target_key, 1.0) * float(self._resolve_numeric_modifier(modifier) or 1.0)
                )
                continue
            profile.values[modifier.target_key] = (
                profile.values.get(modifier.target_key, 0) + int(self._resolve_numeric_modifier(modifier) or 0)
            )
        return profile

    def resolve_combat_profile(self, context: dict[str, Any] | None = None) -> CombatProfile:
        """Resolve semantic combat effects."""
        profile = CombatProfile()
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.COMBAT:
                continue
            if modifier.operator == ModifierOperator.ADD_TAG:
                profile.tags.add(str(modifier.value))
                continue
            profile.values[modifier.target_key] = (
                profile.values.get(modifier.target_key, 0) + int(self._resolve_numeric_modifier(modifier) or 0)
            )
        return profile

    def resolve_combat_value(self, target_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve one numeric combat-profile value."""
        return int(self.resolve_combat_profile(context=context).values.get(target_key, 0))

    def resolve_perception_value(self, target_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve one numeric perception-related modifier value."""
        return self.resolve_numeric_total(TargetDomain.PERCEPTION, target_key, context=context)

    def resolve_flags(self, context: dict[str, Any] | None = None) -> dict[str, bool]:
        """Resolve boolean rule flags."""
        flags: dict[str, bool] = {}
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.RULE_FLAG:
                continue
            resolved_value = self._resolve_numeric_modifier(modifier)
            if modifier.operator == ModifierOperator.UNSET_FLAG or not resolved_value:
                flags[modifier.target_key] = False
            else:
                flags[modifier.target_key] = True
        return flags

    def resolve_capabilities(self, context: dict[str, Any] | None = None) -> dict[str, bool]:
        """Resolve capability grants and removals."""
        capabilities: dict[str, bool] = {}
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.CAPABILITY:
                continue
            resolved_value = self._resolve_numeric_modifier(modifier)
            if modifier.operator == ModifierOperator.REMOVE_CAPABILITY or resolved_value == 0:
                capabilities[modifier.target_key] = False
            else:
                capabilities[modifier.target_key] = True
        return capabilities

    def resolve_social_profile(self, context: dict[str, Any] | None = None) -> SocialProfile:
        """Resolve social statuses and tags."""
        profile = SocialProfile()
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.SOCIAL:
                continue
            if modifier.operator == ModifierOperator.ADD_TAG:
                profile.tags.add(str(modifier.value))
            else:
                profile.statuses[modifier.target_key] = modifier.value
        return profile

    def explain_resolution(
        self,
        target: tuple[str, str],
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a debuggable breakdown for one target."""
        target_domain, target_key = target
        rows: list[dict[str, Any]] = []
        layer_entries = [("new", self.collect_active_modifiers(context=context))]

        for layer_name, modifiers in layer_entries:
            for modifier in modifiers:
                if modifier.target_domain != target_domain:
                    continue
                if not self._modifier_matches_target_key(
                    modifier,
                    target_domain=target_domain,
                    target_key=target_key,
                ):
                    continue
                if not self._modifier_matches_skill_specification(
                    modifier,
                    target_domain=target_domain,
                    specification=specification,
                ):
                    continue
                if not self._modifier_matches_item_context(modifier, target_domain=target_domain, context=context):
                    continue
                if not self._modifier_matches_condition_text(modifier, context):
                    continue
                if not TargetResolver.matches_context(modifier, context):
                    continue
                rows.append(
                    {
                        "layer": layer_name,
                        "source_type": modifier.source_type,
                        "source_id": modifier.source_id,
                        "operator": modifier.operator,
                        "value": modifier.value,
                        "resolved_value": self._resolve_numeric_modifier(modifier),
                        "notes": modifier.notes,
                        "condition_text": str(modifier.metadata.get("condition_text") or ""),
                        "requires_manual_review": bool(modifier.metadata.get("requires_manual_review", False)),
                    }
                )
        return rows

    def comparison_log(self) -> list[NumericResolutionComparison]:
        """Return collected compare-mode rows."""
        return list(self._comparison_log)

    def reset_comparison_log(self) -> None:
        """Clear accumulated compare-mode rows."""
        self._comparison_log.clear()

    def _resolve_numeric_modifier(self, modifier: BaseModifier) -> int | float | None:
        """Resolve the numeric contribution of one modifier from typed metadata only."""
        numeric_value = self._resolve_numeric_value(modifier)
        if numeric_value is None:
            return None

        if modifier.operator in {
            ModifierOperator.SET_FLAG,
            ModifierOperator.GRANT_CAPABILITY,
        }:
            return int(bool(numeric_value))
        if modifier.operator in {
            ModifierOperator.UNSET_FLAG,
            ModifierOperator.REMOVE_CAPABILITY,
        }:
            return 0
        if modifier.operator in {
            ModifierOperator.FLAT_SUB,
            ModifierOperator.CONDITIONAL_PENALTY,
        }:
            return -abs(int(numeric_value))
        if modifier.operator == ModifierOperator.MULTIPLY:
            return float(numeric_value)
        if modifier.operator == ModifierOperator.FLOOR_DIVIDE:
            return float(numeric_value)
        return int(numeric_value)

    def _resolve_numeric_value(self, modifier: BaseModifier) -> int | float | None:
        """Resolve the numeric magnitude of one typed modifier before the operator sign is applied."""
        numeric_value = self._coerce_numeric(modifier.value)
        if numeric_value is None:
            return None

        if str(modifier.mode or "flat") == "scaled":
            scale_source = str(modifier.scaling.get("scale_source") or "")
            scale_value = self._resolve_scale_value(modifier, scale_source)
            if scale_value is None:
                return 0
            mul = self._coerce_numeric(modifier.scaling.get("mul"), default=1)
            div = self._coerce_numeric(modifier.scaling.get("div"), default=1)
            if not div:
                return 0

            raw_value = (scale_value * numeric_value * mul) / div
            round_mode = str(modifier.scaling.get("round_mode") or "floor")
            resolved_value = math.ceil(raw_value) if round_mode == "ceil" else math.floor(raw_value)

            cap_mode = str(modifier.scaling.get("cap_mode") or "none")
            if cap_mode != "none":
                cap_source = str(modifier.scaling.get("cap_source") or "")
                cap_value = self._resolve_scale_value(modifier, cap_source)
                if cap_value is not None:
                    if cap_mode == "min":
                        resolved_value = max(resolved_value, int(cap_value))
                    elif cap_mode == "max":
                        resolved_value = min(resolved_value, int(cap_value))
            numeric_value = resolved_value

        if modifier.value_min is not None:
            numeric_value = max(numeric_value, self._coerce_numeric(modifier.value_min, default=numeric_value))
        if modifier.value_max is not None:
            numeric_value = min(numeric_value, self._coerce_numeric(modifier.value_max, default=numeric_value))
        return numeric_value

    def _migrated_numeric_total(
        self,
        target_domain: str,
        target_key: str,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> int:
        """Resolve one numeric target from migrated typed modifiers."""
        relevant_modifiers = [
            modifier
            for modifier in self.collect_active_modifiers(context=context)
            if modifier.target_domain == target_domain
            and self._modifier_matches_target_key(modifier, target_domain=target_domain, target_key=target_key)
            and self._modifier_matches_skill_specification(
                modifier,
                target_domain=target_domain,
                specification=specification,
            )
            and self._modifier_matches_item_context(modifier, target_domain=target_domain, context=context)
            and self._modifier_matches_condition_text(modifier, context)
            and TargetResolver.matches_context(modifier, context)
        ]

        resolved_total = 0
        seen_unique_sources: set[tuple[str, str, str, str]] = set()
        for modifier in sorted(relevant_modifiers, key=lambda entry: (entry.priority, entry.source_type, entry.source_id)):
            if modifier.stack_behavior == StackBehavior.UNIQUE_BY_SOURCE:
                dedupe_key = (modifier.source_type, modifier.source_id, modifier.target_domain, modifier.target_key)
                if dedupe_key in seen_unique_sources:
                    continue
                seen_unique_sources.add(dedupe_key)

            resolved_value = self._resolve_numeric_modifier(modifier)
            if resolved_value is None:
                continue

            if modifier.operator == ModifierOperator.OVERRIDE:
                resolved_total = int(resolved_value)
                continue
            if modifier.operator == ModifierOperator.MULTIPLY:
                resolved_total = int(resolved_total * resolved_value)
                continue
            if modifier.operator == ModifierOperator.FLOOR_DIVIDE:
                if not resolved_value:
                    continue
                resolved_total = int(resolved_total // resolved_value)
                continue
            if modifier.operator == ModifierOperator.MIN_VALUE:
                resolved_total = max(resolved_total, int(resolved_value))
                continue
            if modifier.operator == ModifierOperator.MAX_VALUE:
                resolved_total = min(resolved_total, int(resolved_value))
                continue

            resolved_total += int(resolved_value)
        return int(resolved_total)

    @staticmethod
    def _modifier_matches_target_key(modifier: BaseModifier, *, target_domain: str, target_key: str) -> bool:
        """Match direct target_key or concrete skill selections stored in metadata."""
        if modifier.target_key == target_key:
            return True
        if target_domain not in {TargetDomain.SKILL, TargetDomain.SKILL_RANK, TargetDomain.SKILL_RANK_CAP}:
            return False
        selected_skill_slugs = modifier.metadata.get("target_skill_slugs") or []
        return target_key in selected_skill_slugs

    def _modifier_matches_item_context(
        self,
        modifier: BaseModifier,
        *,
        target_domain: str,
        context: dict[str, Any] | None,
    ) -> bool:
        """Keep concrete item combat effects out of global combat totals."""
        if target_domain != TargetDomain.COMBAT or str(modifier.source_type or "") != "characteritem":
            return True
        expected_item_id = self._coerce_source_id(modifier.source_id)
        if expected_item_id is None:
            return False
        actual_item_id = self._coerce_source_id((context or {}).get("character_item_id"))
        return actual_item_id == expected_item_id

    @staticmethod
    def _normalize_condition_text(value: object) -> str:
        """Normalize a player-facing free-text restriction for stable matching."""
        return " ".join(str(value or "").split()).casefold()

    def _modifier_matches_condition_text(
        self,
        modifier: BaseModifier,
        context: dict[str, Any] | None,
    ) -> bool:
        """Apply free-text restrictions only in their explicit sheet context."""
        expected = self._normalize_condition_text(modifier.metadata.get("condition_text"))
        if not expected:
            return True
        actual = self._normalize_condition_text((context or {}).get("condition_text"))
        return bool(actual) and actual == expected

    def _migrated_choice_skill_modifier_total(
        self,
        skill_id: int,
        context: dict[str, Any] | None = None,
        *,
        specification: str | None = None,
    ) -> int:
        """Resolve choice-bound skill modifiers from migrated typed modifiers."""
        if self.character_engine is None:
            return 0

        total = 0
        for modifier in self.collect_active_modifiers(context=context):
            if modifier.target_domain != TargetDomain.SKILL:
                continue
            choice_binding = modifier.metadata.get("choice_binding")
            if not choice_binding:
                continue

            if choice_binding["kind"] == "technique_choice_definition":
                choices = self.character_engine._technique_choices_by_definition_id.get(choice_binding["id"], [])
            else:
                choices = self.character_engine._race_choices_by_definition_id.get(choice_binding["id"], [])

            if any(
                choice.selected_skill_id == skill_id
                and self._choice_skill_modifier_matches_specification(
                    modifier,
                    specification=specification,
                )
                for choice in choices
            ):
                total += int(self._resolve_numeric_modifier(modifier) or 0)
        return total

    def _modifier_matches_skill_specification(
        self,
        modifier: BaseModifier,
        *,
        target_domain: str,
        specification: str | None,
    ) -> bool:
        """Return whether a direct skill modifier applies to the current skill specification."""
        if target_domain not in {TargetDomain.SKILL, TargetDomain.SKILL_RANK, TargetDomain.SKILL_RANK_CAP}:
            return True
        expected = self._expected_skill_specification(modifier)
        if expected is None:
            return True
        return self._normalize_skill_specification(specification) == expected

    def _choice_skill_modifier_matches_specification(
        self,
        modifier: BaseModifier,
        *,
        specification: str | None,
    ) -> bool:
        """Return whether a choice-bound skill modifier applies to the current skill specification."""
        expected = self._expected_skill_specification(modifier)
        if expected is None:
            return True
        return self._normalize_skill_specification(specification) == expected

    def _expected_skill_specification(self, modifier: BaseModifier) -> str | None:
        """Resolve the optional skill specification gate for a choice-bound modifier."""
        metadata = modifier.metadata or {}
        fixed_specification = metadata.get("skill_specification")
        if fixed_specification not in (None, ""):
            return self._normalize_skill_specification(fixed_specification)

        source = str(metadata.get("skill_specification_source") or "").strip()
        if source != "technique_specification":
            return None

        source_id = self._coerce_source_id(modifier.source_id)
        if source_id is None or self.character_engine is None:
            return None
        learned_technique = self.character_engine._learned_techniques_by_id.get(source_id)
        if learned_technique is None:
            return None
        normalized = self._normalize_skill_specification(learned_technique.specification_value)
        return normalized or None

    def _normalize_skill_specification(self, value: Any) -> str:
        """Normalize skill specification text for exact matching."""
        text = " ".join(str(value or "").strip().split())
        return "" if text == "*" else text.casefold()

    def _display_skill_specification(self, modifier: BaseModifier) -> str:
        """Return the configured skill specification with original display casing when available."""
        metadata = modifier.metadata or {}
        fixed_specification = metadata.get("skill_specification")
        if fixed_specification not in (None, ""):
            return " ".join(str(fixed_specification or "").strip().split())

        source_id = self._coerce_source_id(modifier.source_id)
        if source_id is None or self.character_engine is None:
            return ""
        learned_technique = self.character_engine._learned_techniques_by_id.get(source_id)
        if learned_technique is None:
            return ""
        return " ".join(str(learned_technique.specification_value or "").strip().split())

    def _modifier_source_is_active(
        self,
        modifier: BaseModifier,
        learned_stack: set[int],
        available_stack: set[int],
    ) -> bool:
        """Check whether one typed modifier source currently contributes effects."""
        if self.character_engine is None:
            return True

        source_type = str(modifier.source_type or "").lower()
        source_id = self._coerce_source_id(modifier.source_id)

        if source_type == "race":
            return source_id is not None and self.character_engine.character.race_id == source_id
        if source_type == "school":
            return source_id is not None and self.character_engine.school_level(source_id) > 0
        if source_type == "trait":
            return source_id is not None and source_id in self.character_engine._trait_levels
        if source_type == SOURCE_ITEM_RUNE:
            return source_id is not None and any(
                item_rune.id == source_id for item_rune in self.character_engine._equipped_item_runes
            )
        if source_type == "rune":
            return source_id is not None and self.character_engine.is_rune_equipped(source_id)
        if source_type != "technique" or source_id is None:
            return True

        technique = self.character_engine._coerce_technique(source_id)
        if technique.id in self.character_engine._race_technique_ids:
            return (
                self.character_engine._technique_effect_is_computed(technique)
                and self.character_engine._is_technique_choice_complete(technique)
                and technique.technique_type == technique.TechniqueType.PASSIVE
            )

        return (
            self.character_engine._technique_effect_is_computed(technique)
            and self.character_engine._is_technique_choice_complete(technique)
            and technique.technique_type == technique.TechniqueType.PASSIVE
            and self.character_engine._has_technique_learned(technique, learned_stack, available_stack)
            and self.character_engine._is_technique_available(technique, learned_stack, available_stack)
        )

    def _modifier_school_gate_is_open(self, modifier: BaseModifier) -> bool:
        """Check optional minimum school-level gating for one typed modifier."""
        if self.character_engine is None:
            return True
        min_school_level = modifier.scaling.get("min_school_level")
        if min_school_level in (None, ""):
            return True
        gate_school_id = self._modifier_gate_school_id(modifier)
        if gate_school_id is None:
            return False
        return self.character_engine.school_level(gate_school_id) >= int(min_school_level)

    def _expand_choice_bound_modifiers(self, modifiers: list[BaseModifier]) -> list[BaseModifier]:
        """Expand choice-bound modifiers into concrete target-key instances."""
        expanded: list[BaseModifier] = []
        for modifier in modifiers:
            bound_targets = self._resolve_choice_bound_targets(modifier)
            if not bound_targets:
                expanded.append(modifier)
                continue
            for target_domain, target_key in bound_targets:
                expanded.append(
                    replace(
                        modifier,
                        target_domain=target_domain,
                        target_key=target_key,
                    )
                )
        return expanded

    def _resolve_choice_bound_targets(self, modifier: BaseModifier) -> list[tuple[str, str]]:
        """Resolve concrete targets for one choice-bound modifier, if any."""
        if self.character_engine is None:
            return []
        choice_binding = modifier.metadata.get("choice_binding") or {}
        if choice_binding.get("kind") != "trait_choice_definition":
            return []
        choices = self.character_engine._trait_choices_by_definition_id.get(int(choice_binding["id"]), [])
        resolved_targets: list[tuple[str, str]] = []
        for choice in choices:
            target = choice.resolved_modifier_target()
            if target is None:
                continue
            if target[0] == TargetDomain.PROFICIENCY_GROUP:
                resolved_targets.extend(self._expand_proficiency_group_target(target[1]))
                continue
            if target[0] == TargetDomain.ATTRIBUTE and modifier.target_domain == TargetDomain.ATTRIBUTE_CAP:
                resolved_targets.append((TargetDomain.ATTRIBUTE_CAP, target[1]))
                continue
            if target[0] != modifier.target_domain and target[0] != "metadata":
                continue
            resolved_targets.append(target)
        return resolved_targets

    def _expand_proficiency_group_target(self, group_key: str) -> list[tuple[str, str]]:
        """Map one proficiency-group key to concrete central modifier targets."""
        if group_key == PROFICIENCY_GROUP_FOREIGN_LANGUAGES:
            return [(TargetDomain.LANGUAGE, PROFICIENCY_GROUP_FOREIGN_LANGUAGES)]
        return [(TargetDomain.SKILL_CATEGORY, group_key)]

    def _modifier_gate_school_id(self, modifier: BaseModifier) -> int | None:
        """Resolve which school drives school-level scaling or gating."""
        if self.character_engine is None:
            return None
        scale_school_id = modifier.scaling.get("scale_school_id")
        if scale_school_id:
            return int(scale_school_id)

        source_type = str(modifier.source_type or "").lower()
        source_id = self._coerce_source_id(modifier.source_id)
        if source_type == "school":
            return source_id
        if source_type == "technique" and source_id is not None:
            return self.character_engine._coerce_technique(source_id).school_id
        return None

    def _resolve_scale_value(self, modifier: BaseModifier, scale_source: str | None) -> int | None:
        """Resolve the raw numeric input used for scaled typed modifier math."""
        if not scale_source:
            return None
        if scale_source == "vampire_trait_rank":
            return int(modifier.scaling.get("_vampire_trait_rank") or 0)
        if scale_source == "vampire_age_cycle":
            return int(modifier.scaling.get("_vampire_age_cycle") or 0)
        if scale_source == "item_invested_cp":
            return int(modifier.metadata.get("item_invested_cp") or 0)
        if scale_source == "trait_level" and self.character_engine is None:
            return self.trait_levels_by_slug.get(str(modifier.source_id or ""))
        if self.character_engine is None:
            return None
        if scale_source == "school_level":
            gate_school_id = self._modifier_gate_school_id(modifier)
            return self.character_engine.school_level(gate_school_id) if gate_school_id else None
        if scale_source == "fame_total":
            return self.character_engine.fame_total()
        if scale_source == "trait_level":
            source_id = self._coerce_source_id(modifier.source_id)
            if source_id is not None:
                return self.character_engine._trait_levels.get(source_id)
            return self.character_engine._trait_levels_by_slug.get(str(modifier.source_id or ""))
        if scale_source == RUNE_CRAFTER_LEVEL:
            item_rune_id = self._coerce_source_id(modifier.source_id)
            if item_rune_id is None:
                return None
            for item_rune in self.character_engine._equipped_item_runes:
                if int(item_rune.id) == item_rune_id:
                    return int(item_rune.crafter_level)
            return None
        if scale_source == "skill_level":
            skill_id = modifier.scaling.get("scale_skill_id")
            if not skill_id:
                return None
            scale_skill = self.character_engine.skills().get(self._scale_skill_slug(int(skill_id)))
            return int(scale_skill["level"]) if scale_skill else 0
        if scale_source == "skill_total":
            skill_id = modifier.scaling.get("scale_skill_id")
            if not skill_id:
                return None
            return self.character_engine.skill_total(self._scale_skill_slug(int(skill_id)))
        return None

    def _scale_skill_slug(self, skill_id: int) -> str:
        """Resolve a skill slug from a persisted skill id."""
        if self.character_engine is None:
            return ""
        for slug, info in self.character_engine.skills().items():
            if int(info["skill_id"]) == int(skill_id):
                return slug
        return str(Skill.objects.only("slug").get(pk=int(skill_id)).slug)

    def _coerce_numeric(self, value: Any, *, default: int | float | None = None) -> int | float | None:
        """Convert supported values into a numeric payload."""
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _coerce_source_id(self, value: Any) -> int | None:
        """Normalize a source id into an integer when possible."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

