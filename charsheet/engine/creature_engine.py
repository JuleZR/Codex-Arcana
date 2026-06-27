"""Calculation helpers for creature templates and character-owned creatures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cached_property
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
from charsheet.models.creatures import ATTRIBUTE_FIELD_MAP, CharacterCreature, CharacterCreatureItem, Creature, CreatureAttack
from charsheet.models.character import CharacterItem
from charsheet.models.techniques import CharacterTechnique
from charsheet.modifiers.definitions import BaseModifier, TargetDomain
from charsheet.modifiers.engine import ModifierEngine
from charsheet.modifiers.registry import build_creature_trait_semantic_modifiers
from charsheet.models.creatures import (
    CharacterCreatureCard,
    CharacterCreatureCardAttack,
    CharacterCreatureCardCommand,
    CharacterCreatureCardCommandPrerequisite,
    CharacterCreatureCardSkill,
    CharacterCreatureCardTrait,
    CreatureCardBinding,
)
from .item_engine import ItemEngine


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
        return int(value or 0) + self._modifier_total(TargetDomain.ATTRIBUTE, attribute)

    def initiative(self) -> int:
        override = self._stat_override("initiative_override")
        if override is not None:
            return int(override) + self._modifier_total(TargetDomain.DERIVED_STAT, "initiative")
        return int(self.attribute_mod(ATTR_WA) or 0) + self._modifier_total(TargetDomain.DERIVED_STAT, "initiative")

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

    def gw_against_fear(self) -> int:
        return self.gw() + self.fear_resistance_bonus()

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
        natural_rs = int(self._value("natural_rs", 0) or 0) + self._modifier_total(TargetDomain.DERIVED_STAT, "natural_rs")
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
        attack_value_bonus = self._modifier_total(TargetDomain.COMBAT, "attack_value")
        return [
            {
                "name": attack.name,
                "attack_value": attack.attack_value + attack_value_bonus,
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
                    "value": (override.value_override if override else row.value)
                    + self._modifier_total(TargetDomain.SKILL, row.skill.slug),
                    "notes": override.notes if override and override.notes else row.notes,
                }
            )
        for skill_id, override in overrides.items():
            if skill_id not in seen:
                base_rows.append(
                    {
                        "name": override.skill.name,
                        "value": override.value_override + self._modifier_total(TargetDomain.SKILL, override.skill.slug),
                        "notes": override.notes,
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
            for trait in self._effective_trait_rows
        ]
        return rows

    def commands(self) -> list[dict[str, Any]]:
        return [
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

    def card_context(self) -> dict[str, Any]:
        armor = self.armor_totals()
        fear_bonus = self.fear_resistance_bonus()
        wound_rows = self.wound_rows()
        wound_zone = self.current_wound_zone()
        quality = self.creature.quality
        return {
            "name": self.display_name(),
            "creature_name": self.creature.display_name,
            "image": self.image(),
            "quality": ItemEngine.normalize_quality(quality),
            "quality_label": getattr(quality, "name", ItemEngine.normalize_quality(quality)),
            "quality_color": ItemEngine.quality_color(quality),
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
            "commands": self.commands(),
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
    def _serialize_command_prerequisites(command) -> list[list[dict[str, Any]]]:
        return [
            [{"name": prerequisite.name, "slug": prerequisite.slug} for prerequisite in group]
            for group in command.prerequisite_groups
        ]

    @staticmethod
    def _format_damage(attack) -> str:
        if not attack.damage_dice_amount or not attack.damage_dice_faces:
            return ""
        bonus = ""
        flat_bonus = int(attack.damage_flat_bonus or 0)
        flat_operator = str(getattr(attack, "damage_flat_operator", "") or "")
        if flat_bonus:
            if flat_operator == CreatureAttack.DamageOperator.DIVIDE:
                bonus = f"/{abs(flat_bonus)}"
            elif flat_operator == CreatureAttack.DamageOperator.SUBTRACT:
                bonus = f"-{abs(flat_bonus)}"
            elif flat_operator == CreatureAttack.DamageOperator.ADD:
                bonus = f"+{abs(flat_bonus)}"
            else:
                bonus = f"{flat_bonus:+d}"
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


class CreatureCardEngine:
    """Render concrete character creature-card snapshots."""

    def __init__(self, card: CharacterCreatureCard):
        self.card = card

    def display_name(self) -> str:
        return self.card.name

    def image(self):
        return self.card.image

    def gw_against_fear(self) -> int:
        return int(self.card.gw) + int(self.card.fear_resistance_bonus or 0)

    def wound_rows(self) -> list[dict[str, Any]]:
        step = max(1, int(self.card.wound_step or 1))
        return [
            {"label": label, "threshold": step * index}
            for index, label in enumerate(WOUND_STAGE_LABELS, start=1)
        ]

    def current_wound_zone(self) -> dict[str, Any]:
        damage = int(self.card.current_damage or 0)
        current = {"label": "-", "threshold": 0, "penalty": 0}
        for row in self.wound_rows():
            if damage >= int(row["threshold"]):
                current = {
                    "label": row["label"],
                    "threshold": row["threshold"],
                    "penalty": CreatureEngine._wound_penalty_for_label(row["label"]),
                }
            else:
                break
        return current

    def movement(self) -> dict[str, Any]:
        return {
            "combat": self.card.combat_speed,
            "march": self.card.march_speed,
            "sprint": self.card.sprint_speed,
            "swim": self.card.swimming_speed,
            "fly_combat": self.card.combat_fly_speed,
            "fly_march": self.card.march_fly_speed,
            "fly_sprint": self.card.sprint_fly_speed,
        }

    def movement_display(self) -> dict[str, str | None]:
        return {key: CreatureEngine._compact_number(value) for key, value in self.movement().items()}

    def attribute_rows(self) -> list[dict[str, Any]]:
        rows = []
        for field_name, label in (
            ("strength_mod", "ST"),
            ("constitution_mod", "KON"),
            ("dexterity_mod", "GE"),
            ("intelligence_mod", "INT"),
            ("perception_mod", "WA"),
            ("willpower_mod", "WILL"),
            ("charisma_mod", "CHA"),
        ):
            value = getattr(self.card, field_name)
            rows.append(
                {
                    "label": label,
                    "value": value,
                    "display": "-" if value is None else f"{int(value):+d}",
                }
            )
        return rows

    def attacks(self) -> list[dict[str, Any]]:
        return [
            {"name": attack.name, "attack_value": attack.attack_value, "damage": attack.damage, "notes": attack.notes}
            for attack in self.card.attacks.all()
        ]

    def skills(self) -> list[dict[str, Any]]:
        return [
            {"name": skill.name, "value": skill.value, "notes": skill.notes}
            for skill in self.card.skills.all()
        ]

    def commands(self) -> list[dict[str, Any]]:
        return [
            {
                "name": command.name,
                "slug": command.slug,
                "ep_cost": command.ep_cost,
                "difficulty": command.difficulty,
                "prerequisites": CreatureEngine._serialize_command_prerequisites(command),
                "prerequisite_display": command.prerequisite_display,
                "training_days": command.training_days,
                "description": command.description,
            }
            for command in self.card.commands.all()
        ]

    def traits(self) -> list[dict[str, Any]]:
        return [
            {"name": trait.name, "level": trait.level, "description": trait.description}
            for trait in self.card.traits.all()
        ]

    def card_context(self) -> dict[str, Any]:
        fear_bonus = int(self.card.fear_resistance_bonus or 0)
        wound_rows = self.wound_rows()
        wound_zone = self.current_wound_zone()
        quality = self.card.quality
        return {
            "id": self.card.pk,
            "name": self.display_name(),
            "creature_name": self.card.creature_type or self.card.name,
            "image": self.image(),
            "quality": ItemEngine.normalize_quality(quality),
            "quality_label": getattr(quality, "name", ItemEngine.normalize_quality(quality)),
            "quality_color": ItemEngine.quality_color(quality),
            "size_class": self.card.size_class,
            "size_modifier": self.card.size_modifier,
            "initiative": self.card.initiative,
            "vw": self.card.vw,
            "sr": self.card.sr,
            "gw": self.card.gw,
            "gw_fear": self.gw_against_fear() if fear_bonus else None,
            "fear_bonus": fear_bonus,
            "rs_natural": self.card.rs,
            "rs_armor": 0,
            "rs_total": self.card.rs,
            "encumbrance": 0,
            "current_damage": int(self.card.current_damage or 0),
            "wounds": wound_rows,
            "wound_max": wound_rows[-1]["threshold"] if wound_rows else 0,
            "wound_zone": wound_zone,
            "wound_penalty": wound_zone["penalty"],
            "movement": self.movement(),
            "movement_display": self.movement_display(),
            "attributes": self.attribute_rows(),
            "attacks": self.attacks(),
            "skills": self.skills(),
            "special_skills": [],
            "commands": self.commands(),
            "traits": self.traits(),
            "climate_and_occurrence": self.card.source_reference,
            "organization": self.card.trigger_label,
        }


def _creature_card_snapshot_values(creature: Creature) -> dict[str, Any]:
    engine = CreatureEngine(creature)
    armor = engine.armor_totals()
    movement = engine.movement()
    return {
        "name": creature.display_name,
        "creature_type": "",
        "image": creature.image,
        "description": creature.description,
        "source_reference": creature.climate_and_occurrence,
        "quality": creature.quality,
        "initiative": engine.initiative(),
        "vw": engine.vw(),
        "sr": engine.sr(),
        "gw": engine.gw(),
        "fear_resistance_bonus": engine.fear_resistance_bonus(),
        "rs": armor.natural_rs,
        "wound_step": engine.wound_step(),
        "size_class": engine.size_class(),
        "size_modifier": engine.size_modifier(),
        "combat_speed": movement["combat"],
        "march_speed": movement["march"],
        "sprint_speed": movement["sprint"],
        "swimming_speed": movement["swim"],
        "combat_fly_speed": movement["fly_combat"],
        "march_fly_speed": movement["fly_march"],
        "sprint_fly_speed": movement["fly_sprint"],
        "strength_mod": engine.attribute_mod(ATTR_ST),
        "constitution_mod": engine.attribute_mod(ATTR_KON),
        "dexterity_mod": engine.attribute_mod(ATTR_GE),
        "intelligence_mod": engine.attribute_mod(ATTR_INT),
        "perception_mod": engine.attribute_mod(ATTR_WA),
        "willpower_mod": engine.attribute_mod(ATTR_WILL),
        "charisma_mod": engine.attribute_mod(ATTR_CHA),
    }


def _copy_creature_rows(card: CharacterCreatureCard) -> None:
    creature = card.creature
    engine = CreatureEngine(creature)
    CharacterCreatureCardAttack.objects.bulk_create(
        CharacterCreatureCardAttack(
            card=card,
            name=row["name"],
            attack_value=row["attack_value"],
            damage=row["damage"],
            notes=row["notes"],
            order=index,
        )
        for index, row in enumerate(engine.attacks())
    )
    CharacterCreatureCardSkill.objects.bulk_create(
        CharacterCreatureCardSkill(
            card=card,
            name=row["name"],
            value=row["value"],
            notes=row["notes"],
            order=index,
        )
        for index, row in enumerate(engine.skills())
    )
    CharacterCreatureCardTrait.objects.bulk_create(
        CharacterCreatureCardTrait(
            card=card,
            name=row["name"],
            level=row["level"],
            description=row["description"],
            order=index,
        )
        for index, row in enumerate(engine.traits())
    )
    command_references = list(creature.commands.select_related("command").prefetch_related("command__prerequisite_links__prerequisite"))
    card_commands = [
        CharacterCreatureCardCommand(
            card=card,
            name=row.command.name,
            slug=row.command.slug,
            ep_cost=row.command.ep_cost,
            difficulty=row.command.difficulty,
            description=row.command.description,
            order=row.order,
        )
        for row in command_references
    ]
    CharacterCreatureCardCommand.objects.bulk_create(card_commands)
    card_commands_by_name = {command.name: command for command in card_commands if command.pk}
    if len(card_commands_by_name) != len(card_commands):
        card_commands_by_name = {command.name: command for command in card.commands.all()}
    CharacterCreatureCardCommandPrerequisite.objects.bulk_create(
        CharacterCreatureCardCommandPrerequisite(
            command=card_commands_by_name[row.command.name],
            prerequisite=card_commands_by_name[link.prerequisite.name],
            alternative_group=link.alternative_group,
            order=link.order,
        )
        for row in command_references
        for link in row.command.prerequisite_links.all()
        if row.command.name in card_commands_by_name and link.prerequisite.name in card_commands_by_name
    )


def sync_character_creature_cards(character) -> list[CharacterCreatureCard]:
    """Create/reactivate/deactivate concrete creature cards for one character."""

    item_ids = set(
        CharacterItem.objects.filter(owner=character, amount__gt=0, stored=False).values_list("item_id", flat=True)
    )
    technique_ids = set(
        CharacterTechnique.objects.filter(character=character).values_list("technique_id", flat=True)
    )
    bindings = list(
        CreatureCardBinding.objects.filter(active=True, creature__isnull=False)
        .select_related("creature", "creature__quality", "item_trigger", "technique_trigger")
        .prefetch_related(
            "creature__attacks",
            "creature__skills__skill",
            "creature__traits__trait",
            "creature__commands__command",
            "creature__commands__command__prerequisite_links__prerequisite",
        )
    )
    active_binding_ids = set()
    for binding in bindings:
        matches_item = (
            binding.trigger_type == CreatureCardBinding.TriggerType.ITEM
            and binding.item_trigger_id in item_ids
        )
        matches_technique = (
            binding.trigger_type == CreatureCardBinding.TriggerType.TECHNIQUE
            and binding.technique_trigger_id in technique_ids
        )
        if not (matches_item or matches_technique):
            continue
        active_binding_ids.add(binding.pk)
        card, created = CharacterCreatureCard.objects.get_or_create(
            character=character,
            binding=binding,
            defaults=CharacterCreatureCard.snapshot_defaults(
                binding.creature,
                binding,
                _creature_card_snapshot_values(binding.creature),
            ),
        )
        if created:
            _copy_creature_rows(card)
        else:
            update_fields = []
            if not card.active:
                card.active = True
                update_fields.append("active")
            if card.creature_id is None:
                card.creature = binding.creature
                update_fields.append("creature")
            if update_fields:
                card.save(update_fields=update_fields)

    existing_cards = CharacterCreatureCard.objects.filter(character=character)
    existing_cards.exclude(binding_id__in=active_binding_ids).filter(active=True).update(active=False)
    return list(
        existing_cards.filter(active=True)
        .select_related("creature", "quality", "binding", "binding__item_trigger", "binding__technique_trigger")
        .prefetch_related("attacks", "skills", "traits", "commands__prerequisite_links__prerequisite")
        .order_by("name", "id")
    )
