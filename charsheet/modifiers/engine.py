"""Central modifier engine for numeric and semantic rule effects."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Any

from charsheet.modifiers.definitions import BaseModifier, ModifierOperator, StackBehavior, TargetDomain
from charsheet.constants import PROFICIENCY_GROUP_FOREIGN_LANGUAGES, RUNE_CRAFTER_LEVEL, SOURCE_ITEM_RUNE
from charsheet.modifiers.legacy import LegacyModifierAdapter
from charsheet.modifiers.migration import (
    LegacyModifierMigrationService,
    ModifierResolutionMode,
    NumericResolutionComparison,
)
from charsheet.modifiers.registry import build_trait_semantic_modifiers
from charsheet.models import Modifier, Skill


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
    ):
        self.character_engine = character_engine
        self._injected_modifiers = list(modifiers or [])
        self.resolution_mode = ModifierResolutionMode.normalize(
            resolution_mode or os.getenv("CODEX_MODIFIER_MODE")
        )
        self._comparison_log: list[NumericResolutionComparison] = []
        self._active_modifiers_cache: list[BaseModifier] | None = None

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
        """Resolve active equipped ItemRune assignments into concrete modifiers."""
        if self.character_engine is None:
            return []
        modifiers: list[BaseModifier] = []
        for item_rune in self.character_engine._equipped_item_runes:
            rune = item_rune.rune
            for template in rune.modifier_templates.all():
                modifier = LegacyModifierAdapter.adapt(template)
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
    def migration_service(self) -> LegacyModifierMigrationService:
        """Return the legacy inventory and migration service for this engine."""
        if self.character_engine is None:
            return LegacyModifierMigrationService()
        return LegacyModifierMigrationService(self.character_engine._all_modifiers)

    @cached_property
    def _migrated_legacy_records(self):
        """Return all migrated legacy records that expose a typed modifier."""
        return [
            record
            for record in self.migration_service.migration_records()
            if record.primary_modifier() is not None
        ]

    @cached_property
    def _review_required_records(self):
        """Return migrated records that still require manual semantic review."""
        if self.character_engine is None:
            return []
        return [record for record in self.migration_service.migration_records() if record.requires_manual_review]

    def collect_active_modifiers(self, character=None, context: dict[str, Any] | None = None) -> list[BaseModifier]:
        """Collect all active typed modifiers for the current character and context."""
        if not context:
            if self._active_modifiers_cache is not None:
                return self._active_modifiers_cache
        context = context or {}
        collected = list(self._injected_modifiers)
        if self.character_engine is not None:
            learned_stack: set[int] = set()
            available_stack: set[int] = set()
            for record in self._migrated_legacy_records:
                modifier = record.primary_modifier()
                if modifier is None:
                    continue
                if not self._modifier_source_is_active(modifier, learned_stack, available_stack):
                    continue
                if not self._modifier_school_gate_is_open(modifier):
                    continue
                collected.append(modifier)
            collected.extend(self._active_trait_modifiers)
            collected.extend(self._active_item_rune_modifiers)
        expanded = self._expand_choice_bound_modifiers(collected)
        result = [modifier for modifier in expanded if modifier is not None and modifier.applies(context)]
        if not context:
            self._active_modifiers_cache = result
        return result

    def collect_legacy_modifiers(self, context: dict[str, Any] | None = None) -> list[BaseModifier]:
        """Return active legacy modifiers adapted for debug inspection only."""
        context = context or {}
        collected = list(self._injected_modifiers)
        if self.character_engine is not None:
            learned_stack: set[int] = set()
            available_stack: set[int] = set()
            for legacy_modifier in self.character_engine._all_modifiers:
                if not self.character_engine._modifier_source_is_active(legacy_modifier, learned_stack, available_stack):
                    continue
                if not self.character_engine._modifier_school_gate_is_open(legacy_modifier):
                    continue
                collected.append(LegacyModifierAdapter.adapt(legacy_modifier))
        return [modifier for modifier in collected if modifier.applies(context)]

    def resolve_numeric_total(self, target_domain: str, target_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve the summed numeric result for one target."""
        new_value = self._migrated_numeric_total(target_domain, target_key, context=context)
        if self.resolution_mode == ModifierResolutionMode.COMPARE:
            legacy_value = self._legacy_numeric_total(target_domain, target_key, context=context)
            self._append_comparison(
                target_domain=target_domain,
                target_key=target_key,
                legacy_value=legacy_value,
                new_value=new_value,
            )
        return new_value

    def resolve_choice_skill_modifier_total(self, skill_id: int, context: dict[str, Any] | None = None) -> int:
        """Resolve choice-bound skill modifiers according to the active debug mode."""
        new_value = self._migrated_choice_skill_modifier_total(skill_id, context=context)
        if self.resolution_mode == ModifierResolutionMode.COMPARE:
            legacy_value = self._legacy_choice_skill_modifier_total(skill_id)
            self._append_comparison(
                target_domain=TargetDomain.SKILL,
                target_key=f"selected_skill:{skill_id}",
                legacy_value=legacy_value,
                new_value=new_value,
            )
        return new_value

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

    def explain_resolution(self, target: tuple[str, str], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Return a debuggable breakdown for one target."""
        target_domain, target_key = target
        rows: list[dict[str, Any]] = []
        layer_entries = [("new", self.collect_active_modifiers(context=context))]
        if self.resolution_mode == ModifierResolutionMode.COMPARE:
            layer_entries.append(("legacy_debug", self.collect_legacy_modifiers(context=context)))

        for layer_name, modifiers in layer_entries:
            for modifier in modifiers:
                if modifier.target_domain != target_domain or modifier.target_key != target_key:
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

    def migration_records(self):
        """Return migration records for the bound legacy modifier inventory."""
        return list(self.migration_service.migration_records())

    def review_required_records(self):
        """Return migration records that still require manual review."""
        return list(self._review_required_records)

    def debug_legacy_numeric_total(self, target_domain: str, target_key: str, context: dict[str, Any] | None = None) -> int:
        """Return the legacy numeric result for one target for internal diagnostics."""
        return self._legacy_numeric_total(target_domain, target_key, context=context)

    def debug_legacy_choice_skill_modifier_total(self, skill_id: int) -> int:
        """Return the legacy choice-bound modifier total for one skill for diagnostics."""
        return self._legacy_choice_skill_modifier_total(skill_id)

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

    def _migrated_numeric_total(self, target_domain: str, target_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve one numeric target from migrated typed modifiers."""
        relevant_modifiers = [
            modifier
            for modifier in self.collect_active_modifiers(context=context)
            if modifier.target_domain == target_domain and modifier.target_key == target_key
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
            if modifier.operator == ModifierOperator.MIN_VALUE:
                resolved_total = max(resolved_total, int(resolved_value))
                continue
            if modifier.operator == ModifierOperator.MAX_VALUE:
                resolved_total = min(resolved_total, int(resolved_value))
                continue

            resolved_total += int(resolved_value)
        return int(resolved_total)

    def _migrated_choice_skill_modifier_total(self, skill_id: int, context: dict[str, Any] | None = None) -> int:
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

            if any(choice.selected_skill_id == skill_id for choice in choices):
                total += int(self._resolve_numeric_modifier(modifier) or 0)
        return total

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
        if self.character_engine is None or not scale_source:
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

    def _legacy_numeric_total(self, target_domain: str, target_key: str, context: dict[str, Any] | None = None) -> int:
        """Resolve one numeric target directly from the legacy modifier rows for debug use."""
        if self.character_engine is None:
            return 0
        if target_domain == TargetDomain.SKILL:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.SKILL, target_key)
        if target_domain == TargetDomain.SKILL_CATEGORY:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.CATEGORY, target_key)
        if target_domain == TargetDomain.ATTRIBUTE:
            return (
                self.character_engine._resolve_target_modifiers(Modifier.TargetKind.ATTRIBUTE, target_key)
                + self.character_engine._resolve_target_modifiers(Modifier.TargetKind.STAT, target_key)
            )
        if target_domain in {TargetDomain.DERIVED_STAT, TargetDomain.RULE_FLAG}:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.STAT, target_key)
        if target_domain == TargetDomain.COMBAT:
            total = self.character_engine._resolve_target_modifiers(Modifier.TargetKind.STAT, target_key)
            total += self.character_engine._resolve_target_modifiers(Modifier.TargetKind.SKILL, target_key)
            return total
        if target_domain == TargetDomain.ITEM:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.ITEM, target_key)
        if target_domain == TargetDomain.ITEM_CATEGORY:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.ITEM_CATEGORY, target_key)
        if target_domain == TargetDomain.SPECIALIZATION:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.SPECIALIZATION, target_key)
        if target_domain == TargetDomain.ENTITY:
            return self.character_engine._resolve_target_modifiers(Modifier.TargetKind.ENTITY, target_key)
        return 0

    def _legacy_choice_skill_modifier_total(self, skill_id: int) -> int:
        """Resolve choice-bound skill modifiers directly from legacy rows for debug use."""
        if self.character_engine is None:
            return 0
        return self.character_engine._legacy_choice_skill_modifier_total(skill_id)

    def _append_comparison(self, *, target_domain: str, target_key: str, legacy_value: int, new_value: int) -> None:
        """Append one comparison row without influencing production results."""
        matching_review_records = [
            record
            for record in self._review_required_records
            if (
                record.new_target_domain == target_domain
                and record.primary_modifier() is not None
                and (
                    record.primary_modifier().target_key == target_key
                    or record.primary_modifier().metadata.get("legacy_target_identifier") == target_key
                )
            )
        ]
        if legacy_value == new_value:
            classification = "match"
        elif matching_review_records:
            classification = "review_required"
        else:
            classification = "difference"
        notes = tuple(record.migration_note for record in matching_review_records)
        self._comparison_log.append(
            NumericResolutionComparison(
                target_domain=target_domain,
                target_key=target_key,
                legacy_value=int(legacy_value),
                new_value=int(new_value),
                matches=legacy_value == new_value,
                classification=classification,
                notes=notes,
            )
        )
