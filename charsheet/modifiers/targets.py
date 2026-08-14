"""Central target normalization and matching for semantic effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from charsheet.constants import ATTRIBUTE_CODE_CHOICES, VALID_STAT_SLUGS
from charsheet.modifiers.definitions import TargetDomain


ATTRIBUTE_KEYS = {value for value, _label in ATTRIBUTE_CODE_CHOICES}
DAMAGE_TARGET_PREFIX = "dmg_"
DAMAGE_TARGET_KEYS = {
    "weapon_damage",
    "weapon_damage_dice",
    "weapon_maneuver_damage",
    "unarmed_damage",
}
RULE_FLAG_KEYS = {
    "wound_penalty_ignore",
    "can_act_while_out_of_action",
    "armor_penalty_ignore",
    "shield_penalty_ignore",
    "coma_ignore",
    "vampire_strength_over_race_maximum",
    "vampire_power_manual_activation",
    "vampire_power_blood_theft",
    "vampire_power_blood_sacrament",
    "vampire_power_attribute_boost",
    "vampire_regeneration",
}
DERIVED_STAT_KEYS = VALID_STAT_SLUGS - RULE_FLAG_KEYS


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    """A canonical semantic target plus optional applicability metadata."""

    domain: str
    key: str
    context_requirements: dict[str, tuple[str, ...]] = field(default_factory=dict)


class TargetResolver:
    """Normalize rule targets and evaluate target-specific context gates."""

    WEAPON_TYPE = "weapon_type"
    WEAPON_SKILL = "weapon_skill"
    WEAPON_CATEGORY = "weapon_category"
    SPECIFIC_WEAPON = "weapon"
    DAMAGE_VALUE = "damage"

    @classmethod
    def resolve(cls, target_domain: str, target_key: str, metadata: dict[str, Any] | None = None) -> ResolvedTarget:
        """Return the canonical target used by the modifier engine."""
        metadata = metadata or {}
        raw_domain = str(target_domain or "").strip()
        raw_key = str(target_key or "").strip()

        if raw_domain == cls.DAMAGE_VALUE or cls.is_damage_key(raw_key):
            return ResolvedTarget(TargetDomain.COMBAT, raw_key)
        if raw_domain == "stat":
            if raw_key in RULE_FLAG_KEYS:
                return ResolvedTarget(TargetDomain.RULE_FLAG, raw_key)
            if raw_key in ATTRIBUTE_KEYS:
                return ResolvedTarget(TargetDomain.ATTRIBUTE, raw_key)
            if cls.is_damage_key(raw_key):
                return ResolvedTarget(TargetDomain.COMBAT, raw_key)
            return ResolvedTarget(TargetDomain.DERIVED_STAT, raw_key)
        if raw_domain == cls.WEAPON_TYPE:
            weapon_types = cls._tuple_values(metadata.get("target_weapon_type")) or (raw_key,)
            return ResolvedTarget(
                TargetDomain.COMBAT,
                raw_key,
                {"weapon_types": weapon_types},
            )
        if raw_domain == cls.WEAPON_SKILL:
            weapon_skills = cls._tuple_values(metadata.get("target_weapon_skill")) or (raw_key,)
            return ResolvedTarget(
                TargetDomain.COMBAT,
                raw_key,
                {"weapon_skill_slugs": weapon_skills},
            )
        if raw_domain == cls.WEAPON_CATEGORY:
            return ResolvedTarget(
                TargetDomain.COMBAT,
                raw_key,
                {"weapon_categories": (raw_key,)},
            )
        if raw_domain == cls.SPECIFIC_WEAPON:
            return ResolvedTarget(
                TargetDomain.COMBAT,
                raw_key,
                {"weapon_ids": (raw_key,)},
            )

        context_requirements = cls._metadata_context_requirements(metadata)
        return ResolvedTarget(raw_domain, raw_key, context_requirements)

    @classmethod
    def is_damage_key(cls, key: str) -> bool:
        """Return whether a target key addresses a damage value."""
        normalized = str(key or "")
        return normalized in DAMAGE_TARGET_KEYS or normalized.startswith(DAMAGE_TARGET_PREFIX)

    @classmethod
    def matches_context(cls, modifier, context: dict[str, Any] | None = None) -> bool:
        """Return whether target metadata requirements match the evaluation context."""
        requirements = cls._metadata_context_requirements(getattr(modifier, "metadata", {}) or {})
        if not requirements:
            return True
        context = context or {}
        for context_key, expected_values in requirements.items():
            actual_values = cls._context_values(context.get(context_key))
            if not actual_values.intersection(expected_values):
                return False
        return True

    @classmethod
    def _metadata_context_requirements(cls, metadata: dict[str, Any]) -> dict[str, tuple[str, ...]]:
        requirements: dict[str, tuple[str, ...]] = {}
        mapping = {
            "target_weapon_type": "weapon_types",
            "target_weapon_skill": "weapon_skill_slugs",
            "target_weapon_category": "weapon_categories",
            "target_weapon_id": "weapon_ids",
        }
        for metadata_key, context_key in mapping.items():
            values = cls._tuple_values(metadata.get(metadata_key))
            if values:
                requirements[context_key] = values
        return requirements

    @staticmethod
    def _tuple_values(value: Any) -> tuple[str, ...]:
        if value in (None, ""):
            return ()
        if isinstance(value, (list, tuple, set)):
            return tuple(str(entry) for entry in value if entry not in (None, ""))
        return (str(value),)

    @staticmethod
    def _context_values(value: Any) -> set[str]:
        if value in (None, ""):
            return set()
        if isinstance(value, (list, tuple, set)):
            return {str(entry) for entry in value if entry not in (None, "")}
        return {str(value)}
