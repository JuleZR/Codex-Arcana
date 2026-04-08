"""Typed modifier domain objects used by the new central modifier engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StringEnum(str, Enum):
    """Python < 3.11 compatible string enum base."""


class ModifierOperator(StringEnum):
    """Semantic operation applied by one modifier."""

    FLAT_ADD = "flat_add"
    FLAT_SUB = "flat_sub"
    MULTIPLY = "multiply"
    OVERRIDE = "override"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    SET_FLAG = "set_flag"
    UNSET_FLAG = "unset_flag"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    GRANT_CAPABILITY = "grant_capability"
    REMOVE_CAPABILITY = "remove_capability"
    GRANT_IMMUNITY = "grant_immunity"
    GRANT_VULNERABILITY = "grant_vulnerability"
    CHANGE_RESOURCE_CAP = "change_resource_cap"
    CHANGE_STARTING_FUNDS = "change_starting_funds"
    CHANGE_APPEARANCE_CLASS = "change_appearance_class"
    CHANGE_SOCIAL_STATUS = "change_social_status"
    REROLL_GRANT = "reroll_grant"
    REROLL_FORBID = "reroll_forbid"
    REPEAT_ACTION_ALLOWED = "repeat_action_allowed"
    ACTION_COST_CHANGE = "action_cost_change"
    CONDITIONAL_BONUS = "conditional_bonus"
    CONDITIONAL_PENALTY = "conditional_penalty"


class TargetDomain(StringEnum):
    """High-level rule domains addressable by modifiers."""

    SKILL = "skill"
    SKILL_CATEGORY = "skill_category"
    LANGUAGE = "language"
    PROFICIENCY_GROUP = "proficiency_group"
    TRAIT = "trait"
    ATTRIBUTE = "attribute"
    ATTRIBUTE_CAP = "attribute_cap"
    DERIVED_STAT = "derived_stat"
    RESOURCE = "resource"
    RESISTANCE = "resistance"
    MOVEMENT = "movement"
    COMBAT = "combat"
    PERCEPTION = "perception"
    ECONOMY = "economy"
    SOCIAL = "social"
    RULE_FLAG = "rule_flag"
    CAPABILITY = "capability"
    BEHAVIOR = "behavior"
    TAG = "tag"
    METADATA = "metadata"
    ITEM = "item"
    ITEM_CATEGORY = "item_category"
    SPECIALIZATION = "specialization"
    ENTITY = "entity"


class StackBehavior(StringEnum):
    """How multiple modifiers on the same target should combine."""

    STACK = "stack"
    HIGHEST = "highest"
    LOWEST = "lowest"
    OVERRIDE = "override"
    UNIQUE_BY_SOURCE = "unique_by_source"


class ModifierVisibility(StringEnum):
    """Where a modifier should be exposed."""

    PUBLIC = "public"
    INTERNAL = "internal"
    STORY = "story"


@dataclass(slots=True)
class ConditionSet:
    """Centralized applicability rules for one modifier."""

    applies_in_combat: bool | None = None
    applies_outside_combat: bool | None = None
    applies_against_target_tag: tuple[str, ...] = ()
    applies_with_weapon_type: tuple[str, ...] = ()
    applies_with_skill: tuple[str, ...] = ()
    applies_when_wounded: bool | None = None
    applies_when_unarmored: bool | None = None
    applies_in_darkness: bool | None = None
    applies_in_low_light: bool | None = None
    applies_in_heat: bool | None = None
    applies_in_cold: bool | None = None
    applies_against_magic: bool | None = None
    applies_against_school: tuple[str, ...] = ()
    applies_while_moving: bool | None = None
    applies_while_sprinting: bool | None = None
    applies_to_social_interactions: bool | None = None
    applies_during_character_creation: bool | None = None
    applies_if_flag_present: tuple[str, ...] = ()
    applies_if_flag_absent: tuple[str, ...] = ()

    def matches(self, context: dict[str, Any] | None = None) -> bool:
        """Return whether the condition set matches a context payload."""
        context = context or {}
        boolean_checks = {
            "in_combat": self.applies_in_combat,
            "outside_combat": self.applies_outside_combat,
            "wounded": self.applies_when_wounded,
            "unarmored": self.applies_when_unarmored,
            "in_darkness": self.applies_in_darkness,
            "in_low_light": self.applies_in_low_light,
            "in_heat": self.applies_in_heat,
            "in_cold": self.applies_in_cold,
            "against_magic": self.applies_against_magic,
            "while_moving": self.applies_while_moving,
            "while_sprinting": self.applies_while_sprinting,
            "social_interaction": self.applies_to_social_interactions,
            "during_character_creation": self.applies_during_character_creation,
        }
        for key, expected in boolean_checks.items():
            if expected is not None and bool(context.get(key, False)) != expected:
                return False

        tuple_checks = {
            "target_tags": self.applies_against_target_tag,
            "weapon_types": self.applies_with_weapon_type,
            "skill_slugs": self.applies_with_skill,
            "school_slugs": self.applies_against_school,
        }
        for key, expected_values in tuple_checks.items():
            if not expected_values:
                continue
            actual_values = set(context.get(key, ()))
            if not actual_values.intersection(expected_values):
                return False

        active_flags = set(context.get("flags", ()))
        if self.applies_if_flag_present and not active_flags.issuperset(self.applies_if_flag_present):
            return False
        if self.applies_if_flag_absent and active_flags.intersection(self.applies_if_flag_absent):
            return False
        return True


@dataclass(slots=True)
class BaseModifier:
    """Generic modifier base carrying numeric and semantic rule concepts."""

    source_type: str
    source_id: str
    target_domain: str
    target_key: str
    mode: str = "flat"
    value: float | int | str | None = None
    value_min: float | int | None = None
    value_max: float | int | None = None
    formula: str = ""
    scaling: dict[str, Any] = field(default_factory=dict)
    operator: str = ModifierOperator.FLAT_ADD
    stack_behavior: str = StackBehavior.STACK
    condition_set: ConditionSet = field(default_factory=ConditionSet)
    active_flag: bool = True
    priority: int = 0
    notes: str = ""
    rules_text: str = ""
    visibility: str = ModifierVisibility.PUBLIC
    hidden: bool = False
    sheet_relevant: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def applies(self, context: dict[str, Any] | None = None) -> bool:
        """Return whether the modifier is active in the provided context."""
        return self.active_flag and self.condition_set.matches(context)


class SkillModifier(BaseModifier):
    """Modifier targeting one skill or skill-like resolution."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.SKILL)
        super().__init__(*args, **kwargs)


class LanguageModifier(BaseModifier):
    """Modifier targeting one language or a language-like grouping."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.LANGUAGE)
        super().__init__(*args, **kwargs)


class ProficiencyGroupModifier(BaseModifier):
    """Modifier targeting a mixed proficiency group that expands into concrete targets."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.PROFICIENCY_GROUP)
        super().__init__(*args, **kwargs)


class TraitModifier(BaseModifier):
    """Modifier targeting trait data or trait acquisition rules."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.TRAIT)
        super().__init__(*args, **kwargs)


class DerivedStatModifier(BaseModifier):
    """Modifier targeting one derived stat such as initiative or VW."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.DERIVED_STAT)
        super().__init__(*args, **kwargs)


class AttributeCapModifier(BaseModifier):
    """Modifier targeting one attribute's allowed maximum value."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.ATTRIBUTE_CAP)
        super().__init__(*args, **kwargs)


class ResourceModifier(BaseModifier):
    """Modifier targeting mutable or capped resources."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.RESOURCE)
        super().__init__(*args, **kwargs)


class ResistanceModifier(BaseModifier):
    """Modifier targeting resistances, immunities, and vulnerabilities."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.RESISTANCE)
        super().__init__(*args, **kwargs)


class MovementModifier(BaseModifier):
    """Modifier targeting movement speeds or movement capabilities."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.MOVEMENT)
        super().__init__(*args, **kwargs)


class CombatModifier(BaseModifier):
    """Modifier targeting attacks, damage, actions, or defensive combat hooks."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.COMBAT)
        super().__init__(*args, **kwargs)


class PerceptionModifier(BaseModifier):
    """Modifier targeting senses and perception-related effects."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.PERCEPTION)
        super().__init__(*args, **kwargs)


class EconomyModifier(BaseModifier):
    """Modifier targeting money, income, and character-creation economy."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.ECONOMY)
        super().__init__(*args, **kwargs)


class SocialModifier(BaseModifier):
    """Modifier targeting social rank, legal state, and social tags."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.SOCIAL)
        super().__init__(*args, **kwargs)


class ItemModifier(BaseModifier):
    """Modifier targeting one concrete item or item-like selector."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.ITEM)
        super().__init__(*args, **kwargs)


class SpecializationModifier(BaseModifier):
    """Modifier targeting one specialization record."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.SPECIALIZATION)
        super().__init__(*args, **kwargs)


class EntityModifier(BaseModifier):
    """Modifier targeting one generic persisted entity."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.ENTITY)
        super().__init__(*args, **kwargs)


class RuleFlagModifier(BaseModifier):
    """Modifier toggling binary rule states."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("target_domain", TargetDomain.RULE_FLAG)
        super().__init__(*args, **kwargs)


class ConditionalModifier(BaseModifier):
    """Explicit modifier class for context-sensitive effects."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
