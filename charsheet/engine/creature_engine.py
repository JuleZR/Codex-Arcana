"""Calculation helpers for creature templates and character-owned creatures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from charsheet.constants import (
    ATTR_CHA,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    GK_MODS,
    QUALITY_BEL_MODS,
)
from charsheet.models.creatures import ATTRIBUTE_FIELD_MAP, CharacterCreature, CharacterCreatureItem, Creature


WOUND_STAGE_LABELS = ("0", "-2", "-4", "-6", "Ausser Gefecht", "Koma")


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
        override = self._override("size_modifier")
        if override is not None:
            return int(override)
        explicit = int(getattr(self.creature, "size_modifier", 0) or 0)
        if explicit:
            return explicit
        return int(GK_MODS.get(self.size_class(), 0))

    def attribute_mod(self, attribute: str) -> int | None:
        field_name = ATTRIBUTE_FIELD_MAP.get(attribute)
        if not field_name:
            return 0
        value = self._value(field_name, None)
        if value is None and attribute == ATTR_CHA:
            return None
        return int(value or 0)

    def initiative(self) -> int:
        override = self._stat_override("initiative_override")
        if override is not None:
            return int(override)
        return int(self.attribute_mod(ATTR_WA) or 0)

    def vw(self) -> int:
        override = self._stat_override("vw_override")
        if override is not None:
            return int(override)
        return 14 + int(self.attribute_mod(ATTR_GE) or 0) + int(self.attribute_mod(ATTR_WA) or 0) + self.size_modifier()

    def sr(self) -> int:
        override = self._stat_override("sr_override")
        if override is not None:
            return int(override)
        return 14 + int(self.attribute_mod(ATTR_ST) or 0) + int(self.attribute_mod(ATTR_KON) or 0)

    def gw(self) -> int:
        override = self._stat_override("gw_override")
        if override is not None:
            return int(override)
        return 14 + int(self.attribute_mod(ATTR_INT) or 0) + int(self.attribute_mod(ATTR_WILL) or 0)

    def fear_resistance_bonus(self) -> int:
        return int(self._value("fear_resistance_bonus", 0) or 0)

    def gw_against_fear(self) -> int:
        return self.gw() + self.fear_resistance_bonus()

    def wound_step(self) -> int:
        override = self._value("wound_step_override", None)
        if override is not None:
            return int(override)
        return 5 + int(self.attribute_mod(ATTR_KON) or 0)

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
            "combat": self._value("combat_speed", 0),
            "march": self._value("march_speed", 0),
            "sprint": self._value("sprint_speed", 0),
            "swim": self._value("swimming_speed", 0),
            "fly_combat": self._value("combat_fly_speed", None),
            "fly_march": self._value("march_fly_speed", None),
            "fly_sprint": self._value("sprint_fly_speed", None),
        }

    def movement_display(self) -> dict[str, str | None]:
        movement = self.movement()
        return {key: self._compact_number(value) for key, value in movement.items()}

    def equipped_items(self):
        if self.instance is None:
            return CharacterCreatureItem.objects.none()
        return (
            self.instance.items.filter(equipped=True)
            .select_related("item", "item__armorstats")
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
        encumbrance += QUALITY_BEL_MODS.get(creature_item.quality, 0)
        return max(0, int(encumbrance))

    def armor_totals(self) -> CreatureArmorTotals:
        natural_rs = int(self._value("natural_rs", 0) or 0)
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
        return [
            {
                "name": attack.name,
                "attack_value": attack.attack_value,
                "damage": self._format_damage(attack),
                "notes": attack.notes,
            }
            for attack in self.creature.attacks.all()
        ]

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
                    "value": override.value_override if override else row.value,
                    "notes": override.notes if override and override.notes else row.notes,
                }
            )
        for skill_id, override in overrides.items():
            if skill_id not in seen:
                base_rows.append(
                    {"name": override.skill.name, "value": override.value_override, "notes": override.notes}
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
                    "notes": override.notes if override and override.notes else row.notes,
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
            for trait in self.creature.traits.select_related("trait")
        ]
        if self.instance:
            for override in self.instance.trait_overrides.select_related("base_trait", "trait"):
                if not override.active:
                    continue
                rows.append(
                    {
                        "name": override.display_name,
                        "level": override.level_override,
                        "description": override.description_override,
                    }
                )
        return rows

    def card_context(self) -> dict[str, Any]:
        armor = self.armor_totals()
        fear_bonus = self.fear_resistance_bonus()
        wound_rows = self.wound_rows()
        wound_zone = self.current_wound_zone()
        return {
            "name": self.display_name(),
            "creature_name": self.creature.display_name,
            "image": self.image(),
            "size_class": self.size_class(),
            "size_modifier": self.size_modifier(),
            "initiative": self.initiative(),
            "vw": self.vw(),
            "sr": self.sr(),
            "gw": self.gw(),
            "gw_fear": self.gw_against_fear() if fear_bonus else None,
            "fear_bonus": fear_bonus,
            "rs_natural": armor.natural_rs,
            "rs_armor": armor.armor_rs,
            "rs_total": armor.total_rs,
            "encumbrance": armor.encumbrance,
            "current_damage": int(getattr(self.instance, "current_damage", 0) or 0),
            "wounds": wound_rows,
            "wound_max": wound_rows[-1]["threshold"] if wound_rows else 0,
            "wound_zone": wound_zone,
            "wound_penalty": wound_zone["penalty"],
            "movement": self.movement(),
            "movement_display": self.movement_display(),
            "attributes": self.attribute_rows(),
            "attacks": self.attacks(),
            "skills": self.skills(),
            "special_skills": self.special_skills(),
            "traits": self.traits(),
            "climate_and_occurrence": self.creature.climate_and_occurrence,
            "organization": self.creature.organization,
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
    def _format_damage(attack) -> str:
        if not attack.damage_dice_amount or not attack.damage_dice_faces:
            return ""
        bonus = ""
        if attack.damage_flat_bonus > 0:
            bonus = f"+{attack.damage_flat_bonus}"
        elif attack.damage_flat_bonus < 0:
            bonus = str(attack.damage_flat_bonus)
        damage_type = f" {attack.damage_type}" if attack.damage_type else ""
        return f"{attack.damage_dice_amount}w{attack.damage_dice_faces}{bonus}{damage_type}"

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
        return f"{number:g}"

    @staticmethod
    def _wound_penalty_for_label(label: str) -> int:
        if label in {"-2", "-4", "-6"}:
            return int(label)
        return 0
