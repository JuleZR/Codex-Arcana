"""Calculation helpers for creature templates and character-owned creatures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property
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
from charsheet.modifiers.definitions import BaseModifier, TargetDomain
from charsheet.modifiers.engine import ModifierEngine
from charsheet.modifiers.registry import build_creature_trait_semantic_modifiers
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

    @cached_property
    def _effective_trait_rows(self) -> list[Any]:
        """Return base traits plus active instance traits, replacing linked base rows."""
        skipped_base_trait_ids = set()
        override_rows = []
        if self.instance:
            override_rows = list(
                self.instance.trait_overrides.select_related("base_trait", "trait").prefetch_related("choices")
            )
            skipped_base_trait_ids = {
                row.base_trait_id
                for row in override_rows
                if row.active and row.base_trait_id is not None
            }
        base_rows = [
            row
            for row in self.creature.traits.select_related("trait").prefetch_related("choices")
            if row.id not in skipped_base_trait_ids
        ]
        return base_rows + [row for row in override_rows if row.active]

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
    def _semantic_modifiers(self) -> list[BaseModifier]:
        modifiers: list[BaseModifier] = []
        for row in self._effective_trait_rows:
            modifiers.extend(
                build_creature_trait_semantic_modifiers(
                    trait_slug=row.trait.slug,
                    level=int(row.trait_level or 0),
                    trait=row.trait,
                )
            )
        return self._expand_choice_bound_modifiers(modifiers)

    @cached_property
    def modifier_engine(self) -> ModifierEngine:
        return ModifierEngine(
            modifiers=self._semantic_modifiers,
            trait_levels_by_slug=self._trait_levels_by_slug,
        )

    def _expand_choice_bound_modifiers(self, modifiers: list[BaseModifier]) -> list[BaseModifier]:
        expanded: list[BaseModifier] = []
        for modifier in modifiers:
            choice_binding = (modifier.metadata or {}).get("choice_binding") or {}
            if choice_binding.get("kind") != "creature_trait_choice_definition":
                expanded.append(modifier)
                continue
            bound_targets = self._choice_targets_by_definition_id.get(int(choice_binding.get("id") or 0), [])
            if not bound_targets:
                expanded.append(modifier)
                continue
            for target_domain, target_key in bound_targets:
                if target_domain != modifier.target_domain and target_domain != "metadata":
                    continue
                expanded.append(replace(modifier, target_domain=target_domain, target_key=target_key))
        return expanded

    def _modifier_total(self, target_domain: str, target_key: str) -> int:
        return int(self.modifier_engine.resolve_numeric_total(target_domain, target_key) or 0)

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
        override = self._stat_override("initiative_override")
        if override is not None:
            return int(override) + self._modifier_total(TargetDomain.DERIVED_STAT, "initiative")
        return (
            int(self.attribute_mod(ATTR_WA) or 0)
            + self.size_modifier()
            + self._modifier_total(TargetDomain.DERIVED_STAT, "initiative")
        )

    def vw(self) -> int:
        override = self._stat_override("vw_override")
        if override is not None:
            return int(override) + self._modifier_total(TargetDomain.DERIVED_STAT, "vw")
        return (
            14
            + int(self.attribute_mod(ATTR_GE) or 0)
            + int(self.attribute_mod(ATTR_WA) or 0)
            + self.size_modifier()
            + self._modifier_total(TargetDomain.DERIVED_STAT, "vw")
        )

    def sr(self) -> int:
        override = self._stat_override("sr_override")
        if override is not None:
            return int(override) + self._modifier_total(TargetDomain.DERIVED_STAT, "sr")
        return (
            14
            + int(self.attribute_mod(ATTR_ST) or 0)
            + int(self.attribute_mod(ATTR_KON) or 0)
            + self._modifier_total(TargetDomain.DERIVED_STAT, "sr")
        )

    def gw(self) -> int:
        override = self._stat_override("gw_override")
        if override is not None:
            return int(override) + self._modifier_total(TargetDomain.DERIVED_STAT, "gw")
        return (
            14
            + int(self.attribute_mod(ATTR_INT) or 0)
            + int(self.attribute_mod(ATTR_WILL) or 0)
            + self._modifier_total(TargetDomain.DERIVED_STAT, "gw")
        )

    def fear_resistance_bonus(self) -> int:
        return int(self._value("fear_resistance_bonus", 0) or 0)

    def defense_extra_label(self) -> str:
        return str(self._value("defense_extra_label", "") or "").strip()

    def defense_extra_value(self) -> int | None:
        value = self._value("fear_resistance_bonus", None)
        if value is None or value == "":
            return None
        return int(value)

    def gw_against_fear(self) -> int:
        return int(self.defense_extra_value() or 0)

    def wound_step(self) -> int:
        override = self._value("wound_step_override", None)
        if override is not None:
            return int(override) + self._modifier_total(TargetDomain.DERIVED_STAT, "wound_step")
        return 5 + int(self.attribute_mod(ATTR_KON) or 0) + self._modifier_total(TargetDomain.DERIVED_STAT, "wound_step")

    def wound_rows(self) -> list[dict[str, Any]]:
        step = max(1, self.wound_step())
        return [
            {"label": label, "threshold": step * index}
            for index, label in enumerate(WOUND_STAGE_LABELS, start=1)
        ]

    def current_wound_zone(self) -> dict[str, Any]:
        damage = int(getattr(self.instance, "current_damage", 0) or 0)
        rows = self.wound_rows()
        current = {"label": "-", "threshold": 0, "penalty": 0}
        for row in rows:
            if damage >= int(row["threshold"]):
                current = {
                    "label": row["label"],
                    "threshold": row["threshold"],
                    "penalty": self._wound_penalty_for_label(row["label"]),
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
        value = self._value(field_name, default)
        bonus = self._modifier_total(TargetDomain.MOVEMENT, target_key)
        if value is None:
            return None if not bonus else bonus
        return value + bonus

    def movement_display(self) -> dict[str, str | None]:
        movement = self.movement()
        return {key: self._compact_number(value) for key, value in movement.items()}

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
            int(self._value("natural_rs", 0) or 0)
            + self._modifier_total(TargetDomain.DERIVED_STAT, DEFENSE_RS)
            + self._modifier_total(TargetDomain.DERIVED_STAT, "natural_rs")
        )
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
        attack_value_bonus = int(self.attribute_increase_totals.get(ATTR_GE, 0) or 0) + self._modifier_total(TargetDomain.COMBAT, "attack_value")
        damage_bonus = int(self.attribute_increase_totals.get(ATTR_ST, 0) or 0)
        return [
            self._attack_context(attack, attack_value_bonus, damage_bonus)
            for attack in self.creature.attacks.all()
        ]

    def _attack_context(self, attack, attack_value_bonus: int, damage_bonus: int) -> dict[str, Any]:
        damage = self._apply_damage_bonus(self._format_damage(attack), damage_bonus)
        notes = str(attack.notes or "")
        show_notes_as_damage = bool(getattr(attack, "show_notes_as_damage", False) and notes)
        append_notes_to_damage = bool(getattr(attack, "append_notes_to_damage", False) and notes and not show_notes_as_damage)
        damage_display = damage
        if show_notes_as_damage:
            damage_display = notes
        elif append_notes_to_damage:
            damage_display = f"{damage} {notes}".strip()
        return {
            "name": attack.name,
            "attack_value": attack.attack_value + attack_value_bonus,
            "damage": damage,
            "damage_display": damage_display,
            "notes": "" if show_notes_as_damage or append_notes_to_damage else notes,
            "show_notes_as_damage": show_notes_as_damage,
            "append_notes_to_damage": append_notes_to_damage,
        }

    def skills(self) -> list[dict[str, Any]]:
        overrides = {}
        if self.instance:
            overrides = {
                entry.skill_id: entry
                for entry in self.instance.skill_overrides.select_related("skill")
            }
        base_rows = []
        seen = set()
        for row in self.creature.skills.select_related("skill"):
            override = overrides.get(row.skill_id)
            seen.add(row.skill_id)
            base_rows.append(
                {
                    "name": row.skill.name,
                    "value": (override.value_override if override else row.value)
                    + self._modifier_total(TargetDomain.SKILL, row.skill.slug),
                    "notes": override.notes if override and override.notes else row.notes or row.skill.description,
                }
            )
        for skill_id, override in overrides.items():
            if skill_id not in seen:
                base_rows.append(
                    {
                        "name": override.skill.name,
                        "value": override.value_override + self._modifier_total(TargetDomain.SKILL, override.skill.slug),
                        "notes": override.notes or override.skill.description,
                    }
                )
        return base_rows

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
            rows.append(
                {
                    "name": row.skill.name,
                    "value": override.value_override if override else row.value,
                    "notes": override.notes if override and override.notes else row.notes or row.skill.description,
                    "kind": "creature",
                }
            )
        for skill_id, override in overrides.items():
            if skill_id not in seen:
                rows.append(
                    {
                        "name": override.skill.name,
                        "value": override.value_override,
                        "notes": override.notes,
                        "kind": "creature",
                    }
                )
        return rows

    def traits(self) -> list[dict[str, Any]]:
        rows = [
            {
                "name": trait.display_name,
                "level": trait.level,
                "description": trait.description,
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
            "vw": self.vw(),
            "sr": self.sr(),
            "gw": self.gw(),
            "gw_extra": defense_extra_value if defense_extra_value else None,
            "gw_extra_label": defense_extra_label,
            "gw_fear": self.gw_against_fear() if defense_extra_value else None,
            "fear_bonus": defense_extra_value,
            "rs_natural": armor.natural_rs,
            "rs_armor": armor.armor_rs,
            "rs_total": armor.total_rs,
            "encumbrance": armor.encumbrance,
            "current_damage": int(getattr(self.instance, "current_damage", 0) or 0),
            "wounds": wound_rows,
            "wound_max": wound_rows[-1]["threshold"] if wound_rows else 0,
            "wound_zone": wound_zone,
            "wound_penalty": wound_zone["penalty"],
            "movement": movement,
            "movement_display": self.movement_display(),
            "movement_mana_cost": self.creature.movement_mana_cost,
            "movement_note": self.creature.movement_note,
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
                    "display": "-" if value is None else f"{int(value):+d}",
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
    def _apply_damage_bonus(damage: str, bonus: int) -> str:
        if not damage or not bonus:
            return damage
        match = re.match(r"^(?P<head>\s*\d+w\d+)(?P<flat>[+-]\d+)?(?P<tail>.*)$", str(damage))
        if not match:
            return damage
        flat = int(match.group("flat") or 0) + bonus
        flat_display = f"{flat:+d}" if flat else ""
        return f"{match.group('head')}{flat_display}{match.group('tail')}"

    @staticmethod
    def _compact_number(value: Any) -> str | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if number.is_integer():
            return str(int(number))
        fraction = Fraction(number).limit_denominator(16)
        whole, remainder = divmod(fraction.numerator, fraction.denominator)
        if whole:
            return f"{whole} {remainder}/{fraction.denominator}"
        return f"{remainder}/{fraction.denominator}"

    @staticmethod
    def _wound_penalty_for_label(label: str) -> int:
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
