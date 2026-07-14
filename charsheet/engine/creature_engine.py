"""Calculation helpers for creature templates and character-owned creatures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property
import math
import re
from typing import Any

from charsheet.constants import (
    ATTR_CHA,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DEFENSE_RS,
    GK_MODS,
    QUALITY_BEL_MODS,
    QUALITY_COMMON,
    QUALITY_EXCELLENT,
    QUALITY_FINE,
    QUALITY_LEGENDARY,
    QUALITY_POOR,
    QUALITY_VERY_POOR,
    QUALITY_WRETCHED,
    SKILL_COMBAT,
)
from charsheet.models.creatures import (
    ATTRIBUTE_FIELD_MAP,
    CharacterCreature,
    CharacterCreatureAttributeIncrease,
    CharacterCreatureCommand,
    CharacterCreatureCommandPrerequisite,
    CharacterCreatureItem,
    Creature,
    CreatureAttack,
    CreatureSourceBinding,
)
from charsheet.models.character import CharacterItem
from charsheet.models.techniques import CharacterTechnique
from charsheet.modifiers.definitions import ModifierOperator, StackBehavior, TargetDomain
from charsheet.models.creatures import CREATURE_CARD_QUALITY_TRAINING_BUDGETS
from charsheet.models.items import Quality
from .item_engine import ItemEngine


WOUND_STAGE_LABELS = ("0", "-2", "-4", "-6", "Ausser Gefecht", "Koma")

CREATURE_KIND_LABELS = {
    QUALITY_WRETCHED: "Schwächliche Kreatur",
    QUALITY_VERY_POOR: "Einfache Kreatur",
    QUALITY_POOR: "Minderwertige Kreatur",
    QUALITY_COMMON: "Kreatur",
    QUALITY_FINE: "Besondere Kreatur",
    QUALITY_EXCELLENT: "Mächtige Kreatur",
    QUALITY_LEGENDARY: "Legendäre Kreatur",
    "unique": "Einzigartige Kreatur",
}


@dataclass(frozen=True)
class CreatureArmorTotals:
    natural_rs: int
    armor_rs: int
    total_rs: int
    encumbrance: int


@dataclass(frozen=True)
class CreatureSemanticEffect:
    """Creature-only numeric effect resolved without the character modifier engine."""

    source_id: str
    target_domain: str
    target_key: str
    operator: str
    value: Any = None
    mode: str = "flat"
    value_min: int | float | None = None
    value_max: int | float | None = None
    scaling: dict[str, Any] | None = None
    stack_behavior: str = StackBehavior.STACK
    priority: int = 0
    condition_text: str = ""
    rules_text: str = ""
    notes: str = ""
    metadata: dict[str, Any] | None = None

    @property
    def display_text(self) -> str:
        return self.condition_text or self.rules_text or self.notes


class CreatureEngine:
    """Resolve effective creature values without mutating the creature template."""

    def __init__(self, creature: Creature | CharacterCreature):
        self.source = creature
        self.instance = creature if isinstance(creature, CharacterCreature) else None
        self.creature = creature.creature if self.instance else creature

    def _override(self, field_name: str) -> Any:
        if self.instance is None:
            return None
        return getattr(self.instance, f"{field_name}_override", None)

    def _value(self, field_name: str, default: Any = 0) -> Any:
        override = self._override(field_name)
        if override is not None and override != "":
            return override
        return getattr(self.creature, field_name, default)

    def _stat_override(self, field_name: str) -> Any:
        if self.instance is not None:
            value = getattr(self.instance, field_name, None)
            if value is not None:
                return value
        return getattr(self.creature, field_name, None)

    def _instance_numeric_adjustment(self, field_name: str) -> int | float:
        if self.instance is None:
            return 0
        value = getattr(self.instance, field_name, None)
        if value in (None, ""):
            return 0
        return value

    @cached_property
    def _effective_trait_rows(self) -> list[Any]:
        """Return base traits plus active instance traits, replacing linked base rows."""
        skipped_base_trait_ids = set()
        override_rows = []
        if self.instance:
            override_rows = list(
                self.instance.trait_overrides.select_related("base_trait", "trait").prefetch_related(
                    "choices",
                    "choices__selected_creature_attack",
                    "trait__semantic_effects",
                    "trait__choice_definitions__allowed_attributes",
                    "trait__semantic_effects__target_skills",
                )
            )
            skipped_base_trait_ids = {
                row.base_trait_id
                for row in override_rows
                if row.active and row.base_trait_id is not None
            }
        base_rows = [
            row
            for row in self.creature.traits.select_related("trait").prefetch_related(
                "choices",
                "choices__selected_creature_attack",
                "trait__semantic_effects",
                "trait__choice_definitions__allowed_attributes",
                "trait__semantic_effects__target_skills",
            )
            if row.id not in skipped_base_trait_ids
        ]
        return base_rows + [row for row in override_rows if row.active]

    @cached_property
    def _effective_special_skill_rows(self) -> list[Any]:
        rows_by_skill_id = {
            row.skill_id: row
            for row in self.creature.special_skills.select_related("skill").prefetch_related(
                "skill__semantic_effects",
                "skill__semantic_effects__target_skills",
            )
        }
        if self.instance:
            for row in self.instance.special_skill_overrides.select_related("skill").prefetch_related(
                "skill__semantic_effects",
                "skill__semantic_effects__target_skills",
            ):
                rows_by_skill_id[row.skill_id] = row
        return list(rows_by_skill_id.values())

    @staticmethod
    def _effective_special_skill_row_value(row: Any) -> int:
        return int(getattr(row, "value_override", getattr(row, "value", 0)) or 0)

    @cached_property
    def _trait_levels_by_slug(self) -> dict[str, int]:
        levels: dict[str, int] = {}
        for row in self._effective_trait_rows:
            slug = row.trait.slug
            levels[slug] = max(levels.get(slug, 0), int(row.trait_level or 0))
        return levels

    @cached_property
    def _choice_targets_by_definition_id(self) -> dict[int, list[tuple[str, str]]]:
        targets: dict[int, list[tuple[str, str]]] = {}
        for row in self._effective_trait_rows:
            for choice in row.choices.all():
                target = choice.resolved_modifier_target()
                if target is None:
                    continue
                targets.setdefault(choice.definition_id, []).append(target)
        return targets

    @cached_property
    def _semantic_effects(self) -> list[CreatureSemanticEffect]:
        effects: list[CreatureSemanticEffect] = []
        for row in self._effective_trait_rows:
            for effect_row in row.trait.semantic_effects.all():
                if not effect_row.active_flag:
                    continue
                effects.extend(self._effect_row_to_creature_effects(effect_row, level=int(row.trait_level or 0)))
        for special_skill_row in self._effective_special_skill_rows:
            skill_value = self._effective_special_skill_row_value(special_skill_row)
            for effect_row in special_skill_row.skill.semantic_effects.all():
                if not effect_row.active_flag:
                    continue
                effects.extend(self._effect_row_to_creature_effects(effect_row, level=skill_value))
        return self._expand_choice_bound_effects(effects)

    def _effect_row_to_creature_effects(self, effect_row, *, level: int) -> list[CreatureSemanticEffect]:
        metadata = dict(effect_row.metadata or {})
        has_choice_target = any(field.name == "target_choice_definition" for field in effect_row._meta.fields)
        is_choice_bound = bool(has_choice_target and effect_row.target_choice_definition_id)
        if has_choice_target and effect_row.target_choice_definition_id:
            metadata["choice_binding"] = {
                "kind": "creature_trait_choice_definition",
                "id": int(effect_row.target_choice_definition_id),
            }
        source_id = getattr(getattr(effect_row, "trait", None), "slug", "") or getattr(getattr(effect_row, "special_skill", None), "slug", "")
        condition_text = str(getattr(effect_row, "condition_text", "") or "").strip()
        base_effect = CreatureSemanticEffect(
            source_id=source_id,
            target_domain=effect_row.target_domain,
            target_key=effect_row.target_key,
            operator=effect_row.operator,
            mode=effect_row.mode,
            value=effect_row._coerce_scalar(effect_row.value),
            value_min=effect_row.value_min,
            value_max=effect_row.value_max,
            scaling={**dict(effect_row.scaling or {}), "_trait_level": 1 if is_choice_bound else level},
            stack_behavior=effect_row.stack_behavior,
            priority=int(effect_row.priority),
            condition_text=condition_text,
            rules_text=effect_row.rules_text,
            notes=effect_row.notes,
            metadata=metadata,
        )
        if not effect_row.pk:
            return [base_effect]
        skill_slugs = list(effect_row.target_skills.order_by("slug").values_list("slug", flat=True))
        if not skill_slugs:
            return [base_effect]
        return [replace(base_effect, target_domain=TargetDomain.SKILL, target_key=slug) for slug in skill_slugs]

    def _expand_choice_bound_effects(self, effects: list[CreatureSemanticEffect]) -> list[CreatureSemanticEffect]:
        expanded: list[CreatureSemanticEffect] = []
        for effect in effects:
            choice_binding = (effect.metadata or {}).get("choice_binding") or {}
            if choice_binding.get("kind") != "creature_trait_choice_definition":
                expanded.append(effect)
                continue
            bound_targets = self._choice_targets_by_definition_id.get(int(choice_binding.get("id") or 0), [])
            if not bound_targets:
                expanded.append(effect)
                continue
            for target_domain, target_key in bound_targets:
                is_skill_choice_special_skill = (
                    effect.target_domain == TargetDomain.SKILL
                    and target_domain == "creature_special_skill"
                )
                is_creature_attack_damage = (
                    effect.target_domain == "creature_attack_damage"
                    and target_domain == "creature_attack"
                )
                if (
                    target_domain != effect.target_domain
                    and target_domain != "metadata"
                    and not is_skill_choice_special_skill
                    and not is_creature_attack_damage
                ):
                    continue
                expanded_domain = "creature_attack_damage" if is_creature_attack_damage else target_domain
                expanded.append(replace(effect, target_domain=expanded_domain, target_key=target_key))
        return expanded

    def _modifier_total(self, target_domain: str, target_key: str) -> int | float:
        return self._normalize_numeric_display_value(
            self._creature_effect_total(target_domain, target_key, conditional=False) or 0
        )

    def _creature_effect_total(self, target_domain: str, target_key: str, *, conditional: bool | None = None) -> int | float:
        relevant = [
            effect
            for effect in self._semantic_effects
            if effect.target_domain == target_domain and effect.target_key == target_key
            and (conditional is None or bool(effect.display_text) is conditional)
        ]
        resolved_total = 0
        seen_unique_sources: set[tuple[str, str, str]] = set()
        for effect in sorted(relevant, key=lambda entry: (entry.priority, entry.source_id, entry.target_domain, entry.target_key)):
            if effect.stack_behavior == StackBehavior.UNIQUE_BY_SOURCE:
                dedupe_key = (effect.source_id, effect.target_domain, effect.target_key)
                if dedupe_key in seen_unique_sources:
                    continue
                seen_unique_sources.add(dedupe_key)
            resolved_value = self._resolve_creature_effect_value(effect)
            if resolved_value is None:
                continue
            if effect.operator == ModifierOperator.OVERRIDE:
                resolved_total = resolved_value
                continue
            if effect.operator == ModifierOperator.MULTIPLY:
                resolved_total = resolved_total * resolved_value
                continue
            if effect.operator == ModifierOperator.FLOOR_DIVIDE:
                if not resolved_value:
                    continue
                resolved_total = resolved_total // resolved_value
                continue
            if effect.operator == ModifierOperator.MIN_VALUE:
                resolved_total = max(resolved_total, resolved_value)
                continue
            if effect.operator == ModifierOperator.MAX_VALUE:
                resolved_total = min(resolved_total, resolved_value)
                continue
            resolved_total += resolved_value
        return self._normalize_numeric_display_value(resolved_total)

    def _conditional_value_variants(self, target_domain: str, target_key: str, base_value: int | float) -> list[dict[str, Any]]:
        variants = []
        seen: set[tuple[int | float, str]] = set()
        relevant = [
            effect
            for effect in self._semantic_effects
            if effect.target_domain == target_domain
            and effect.target_key == target_key
            and effect.display_text
        ]
        for effect in sorted(relevant, key=lambda entry: (entry.priority, entry.source_id, entry.target_domain, entry.target_key)):
            resolved_value = self._resolve_creature_effect_value(effect)
            if resolved_value is None:
                continue
            value = self._apply_effect_to_base(base_value, effect, resolved_value)
            value = self._normalize_numeric_display_value(value)
            key = (value, effect.display_text)
            if key in seen:
                continue
            seen.add(key)
            variants.append({"value": value, "note": effect.display_text})
        return variants

    def _value_display_parts(
        self,
        target_domain: str,
        target_key: str,
        base_value: Any,
        *,
        signed: bool = False,
        compact: bool = False,
    ) -> list[dict[str, Any]]:
        if base_value is None:
            return [{"value": "-", "note": ""}]
        base_number = self._coerce_numeric(base_value, default=base_value)
        base_number = self._normalize_numeric_display_value(base_number)
        parts = [{"value": self._format_variant_value(base_number, signed=signed, compact=compact), "note": ""}]
        for variant in self._conditional_value_variants(target_domain, target_key, base_number):
            parts.append(
                {
                    "value": self._format_variant_value(variant["value"], signed=signed, compact=compact),
                    "note": variant["note"],
                }
            )
        return parts

    def _combined_value_display_parts(
        self,
        targets: list[tuple[str, str]],
        base_value: Any,
        *,
        signed: bool = False,
        compact: bool = False,
    ) -> list[dict[str, Any]]:
        if base_value is None:
            return [{"value": "-", "note": ""}]
        base_number = self._coerce_numeric(base_value, default=base_value)
        base_number = self._normalize_numeric_display_value(base_number)
        parts = [{"value": self._format_variant_value(base_number, signed=signed, compact=compact), "note": ""}]
        seen = set()
        for target_domain, target_key in targets:
            for variant in self._conditional_value_variants(target_domain, target_key, base_number):
                key = (variant["value"], variant["note"])
                if key in seen:
                    continue
                seen.add(key)
                parts.append(
                    {
                        "value": self._format_variant_value(variant["value"], signed=signed, compact=compact),
                        "note": variant["note"],
                    }
                )
        return parts

    @classmethod
    def _format_variant_value(cls, value: Any, *, signed: bool = False, compact: bool = False) -> str:
        if compact:
            return cls._compact_number(value) or ""
        number = cls._coerce_numeric(value, default=value)
        number = cls._normalize_numeric_display_value(number)
        if signed:
            if isinstance(number, int):
                return f"{number:+d}"
            return f"{number:+g}"
        return str(number)

    @staticmethod
    def _apply_effect_to_base(base_value: int | float, effect: CreatureSemanticEffect, resolved_value: int | float) -> int | float:
        if effect.operator == ModifierOperator.OVERRIDE:
            return resolved_value
        if effect.operator == ModifierOperator.MULTIPLY:
            return base_value * resolved_value
        if effect.operator == ModifierOperator.FLOOR_DIVIDE:
            if not resolved_value:
                return base_value
            return base_value // resolved_value
        if effect.operator == ModifierOperator.MIN_VALUE:
            return max(base_value, resolved_value)
        if effect.operator == ModifierOperator.MAX_VALUE:
            return min(base_value, resolved_value)
        return base_value + resolved_value

    @staticmethod
    def _normalize_numeric_display_value(value: Any) -> Any:
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    def _resolve_creature_effect_value(self, effect: CreatureSemanticEffect) -> int | float | None:
        numeric_value = self._coerce_numeric(effect.value)
        if numeric_value is None:
            return None
        if str(effect.mode or "flat") == "scaled":
            scaling = dict(effect.scaling or {})
            scale_source = str(scaling.get("scale_source") or "")
            scale_value = int(scaling.get("_trait_level") or 0) if scale_source == "trait_level" else None
            if scale_value is None:
                return 0
            mul = self._coerce_numeric(scaling.get("mul"), default=1)
            div = self._coerce_numeric(scaling.get("div"), default=1)
            if not div:
                return 0
            raw_value = (scale_value * numeric_value * mul) / div
            numeric_value = math.ceil(raw_value) if str(scaling.get("round_mode") or "floor") == "ceil" else math.floor(raw_value)
        if effect.value_min is not None:
            numeric_value = max(numeric_value, self._coerce_numeric(effect.value_min, default=numeric_value))
        if effect.value_max is not None:
            numeric_value = min(numeric_value, self._coerce_numeric(effect.value_max, default=numeric_value))
        if effect.operator in {ModifierOperator.FLAT_SUB, ModifierOperator.CONDITIONAL_PENALTY}:
            return -abs(numeric_value)
        if effect.operator == ModifierOperator.MULTIPLY:
            return float(numeric_value)
        if effect.operator == ModifierOperator.FLOOR_DIVIDE:
            return float(numeric_value)
        return self._normalize_numeric_display_value(numeric_value)

    @staticmethod
    def _coerce_numeric(value: Any, *, default: int | float | None = None) -> int | float | None:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return default

    def _effect_notes(self, target_domain: str, target_key: str) -> list[str]:
        return [
            effect.display_text
            for effect in self._semantic_effects
            if effect.target_domain == target_domain
            and effect.target_key == target_key
            and effect.display_text
        ]

    def _join_effect_notes(self, target_domain: str, target_key: str) -> str:
        seen = []
        for text in self._effect_notes(target_domain, target_key):
            if text not in seen:
                seen.append(text)
        return "; ".join(seen)

    def _join_effect_notes_for_targets(self, targets: list[tuple[str, str]]) -> str:
        seen = []
        for target_domain, target_key in targets:
            for text in self._effect_notes(target_domain, target_key):
                if text not in seen:
                    seen.append(text)
        return "; ".join(seen)

    def effect_condition_summary(self) -> list[dict[str, str]]:
        rows = []
        seen: set[tuple[str, str, str]] = set()
        for effect in self._semantic_effects:
            text = effect.display_text
            if not text:
                continue
            if self._effect_is_rendered_inline(effect):
                continue
            key = (effect.target_domain, effect.target_key, text)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "target": self._effect_target_label(effect.target_domain, effect.target_key),
                    "text": text,
                }
            )
        return rows

    @staticmethod
    def _effect_is_rendered_inline(effect: CreatureSemanticEffect) -> bool:
        inline_targets = {
            TargetDomain.ATTRIBUTE,
            TargetDomain.MOVEMENT,
            TargetDomain.COMBAT,
            TargetDomain.SKILL,
            "creature_special_skill",
        }
        if effect.target_domain in inline_targets:
            return True
        return effect.target_domain == TargetDomain.DERIVED_STAT and effect.target_key in {
            "initiative",
            "vw",
            "sr",
            "gw",
            "rs",
            "natural_rs",
            "encumbrance",
        }

    def _effect_target_label(self, target_domain: str, target_key: str) -> str:
        if target_domain == TargetDomain.ATTRIBUTE:
            return target_key
        if target_domain == TargetDomain.DERIVED_STAT:
            labels = {
                "initiative": "Initiative",
                "vw": "VW",
                "sr": "SR",
                "gw": "GW",
                "rs": "RS",
                "natural_rs": "RS",
                "wound_step": "Wundschwelle",
                "wound_penalty_reduction": "Wundmali reduzieren",
                "encumbrance": "BEL",
            }
            return labels.get(target_key, target_key)
        if target_domain == TargetDomain.MOVEMENT:
            labels = {
                "combat": "Bewegung Kampf",
                "march": "Bewegung Marsch",
                "sprint": "Bewegung Sprint",
                "swim": "Schwimmen",
                "swim_combat": "Schwimmen Kampf",
                "swim_march": "Schwimmen Marsch",
                "swim_sprint": "Schwimmen Sprint",
                "fly_combat": "Flug Kampf",
                "fly_march": "Flug Marsch",
                "fly_sprint": "Flug Sprint",
            }
            return labels.get(target_key, target_key)
        if target_domain == TargetDomain.COMBAT:
            labels = {"attack_value": "Angriff", "damage": "Schaden"}
            return labels.get(target_key, target_key)
        if target_domain == "creature_attack":
            attack = self.creature.attacks.filter(pk=target_key).first()
            return attack.name if attack is not None else f"Angriff {target_key}"
        if target_domain == "creature_attack_damage":
            attack = self.creature.attacks.filter(pk=target_key).first()
            name = attack.name if attack is not None else f"Angriff {target_key}"
            return f"{name} Schaden"
        if target_domain == "creature_attack_type_damage":
            return f"{target_key} Schaden"
        if target_domain == "creature_special_skill":
            for row in self.creature.special_skills.select_related("skill"):
                if row.skill.slug == target_key:
                    return row.skill.name
            return target_key
        if target_domain == TargetDomain.SKILL:
            for row in self.creature.skills.select_related("skill"):
                if row.skill.slug == target_key:
                    return row.skill.name
            return target_key
        if target_domain == TargetDomain.SKILL_CATEGORY:
            for row in self.creature.skills.select_related("skill__category"):
                if row.skill.category.slug == target_key:
                    return row.skill.category.name
            return target_key
        return f"{target_domain}:{target_key}"

    @cached_property
    def attribute_increase_totals(self) -> dict[str, int]:
        if self.instance is None:
            return {}
        return {
            row.attribute: int(row.amount or 0)
            for row in self.instance.attribute_increases.all()
        }

    def display_name(self) -> str:
        if self.instance:
            return self.instance.display_name
        return self.creature.display_name

    def image(self):
        if self.instance:
            return self.instance.image
        return self.creature.image

    def size_class(self) -> str:
        if self.instance and self.instance.size_class_override:
            return self.instance.size_class_override
        return self.creature.size_class

    def size_modifier(self) -> int:
        return int(GK_MODS.get(self.size_class(), 0))

    def attribute_base_mod(self, attribute: str) -> int | None:
        field_name = ATTRIBUTE_FIELD_MAP.get(attribute)
        if not field_name:
            return 0
        override = self._override(field_name)
        if override is not None and override != "":
            value = override
        else:
            value = None
            for row in self.creature.attributes.select_related("attribute"):
                if row.attribute.short_name == attribute:
                    value = row.base_value
                    break
        if value is None and attribute == ATTR_CHA:
            return None
        return (
            self._attribute_modifier(value)
            + self._modifier_total(TargetDomain.ATTRIBUTE, attribute)
        )

    def attribute_mod(self, attribute: str) -> int | None:
        base_mod = self.attribute_base_mod(attribute)
        if base_mod is None:
            return None
        return base_mod + int(self.attribute_increase_totals.get(attribute, 0) or 0)

    @staticmethod
    def _attribute_modifier(value: Any) -> int:
        """Return the modifier derived from a stored creature attribute value."""
        return int(value or 0) - 5

    def initiative(self) -> int:
        base = self.creature.initiative_override
        if base is None:
            base = int(self.attribute_mod(ATTR_WA) or 0)
        return int(base) + int(self._instance_numeric_adjustment("initiative_override")) + self._modifier_total(TargetDomain.DERIVED_STAT, "initiative")

    def vw(self) -> int:
        if self.creature.vw_override is not None:
            base = int(self.creature.vw_override)
        else:
            base = 14 + int(self.attribute_mod(ATTR_GE) or 0) + int(self.attribute_mod(ATTR_WA) or 0) + self.size_modifier()
        return base + int(self._instance_numeric_adjustment("vw_override")) + self._modifier_total(TargetDomain.DERIVED_STAT, "vw")

    def sr(self) -> int:
        if self.creature.sr_override is not None:
            base = int(self.creature.sr_override)
        else:
            base = 14 + int(self.attribute_mod(ATTR_ST) or 0) + int(self.attribute_mod(ATTR_KON) or 0)
        return base + int(self._instance_numeric_adjustment("sr_override")) + self._modifier_total(TargetDomain.DERIVED_STAT, "sr")

    def gw(self) -> int:
        if self.creature.gw_override is not None:
            base = int(self.creature.gw_override)
        else:
            base = 14 + int(self.attribute_mod(ATTR_INT) or 0) + int(self.attribute_mod(ATTR_WILL) or 0)
        return base + int(self._instance_numeric_adjustment("gw_override")) + self._modifier_total(TargetDomain.DERIVED_STAT, "gw")

    def fear_resistance_bonus(self) -> int:
        return int(self._value("fear_resistance_bonus", 0) or 0)

    def defense_extra_label(self) -> str:
        return str(self._value("defense_extra_label", "") or "").strip()

    def defense_extra_value(self) -> int | None:
        value = self.creature.fear_resistance_bonus
        adjustment = self._instance_numeric_adjustment("fear_resistance_bonus_override")
        if value is None and not adjustment:
            return None
        value = int(value or 0) + int(adjustment or 0)
        if value is None or value == "":
            return None
        return int(value)

    def gw_against_fear(self) -> int:
        return int(self.defense_extra_value() or 0)

    def wound_step(self) -> int:
        if self.creature.wound_step_override is not None:
            base = int(self.creature.wound_step_override)
        else:
            base = 5 + int(self.attribute_mod(ATTR_KON) or 0)
        return max(1, base + int(self._instance_numeric_adjustment("wound_step_override")) + self._modifier_total(TargetDomain.DERIVED_STAT, "wound_step"))

    def wound_penalty_reduction(self) -> int:
        return max(0, int(self._modifier_total(TargetDomain.DERIVED_STAT, "wound_penalty_reduction") or 0))

    def wound_rows(self) -> list[dict[str, Any]]:
        explicit_thresholds = self._wound_thresholds_override()
        if explicit_thresholds:
            return [
                {"label": label, "threshold": threshold, "penalty": self._wound_penalty_for_label(label)}
                for label, threshold in zip(WOUND_STAGE_LABELS, explicit_thresholds)
            ]
        step = max(1, self.wound_step())
        return [
            {"label": label, "threshold": step * index, "penalty": self._wound_penalty_for_label(label)}
            for index, label in enumerate(WOUND_STAGE_LABELS, start=1)
        ]

    def _wound_thresholds_override(self) -> list[int]:
        raw_value = ""
        if self.instance is not None:
            raw_value = getattr(self.instance, "wound_thresholds_override", "") or ""
        if not raw_value:
            raw_value = getattr(self.creature, "wound_thresholds_override", "") or ""
        raw = str(raw_value).strip()
        if not raw:
            return []
        thresholds: list[int] = []
        for token in re.split(r"[,;/\s]+", raw):
            if not token:
                continue
            try:
                threshold = int(token)
            except (TypeError, ValueError):
                continue
            if threshold > 0:
                thresholds.append(threshold)
        return thresholds[: len(WOUND_STAGE_LABELS)]

    def current_wound_zone(self) -> dict[str, Any]:
        damage = int(getattr(self.instance, "current_damage", 0) or 0)
        rows = self.wound_rows()
        current = {"label": "-", "threshold": 0, "penalty": 0}
        for row in rows:
            if damage >= int(row["threshold"]):
                current = {
                    "label": row["label"],
                    "threshold": row["threshold"],
                    "penalty": row["penalty"],
                }
            else:
                break
        return current

    def movement(self) -> dict[str, Any]:
        return {
            "combat": self._movement_value("combat_speed", "combat", 0),
            "march": self._movement_value("march_speed", "march", 0),
            "sprint": self._movement_value("sprint_speed", "sprint", 0),
            "swim": self._movement_value("swimming_speed", "swim", 0),
            "swim_combat": self._movement_value("combat_swimming_speed", "swim_combat", None),
            "swim_march": self._movement_value("march_swimming_speed", "swim_march", None),
            "swim_sprint": self._movement_value("sprint_swimming_speed", "swim_sprint", None),
            "fly_combat": self._movement_value("combat_fly_speed", "fly_combat", None),
            "fly_march": self._movement_value("march_fly_speed", "fly_march", None),
            "fly_sprint": self._movement_value("sprint_fly_speed", "fly_sprint", None),
        }

    def _movement_value(self, field_name: str, target_key: str, default: Any) -> Any:
        value = getattr(self.creature, field_name, default)
        adjustment = self._instance_numeric_adjustment(f"{field_name}_override")
        if value is None and adjustment:
            value = 0
        if value is not None:
            value += adjustment
        bonus = self._modifier_total(TargetDomain.MOVEMENT, target_key)
        if value is None:
            return None if not bonus else bonus
        return max(0, value + bonus)

    def movement_display(self) -> dict[str, str | None]:
        movement = self.movement()
        return {key: self._compact_number(value) for key, value in movement.items()}

    def movement_display_parts(self) -> dict[str, list[dict[str, Any]]]:
        movement = self.movement()
        return {
            key: self._value_display_parts(TargetDomain.MOVEMENT, key, value, compact=True)
            for key, value in movement.items()
        }

    def movement_display_text(self) -> dict[str, str | None]:
        return {
            key: self._display_parts_text(parts)
            for key, parts in self.movement_display_parts().items()
        }

    def movement_tooltip_text(self) -> dict[str, str | None]:
        return {
            key: self._display_parts_text(parts, include_notes=True, mana_tokens=True)
            for key, parts in self.movement_display_parts().items()
        }

    @staticmethod
    def _display_parts_text(
        parts: list[dict[str, Any]],
        *,
        include_notes: bool = False,
        mana_tokens: bool = False,
    ) -> str | None:
        if not parts:
            return None
        rendered = []
        for part in parts:
            value = str(part.get("value", ""))
            if mana_tokens:
                value = f"[[MANA:{value}]]"
            note = str(part.get("note", "") or "")
            rendered.append(f"{value} ({note})" if include_notes and note else value)
        return " ".join(rendered) if mana_tokens else "/".join(rendered)

    def movement_notes(self) -> dict[str, str]:
        return {
            "combat": self._join_effect_notes(TargetDomain.MOVEMENT, "combat"),
            "march": self._join_effect_notes(TargetDomain.MOVEMENT, "march"),
            "sprint": self._join_effect_notes(TargetDomain.MOVEMENT, "sprint"),
            "swim": self._join_effect_notes(TargetDomain.MOVEMENT, "swim"),
            "swim_combat": self._join_effect_notes(TargetDomain.MOVEMENT, "swim_combat"),
            "swim_march": self._join_effect_notes(TargetDomain.MOVEMENT, "swim_march"),
            "swim_sprint": self._join_effect_notes(TargetDomain.MOVEMENT, "swim_sprint"),
            "fly_combat": self._join_effect_notes(TargetDomain.MOVEMENT, "fly_combat"),
            "fly_march": self._join_effect_notes(TargetDomain.MOVEMENT, "fly_march"),
            "fly_sprint": self._join_effect_notes(TargetDomain.MOVEMENT, "fly_sprint"),
        }

    def equipped_items(self):
        if self.instance is None:
            return CharacterCreatureItem.objects.none()
        return (
            self.instance.items.filter(equipped=True)
            .select_related("item", "item__default_quality", "quality", "item__armorstats")
            .order_by("item__name")
        )

    def _armor_rs(self, creature_item: CharacterCreatureItem) -> int:
        stats = getattr(creature_item.item, "armorstats", None)
        if stats is None:
            return 0
        if creature_item.armor_rs_total_override is not None:
            return int(creature_item.armor_rs_total_override)
        if stats.rs_total:
            return int(stats.rs_total)
        zone_fields = (
            "armor_rs_head",
            "armor_rs_torso",
            "armor_rs_arm_left",
            "armor_rs_arm_right",
            "armor_rs_leg_left",
            "armor_rs_leg_right",
        )
        total = 0
        for field in zone_fields:
            override = getattr(creature_item, f"{field}_override", None)
            stat_field = field.replace("armor_", "")
            total += int(override if override is not None else getattr(stats, stat_field, 0))
        return total

    def _armor_encumbrance(self, creature_item: CharacterCreatureItem) -> int:
        stats = getattr(creature_item.item, "armorstats", None)
        if stats is None:
            return 0
        encumbrance = (
            creature_item.armor_encumbrance_override
            if creature_item.armor_encumbrance_override is not None
            else stats.encumbrance
        )
        effective_quality = ItemEngine.normalize_quality(creature_item.quality)
        base_quality = ItemEngine.normalize_quality(creature_item.item.default_quality)
        encumbrance += int(QUALITY_BEL_MODS.get(effective_quality, 0) or 0) - int(QUALITY_BEL_MODS.get(base_quality, 0) or 0)
        return max(0, int(encumbrance))

    def armor_totals(self) -> CreatureArmorTotals:
        natural_rs = (
            int(self.creature.natural_rs or 0)
            + int(self._instance_numeric_adjustment("natural_rs_override"))
            + self._modifier_total(TargetDomain.DERIVED_STAT, DEFENSE_RS)
            + self._modifier_total(TargetDomain.DERIVED_STAT, "natural_rs")
        )
        natural_rs = max(0, natural_rs)
        armor_rs = 0
        encumbrance = 0
        for creature_item in self.equipped_items():
            armor_rs += self._armor_rs(creature_item)
            encumbrance += self._armor_encumbrance(creature_item)
        return CreatureArmorTotals(
            natural_rs=natural_rs,
            armor_rs=armor_rs,
            total_rs=natural_rs + armor_rs,
            encumbrance=encumbrance,
        )

    def attacks(self) -> list[dict[str, Any]]:
        attack_value_bonus = (
            int(self.attribute_increase_totals.get(ATTR_GE, 0) or 0)
            + self.size_modifier()
            + self._modifier_total(TargetDomain.COMBAT, "attack_value")
        )
        damage_bonus = (
            int(self.attribute_increase_totals.get(ATTR_ST, 0) or 0)
            + self._modifier_total(TargetDomain.COMBAT, "damage")
        )
        return [
            self._attack_context(attack, attack_value_bonus, damage_bonus)
            for attack in self.creature.attacks.select_related("attack_type").all()
        ]

    def _attack_context(self, attack, attack_value_bonus: int, damage_bonus: int) -> dict[str, Any]:
        attack_target_key = str(attack.pk)
        attack_specific_bonus = self._modifier_total("creature_attack", attack_target_key)
        attack_value = attack.attack_value + attack_value_bonus + attack_specific_bonus
        attack_specific_damage_bonus = self._modifier_total("creature_attack_damage", attack_target_key)
        attack_type_key = getattr(getattr(attack, "attack_type", None), "slug", "")
        attack_type_damage_bonus = (
            self._modifier_total("creature_attack_type_damage", attack_type_key)
            if attack_type_key
            else 0
        )
        total_damage_bonus = damage_bonus + attack_specific_damage_bonus + attack_type_damage_bonus
        damage = self._apply_damage_bonus(self._format_damage(attack), total_damage_bonus)
        notes = str(attack.notes or "")
        show_notes_as_damage = bool(getattr(attack, "show_notes_as_damage", False) and notes)
        append_notes_to_damage = bool(getattr(attack, "append_notes_to_damage", False) and notes and not show_notes_as_damage)
        damage_display = damage
        if show_notes_as_damage:
            damage_display = notes
        elif append_notes_to_damage:
            damage_display = self._append_notes_to_damage_display(damage, notes, attack.damage_type)
        return {
            "name": attack.name,
            "attack_value": attack_value,
            "attack_value_parts": self._combined_value_display_parts(
                [
                    (TargetDomain.COMBAT, "attack_value"),
                    ("creature_attack", attack_target_key),
                ],
                attack_value,
            ),
            "attack_value_note": "; ".join(
                note
                for note in (
                    self._join_effect_notes(TargetDomain.COMBAT, "attack_value"),
                    self._join_effect_notes("creature_attack", attack_target_key),
                )
                if note
            ),
            "damage": damage,
            "damage_variants": [
                {
                    "value": self._apply_damage_bonus(damage, variant["value"] - int(damage_bonus or 0)),
                    "note": variant["note"],
                }
                for variant in self._conditional_value_variants(TargetDomain.COMBAT, "damage", int(total_damage_bonus or 0))
            ] + [
                {
                    "value": self._apply_damage_bonus(damage, variant["value"] - int(total_damage_bonus or 0)),
                    "note": variant["note"],
                }
                for variant in self._conditional_value_variants(
                    "creature_attack_damage",
                    attack_target_key,
                    int(total_damage_bonus or 0),
                )
            ] + [
                {
                    "value": self._apply_damage_bonus(damage, variant["value"] - int(total_damage_bonus or 0)),
                    "note": variant["note"],
                }
                for variant in self._conditional_value_variants(
                    "creature_attack_type_damage",
                    attack_type_key,
                    int(total_damage_bonus or 0),
                )
                if attack_type_key
            ],
            "damage_display": damage_display,
            "notes": "" if show_notes_as_damage or append_notes_to_damage else notes,
            "show_notes_as_damage": show_notes_as_damage,
            "append_notes_to_damage": append_notes_to_damage,
        }

    @staticmethod
    def _append_notes_to_damage_display(damage: str, notes: str, damage_type: str) -> str:
        damage = str(damage or "").strip()
        notes = str(notes or "").strip()
        damage_type = str(damage_type or "").strip()
        if not notes:
            return damage
        if not damage:
            return notes
        if damage_type and damage == damage_type:
            return f"{notes} {damage_type}".strip()
        type_suffix = f" {damage_type}" if damage_type else ""
        if type_suffix and damage.endswith(type_suffix):
            damage_without_type = damage[: -len(type_suffix)].rstrip()
            return f"{damage_without_type} {notes}{type_suffix}".strip()
        return f"{damage} {notes}".strip()

    def skills(self) -> list[dict[str, Any]]:
        overrides = {}
        if self.instance:
            overrides = {
                entry.skill_id: entry
                for entry in self.instance.skill_overrides.select_related("skill", "skill__attribute", "skill__category")
            }
        base_rows = []
        seen = set()
        for row in self.creature.skills.select_related("skill", "skill__attribute", "skill__category"):
            override = overrides.get(row.skill_id)
            seen.add(row.skill_id)
            value = override.value_override if override else row.value
            deviation = int(row.deviation or 0) + (int(override.deviation or 0) if override else 0)
            attribute_modifier = self._skill_attribute_modifier(row.skill)
            category_slug = row.skill.category.slug
            effective_value = (
                value
                + deviation
                + attribute_modifier
                + self._skill_size_modifier(row.skill)
                + self._modifier_total(TargetDomain.SKILL_CATEGORY, category_slug)
                + self._modifier_total(TargetDomain.SKILL, row.skill.slug)
            )
            base_rows.append(
                {
                    "name": row.skill.name,
                    "value": effective_value,
                    "value_parts": self._combined_value_display_parts(
                        [
                            (TargetDomain.SKILL_CATEGORY, category_slug),
                            (TargetDomain.SKILL, row.skill.slug),
                        ],
                        effective_value,
                    ),
                    "deviation": deviation,
                        "attribute": row.skill.attribute.short_name,
                        "attribute_modifier": attribute_modifier,
                        "effect_note": self._join_effect_notes_for_targets(
                            [
                                (TargetDomain.SKILL_CATEGORY, category_slug),
                                (TargetDomain.SKILL, row.skill.slug),
                            ]
                        ),
                        "notes": override.notes if override and override.notes else row.notes or row.skill.description,
                }
            )
        for skill_id, override in overrides.items():
            if skill_id not in seen:
                deviation = int(override.deviation or 0)
                attribute_modifier = self._skill_attribute_modifier(override.skill)
                category_slug = override.skill.category.slug
                effective_value = (
                    override.value_override
                    + deviation
                    + attribute_modifier
                    + self._skill_size_modifier(override.skill)
                    + self._modifier_total(TargetDomain.SKILL_CATEGORY, category_slug)
                    + self._modifier_total(TargetDomain.SKILL, override.skill.slug)
                )
                base_rows.append(
                    {
                        "name": override.skill.name,
                        "value": effective_value,
                        "value_parts": self._combined_value_display_parts(
                            [
                                (TargetDomain.SKILL_CATEGORY, category_slug),
                                (TargetDomain.SKILL, override.skill.slug),
                            ],
                            effective_value,
                        ),
                        "deviation": deviation,
                        "attribute": override.skill.attribute.short_name,
                        "attribute_modifier": attribute_modifier,
                        "effect_note": self._join_effect_notes_for_targets(
                            [
                                (TargetDomain.SKILL_CATEGORY, category_slug),
                                (TargetDomain.SKILL, override.skill.slug),
                            ]
                        ),
                        "notes": override.notes or override.skill.description,
                    }
                )
        return base_rows

    def _skill_attribute_modifier(self, skill) -> int:
        attribute = getattr(skill, "attribute", None)
        short_name = getattr(attribute, "short_name", "")
        if not short_name:
            return 0
        return int(self.attribute_mod(short_name) or 0)

    def _skill_size_modifier(self, skill) -> int:
        category = getattr(skill, "category", None)
        category_slug = getattr(category, "slug", "")
        if category_slug == SKILL_COMBAT:
            return self.size_modifier()
        if getattr(skill, "slug", "") == "skill_evasion":
            return self.size_modifier()
        if getattr(skill, "slug", "") == "skill_hide":
            return self.size_modifier() * 2
        return 0

    def special_skills(self) -> list[dict[str, Any]]:
        overrides = {}
        if self.instance:
            overrides = {
                entry.skill_id: entry
                for entry in self.instance.special_skill_overrides.select_related("skill")
            }
        rows = []
        seen = set()
        for row in self.creature.special_skills.select_related("skill"):
            override = overrides.get(row.skill_id)
            seen.add(row.skill_id)
            value = (override.value_override if override else row.value) + self._modifier_total("creature_special_skill", row.skill.slug)
            rows.append(
                {
                    "name": row.skill.name,
                    "value": value,
                    "value_parts": self._value_display_parts("creature_special_skill", row.skill.slug, value, signed=True),
                    "effect_note": self._join_effect_notes("creature_special_skill", row.skill.slug),
                    "notes": override.notes if override and override.notes else row.notes or row.skill.description,
                    "kind": "creature",
                }
            )
        for skill_id, override in overrides.items():
            if skill_id not in seen:
                value = override.value_override + self._modifier_total("creature_special_skill", override.skill.slug)
                rows.append(
                    {
                        "name": override.skill.name,
                        "value": value,
                        "value_parts": self._value_display_parts("creature_special_skill", override.skill.slug, value, signed=True),
                        "effect_note": self._join_effect_notes("creature_special_skill", override.skill.slug),
                        "notes": override.notes,
                        "kind": "creature",
                    }
                )
        return rows

    def traits(self) -> list[dict[str, Any]]:
        def choice_summary(trait_row) -> str:
            choices = []
            for choice in trait_row.choices.all():
                display = choice.selected_target_display()
                if display and display != "-":
                    choices.append(f"{choice.definition.name}: {display}")
            return ", ".join(choices)

        rows = [
            {
                "name": trait.display_name,
                "level": trait.level,
                "description": trait.description,
                "choice_summary": choice_summary(trait),
            }
            for trait in self._effective_trait_rows
        ]
        return rows

    def commands(self) -> list[dict[str, Any]]:
        rows = [
            {
                "name": reference.command.name,
                "slug": reference.command.slug,
                "ep_cost": reference.command.ep_cost,
                "difficulty": reference.command.difficulty,
                "prerequisites": self._serialize_command_prerequisites(reference.command),
                "prerequisite_display": reference.command.prerequisite_display,
                "training_days": reference.command.training_days,
                "description": reference.command.description,
            }
            for reference in self.creature.commands.select_related("command")
        ]
        if self.instance:
            base_command_ids = {reference.command_id for reference in self.creature.commands.all()}
            for command_row in self.instance.commands.select_related("command").prefetch_related("prerequisite_links__prerequisite__command"):
                if command_row.command_id in base_command_ids:
                    continue
                rows.append(
                    {
                        "name": command_row.name,
                        "slug": command_row.slug,
                        "ep_cost": command_row.ep_cost,
                        "difficulty": command_row.difficulty,
                        "prerequisites": [
                            [{"name": prerequisite.name, "slug": prerequisite.slug} for prerequisite in group]
                            for group in command_row.prerequisite_groups
                        ],
                        "prerequisite_display": command_row.prerequisite_display,
                        "training_days": command_row.training_days,
                        "description": command_row.description,
                    }
                )
        return rows

    def card_context(self) -> dict[str, Any]:
        armor = self.armor_totals()
        defense_extra_value = self.defense_extra_value()
        defense_extra_label = self.defense_extra_label()
        wound_rows = self.wound_rows()
        wound_zone = self.current_wound_zone()
        quality = self.instance.quality if self.instance else self.creature.quality
        normalized_quality = ItemEngine.normalize_quality(quality)
        holo_kind = "creature-legendary" if normalized_quality == "legendary" else "creature"
        movement = self.movement()
        movement_notes = self.movement_notes()
        has_ground = all(movement.get(key) is not None for key in ("combat", "march", "sprint"))
        has_single_swim = movement.get("swim") not in (None, "", 0, 0.0)
        has_swim = all(movement.get(key) is not None for key in ("swim_combat", "swim_march", "swim_sprint"))
        has_flight = any(movement.get(key) is not None for key in ("fly_combat", "fly_march", "fly_sprint"))
        quality_choices = [
            {
                "value": row.code,
                "label": row.name,
                "color": row.hex_color,
                "selected": row.code == normalized_quality,
                "advantage_points": CREATURE_CARD_QUALITY_TRAINING_BUDGETS.get(row.code, (0, 0))[0],
                "disadvantage_points": CREATURE_CARD_QUALITY_TRAINING_BUDGETS.get(row.code, (0, 0))[1],
            }
            for row in Quality.objects.all()
        ]
        return {
            "id": self.instance.pk if self.instance else self.creature.pk,
            "name": self.display_name(),
            "creature_name": self.creature.display_name,
            "image": self.image(),
            "default_image": self.creature.image,
            "has_custom_image": bool(self.instance and self.instance.image_override),
            "quality": normalized_quality,
            "quality_label": getattr(quality, "name", normalized_quality),
            "quality_color": ItemEngine.quality_color(quality),
            "quality_choices": quality_choices,
            "holo": normalized_quality in {"legendary", "unique"},
            "holo_kind": holo_kind,
            "creature_kind_label": creature_kind_label(quality),
            "size_class": self.size_class(),
            "size_modifier": self.size_modifier(),
            "initiative": self.initiative(),
            "initiative_note": self._join_effect_notes(TargetDomain.DERIVED_STAT, "initiative"),
            "initiative_variants": self._conditional_value_variants(TargetDomain.DERIVED_STAT, "initiative", self.initiative()),
            "vw": self.vw(),
            "vw_note": self._join_effect_notes(TargetDomain.DERIVED_STAT, "vw"),
            "vw_variants": self._conditional_value_variants(TargetDomain.DERIVED_STAT, "vw", self.vw()),
            "sr": self.sr(),
            "sr_note": self._join_effect_notes(TargetDomain.DERIVED_STAT, "sr"),
            "sr_variants": self._conditional_value_variants(TargetDomain.DERIVED_STAT, "sr", self.sr()),
            "gw": self.gw(),
            "gw_note": self._join_effect_notes(TargetDomain.DERIVED_STAT, "gw"),
            "gw_variants": self._conditional_value_variants(TargetDomain.DERIVED_STAT, "gw", self.gw()),
            "gw_extra": defense_extra_value if defense_extra_value else None,
            "gw_extra_label": defense_extra_label,
            "gw_fear": self.gw_against_fear() if defense_extra_value else None,
            "fear_bonus": defense_extra_value,
            "rs_natural": armor.natural_rs,
            "rs_armor": armor.armor_rs,
            "rs_total": armor.total_rs,
            "rs_note": self._join_effect_notes(TargetDomain.DERIVED_STAT, "rs") or self._join_effect_notes(TargetDomain.DERIVED_STAT, "natural_rs"),
            "rs_variants": (
                self._conditional_value_variants(TargetDomain.DERIVED_STAT, "rs", armor.total_rs)
                + self._conditional_value_variants(TargetDomain.DERIVED_STAT, "natural_rs", armor.total_rs)
            ),
            "encumbrance": armor.encumbrance,
            "encumbrance_note": self._join_effect_notes(TargetDomain.DERIVED_STAT, "encumbrance"),
            "encumbrance_variants": self._conditional_value_variants(TargetDomain.DERIVED_STAT, "encumbrance", armor.encumbrance),
            "current_damage": int(getattr(self.instance, "current_damage", 0) or 0),
            "wounds": wound_rows,
            "wound_max": wound_rows[-1]["threshold"] if wound_rows else 0,
            "wound_zone": wound_zone,
            "wound_penalty": wound_zone["penalty"],
            "movement": movement,
            "movement_display": self.movement_display(),
            "movement_display_text": self.movement_display_text(),
            "movement_tooltip_text": self.movement_tooltip_text(),
            "movement_notes": movement_notes,
            "movement_mana_cost": (
                None
                if self.creature.movement_mana_cost is None and not self._instance_numeric_adjustment("movement_mana_cost_override")
                else max(0, int(self.creature.movement_mana_cost or 0) + int(self._instance_numeric_adjustment("movement_mana_cost_override")))
            ),
            "movement_note": self._value("movement_note", ""),
            "has_ground_movement": has_ground,
            "has_single_swim": has_single_swim,
            "has_swim": has_swim,
            "has_flight": has_flight,
            "attributes": self.attribute_rows(),
            "attacks": self.attacks(),
            "skills": self.skills(),
            "special_skills": self.special_skills(),
            "commands": self.commands(),
            "traits": self.traits(),
            "effect_conditions": self.effect_condition_summary(),
            "climate_and_occurrence": self.creature.climate_and_occurrence,
            "organization": self.instance.trigger_label if self.instance and self.instance.trigger_label else self.creature.organization,
        }

    def attribute_rows(self) -> list[dict[str, Any]]:
        labels = (
            (ATTR_ST, "ST"),
            (ATTR_KON, "KON"),
            (ATTR_GE, "GE"),
            (ATTR_INT, "INT"),
            (ATTR_WA, "WA"),
            (ATTR_WILL, "WILL"),
            (ATTR_CHA, "CHA"),
        )
        rows = []
        for code, label in labels:
            value = self.attribute_mod(code)
            rows.append(
                {
                    "label": label,
                    "value": value,
                    "display": "-" if value is None else self._format_variant_value(value, signed=True),
                    "display_parts": self._value_display_parts(TargetDomain.ATTRIBUTE, code, value, signed=True),
                    "effect_note": self._join_effect_notes(TargetDomain.ATTRIBUTE, code),
                }
            )
        return rows

    @staticmethod
    def _serialize_command_prerequisites(command) -> list[list[dict[str, Any]]]:
        return [
            [{"name": prerequisite.name, "slug": prerequisite.slug} for prerequisite in group]
            for group in command.prerequisite_groups
        ]

    @staticmethod
    def _format_damage(attack) -> str:
        flat_bonus = int(attack.damage_flat_bonus or 0)
        flat_operator = str(getattr(attack, "damage_flat_operator", "") or "")
        damage_type = f" {attack.damage_type}" if attack.damage_type else ""
        if not attack.damage_dice_amount or not attack.damage_dice_faces:
            if flat_bonus:
                return f"{abs(flat_bonus)}{damage_type}"
            return damage_type.strip()
        bonus = ""
        if flat_bonus:
            if flat_operator == CreatureAttack.DamageOperator.DIVIDE:
                bonus = f"/{abs(flat_bonus)}"
            elif flat_operator == CreatureAttack.DamageOperator.SUBTRACT:
                bonus = f"-{abs(flat_bonus)}"
            elif flat_operator == CreatureAttack.DamageOperator.ADD:
                bonus = f"+{abs(flat_bonus)}"
            else:
                bonus = f"{flat_bonus:+d}"
        return f"{attack.damage_dice_amount}w{attack.damage_dice_faces}{bonus}{damage_type}"

    @staticmethod
    def _apply_damage_bonus(damage: str, bonus: int | float) -> str:
        if not damage or not bonus:
            return damage
        match = re.match(r"^(?P<head>\s*\d+w\d+)(?P<flat>[+-]\d+)?(?P<tail>.*)$", str(damage))
        if not match:
            return damage
        flat = int(match.group("flat") or 0) + bonus
        flat = CreatureEngine._normalize_numeric_display_value(flat)
        flat_display = CreatureEngine._format_variant_value(flat, signed=True) if flat else ""
        return f"{match.group('head')}{flat_display}{match.group('tail')}"

    @staticmethod
    def _compact_number(value: Any) -> str | None:
        if value is None or value == "":
            return None
        try:
            number = float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return str(value)
        if number.is_integer():
            return str(int(number))
        fraction = Fraction(number).limit_denominator(16)
        whole, remainder = divmod(fraction.numerator, fraction.denominator)
        unicode_fraction = {
            (1, 2): "\u00bd",
            (1, 3): "\u2153",
            (2, 3): "\u2154",
            (1, 4): "\u00bc",
            (3, 4): "\u00be",
            (1, 5): "\u2155",
            (2, 5): "\u2156",
            (3, 5): "\u2157",
            (4, 5): "\u2158",
            (1, 6): "\u2159",
            (5, 6): "\u215a",
            (1, 7): "\u2150",
            (1, 8): "\u215b",
            (3, 8): "\u215c",
            (5, 8): "\u215d",
            (7, 8): "\u215e",
            (1, 9): "\u2151",
            (1, 10): "\u2152",
        }.get((remainder, fraction.denominator))
        if unicode_fraction:
            return f"{whole}{unicode_fraction}" if whole else unicode_fraction
        if whole:
            return f"{whole} {remainder}/{fraction.denominator}"
        return f"{remainder}/{fraction.denominator}"

    def _wound_penalty_for_label(self, label: str) -> int:
        penalty = self._base_wound_penalty_for_label(label)
        if penalty >= 0:
            return penalty
        return min(0, penalty + self.wound_penalty_reduction())

    @staticmethod
    def _base_wound_penalty_for_label(label: str) -> int:
        if label in {"-2", "-4", "-6"}:
            return int(label)
        return 0


def creature_kind_label(quality: Any) -> str:
    """Return the creature-card rank label for one quality tier."""
    return CREATURE_KIND_LABELS.get(ItemEngine.normalize_quality(quality), "Kreatur")


def _creature_card_snapshot_values(creature: Creature, *, quality: Any | None = None) -> dict[str, Any]:
    engine = CreatureEngine(creature)
    armor = engine.armor_totals()
    movement = engine.movement()
    return {
        "name": creature.display_name,
        "creature_type": "",
        "image": creature.image,
        "description": creature.description,
        "source_reference": creature.climate_and_occurrence,
        "quality": quality if quality is not None else creature.quality,
        "initiative": engine.initiative(),
        "vw": engine.vw(),
        "sr": engine.sr(),
        "gw": engine.gw(),
        "defense_extra_label": engine.defense_extra_label(),
        "fear_resistance_bonus": engine.defense_extra_value(),
        "rs": armor.natural_rs,
        "wound_step": engine.wound_step(),
        "size_class": engine.size_class(),
        "size_modifier": engine.size_modifier(),
        "combat_speed": movement["combat"],
        "march_speed": movement["march"],
        "sprint_speed": movement["sprint"],
        "swimming_speed": movement["swim"],
        "combat_swimming_speed": movement["swim_combat"],
        "march_swimming_speed": movement["swim_march"],
        "sprint_swimming_speed": movement["swim_sprint"],
        "combat_fly_speed": movement["fly_combat"],
        "march_fly_speed": movement["fly_march"],
        "sprint_fly_speed": movement["fly_sprint"],
        "movement_mana_cost": creature.movement_mana_cost,
        "movement_note": creature.movement_note,
        "strength_mod": engine.attribute_mod(ATTR_ST),
        "constitution_mod": engine.attribute_mod(ATTR_KON),
        "dexterity_mod": engine.attribute_mod(ATTR_GE),
        "intelligence_mod": engine.attribute_mod(ATTR_INT),
        "perception_mod": engine.attribute_mod(ATTR_WA),
        "willpower_mod": engine.attribute_mod(ATTR_WILL),
        "charisma_mod": engine.attribute_mod(ATTR_CHA),
    }


def sync_character_creatures(character) -> list[CharacterCreature]:
    """Create/reactivate/deactivate concrete creature instances for one character."""

    character_items = list(
        CharacterItem.objects.filter(owner=character, amount__gt=0, stored=False)
        .select_related("item", "quality")
        .order_by("id")
    )
    items_by_item_id = {}
    for character_item in character_items:
        items_by_item_id.setdefault(character_item.item_id, []).append(character_item)

    character_techniques = list(
        CharacterTechnique.objects.filter(character=character)
        .select_related("technique")
        .order_by("id")
    )
    techniques_by_technique_id = {
        character_technique.technique_id: character_technique
        for character_technique in character_techniques
    }
    bindings = list(
        CreatureSourceBinding.objects.filter(active=True, creature__isnull=False)
        .select_related("creature", "creature__quality", "quality", "item_trigger", "technique_trigger")
        .prefetch_related(
            "creature__attacks",
            "creature__skills__skill",
            "creature__traits__trait",
            "creature__commands__command",
            "creature__commands__command__prerequisite_links__prerequisite",
        )
    )
    active_creature_ids = set()
    for binding in bindings:
        source_rows = []
        if binding.trigger_type == CreatureSourceBinding.TriggerType.ITEM:
            source_rows = [
                {
                    "source_character_item": character_item,
                    "source_character_technique": None,
                    "quality": character_item.quality,
                }
                for character_item in items_by_item_id.get(binding.item_trigger_id, [])
            ]
        elif binding.trigger_type == CreatureSourceBinding.TriggerType.TECHNIQUE:
            character_technique = techniques_by_technique_id.get(binding.technique_trigger_id)
            if character_technique is not None:
                source_rows = [
                    {
                        "source_character_item": None,
                        "source_character_technique": character_technique,
                        "quality": binding.quality,
                    }
                ]
        if not source_rows:
            continue
        for source in source_rows:
            budgets = CharacterCreature.training_budget_defaults(source["quality"])
            instance, created = CharacterCreature.objects.get_or_create(
                owner=character,
                source_binding=binding,
                source_character_item=source["source_character_item"],
                source_character_technique=source["source_character_technique"],
                defaults={
                    "creature": binding.creature,
                    "quality": source["quality"],
                    "active": True,
                    **budgets,
                },
            )
            active_creature_ids.add(instance.pk)
            update_fields = []
            if not instance.active:
                instance.active = True
                update_fields.append("active")
            if instance.creature_id != binding.creature_id:
                instance.creature = binding.creature
                update_fields.append("creature")
            if update_fields:
                instance.save(update_fields=sorted(set(update_fields)))

    existing_creatures = CharacterCreature.objects.filter(owner=character, source_binding__isnull=False)
    existing_creatures.exclude(pk__in=active_creature_ids).filter(active=True).update(active=False)
    return list(
        existing_creatures.filter(active=True)
        .select_related(
            "creature",
            "quality",
            "source_binding",
            "source_binding__quality",
            "source_binding__item_trigger",
            "source_binding__technique_trigger",
            "source_character_item",
            "source_character_item__quality",
            "source_character_technique",
        )
        .prefetch_related(
            "creature__attacks",
            "skill_overrides__skill",
            "special_skill_overrides__skill",
            "trait_overrides__trait",
            "commands__command",
            "commands__prerequisite_links__prerequisite",
            "attribute_increases",
        )
        .order_by("name_override", "creature__name", "id")
    )
