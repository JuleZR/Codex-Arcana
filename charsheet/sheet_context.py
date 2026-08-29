"""Prepared context data for the character sheet template."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
import json
import math

from django.db.models import Q
from django.urls import reverse

from charsheet.constants import (
    ARMOR_ENCUMBRANCE,
    ARMOR_PENALTY_IGNORE,
    ARCANE_POWER,
    ATTRIBUTE_ORDER,
    ATTR_CHA,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DAMAGE_TYPE_CHOICES,
    DEFENSE_GW,
    DEFENSE_RS,
    DEFENSE_SR,
    DEFENSE_VW,
    GK_CHOICES,
    GK_MODS,
    INITIATIVE,
    MELEE_MANEUVERS,
    ONE_HANDED,
    POTENTIAL,
    RULE_FLAG_CHOICES,
    RULE_FLAG_TARGET_KIND,
    SHIELD_ENCUMBRANCE,
    SKILL_COMBAT,
    STAT_SLUG_CHOICES,
    SOURCE_ITEM_RUNE,
    TWO_HANDED,
    VAMPIRE_STATE_UI_LABELS,
    VAMPIRE_ANCHOR_TRAIT_SLUG,
    WEAPON_DAMAGE,
    WEAPON_DAMAGE_DICE,
    WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
    WEAPON_MANEUVER_DAMAGE,
    WEAPON_MASTERY_BONUS,
    WEAPON_MASTERY_EFFECT_DESCRIPTION,
)
from charsheet.engine import BattleCalculatorEngine, CharacterEngine, ItemEngine
from charsheet.engine.creature_engine import CreatureEngine, sync_character_creatures
from charsheet.modifiers.targets import TargetResolver
from charsheet.item_transfers import has_item_permission, item_is_pending, pending_transfer_for_item
from charsheet.item_disclosure import (
    identified_effect_id_sets,
    item_identification_initialized,
    is_character_item_effect_identified,
    resolve_character_item_display,
)
from charsheet.forms import (
    CharacterInfoInlineForm,
    CharacterSkillSpecificationForm,
    CharacterTechniqueSpecificationForm,
    CharacterTraitSpecificationForm,
)
from charsheet.magic_effects import TEXT_TARGET_KIND, unpack_magic_effect_summary
from charsheet.learning_progression import build_learning_magic_groups, build_learning_progression_context
from charsheet.learning_rules import DEFAULT_SCHOOL_MAX_LEVEL, school_max_levels
from charsheet.lesson_rules import (
    LESSON_COST_HANDLERS,
    LessonRuleError,
    format_cost,
    format_lesson_costs,
    format_lesson_requirements,
    lesson_requirements_met,
)
from charsheet.religion_rules import is_clerical_school, selected_divine_entity
from charsheet.models import (
    Aspect,
    AlchemicalBrewStats,
    Character,
    CharacterAspect,
    CharacterDivineEntity,
    CharacterDruidCult,
    CharacterShamanPatron,
    CharacterItem,
    CharacterWeaponMasteryArcana,
    CharacterCreature,
    CharacterDaemonicPower,
    Creature,
    CreatureSourceBinding,
    DivineEntityAspect,
    DivineEntity,
    DruidCult,
    ItemRune,
    CharacterLanguage,
    CharacterLesson,
    CharacterSpell,
    CharacterCreatureTraitChoice,
    CharacterItemSemanticEffect,
    DaemonicPower,
    DaemonicPowerTier,
    RaceStartingItem,
    CharacterTechnique,
    CharacterTrait,
    CharacterVampirePower,
    CreatureCommand,
    CreatureSpecialSkill,
    CreatureTrait,
    CreatureTraitChoice,
    CreatureTraitChoiceDefinition,
    CreatureTraitDefinition,
    DamageSource,
    Item,
    ItemSemanticEffect,
    ItemTransfer,
    Language,
    Lesson,
    LessonCost,
    Quality,
    RaceTechnique,
    Rune,
    School,
    Skill,
    SkillCategory,
    Spell,
    Specialization,
    Technique,
    Trait,
    VampirePower,
    VampireTrait,
    WeaponType,
    Race,
)
from charsheet.view_utils import format_compact_number, format_modifier, format_thousands, quality_payload


LOCAL_WEAPON_DAMAGE_SOURCE_TYPES = {"item", "characteritem", SOURCE_ITEM_RUNE}

SHOP_MODIFIER_MOVEMENT_TARGET_CHOICES = (
    ("ground", "Laufen: Kampf, Marsch und Sprint"),
    ("ground_combat", "Laufen Kampf"),
    ("ground_march", "Laufen Marsch"),
    ("ground_sprint", "Laufen Sprint"),
    ("swim", "Schwimmen: alle Werte"),
    ("swim_combat", "Schwimmen Kampf"),
    ("swim_march", "Schwimmen Marsch"),
    ("swim_sprint", "Schwimmen Sprint"),
    ("fly", "Fliegen: Kampf, Marsch und Sprint"),
    ("fly_combat", "Fliegen Kampf"),
    ("fly_march", "Fliegen Marsch"),
    ("fly_sprint", "Fliegen Sprint"),
)


def _vampire_learning_payload(character, vampire_rules):
    owned_powers = list(
        CharacterVampirePower.objects.filter(character=character)
        .select_related("power")
        .order_by("power__sort_order", "power__name")
    )
    owned_power_ids = {row.power_id for row in owned_powers}
    owned_power_map = {row.power_id: row for row in owned_powers}
    return {
        "age_cycle": vampire_rules.age_cycle(),
        "capacity_bonus": vampire_rules.capacity_bonus(),
        "age_unit_cost": vampire_rules.age_cycle_cost(2),
        "capacity_unit_cost": vampire_rules.capacity_bonus_cost(1),
        "available_powers": [
            {
                "id": power.id,
                "name": power.name,
                "description": power.description,
                "cost_with_weakness": vampire_rules.power_cost(without_weakness=False),
                "cost_without_weakness": vampire_rules.power_cost(without_weakness=True),
                "weakness": power.weakness,
                "level": int(owned_power_map[power.id].level) if power.id in owned_power_map else 0,
                "max_level": 99 if power.can_be_learned_multiple_times else 1,
                "can_choose_without_weakness": power.id not in owned_power_map,
            }
            for power in VampirePower.objects.filter(
                is_active=True,
            ).exclude(weakness="").filter(
                Q(can_be_learned_multiple_times=True) | ~Q(pk__in=owned_power_ids)
            ).order_by("sort_order", "name")
        ],
        "owned_powers": [
            {
                "id": row.power_id,
                "name": row.power.name,
                "description": row.power.description,
                "weakness": row.power.weakness,
                "level": max(1, int(row.level or 1)),
                "can_be_learned_multiple_times": row.power.can_be_learned_multiple_times,
                "refund": (
                    vampire_rules.power_cost(without_weakness=False)
                    if int(row.level or 1) > 1
                    else vampire_rules.power_cost(
                        without_weakness=bool(
                            row.purchased_without_weakness or row.weakness_bought_off
                        )
                    )
                ),
            }
            for row in owned_powers
        ],
        "buyoff_options": [
            {
                "id": row.power_id,
                "name": row.power.name,
                "description": row.power.description,
                "weakness": row.power.weakness,
                "cost": 5,
            }
            for row in owned_powers
            if str(row.power.weakness or "").strip()
            and not row.purchased_without_weakness
            and not row.weakness_bought_off
        ],
    }


def _vampire_sheet_entries(vampire_rules):
    """Keep passive vampire traits and learnable powers separate in the sheet UI."""
    def visible_weakness(entry) -> str:
        if not entry.weakness_is_active:
            return ""
        weakness = str(entry.power.weakness or "").strip()
        return "" if weakness in {"-", "\u2013", "\u2014"} else weakness

    traits = [
        {
            "name": entry.trait.name,
            "slug": entry.trait.slug,
            "type": entry.trait.trait_type,
            "type_label": (
                "Vorzug"
                if entry.trait.trait_type == VampireTrait.TraitType.ADVANTAGE
                else "Schwäche"
            ),
            "rank": entry.rank,
            "description": entry.trait.description,
            "source": entry.source,
        }
        for entry in vampire_rules.effective_traits(include_weaknesses=True)
    ]
    powers = [
        {
            "id": entry.power.id,
            "name": entry.power.name,
            "slug": entry.power.slug,
            "description": entry.power.description,
            "weakness": visible_weakness(entry),
            "weakness_bought_off": not entry.weakness_is_active,
            "blood_cost": entry.power.blood_cost,
            "rank": entry.rank,
            "can_be_learned_multiple_times": entry.power.can_be_learned_multiple_times,
            "source": entry.source,
        }
        for entry in vampire_rules.effective_powers()
    ]
    trait_type_order = {
        VampireTrait.TraitType.ADVANTAGE: 0,
        VampireTrait.TraitType.DISADVANTAGE: 1,
    }
    traits.sort(
        key=lambda row: (
            trait_type_order.get(row["type"], 99),
            str(row["name"]).casefold(),
            str(row["slug"]),
        )
    )
    powers.sort(key=lambda row: (str(row["name"]).casefold(), str(row["slug"])))
    return traits, powers


def _vampire_trait_groups(traits):
    """Group vampire traits as advantages then weaknesses for the schools panel."""
    definitions = (
        (VampireTrait.TraitType.ADVANTAGE, "advantages", "Vorzüge"),
        (VampireTrait.TraitType.DISADVANTAGE, "weaknesses", "Schwächen"),
    )
    return [
        {
            "key": key,
            "label": label,
            "traits": [row for row in traits if row["type"] == trait_type],
        }
        for trait_type, key, label in definitions
        if any(row["type"] == trait_type for row in traits)
    ]


def _divine_entity_card_kind_label(divine_entity) -> str:
    """Return the visible god-card kind for deities and cult demons."""
    school = getattr(divine_entity, "school", None)
    school_name = str(getattr(school, "name", "") or "").strip().casefold()
    school_type = getattr(school, "type", None)
    type_name = str(getattr(school_type, "name", "") or "").strip().casefold()
    type_slug = str(getattr(school_type, "slug", "") or "").strip().casefold()
    is_cult_entity = (
        school_name.startswith(("kultist", "cultist"))
        or type_name in {"kult", "cult"}
        or type_slug in {"kult", "cult", "school_kult", "school_cult"}
    )
    return "Dämon" if is_cult_entity else "Gottheit"


def _cultist_corruption_level(engine) -> int:
    """Return the learned cultist progression, capped for the visual stages."""
    levels = []
    for entry in engine._school_entries.values():
        school = entry.school
        school_name = str(getattr(school, "name", "") or "").strip().casefold()
        school_type = getattr(school, "type", None)
        type_name = str(getattr(school_type, "name", "") or "").strip().casefold()
        type_slug = str(getattr(school_type, "slug", "") or "").strip().casefold()
        if (
            school_name.startswith(("kultist", "cultist"))
            or type_name in {"kult", "cult"}
            or type_slug in {"kult", "cult", "school_kult", "school_cult"}
        ):
            levels.append(int(entry.level))
    return min(10, max(levels, default=0))


def _size_class_options(*, selected: str | None = None) -> list[dict[str, object]]:
    """Return size-class choices with their visible rules modifier."""
    return [
        {
            "value": value,
            "label": label,
            "modifier": int(GK_MODS.get(value, 0)),
            "modifier_display": format_modifier(int(GK_MODS.get(value, 0))),
            "display_label": f"{label} ({format_modifier(int(GK_MODS.get(value, 0)))})",
            "selected": value == selected,
        }
        for value, label in GK_CHOICES
    ]


_DAMAGE_GAUGE_START = -180
_DAMAGE_GAUGE_SWEEP = 180
_DAMAGE_GAUGE_NEEDLE_MIN = 6.0
_DAMAGE_GAUGE_NEEDLE_MAX = 174.0
_DAMAGE_GAUGE_NEEDLE_SWEEP = _DAMAGE_GAUGE_NEEDLE_MAX - _DAMAGE_GAUGE_NEEDLE_MIN
_DAMAGE_GAUGE_CX = 120
_DAMAGE_GAUGE_CY = 122
_DAMAGE_GAUGE_RADIUS = 84
_DAMAGE_GAUGE_TICK_OUTER = 90
_DAMAGE_GAUGE_TICK_INNER_MAJOR = 70
_DAMAGE_GAUGE_TICK_INNER_MINOR = 76


def build_creature_card_training_context(card):
    engine = CreatureEngine(card)
    base_creature = engine.creature
    traits = list(card.trait_overrides.select_related("trait").all())
    base_trait_rows = list(base_creature.traits.select_related("trait").prefetch_related("choices").all())
    base_trait_levels = {
        row.trait_id: int(row.trait_level or 0)
        for row in base_trait_rows
        if row.trait_id
    }
    commands = list(card.commands.select_related("command").prefetch_related("prerequisite_links__prerequisite__command").all())
    skill_overrides = {row.skill_id: row for row in card.skill_overrides.select_related(
        "skill",
        "skill__attribute",
        "skill__category"
        ).all()}
    special_skill_overrides = {
        row.skill_id: row
        for row in card.special_skill_overrides.select_related("skill").all()
    }
    language_overrides = {
        row.language_id: row
        for row in card.language_overrides.select_related("language").all()
    }
    base_language_rows = list(base_creature.languages.select_related("language").all())
    base_language_ids = {row.language_id for row in base_language_rows}
    language_rows = [
        {
            "id": row.language_id,
            "name": row.language.name,
            "can_write": bool(
                language_overrides[row.language_id].can_write
                if row.language_id in language_overrides
                else row.can_write
            ),
            "can_remove": False,
        }
        for row in base_language_rows
    ]
    language_rows.extend(
        {
            "id": row.language_id,
            "name": row.language.name,
            "can_write": bool(row.can_write),
            "can_remove": True,
        }
        for language_id, row in language_overrides.items()
        if language_id not in base_language_ids
    )
    language_rows.sort(key=lambda row: row["name"].casefold())
    known_language_ids = {row["id"] for row in language_rows}
    language_catalog = [
        {"id": language.pk, "name": language.name}
        for language in Language.objects.order_by("name")
        if language.pk not in known_language_ids
    ]
    hidden_skill_note_ids = {
        row.pk
        for row in card.hidden_skill_notes.all()
    }
    skill_rows = []
    seen_skill_ids = set(
        base_creature.skills.filter(
            skill__isnull=False,
            hide_from_creature_training=True,
        ).values_list("skill_id", flat=True)
    )
    seen_special_skill_ids = set()

    def normal_skill_training_row(
        *,
        row_id: str,
        remove_id: str,
        name: str,
        value: int,
        deviation: int,
        notes: str,
        can_remove: bool,
        skill: Skill,
    ) -> dict:
        attribute_modifier = engine._skill_attribute_modifier(skill)
        gk_multiplier = (
            2
            if skill.slug == "skill_hide"
            else 1
            if skill.slug == "skill_evasion" or skill.category.slug == SKILL_COMBAT
            else 0
        )
        gk_modifier = gk_multiplier * engine.size_modifier()
        skill_modifier = engine._modifier_total("skill", skill.slug)
        wound_penalty = engine.current_wound_penalty()
        return {
            "id": row_id,
            "remove_id": remove_id,
            "name": name,
            "value": value,
            "notes": notes,
            "can_remove": can_remove,
            "is_normal_skill": True,
            "attribute": skill.attribute.short_name,
            "deviation": deviation,
            "attribute_modifier": attribute_modifier,
            "gk_multiplier": gk_multiplier,
            "gk_modifier": gk_modifier,
            "skill_modifier": skill_modifier,
            "wound_penalty": wound_penalty,
            "effective_value": value + deviation + attribute_modifier + gk_modifier + skill_modifier + wound_penalty,
        }

    for note_row in base_creature.skills.filter(skill__isnull=True):
        note = str(note_row.notes or "").strip()
        if not note:
            continue
        skill_rows.append(
            {
                "id": f"note_{note_row.pk}",
                "note_id": note_row.pk,
                "name": note,
                "notes": "",
                "can_remove": False,
                "is_normal_skill": False,
                "is_note_only": True,
                "visible_on_card": note_row.pk not in hidden_skill_note_ids,
            }
        )

    for base_skill in base_creature.skills.select_related(
        "skill",
        "skill__attribute",
        "skill__category",
    ).filter(skill__isnull=False, hide_from_creature_training=False):
        override = skill_overrides.get(base_skill.skill_id)
        seen_skill_ids.add(base_skill.skill_id)
        skill_rows.append(
            normal_skill_training_row(
                row_id=f"normal_{base_skill.skill_id}",
                remove_id="",
                name=base_skill.skill.name,
                value=override.value if override else base_skill.value,
                deviation=int(base_skill.deviation or 0) + (int(override.deviation or 0) if override else 0),
                notes=(override.notes if override and override.notes else base_skill.notes or base_skill.skill.description),
                can_remove=False,
                skill=base_skill.skill,
            )
        )
    for override in skill_overrides.values():
        if override.skill_id in seen_skill_ids:
            continue
        seen_skill_ids.add(override.skill_id)
        skill_rows.append(
            normal_skill_training_row(
                row_id=f"normal_{override.skill_id}",
                remove_id=f"normal:{override.skill_id}",
                name=override.skill.name,
                value=override.value,
                deviation=int(override.deviation or 0),
                notes=override.notes or override.skill.description,
                can_remove=True,
                skill=override.skill,
            )
        )
    for base_skill in base_creature.special_skills.select_related("skill").all():
        override = special_skill_overrides.get(base_skill.skill_id)
        seen_special_skill_ids.add(base_skill.skill_id)
        skill_rows.append(
            {
                "id": f"special_{base_skill.skill_id}",
                "remove_id": "",
                "name": base_skill.skill.name,
                "value": override.value_override if override else base_skill.value,
                "notes": (override.notes if override and override.notes else base_skill.notes or base_skill.skill.description),
                "can_remove": False,
                "is_normal_skill": False,
            }
        )
    for override in special_skill_overrides.values():
        if override.skill_id in seen_special_skill_ids:
            continue
        seen_special_skill_ids.add(override.skill_id)
        skill_rows.append(
            {
                "id": f"special_{override.skill_id}",
                "remove_id": f"special:{override.skill_id}",
                "name": override.skill.name,
                "value": override.value_override,
                "notes": override.notes or override.skill.description,
                "can_remove": True,
                "is_normal_skill": False,
            }
        )
    attribute_increases = {
        row.attribute: row.amount
        for row in card.attribute_increases.all()
    }
    total_disadvantage_points = sum(
        row.point_cost
        for row in traits
        if row.training_trait_type == row.TrainingTraitType.DISADVANTAGE
    )
    base_disadvantage_points = min(total_disadvantage_points, int(card.max_base_disadvantage_points or 0))
    additional_disadvantage_points = max(0, total_disadvantage_points - base_disadvantage_points)
    advantage_points = sum(
        row.point_cost
        for row in traits
        if row.training_trait_type == row.TrainingTraitType.ADVANTAGE
    )
    bonus_advantage_points = min(additional_disadvantage_points, 4)
    effective_advantage_points = int(card.max_base_advantage_points or 0) + bonus_advantage_points
    effective_disadvantage_points = int(card.max_base_disadvantage_points or 0) + 4
    remaining_advantage_points = effective_advantage_points - advantage_points
    known_command_slugs = {command.slug for command in commands if command.slug}
    advantage_levels = {
        row.trait_id: int(row.trait_level or 1)
        for row in traits
        if row.trait_id and row.training_trait_type == row.TrainingTraitType.ADVANTAGE
    }
    disadvantage_levels = {
        row.trait_id: int(row.trait_level or 1)
        for row in traits
        if row.trait_id and row.training_trait_type == row.TrainingTraitType.DISADVANTAGE
    }
    visible_hidden_trait_ids = set(base_trait_levels) | set(advantage_levels) | set(disadvantage_levels)
    existing_trait_choices = {
        (choice.character_creature_trait.trait_id, choice.definition_id): choice
        for choice in CharacterCreatureTraitChoice.objects.filter(character_creature_trait__in=traits)
        .select_related("character_creature_trait", "selected_skill")
    }
    base_trait_choices = {
        (choice.creature_trait.trait_id, choice.definition_id): choice
        for choice in CreatureTraitChoice.objects.filter(creature_trait__in=base_trait_rows)
        .select_related("creature_trait", "selected_skill")
    }
    command_catalog = []
    for command in CreatureCommand.objects.prefetch_related("prerequisite_links__prerequisite").order_by("name"):
        prerequisite_groups = command.prerequisite_groups
        missing = [
            prerequisite.name
            for group in prerequisite_groups
            if not any(prerequisite.slug in known_command_slugs for prerequisite in group)
            for prerequisite in group
        ]
        command_catalog.append(
            {
                "id": command.pk,
                "name": command.name,
                "slug": command.slug,
                "ep_cost": command.ep_cost,
                "training_days": command.training_days,
                "difficulty": command.difficulty,
                "prerequisite_display": command.prerequisite_display,
                "missing_prerequisites": missing,
                "prerequisite_group_ids_json": json.dumps(
                    [[prerequisite.pk for prerequisite in group] for group in prerequisite_groups]
                ),
                "known": command.slug in known_command_slugs,
            }
        )

    def skill_choice_options(definition):
        skills = Skill.objects.select_related("category").order_by("name")
        if definition.pk:
            allowed_skill_ids = list(definition.allowed_skills.values_list("id", flat=True))
            allowed_category_ids = list(definition.allowed_skill_categories.values_list("id", flat=True))
            if allowed_skill_ids:
                skills = skills.filter(pk__in=allowed_skill_ids)
            if allowed_category_ids:
                skills = skills.filter(category_id__in=allowed_category_ids)
        if definition.allowed_skill_category_id:
            skills = skills.filter(category_id=definition.allowed_skill_category_id)
        if definition.allowed_skill_family:
            skills = skills.filter(family=definition.allowed_skill_family)
        return [{"value": skill.pk, "label": skill.name, "meta": skill.category.name} for skill in skills]

    def trait_choice_rows(trait):
        rows = []
        for definition in trait.choice_definitions.all():
            if not definition.is_active:
                continue
            if definition.target_kind != CreatureTraitChoiceDefinition.TargetKind.SKILL:
                rows.append(
                    {
                        "definition_id": definition.pk,
                        "name": definition.name,
                        "input_type": "unsupported",
                        "note": "Diese Choice-Art wird im Kreaturen-Training noch nicht direkt bearbeitet.",
                    }
                )
                continue
            existing_choice = existing_trait_choices.get((trait.pk, definition.pk)) or base_trait_choices.get(
                (trait.pk, definition.pk)
            )
            rows.append(
                {
                    "definition_id": definition.pk,
                    "name": definition.name,
                    "input_type": "skill",
                    "field_name": f"creature_trait_choice_{trait.pk}_{definition.pk}",
                    "required": definition.is_required,
                    "selected": existing_choice.selected_skill_id if existing_choice else "",
                    "options": skill_choice_options(definition),
                }
            )
        return rows

    trait_catalog = []
    for trait in CreatureTraitDefinition.objects.prefetch_related(
        "choice_definitions",
        "choice_definitions__allowed_skills",
        "choice_definitions__allowed_skill_categories",
    ).order_by("trait_type", "name"):
        if trait.hide_from_creature_training and trait.pk not in visible_hidden_trait_ids:
            continue
        advantage_selected = trait.pk in advantage_levels
        disadvantage_selected = trait.pk in disadvantage_levels
        base_level = int(base_trait_levels.get(trait.pk, 0) or 0)
        advantage_total_level = int(advantage_levels.get(trait.pk, base_level) or base_level)
        disadvantage_total_level = int(disadvantage_levels.get(trait.pk, base_level) or base_level)
        trait_catalog.append(
            {
                "id": trait.pk,
                "name": trait.name,
                "trait_type": trait.trait_type,
                "min_level": trait.min_level,
                "max_level": trait.max_level,
                "training_min_level": max(int(trait.min_level), base_level),
                "training_max_level": int(trait.max_level),
                "cost_display": trait.cost_display(),
                "advantage_selected": advantage_selected or bool(base_level and trait.trait_type == trait.TraitType.ADV),
                "disadvantage_selected": disadvantage_selected or bool(base_level and trait.trait_type == trait.TraitType.DIS),
                "advantage_level": advantage_total_level if advantage_selected or base_level else int(trait.min_level),
                "disadvantage_level": disadvantage_total_level if disadvantage_selected or base_level else int(trait.min_level),
                "base_level": base_level,
                "has_base": bool(base_level),
                "effective_advantage_level": advantage_total_level,
                "effective_disadvantage_level": disadvantage_total_level,
                "choice_rows": trait_choice_rows(trait),
            }
        )
    card_attribute_values = {
        ATTR_ST: engine.attribute_base_mod(ATTR_ST),
        ATTR_KON: engine.attribute_base_mod(ATTR_KON),
        ATTR_GE: engine.attribute_base_mod(ATTR_GE),
        ATTR_INT: engine.attribute_base_mod(ATTR_INT),
        ATTR_WA: engine.attribute_base_mod(ATTR_WA),
        ATTR_WILL: engine.attribute_base_mod(ATTR_WILL),
        ATTR_CHA: engine.attribute_base_mod(ATTR_CHA),
    }
    attribute_options = []
    for code, label in (
        (ATTR_ST, "Stärke"),
        (ATTR_KON, "Konstitution"),
        (ATTR_GE, "Geschick"),
        (ATTR_INT, "Intelligenz"),
        (ATTR_WA, "Wahrnehmung"),
        (ATTR_WILL, "Willenskraft"),
        (ATTR_CHA, "Charisma"),
    ):
        base_value = card_attribute_values.get(code)
        increase = attribute_increases.get(code, 0)
        current_modifier = None if base_value is None else int(base_value) + int(increase or 0)
        current_attribute_value = None if current_modifier is None else current_modifier + 5
        base_attribute_value = None if base_value is None else int(base_value) + 5
        attribute_options.append(
            {
                "code": code,
                "label": label,
                "base": base_value,
                "base_value": base_attribute_value,
                "amount": increase,
                "current": current_modifier,
                "current_value": current_attribute_value,
                "input_value": 0 if current_attribute_value is None else current_attribute_value,
                "current_value_display": "-" if current_attribute_value is None else str(current_attribute_value),
                "current_display": "-" if current_modifier is None else f"{current_modifier:+d}",
            }
        )

    quality_choices = [
        {
            "value": quality.code,
            "label": quality.name,
            "color": quality.hex_color,
            "selected": quality.code == getattr(card.quality, "code", card.quality_id),
        }
        for quality in Quality.objects.all()
    ]
    existing_skill_names = {
        skill["name"].casefold()
        for skill in skill_rows
    } | {
        row.skill.name.casefold()
        for row in base_creature.skills.select_related("skill").filter(skill__isnull=False)
    }
    skill_catalog = [
        {
            "id": f"skill:{skill.pk}",
            "name": skill.name,
        }
        for skill in Skill.objects.order_by("name")
        if skill.name.casefold() not in existing_skill_names
    ]
    special_skill_catalog = [
        {
            "id": f"special:{skill.pk}",
            "name": skill.name,
        }
        for skill in CreatureSpecialSkill.objects.order_by("name")
        if skill.name.casefold() not in existing_skill_names
    ]
    movement = engine.movement()
    can_swim = any(movement.get(field_name) is not None for field_name in ("swim_combat", "swim_march", "swim_sprint"))
    can_fly = any(movement.get(field_name) is not None for field_name in ("fly_combat", "fly_march", "fly_sprint"))
    movement_mana_adjustment = int(card.movement_mana_cost_override or 0)
    movement_mana_cost = (
        None
        if base_creature.movement_mana_cost is None and not movement_mana_adjustment
        else max(0, int(base_creature.movement_mana_cost or 0) + movement_mana_adjustment)
    )
    can_mana = movement_mana_cost is not None
    movement_options = {
        "combat_speed": format_compact_number(movement["combat"] or 0),
        "march_speed": format_compact_number(movement["march"] or 0),
        "sprint_speed": format_compact_number(movement["sprint"] or 0),
        "swimming_speed": format_compact_number(movement["swim"] or 0),
        "combat_swimming_speed": "" if movement["swim_combat"] is None else format_compact_number(movement["swim_combat"]),
        "march_swimming_speed": "" if movement["swim_march"] is None else format_compact_number(movement["swim_march"]),
        "sprint_swimming_speed": "" if movement["swim_sprint"] is None else format_compact_number(movement["swim_sprint"]),
        "can_swim": can_swim,
        "can_fly": can_fly,
        "combat_fly_speed": format_compact_number(movement["fly_combat"] or 0),
        "march_fly_speed": format_compact_number(movement["fly_march"] or 0),
        "sprint_fly_speed": format_compact_number(movement["fly_sprint"] or 0),
        "movement_mana_cost": "" if movement_mana_cost is None else movement_mana_cost,
        "movement_note": engine._value("movement_note", ""),
        "can_mana": can_mana,
    }
    current_size_class = engine.size_class()
    size_options = _size_class_options(selected=current_size_class)
    armor = engine.armor_totals()
    core_value_options = {
        "initiative": engine.initiative(),
        "vw": engine.vw(),
        "sr": engine.sr(),
        "gw": engine.gw(),
        "natural_rs": armor.natural_rs,
        "wound_step": engine.wound_step(),
        "wound_thresholds": card.wound_thresholds_override or base_creature.wound_thresholds_override,
    }
    base_daemonic_power_ids = set(
        base_creature.daemonic_powers.values_list("id", flat=True)
    )
    trained_daemonic_power_ids = set(
        card.daemonic_power_additions.values_list("power_id", flat=True)
    )
    daemonic_power_groups = []
    for tier in DaemonicPowerTier.objects.prefetch_related("powers").order_by(
        "sort_number",
        "name",
        "id",
    ):
        rows = []
        for power in tier.powers.order_by("name", "id"):
            is_base = power.id in base_daemonic_power_ids
            rows.append(
                {
                    "id": power.id,
                    "name": power.name,
                    "description": power.description,
                    "weakness_description": power.weakness_description,
                    "selected": is_base or power.id in trained_daemonic_power_ids,
                    "is_base": is_base,
                }
            )
        if rows:
            daemonic_power_groups.append(
                {
                    "id": tier.id,
                    "name": tier.name,
                    "slug": tier.slug,
                    "sort_number": tier.sort_number,
                    "powers": rows,
                }
            )

    return {
        "card": card,
        "update_url": reverse("update_character_creature_training", kwargs={"pk": card.pk}),
        "quality_choices": quality_choices,
        "current_quality": quality_payload(card.quality),
        "commands": commands,
        "skill_rows": skill_rows,
        "skill_catalog": skill_catalog,
        "special_skill_catalog": special_skill_catalog,
        "language_rows": language_rows,
        "language_catalog": language_catalog,
        "known_command_ids": {command.command_id for command in commands if command.command_id},
        "command_catalog": command_catalog,
        "traits": traits,
        "trait_catalog": trait_catalog,
        "advantage_ids": set(advantage_levels),
        "disadvantage_ids": set(disadvantage_levels),
        "attribute_increases": attribute_increases,
        "attribute_options": attribute_options,
        "size_options": size_options,
        "current_size_class": current_size_class,
        "current_size_modifier": int(GK_MODS.get(current_size_class, 0)),
        "current_size_modifier_display": format_modifier(int(GK_MODS.get(current_size_class, 0))),
        "movement_options": movement_options,
        "core_value_options": core_value_options,
        "daemonic_power_groups": daemonic_power_groups,
        "base_advantage_points": int(card.max_base_advantage_points or 0),
        "base_disadvantage_points": int(card.max_base_disadvantage_points or 0),
        "spent_advantage_points": advantage_points,
        "spent_base_disadvantage_points": base_disadvantage_points,
        "spent_additional_disadvantage_points": additional_disadvantage_points,
        "spent_disadvantage_points": total_disadvantage_points,
        "bonus_advantage_points": bonus_advantage_points,
        "effective_advantage_points": effective_advantage_points,
        "effective_disadvantage_points": effective_disadvantage_points,
        "quality_advantage_points": int(card.max_base_advantage_points or 0),
        "weakness_advantage_points": bonus_advantage_points,
        "consumed_advantage_points": advantage_points,
        "open_advantage_points": remaining_advantage_points,
        "remaining_advantage_points": remaining_advantage_points,
        "remaining_disadvantage_points": effective_disadvantage_points - base_disadvantage_points - additional_disadvantage_points,
    }


def _creature_trait_skill_choice_options(definition: CreatureTraitChoiceDefinition) -> list[dict[str, object]]:
    skills = Skill.objects.select_related("category").order_by("name")
    allowed_skill_ids = list(definition.allowed_skills.values_list("id", flat=True))
    allowed_category_ids = list(definition.allowed_skill_categories.values_list("id", flat=True))
    if allowed_skill_ids:
        skills = skills.filter(pk__in=allowed_skill_ids)
    if allowed_category_ids:
        skills = skills.filter(category_id__in=allowed_category_ids)
    if definition.allowed_skill_category_id:
        skills = skills.filter(category_id=definition.allowed_skill_category_id)
    if definition.allowed_skill_family:
        skills = skills.filter(family=definition.allowed_skill_family)
    options = [{"value": f"skill:{skill.pk}", "label": skill.name, "meta": skill.category.name} for skill in skills]
    special_skills = (
        CreatureSpecialSkill.objects.order_by("name")
        if definition.allow_all_creature_special_skills
        else definition.allowed_creature_special_skills.order_by("name")
    )
    options.extend(
        {
            "value": f"special:{skill.pk}",
            "label": skill.name,
            "meta": "Kreatur-Spezialfertigkeit",
        }
        for skill in special_skills
    )
    return options


def build_creature_choice_progression_context(cards: list[CharacterCreature]) -> dict[str, object]:
    choice_rows = []
    pending_decisions = []
    for card in cards:
        base_rows = list(CreatureEngine(card).creature.traits.select_related("trait").prefetch_related("choices").all())
        override_rows = list(card.trait_overrides.select_related("base_trait", "trait").prefetch_related("choices").all())
        override_by_trait_id = {row.trait_id: row for row in override_rows if row.active}
        effective_rows = [override_by_trait_id.get(row.trait_id) or row for row in base_rows]
        base_trait_ids = {row.trait_id for row in base_rows}
        effective_rows.extend(row for row in override_rows if row.active and row.trait_id not in base_trait_ids)
        for row in effective_rows:
            definitions = list(
                row.trait.choice_definitions.filter(
                    is_active=True,
                    target_kind=CreatureTraitChoiceDefinition.TargetKind.SKILL,
                )
                .prefetch_related("allowed_skills", "allowed_skill_categories", "allowed_creature_special_skills")
                .order_by("sort_order", "name", "id")
            )
            if not definitions:
                continue
            existing_choices = list(row.choices.all())
            trait_level = max(1, int(getattr(row, "trait_level", 1) or 1))
            for definition in definitions:
                existing_count = len([choice for choice in existing_choices if choice.definition_id == definition.id])
                required_count = (definition.min_choices if definition.is_required else 0) * trait_level
                missing_count = max(0, required_count - existing_count)
                allow_duplicate_selections = bool(definition.allow_duplicate_selections)
                for slot_index in range(missing_count):
                    field_name = f"learn_choice_creature_trait_{card.pk}_{row.trait_id}_{definition.pk}_{slot_index}"
                    options = _creature_trait_skill_choice_options(definition)
                    choice_rows.append(
                        {
                            "choice_scope": "creature_trait",
                            "card_id": card.pk,
                            "base_trait_id": row.id if isinstance(row, CreatureTrait) else None,
                            "trait_id": row.trait_id,
                            "definition_id": definition.pk,
                            "target_kind": definition.target_kind,
                            "field_name": field_name,
                            "supported": True,
                            "options": options,
                        }
                    )
                    pending_decisions.append(
                        {
                            "decision_id": f"creature-trait-choice-{card.pk}-{row.trait_id}-{definition.pk}-{slot_index}",
                            "kind": "creature_trait_choice",
                            "title": f"Choice: {card.display_name}",
                            "summary": f"{row.trait.name}: {definition.name}",
                            "description": definition.description or "",
                            "prompt": "Auswahl treffen",
                            "input_type": "options",
                            "supported": True,
                            "selection_group_id": f"creature-trait-choice:{card.pk}:{row.trait_id}:{definition.pk}",
                            "allow_duplicate_selections": allow_duplicate_selections,
                            "options": [
                                {
                                    "id": str(option["value"]),
                                    "label": option["label"],
                                    "meta": option["meta"],
                                    "badge": "",
                                    "description": "",
                                    "facts": [],
                                    "submit_name": field_name,
                                    "submit_value": str(option["value"]),
                                }
                                for option in options
                            ],
                        }
                    )
    return {"learn_choice_rows": choice_rows, "learn_pending_decisions": pending_decisions}


def _spell_attribute_chart_line(counts: dict[str, int]) -> str:
    """Return compact tooltip markup for spell-attribute frequency bars."""
    if not any(int(count or 0) > 0 for count in counts.values()):
        return ""
    ordered_codes = [short_name for short_name, _label in ATTRIBUTE_ORDER]
    extras = sorted(code for code in counts if code not in ordered_codes)
    entries = [
        f"{code}={max(0, int(counts.get(code, 0) or 0))}"
        for code in [*ordered_codes, *extras]
    ]
    return f"[[SPELLATTR:{';'.join(entries)}]]"


def _tooltip_source_symbol_line(
    symbol: str = "",
    image_url: str = "",
    secondary_symbol: str = "",
    secondary_image_url: str = "",
) -> str:
    symbol = str(symbol or "").strip()
    image_url = str(image_url or "").strip()
    secondary_symbol = str(secondary_symbol or "").strip()
    secondary_image_url = str(secondary_image_url or "").strip()
    if not symbol and not image_url and not secondary_symbol and not secondary_image_url:
        return ""
    return f"[[SOURCESYMBOL:{symbol}|{image_url}|{secondary_symbol}|{secondary_image_url}]]"


def _prepend_tooltip_source_symbol(
    description: str,
    symbol: str = "",
    image_url: str = "",
    secondary_symbol: str = "",
    secondary_image_url: str = "",
) -> str:
    description = str(description or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    symbol_line = _tooltip_source_symbol_line(symbol, image_url, secondary_symbol, secondary_image_url)
    if not symbol_line:
        return description
    return f"{symbol_line}\n{description}" if description else symbol_line


def _append_spell_attribute_chart(description: str, chart_line: str) -> str:
    description = str(description or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    chart_line = str(chart_line or "").strip()
    if not chart_line:
        return description
    chart_block = f"**Prägende Eigenschaften**\n{chart_line}"
    return f"{description}\n\n{chart_block}" if description else chart_block


def _spell_attribute_chart_maps() -> tuple[dict[int, str], dict[int, str]]:
    school_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    aspect_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for spell in Spell.objects.select_related("spell_attribute").exclude(spell_attribute__isnull=True):
        code = str(spell.spell_attribute.short_name or spell.spell_attribute.name or "").strip()
        if not code:
            continue
        if spell.school_id:
            school_counts[int(spell.school_id)][code] += 1
        if spell.aspect_id:
            aspect_counts[int(spell.aspect_id)][code] += 1

    linked_school_aspects: set[tuple[int, int]] = set(
        DivineEntityAspect.objects.exclude(entity__school__isnull=True)
        .exclude(aspect__isnull=True)
        .values_list("entity__school_id", "aspect_id")
        .distinct()
    )
    for school_id, aspect_id in linked_school_aspects:
        for code, count in aspect_counts.get(int(aspect_id), {}).items():
            school_counts[int(school_id)][code] += int(count or 0)

    return (
        {school_id: _spell_attribute_chart_line(counts) for school_id, counts in school_counts.items()},
        {aspect_id: _spell_attribute_chart_line(counts) for aspect_id, counts in aspect_counts.items()},
    )


def _damage_gauge_stage_label(stage: str) -> str:
    labels = {
        "-": "Stabil",
        "Angeschlagen": "Angeschlagen",
        "Verletzt": "Verletzt",
        "Verwundet": "Verwundet",
        "Schwer verwundet": "Schwer",
        "Ausser Gefecht": "Gefecht",
        "Außer Gefecht": "Gefecht",
        "Koma": "Koma",
        "Tod": "Tod",
    }
    return labels.get(stage, stage)


def _damage_gauge_point(angle_degrees: float, radius: float) -> tuple[float, float]:
    radians = math.radians(angle_degrees)
    return (
        _DAMAGE_GAUGE_CX + math.cos(radians) * radius,
        _DAMAGE_GAUGE_CY + math.sin(radians) * radius,
    )


def _damage_gauge_arc_path(start_angle: float, end_angle: float, radius: float = _DAMAGE_GAUGE_RADIUS) -> str:
    start_x, start_y = _damage_gauge_point(start_angle, radius)
    end_x, end_y = _damage_gauge_point(end_angle, radius)
    large_arc_flag = 1 if abs(end_angle - start_angle) > 180 else 0
    return (
        f"M {start_x:.2f} {start_y:.2f} "
        f"A {radius:.2f} {radius:.2f} 0 {large_arc_flag} 1 {end_x:.2f} {end_y:.2f}"
    )


def _mix_hex_color(start_hex: str, end_hex: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, float(ratio)))
    start = start_hex.lstrip("#")
    end = end_hex.lstrip("#")
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (0, 2, 4))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (0, 2, 4))
    mixed = tuple(round(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * ratio) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _build_damage_gauge_data(
    current_damage: int,
    threshold_rows: list[dict[str, int | str]],
    damage_max: int,
    *,
    stun_damage: int = 0,
    lethal_damage: int = 0,
) -> dict[str, object]:
    if damage_max <= 0:
        damage_max = 1

    sorted_threshold_values = sorted(
        int(row["threshold"])
        for row in threshold_rows
        if row.get("threshold") is not None
    )

    def value_to_rotation(value: float) -> float:
        clamped = max(0.0, min(float(damage_max), float(value)))
        adjusted = clamped
        if clamped in sorted_threshold_values and clamped < float(damage_max):
            adjusted = clamped + 1.0
        elif 0.0 < clamped < float(damage_max):
            adjusted = clamped + 0.5
        adjusted = max(0.0, min(float(damage_max), adjusted))
        return _DAMAGE_GAUGE_NEEDLE_MIN + (adjusted / float(damage_max)) * _DAMAGE_GAUGE_NEEDLE_SWEEP

    sorted_rows = sorted(
        (
            {
                "threshold": int(row["threshold"]),
                "stage": str(row["stage"]),
                "penalty": int(row["penalty"] or 0),
            }
            for row in threshold_rows
            if row.get("threshold") is not None
        ),
        key=lambda row: row["threshold"],
    )

    interval_segments: list[dict[str, object]] = []
    current_stage = "-"
    current_penalty = 0
    segment_start = 0

    for row in sorted_rows:
        threshold = max(0, min(int(row["threshold"]), int(damage_max)))
        if row["stage"] == current_stage and row["penalty"] == current_penalty:
            continue
        if threshold > segment_start:
            interval_segments.append(
                {
                    "start_value": segment_start,
                    "end_value": threshold,
                    "stage": current_stage,
                    "penalty": current_penalty,
                }
            )
        current_stage = row["stage"]
        current_penalty = row["penalty"]
        segment_start = threshold

    if segment_start < damage_max:
        interval_segments.append(
            {
                "start_value": segment_start,
                "end_value": damage_max,
                "stage": current_stage,
                "penalty": current_penalty,
            }
        )

    if not interval_segments:
        interval_segments = [{"start_value": 0, "end_value": damage_max, "stage": "-", "penalty": 0}]

    if sorted_rows and sorted_rows[-1]["threshold"] >= damage_max:
        terminal_stage = sorted_rows[-1]["stage"]
        terminal_penalty = sorted_rows[-1]["penalty"]
        previous_threshold = sorted_rows[-2]["threshold"] if len(sorted_rows) > 1 else 0
        terminal_visual_width = max(1.0, (damage_max - previous_threshold) * 0.28)
        terminal_start = max(float(previous_threshold), float(damage_max) - terminal_visual_width)
        if interval_segments:
            interval_segments[-1]["end_value"] = terminal_start
        interval_segments.append(
            {
                "start_value": terminal_start,
                "end_value": float(damage_max),
                "stage": terminal_stage,
                "penalty": terminal_penalty,
            }
        )

    first_danger_index = next(
        (index for index, segment in enumerate(interval_segments) if int(segment["penalty"]) < 0),
        len(interval_segments),
    )

    def _segment_label_position(start_percent: float, end_percent: float) -> tuple[str, str]:
        mid_ratio = ((start_percent + end_percent) / 2.0) / 100.0
        angle = math.radians(180.0 - (mid_ratio * 180.0))
        radius_x = 38.0
        radius_y = 81.0
        x = 50.0 + math.cos(angle) * radius_x
        y = 100.0 - math.sin(angle) * radius_y
        return (f"{x:.2f}%", f"{y:.2f}%")

    segments: list[dict[str, object]] = []
    safe_count = max(1, first_danger_index)
    danger_count = max(1, len(interval_segments) - first_danger_index)
    for index, state_segment in enumerate(interval_segments):
        start_percent = (float(state_segment["start_value"]) / float(damage_max)) * 100.0
        end_percent = (float(state_segment["end_value"]) / float(damage_max)) * 100.0
        label_left, label_top = _segment_label_position(start_percent, end_percent)
        penalty = int(state_segment["penalty"])
        if index < first_danger_index:
            safe_ratio = 0.0 if safe_count <= 1 else index / float(safe_count - 1)
            color = _mix_hex_color("#18995a", "#7bd883", safe_ratio)
            class_name = "is-safe"
        else:
            danger_index = index - first_danger_index
            danger_ratio = 0.0 if danger_count <= 1 else danger_index / float(danger_count - 1)
            color = _mix_hex_color("#f08a56", "#b31325", danger_ratio)
            class_name = "is-danger"
        if str(state_segment["stage"]).strip() == "Koma":
            color = "#8d1623"

        segments.append(
            {
                "stage": state_segment["stage"],
                "class_name": class_name,
                "start_percent": f"{start_percent:.4f}",
                "end_percent": f"{end_percent:.4f}",
                "color": color,
                "penalty_display": format_modifier(penalty) if penalty else "",
                "label_left": label_left,
                "label_top": label_top,
            }
        )

    gradient_stops = ", ".join(
        f"{segment['color']} {_DAMAGE_GAUGE_NEEDLE_MIN + (float(segment['start_percent']) / 100.0) * _DAMAGE_GAUGE_NEEDLE_SWEEP:.2f}deg "
        f"{_DAMAGE_GAUGE_NEEDLE_MIN + (float(segment['end_percent']) / 100.0) * _DAMAGE_GAUGE_NEEDLE_SWEEP:.2f}deg"
        for segment in segments
    )
    needle_angle = value_to_rotation(current_damage)
    return {
        "needle_angle": f"{needle_angle:.2f}",
        "stun_needle_angle": f"{value_to_rotation(stun_damage):.2f}",
        "lethal_needle_angle": f"{value_to_rotation(lethal_damage):.2f}",
        "total_needle_angle": f"{needle_angle:.2f}",
        "segments": segments,
        "gradient_stops": gradient_stops,
    }


SHOP_ARMOR_COMPONENT_GROUP = "armor_component"

SHOP_GROUP_LABELS = {
    Item.ItemType.WEAPON: "Waffen",
    Item.ItemType.ARMOR: "Rüstungen",
    SHOP_ARMOR_COMPONENT_GROUP: "Rüstungsteile",
    Item.ItemType.SHIELD: "Schilde",
    Item.ItemType.CLOTHING: "Kleidung",
    Item.ItemType.RING: "Ringe",
    Item.ItemType.AMULET: "Amulette",
    Item.ItemType.MAGICAL_WEAPON: "Magische Waffen",
    Item.ItemType.MAGICAL_ARMOR: "Magische Rüstungen",
    Item.ItemType.AMMO: "Munition",
    Item.ItemType.ALCHEMICAL_BREW: "Alchemistische Gebräue",
    Item.ItemType.EQUIPMENT: "Ausrüstung",
    Item.ItemType.CONSUM: "Verbrauchsgegenstände",
    Item.ItemType.CREATURE: "Tiere & Kreaturen",
    Item.ItemType.MISC: "Sonstiges",
}
SHOP_GROUP_ORDER = [
    Item.ItemType.WEAPON,
    Item.ItemType.ARMOR,
    SHOP_ARMOR_COMPONENT_GROUP,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    Item.ItemType.RING,
    Item.ItemType.AMULET,
    Item.ItemType.MAGICAL_WEAPON,
    Item.ItemType.MAGICAL_ARMOR,
    Item.ItemType.AMMO,
    Item.ItemType.CONSUM,
    Item.ItemType.ALCHEMICAL_BREW,
    Item.ItemType.CREATURE,
    Item.ItemType.EQUIPMENT,
    Item.ItemType.MISC,
]
SHOP_FORM_ORDER = [
    Item.ItemType.MISC,
    Item.ItemType.CREATURE,
    Item.ItemType.CONSUM,
    Item.ItemType.AMMO,
    Item.ItemType.WEAPON,
    Item.ItemType.ARMOR,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    Item.ItemType.RING,
    Item.ItemType.AMULET,
    Item.ItemType.MAGICAL_WEAPON,
    Item.ItemType.MAGICAL_ARMOR,
]
QUALITY_TOOLTIP_TYPES = {
    Item.ItemType.ARMOR,
    Item.ItemType.WEAPON,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    *Item.magic_item_type_values(),
}
EQUIPPABLE_ITEM_TYPES = {
    Item.ItemType.ARMOR,
    Item.ItemType.WEAPON,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    *Item.magic_item_type_values(),
}
RUNE_RETROFIT_ITEM_TYPES = {Item.ItemType.ARMOR, Item.ItemType.WEAPON, Item.ItemType.MISC}
MODIFIER_SOURCE_LABELS = {
    "race": "Rasse",
    "trait": "Merkmal",
    "school": "Schule",
    "technique": "Technik",
    "daemonic_power": "Dämonische Kraft",
    "item": "Magischer Gegenstand",
    SOURCE_ITEM_RUNE: "Rune",
}


def _single_line(value: str) -> str:
    """Collapse multiline text into one tooltip-friendly line."""
    return " ".join(str(value or "").replace("\r", "\n").split())


def _semantic_rounding_mode(rules_text: str) -> str:
    text = str(rules_text or "").lower()

    if "[[auf]]" in text:
        return "ceil"

    if "[[ab]]" in text:
        return "floor"

    return ""


def _strip_semantic_rule_markers(text: str) -> str:
    return (
        str(text or "")
        .replace("[[prozent]]", "")
        .replace("[[auf]]", "")
        .replace("[[ab]]", "")
        .strip()
    )


def _to_roman(value: int | None) -> str:
    """Convert positive integers into Roman numerals for school level labels."""
    number = int(value or 0)
    if number <= 0:
        return ""
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    parts: list[str] = []
    for arabic, roman in numerals:
        while number >= arabic:
            parts.append(roman)
            number -= arabic
    return "".join(parts)


def _rune_image_url(rune: Rune) -> str:
    """Return a tooltip-safe rune image URL when an image is present."""
    image = getattr(rune, "image", None)
    if not image:
        return ""
    try:
        return _single_line(image.url)
    except (ValueError, OSError):
        return ""


def _school_symbol_image_url(school: School) -> str:
    """Return a sheet-safe school symbol image URL when one is present."""
    image = getattr(school, "symbol_image", None)
    if not image:
        return ""
    try:
        return _single_line(image.url)
    except (ValueError, OSError):
        return ""


def _aspect_image_url(aspect) -> str:
    image = getattr(aspect, "aspect_image", None)
    if not image:
        return ""
    try:
        return _single_line(image.url)
    except (ValueError, OSError):
        return ""


def _image_field_url(instance, field_name: str) -> str:
    image = getattr(instance, field_name, None)
    if not image:
        return ""
    try:
        return _single_line(image.url)
    except (ValueError, OSError):
        return ""


def _serialize_character_item_rune_specs(character_item: CharacterItem) -> list[dict[str, object]]:
    """Return one frontend-friendly slot list with specialization and crafter level."""
    active_item_runes = [item_rune for item_rune in character_item.item_runes.all() if item_rune.is_active]
    rune_specs = list(character_item.rune_specs.all())
    spec_lookup = {
        (spec.rune_id, spec.slot): spec.specification
        for spec in rune_specs
    }
    slot_counters: defaultdict[int, int] = defaultdict(int)
    payloads: list[dict[str, object]] = []

    for item_rune in active_item_runes:
        slot_counters[item_rune.rune_id] += 1
        slot = slot_counters[item_rune.rune_id]
        payloads.append(
            {
                "rune_id": item_rune.rune_id,
                "specification": spec_lookup.get((item_rune.rune_id, slot), ""),
                "slot": slot,
                "crafter_level": item_rune.crafter_level,
            }
        )

    if payloads:
        return payloads

    return [
        {
            "rune_id": spec.rune_id,
            "specification": spec.specification,
            "slot": spec.slot,
            "crafter_level": 0,
        }
        for spec in rune_specs
    ]


def _collect_rune_rows(*, item: Item, character_item: CharacterItem | None = None) -> list[dict[str, str]]:
    """Return combined visible rune rows for tooltips, including specification text."""
    rows: list[dict[str, str]] = []
    if character_item is not None:
        item_runes = list(character_item.item_runes.all())
        if item_runes:
            for item_rune in item_runes:
                if not item_rune.is_active:
                    continue
                level_label = (
                    f" (Waffenmeister {item_rune.crafter_level})"
                    if item_rune.rune.is_level_scaled
                    else ""
                )
                rows.append(
                    {
                        "name": f"{item_rune.rune.name}{level_label}",
                        "description": _rune_card_description(item_rune.rune),
                        "inline_description": _rune_inline_description(item_rune.rune),
                        "image": _rune_image_url(item_rune.rune),
                    }
                )
            return rows

        specs = list(character_item.rune_specs.all())
        if specs:
            for spec in specs:
                display_name = spec.rune.name
                if spec.specification:
                    display_name = f"{spec.rune.name}: {spec.specification}"
                rows.append(
                    {
                        "name": display_name,
                        "description": _rune_card_description(spec.rune),
                        "inline_description": _rune_inline_description(spec.rune),
                        "image": _rune_image_url(spec.rune),
                    }
                )
            return rows

        for rune in character_item.runes.all():
            rows.append(
                {
                    "name": rune.name,
                    "description": _rune_card_description(rune),
                    "inline_description": _rune_inline_description(rune),
                    "image": _rune_image_url(rune),
                }
            )
        return rows

    seen_base_ids: set[int] = set()
    for rune in item.runes.all():
        if rune.id not in seen_base_ids:
            seen_base_ids.add(rune.id)
            rows.append(
                {
                    "name": rune.name,
                    "description": _rune_card_description(rune),
                    "inline_description": _rune_inline_description(rune),
                    "image": _rune_image_url(rune),
                }
            )
    return rows


def _character_item_has_visible_runes(*, item: Item, character_item: CharacterItem | None = None) -> bool:
    """Return whether one item currently exposes any visible runes in the UI."""
    return bool(_collect_rune_rows(item=item, character_item=character_item))


def _rune_inline_description(rune: Rune) -> str:
    """Prefer a rune's short description for inline item-card displays."""
    short_description = str(getattr(rune, "short_description", "") or "").strip()
    if short_description:
        return short_description
    return str(rune.description or "").strip()


def _rune_card_description(rune: Rune) -> str:
    """Return the full rune description for standalone rune cards."""
    return str(rune.description or "").strip()


def _serialize_item_semantic_effect_payload(
    effect: ItemSemanticEffect | CharacterItemSemanticEffect,
    *,
    invested_cp: int | None = None,
    character_race_id: int | None = None,
    character_school_ids: set[int] | None = None,
) -> dict[str, object]:
    """Return one frontend-friendly payload for an item semantic effect."""
    metadata = dict(effect.metadata or {})
    condition_races = list(effect.condition_races.all())
    condition_race_ids = [int(race.id) for race in condition_races]
    condition_race_labels = [str(race.name) for race in condition_races if str(race.name).strip()]
    race_condition_matches = (
        not condition_race_ids
        or (character_race_id is not None and int(character_race_id) in condition_race_ids)
    )
    condition_schools = list(effect.condition_schools.all())
    condition_school_ids = [int(school.id) for school in condition_schools]
    condition_school_labels = [
        str(school.name)
        for school in condition_schools
        if str(school.name).strip()
    ]

    school_condition_matches = (
        not condition_school_ids
        or bool(
            set(character_school_ids or set()).intersection(condition_school_ids)
        )
    )
    condition_matches = (
        race_condition_matches
        and school_condition_matches
    )
    target_domain = str(effect.target_domain or "")
    target_key = str(effect.target_key or "")
    base_item_effect_id = None
    try:
        base_item_effect_id = int(metadata.get("base_item_effect_id"))
    except (TypeError, ValueError):
        base_item_effect_id = None
    if target_domain == "metadata" and target_key == "rules_text":
        text = str(effect.rules_text or effect.notes or "")
        resolved_invested_cp = int((effect.item_invested_cp() if invested_cp is None else invested_cp) or 0)
        return {
            "target_kind": TEXT_TARGET_KIND,
            "value": 0,
            "effect_description": "",
            "rules_text": text,
            "invested_cp": resolved_invested_cp,
            "target_display": "",
            "display_order": int(effect.sort_order or 0),
            "operator": str(effect.operator or ""),
            "scale_source": "",
            "scale_divisor": "",
            "active_flag": bool(effect.active_flag),
            "toggleable": bool(getattr(effect, "toggleable", False)),
            "toggle_state_inverted": bool(getattr(effect, "toggle_state_inverted", False)),
            "display_group": int(effect.display_group) if effect.display_group is not None else None,
            "display_group_append": bool(getattr(effect, "display_group_append", False)),
            "semantic_effect_source": "character_item" if isinstance(effect, CharacterItemSemanticEffect) else "item",
            "semantic_effect_ids": [int(effect.pk)] if effect.pk else [],
            "base_item_effect_id": base_item_effect_id,
            "race_condition_matches": race_condition_matches,
            "condition_race_labels": condition_race_labels,
            "condition_school_labels": condition_school_labels,
            "inactive_due_to_race": bool(
                condition_race_ids and not race_condition_matches
            ),
            "inactive_due_to_school": bool(
                condition_school_ids and not school_condition_matches
            ),
        }
    try:
        raw_value = effect._coerce_scalar(effect.value)
        value = Decimal(str(raw_value or 0))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal("0")
    if str(effect.operator or "") == "flat_sub":
        value *= -1

    resolved_invested_cp = int((effect.item_invested_cp() if invested_cp is None else invested_cp) or 0)
    effective_value = value
    if str(effect.scale_source or "") == "item_invested_cp":
        divisor = int(effect.scale_divisor or 1)
        effective_value = value * (resolved_invested_cp // max(1, divisor))

    payload: dict[str, object] = {
        "target_kind": metadata.get("ui_target_kind") or metadata.get("legacy_target_kind") or target_domain,
        "value": format(value, "f"),
        "effective_value": format(effective_value, "f"),
        "effect_description": str(metadata.get("condition_text") or effect.notes or ""),
        "rules_text": str(effect.rules_text or ""),
        "invested_cp": resolved_invested_cp,
        "target_display": "",
        "display_order": int(effect.sort_order or 0),
        "operator": str(effect.operator or ""),
        "scale_source": str(effect.scale_source or ""),
        "scale_divisor": int(effect.scale_divisor or 0) if effect.scale_divisor else "",
        "active_flag": bool(effect.active_flag),
        "toggleable": bool(getattr(effect, "toggleable", False)),
        "toggle_state_inverted": bool(getattr(effect, "toggle_state_inverted", False)),
        "display_group": int(effect.display_group) if effect.display_group is not None else None,
        "display_group_append": bool(getattr(effect, "display_group_append", False)),
        "semantic_effect_source": "character_item" if isinstance(effect, CharacterItemSemanticEffect) else "item",
        "semantic_effect_ids": [int(effect.pk)] if effect.pk else [],
        "base_item_effect_id": base_item_effect_id,
        "race_condition_matches": race_condition_matches,
        "condition_race_labels": condition_race_labels,
        "condition_school_labels": condition_school_labels,
        "inactive_due_to_race": bool(condition_race_ids and not race_condition_matches),
        "inactive_due_to_school": bool(condition_school_ids and not school_condition_matches),
    }

    if target_domain == "rule_flag":
        payload["target_kind"] = RULE_FLAG_TARGET_KIND
        payload["target_rule_flag"] = target_key
        payload["target_display"] = dict(RULE_FLAG_CHOICES).get(target_key, target_key)
        payload["value"] = 1
    elif target_domain == "attribute":
        payload["target_kind"] = "attribute"
        payload["target_attribute"] = target_key
        payload["target_display"] = dict(ATTRIBUTE_ORDER).get(target_key, target_key)
    elif target_domain == "derived_stat":
        payload["target_kind"] = "stat"
        payload["target_stat"] = target_key
        payload["target_display"] = dict(STAT_SLUG_CHOICES).get(target_key, target_key)
    elif target_domain == "movement":
        payload["target_kind"] = "movement"
        payload["target_movement"] = target_key
        payload["target_display"] = _movement_effect_target_display(target_key)
        payload["value_display"] = _movement_effect_value_display(raw_value, str(effect.operator or ""), target_key)
    elif target_domain == "combat":
        if target_key == MELEE_MANEUVERS:
            payload["target_kind"] = "weapon_maneuver"
            payload["target_display"] = "(Mit der Waffe verknüpfter Skill)"
        elif target_key == WEAPON_DAMAGE:
            payload["target_kind"] = "stat"
            payload["target_stat"] = WEAPON_DAMAGE
            payload["target_display"] = "Schaden"
        elif target_key == WEAPON_DAMAGE_DICE:
            payload["target_kind"] = "weapon_damage_dice"
            payload["target_display"] = "Würfelanzahl"
        elif target_key == WEAPON_MANEUVER_DAMAGE:
            payload["target_kind"] = WEAPON_MANEUVER_DAMAGE
            payload["target_display"] = "Manöver und Schaden"
        else:
            payload["target_kind"] = "stat"
            payload["target_stat"] = target_key
            payload["target_display"] = dict(STAT_SLUG_CHOICES).get(target_key, target_key)
    elif target_domain == "skill":
        payload["target_kind"] = "skill"
        payload["target_skill"] = str(metadata.get("target_skill_id") or "")
        payload["target_display"] = _item_skill_target_display(target_key, metadata)
    elif target_domain == "skill_category":
        payload["target_kind"] = "category"
        payload["target_skill_category"] = str(metadata.get("target_skill_category_id") or "")
        payload["target_display"] = _item_skill_category_target_display(target_key, metadata)
    elif target_domain == "item_category":
        payload["target_kind"] = "item_category"
        payload["target_item_category"] = target_key
        payload["target_display"] = dict(Item.ItemType.choices).get(target_key, target_key)
    elif target_domain == "item":
        payload["target_kind"] = "item"
        payload["target_item"] = str(metadata.get("target_item_id") or target_key)
        payload["target_display"] = target_key
    elif target_domain == "specialization":
        payload["target_kind"] = "specialization"
        payload["target_specialization"] = str(metadata.get("target_specialization_id") or target_key)
        payload["target_display"] = target_key

    if str(metadata.get("ui_target_kind") or "") in {WEAPON_MANEUVER_DAMAGE, WEAPON_MASTERY_BONUS}:
        payload["target_kind"] = str(metadata["ui_target_kind"])
        payload["target_display"] = (
            WEAPON_MASTERY_EFFECT_DESCRIPTION
            if payload["target_kind"] == WEAPON_MASTERY_BONUS
            else "Bonus/Malus auf Manöver und Schaden"
        )
    if target_domain == "movement":
        payload["target_kind"] = "movement"
        payload["target_display"] = _movement_effect_target_display(target_key)
        payload["value_display"] = _movement_effect_value_display(raw_value, str(effect.operator or ""), target_key)
    return payload


def _item_skill_target_display(target_key: str, metadata: dict[str, object] | None = None) -> str:
    """Return the human-facing skill name for an item semantic-effect target."""
    metadata = metadata or {}
    target_skill_id = str(metadata.get("target_skill_id") or "").strip()
    if target_skill_id.isdigit():
        name = Skill.objects.filter(pk=int(target_skill_id)).values_list("name", flat=True).first()
        if name:
            return str(name)

    raw_target = str(target_key or "").strip()
    target_tail = raw_target.rsplit("/", 1)[-1].strip()
    candidates = []
    for candidate in (raw_target, target_tail):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
        if candidate.startswith("skill_"):
            without_prefix = candidate.removeprefix("skill_")
            if without_prefix and without_prefix not in candidates:
                candidates.append(without_prefix)
    if candidates:
        skills_by_slug = {
            slug: name
            for slug, name in Skill.objects.filter(slug__in=candidates).values_list("slug", "name")
        }
        for candidate in candidates:
            if candidate in skills_by_slug:
                return str(skills_by_slug[candidate])
    return target_tail or raw_target


def _item_skill_category_target_display(target_key: str, metadata: dict[str, object] | None = None) -> str:
    """Return the human-facing skill category name for an item semantic-effect target."""
    metadata = metadata or {}
    target_category_id = str(metadata.get("target_skill_category_id") or "").strip()
    if target_category_id.isdigit():
        name = SkillCategory.objects.filter(pk=int(target_category_id)).values_list("name", flat=True).first()
        if name:
            return str(name)

    raw_target = str(target_key or "").strip()
    candidates = []
    for candidate in (raw_target, raw_target.rsplit("/", 1)[-1].strip()):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    if candidates:
        categories_by_slug = {
            slug: name
            for slug, name in SkillCategory.objects.filter(slug__in=candidates).values_list("slug", "name")
        }
        for candidate in candidates:
            if candidate in categories_by_slug:
                return str(categories_by_slug[candidate])
    return raw_target.rsplit("/", 1)[-1].strip() or raw_target


def _movement_effect_target_display(target_key: str) -> str:
    return {
        "ground": "Laufen",
        "ground_combat": "Laufen Kampf",
        "ground_march": "Laufen Marsch",
        "ground_sprint": "Laufen Sprint",
        "swim": "Schwimmen",
        "swim_all": "Schwimmen",
        "swim_combat": "Schwimmen Kampf",
        "swim_march": "Schwimmen Marsch",
        "swim_sprint": "Schwimmen Sprint",
        "fly": "Fliegen",
        "fly_combat": "Fliegen Kampf",
        "fly_march": "Fliegen Marsch",
        "fly_sprint": "Fliegen Sprint",
    }.get(str(target_key or ""), str(target_key or "Bewegung"))


def _movement_effect_values(raw_value: object, target_key: str) -> list[object]:
    raw_value = _coerce_movement_effect_value(raw_value)
    if isinstance(raw_value, (list, tuple)):
        return list(raw_value[:3])
    if isinstance(raw_value, dict):
        aliases = (
            ("combat", ("combat", "ground_combat", "swim_combat", "fly_combat")),
            ("march", ("march", "ground_march", "swim_march", "fly_march")),
            ("sprint", ("sprint", "ground_sprint", "swim_sprint", "fly_sprint")),
        )
        values = []
        for alias, keys in aliases:
            value = raw_value.get(alias)
            if value is None:
                value = next((raw_value.get(key) for key in keys if raw_value.get(key) is not None), None)
            if value is not None:
                values.append(value)
        return values
    if target_key in {"ground", "swim", "swim_all", "fly"}:
        return [raw_value, raw_value, raw_value]
    return [raw_value]


def _coerce_movement_effect_value(raw_value: object) -> object:
    if not isinstance(raw_value, str):
        return raw_value
    text = raw_value.strip()
    if not text:
        return raw_value
    try:
        return json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    if text.startswith("[") and text.endswith("}"):
        try:
            return json.loads(f"{text[:-1]}]")
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if text.startswith("[") and text.endswith("]"):
        parts = [part.strip() for part in text[1:-1].split(",")]
        if len(parts) == 3:
            try:
                return [float(part.replace(",", ".")) for part in parts]
            except (TypeError, ValueError):
                pass
    return raw_value


def _movement_effect_value_display(raw_value: object, operator: str, target_key: str) -> str:
    values = _movement_effect_values(raw_value, target_key)
    if not values:
        return _movement_effect_target_display(target_key)

    def _format_value(value: object) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if operator == "multiply":
            return f"x{format_compact_number(number)}"
        if operator == "override":
            return format_compact_number(number)
        signed = -abs(number) if operator == "flat_sub" else number
        sign = "+" if signed >= 0 else "-"
        return f"{sign}{format_compact_number(abs(signed))}"

    return f"{_movement_effect_target_display(target_key)}: {' / '.join(_format_value(value) for value in values)}"


def _collapse_weapon_mastery_bonus_payloads(modifier_payloads: list[dict[str, object]]) -> list[dict[str, object]]:
    """Merge persisted maneuver/damage pairs back into one Waffenmeister row for the editor UI."""
    collapsed_payloads: list[dict[str, object]] = []
    consumed_indices: set[int] = set()
    for index, payload in enumerate(modifier_payloads):
        if index in consumed_indices:
            continue
        if str(payload.get("target_kind") or "") != "weapon_maneuver":
            collapsed_payloads.append(payload)
            continue
        payload_value = int(payload.get("value", 0) or 0)
        payload_effective_value = int(payload.get("effective_value", payload_value) or 0)
        payload_description = str(payload.get("effect_description") or "").strip()
        payload_rules_text = str(payload.get("rules_text") or "").strip()
        payload_scale_source = str(payload.get("scale_source") or "").strip()
        payload_scale_divisor = payload.get("scale_divisor") or ""
        payload_active_flag = bool(payload.get("active_flag", True))
        payload_toggleable = bool(payload.get("toggleable", False))
        payload_toggle_state_inverted = bool(payload.get("toggle_state_inverted", False))
        payload_inactive_due_to_race = bool(payload.get("inactive_due_to_race", False))
        payload_inactive_due_to_school = bool(payload.get("inactive_due_to_school", False))
        matching_index = None
        for candidate_index in range(index + 1, len(modifier_payloads)):
            if candidate_index in consumed_indices:
                continue
            candidate = modifier_payloads[candidate_index]
            if str(candidate.get("target_kind") or "") != "stat":
                continue
            if str(candidate.get("target_stat") or "") != WEAPON_DAMAGE:
                continue
            if int(candidate.get("value", 0) or 0) != payload_value:
                continue
            if int(candidate.get("effective_value", payload_value) or 0) != payload_effective_value:
                continue
            if str(candidate.get("effect_description") or "").strip() != payload_description:
                continue
            if str(candidate.get("rules_text") or "").strip() != payload_rules_text:
                continue
            if str(candidate.get("scale_source") or "").strip() != payload_scale_source:
                continue
            if (candidate.get("scale_divisor") or "") != payload_scale_divisor:
                continue
            if bool(candidate.get("active_flag", True)) != payload_active_flag:
                continue
            if bool(candidate.get("toggleable", False)) != payload_toggleable:
                continue
            if bool(candidate.get("toggle_state_inverted", False)) != payload_toggle_state_inverted:
                continue
            if bool(candidate.get("inactive_due_to_race", False)) != payload_inactive_due_to_race:
                continue
            if bool(candidate.get("inactive_due_to_school", False)) != payload_inactive_due_to_school:
                continue
            matching_index = candidate_index
            break
        if matching_index is None:
            collapsed_payloads.append(payload)
            continue
        consumed_indices.add(matching_index)
        collapsed_target_kind = (
            WEAPON_MASTERY_BONUS
            if payload_description == WEAPON_MASTERY_EFFECT_DESCRIPTION
            else WEAPON_MANEUVER_DAMAGE
        )
        collapsed_target_display = (
            WEAPON_MASTERY_EFFECT_DESCRIPTION
            if collapsed_target_kind == WEAPON_MASTERY_BONUS
            else "Bonus/Malus auf Manöver und Schaden"
        )
        collapsed_payloads.append(
            {
                "target_kind": collapsed_target_kind,
                "value": payload_value,
                "effective_value": payload_effective_value,
                "effect_description": payload_description,
                "rules_text": payload_rules_text,
                "target_display": collapsed_target_display,
                "display_order": int(payload.get("display_order", 0) or 0),
                "scale_source": payload_scale_source,
                "scale_divisor": payload_scale_divisor,
                "active_flag": payload_active_flag,
                "toggleable": payload_toggleable,
                "toggle_state_inverted": payload_toggle_state_inverted,
                "inactive_due_to_race": payload_inactive_due_to_race,
                "inactive_due_to_school": payload_inactive_due_to_school,
                "condition_race_labels": list(
                    dict.fromkeys(
                        [
                            *(payload.get("condition_race_labels") or []),
                            *(modifier_payloads[matching_index].get("condition_race_labels") or []),
                        ]
                    )
                ),
                "condition_school_labels": list(
                    dict.fromkeys(
                        [
                            *(payload.get("condition_school_labels") or []),
                            *(modifier_payloads[matching_index].get("condition_school_labels") or []),
                        ]
                    )
                ),
                "display_group": payload.get("display_group"),
                "display_group_append": bool(payload.get("display_group_append", False)),
                "semantic_effect_source": str(payload.get("semantic_effect_source") or ""),
                "semantic_effect_ids": [
                    int(value)
                    for value in [
                        *(payload.get("semantic_effect_ids") or []),
                        *(modifier_payloads[matching_index].get("semantic_effect_ids") or []),
                    ]
                    if str(value).isdigit()
                ],
                "character_item_id": payload.get("character_item_id") or modifier_payloads[matching_index].get("character_item_id"),
            }
        )
    return collapsed_payloads


def _merge_magic_effect_payloads(
    *, effect_summary: str, modifier_payloads: list[dict[str, object]]
) -> tuple[str, list[dict[str, object]]]:
    """Combine persisted numeric modifiers with text-only effects stored in the summary field."""
    visible_summary, text_payloads = unpack_magic_effect_summary(effect_summary)
    merged_payloads = [*modifier_payloads, *text_payloads]
    merged_payloads.sort(key=lambda payload: (int(payload.get("display_order") or 0), str(payload.get("target_kind") or "")))
    return visible_summary, merged_payloads


def _character_item_effect_summary_for_view(
    character_item: CharacterItem,
    *,
    include_controls: bool = False,
    sl_effect_group_id: int | None = None,
) -> str:
    """Return legacy effect summary only where it is allowed for this viewer path."""
    if (
        (
            item_identification_initialized(character_item)
            or character_item.effect_identifications.exists()
        )
        and not include_controls
        and sl_effect_group_id is None
    ):
        return ""
    return character_item.magic_effect_summary or ""


def _tooltip_hidden_fields(character_item: CharacterItem) -> str:
    display = resolve_character_item_display(character_item, None, preview_player=True)
    return ",".join(sorted(display.hidden_field_keys))


def _format_magic_rule_effect_line(
    rules_text: str,
    value_display: str,
    value_only_display: str,
    *,
    invested_cp: object = "",
    operator: str = "",
    raw_value: object = None,
) -> str:
    """Format item rules_text as an inline prefix around the calculated effect."""
    text = _single_line(rules_text)

    if "[[prozent]]" in text and operator == "multiply":
        try:
            decimal_value = Decimal(str(raw_value))
            percent_value = (decimal_value - Decimal("1")) * Decimal("100")
            formatted_percent = format_compact_number(percent_value).replace(".", ",")

            if percent_value > 0:
                formatted_percent = f"+{formatted_percent}"

            value_display = (
                f"{str(value_display).split(' × ', 1)[0]} "
                f"{formatted_percent} %"
            )
            value_only_display = f"{formatted_percent} %"

        except (InvalidOperation, TypeError, ValueError):
            pass

    text = _strip_semantic_rule_markers(text)

    if not text:
        return ""

    invested_cp_text = ""
    try:
        invested_cp_text = str(int(invested_cp))
    except (TypeError, ValueError):
        invested_cp_text = ""

    if text.startswith("|"):
        closing_index = text.find("|", 1)

        if closing_index > 1:
            label = (
                text[1:closing_index]
                .replace("@", invested_cp_text)
                .strip()
            )
            suffix = text[closing_index + 1:].strip()

            if label:
                effect_text = value_display

                if suffix:
                    effect_text = f"{effect_text} {suffix}"

                return f"**{label}** · {effect_text}"

    return f"{text} - {value_display}"


def _magic_pipe_parts(rules_text: str, *, invested_cp: object = "") -> tuple[str, str]:
    """Return the optional pipe label and suffix from magic effect text."""
    text = _single_line(rules_text)
    if not text.startswith("|"):
        return "", ""
    closing_index = text.find("|", 1)
    if closing_index <= 1:
        return "", ""
    invested_cp_text = ""
    try:
        invested_cp_text = str(int(invested_cp))
    except (TypeError, ValueError):
        invested_cp_text = ""
    label = text[1:closing_index].replace("@", invested_cp_text).strip()
    suffix = text[closing_index + 1:].strip()
    return label, suffix


def _format_magic_text_effect_line(rules_text: str, *, invested_cp: object = "") -> str:
    """Format text-only item rules_text with the same pipe-label marker."""
    text = _single_line(rules_text)
    if not text:
        return ""
    invested_cp_text = ""
    try:
        invested_cp_text = str(int(invested_cp))
    except (TypeError, ValueError):
        invested_cp_text = ""
    if text.startswith("|"):
        closing_index = text.find("|", 1)
        if closing_index > 1:
            label = text[1:closing_index].replace("@", invested_cp_text).strip()
            suffix = text[closing_index + 1:].strip()
            if label and suffix:
                return f"**{label}** · {suffix}"
            if label:
                return f"**{label}**"
    return text


def _build_character_item_magic_tooltip_rows(
    *,
    effect_summary: str,
    modifier_payloads:
        list[dict[str, object]],
    include_condition_blocked: bool = False,
) -> list[tuple[str, object]]:
    """Return tooltip rows for magic effects stored on one owned item."""
    display_entries: list[dict[str, object]] = []
    numeric_effects: OrderedDict[tuple[object, ...], dict[str, object]] = OrderedDict()
    summary_line, merged_payloads = _merge_magic_effect_payloads(
        effect_summary=effect_summary,
        modifier_payloads=modifier_payloads,
    )
    if not include_condition_blocked:
        merged_payloads = [
            payload
            for payload in merged_payloads
            if not payload.get("inactive_due_to_race")
            and not payload.get("inactive_due_to_school")
        ]
    summary_line = _single_line(summary_line)
    if summary_line:
        display_entries.append({"line": summary_line, "payload": {}})

    def toggle_marker_for(entry: dict[str, object]) -> str:
        if not entry.get("toggleable"):
            return ""
        character_item_id = entry.get("character_item_id")
        source = str(entry.get("semantic_effect_source") or "")
        ids = ",".join(str(value) for value in (entry.get("semantic_effect_ids") or []) if str(value).isdigit())
        if not character_item_id or source not in {"item", "character_item"} or not ids:
            return ""
        url = reverse("toggle_character_item_semantic_effects", args=[int(character_item_id)])
        active = bool(entry.get("active_flag", True))
        inverted = bool(entry.get("toggle_state_inverted", False))
        display_active = inverted != active
        return f"[[EFFECTTOGGLE:{url};{source};{ids};{'1' if display_active else '0'};{'1' if inverted else '0'}]] "

    def identification_marker_for(entry: dict[str, object]) -> str:
        url = str(entry.get("effect_identification_url") or "")
        source = str(entry.get("semantic_effect_source") or "")
        ids = ",".join(str(value) for value in (entry.get("semantic_effect_ids") or []) if str(value).isdigit())
        if not url or source not in {"item", "character_item"} or not ids:
            return ""
        identified = bool(entry.get("identified_for_players", True))
        return f"[[EFFECTIDENTIFY:{url};{source};{ids};{'1' if identified else '0'}]] "

    def display_line_for(entry: dict[str, object], line: str) -> str:
        if entry.get("inactive_due_to_race") or entry.get("inactive_due_to_school"):
            return f"[[INACTIVERACE:{line}]]"
        return line

    def add_display_entry(
        entry: dict[str, object],
        line: str,
        *,
        group_title: str = "",
        group_effect: str = "",
        group_suffix: str = "",
        group_condition: str = "",
    ) -> None:
        display_entries.append(
            {
                "line": display_line_for(entry, line),
                "payload": dict(entry),
                "group_title": group_title,
                "group_effect": group_effect,
                "group_suffix": group_suffix,
                "group_condition": group_condition,
            }
        )

    def grouped_toggle_payload(entry: dict[str, object], associated_entries: list[dict[str, object]]) -> dict[str, object]:
        candidates = [entry, *associated_entries]
        payload = next(
            (
                dict(candidate.get("payload") or {})
                for candidate in candidates
                if dict(candidate.get("payload") or {}).get("toggleable")
            ),
            dict(entry.get("payload") or {}),
        )
        if not payload.get("toggleable"):
            return payload
        base_ids: list[int] = []
        for candidate in candidates:
            candidate_payload = dict(candidate.get("payload") or {})
            if not candidate_payload.get("toggleable"):
                continue
            if str(candidate_payload.get("semantic_effect_source") or "") == "item":
                raw_ids = candidate_payload.get("semantic_effect_ids") or []
            elif candidate_payload.get("base_item_effect_id"):
                raw_ids = [candidate_payload.get("base_item_effect_id")]
            else:
                raw_ids = []
            for raw_id in raw_ids:
                if str(raw_id).isdigit() and int(raw_id) not in base_ids:
                    base_ids.append(int(raw_id))
        if base_ids:
            payload["semantic_effect_source"] = "item"
            payload["semantic_effect_ids"] = base_ids
            return payload
        source = str(payload.get("semantic_effect_source") or "")
        ids: list[int] = []
        for candidate in candidates:
            candidate_payload = dict(candidate.get("payload") or {})
            if not candidate_payload.get("toggleable"):
                continue
            if str(candidate_payload.get("semantic_effect_source") or "") != source:
                continue
            for raw_id in candidate_payload.get("semantic_effect_ids") or []:
                if str(raw_id).isdigit() and int(raw_id) not in ids:
                    ids.append(int(raw_id))
        if ids:
            payload["semantic_effect_ids"] = ids
        return payload

    def leading_effect_markers(line: str) -> tuple[str, str]:
        markers: list[str] = []
        visible_line = str(line)
        while True:
            if not (
                visible_line.startswith("[[EFFECTTOGGLE:")
                or visible_line.startswith("[[EFFECTIDENTIFY:")
            ):
                break
            marker_end = visible_line.find("]]")
            if marker_end == -1:
                break
            markers.append(visible_line[:marker_end + 2])
            visible_line = visible_line[marker_end + 2:].lstrip()
        return " ".join(markers), visible_line

    def _unique_text(values: list[object]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            text = _single_line(str(value or ""))
            if not text:
                continue
            key = " ".join(text.lower().split())
            if key in seen:
                continue
            seen.add(key)
            unique_values.append(text)
        return unique_values

    def _append_unique_tail(line: str, extra: str) -> str:
        normalized_line = " ".join(_single_line(line).lower().split())
        normalized_extra = " ".join(_single_line(extra).lower().split())
        if not normalized_extra or normalized_extra in normalized_line:
            return line
        return f"{line} - {extra}"

    def entry_duplicate_signature(entry: dict[str, object]) -> tuple[str, str, str]:
        effect = " ".join(_single_line(str(entry.get("group_effect") or "")).lower().split())
        suffix = " ".join(_single_line(str(entry.get("group_suffix") or "")).lower().split())
        condition = " ".join(_single_line(str(entry.get("group_condition") or "")).lower().split())
        if not effect:
            return "", "", ""
        return effect, suffix, condition

    def grouped_line_for(group_entries: list[dict[str, object]], main_entry: dict[str, object]) -> str:
        titles = _unique_text([entry.get("group_title") for entry in group_entries])
        effects = _unique_text([entry.get("group_effect") for entry in group_entries])
        suffixes = _unique_text(
            [
                *[entry.get("group_suffix") for entry in group_entries],
            ]
        )
        if titles or effects or suffixes:
            title_section = ", ".join(f"**{title}**" for title in titles)
            detail_sections: list[str] = []
            if effects:
                detail_sections.append(", ".join(effects))
            if suffixes:
                detail_sections.append(" ".join(suffixes))
            if title_section and detail_sections:
                return f"{title_section} · {' '.join(detail_sections)}"
            if title_section:
                return title_section
            return " ".join(detail_sections)
        associated_lines = [
            str(entry["line"])
            for entry in group_entries
            if entry is not main_entry
        ]
        if associated_lines:
            return f"{main_entry['line']}: {', '.join(associated_lines)}"
        return str(main_entry["line"])

    def grouped_effect_lines() -> list[str]:
        lines: list[str] = []
        grouped_entries: OrderedDict[object, list[dict[str, object]]] = OrderedDict()
        consumed_indexes: set[int] = set()
        rendered_groups: set[object] = set()
        grouped_signatures: set[tuple[str, str, str]] = set()
        for index, entry in enumerate(display_entries):
            payload = dict(entry.get("payload") or {})
            group = payload.get("display_group")
            if group in (None, ""):
                continue
            grouped_entries.setdefault(group, []).append({"index": index, **entry})
            signature = entry_duplicate_signature(entry)
            if signature != ("", "", ""):
                grouped_signatures.add(signature)

        for index, entry in enumerate(display_entries):
            if index in consumed_indexes:
                continue
            payload = dict(entry.get("payload") or {})
            group = payload.get("display_group")
            if group in (None, ""):
                signature = entry_duplicate_signature(entry)
                if signature in grouped_signatures:
                    continue
                lines.append(f"{toggle_marker_for(payload)}{identification_marker_for(payload)}{entry['line']}")
                continue
            if group in rendered_groups:
                continue
            group_entries = grouped_entries.get(group, [])
            main_entries = [
                candidate
                for candidate in group_entries
                if not dict(candidate.get("payload") or {}).get("display_group_append")
            ]
            main_entry = main_entries[0] if main_entries else group_entries[0]
            associated_entries = [candidate for candidate in group_entries if candidate is not main_entry]
            for candidate in group_entries:
                consumed_indexes.add(int(candidate["index"]))
            rendered_groups.add(group)
            line = grouped_line_for(group_entries, main_entry)

            group_inactive = any(
                dict(candidate.get("payload") or {}).get("inactive_due_to_race")
                or dict(candidate.get("payload") or {}).get("inactive_due_to_school")
                for candidate in group_entries
            )

            if group_inactive:
                line = f"[[INACTIVERACE:{line}]]"

            marker_payload = grouped_toggle_payload(main_entry, associated_entries)
            lines.append(f"{toggle_marker_for(marker_payload)}{identification_marker_for(marker_payload)}{line}")
        return lines

    def numeric_value_display(
        entry: dict[str, object],
        value: Decimal,
    ) -> tuple[str, str]:
        target_kind = str(entry["target_kind"])
        target_display = str(entry["target_display"])
        operator = str(entry.get("operator") or "")

        formatted_value = format_compact_number(value).replace(".", ",")
        signed_value = (
            formatted_value
            if formatted_value.startswith("-")
            else f"+{formatted_value}"
        )

        if (
            operator == "override"
            and str(entry.get("target_stat") or "") == DEFENSE_RS
            and value == 0
        ):
            return "", ""

        if target_kind == RULE_FLAG_TARGET_KIND:
            return target_display, target_display

        if target_kind == "weapon_maneuver":
            return (
                f"{signed_value} Manöver",
                f"{signed_value} Manöver",
            )

        if (
            target_kind == "stat"
            and str(entry.get("target_stat") or "") == WEAPON_DAMAGE
        ):
            return (
                f"{signed_value} Schaden",
                f"{signed_value} Schaden",
            )

        if target_kind in {
            WEAPON_MANEUVER_DAMAGE,
            WEAPON_MASTERY_BONUS,
        }:
            return (
                f"{signed_value} / {signed_value}",
                f"{signed_value} / {signed_value}",
            )

        if target_kind == "weapon_damage_dice":
            dice_value = int(value)
            return (
                f"{dice_value:+d} W10",
                f"{dice_value:+d} W10",
            )

        if (
            operator == "override"
            and str(entry.get("target_stat") or "") in {
                ARMOR_ENCUMBRANCE,
                SHIELD_ENCUMBRANCE,
            }
        ):
            return f"Belastung {formatted_value}", formatted_value

        if operator == "multiply":
            return (
                f"{target_display} × {formatted_value}",
                f"× {formatted_value}",
            )

        if operator == "floor_divide":
            return (
                f"{target_display} ÷ {formatted_value}",
                f"÷ {formatted_value}",
            )

        return (
            f"{signed_value} {target_display}",
            signed_value,
        )

    def flush_numeric_effects() -> None:
        for entry in numeric_effects.values():
            value = Decimal(entry["value"])
            effect_description = str(entry["effect_description"])
            rules_text = str(entry["rules_text"])
            invested_cp = entry.get("invested_cp", "")
            value_display, value_only_display = numeric_value_display(entry, value)
            group_title, group_suffix = _magic_pipe_parts(rules_text, invested_cp=invested_cp)
            if not group_title and not group_suffix:
                group_suffix = _single_line(rules_text)
            group_condition = _single_line(effect_description)
            rule_line = _format_magic_rule_effect_line(
                rules_text,
                value_display,
                value_only_display,
                invested_cp=invested_cp,
                operator=str(entry.get("operator") or ""),
                raw_value=value,
            )
            if not value_display and effect_description:
                add_display_entry(entry, effect_description, group_condition=group_condition)
            elif rule_line:
                add_display_entry(
                    entry,
                    rule_line,
                    group_title=group_title,
                    group_effect=value_display,
                    group_suffix=group_suffix,
                    group_condition=group_condition,
                )
            elif effect_description:
                line = f"{effect_description} - {value_display}"
                add_display_entry(entry, line, group_effect=line, group_condition=group_condition)
            else:
                add_display_entry(entry, value_display, group_effect=value_display)

    for payload in merged_payloads:
        if str(payload.get("target_kind") or "") == TEXT_TARGET_KIND:
            flush_numeric_effects()
            numeric_effects.clear()
            effect_description = _format_magic_text_effect_line(
                str(payload.get("rules_text") or ""),
                invested_cp=payload.get("invested_cp", ""),
            )
            if effect_description:
                group_title, group_suffix = _magic_pipe_parts(
                    str(payload.get("rules_text") or ""),
                    invested_cp=payload.get("invested_cp", ""),
                )
                add_display_entry(
                    payload,
                    effect_description,
                    group_title=group_title,
                    group_suffix=group_suffix,
                )
            continue
        if str(payload.get("value_display") or "").strip():
            flush_numeric_effects()
            numeric_effects.clear()
            value_display = _single_line(str(payload.get("value_display") or ""))
            effect_description = _single_line(str(payload.get("effect_description") or ""))
            rules_text = _single_line(str(payload.get("rules_text") or ""))
            group_title, group_suffix = _magic_pipe_parts(rules_text, invested_cp=payload.get("invested_cp", ""))
            if not group_title and not group_suffix:
                group_suffix = _single_line(rules_text)
            group_condition = _single_line(effect_description)
            rule_line = _format_magic_rule_effect_line(
                rules_text,
                value_display,
                value_display,
                invested_cp=payload.get("invested_cp", ""),
            )
            if rule_line:
                add_display_entry(
                    payload,
                    rule_line,
                    group_title=group_title,
                    group_effect=value_display,
                    group_suffix=group_suffix,
                    group_condition=group_condition,
                )
            elif effect_description:
                line = f"{effect_description} - {value_display}"
                add_display_entry(payload, line, group_effect=line, group_condition=group_condition)
            else:
                add_display_entry(payload, value_display, group_effect=value_display)
            continue
        target_display = _single_line(str(payload.get("target_display") or "")) or "Ziel"
        effect_description = _single_line(str(payload.get("effect_description") or ""))
        rules_text = _single_line(str(payload.get("rules_text") or ""))
        invested_cp = payload.get("invested_cp", "")
        try:
            value = Decimal(
                str(payload.get("effective_value", payload.get("value")) or 0)
            )
        except (InvalidOperation, TypeError, ValueError):
            value = Decimal("0")
        target_kind = str(payload.get("target_kind") or "")
        key = (
            target_kind,
            target_display,
            str(payload.get("operator") or ""),
            " ".join(rules_text.replace("@", str(invested_cp)).lower().split()),
            " ".join(effect_description.lower().split()),
            "inactive_due_to_race" if payload.get("inactive_due_to_race") else "active_for_race",
            "inactive_due_to_school" if payload.get("inactive_due_to_school") else "active_for_school",
            "toggleable" if payload.get("toggleable") else "fixed",
            "toggle_inverted" if payload.get("toggle_state_inverted") else "toggle_normal",
            "active_flag" if payload.get("active_flag", True) else "inactive_flag",
            f"display_group:{payload.get('display_group') or ''}",
            "display_group_append" if payload.get("display_group_append") else "display_group_main",
        )
        if key not in numeric_effects:
            numeric_effects[key] = {
                "target_kind": target_kind,
                "target_display": target_display,
                "target_stat": str(payload.get("target_stat") or ""),
                "operator": str(payload.get("operator") or ""),
                "effect_description": effect_description,
                "rules_text": rules_text,
                "invested_cp": invested_cp,
                "value": 0,
                "active_flag": bool(payload.get("active_flag", True)),
                "toggleable": bool(payload.get("toggleable", False)),
                "toggle_state_inverted": bool(payload.get("toggle_state_inverted", False)),
                "display_group": payload.get("display_group"),
                "display_group_append": bool(payload.get("display_group_append", False)),
                "semantic_effect_source": str(payload.get("semantic_effect_source") or ""),
                "semantic_effect_ids": list(payload.get("semantic_effect_ids") or []),
                "character_item_id": payload.get("character_item_id"),
                "effect_identification_url": str(payload.get("effect_identification_url") or ""),
                "identified_for_players": bool(payload.get("identified_for_players", True)),
                "inactive_due_to_race": bool(payload.get("inactive_due_to_race")),
                "inactive_due_to_school": bool(payload.get("inactive_due_to_school")),
                "condition_race_labels": list(payload.get("condition_race_labels") or []),
                "condition_school_labels": list(payload.get("condition_school_labels") or []),
            }
        numeric_effects[key]["value"] = (
            Decimal(str(numeric_effects[key]["value"])) + value
        )
        continue

    def split_effect_column(line: str) -> tuple[str, str]:
        """Move a leading pipe-derived bold label into the left tooltip column."""
        marker, visible_line = leading_effect_markers(str(line))

        if visible_line.startswith("**"):
            if " · " in visible_line:
                title_section, detail = visible_line.split(" · ", 1)

                if title_section.endswith("**"):
                    label = title_section.replace("**", "").strip()
                    detail = f"{marker} {detail}".strip() if marker else detail
                    return label, detail

            elif visible_line.endswith("**"):
                label = visible_line.replace("**", "").strip()
                return label, marker

        if marker:
            visible_line = f"{marker} {visible_line}".strip()

        return "", visible_line

    flush_numeric_effects()
    effect_lines = grouped_effect_lines()

    effect_rows = [
        split_effect_column(line)
        for line in effect_lines
    ]

    effect_label = "Effekte" if len(effect_rows) > 1 else "Effekt"
    rows: list[tuple[str, object]] = []

    for index, (pipe_label, detail) in enumerate(effect_rows):
        if index == 0:
            if pipe_label:
                rows.append((effect_label, "[[EMPTY]]"))
                rows.append((
                    f"**{pipe_label}**",
                    detail or "[[EMPTY]]",
                ))
            else:
                rows.append((
                    effect_label,
                    detail or "[[EMPTY]]",
                ))
            continue

        rows.append((
            f"**{pipe_label}**" if pipe_label else "[[EMPTY]]",
            detail or "[[EMPTY]]",
        ))

    return rows


def _load_character_item_modifier_payloads(
    character_items: list[CharacterItem],
    *,
    include_unidentified: bool = False,
) -> dict[int, list[dict[str, object]]]:
    """Return serialized effective magic-modifier payloads keyed by owned item id."""
    if not character_items:
        return {}
    modifiers_by_character_item_id: dict[int, list[dict[str, object]]] = {}
    item_ids = {int(entry.item_id) for entry in character_items if entry.item_id}
    base_effects_by_item_id: dict[int, list[ItemSemanticEffect]] = {}
    for effect in (
        ItemSemanticEffect.objects
        .filter(item_id__in=item_ids)
        .filter(Q(active_flag=True) | Q(toggleable=True))
        .select_related("item")
        .prefetch_related(
            "condition_races",
            "condition_schools",
        )
        .order_by("item_id", "sort_order", "id")
    ):
        base_effects_by_item_id.setdefault(int(effect.item_id), []).append(effect)
    instance_effects = list(
        CharacterItemSemanticEffect.objects
        .filter(character_item_id__in=[entry.id for entry in character_items])
        .filter(Q(active_flag=True) | Q(toggleable=True))
        .select_related("character_item", "character_item__item", "character_item__owner")
        .prefetch_related(
            "condition_races",
            "condition_schools",
        )
        .order_by("sort_order", "id")
    )
    instance_effects_by_base: dict[tuple[int, int], CharacterItemSemanticEffect] = {}
    standalone_instance_effects_by_character_item_id: dict[int, list[CharacterItemSemanticEffect]] = {}
    for effect in instance_effects:
        character_item_id = int(effect.character_item_id)
        base_id = dict(effect.metadata or {}).get("base_item_effect_id")
        try:
            base_id = int(base_id)
        except (TypeError, ValueError):
            standalone_instance_effects_by_character_item_id.setdefault(character_item_id, []).append(effect)
            continue
        instance_effects_by_base[(character_item_id, base_id)] = effect

    def effects_match_for_display_override(
        base_effect: ItemSemanticEffect,
        instance_effect: CharacterItemSemanticEffect,
    ) -> bool:
        """Treat unlinked instance rows as overrides when they mirror a base row."""
        def comparable_metadata(effect: ItemSemanticEffect | CharacterItemSemanticEffect) -> dict[str, object]:
            ignored_keys = {
                "base_item_effect_id",
                "legacy_target_kind",
                "legacy_target_slug",
                "semantic_effect_key",
                "semantic_effect_label",
                "target_item_id",
                "target_skill_category_id",
                "target_skill_id",
                "target_specialization_id",
                "ui_target_kind",
            }
            return {
                key: value
                for key, value in dict(effect.metadata or {}).items()
                if key not in ignored_keys
            }

        comparable_fields = (
            "target_domain",
            "target_key",
            "operator",
            "mode",
            "value",
            "scale_source",
            "scale_divisor",
            "value_min",
            "value_max",
            "formula",
            "stack_behavior",
            "rules_text",
            "visibility",
            "hidden",
            "sheet_relevant",
            "toggleable",
            "toggle_state_inverted",
            "display_group",
            "display_group_append",
            "priority",
        )
        for field_name in comparable_fields:
            if getattr(base_effect, field_name) != getattr(instance_effect, field_name):
                return False
        return (
            dict(base_effect.scaling or {}) == dict(instance_effect.scaling or {})
            and dict(base_effect.condition_set or {}) == dict(instance_effect.condition_set or {})
            and comparable_metadata(base_effect) == comparable_metadata(instance_effect)
            and list(base_effect.condition_races.order_by("id").values_list("id", flat=True))
            == list(instance_effect.condition_races.order_by("id").values_list("id", flat=True))
        )

    for character_item in character_items:
        character_item_id = int(character_item.id)
        base_effects = base_effects_by_item_id.get(int(character_item.item_id), [])
        merged_effects: list[ItemSemanticEffect | CharacterItemSemanticEffect] = []
        standalone_effects = list(standalone_instance_effects_by_character_item_id.get(character_item_id, []))
        consumed_standalone_effect_ids: set[int] = set()
        if base_effects and not standalone_effects:
            for effect in base_effects:
                linked_override = instance_effects_by_base.get((character_item_id, int(effect.id)))
                if linked_override is not None:
                    merged_effects.append(linked_override)
                    continue
                display_override = next(
                    (
                        candidate
                        for candidate in standalone_effects
                        if int(candidate.id) not in consumed_standalone_effect_ids
                        and effects_match_for_display_override(effect, candidate)
                    ),
                    None,
                )
                if display_override is not None:
                    consumed_standalone_effect_ids.add(int(display_override.id))
                    merged_effects.append(display_override)
                    continue
                merged_effects.append(effect)
        merged_effects.extend(
            effect for effect in standalone_effects if int(effect.id) not in consumed_standalone_effect_ids
        )
        if not merged_effects:
            continue
        character_race_id = character_item.owner.race_id if character_item.owner_id else None

        character_school_ids = (
            set(
                character_item.owner.schools.values_list(
                    "school_id",
                    flat=True,
                )
            )
            if character_item.owner_id
            else set()
        )
        modifiers_by_character_item_id[character_item_id] = []
        for effect in sorted(merged_effects, key=lambda entry: (int(entry.sort_order or 0), int(entry.id or 0))):
            if not include_unidentified and not is_character_item_effect_identified(character_item, effect):
                continue
            payload = _serialize_item_semantic_effect_payload(
                effect,
                invested_cp=character_item.invested_cp,
                character_race_id=character_race_id,
                character_school_ids=character_school_ids,
            )
            payload["character_item_id"] = character_item_id
            modifiers_by_character_item_id[character_item_id].append(payload)
    for character_item_id, payloads in list(modifiers_by_character_item_id.items()):
        modifiers_by_character_item_id[character_item_id] = _collapse_weapon_mastery_bonus_payloads(payloads)
    return modifiers_by_character_item_id


def _build_character_item_rune_tooltip_rows(
    *, item: Item, character_item: CharacterItem | None = None
) -> list[tuple[str, object]]:
    """Return tooltip rows for visible runes on one item."""
    rune_lines: list[str] = []
    for row in _collect_rune_rows(item=item, character_item=character_item):
        rune_name = _single_line(str(row.get("name") or ""))
        rune_description = _single_line(str(row.get("inline_description") or row.get("description") or ""))
        rune_image = _single_line(str(row.get("image") or ""))
        if not rune_name:
            continue
        rune_lines.append(f"[[RUNEINLINE:{rune_name}|{rune_description}|{rune_image}]]")
    if not rune_lines:
        return []
    return [
        ("Runen" if index == 0 else "[[EMPTY]]", line)
        for index, line in enumerate(rune_lines)
    ]


def _build_weapon_symbol_tooltip_rows(item_engine: ItemEngine) -> list[tuple[str, object]]:
    """Return item-card rows for weapon symbol effects."""
    effect_lines = item_engine.get_weapon_effect_descriptions()
    if not effect_lines:
        return []
    return [
        ("[[WEAPON_SYMBOL]]", line)
        for line in effect_lines
    ]


def _format_item_tooltip(
    *,
    description: str,
    quality_label: str | None = None,
    quality_color: str | None = None,
    status_label: str | None = None,
    status_color: str | None = None,
    detail_rows: list[tuple[str, object]] | None = None,
) -> str:
    """Return the tooltip text used by item-related template rows."""
    table_rows: list[tuple[str, object]] = list(detail_rows or [])
    if status_label and status_color:
        table_rows.insert(0, ("Status", f"[[STATUS:{status_label}|{status_color}]]"))

    parts: list[str] = []
    table = _build_tooltip_table(table_rows)
    if table:
        parts.append(table)

    description_block = str(description or "").strip()
    if description_block:
        parts.append(description_block)
    return "\n\n".join(parts)


def _escape_tooltip_table_cell(value: object) -> str:
    """Escape tooltip table separators in markdown-style cells."""
    return str(value if value not in (None, "") else "-").replace("|", "\\|")


def _build_tooltip_table(rows: list[tuple[str, object]]) -> str:
    """Return a compact markdown table for the tooltip renderer."""
    if not rows:
        return ""
    lines = [
        "| Wert | Details |",
        "| --- | --- |",
    ]
    for label, value in rows:
        lines.append(
            f"| {_escape_tooltip_table_cell(label)} | {_escape_tooltip_table_cell(value)} |"
        )
    return "\n".join(lines)


def _build_core_stat_tooltip(
    rows: list[dict[str, object]],
    *,
    conditional_modifiers: list[str] | None = None,
) -> str:
    """Return one compact two-column table for a derived combat stat."""
    lines = [
        "| Grundlage | Wert |",
        "| --- | ---: |",
    ]
    for row in rows:
        if row.get("tone") != "total" and _is_zeroish_tooltip_value(row.get("value")):
            continue
        label = str(row.get("label", "") or "-")
        value = str(row.get("value", "") or "0")
        source = str(row.get("source", "") or "")
        if source:
            label = f"{label} [[SUB:{source}]]"
        if row.get("tone") == "total":
            label = f"**{label}**"
            value = f"**{value}**"
        lines.append(
            f"| {_escape_tooltip_table_cell(label)} | {_escape_tooltip_table_cell(f'`{value}`')} |"
        )
    if conditional_modifiers:
        lines.append("")
        lines.append("| Bedingte Modifikatoren |")
        lines.append("| --- |")
        for entry in conditional_modifiers:
            lines.append(f"| {_escape_tooltip_table_cell(entry)} |")
    return "\n".join(lines)


def _is_zeroish_tooltip_value(value: object) -> bool:
    """Return whether one tooltip value represents a visible zero contribution."""
    text = str(value if value is not None else "").strip().replace("`", "")
    return text in {"", "0", "+0", "-0", "0.0", "+0.0", "-0.0"}


def _format_item_weight(value: object) -> str:
    """Return ItemCard weight text with compact German decimal formatting."""
    try:
        value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        pass
    text = format_compact_number(value).replace(".", ",")
    return f"{text} kg"


def _has_visible_item_weight(value: object) -> bool:
    """Return whether an ItemCard should include the weight row."""
    if value in (None, ""):
        return False
    try:
        return Decimal(str(value)) != 0
    except (InvalidOperation, ValueError):
        return True


def _strip_item_card_effect_markers(value: object) -> tuple[str, bool]:
    """Return display text and whether the tooltip row was condition-blocked."""
    text = str(value).replace("[[EMPTY]]", "").strip()
    while text.startswith("[[EFFECTTOGGLE:") or text.startswith("[[EFFECTIDENTIFY:"):
        marker_end = text.find("]]")
        if marker_end == -1:
            break
        text = text[marker_end + 2:].lstrip()

    inactive = False
    if text.startswith("[[INACTIVERACE:") and text.endswith("]]"):
        inactive = True
        text = text[len("[[INACTIVERACE:"):-2].strip()

    return text, inactive


def _item_card_condition_notes(
    modifier_payloads: list[dict[str, object]],
) -> list[str]:
    """Return readable condition notes for condition-blocked effect rows."""
    notes: list[str] = []
    for payload in modifier_payloads:
        labels: list[str] = []
        if payload.get("inactive_due_to_race"):
            labels.extend(str(value) for value in payload.get("condition_race_labels") or [])
        if payload.get("inactive_due_to_school"):
            labels.extend(str(value) for value in payload.get("condition_school_labels") or [])
        labels = [label.strip() for label in labels if label.strip()]
        if labels:
            notes.append("Bedingung: " + ", ".join(dict.fromkeys(labels)))
    return notes


def _shared_item_card_effect_rows(
    effect_rows: list[tuple[str, object]],
    *,
    condition_notes: list[str] | None = None,
) -> list[dict[str, object]]:
    """Translate tooltip-internal effect rows into safe shared-card rows."""
    safe_rows: list[dict[str, object]] = []
    remaining_condition_notes = list(condition_notes or [])
    for label, value in effect_rows:
        if (
            str(label) in {"Effekt", "Effekte", "[[EMPTY]]"}
            and str(value).strip() in {"", "[[EMPTY]]"}
        ):
            continue

        label_text = "" if str(label) in {"Effekt", "Effekte", "[[EMPTY]]"} else str(label)
        value_text, inactive = _strip_item_card_effect_markers(value)
        label_text, label_inactive = _strip_item_card_effect_markers(label_text)
        inactive = inactive or label_inactive

        if not label_text and value_text.startswith("**"):
            for separator in (" · ", " Â· "):
                if separator in value_text:
                    title, detail = value_text.split(separator, 1)
                    if title.endswith("**"):
                        label_text = title
                        value_text = detail
                    break

        safe_rows.append(
            {
                "label": label_text.replace("**", "").strip(),
                "value": value_text.strip(),
                "inactive": inactive,
                "condition_note": remaining_condition_notes.pop(0) if inactive and remaining_condition_notes else "",
            }
        )
    return safe_rows


def _build_alchemical_brew_requirement_line(
    item: Item,
) -> str:
    """Return the generated crafting line for an alchemical brew."""
    brew = (
        AlchemicalBrewStats.objects
        .filter(item_id=item.pk)
        .first()
    )

    if brew is None:
        return ""

    parts: list[str] = []

    if brew.ingredient_cost_gm is not None:
        parts.append(
            f"{brew.ingredient_cost_gm} GM"
        )

    if (
        brew.craft_time_amount is not None
        and brew.craft_time_unit
    ):
        time_units = {
            "hours": ("Stunde", "Stunden"),
            "days": ("Tag", "Tage"),
            "weeks": ("Woche", "Wochen"),
            "months": ("Monat", "Monate"),
        }

        singular, plural = time_units.get(
            brew.craft_time_unit,
            (
                brew.get_craft_time_unit_display(),
                brew.get_craft_time_unit_display(),
            ),
        )

        unit = (
            singular
            if brew.craft_time_amount == 1
            else plural
        )

        parts.append(
            f"Zeitaufwand: "
            f"{brew.craft_time_amount} {unit}"
        )

    requirements = list(
        brew.requirements
        .select_related(
            "skill",
            "school",
            "aspect",
        )
        .order_by(
            "sort_order",
            "id",
        )
    )

    def requirement_text(requirement) -> str:
        if requirement.skill_id:
            name = requirement.skill.name
        elif requirement.school_id:
            name = requirement.school.name
        else:
            name = requirement.aspect.name

        return (
            f"{name} "
            f"{requirement.required_level}"
        )

    alternative_groups = defaultdict(list)

    for requirement in requirements:
        if requirement.alternative_group is not None:
            alternative_groups[
                requirement.alternative_group
            ].append(requirement)

    rendered_groups = set()

    for requirement in requirements:
        group = requirement.alternative_group

        if group is None:
            parts.append(
                requirement_text(requirement)
            )
            continue

        if group in rendered_groups:
            continue

        rendered_groups.add(group)

        alternatives = alternative_groups[group]

        if len(alternatives) == 1:
            parts.append(
                requirement_text(
                    alternatives[0]
                )
            )
            continue

        parts.append(
            " oder ".join(
                requirement_text(entry)
                for entry in alternatives
            )
        )

    additional_requirements = str(
        brew.additional_requirements or ""
    ).strip()

    if additional_requirements:
        parts.append(
            additional_requirements
        )

    # MW bewusst ganz am Ende.
    if brew.craft_mw is not None:
        parts.append(
            f"MW: {brew.craft_mw}"
        )

    if not parts:
        return ""

    return (
        "`**Voraussetzungen:** "
        + ", ".join(parts)
        + "`"
    )


def build_character_item_card_context(
    character_item: CharacterItem,
    viewer=None,
    *,
    preview_player: bool = True,
    include_controls: bool = False,
    strength: int | None = None,
    modifier_payloads: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Return the shared resolved item-card context for sheet and GM preview."""
    item = character_item.item
    item_engine = ItemEngine(character_item)
    player_display = resolve_character_item_display(
        character_item,
        viewer,
        preview_player=True,
    )
    display = resolve_character_item_display(
        character_item,
        viewer,
        preview_player=False if include_controls else preview_player,
    )
    quality = quality_payload(item_engine.get_effective_quality())
    stored_modifier_payloads = (
        modifier_payloads
        if modifier_payloads is not None
        else _load_character_item_modifier_payloads(
            [character_item],
            include_unidentified=include_controls,
        ).get(character_item.id, [])
    )
    visible_magic_effect_summary, magic_modifier_payloads = _merge_magic_effect_payloads(
        effect_summary=_character_item_effect_summary_for_view(
            character_item,
            include_controls=include_controls,
        ),
        modifier_payloads=stored_modifier_payloads,
    )
    hidden_field_keys = player_display.hidden_field_keys if include_controls else display.hidden_field_keys

    card_description = str(
        display.description or ""
    ).strip()

    brew_requirement_line = (
        _build_alchemical_brew_requirement_line(
            item
        )
    )

    if brew_requirement_line:
        card_description = "\n\n".join(
            part
            for part in (
                card_description,
                brew_requirement_line,
            )
            if part
        )

    quality_label = "" if "quality" in hidden_field_keys and not include_controls else display.quality_label
    quality_color = "" if "quality" in hidden_field_keys and not include_controls else quality["color"]
    detail_rows = _build_item_tooltip_rows(
        item_engine,
        item,
        strength=strength,
        modifier_payloads=magic_modifier_payloads,
    )
    if "price" in hidden_field_keys and not include_controls:
        detail_rows = [row for row in detail_rows if row[0] != "Kaufpreis"]
    if "weight" in hidden_field_keys and not include_controls:
        detail_rows = [row for row in detail_rows if row[0] != "Gewicht"]
    if "size_class" in hidden_field_keys and not include_controls:
        detail_rows = [row for row in detail_rows if row[0] != "GK"]
    detail_field_keys = {
        "Kaufpreis": "price",
        "Gewicht": "weight",
        "GK": "size_class",
    }
    safe_detail_rows = []
    for label, value in detail_rows:
        label_text = str(label).replace("**", "")
        field_key = detail_field_keys.get(str(label), "")
        value_text = str(value).replace("**", "")
        safe_detail_rows.append(
            {
                "label": label_text,
                "value": value_text,
                "field_key": field_key,
            }
        )
    return {
        "display": display,
        "title": display.name,
        "item_type_label": display.item_type,
        "quality_label": quality_label,
        "subtitle": " - ".join(part for part in [display.item_type, quality_label] if part),
        "image_url": player_display.image_url if include_controls else display.image_url,
        "actual_image_url": display.image_url,
        "accent": quality_color,
        "detail_rows": safe_detail_rows,
        "weapon_symbol_rows": [
            {"label": "", "value": str(value).replace("**", "")}
            for _label, value in _build_weapon_symbol_tooltip_rows(item_engine)
        ],
        "effect_rows": _shared_item_card_effect_rows(
            _build_character_item_magic_tooltip_rows(
                effect_summary=visible_magic_effect_summary,
                modifier_payloads=magic_modifier_payloads,
                include_condition_blocked=include_controls,
            ),
            condition_notes=_item_card_condition_notes(magic_modifier_payloads),
        ),
        "rune_rows": [
            {
                "label": "" if str(label) in {"Rune", "Runen", "[[EMPTY]]"} else str(label).replace("**", ""),
                "value": str(value).replace("[[EMPTY]]", "").strip(),
            }
            for label, value in _build_character_item_rune_tooltip_rows(
                item=item,
                character_item=character_item,
            )
            if not (
                str(label) in {"Rune", "Runen", "[[EMPTY]]"}
                and str(value).strip() in {"", "[[EMPTY]]"}
            )
        ],
        "description": card_description,
        "controls": include_controls,
        "disclosure_rows": [],
        "effect_identification_rows": [],
    }


def _apply_item_semantic_stat_effects(
    base_value: int,
    modifier_payloads: list[dict[str, object]] | None,
    target_stat: str,
) -> int:
    """Apply active item-local semantic effects to a displayed item stat."""
    value = Decimal(base_value)

    for payload in modifier_payloads or []:
        if not payload.get("active_flag", True):
            continue

        if payload.get("inactive_due_to_race"):
            continue

        if payload.get("inactive_due_to_school"):
            continue

        if str(payload.get("target_stat") or "") != target_stat:
            continue

        operator = str(payload.get("operator") or "")

        try:
            effect_value = Decimal(
                str(
                    payload.get(
                        "effective_value",
                        payload.get("value"),
                    )
                    or 0
                )
            )
        except (InvalidOperation, TypeError, ValueError):
            continue

        if operator == "flat_add":
            value += effect_value

        elif operator == "flat_sub":
            value -= effect_value

        elif operator == "multiply":
            value *= effect_value

            rounding_mode = _semantic_rounding_mode(
                str(payload.get("rules_text") or "")
            )

            if rounding_mode == "ceil":
                value = value.to_integral_value(
                    rounding=ROUND_CEILING
                )

            elif rounding_mode == "floor":
                value = value.to_integral_value(
                    rounding=ROUND_FLOOR
                )

        elif operator == "floor_divide":
            if effect_value:
                value //= effect_value

        elif operator == "override":
            value = effect_value

        elif operator == "min_value":
            value = max(value, effect_value)

        elif operator == "max_value":
            value = min(value, effect_value)

    return value


def _build_item_tooltip_rows(
    item_engine: ItemEngine,
    item: Item,
    *,
    strength: int | None = None,
    armor_rs: int | None = None,
    armor_encumbrance: int | None = None,
    shield_encumbrance: int | None = None,
    modifier_payloads: list[dict[str, object]] | None = None,
) -> list[tuple[str, object]]:
    """Return structured item values for inventory-like tooltips."""
    rows: list[tuple[str, object]] = [("Kaufpreis", f"{format_thousands(item_engine.get_price())} KM")]

    weight = item_engine.get_weight()
    if _has_visible_item_weight(weight):
        rows.append(("Gewicht", _format_item_weight(weight)))

    size_class = item_engine.get_size_class()
    if size_class:
        rows.append(("GK", size_class))

    if item.item_type in Item.weapon_item_type_values():
        weapon_stats = item_engine._get_weapon_stats()

        if weapon_stats and weapon_stats.wield_mode == TWO_HANDED:
            two_handed_damage = item_engine.get_two_handed_damage_label()
            if two_handed_damage:
                rows.append(("Schaden", two_handed_damage))
        else:
            rows.append(("Schaden", item_engine.get_one_handed_damage_label()))

            two_handed_damage = item_engine.get_two_handed_damage_label()
            if two_handed_damage:
                rows.append(("2H Schaden", two_handed_damage))

        base_range_label = item_engine.get_weapon_range_label()
        range_label = item_engine.get_weapon_range_label(strength=strength)
        if range_label:
            if strength is not None and base_range_label and base_range_label != range_label:
                range_label = f"{range_label} [[SUB:{base_range_label}]]"
            rows.append(("Reichweite", range_label))
        reload_time = item_engine.get_weapon_reload_time()
        if reload_time is not None:
            rows.append(("Nachladez.", reload_time))
        shot_count = item_engine.get_weapon_shot_count()
        if shot_count is not None:
            rows.append(("Schussanzahl", shot_count))
        min_st_1h = item_engine.get_weapon_min_st(ONE_HANDED)
        min_st_2h = item_engine.get_weapon_min_st(TWO_HANDED)
        if min_st_1h is not None and min_st_2h is not None and min_st_1h != min_st_2h:
            rows.append(("Min-ST", f"1H {min_st_1h} / 2H {min_st_2h}"))
        elif min_st_1h is not None:
            rows.append(("Min-ST", min_st_1h))
        min_ge_1h = item_engine.get_weapon_min_ge(ONE_HANDED)
        min_ge_2h = item_engine.get_weapon_min_ge(TWO_HANDED)
        if min_ge_1h is not None and min_ge_2h is not None and min_ge_1h != min_ge_2h:
            rows.append(("Min-GE", f"1H {min_ge_1h} / 2H {min_ge_2h}"))
        elif min_ge_1h is not None:
            rows.append(("Min-GE", min_ge_1h))

    elif getattr(item, "armorstats", None) is not None:
        rs = item_engine.get_armor_rs_raw() if armor_rs is None else armor_rs

        if rs is not None and armor_rs is None:
            rs = _apply_item_semantic_stat_effects(
                rs,
                modifier_payloads,
                DEFENSE_RS,
            )

        if rs is not None:
            rows.append(("RS", rs))

        rows.append((
            "Bel",
            item_engine.get_armor_encumbrance()
            if armor_encumbrance is None
            else armor_encumbrance,
        ))

        min_st = item_engine.get_armor_min_st()
        if min_st is not None:
            rows.append(("Min-ST", min_st))

    elif item.item_type == Item.ItemType.SHIELD:
        rs = item_engine.get_effective_shield_rs()
        if rs is not None:
            rows.append(("RS", rs))
        rows.append(("Bel", item_engine.get_shield_encumbrance() if shield_encumbrance is None else shield_encumbrance))
        min_st = item_engine.get_shield_min_st()
        if min_st is not None:
            rows.append(("Min-ST", min_st))
    elif item.item_type in Item.magic_item_type_values():
        effect_summary, text_payloads = unpack_magic_effect_summary(
            getattr(getattr(item, "magicitemstats", None), "effect_summary", "")
        )
        if effect_summary:
            rows.append(("Effekt", effect_summary))
        for payload in text_payloads:
            description = _single_line(str(payload.get("effect_description") or ""))
            if description:
                rows.append(("Magie", description))
    elif getattr(item, "magicitemstats", None) is not None:
        effect_summary, text_payloads = unpack_magic_effect_summary(getattr(item.magicitemstats, "effect_summary", ""))
        if effect_summary:
            rows.append(("Effekt", effect_summary))
        for payload in text_payloads:
            description = _single_line(str(payload.get("effect_description") or ""))
            if description:
                rows.append(("Magie", description))

    return rows


def _filter_item_tooltip_rows_for_display(
    rows: list[tuple[str, object]],
    hidden_field_keys: frozenset[str] | set[str],
    *,
    include_hidden_values: bool = False,
) -> list[tuple[str, object]]:
    if include_hidden_values:
        return rows
    label_field_keys = {
        "Kaufpreis": "price",
        "Gewicht": "weight",
        "GK": "size_class",
    }
    return [
        row
        for row in rows
        if label_field_keys.get(str(row[0])) not in hidden_field_keys
    ]


def _build_weapon_calculation_tooltip(
    engine,
    row: dict[str, object],
    *,
    extra_load_penalty: int = 0,
    extra_load_label: str = "Traglast",
) -> str:
    """Return a detailed damage-modifier ledger for one equipped weapon row."""
    character_item = row["character_item"]
    weapon_context = _character_item_weapon_target_context(character_item)
    damage_source_slug = ItemEngine(character_item).get_weapon_damage_source_slug()
    damage_attribute_code = str(
        row.get("damage_attribute_code") or ATTR_ST
    )

    damage_attribute_modifier = int(
        row.get(
            "damage_attribute_modifier",
            engine.attribute_modifier(damage_attribute_code),
        )
        or 0
    )
    mastery_bonus = int(row.get("weapon_mastery_damage_bonus", 0) or 0)
    mastery_source = "Schule: Waffenmeister"
    weapon_master_school_entry = getattr(engine, "_weapon_master_school_entry", None)
    if weapon_master_school_entry is not None and getattr(weapon_master_school_entry, "school", None) is not None:
        mastery_source = weapon_master_school_entry.school.name
    damage_modifier_rows = (
        _build_modifier_breakdown_rows(
            engine,
            damage_source_slug,
            target_domain=_modifier_target_domain_for_stat_key(damage_source_slug),
            context=weapon_context,
        )
        if damage_source_slug
        else []
    )
    weapon_damage_rows = _build_modifier_breakdown_rows(
        engine,
        WEAPON_DAMAGE,
        target_domain="combat",
        context=weapon_context,
        excluded_source_types=LOCAL_WEAPON_DAMAGE_SOURCE_TYPES,
    )
    item_damage_rows = _build_character_item_stat_modifier_rows(engine, character_item, WEAPON_DAMAGE)
    rows = []
    if str(row.get("maneuver_attribute_mode") or "") != "none":
        rows.append(
            {
                "label": f"{damage_attribute_code}-Bonus/Malus",
                "value": format_modifier(damage_attribute_modifier),
                "source": damage_attribute_code,
            }
        )
    rows.extend(damage_modifier_rows)
    rows.extend(weapon_damage_rows)
    if mastery_bonus:
        rows.append(
            {
                "label": "Waffenmeister",
                "value": format_modifier(mastery_bonus),
                "source": mastery_source,
                "tone": "modifier",
            }
        )
    rows.extend(item_damage_rows)
    rows.append({"label": "Belastung", "value": row["bel_malus_display"]})
    if extra_load_penalty:
        rows.append({"label": extra_load_label, "value": format_modifier(extra_load_penalty)})
    total_value = int(row.get("with_bel_value", row.get("with_bel", 0)) or 0) + int(extra_load_penalty or 0)
    rows.append({"label": "= Gesamt", "value": format_modifier(total_value), "tone": "total"})
    conditional_modifiers = _conditional_weapon_modifier_lines(
        engine,
        row,
    )
    return _build_core_stat_tooltip(
        rows,
        conditional_modifiers=conditional_modifiers,
    )


def _build_weapon_maneuver_breakdown_rows(engine, weapon_row: dict[str, object]) -> list[dict[str, object]]:
    """Return source-separated maneuver modifier rows for one weapon context entry."""
    rows: list[dict[str, object]] = []

    quality_bonus = int(weapon_row.get("quality_maneuver_bonus", 0) or 0)
    if quality_bonus:
        rows.append({
            "label": "Qualität",
            "value": format_modifier(quality_bonus),
            "source": str(weapon_row.get("item_name") or weapon_row["item"].name),
        })

    combat_bonus = int(weapon_row.get("trait_maneuver_modifier", 0) or 0)
    if combat_bonus:
        rows.append({
            "label": "Manoevermodifikatoren",
            "value": format_modifier(combat_bonus),
            "source": "Allgemein",
        })

    mastery_bonus = int(weapon_row.get("weapon_mastery_maneuver_bonus", 0) or 0)
    if mastery_bonus:
        mastery_source = "Schule: Waffenmeister"
        weapon_master_school_entry = getattr(engine, "_weapon_master_school_entry", None)
        if weapon_master_school_entry is not None and getattr(weapon_master_school_entry, "school", None) is not None:
            mastery_source = weapon_master_school_entry.school.name
        rows.append({
            "label": "Waffenmeister",
            "value": format_modifier(mastery_bonus),
            "source": mastery_source,
        })

    size_modifier = int(weapon_row.get("size_modifier", 0) or 0)
    if size_modifier:
        rows.append({
            "label": "GK",
            "value": format_modifier(size_modifier),
            "source": engine.size_class(),
        })

    item_bonus = int(weapon_row.get("item_maneuver_modifier", 0) or 0)
    if item_bonus:
        rows.append({
            "label": "Waffeneffekt",
            "value": format_modifier(item_bonus),
            "source": str(weapon_row.get("item_name") or weapon_row["item"].name),
        })

    return rows


def _build_total_armor_tooltip(engine) -> str:
    """Return a breakdown tooltip for the total armor protection value."""
    armor_piece_rows = _build_armor_rs_piece_rows(engine)
    armor_rune_sources = {
        (SOURCE_ITEM_RUNE, str(item_rune.id))
        for armor in engine.equipped_armor_items()
        for item_rune in armor.item_runes.all()
        if item_rune.is_active
    }
    return _build_core_stat_tooltip(
        [
            *armor_piece_rows,
            *_build_modifier_breakdown_rows(
                engine,
                DEFENSE_RS,
                excluded_sources=armor_rune_sources,
            ),
            {"label": "= Gesamt", "value": engine.get_grs(), "tone": "total"},
        ]
    )


def _build_armor_rs_piece_rows(engine) -> list[dict[str, object]]:
    """Return the effective armor protection basis for the GRS tooltip."""
    armor_rows = engine.equipped_armor_rows()
    shield_rows = engine.equipped_shield_rows()
    complete_armor_rows = [
        row
        for row in armor_rows
        if _is_complete_armor_row(row)
    ]
    if complete_armor_rows:
        rows = [
            {
                "label": row["item_name"],
                "value": int(row["rs"] or 0),
                "source": "Rüstung",
            }
            for row in complete_armor_rows
        ]
        rows.extend(
            {
                "label": row["item_name"],
                "value": int(row["rs"] or 0),
                "source": "Schild-RS",
            }
            for row in shield_rows
            if int(row["rs"] or 0)
        )
        covered_main_zone_average = _main_zone_armor_average(engine)
        displayed_direct_rs = sum(int(row["value"] or 0) for row in rows)
        additional_zone_rs = covered_main_zone_average - displayed_direct_rs
        if additional_zone_rs:
            rows.append(
                {
                    "label": "Weitere Rüstungszonen / 6",
                    "value": additional_zone_rs,
                    "source": "einmal abrunden",
                }
            )
        return rows

    zone_values = engine.armor_zone_protection()
    labels = (
        ("head", "Kopf"),
        ("torso", "Torso"),
        ("arm_left", "Arm links"),
        ("arm_right", "Arm rechts"),
        ("leg_left", "Bein links"),
        ("leg_right", "Bein rechts"),
    )
    rows = [
        {
            "label": label,
            "value": int(zone_values[zone]),
            "source": "inkl. Qualität, Rüstungsrunen und Schild-RS",
        }
        for zone, label in labels
    ]
    rows.append(
        {
            "label": "Zonensumme / 6",
            "value": sum(int(zone_values[zone]) for zone, _label in labels) // 6,
            "source": "einmal abrunden",
        }
    )
    return rows


def _is_complete_armor_row(row: dict[str, object]) -> bool:
    """Return whether an equipped armor row represents one complete armor."""
    item = row.get("item")
    stats = getattr(item, "armorstats", None)
    if stats is None or stats.parent_set_id:
        return False
    return all(getattr(stats, f"covers_{zone}", False) for zone in stats.MAIN_ZONE_FIELDS)


def _main_zone_armor_average(engine) -> int:
    """Return the rounded-down average of the six GRS body zones."""
    zone_values = engine.armor_zone_protection()
    return sum(
        int(zone_values[zone])
        for zone in ("head", "torso", "arm_left", "arm_right", "leg_left", "leg_right")
    ) // 6


def _build_load_tooltip(engine) -> str:
    """Return a breakdown tooltip for the effective encumbrance penalty."""
    armor_load = sum(int(row["bel_effective"] or 0) for row in engine.equipped_armor_rows())
    shield_load = sum(int(row["bel_effective"] or 0) for row in engine.equipped_shield_rows())
    total_raw_load = armor_load + shield_load
    rows: list[dict[str, object]] = [
        {"label": "Rüstungen", "value": armor_load},
        {"label": "Schilde", "value": shield_load},
    ]
    if engine.resolve_flags().get(ARMOR_PENALTY_IGNORE, False) and total_raw_load:
        rows.append(_build_rule_flag_tooltip_row(engine, ARMOR_PENALTY_IGNORE, format_modifier(-total_raw_load)))
    rows.append({"label": "= Gesamt", "value": format_modifier(engine.load_penalty()), "tone": "total"})
    return _build_core_stat_tooltip(rows)


def _build_carry_load_tooltip(carry_state: dict[str, object], *, active: bool) -> str:
    """Return a tooltip for the carried-weight toggle and its penalty table."""
    weight = carry_state["weight"]
    strength = int(carry_state["strength"])
    penalty = int(carry_state["penalty"])
    rows: list[dict[str, object]] = [
        {"label": "Mitgeführt", "value": f"{format_compact_number(weight)} kg"},
        {"label": "Zustand", "value": str(carry_state["state_label"])},
        {"label": "Traglast", "value": "[[STATUS:Ein|#6d8f4e]]" if active else "[[STATUS:Aus|#8f6b4a]]"},
        {"label": "Malus", "value": format_modifier(penalty if active else 0)},
        {"label": "[[EMPTY]]", "value": "[[EMPTY]]"},
        {"label": "Unbelastet", "value": f"unter {format_compact_number(int(carry_state['threshold_light']))} kg"},
        {"label": "Leicht belastet", "value": f"ab {format_compact_number(int(carry_state['threshold_light']))} kg"},
        {"label": "Bepackt", "value": f"ab {format_compact_number(int(carry_state['threshold_medium']))} kg"},
        {"label": "Schwer bepackt", "value": f"ab {format_compact_number(int(carry_state['threshold_heavy']))} kg"},
        {"label": "Überladen", "value": f"ab {format_compact_number(int(carry_state['threshold_overloaded']))} kg"},
        {"label": "Stärke", "value": strength},
    ]
    return _build_core_stat_tooltip(rows)


def _build_combined_load_tooltip(engine, carry_state: dict[str, object], *, carry_enabled: bool) -> str:
    """Return a tooltip for armor/shield load plus optional carrying load."""
    armor_load = sum(int(row["bel_effective"] or 0) for row in engine.equipped_armor_rows())
    shield_load = sum(int(row["bel_effective"] or 0) for row in engine.equipped_shield_rows())
    total_raw_load = armor_load + shield_load
    carry_penalty = int(carry_state["penalty"]) if carry_enabled else 0
    total_penalty = int(engine.load_penalty()) + carry_penalty
    rows: list[dict[str, object]] = [
        {"label": "Rüstungen", "value": armor_load},
        {"label": "Schilde", "value": shield_load},
        {"label": "Traglast", "value": format_modifier(carry_penalty), "source": str(carry_state["state_label"])},
    ]
    if engine.resolve_flags().get(ARMOR_PENALTY_IGNORE, False) and total_raw_load:
        rows.append(_build_rule_flag_tooltip_row(engine, ARMOR_PENALTY_IGNORE, format_modifier(-total_raw_load)))
    rows.append({"label": "= Gesamt", "value": format_modifier(total_penalty), "tone": "total"})
    return _build_core_stat_tooltip(rows)


def _build_minimum_strength_tooltip(engine) -> str:
    """Return a breakdown tooltip for the displayed armor minimum strength."""
    minimum_strength = int(engine.get_ms())
    complete_armor_rows = [
        row
        for row in engine.equipped_armor_rows()
        if row.get("armor_stats") is not None and row["armor_stats"].parent_set_id is None
    ]
    if complete_armor_rows:
        return _build_core_stat_tooltip(
            [
                *[
                    {
                        "label": row["item_name"],
                        "value": int(row["min_st"] or 0),
                        "source": "Gesamtrüstung",
                    }
                    for row in complete_armor_rows
                ],
                {
                    "label": "= Mindeststärke",
                    "value": minimum_strength,
                    "source": "höchster MS-Wert",
                    "tone": "total",
                },
            ]
        )

    total_rs = int(engine.get_grs())
    return _build_core_stat_tooltip(
        [
            {"label": "Gesamtrüstungsschutz", "value": total_rs, "source": "RS"},
            {
                "label": "Mindeststärke",
                "value": minimum_strength,
                "source": "Einzelteile: RS / 2, aufrunden",
                "tone": "total",
            },
        ]
    )


def _prettify_source_id(value: object) -> str:
    """Convert internal slugs into a compact human-readable fallback label."""
    text = str(value or "").strip()
    if not text:
        return "Unbekannt"
    if text.isdigit():
        return text
    return text.replace("_", " ").replace("-", " ").strip().title()


def _resolve_modifier_source_name(engine, source_type: object, source_id: object) -> str:
    """Return a readable source label for one modifier explanation row."""
    source_type_text = str(source_type or "").strip().lower()
    source_id_text = str(source_id or "").strip()
    if source_type_text == "race":
        race = getattr(engine.character, "race", None)
        if race is not None and (not source_id_text or source_id_text == str(race.id)):
            return race.name
        if source_id_text.isdigit():
            race = Race.objects.filter(pk=int(source_id_text)).only("name").first()
            if race is not None:
                return race.name
    if source_type_text == "trait":
        if source_id_text.isdigit():
            trait = Trait.objects.filter(pk=int(source_id_text)).only("name").first()
            if trait is not None:
                return trait.name
        trait = Trait.objects.filter(slug=source_id_text).only("name").first()
        if trait is not None:
            return trait.name
    if source_type_text == "school":
        if source_id_text.isdigit():
            school_entry = engine._school_entries.get(int(source_id_text))
            if school_entry is not None:
                return school_entry.school.name
            school = School.objects.filter(pk=int(source_id_text)).only("name").first()
            if school is not None:
                return school.name
    if source_type_text == "technique":
        if source_id_text.isdigit():
            technique = engine._techniques_by_id.get(int(source_id_text))
            if technique is not None:
                return technique.name
            technique = Technique.objects.filter(pk=int(source_id_text)).only("name").first()
            if technique is not None:
                return technique.name
    if source_type_text == "daemonic_power" and source_id_text.isdigit():
        power = DaemonicPower.objects.filter(pk=int(source_id_text)).only("name").first()
        if power is not None:
            return power.name
    if source_type_text == "item" and source_id_text.isdigit():
        item = Item.objects.filter(pk=int(source_id_text)).only("name").first()
        if item is not None:
            return item.name
    if source_type_text == "characteritem" and source_id_text.isdigit():
        character_item = CharacterItem.objects.filter(pk=int(source_id_text)).select_related("item").first()
        if character_item is not None:
            return character_item.effective_name
    if source_type_text == SOURCE_ITEM_RUNE and source_id_text.isdigit():
        item_rune = ItemRune.objects.filter(pk=int(source_id_text)).select_related("rune", "item__item").first()
        if item_rune is not None:
            return item_rune.rune.name
    return _prettify_source_id(source_id_text or source_type_text)


def _resolve_modifier_source_detail(engine, source_type: object, source_id: object) -> str:
    """Return an optional compact detail line for one modifier source."""
    source_type_text = str(source_type or "").strip().lower()
    source_id_text = str(source_id or "").strip()
    if source_type_text == SOURCE_ITEM_RUNE and source_id_text.isdigit():
        item_rune = ItemRune.objects.filter(pk=int(source_id_text)).select_related("item__item").first()
        if item_rune is not None:
            return f"auf {item_rune.item.effective_name}"
    if source_type_text != "technique":
        return ""
    technique = None
    if source_id_text.isdigit():
        technique = engine._techniques_by_id.get(int(source_id_text))
        if technique is None:
            technique = Technique.objects.filter(pk=int(source_id_text)).select_related("school").only(
                "name", "level", "school__name"
            ).first()
    if technique is None:
        return ""
    school_name = str(getattr(getattr(technique, "school", None), "name", "") or "").strip()
    technique_level = getattr(technique, "level", None)
    if school_name and technique_level:
        return f"{school_name} {_to_roman(int(technique_level))}"
    return school_name


def _format_modifier_source_display(source_label: str, source_name: str) -> str:
    """Return the most concrete readable source label available."""
    source_name_text = str(source_name or "").strip()
    if source_name_text:
        return source_name_text
    return "Unbekannt"


def _clean_modifier_note_text(note_text: object, *, invested_cp: object = "") -> str:
    """Hide generic migration notes that do not help the player-facing tooltip."""
    text = str(note_text or "").strip()
    hidden_notes = {
        "mapped automatically from legacy modifier semantics.",
        "damage-style stat slug migrated as combat modifier.",
        "legacy target_kind=skill uses a damage slug. migrated as combat modifier for backward-compatible combat resolution.",
    }
    if text.lower() in hidden_notes:
        return ""
    invested_cp_text = ""
    try:
        invested_cp_text = str(int(invested_cp))
    except (TypeError, ValueError):
        invested_cp_text = ""
    if text.startswith("|"):
        closing_index = text.find("|", 1)
        if closing_index > 1:
            label = text[1:closing_index].replace("@", invested_cp_text).strip()
            suffix = text[closing_index + 1:].strip().replace("@", invested_cp_text)
            text = " ".join(part for part in (label, suffix) if part)
    elif invested_cp_text:
        text = text.replace("@", invested_cp_text)
    for marker in ("**", "__", "`"):
        text = text.replace(marker, "")
    return text


def _item_source_invested_cp(source_type: object, source_id: object) -> int | None:
    source_type_text = str(source_type or "").strip().lower()
    source_id_text = str(source_id or "").strip()
    if not source_id_text.isdigit():
        return None
    if source_type_text == "characteritem":
        character_item = CharacterItem.objects.filter(pk=int(source_id_text)).select_related("item").first()
        if character_item is None:
            return None
        return character_item.invested_cp if character_item.invested_cp is not None else character_item.item.invested_cp
    if source_type_text == "item":
        item = Item.objects.filter(pk=int(source_id_text)).only("invested_cp").first()
        return None if item is None else item.invested_cp
    return None


def _build_modifier_breakdown_rows(
    engine,
    stat_key: str,
    *,
    target_domain: str = "derived_stat",
    context: dict[str, object] | None = None,
    excluded_sources: set[tuple[str, str]] | None = None,
    excluded_source_types: set[str] | None = None,
) -> list[dict[str, object]]:
    """Return ledger rows for each contributing modifier source."""
    explanation = engine.explain_modifier_resolution(target_domain, stat_key, context=context)
    if excluded_source_types:
        explanation = [
            entry
            for entry in explanation
            if str(entry.get("source_type") or "") not in excluded_source_types
        ]
    if excluded_sources:
        explanation = [
            entry
            for entry in explanation
            if (
                str(entry.get("source_type") or ""),
                str(entry.get("source_id") or ""),
            )
            not in excluded_sources
        ]
    return _build_grouped_explanation_rows(engine, explanation)


CORE_STAT_CONDITION_TARGETS = {
    INITIATIVE,
    DEFENSE_VW,
    DEFENSE_SR,
    DEFENSE_GW,
    ARCANE_POWER,
    POTENTIAL,
}


def _conditional_modifier_lines(
    engine,
    target_domain: str,
    target_key: str,
    *,
    specification: str | None = None,
) -> list[str]:
    """Return informational conditional modifier lines for a target."""
    modifier_engine = engine.modifier_engine
    totals: OrderedDict[str, dict[str, object]] = OrderedDict()
    for modifier in modifier_engine.collect_active_modifiers():
        if str(modifier.target_domain or "") != target_domain:
            continue
        if not modifier_engine._modifier_matches_target_key(
            modifier,
            target_domain=target_domain,
            target_key=target_key,
        ):
            continue
        if not modifier_engine._modifier_matches_skill_specification(
            modifier,
            target_domain=target_domain,
            specification=specification,
        ):
            continue
        if not TargetResolver.matches_context(modifier):
            continue
        condition_text = " ".join(str(modifier.metadata.get("condition_text") or "").split())
        condition_key = modifier_engine._normalize_condition_text(condition_text)
        if not condition_key:
            continue
        resolved_value = modifier_engine._resolve_numeric_modifier(modifier)
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        if condition_key not in totals:
            totals[condition_key] = {"condition_text": condition_text, "value": 0}
        totals[condition_key]["value"] = int(totals[condition_key]["value"]) + int(resolved_value)
    return [
        f"{format_modifier(int(row['value']))} {row['condition_text']}"
        for row in totals.values()
        if int(row["value"])
    ]


def _conditional_core_stat_modifiers(engine, stat_key: str) -> list[str]:
    """Return situational core-stat modifiers for the calculation tooltip."""
    if stat_key not in CORE_STAT_CONDITION_TARGETS:
        return []
    return _conditional_modifier_lines(engine, "derived_stat", stat_key)


def _build_core_stat_condition_badge(engine, stat_key: str) -> dict[str, object]:
    """Return marker payload for situational core-stat bonuses."""
    entries = _conditional_core_stat_modifiers(engine, stat_key)
    return {
        "visible": bool(entries),
        "tooltip": "\n".join(entries),
        "entries": entries,
    }


def _modifier_target_domain_for_stat_key(stat_key: str) -> str:
    """Return the modifier domain used by CharacterEngine for a stat-like key."""
    return "combat" if str(stat_key or "").startswith("dmg_") else "derived_stat"


def _character_item_weapon_target_context(
    character_item: CharacterItem,
    weapon_stats=None,
) -> dict[str, tuple[str, ...]]:
    """Return weapon target context for one equipped item row."""
    item = character_item.item
    weapon_skill_slugs: set[str] = set()
    weapon_type_slugs: set[str] = set()

    if weapon_stats is not None:
        weapon_stats_entries = [weapon_stats]
    else:
        weapon_stats_entries = list(item.weapon_stats.all())

    for stats in weapon_stats_entries:
        weapon_type = getattr(stats, "weapon_type", None)
        if weapon_type and getattr(weapon_type, "slug", ""):
            weapon_type_slugs.add(str(weapon_type.slug))

        skill_manager = getattr(stats, "skills", None)
        if skill_manager is not None:
            weapon_skill_slugs.update(
                str(skill.slug)
                for skill in skill_manager.all()
            )

    for stats_name in ("rangedweaponstats", "shieldstats"):
        stats = getattr(item, stats_name, None)
        if not stats:
            continue

        weapon_type = getattr(stats, "weapon_type", None)
        if weapon_type and getattr(weapon_type, "slug", ""):
            weapon_type_slugs.add(str(weapon_type.slug))

        skill_manager = getattr(stats, "skills", None)
        if skill_manager is not None:
            weapon_skill_slugs.update(
                str(skill.slug)
                for skill in skill_manager.all()
            )

    return {
        "character_item_id": str(character_item.id),
        "weapon_ids": (
            str(item.id),
            str(character_item.id),
        ),
        "weapon_types": tuple(sorted(weapon_type_slugs)),
        "weapon_skill_slugs": tuple(sorted(weapon_skill_slugs)),
    }


def _conditional_weapon_modifier_lines(
    engine,
    weapon_row: dict[str, object],
) -> list[str]:
    """Return conditional combat modifiers for one concrete weapon profile."""
    character_item = weapon_row["character_item"]
    weapon_stats = weapon_row.get("weapon_stats")

    weapon_context = _character_item_weapon_target_context(
        character_item,
        weapon_stats=weapon_stats,
    )

    relevant_target_keys = {
        WEAPON_DAMAGE,
        WEAPON_DAMAGE_DICE,
        WEAPON_MANEUVER_DAMAGE,
    }

    effects = list(
        ItemSemanticEffect.objects.filter(
            item_id=character_item.item_id,
            active_flag=True,
        )
        .exclude(notes="")
        .order_by("sort_order", "id")
    )

    effects.extend(
        CharacterItemSemanticEffect.objects.filter(
            character_item_id=character_item.id,
            active_flag=True,
        )
        .exclude(notes="")
        .order_by("sort_order", "id")
    )

    lines: list[str] = []

    for effect in effects:
        if not is_character_item_effect_identified(character_item, effect):
            continue
        if effect.target_domain != "combat":
            continue

        if str(effect.target_key or "") not in relevant_target_keys:
            continue

        modifier = effect.to_modifier(
            invested_cp=character_item.invested_cp,
        )

        if not engine.modifier_engine._modifier_matches_race_condition(
            modifier
        ):
            continue

        if not TargetResolver.matches_context(
            modifier,
            weapon_context,
        ):
            continue

        resolved_value = int(
            engine.modifier_engine._resolve_numeric_modifier(
                modifier
            )
            or 0
        )

        if not resolved_value:
            continue

        condition_text = " ".join(
            str(effect.notes or "").split()
        )

        if str(effect.target_key or "") == WEAPON_DAMAGE_DICE:
            value_label = f"{resolved_value:+d}w10"
        else:
            value_label = format_modifier(resolved_value)

        lines.append(
            f"{value_label} {condition_text}"
        )

    return lines


def _build_rule_flag_tooltip_row(engine, flag_key: str, value: object) -> dict[str, object]:
    """Return one tooltip row for an active rule-flag effect."""
    explanation = engine.explain_modifier_resolution("rule_flag", flag_key)
    if not explanation:
        return {"label": _prettify_source_id(flag_key), "value": value, "source": "Effekt"}
    row_meta = _collect_explanation_source_metadata(engine, explanation)
    if not row_meta:
        return {"label": _prettify_source_id(flag_key), "value": value, "source": "Effekt"}

    labels = [entry["label"] for entry in row_meta]
    sources = [entry["source"] for entry in row_meta if entry["source"]]
    return {
        "label": ", ".join(labels),
        "value": value,
        "source": ", ".join(dict.fromkeys(sources)),
    }


def _collect_explanation_source_metadata(engine, explanation: list[dict[str, object]]) -> list[dict[str, str]]:
    """Return readable unique source metadata from modifier explanation rows."""
    source_rows: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for entry in explanation:
        resolved_value = entry.get("resolved_value")
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        source_type = str(entry.get("source_type") or "").strip().lower()
        source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
        source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
        source_detail = _resolve_modifier_source_detail(engine, source_type, entry.get("source_id"))
        row_label = source_name or source_label or _prettify_source_id(source_type)
        if row_label in seen_labels:
            continue
        seen_labels.add(row_label)
        source_rows.append(
            {
                "label": row_label,
                "source": source_detail or (source_label if source_label != row_label else ""),
            }
        )
    return source_rows


def _build_grouped_explanation_rows(engine, explanation: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return grouped tooltip rows from one modifier explanation payload."""
    grouped_rows: OrderedDict[tuple[str, str], dict[str, object]] = OrderedDict()
    for entry in explanation:
        resolved_value = entry.get("resolved_value")
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        source_type = str(entry.get("source_type") or "").strip().lower()
        source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
        source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
        source_detail = _resolve_modifier_source_detail(engine, source_type, entry.get("source_id"))
        source_display = _format_modifier_source_display(source_label, source_name)
        note_text = _clean_modifier_note_text(
            entry.get("notes"),
            invested_cp=_item_source_invested_cp(source_type, entry.get("source_id")),
        )
        row_label = note_text or source_name or "Unbekannt"
        if source_display.strip().casefold() == row_label.strip().casefold():
            source_display = ""
        if source_detail:
            source_display = source_detail
        group_key = (source_type, row_label)
        existing = grouped_rows.get(group_key)
        if existing is None:
            grouped_rows[group_key] = {
                "label": row_label,
                "value": int(resolved_value),
                "source": source_display,
                "tone": "modifier",
                "count": 1,
            }
            continue
        existing["value"] = int(existing["value"]) + int(resolved_value)
        existing["count"] = int(existing.get("count", 1)) + 1

    rows: list[dict[str, object]] = []
    for row in grouped_rows.values():
        label = str(row["label"])
        count = int(row.get("count", 1))
        if count > 1:
            label = f"{label} {_to_roman(count)}".strip()
        rows.append(
            {
                "label": label,
                "value": format_modifier(int(row["value"])),
                "source": row["source"],
                "tone": row["tone"],
            }
        )
    return rows


def _build_character_item_stat_modifier_rows(engine, character_item: CharacterItem, stat_key: str) -> list[dict[str, object]]:
    """Return grouped breakdown rows for one item-bound stat modifier source."""
    explanation: list[dict[str, object]] = []
    target_context = _character_item_weapon_target_context(character_item)

    for modifier in engine.modifier_engine._active_item_semantic_modifiers:
        source_type = str(
            getattr(modifier, "source_type", "") or ""
        )
        source_id = str(
            getattr(modifier, "source_id", "") or ""
        )

        if source_type == "characteritem":
            if source_id != str(character_item.id):
                continue
        elif source_type == "item":
            if source_id != str(character_item.item_id):
                continue
        else:
            continue
        if not engine.modifier_engine._modifier_matches_race_condition(modifier):
            continue
        if not engine.modifier_engine._modifier_matches_school_condition(modifier):
            continue
        target_domain = getattr(getattr(modifier, "target_domain", ""), "value", getattr(modifier, "target_domain", ""))
        if str(target_domain or "") != "combat":
            continue
        modifier_target_key = str(
            getattr(modifier, "target_key", "") or ""
        )

        if modifier_target_key != stat_key and not (
            modifier_target_key == WEAPON_MANEUVER_DAMAGE
            and stat_key in {MELEE_MANEUVERS, WEAPON_DAMAGE}
        ):
            continue
        if not TargetResolver.matches_context(modifier, target_context):
            continue
        resolved_value = engine.modifier_engine._resolve_numeric_modifier(modifier)
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        explanation.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "resolved_value": resolved_value,
                "notes": _clean_modifier_note_text(
                    getattr(modifier, "notes", "")
                    or getattr(modifier, "rules_text", ""),
                    invested_cp=_item_source_invested_cp(
                        source_type,
                        source_id,
                    ),
                ),
            }
        )
    if stat_key == WEAPON_DAMAGE:
        equipped_item_rune_ids = {
            int(item_rune.id)
            for item_rune in character_item.item_runes.all()
            if item_rune.is_active
        }
        for modifier in engine.modifier_engine._active_item_rune_modifiers:
            if str(getattr(modifier, "source_type", "") or "") != SOURCE_ITEM_RUNE:
                continue
            if not engine.modifier_engine._modifier_matches_race_condition(modifier):
                continue
            if not engine.modifier_engine._modifier_matches_school_condition(modifier):
                continue
            if str(getattr(modifier, "target_key", "") or "") != stat_key:
                continue
            try:
                source_id = int(getattr(modifier, "source_id", ""))
            except (TypeError, ValueError):
                continue
            if source_id not in equipped_item_rune_ids:
                continue
            if not TargetResolver.matches_context(modifier, target_context):
                continue
            resolved_value = engine.modifier_engine._resolve_numeric_modifier(modifier)
            if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                continue
            explanation.append(
                {
                    "source_type": SOURCE_ITEM_RUNE,
                    "source_id": source_id,
                    "resolved_value": resolved_value,
                    "notes": getattr(modifier, "notes", ""),
                }
            )
    return _build_grouped_explanation_rows(engine, explanation)


def _build_skill_modifier_rows(
    engine, skill_slug: str,
    *,
    skill_name: str,
    category_slug: str | None,
    skill_id: int | None,
    specification: str | None = None
) -> list[dict[str, object]]:
    """Return modifier rows for one skill calculation tooltip."""
    rows: list[dict[str, object]] = []
    for entry in engine.explain_modifier_resolution("skill", skill_slug, specification=specification):
        resolved_value = entry.get("resolved_value")
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        source_type = str(entry.get("source_type") or "").strip().lower()
        source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
        source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
        source_display = _format_modifier_source_display(source_label, source_name)
        note_text = _clean_modifier_note_text(
            entry.get("notes"),
            invested_cp=_item_source_invested_cp(source_type, entry.get("source_id")),
        )
        rows.append(
            {
                "label": note_text or source_name or skill_name,
                "value": format_modifier(int(resolved_value)),
                "source": source_display,
                "tone": "modifier",
            }
        )
    if category_slug:
        for entry in engine.explain_modifier_resolution("skill_category", category_slug):
            resolved_value = entry.get("resolved_value")
            if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                continue
            source_type = str(entry.get("source_type") or "").strip().lower()
            source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
            source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
            source_display = _format_modifier_source_display(source_label, source_name)
            note_text = _clean_modifier_note_text(
                entry.get("notes"),
                invested_cp=_item_source_invested_cp(source_type, entry.get("source_id")),
            )
            rows.append(
                {
                    "label": note_text or source_name or "Kategorie-Bonus",
                    "value": format_modifier(int(resolved_value)),
                    "source": source_display,
                    "tone": "modifier",
                }
            )
    if skill_id is not None:
        choice_bonus = int(engine._resolve_choice_skill_bonus(skill_id))
        if choice_bonus:
            rows.append(
                {
                    "label": "Auswahlbonus",
                    "value": format_modifier(choice_bonus),
                    "source": "Auswahl",
                    "tone": "modifier",
                }
            )
        choice_modifiers = int(engine._resolve_choice_skill_modifiers(skill_id, specification=specification))
        if choice_modifiers:
            rows.append(
                {
                    "label": "Auswahl-Mod.",
                    "value": format_modifier(choice_modifiers),
                    "source": "Auswahl",
                    "tone": "modifier",
                }
            )
    return rows


def _build_skill_rows(
    character: Character,
    engine,
    *,
    load_penalty: int,
) -> tuple[list[dict], list[object], list[dict]]:
    """Build visible skill rows plus skill-manager state for the sheet."""

    def _condition_tooltip(condition_text: str) -> str:
        normalized = " ".join(str(condition_text or "").split())
        if normalized.casefold().startswith("im "):
            return f"bei {normalized[3:]}"
        return normalized

    def _conditional_encumbrance_variants() -> list[dict[str, object]]:
        """Return conditional daemonic encumbrance as skill-value deltas."""
        modifier_engine = engine.modifier_engine
        conditions: OrderedDict[str, str] = OrderedDict()
        for modifier in modifier_engine._active_daemonic_power_modifiers:
            if str(modifier.target_domain or "") != "derived_stat":
                continue
            if not modifier_engine._modifier_matches_target_key(
                modifier,
                target_domain="derived_stat",
                target_key="encumbrance",
            ):
                continue
            condition_text = " ".join(
                str(modifier.metadata.get("condition_text") or "").split()
            )
            normalized = modifier_engine._normalize_condition_text(condition_text)
            if normalized:
                conditions.setdefault(normalized, condition_text)

        variants: list[dict[str, object]] = []
        for condition_text in conditions.values():
            context = {"condition_text": condition_text}
            conditional_encumbrance = modifier_engine.resolve_numeric_total(
                "derived_stat",
                "encumbrance",
                context=context,
            ) - modifier_engine.resolve_numeric_total(
                "derived_stat",
                "encumbrance",
            )
            skill_value_delta = -int(conditional_encumbrance)
            if skill_value_delta == 0:
                continue
            variants.append(
                {
                    "condition_text": condition_text,
                    "tooltip": _condition_tooltip(condition_text),
                    "value_delta": skill_value_delta,
                }
            )
        return variants

    conditional_encumbrance_variants = _conditional_encumbrance_variants()

    def _skill_conditional_modifier_lines(skill: Skill, specification: str | None) -> list[str]:
        entries = [
            *_conditional_modifier_lines(
                engine,
                "skill",
                skill.slug,
                specification=specification,
            ),
            *_conditional_modifier_lines(engine, "skill_category", skill.category.slug),
        ]
        for weapon_row in equipped_weapon_rows:
            weapon_stats = weapon_row.get("weapon_stats")
            if weapon_stats is None:
                continue

            weapon_skill_slugs = {
                str(weapon_skill.slug)
                for weapon_skill in weapon_stats.skills.all()
            }

            if skill.slug not in weapon_skill_slugs:
                continue

            character_item = weapon_row["character_item"]

            weapon_context = _character_item_weapon_target_context(
                character_item,
                weapon_stats=weapon_stats,
            )

            effects = list(
                ItemSemanticEffect.objects.filter(
                    item_id=character_item.item_id,
                    active_flag=True,
                    target_domain="combat",
                    target_key=MELEE_MANEUVERS,
                )
                .exclude(notes="")
                .order_by("sort_order", "id")
            )

            effects.extend(
                CharacterItemSemanticEffect.objects.filter(
                    character_item_id=character_item.id,
                    active_flag=True,
                    target_domain="combat",
                    target_key=MELEE_MANEUVERS,
                )
                .exclude(notes="")
                .order_by("sort_order", "id")
            )

            for effect in effects:
                if not is_character_item_effect_identified(character_item, effect):
                    continue
                modifier = effect.to_modifier(
                    invested_cp=character_item.invested_cp,
                )

                if not TargetResolver.matches_context(
                    modifier,
                    weapon_context,
                ):
                    continue

                value = int(
                    engine.modifier_engine._resolve_numeric_modifier(
                        modifier
                    )
                    or 0
                )

                if not value:
                    continue

                condition_text = " ".join(
                    str(effect.notes or "").split()
                )

                entries.append(
                    f"{format_modifier(value)} {condition_text}"
                )
        seen: OrderedDict[str, str] = OrderedDict()
        for entry in entries:
            normalized = " ".join(entry.casefold().split())
            if normalized:
                seen.setdefault(normalized, entry)
        return list(seen.values())

    def _build_display_name(skill: Skill, specification: str) -> str:
        normalized_spec = (specification or "").strip()
        has_specification = skill.requires_specification and normalized_spec and normalized_spec != "*"
        display_name = skill.name.rstrip(": ").strip()
        if skill.requires_specification:
            return normalized_spec if has_specification else "*"
        if has_specification:
            return f"{display_name} {normalized_spec}"
        return display_name

    def _skill_size_modifier(skill: Skill) -> int:
        if skill.category.slug == SKILL_COMBAT:
            return int(engine.size_modifier())
        if skill.slug == "skill_evasion":
            return int(engine.size_modifier())
        if skill.slug == "skill_hide":
            return int(engine.size_modifier()) * 2
        return 0

    def _build_row(skill: Skill, character_skill=None, *, specification_override: str | None = None) -> dict:
        attribute_modifier = int(engine.attribute_modifier(skill.attribute.short_name))
        if specification_override is not None:
            specification = (specification_override or "").strip() or "*"
        else:
            specification = ((character_skill.specification if character_skill is not None else "*") or "").strip()
        raw_modifiers = int(engine._skill_modifiers(skill.slug, specification=specification))
        base_rank = int(character_skill.level) if character_skill is not None else 0
        rank_bonus = int(engine.skill_rank_bonus(skill.slug, specification=specification))
        rank = base_rank + rank_bonus
        size_modifier = _skill_size_modifier(skill)
        total_with_load = rank + attribute_modifier + raw_modifiers + size_modifier
        conditional_modifiers = _skill_conditional_modifier_lines(skill, specification)
        for variant in conditional_encumbrance_variants:
            conditional_modifiers.append(
                f"{format_modifier(int(variant['value_delta']))} {_condition_tooltip(str(variant['condition_text']))}"
            )
        origin = " ".join(str(character.country_of_origin or "").split())
        is_origin_local_knowledge = (
            bool(origin)
            and skill.slug == "knw_local_knowledge"
            and specification == origin
        )
        return {
            "row_kind": "skill",
            "is_context_row": bool(skill.requires_specification),
            "is_specification_child": bool(skill.requires_specification),
            "character_skill_id": character_skill.id if character_skill is not None else None,
            "skill_id": skill.id,
            "name": skill.name,
            "display_name": _build_display_name(skill, specification),
            "description": skill.description,
            "category_name": skill.category.name,
            "category_slug": skill.category.slug,
            "family": skill.family,
            "attribute": skill.attribute.short_name,
            "attribute_mod": format_modifier(attribute_modifier),
            "attribute_mod_value": attribute_modifier,
            "rank": rank,
            "rank_value": rank,
            "base_rank_value": base_rank,
            "rank_bonus_value": rank_bonus,
            "misc_mod": format_modifier(raw_modifiers - load_penalty),
            "misc_mod_value": raw_modifiers - load_penalty,
            "size_mod_value": size_modifier,
            "total": total_with_load - load_penalty,
            "total_value": total_with_load - load_penalty,
            "with_load_total": total_with_load,
            "with_load_total_value": total_with_load,
            "calculation_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Eigenschaft", "value": format_modifier(attribute_modifier), "source": skill.attribute.short_name},
                    {"label": "Rang", "value": base_rank},
                    *(
                        [{"label": "Rang-Bonus", "value": format_modifier(rank_bonus), "source": "Effekt"}]
                        if rank_bonus
                        else []
                    ),
                    {
                        "label": "Wundmalus",
                        "value": format_modifier(engine.current_wound_penalty()),
                    },
                    *(
                        [{"label": "GK", "value": format_modifier(size_modifier), "source": engine.size_class()}]
                        if size_modifier
                        else []
                    ),
                    *_build_skill_modifier_rows(
                        engine,
                        skill.slug,
                        skill_name=skill.name,
                        category_slug=skill.category.slug,
                        skill_id=skill.id,
                        specification=specification,
                    ),
                    {"label": "Belastung", "value": format_modifier(load_penalty)},
                    {"label": "= Gesamt", "value": total_with_load, "tone": "total"},
                ],
                conditional_modifiers=conditional_modifiers,
            ),
            "has_conditional_modifiers": bool(conditional_modifiers),
            "can_edit_specification": (
                skill.requires_specification
                and character_skill is not None
                and not is_origin_local_knowledge
            ),
            "specification": "" if specification == "*" else specification,
            "is_auto_visible": character_skill is None,
        }

    def _build_specification_parent_row(skill: Skill) -> dict:
        return {
            "row_kind": "skill_specification_parent",
            "is_context_row": False,
            "is_specification_parent": True,
            "skill_id": skill.id,
            "name": skill.name,
            "display_name": skill.name.rstrip(": ").strip(),
            "description": skill.description,
            "category_name": skill.category.name,
            "category_slug": skill.category.slug,
            "family": skill.family,
            "attribute": "",
            "attribute_mod": "",
            "rank": "",
            "misc_mod": "",
            "total": "",
            "with_load_total": "",
            "calculation_tooltip": "",
            "has_conditional_modifiers": False,
            "can_edit_specification": False,
            "specification": "",
            "is_auto_visible": False,
        }

    def _append_skill_rows(skill: Skill, rows: list[dict]) -> None:
        if not rows:
            return
        if skill.requires_specification:
            skill_rows.append(_build_specification_parent_row(skill))
        for row in rows:
            skill_rows.append(row)
            skill_rows.extend(_build_display_context_rows(row, skill))

    resolved_equipment_names_by_character_item_id: dict[int, str] = {}

    def _resolved_equipment_name(character_item: CharacterItem) -> str:
        character_item_id = int(character_item.pk)
        if character_item_id not in resolved_equipment_names_by_character_item_id:
            resolved_equipment_names_by_character_item_id[character_item_id] = resolve_character_item_display(
                character_item,
                getattr(character, "owner", None),
                preview_player=True,
            ).name
        return resolved_equipment_names_by_character_item_id[character_item_id]

    def _build_weapon_context_rows(base_row: dict) -> list[dict]:
        skill_id = int(base_row["skill_id"])
        rows: list[dict] = []
        for weapon_row in equipped_weapon_rows:
            if not weapon_row.get("is_primary_profile", False):
                continue
            weapon_stats = weapon_row.get("weapon_stats")
            ranged_stats = getattr(weapon_row["item"], "rangedweaponstats", None)
            offensive_stats = ranged_stats or weapon_stats
            if offensive_stats is None:
                continue
            linked_skill_ids = {entry.id for entry in offensive_stats.skills.all()}
            if skill_id not in linked_skill_ids:
                continue
            item_name = _resolved_equipment_name(weapon_row["character_item"])
            weapon_row = {**weapon_row, "item_name": item_name}
            maneuver_breakdown_rows = _build_weapon_maneuver_breakdown_rows(engine, weapon_row)
            for option in weapon_row.get("maneuver_options") or []:
                maneuver_bonus = int(option.get("total_modifier") or 0) - int(option.get("attribute_modifier") or 0)
                rows.append(
                    {
                        "row_kind": "weapon_context",
                        "is_context_row": True,
                        "skill_id": skill_id,
                        "name": base_row["name"],
                        "display_name": f"mit {item_name} ({option['attribute_code']})",
                        "weapon_base_name": item_name,
                        "description": f"Manöverbonus mit {item_name} über {option['attribute_code']}",
                        "weapon_attribute_code": option["attribute_code"],
                        "attribute": base_row["attribute"],
                        "attribute_mod": base_row["attribute_mod"],
                        "attribute_mod_value": int(base_row["attribute_mod_value"]),
                        "rank": int(base_row["rank_value"]),
                        "rank_value": int(base_row["rank_value"]),
                        "misc_mod": format_modifier(int(base_row["misc_mod_value"]) + maneuver_bonus),
                        "misc_mod_value": int(base_row["misc_mod_value"]) + maneuver_bonus,
                        "total": int(base_row["total_value"]) + maneuver_bonus,
                        "total_value": int(base_row["total_value"]) + maneuver_bonus,
                        "with_load_total": int(base_row["with_load_total_value"]) + maneuver_bonus,
                        "with_load_total_value": int(base_row["with_load_total_value"]) + maneuver_bonus,
                        "calculation_tooltip": _build_core_stat_tooltip(
                            [
                                {"label": "Grundwert", "value": int(base_row["with_load_total_value"]), "source": base_row["display_name"]},
                                *maneuver_breakdown_rows,
                                {"label": "= Gesamt", "value": int(base_row["with_load_total_value"]) + maneuver_bonus, "tone": "total"},
                            ]
                        ),
                        "can_edit_specification": False,
                        "specification": "",
                        "is_auto_visible": False,
                    }
                )
        rows.sort(key=lambda row: row["display_name"].lower())
        return rows

    def _is_shield_skill(skill: Skill) -> bool:
        name = str(skill.name or "").strip().casefold()
        slug = str(skill.slug or "").strip().casefold()
        return name in {"schilde", "schild"} or "shield" in slug or "schild" in slug

    def _build_shield_context_rows(base_row: dict, skill: Skill) -> list[dict]:
        if not _is_shield_skill(skill):
            return []
        rows: list[dict] = []
        for shield_row in equipped_shield_rows:
            parade_bonus = int(shield_row.get("parade_bonus") or 0)
            if parade_bonus == 0:
                continue
            item_name = _resolved_equipment_name(shield_row["character_item"])
            with_load_total = int(base_row["with_load_total_value"]) + parade_bonus
            total = int(base_row["total_value"]) + parade_bonus
            rows.append(
                {
                    "row_kind": "shield_context",
                    "is_context_row": True,
                    "skill_id": int(base_row["skill_id"]),
                    "name": base_row["name"],
                    "display_name": f"mit {item_name}",
                    "description": f"Paradebonus bei Verteidigung mit {item_name}",
                    "attribute": base_row["attribute"],
                    "attribute_mod": base_row["attribute_mod"],
                    "attribute_mod_value": int(base_row["attribute_mod_value"]),
                    "rank": int(base_row["rank_value"]),
                    "rank_value": int(base_row["rank_value"]),
                    "misc_mod": format_modifier(int(base_row["misc_mod_value"]) + parade_bonus),
                    "misc_mod_value": int(base_row["misc_mod_value"]) + parade_bonus,
                    "total": total,
                    "total_value": total,
                    "with_load_total": with_load_total,
                    "with_load_total_value": with_load_total,
                    "calculation_tooltip": _build_core_stat_tooltip(
                        [
                            {"label": "Grundwert", "value": int(base_row["with_load_total_value"]), "source": base_row["display_name"]},
                            {"label": "PB", "value": format_modifier(parade_bonus), "source": item_name},
                            {"label": "= Gesamt", "value": with_load_total, "tone": "total"},
                        ]
                    ),
                    "can_edit_specification": False,
                    "specification": "",
                    "is_auto_visible": False,
                }
            )
        rows.sort(key=lambda row: row["display_name"].lower())
        return rows

    def _conditional_daemonic_effects(skill: Skill, specification: str | None = None) -> OrderedDict[str, str]:
        """Return normalized, player-facing restrictions targeting one skill."""
        conditions: OrderedDict[str, str] = OrderedDict()
        modifier_engine = engine.modifier_engine
        for modifier in modifier_engine._active_daemonic_power_modifiers:
            target_domain = str(modifier.target_domain or "")
            if target_domain == "skill":
                matches_target = modifier_engine._modifier_matches_target_key(
                    modifier,
                    target_domain=target_domain,
                    target_key=skill.slug,
                )
            elif target_domain == "skill_category":
                matches_target = modifier.target_key == skill.category.slug
            else:
                continue
            if not matches_target:
                continue
            if not modifier_engine._modifier_matches_skill_specification(
                modifier,
                target_domain=target_domain,
                specification=specification,
            ):
                continue
            condition_text = " ".join(str(modifier.metadata.get("condition_text") or "").split())
            normalized = modifier_engine._normalize_condition_text(condition_text)
            if normalized:
                conditions.setdefault(normalized, condition_text)
        return conditions

    def _build_conditional_daemonic_context_rows(base_row: dict, skill: Skill) -> list[dict]:
        """Build one cumulative child row per daemonic-power restriction."""
        specification = str(base_row.get("specification") or "")
        modifier_engine = engine.modifier_engine
        rows: list[dict] = []
        for normalized_condition, condition_text in _conditional_daemonic_effects(skill, specification).items():
            context = {"condition_text": condition_text}
            direct_total = modifier_engine.resolve_numeric_total(
                "skill",
                skill.slug,
                context=context,
                specification=specification,
            ) - modifier_engine.resolve_numeric_total(
                "skill",
                skill.slug,
                specification=specification,
            )
            category_total = modifier_engine.resolve_numeric_total(
                "skill_category",
                skill.category.slug,
                context=context,
            ) - modifier_engine.resolve_numeric_total(
                "skill_category",
                skill.category.slug,
            )
            conditional_total = int(direct_total) + int(category_total)
            if conditional_total == 0:
                continue

            explanation = [
                *modifier_engine.explain_resolution(
                    ("skill", skill.slug),
                    context=context,
                    specification=specification,
                ),
                *modifier_engine.explain_resolution(
                    ("skill_category", skill.category.slug),
                    context=context,
                ),
            ]
            conditional_explanation = [
                entry
                for entry in explanation
                if modifier_engine._normalize_condition_text(entry.get("condition_text")) == normalized_condition
            ]
            source_names = [
                _resolve_modifier_source_name(engine, entry.get("source_type"), entry.get("source_id"))
                for entry in conditional_explanation
            ]
            source_names = list(dict.fromkeys(name for name in source_names if name))
            with_load_total = int(base_row["with_load_total_value"]) + conditional_total
            rows.append(
                {
                    "row_kind": "conditional_effect_context",
                    "is_context_row": True,
                    "skill_id": int(base_row["skill_id"]),
                    "name": base_row["name"],
                    "display_name": f"bei {condition_text}",
                    "description": (
                        f"Bedingte dämonische Effekte: {', '.join(source_names)}"
                        if source_names
                        else f"Bedingter dämonischer Effekt bei {condition_text}"
                    ),
                    "attribute": base_row["attribute"],
                    "attribute_mod": base_row["attribute_mod"],
                    "attribute_mod_value": int(base_row["attribute_mod_value"]),
                    "rank": int(base_row["rank_value"]),
                    "rank_value": int(base_row["rank_value"]),
                    "misc_mod": format_modifier(int(base_row["misc_mod_value"]) + conditional_total),
                    "misc_mod_value": int(base_row["misc_mod_value"]) + conditional_total,
                    "total": int(base_row["total_value"]) + conditional_total,
                    "total_value": int(base_row["total_value"]) + conditional_total,
                    "with_load_total": with_load_total,
                    "with_load_total_value": with_load_total,
                    "calculation_tooltip": _build_core_stat_tooltip(
                        [
                            {
                                "label": "Grundwert",
                                "value": int(base_row["with_load_total_value"]),
                                "source": base_row["display_name"],
                            },
                            *_build_grouped_explanation_rows(engine, conditional_explanation),
                            {"label": "= Gesamt", "value": with_load_total, "tone": "total"},
                        ]
                    ),
                    "can_edit_specification": False,
                    "specification": specification,
                    "is_auto_visible": False,
                }
            )
        return rows

    def _build_display_context_rows(base_row: dict, skill: Skill) -> list[dict]:
        """Return conditional power rows followed by applicable weapon rows."""
        context_rows: list[dict] = []
        if skill.requires_specification:
            return context_rows
        context_rows.extend(_build_shield_context_rows(base_row, skill))
        weapon_context_rows = _build_weapon_context_rows(base_row)
        if not weapon_context_rows:
            return context_rows
        matching_attribute_rows = [
            entry
            for entry in weapon_context_rows
            if str(entry.get("weapon_attribute_code", "")) == str(base_row["attribute"])
        ]
        candidate_rows = matching_attribute_rows or weapon_context_rows
        for weapon_context_row in sorted(
            candidate_rows,
            key=lambda entry: (
                -int(entry.get("with_load_total_value", 0) or 0),
                str(entry.get("display_name", "")).lower(),
            ),
        ):
            weapon_context_row = dict(weapon_context_row)
            display_name = str(weapon_context_row.get("display_name", ""))
            if " (" in display_name and display_name.endswith(")"):
                weapon_context_row["display_name"] = display_name.rsplit(" (", 1)[0]
            context_rows.append(weapon_context_row)
        return context_rows

    skill_rows: list[dict] = []
    character_skills = list(
        character.characterskill_set
        .select_related("skill", "skill__attribute", "skill__category")
        .order_by("skill__name", "specification", "id")
    )
    skills_by_id = {
        skill.id: skill
        for skill in Skill.objects.select_related("category", "attribute").order_by("name", "id")
    }
    character_skills_by_skill_id: dict[int, list[object]] = {}
    for character_skill in character_skills:
        character_skills_by_skill_id.setdefault(character_skill.skill_id, []).append(character_skill)
    modifier_specifications_by_skill_id: dict[int, set[str]] = {}

    def _modifier_skill_specification_keys(skill: Skill) -> set[str]:
        if skill.id not in modifier_specifications_by_skill_id:
            modifier_specifications_by_skill_id[skill.id] = {
                " ".join(str(specification or "").strip().split()).casefold()
                for specification in engine.modifier_skill_specifications(skill.id, skill.slug)
                if " ".join(str(specification or "").strip().split())
            }
        return modifier_specifications_by_skill_id[skill.id]

    def _is_modifier_only_skill_row(character_skill) -> bool:
        if int(character_skill.level) > 0 or not character_skill.skill.requires_specification:
            return False
        specification = " ".join(str(character_skill.specification or "").strip().split())
        if not specification or specification == "*":
            return False
        return specification.casefold() in _modifier_skill_specification_keys(character_skill.skill)

    equipped_weapon_rows = engine.equipped_weapon_rows()
    equipped_shield_rows = engine.equipped_shield_rows()

    for skill in skills_by_id.values():
        rows_for_skill = character_skills_by_skill_id.get(skill.id, [])
        rows_for_skill = [
            character_skill
            for character_skill in rows_for_skill
            if not _is_modifier_only_skill_row(character_skill)
        ]
        if rows_for_skill:
            visible_rows = []
            for character_skill in rows_for_skill:
                row = _build_row(skill, character_skill=character_skill)
                visible_rows.append(row)
            _append_skill_rows(skill, visible_rows)
            continue

    skill_manager_rows: list[dict] = []
    for skill in skills_by_id.values():
        if skill.requires_specification:
            continue
        rows_for_skill = character_skills_by_skill_id.get(skill.id, [])
        has_skill_row = bool(rows_for_skill)
        has_skilled_row = any(int(row.level) > 0 for row in rows_for_skill)
        if has_skilled_row:
            continue
        generic_row = next((row for row in rows_for_skill if (row.specification or "*") == "*"), None)
        auto_visible = False
        can_add = not has_skill_row
        can_remove = (
            generic_row is not None
            and int(generic_row.level) == 0
            and not has_skilled_row
            and not auto_visible
        )
        if has_skill_row:
            status_label = "Eingeblendet"
        else:
            status_label = "Ausgeblendet"
        skill_manager_rows.append(
            {
                "skill_id": skill.id,
                "name": skill.name,
                "category_name": skill.category.name,
                "is_visible": has_skill_row or auto_visible,
                "can_add": can_add,
                "can_remove": can_remove,
                "status_label": status_label,
            }
        )

    return skill_rows, character_skills, skill_manager_rows


def _build_trait_rows(character: Character) -> tuple[list[dict], list[dict]]:
    """Build prepared rows for advantages and disadvantages."""
    traits_qs = (
        CharacterTrait.objects
        .filter(owner=character)
        .select_related("trait")
        .order_by("trait__trait_type", "trait__name")
    )
    advantage_rows: list[dict] = []
    disadvantage_rows: list[dict] = []
    for entry in traits_qs:
        row = {
            "id": entry.id,
            "name": entry.trait.name,
            "description": entry.trait.description,
            "points": entry.trait.cost_for_level(entry.trait_level),
            "can_edit_specification": bool(entry.trait.has_specification),
            "specification": (entry.specification or "").strip(),
        }
        if row["can_edit_specification"]:
            row["display_name"] = entry.trait.name
            row["tooltip"] = "\n\n".join(
                part for part in (f"**{entry.trait.name}: {row['specification'] or '*'}**", row["description"]) if part
            )
        else:
            row["display_name"] = entry.trait.name
            row["tooltip"] = row["description"]
        if entry.trait.trait_type == Trait.TraitType.ADV:
            advantage_rows.append(row)
        else:
            disadvantage_rows.append(row)
    return advantage_rows, disadvantage_rows


def _race_item_ids() -> set[int]:
    """Return item ids that are reserved as race-starting equipment definitions."""
    return set(RaceStartingItem.objects.values_list("item_id", flat=True))


def _character_item_image_url(character_item: CharacterItem) -> str:
    """Return the effective image URL for one owned item."""
    return str(getattr(character_item, "effective_image_url", "") or "")


def _annotate_item_effect_identification_payloads(
    character_item: CharacterItem,
    payloads: list[dict[str, object]],
    *,
    group_id: int | None,
) -> None:
    """Add SL effect-identification controls to already serialized item payloads."""
    if group_id is None:
        return
    identification_initialized = item_identification_initialized(character_item)
    identified_item_ids, identified_character_item_ids = identified_effect_id_sets(character_item)
    effect_identification_url = reverse(
        "update_group_item_effect_identification",
        args=[group_id, character_item.id],
    )
    for payload in payloads:
        source = str(payload.get("semantic_effect_source") or "")
        raw_ids = [
            int(value)
            for value in payload.get("semantic_effect_ids") or []
            if str(value).isdigit()
        ]
        if not raw_ids or source not in {"item", "character_item"}:
            continue
        identified_ids = (
            identified_item_ids
            if source == "item"
            else identified_character_item_ids
        )
        payload["effect_identification_url"] = effect_identification_url
        payload["identified_for_players"] = (
            all(effect_id in identified_ids for effect_id in raw_ids)
            if identification_initialized
            else True
        )


def _build_inventory_rows(
    character: Character,
    *,
    sl_effect_group_id: int | None = None,
) -> list[dict]:
    """Build prepared inventory rows for the unequipped inventory list."""
    inventory_rows: list[dict] = []
    race_item_ids = _race_item_ids()
    strength = int(character.get_engine().attributes().get(ATTR_ST, 0) or 0)

    inventory_items = list(
        CharacterItem.objects
        .filter(
            Q(owner=character, equipped=False)
            | (Q(original_owner_character=character) & ~Q(owner=character))
        )
        .select_related(
            "item",
            "original_owner_character",
            "item__rangedweaponstats",
            "item__armorstats",
            "item__shieldstats",
        )
        .prefetch_related(
            "item__runes",
            "item__weapon_stats",
            "item__weapon_stats__damage_source",
            "runes",
            "rune_specs__rune",
            "item_runes__rune",
            "transfers__recipient",
            "permission_grants",
        )
    )

    inventory_items.sort(
        key=lambda entry: ItemEngine(entry).get_name().lower()
    )

    modifiers_by_character_item_id = _load_character_item_modifier_payloads(
        inventory_items,
        include_unidentified=sl_effect_group_id is not None,
    )

    for character_item in inventory_items:
        item = character_item.item
        pending_transfer = pending_transfer_for_item(character_item)

        is_gm_edit_pending = bool(
            pending_transfer
            and pending_transfer.transfer_kind == ItemTransfer.TransferKind.GM_EDIT
        )

        is_current_holder = character_item.owner_id == character.id
        is_original_owner = (
            character_item.original_owner_character_id == character.id
        )
        is_foreign_held = is_original_owner and not is_current_holder
        is_borrowed = is_current_holder and not is_original_owner
        can_use_item = is_current_holder and pending_transfer is None

        active_grants = {}

        for grant in character_item.permission_grants.all():
            if not grant.active:
                continue

            if grant.permission == "consume_final":
                if grant.grantee_id is None:
                    active_grants.setdefault(
                        grant.permission,
                        grant,
                    )

            elif (
                grant.grantee_id == character_item.owner_id
                and grant.ownership_version == character_item.ownership_version
            ):
                active_grants.setdefault(
                    grant.permission,
                    grant,
                )

        can_destroy = has_item_permission(
            character_item,
            "destroy",
            character,
        )

        can_consume_final = has_item_permission(
            character_item,
            "consume_final",
            character,
        )

        is_race_item = item.id in race_item_ids

        item_engine = ItemEngine(character_item)
        weapon_stats = item_engine._get_weapon_stats()
        display = resolve_character_item_display(
            character_item,
            getattr(character, "owner", None),
            preview_player=True,
        )

        item_name = display.name
        quality = quality_payload(
            item_engine.get_effective_quality()
        )

        stored_modifier_payloads = modifiers_by_character_item_id.get(
            character_item.id,
            [],
        )
        _annotate_item_effect_identification_payloads(
            character_item,
            stored_modifier_payloads,
            group_id=sl_effect_group_id,
        )
        sl_reveal_url = (
            reverse("reveal_group_item", args=[sl_effect_group_id, character_item.id])
            if sl_effect_group_id is not None
            else ""
        )
        sl_hide_url = (
            reverse("hide_group_item", args=[sl_effect_group_id, character_item.id])
            if sl_effect_group_id is not None
            else ""
        )

        (
            visible_magic_effect_summary,
            magic_modifier_payloads,
        ) = _merge_magic_effect_payloads(
            effect_summary=_character_item_effect_summary_for_view(
                character_item,
                sl_effect_group_id=sl_effect_group_id,
            ),
            modifier_payloads=stored_modifier_payloads,
        )

        tooltip_text = ""

        item_description = str(
            display.description or ""
        ).strip()

        brew_requirement_line = (
            _build_alchemical_brew_requirement_line(
                item
            )
        )

        if brew_requirement_line:
            item_description = "\n\n".join(
                part
                for part in (
                    item_description,
                    brew_requirement_line,
                )
                if part
            )
        item_tooltip_rows = _filter_item_tooltip_rows_for_display(
            _build_item_tooltip_rows(
                item_engine,
                item,
                strength=strength,
                modifier_payloads=magic_modifier_payloads,
            ),
            display.hidden_field_keys,
            include_hidden_values=sl_effect_group_id is not None,
        )

        if (
            not is_race_item
            and item.item_type in QUALITY_TOOLTIP_TYPES
        ):
            tooltip_text = _format_item_tooltip(
                description=item_description,
                quality_label=quality["label"],
                quality_color=quality["color"],
                detail_rows=(
                    item_tooltip_rows
                    + _build_weapon_symbol_tooltip_rows(
                        item_engine
                    )
                    + _build_character_item_magic_tooltip_rows(
                        effect_summary=visible_magic_effect_summary,
                        modifier_payloads=magic_modifier_payloads,
                        include_condition_blocked=sl_effect_group_id is not None,
                    )
                    + _build_character_item_rune_tooltip_rows(
                        item=item,
                        character_item=character_item,
                    )
                ),
            )

        elif item_description:
            tooltip_text = _format_item_tooltip(
                description=item_description,
                detail_rows=(
                    item_tooltip_rows
                    + _build_weapon_symbol_tooltip_rows(
                        item_engine
                    )
                    + _build_character_item_magic_tooltip_rows(
                        effect_summary=visible_magic_effect_summary,
                        modifier_payloads=magic_modifier_payloads,
                        include_condition_blocked=sl_effect_group_id is not None,
                    )
                    + _build_character_item_rune_tooltip_rows(
                        item=item,
                        character_item=character_item,
                    )
                ),
            )

        active_rune_ids = [
            item_rune.rune_id
            for item_rune in character_item.item_runes.all()
            if item_rune.is_active
        ] or [
            rune.id
            for rune in character_item.runes.all()
        ]

        item_image_url = display.image_url

        equip_drop_zones = []

        if (
            item.item_type in Item.weapon_item_type_values()
            or item.item_type == Item.ItemType.SHIELD
        ):
            equip_drop_zones.append("weapon")

        elif (
            item.item_type in EQUIPPABLE_ITEM_TYPES
            or character_item.is_magic_effective
        ):
            equip_drop_zones.append("armor")

        inventory_rows.append(
            {
                "character_item": character_item,
                "item": item,
                "item_display": display,
                "item_card": build_character_item_card_context(
                    character_item,
                    getattr(character, "owner", None),
                    preview_player=True,
                    strength=strength,
                    modifier_payloads=stored_modifier_payloads,
                ),
                "sl_reveal_url": sl_reveal_url,
                "sl_hide_url": sl_hide_url,
                "tooltip_hidden_fields": ",".join(sorted(display.hidden_field_keys)),
                "item_name": item_name,
                "has_runes": _character_item_has_visible_runes(
                    item=item,
                    character_item=character_item,
                ),
                "rune_rows": _collect_rune_rows(
                    item=item,
                    character_item=character_item,
                ),
                "display_name": (
                    f"{character_item.amount}x {item_name}"
                    if item.stackable
                    else item_name
                ),
                "quality": (
                    ""
                    if is_race_item or "quality" in display.hidden_field_keys
                    else quality["value"]
                ),
                "quality_label": (
                    ""
                    if is_race_item or "quality" in display.hidden_field_keys
                    else display.quality_label
                ),
                "quality_color": (
                    ""
                    if is_race_item or "quality" in display.hidden_field_keys
                    else quality["color"]
                ),
                "tooltip_subtitle": " - ".join(
                    part
                    for part in [
                        display.item_type,
                        (
                            ""
                            if is_race_item
                            else display.quality_label
                        ),
                    ]
                    if part
                ),
                "item_image_url": item_image_url,
                "tooltip_text": (
                    ""
                    if is_gm_edit_pending
                    else tooltip_text
                ),
                "is_stored": (
                    bool(character_item.stored)
                    if is_current_holder
                    else False
                ),
                "is_foreign_held": is_foreign_held,
                "is_borrowed": is_borrowed,
                "foreign_holder_name": (
                    character_item.owner.name
                    if is_foreign_held
                    else ""
                ),
                "pending_transfer": pending_transfer,
                "is_transfer_pending": pending_transfer is not None,
                "is_gm_edit_pending": is_gm_edit_pending,
                "can_recall_transfer": (
                    is_current_holder
                    and pending_transfer is not None
                    and pending_transfer.sender_id == character.id
                    and not is_gm_edit_pending
                ),
                "can_manage_storage": can_use_item,
                "can_transfer": (
                    can_use_item
                    and not character_item.equip_locked
                ),
                "can_grant_transfer_permissions": (
                    is_current_holder
                    and is_original_owner
                ),
                "can_consume": (
                    can_use_item
                    and item.stackable
                    and item.is_consumable
                    and (
                        character_item.amount > 1
                        or can_consume_final
                    )
                ),
                "can_destroy": (
                    can_use_item
                    and can_destroy
                ),
                "can_enforce_original_ownership": (
                    is_original_owner
                    and is_foreign_held
                ),
                "can_manage_permissions": is_foreign_held,
                "can_return_to_original_owner": (
                    is_borrowed
                    and can_use_item
                    and not character_item.equip_locked
                ),
                "consume_grant": active_grants.get(
                    "consume_final"
                ),
                "sell_grant": active_grants.get(
                    "sell"
                ),
                "destroy_grant": active_grants.get(
                    "destroy"
                ),
                "can_equip": (
                    can_use_item
                    and (
                        item.item_type in EQUIPPABLE_ITEM_TYPES
                        or character_item.is_magic_effective
                    )
                ),
                "equip_drop_zone": (
                    equip_drop_zones[0]
                    if equip_drop_zones
                    else ""
                ),
                "equip_drop_zones": ",".join(
                    equip_drop_zones
                ),
                "can_socket_runes": (
                    can_use_item
                    and is_original_owner
                ),
                "equip_label": "Anlegen",
                "extra_rune_ids": active_rune_ids,
                "rune_specs_json": json.dumps(
                    _serialize_character_item_rune_specs(
                        character_item
                    )
                ),
                "description": (
                    display.description
                ),
                "is_character_item_magic": bool(
                    character_item.is_magic
                ),
                "magic_effect_summary": visible_magic_effect_summary,
                "magic_modifier_payloads": magic_modifier_payloads,
                "magic_modifier_payloads_json": json.dumps(
                    magic_modifier_payloads
                ),
                "modify_payload_json": json.dumps(
                    {
                        "name": item_name,
                        "price": item_engine.get_base_price(),
                        "weight": str(
                            item_engine._get_override_value(
                                "weight_override",
                                item.weight,
                            )
                        ),
                        "invested_cp": (
                            character_item.invested_cp
                            or item.invested_cp
                            or ""
                        ),
                        "invested_cp_steps": (
                            item.invested_cp_steps
                            or ""
                        ),
                        "size_class": item_engine.get_size_class(),
                        "not_buyable": bool(item.not_buyable),
                        "not_sellable": bool(item.not_sellable),
                        "weapon_type": item_engine.get_weapon_type(),
                        "weapon_min_st": item_engine.get_weapon_min_st(),
                        "weapon_maneuver_attribute": (
                            item_engine.get_weapon_maneuver_attribute_mode()
                        ),
                        "weapon_damage_source": getattr(
                            item_engine._get_override_value(
                                "weapon_damage_source_override",
                                getattr(
                                    weapon_stats,
                                    "damage_source",
                                    None,
                                ),
                            ),
                            "id",
                            "",
                        ),
                        "weapon_damage_dice_amount": (
                            item_engine._get_override_value(
                                "weapon_damage_dice_amount_override",
                                getattr(
                                    weapon_stats,
                                    "damage_dice_amount",
                                    "",
                                ),
                            )
                        ),
                        "weapon_damage_dice_faces": (
                            item_engine._get_override_value(
                                "weapon_damage_dice_faces_override",
                                getattr(
                                    weapon_stats,
                                    "damage_dice_faces",
                                    "",
                                ),
                            )
                        ),
                        "weapon_damage_flat_operator": (
                            item_engine._get_override_value(
                                "weapon_damage_flat_operator_override",
                                getattr(
                                    weapon_stats,
                                    "damage_flat_operator",
                                    "",
                                ),
                            )
                        ),
                        "weapon_damage_flat_bonus": (
                            item_engine._get_override_value(
                                "weapon_damage_flat_bonus_override",
                                getattr(
                                    weapon_stats,
                                    "damage_flat_bonus",
                                    "",
                                ),
                            )
                        ),
                        "weapon_wield_mode": item_engine.get_weapon_wield_mode(),
                        "weapon_damage_type": item_engine.get_weapon_damage_type(),
                        "weapon_h2_dice_amount": (
                            item_engine._get_override_value(
                                "weapon_h2_dice_amount_override",
                                getattr(
                                    weapon_stats,
                                    "h2_dice_amount",
                                    "",
                                ),
                            )
                        ),
                        "weapon_h2_dice_faces": (
                            item_engine._get_override_value(
                                "weapon_h2_dice_faces_override",
                                getattr(
                                    weapon_stats,
                                    "h2_dice_faces",
                                    "",
                                ),
                            )
                        ),
                        "weapon_h2_flat_operator": (
                            item_engine._get_override_value(
                                "weapon_h2_flat_operator_override",
                                getattr(
                                    weapon_stats,
                                    "h2_flat_operator",
                                    "",
                                ),
                            )
                        ),
                        "weapon_h2_flat_bonus": (
                            item_engine._get_override_value(
                                "weapon_h2_flat_bonus_override",
                                getattr(
                                    weapon_stats,
                                    "h2_flat_bonus",
                                    "",
                                ),
                            )
                        ),
                        "weapon_h2_damage_type": (
                            item_engine.get_weapon_h2_damage_type()
                        ),
                        "armor_rs_total": (
                            item_engine._get_override_value(
                                "armor_rs_total_override",
                                getattr(
                                    getattr(
                                        item,
                                        "armorstats",
                                        None,
                                    ),
                                    "rs_total",
                                    "",
                                ),
                            )
                        ),
                        "armor_encumbrance": (
                            item_engine._get_override_value(
                                "armor_encumbrance_override",
                                getattr(
                                    getattr(
                                        item,
                                        "armorstats",
                                        None,
                                    ),
                                    "encumbrance",
                                    "",
                                ),
                            )
                        ),
                        "armor_min_st": item_engine.get_armor_min_st(),
                        "shield_rs": item_engine.get_effective_shield_rs(),
                        "shield_encumbrance": item_engine.get_shield_bel_raw(),
                        "shield_min_st": item_engine.get_shield_min_st(),
                    }
                ),
            }
        )

    return inventory_rows


def _build_inventory_total_weight_display(character: Character) -> str:
    """Return the summed weight of all non-stored carried and equipped items."""
    total_weight = ItemEngine.active_inventory_weight_for_character(character)
    return format_compact_number(total_weight)


def _build_weapon_rows(engine, *, sl_effect_group_id: int | None = None) -> list[dict]:
    """Build prepared weapon rows with flattened display profiles."""
    weapon_rows: list[dict] = []
    race_item_ids = _race_item_ids()
    raw_rows = engine.equipped_weapon_rows()
    character_items = [row["character_item"] for row in raw_rows]
    modifiers_by_character_item_id = _load_character_item_modifier_payloads(
        character_items,
        include_unidentified=sl_effect_group_id is not None,
    )
    profile_rows_by_item: OrderedDict[int, list[dict]] = OrderedDict()
    for row in raw_rows:
        character_item = row["character_item"]
        profile_rows_by_item.setdefault(character_item.pk, []).append(row)

    expanded_row_count_by_item: dict[int, int] = {}
    for item_id, profile_rows in profile_rows_by_item.items():
        expanded_row_count_by_item[item_id] = sum(
            max(1, len(list(profile_row.get("maneuver_options") or [])))
            for profile_row in profile_rows
        )

    rendered_rows_by_item: dict[int, int] = {}
    for row in raw_rows:
        display = resolve_character_item_display(
            row["character_item"],
            getattr(engine.character, "owner", None),
            preview_player=True,
        )
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(row["quality"])
        character_item_id = row["character_item"].pk
        total_rendered_rows = rendered_rows_by_item.get(character_item_id, 0)
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        _annotate_item_effect_identification_payloads(
            row["character_item"],
            magic_modifier_payloads,
            group_id=sl_effect_group_id,
        )
        sl_reveal_url = (
            reverse("reveal_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        sl_hide_url = (
            reverse("hide_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        item_image_url = display.image_url
        item_name = display.name
        display_options = list(row.get("maneuver_options") or [])
        if not display_options:
            display_options = [
                {
                    "attribute_code": str(row.get("maneuver_attribute_label") or "ST"),
                    "attribute_modifier": int(row.get("maneuver_attribute_modifier", 0) or 0),
                    "attribute_modifier_display": format_modifier(int(row.get("maneuver_attribute_modifier", 0) or 0)),
                    "total_modifier": int(row.get("total_maneuver_modifier", 0) or 0),
                    "total_modifier_display": str(row.get("maneuver_mod_display") or "0"),
                    "with_bel": int(row.get("with_bel", 0) or 0),
                    "with_bel_display": str(row.get("maneuver_with_bel_display") or "0"),
                }
            ]
        for option_index, maneuver_option in enumerate(display_options):
            rendered_row_index = total_rendered_rows + option_index
            display_row = {
                **row,
                "selected_maneuver_option": maneuver_option,
                "maneuver_option_index": option_index,
                "is_primary_profile": rendered_row_index == 0,
                "is_last_profile": rendered_row_index == (expanded_row_count_by_item.get(character_item_id, 1) - 1),
                "show_weapon_name": rendered_row_index == 0,
                "item_name": item_name,
                "weapon_display_name": item_name,
                "show_maneuver_badge": len(display_options) > 1,
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_subtitle": " - ".join(
                    part for part in [display.item_type, "" if is_race_item else display.quality_label] if part
                ),
                "item_image_url": item_image_url,
                "sl_reveal_url": sl_reveal_url,
                "sl_hide_url": sl_hide_url,
                "tooltip_hidden_fields": _tooltip_hidden_fields(row["character_item"]),
                "tooltip_text": _format_item_tooltip(
                    description=display.description,
                    quality_label="" if is_race_item else display.quality_label,
                    quality_color="" if is_race_item else display.quality_color,
                    detail_rows=(
                        _filter_item_tooltip_rows_for_display(
                            _build_item_tooltip_rows(
                                ItemEngine(row["character_item"]),
                                row["item"],
                                strength=int(engine.attributes().get(ATTR_ST, 0) or 0),
                            ),
                            set(_tooltip_hidden_fields(row["character_item"]).split(",")),
                            include_hidden_values=sl_effect_group_id is not None,
                        )
                        + _build_weapon_symbol_tooltip_rows(ItemEngine(row["character_item"]))
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=_character_item_effect_summary_for_view(
                                row["character_item"],
                                sl_effect_group_id=sl_effect_group_id,
                            ),
                            modifier_payloads=magic_modifier_payloads,
                            include_condition_blocked=sl_effect_group_id is not None,
                        )
                        + _build_character_item_rune_tooltip_rows(
                            item=row["item"],
                            character_item=row["character_item"],
                        )
                    ),
                ),
                "has_runes": _character_item_has_visible_runes(
                    item=row["item"],
                    character_item=row["character_item"],
                ),
                "rune_rows": _collect_rune_rows(item=row["item"], character_item=row["character_item"]),
                "maneuver_mod_display": maneuver_option["total_modifier_display"],
                "with_bel_value": int(row.get("with_bel", 0) or 0),
                "maneuver_with_bel_display": maneuver_option["with_bel_display"],
                "maneuver_attribute_label": maneuver_option["attribute_code"],
                "maneuver_attribute_modifier": int(maneuver_option.get("attribute_modifier", 0) or 0),
                "total_maneuver_modifier": int(maneuver_option.get("total_modifier", 0) or 0),
                "calculation_tooltip": "",
                "can_unequip": not row["character_item"].equip_locked,
            }
            conditional_modifiers = _conditional_weapon_modifier_lines(
                engine,
                display_row,
            )

            display_row["has_conditional_modifiers"] = bool(
                conditional_modifiers
            )

            display_row["calculation_tooltip"] = _build_weapon_calculation_tooltip(
                engine,
                display_row,
            )
            weapon_rows.append(display_row)
        rendered_rows_by_item[character_item_id] = total_rendered_rows + len(display_options)
    attribute_sort_order = {"ST": 0, "GE": 1}
    sorted_weapon_rows: list[dict] = []
    rows_by_character_item_id: OrderedDict[int, list[dict]] = OrderedDict()
    for row in weapon_rows:
        rows_by_character_item_id.setdefault(int(row["character_item"].pk), []).append(row)
    for item_rows in rows_by_character_item_id.values():
        item_rows.sort(
            key=lambda entry: (
                attribute_sort_order.get(str(entry.get("maneuver_attribute_label") or ""), 99),
                str(entry.get("mode_label") or ""),
                int(entry.get("maneuver_option_index", 0) or 0),
            )
        )
        for index, entry in enumerate(item_rows):
            entry["is_primary_profile"] = index == 0
            entry["show_weapon_name"] = index == 0
            entry["is_last_profile"] = index == (len(item_rows) - 1)
        sorted_weapon_rows.extend(item_rows)
    return sorted_weapon_rows


def _equipment_icon_key(row: dict) -> str:
    item = row["item"]
    item_type = item.item_type
    if item_type == Item.ItemType.RING:
        return "ring"
    if item_type == Item.ItemType.AMULET:
        return "amulet"
    if item_type == Item.ItemType.SHIELD:
        return "shield"
    if item_type == Item.ItemType.CLOTHING:
        return "clothing"
    if item_type in Item.weapon_item_type_values():
        return "weapon"
    armor_stats = row.get("armor_stats") or getattr(item, "armorstats", None)
    if armor_stats is not None:
        covered_zones = set(armor_stats.covered_zones())
        if all(zone in covered_zones for zone in armor_stats.MAIN_ZONE_FIELDS):
            return "full_armor"
        if covered_zones & {"head", "face", "eyes", "neck"}:
            return "helmet"
        if covered_zones & {"torso", "organs", "soft_tissue"}:
            return "chest_armor"
        if covered_zones & {"hand_left", "hand_right", "arm_left", "arm_right"}:
            return "gloves"
        if covered_zones & {"foot_left", "foot_right", "leg_left", "leg_right"}:
            return "boots"
        return "armor"
    if item_type in Item.armor_item_type_values():
        return "armor"
    if item.is_magic_effective:
        return "magic_item"
    return "item"


def _build_armor_rows(engine, *, sl_effect_group_id: int | None = None) -> list[dict]:
    """Build prepared armor, clothing, and shield rows for the equipment panel."""
    armor_rows: list[dict] = []
    race_item_ids = _race_item_ids()
    armor_equipped_rows = engine.equipped_armor_rows()
    clothing_equipped_rows = engine.equipped_clothing_rows()
    magic_equipped_rows = engine.equipped_magic_item_rows()
    shield_equipped_rows = engine.equipped_shield_rows()
    all_character_items = [
        row["character_item"]
        for row in (*armor_equipped_rows, *clothing_equipped_rows, *magic_equipped_rows, *shield_equipped_rows)
    ]
    modifiers_by_character_item_id = _load_character_item_modifier_payloads(
        all_character_items,
        include_unidentified=sl_effect_group_id is not None,
    )
    for row in armor_equipped_rows:
        display = resolve_character_item_display(
            row["character_item"],
            getattr(engine.character, "owner", None),
            preview_player=True,
        )
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(row["quality"])
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        _annotate_item_effect_identification_payloads(
            row["character_item"],
            magic_modifier_payloads,
            group_id=sl_effect_group_id,
        )
        sl_reveal_url = (
            reverse("reveal_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        sl_hide_url = (
            reverse("hide_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        item_image_url = display.image_url
        item_name = display.name
        armor_rows.append(
            {
                **row,
                "item_name": item_name,
                "kind": "armor",
                "equipment_icon_key": _equipment_icon_key(row),
                "is_magic": bool(row["item"].is_magic or row["character_item"].is_magic),
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_subtitle": " - ".join(
                    part for part in [display.item_type, "" if is_race_item else display.quality_label] if part
                ),
                "item_image_url": item_image_url,
                "sl_reveal_url": sl_reveal_url,
                "sl_hide_url": sl_hide_url,
                "tooltip_hidden_fields": _tooltip_hidden_fields(row["character_item"]),
                "summary": (
                    f"{item_name} "
                    f"(RS {row['rs']} | Bel {row['bel_effective']} | "
                    f"Min-St {row['min_st'] if row['min_st'] is not None else '-'})"
                ),
                "tooltip_text": _format_item_tooltip(
                    description=display.description,
                    quality_label="" if is_race_item else display.quality_label,
                    quality_color="" if is_race_item else display.quality_color,
                    detail_rows=(
                        _filter_item_tooltip_rows_for_display(
                            _build_item_tooltip_rows(
                                ItemEngine(row["character_item"]),
                                row["item"],
                                armor_rs=int(row["rs"] or 0),
                                armor_encumbrance=int(row["bel_effective"] or 0),
                            ),
                            set(_tooltip_hidden_fields(row["character_item"]).split(",")),
                            include_hidden_values=sl_effect_group_id is not None,
                        )
                        + _build_weapon_symbol_tooltip_rows(ItemEngine(row["character_item"]))
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=_character_item_effect_summary_for_view(
                                row["character_item"],
                                sl_effect_group_id=sl_effect_group_id,
                            ),
                            modifier_payloads=magic_modifier_payloads,
                            include_condition_blocked=sl_effect_group_id is not None,
                        )
                        + _build_character_item_rune_tooltip_rows(
                            item=row["item"],
                            character_item=row["character_item"],
                        )
                    ),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in clothing_equipped_rows:
        display = resolve_character_item_display(
            row["character_item"],
            getattr(engine.character, "owner", None),
            preview_player=True,
        )
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(row["quality"])
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        _annotate_item_effect_identification_payloads(
            row["character_item"],
            magic_modifier_payloads,
            group_id=sl_effect_group_id,
        )
        sl_reveal_url = (
            reverse("reveal_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        sl_hide_url = (
            reverse("hide_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        item_image_url = display.image_url
        item_name = display.name
        armor_rows.append(
            {
                **row,
                "item_name": item_name,
                "kind": "clothing",
                "equipment_icon_key": _equipment_icon_key(row),
                "is_magic": bool(row["item"].is_magic or row["character_item"].is_magic),
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_subtitle": " - ".join(
                    part for part in [display.item_type, "" if is_race_item else display.quality_label] if part
                ),
                "item_image_url": item_image_url,
                "sl_reveal_url": sl_reveal_url,
                "sl_hide_url": sl_hide_url,
                "tooltip_hidden_fields": _tooltip_hidden_fields(row["character_item"]),
                "summary": f"{item_name} (Kleidung)",
                "tooltip_text": _format_item_tooltip(
                    description=display.description,
                    quality_label="" if is_race_item else display.quality_label,
                    quality_color="" if is_race_item else display.quality_color,
                    detail_rows=(
                        _filter_item_tooltip_rows_for_display(
                            _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"]),
                            set(_tooltip_hidden_fields(row["character_item"]).split(",")),
                            include_hidden_values=sl_effect_group_id is not None,
                        )
                        + _build_weapon_symbol_tooltip_rows(ItemEngine(row["character_item"]))
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=_character_item_effect_summary_for_view(
                                row["character_item"],
                                sl_effect_group_id=sl_effect_group_id,
                            ),
                            modifier_payloads=magic_modifier_payloads,
                            include_condition_blocked=sl_effect_group_id is not None,
                        )
                        + _build_character_item_rune_tooltip_rows(
                            item=row["item"],
                            character_item=row["character_item"],
                        )
                    ),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in magic_equipped_rows:
        display = resolve_character_item_display(
            row["character_item"],
            getattr(engine.character, "owner", None),
            preview_player=True,
        )
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(row["quality"])
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        _annotate_item_effect_identification_payloads(
            row["character_item"],
            magic_modifier_payloads,
            group_id=sl_effect_group_id,
        )
        sl_reveal_url = (
            reverse("reveal_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        sl_hide_url = (
            reverse("hide_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        item_image_url = display.image_url
        item_name = display.name
        armor_rows.append(
            {
                **row,
                "item_name": item_name,
                "kind": "magic_item",
                "equipment_icon_key": _equipment_icon_key(row),
                "is_magic": bool(row["item"].is_magic or row["character_item"].is_magic),
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_subtitle": " - ".join(
                    part for part in [display.item_type, "" if is_race_item else display.quality_label] if part
                ),
                "item_image_url": item_image_url,
                "sl_reveal_url": sl_reveal_url,
                "sl_hide_url": sl_hide_url,
                "tooltip_hidden_fields": _tooltip_hidden_fields(row["character_item"]),
                "summary": f"{item_name} (Magischer Gegenstand)",
                "tooltip_text": _format_item_tooltip(
                    description=display.description,
                    quality_label="" if is_race_item else display.quality_label,
                    quality_color="" if is_race_item else display.quality_color,
                    detail_rows=(
                        _filter_item_tooltip_rows_for_display(
                            _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"]),
                            set(_tooltip_hidden_fields(row["character_item"]).split(",")),
                            include_hidden_values=sl_effect_group_id is not None,
                        )
                        + _build_weapon_symbol_tooltip_rows(ItemEngine(row["character_item"]))
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=_character_item_effect_summary_for_view(
                                row["character_item"],
                                sl_effect_group_id=sl_effect_group_id,
                            ),
                            modifier_payloads=magic_modifier_payloads,
                            include_condition_blocked=sl_effect_group_id is not None,
                        )
                        + _build_character_item_rune_tooltip_rows(
                            item=row["item"],
                            character_item=row["character_item"],
                        )
                    ),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in shield_equipped_rows:
        display = resolve_character_item_display(
            row["character_item"],
            getattr(engine.character, "owner", None),
            preview_player=True,
        )
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(row["quality"])
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        _annotate_item_effect_identification_payloads(
            row["character_item"],
            magic_modifier_payloads,
            group_id=sl_effect_group_id,
        )
        sl_reveal_url = (
            reverse("reveal_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        sl_hide_url = (
            reverse("hide_group_item", args=[sl_effect_group_id, row["character_item"].id])
            if sl_effect_group_id is not None
            else ""
        )
        item_image_url = display.image_url
        item_name = display.name
        armor_rows.append(
            {
                **row,
                "item_name": item_name,
                "kind": "shield",
                "equipment_icon_key": _equipment_icon_key(row),
                "is_magic": bool(row["item"].is_magic or row["character_item"].is_magic),
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_subtitle": " - ".join(
                    part for part in [display.item_type, "" if is_race_item else display.quality_label] if part
                ),
                "item_image_url": item_image_url,
                "sl_reveal_url": sl_reveal_url,
                "sl_hide_url": sl_hide_url,
                "tooltip_hidden_fields": _tooltip_hidden_fields(row["character_item"]),
                "summary": f"{item_name} (Schild-RS {row['rs']} | Bel {row['bel_effective']} | Min-St {row['min_st'] or '-'})",
                "tooltip_text": _format_item_tooltip(
                    description=display.description,
                    quality_label="" if is_race_item else display.quality_label,
                    quality_color="" if is_race_item else display.quality_color,
                    detail_rows=(
                        _filter_item_tooltip_rows_for_display(
                            _build_item_tooltip_rows(
                                ItemEngine(row["character_item"]),
                                row["item"],
                                shield_encumbrance=int(row["bel_effective"] or 0),
                            ),
                            set(_tooltip_hidden_fields(row["character_item"]).split(",")),
                            include_hidden_values=sl_effect_group_id is not None,
                        )
                        + _build_weapon_symbol_tooltip_rows(ItemEngine(row["character_item"]))
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=_character_item_effect_summary_for_view(
                                row["character_item"],
                                sl_effect_group_id=sl_effect_group_id,
                            ),
                            modifier_payloads=magic_modifier_payloads,
                            include_condition_blocked=sl_effect_group_id is not None,
                        )
                        + _build_character_item_rune_tooltip_rows(
                            item=row["item"],
                            character_item=row["character_item"],
                        )
                    ),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    return armor_rows


_SUPPORT_ICON_COMPUTED = "\u16C9"   # ᛉ — calculated by engine
_SUPPORT_ICON_DESCRIPTIVE = "\u16A8"  # ᚨ — rule text only
_SUPPORT_TOOLTIP_COMPUTED = (
    "Automatisch berechnet\u2009\u2013\u2009"
    "dieser Effekt wird vom System ermittelt und auf die relevanten Werte angewendet."
)
_SUPPORT_TOOLTIP_DESCRIPTIVE = (
    "Regeltext\u2009\u2013\u2009"
    "dieser Effekt wird nicht automatisch berechnet "
    "und muss eigenst\u00e4ndig nachgehalten werden."
)


def _support_icon(support_level: str) -> tuple[str, str]:
    """Return (icon, tooltip) for a technique's support_level value."""
    from charsheet.models.techniques import Technique
    if support_level == Technique.SupportLevel.DESCRIPTIVE:
        return _SUPPORT_ICON_DESCRIPTIVE, _SUPPORT_TOOLTIP_DESCRIPTIVE
    return _SUPPORT_ICON_COMPUTED, _SUPPORT_TOOLTIP_COMPUTED


def _build_school_technique_rows(character: Character, engine) -> tuple[list[dict], dict[int, int]]:
    """Build visible learned technique rows for the school panel."""
    schools = list(
        character.schools
        .select_related("school", "school__type")
        .order_by("school__type__name", "school__name")
    )
    school_levels = {entry.school_id: entry.level for entry in schools}
    school_technique_rows: list[dict] = []
    technique_specialization_names: dict[int, list[str]] = {}
    technique_specialization_descriptions: dict[int, list[str]] = {}
    learned_techniques_by_technique_id = {
        entry.technique_id: entry
        for entry in (
            CharacterTechnique.objects
            .filter(character=character)
            .select_related("technique")
        )
    }
    daemonic_powers_by_technique_id = {
        ownership.granting_technique_id: ownership.power
        for ownership in (
            CharacterDaemonicPower.objects
            .filter(character=character)
            .select_related("power", "power__tier", "granting_technique")
        )
        if (
            ownership.granting_technique.granted_daemonic_power_tier_id
            == ownership.power.tier_id
        )
    }
    for choice in (
        character.technique_choices
        .filter(selected_specialization__isnull=False)
        .select_related("technique", "selected_specialization")
    ):
        technique_specialization_names.setdefault(choice.technique_id, []).append(choice.selected_specialization.name)
        description_text = (choice.selected_specialization.description or "").strip()
        if description_text:
            technique_specialization_descriptions.setdefault(choice.technique_id, []).append(description_text)
    race_techniques = (
        RaceTechnique.objects
        .filter(race=character.race)
        .select_related("technique")
        .order_by("technique__name")
    )
    for race_link in race_techniques:
        technique = race_link.technique
        learned_technique = learned_techniques_by_technique_id.get(technique.id)
        specification_value = ((learned_technique.specification_value if learned_technique else "") or "").strip()
        entry_name = technique.name
        if technique.has_specification:
            entry_name = f"{technique.name}: {specification_value or '*'}"
        icon, icon_tooltip = _support_icon(technique.support_level)
        school_technique_rows.append(
            {
                "kind": "race_technique",
                "level": "",
                "school_name": character.race.name,
                "entry_name": entry_name,
                "description": technique.description,
                "can_edit_specification": bool(technique.has_specification),
                "specification_value": specification_value,
                "technique_id": technique.id,
                "support_level_icon": icon,
                "support_level_tooltip": icon_tooltip,
            }
        )
    race_row_count = len(school_technique_rows)
    if school_levels:
        techniques = (
            Technique.objects
            .filter(school_id__in=school_levels.keys())
            .select_related("school")
            .order_by("school__name", "level", "name")
        )
        for technique in techniques:
            if technique.level <= school_levels.get(technique.school_id, 0):
                if (
                    technique.school.name == "Bardenschule"
                    and technique.level == 10
                    and technique.name == "Erwachte Begabung"
                ):
                    continue
                learned_technique = learned_techniques_by_technique_id.get(technique.id)
                if technique.acquisition_type == Technique.AcquisitionType.CHOICE and learned_technique is None:
                    continue
                specification_value = ((learned_technique.specification_value if learned_technique else "") or "").strip()
                entry_name = technique.name
                if technique.has_specification:
                    entry_name = f"{technique.name}: {specification_value or '*'}"
                selected_specializations = technique_specialization_names.get(technique.id, [])
                selected_specialization_descriptions = technique_specialization_descriptions.get(technique.id, [])
                description_text = technique.description
                if selected_specializations:
                    rendered_specializations = ", ".join(selected_specializations)
                    entry_name = f"{rendered_specializations} ({technique.name})"
                    if selected_specialization_descriptions:
                        description_text = "\n\n".join(selected_specialization_descriptions)
                daemonic_power = daemonic_powers_by_technique_id.get(technique.id)
                tooltip_title = entry_name
                tooltip_subtitle = f"{technique.school.name} {_to_roman(technique.level)}"
                tooltip_text = description_text
                tooltip_card_key = f"technique:{technique.id}"
                if daemonic_power is not None:
                    entry_name = f"{entry_name}: {daemonic_power.name}"
                    tooltip_title = daemonic_power.name
                    tooltip_subtitle = f"Dämonische Kraft · {daemonic_power.tier.name}"
                    tooltip_parts = [
                        (daemonic_power.description or "").strip()
                        or "Keine Beschreibung"
                    ]
                    if daemonic_power.weakness_description:
                        tooltip_parts.append(
                            f"Schwäche: {daemonic_power.weakness_description.strip()}"
                        )
                    tooltip_text = "\n\n".join(tooltip_parts)
                    tooltip_card_key = f"daemonic-power:{daemonic_power.id}"
                icon, icon_tooltip = _support_icon(technique.support_level)
                school_technique_rows.append(
                    {
                        "kind": "technique",
                        "level": technique.level,
                        "level_label": _to_roman(technique.level),
                        "school_name": technique.school.name,
                        "school_id": technique.school_id,
                        "school_symbol": str(getattr(technique.school, "panel_symbol", "") or "").strip(),
                        "school_symbol_image_url": _school_symbol_image_url(technique.school),
                        "entry_name": entry_name,
                        "description": description_text,
                        "tooltip_title": tooltip_title,
                        "tooltip_subtitle": tooltip_subtitle,
                        "tooltip_text": tooltip_text,
                        "tooltip_card_key": tooltip_card_key,
                        "can_edit_specification": bool(technique.has_specification),
                        "specification_value": specification_value,
                        "technique_id": technique.id,
                        "support_level_icon": icon,
                        "support_level_tooltip": icon_tooltip,
                    }
                )
    if race_row_count and len(school_technique_rows) > race_row_count:
        school_technique_rows[race_row_count - 1]["show_group_separator"] = True
    for school_entry in schools:
        for specialization_entry in engine.character_specializations(school_entry.school_id):
            specialization = specialization_entry.specialization
            school_technique_rows.append(
                {
                    "kind": "specialization",
                    "level": "Spez.",
                    "level_label": "Spez.",
                    "school_name": school_entry.school.name,
                    "school_id": school_entry.school_id,
                    "school_symbol": str(getattr(school_entry.school, "panel_symbol", "") or "").strip(),
                    "school_symbol_image_url": _school_symbol_image_url(school_entry.school),
                    "entry_name": specialization.name,
                    "description": specialization.description,
                    "support_level_icon": _SUPPORT_ICON_DESCRIPTIVE,
                    "support_level_tooltip": _SUPPORT_TOOLTIP_DESCRIPTIVE,
                }
            )
    weapon_master_school = engine._weapon_master_school
    if weapon_master_school is not None and weapon_master_school.id in school_levels:
        mastered_entries = sorted(
            engine._weapon_mastery_entries_by_type.values(),
            key=lambda entry: (entry.pick_order, entry.weapon_type_label()),
        )
        for mastery in mastered_entries:
            maneuver_bonus, damage_bonus = mastery.maneuver_damage_bonus(school_levels[weapon_master_school.id])
            school_technique_rows.append(
                {
                    "kind": "weapon_mastery",
                    "level": mastery.pick_order,
                    "level_label": _to_roman(mastery.pick_order),
                    "school_name": weapon_master_school.name,
                    "school_id": weapon_master_school.id,
                    "school_symbol": str(getattr(weapon_master_school, "panel_symbol", "") or "").strip(),
                    "school_symbol_image_url": _school_symbol_image_url(weapon_master_school),
                    "entry_name": f"{mastery.weapon_type_label()} ({maneuver_bonus} / {damage_bonus})",
                    "description": "",
                    "support_level_icon": _SUPPORT_ICON_COMPUTED,
                    "support_level_tooltip": _SUPPORT_TOOLTIP_COMPUTED,
                }
            )
    return school_technique_rows, school_levels


def _group_school_technique_rows(
    school_technique_rows: list[dict],
    school_levels: dict[int, int],
    character: Character,
) -> tuple[list[dict], list[dict]]:
    """Split rows into race rows (flat) and school groups (collapsible).

    Returns (race_rows, school_groups) where each group is:
    {school_name, max_level, max_level_label, rows: [...]}.
    """
    race_rows: list[dict] = []
    groups: OrderedDict[str, dict] = OrderedDict()
    druid_options_by_school_id: dict[int, list[DruidCult]] = {}
    daemonic_patron_options_by_school_id: dict[int, list[DivineEntity]] = {}
    if school_levels:
        for cult in DruidCult.objects.filter(school_id__in=school_levels.keys()).order_by("name"):
            druid_options_by_school_id.setdefault(int(cult.school_id), []).append(cult)
        for entity in (
            DivineEntity.objects.filter(school_id__in=school_levels.keys())
            .select_related("school", "school__type")
            .order_by("name", "id")
        ):
            if _divine_entity_card_kind_label(entity) == "Dämon":
                daemonic_patron_options_by_school_id.setdefault(
                    int(entity.school_id),
                    [],
                ).append(entity)
    druid_binding = (
        CharacterDruidCult.objects.filter(character=character)
        .select_related("cult", "cult__school")
        .first()
    )
    selected_druid_cult_id = int(druid_binding.cult_id) if druid_binding is not None else None
    selected_druid_cult_name = (
        str(druid_binding.tradition_name or druid_binding.cult.name)
        if druid_binding is not None
        else ""
    )
    druid_cult_reset_warning = bool(selected_druid_cult_id) and (
        CharacterAspect.objects.filter(character=character, is_bonus_aspect=True).exists()
        or CharacterSpell.objects.filter(
            character=character,
            source_kind__in=(
                CharacterSpell.SourceKind.DIVINE_EXTRA,
                CharacterSpell.SourceKind.DIVINE_BONUS,
            ),
            spell__aspect_id__isnull=False,
        ).exists()
    )
    daemonic_patron_binding = (
        CharacterDivineEntity.objects.filter(character=character)
        .select_related("entity", "entity__school", "entity__school__type")
        .first()
    )
    selected_daemonic_patron_id = (
        int(daemonic_patron_binding.entity_id)
        if daemonic_patron_binding is not None
        and _divine_entity_card_kind_label(daemonic_patron_binding.entity) == "Dämon"
        else None
    )
    selected_daemonic_patron_name = (
        str(daemonic_patron_binding.custom_name or daemonic_patron_binding.entity.name)
        if selected_daemonic_patron_id and daemonic_patron_binding is not None
        else ""
    )

    for row in school_technique_rows:
        if row["kind"] == "race_technique":
            race_rows.append(row)
            continue
        school_name = row["school_name"]
        if school_name not in groups:
            # Determine the character's current max level in this school.
            school_id = row.get("school_id")
            current_level = school_levels.get(school_id, 0) if school_id else 0
            groups[school_name] = {
                "school_id": school_id,
                "school_name": school_name,
                "symbol": str(row.get("school_symbol") or "").strip(),
                "symbol_image_url": str(row.get("school_symbol_image_url") or "").strip(),
                "max_level": current_level,
                "max_level_label": _to_roman(current_level) if current_level else "",
                "druid_cult_options": druid_options_by_school_id.get(int(school_id or 0), []),
                "selected_druid_cult_id": selected_druid_cult_id,
                "selected_druid_cult_name": (
                    selected_druid_cult_name
                    if selected_druid_cult_id
                    and any(cult.id == selected_druid_cult_id for cult in druid_options_by_school_id.get(int(school_id or 0), []))
                    else ""
                ),
                "druid_cult_reset_warning": druid_cult_reset_warning,
                "daemonic_patron_options": daemonic_patron_options_by_school_id.get(int(school_id or 0), []),
                "selected_daemonic_patron_id": selected_daemonic_patron_id,
                "selected_daemonic_patron_name": (
                    selected_daemonic_patron_name
                    if selected_daemonic_patron_id
                    and any(
                        entity.id == selected_daemonic_patron_id
                        for entity in daemonic_patron_options_by_school_id.get(int(school_id or 0), [])
                    )
                    else ""
                ),
                "rows": [],
            }
        groups[school_name]["rows"].append(row)

    grouped_school_ids = {
        int(group["school_id"])
        for group in groups.values()
        if group.get("school_id")
    }
    missing_school_ids = [school_id for school_id in school_levels if int(school_id) not in grouped_school_ids]
    if missing_school_ids:
        for school in School.objects.filter(pk__in=missing_school_ids).order_by("type__name", "name"):
            current_level = int(school_levels.get(school.id, 0) or 0)
            groups[school.name] = {
                "school_id": school.id,
                "school_name": school.name,
                "symbol": str(getattr(school, "panel_symbol", "") or "").strip(),
                "symbol_image_url": _school_symbol_image_url(school),
                "max_level": current_level,
                "max_level_label": _to_roman(current_level) if current_level else "",
                "druid_cult_options": druid_options_by_school_id.get(int(school.id), []),
                "selected_druid_cult_id": selected_druid_cult_id,
                "selected_druid_cult_name": (
                    selected_druid_cult_name
                    if selected_druid_cult_id
                    and any(cult.id == selected_druid_cult_id for cult in druid_options_by_school_id.get(int(school.id), []))
                    else ""
                ),
                "druid_cult_reset_warning": druid_cult_reset_warning,
                "daemonic_patron_options": daemonic_patron_options_by_school_id.get(int(school.id), []),
                "selected_daemonic_patron_id": selected_daemonic_patron_id,
                "selected_daemonic_patron_name": (
                    selected_daemonic_patron_name
                    if selected_daemonic_patron_id
                    and any(
                        entity.id == selected_daemonic_patron_id
                        for entity in daemonic_patron_options_by_school_id.get(int(school.id), [])
                    )
                    else ""
                ),
                "rows": [],
            }

    if selected_daemonic_patron_id and daemonic_patron_binding is not None:
        patron_symbol_image_url = _image_field_url(
            daemonic_patron_binding.entity,
            "symbol_image",
        )
        if patron_symbol_image_url:
            patron_school_id = int(daemonic_patron_binding.entity.school_id)
            for group in groups.values():
                if int(group.get("school_id") or 0) == patron_school_id:
                    group["symbol"] = ""
                    group["symbol_image_url"] = patron_symbol_image_url
                    break

    return race_rows, list(groups.values())


def _build_daemonic_power_panel(character: Character, engine) -> list[dict]:
    """Build active character powers grouped by deterministic tier ordering."""
    groups: OrderedDict[int, dict] = OrderedDict()
    ownerships = (
        CharacterDaemonicPower.objects.filter(character=character)
        .select_related(
            "power",
            "power__tier",
            "granting_technique",
            "granting_technique__school",
        )
        .order_by(
            "power__tier__sort_number",
            "power__tier__name",
            "power__name",
            "id",
        )
    )
    for ownership in ownerships:
        technique = ownership.granting_technique
        if technique.granted_daemonic_power_tier_id != ownership.power.tier_id:
            continue
        state = engine.technique_state(technique)
        if not state["learned"] or not state["available"]:
            continue
        tier = ownership.power.tier
        group = groups.setdefault(
            tier.id,
            {
                "id": tier.id,
                "name": tier.name,
                "slug": tier.slug,
                "sort_number": tier.sort_number,
                "powers": [],
            },
        )
        group["powers"].append(
            {
                "id": ownership.power_id,
                "name": ownership.power.name,
                "slug": ownership.power.slug,
                "description": ownership.power.description,
                "weakness_description": ownership.power.weakness_description,
                "modifier": engine.modifier_engine.resolve_numeric_total(
                    "daemonic_power",
                    ownership.power.slug,
                ),
                "granting_technique": technique.name,
                "granting_school": technique.school.name,
            }
        )
        group["powers"][-1]["modifier_display"] = (
            format_modifier(group["powers"][-1]["modifier"])
            if group["powers"][-1]["modifier"]
            else ""
        )
    return list(groups.values())


def _build_weapon_mastery_arcana_panel(engine) -> dict | None:
    """Build context for the weapon mastery arcana tab, or None when not applicable."""
    weapon_master_school_entry = engine._weapon_master_school_entry
    if weapon_master_school_entry is None:
        return None
    entries = engine._weapon_mastery_arcana_entries
    mastered_entries = sorted(
        engine._weapon_mastery_entries_by_type.values(),
        key=lambda mastery: (mastery.pick_order, mastery.weapon_type_label()),
    )
    bonus_entries = []
    rune_entries = []
    for index, entry in enumerate(entries):
        related_mastery = mastered_entries[index] if index < len(mastered_entries) else None
        related_weapon_type = related_mastery.weapon_type_label() if related_mastery is not None else "Nicht festgelegt"
        if entry.kind == CharacterWeaponMasteryArcana.ArcanaKind.RUNE and entry.rune_id:
            rune_entries.append({
                "kind": "rune",
                "label": entry.rune.name,
                "description": _rune_card_description(entry.rune),
                "image": _rune_image_url(entry.rune),
                "weapon_type_label": related_weapon_type,
            })
        elif entry.kind == CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY:
            bonus_entries.append({
                "kind": "bonus_capacity",
                "label": "+1/+1 Bonuskapazität",
                "description": "Erhöht die beherrschbare magische Bonuskapazität um +1/+1.",
            })
            bonus_entries[-1]["label"] = related_weapon_type
            bonus_entries[-1]["description"] = (
                f"Erhoeht die beherrschbare magische Bonuskapazitaet fuer {related_weapon_type} um +1/+1."
            )
    return {
        "bonus_entries": bonus_entries,
        "rune_entries": rune_entries,
        "has_entries": bool(bonus_entries or rune_entries),
    }


def _build_language_rows(character: Character) -> tuple[list[dict], object]:
    """Build the compact language display rows and keep the queryset for learning data."""
    engine = character.engine
    language_entries = (
        CharacterLanguage.objects
        .filter(owner=character)
        .select_related("language")
        .order_by("-is_mother_tongue", "language__name")
    )
    language_rows: list[dict] = []
    for entry in language_entries:
        level_count = max(0, min(3, engine.resolve_language_level(entry.language.slug)))
        language_rows.append(
            {
                "name": entry.language.name,
                "level_1": level_count >= 1,
                "level_2": level_count >= 2,
                "level_3": level_count >= 3,
                "can_write": bool(engine.effective_language_write(entry.language.slug)),
            }
        )
    return language_rows, language_entries


def _build_shop_item_groups() -> list[dict]:
    """Build grouped shop rows from all buyable items."""
    grouped_items: dict[str, list[dict]] = {}
    race_item_ids = _race_item_ids()
    buyable_items = (
        Item.objects
        .filter(catalog_group__isnull=True)
        .select_related(
            "armorstats",
            "shieldstats",
            "magicitemstats",
        )
        .prefetch_related(
            "runes",
            "weapon_stats",
            "weapon_stats__damage_source",
            "weapon_stats__weapon_type",
            "weapon_stats__skills",
            "weapon_stats__flags",
        )
        .order_by("item_type", "name")
    )
    for item in buyable_items:
        if item.id in race_item_ids or item.not_buyable:
            continue
        item_engine = ItemEngine(item)
        quality = quality_payload(item_engine.get_effective_quality())
        stats_payload: dict[str, object] = {
            "item_type": item.item_type,
            "size_class": item.size_class,
            "weight": str(item.weight),
            "min_st": None,
        }
        weapon_stats = (
            item.weapon_stats
            .order_by("id")
            .first()
        )

        if weapon_stats is not None:
            stats_payload.update(
                {
                    "damage_dice_amount": weapon_stats.damage_dice_amount,
                    "damage_dice_faces": weapon_stats.damage_dice_faces,
                    "damage_flat_bonus": weapon_stats.damage_flat_bonus,
                    "damage_flat_operator": weapon_stats.damage_flat_operator,
                    "h2_dice_amount": weapon_stats.h2_dice_amount,
                    "h2_dice_faces": weapon_stats.h2_dice_faces,
                    # Rest unverändert
                }
            )
        if weapon_stats is not None:
            stats_payload.update(
                {
                    "damage_dice_amount": weapon_stats.damage_dice_amount,
                    "damage_dice_faces": weapon_stats.damage_dice_faces,
                    "damage_flat_bonus": weapon_stats.damage_flat_bonus,
                    "damage_flat_operator": weapon_stats.damage_flat_operator,
                    "h2_dice_amount": weapon_stats.h2_dice_amount,
                    "h2_dice_faces": weapon_stats.h2_dice_faces,
                    "h2_flat_bonus": weapon_stats.h2_flat_bonus,
                    "h2_flat_operator": weapon_stats.h2_flat_operator,
                    "h2_damage_type": weapon_stats.h2_damage_type,
                    "wield_mode": weapon_stats.wield_mode,
                    "min_st": weapon_stats.min_st,
                    "damage_type": weapon_stats.damage_type,
                }
            )
        armor_stats = getattr(item, "armorstats", None)
        if armor_stats is not None:
            stats_payload.update(
                {
                    "armor_rs": item_engine.get_armor_rs_raw() or 0,
                    "armor_bel": armor_stats.encumbrance,
                    "armor_min_st": armor_stats.min_st,
                    "min_st": armor_stats.min_st,
                }
            )
        shield_stats = getattr(item, "shieldstats", None)
        if shield_stats is not None:
            stats_payload.update(
                {
                    "shield_rs": shield_stats.rs,
                    "shield_bel": shield_stats.encumbrance,
                    "shield_min_st": shield_stats.min_st,
                    "shield_parade_bonus": shield_stats.parade_bonus,
                    "min_st": shield_stats.min_st,
                }
            )
        magic_item_stats = getattr(item, "magicitemstats", None)
        if magic_item_stats is not None:
            stats_payload.update(
                {
                    "effect_summary": magic_item_stats.effect_summary,
                }
            )
        group_key = (
            SHOP_ARMOR_COMPONENT_GROUP
            if armor_stats is not None and armor_stats.parent_set_id
            else item.item_type
        )
        grouped_items.setdefault(group_key, []).append(
            {
                "id": item.id,
                "name": item.name,
                "description": item.description or "",
                "item_type": item.item_type,
                "stackable": bool(item.stackable),
                "base_price": int(item.price),
                "default_price": item_engine.get_price(),
                "default_quality": quality["value"],
                "default_quality_label": quality["label"],
                "default_quality_color": quality["color"],
                "stats": stats_payload,
                "rune_ids": [rune.id for rune in item.runes.all()],
            }
        )

    return [
        {
            "key": item_type,
            "label": SHOP_GROUP_LABELS[item_type],
            "items": grouped_items[item_type],
        }
        for item_type in SHOP_GROUP_ORDER
        if grouped_items.get(item_type)
    ]


def _build_shop_sell_item_groups(character: Character) -> list[dict]:
    """Build grouped sell rows from the character inventory."""
    grouped_items: dict[str, list[dict]] = {}
    inventory_items = (
        CharacterItem.objects
        .filter(owner=character)
        .exclude(item__not_sellable=True)
        .select_related("item", "item__armorstats", "original_owner_character")
        .order_by("item__item_type", "item__name", "quality", "id")
    )
    for character_item in inventory_items:
        if item_is_pending(character_item) or not has_item_permission(character_item, "sell", character):
            continue
        item = character_item.item
        item_engine = ItemEngine(character_item)
        quality = quality_payload(item_engine.get_effective_quality())
        armor_stats = getattr(item, "armorstats", None)
        group_key = (
            SHOP_ARMOR_COMPONENT_GROUP
            if armor_stats is not None and armor_stats.parent_set_id
            else item.item_type
        )
        grouped_items.setdefault(group_key, []).append(
            {
                "character_item_id": character_item.id,
                "item_id": item.id,
                "name": item_engine.get_name(),
                "description": character_item.description or item.description or "",
                "item_type": item.item_type,
                "amount": int(character_item.amount),
                "stackable": bool(item.stackable),
                "quality": quality["value"],
                "quality_label": quality["label"],
                "quality_color": quality["color"],
                "unit_price": item_engine.get_price(),
            }
        )

    return [
        {
            "key": item_type,
            "label": SHOP_GROUP_LABELS[item_type],
            "items": grouped_items[item_type],
        }
        for item_type in SHOP_GROUP_ORDER
        if grouped_items.get(item_type)
    ]


def _build_lesson_context(
    character: Character,
    *,
    engine: CharacterEngine,
    read_only: bool = False,
) -> dict[str, object]:
    """Build learning rows and the learned-lesson character-sheet panel."""
    entries = {
        int(entry.lesson_id): entry
        for entry in CharacterLesson.objects.filter(character=character)
        .select_related("lesson", "lesson__school", "lesson__technique")
    }
    learned_ids = set(entries)
    lesson_queryset = (
        Lesson.objects.select_related("school", "technique")
        .prefetch_related(
            "costs",
            "requirements__group",
            "requirements__required_school",
            "requirements__required_skill",
            "requirements__required_technique",
            "requirements__required_lesson",
        )
        .order_by("school__name", "name")
    )
    learning_groups: OrderedDict[str, list[dict[str, object]]] = OrderedDict()
    panel_groups: OrderedDict[int, dict[str, object]] = OrderedDict()
    for lesson in lesson_queryset:
        entry = entries.get(int(lesson.id))
        requirements_display = format_lesson_requirements(lesson)
        try:
            costs_display = format_lesson_costs(lesson)
        except LessonRuleError as exc:
            costs_display = f"Ungültige Kosten: {exc}"
        requirements_ok = lesson_requirements_met(
            lesson,
            character=character,
            learned_lesson_ids=learned_ids,
            engine=engine,
        )
        quote_parts = []
        if lesson.fluff_quote:
            quote_parts.append(str(lesson.fluff_quote).strip())
        if lesson.fluff_quote_speaker:
            quote_parts.append(f"- {lesson.fluff_quote_speaker}")
        quote_display = "\n".join(part for part in quote_parts if part)
        learning_row = {
            "id": int(lesson.id),
            "name": lesson.name,
            "school_name": lesson.school.name,
            "purchase_cost": int(lesson.purchase_cost),
            "paid_ep": int(entry.paid_ep) if entry else 0,
            "base_value": 1 if entry else 0,
            "can_unlearn": bool(entry and entry.can_unlearn),
            "requirements_met": requirements_ok,
            "requirements_display": requirements_display,
            "costs_display": costs_display,
            "description": lesson.description,
            "fluff_quote": lesson.fluff_quote,
            "fluff_quote_speaker": lesson.fluff_quote_speaker,
            "quote_display": quote_display,
            "activation_label": lesson.get_activation_type_display(),
        }
        if entry is not None or requirements_ok:
            learning_groups.setdefault(lesson.school.name, []).append(learning_row)
        if entry is None:
            continue
        group = panel_groups.setdefault(
            int(lesson.school_id),
            {
                "school_id": int(lesson.school_id),
                "name": lesson.school.name,
                "symbol": str(lesson.school.panel_symbol or ""),
                "symbol_image_url": _school_symbol_image_url(lesson.school),
                "rows": [],
            },
        )
        alternative_groups: dict[int, list[dict[str, object]]] = defaultdict(list)
        manual_ungrouped_costs = []
        base_kp_cost = 0
        for cost in lesson.costs.all():
            if cost.operator == LessonCost.Operator.OR and cost.alternative_group is not None:
                alternative_groups[int(cost.alternative_group)].append(
                    {
                        "id": int(cost.id),
                        "label": f"{int(cost.value)} {cost.type_label}",
                        "description": cost.description,
                        "manual": str(cost.cost_type) not in LESSON_COST_HANDLERS,
                        "cost_type": str(cost.cost_type),
                        "value": int(cost.value),
                    }
                )
            elif str(cost.cost_type) not in LESSON_COST_HANDLERS:
                manual_ungrouped_costs.append(format_cost(cost))
            elif cost.cost_type == LessonCost.CostType.ARCANE_POWER:
                base_kp_cost += int(cost.value)
        group["rows"].append(
            {
                **learning_row,
                "lesson_id": int(lesson.id),
                "activation_url": reverse("activate_lesson", args=[character.id, lesson.id]),
                "activation_enabled": not read_only,
                "alternative_groups": [
                    {"number": number, "options": options}
                    for number, options in sorted(alternative_groups.items())
                ],
                "alternative_groups_json": json.dumps(
                    [
                        {"number": number, "options": options}
                        for number, options in sorted(alternative_groups.items())
                    ],
                    ensure_ascii=False,
                ),
                "manual_costs_json": json.dumps(manual_ungrouped_costs, ensure_ascii=False),
                "base_kp_cost": base_kp_cost,
                "has_alternatives": bool(alternative_groups),
                "search_tokens": (
                    f"{lesson.name} {lesson.school.name} {lesson.description} "
                    f"{lesson.fluff_quote} {lesson.fluff_quote_speaker} "
                    f"{requirements_display} {costs_display} {lesson.get_activation_type_display()}"
                ).lower(),
            }
        )
    panel_group_list = list(panel_groups.values())
    return {
        "learn_lesson_tab_visible": bool(learning_groups),
        "learn_lesson_groups": [
            {"name": name, "rows": rows}
            for name, rows in learning_groups.items()
        ],
        "lesson_panel_enabled": bool(panel_group_list),
        "lesson_panel_groups": panel_group_list,
        "lesson_panel_filter_groups": panel_group_list if len(panel_group_list) > 1 else [],
    }


def _build_learning_rows(
    character: Character,
    attributes: dict[str, int],
    character_skills,
    language_entries,
    school_levels: dict[int, int],
    *,
    engine: CharacterEngine,
    synchronize: bool = True,
) -> dict[str, object]:
    """Build prepared learning rows grouped for the learning window."""
    from charsheet.engine.vampire_engine import VampireRules

    vampire_rules = VampireRules(character)
    vampire_strength_extension = (
        vampire_rules.can_exceed_strength_race_maximum() if character.is_vampire else False
    )
    vampire_disallowed_school_ids = (
        vampire_rules.disallowed_school_ids() if character.is_vampire else set()
    )
    attribute_limits = {
        limit.attribute.short_name: {
            "min": int(limit.min_value),
            "max": int(limit.max_value) + int(engine.resolve_attribute_cap_bonus(limit.attribute.short_name)),
            "original_max": int(limit.max_value),
        }
        for limit in character.race.raceattributelimit_set.select_related("attribute")
    }
    character_skills_by_skill_id: dict[int, list] = {}
    for _cs in character_skills:
        character_skills_by_skill_id.setdefault(_cs.skill_id, []).append(_cs)
    language_lookup = {
        entry.language_id: {
            "level": int(entry.levels),
            "write": bool(entry.can_write),
            "mother": bool(entry.is_mother_tongue),
        }
        for entry in language_entries
    }
    trait_levels = {
        entry.trait_id: int(entry.trait_level)
        for entry in CharacterTrait.objects.filter(owner=character).select_related("trait")
    }
    magic_engine = character.get_magic_engine()
    base_attributes = engine._attributes_map

    learn_attr_rows: list[dict] = []
    for short_name, label in ATTRIBUTE_ORDER:
        base_value = int(base_attributes.get(short_name, 0))
        learn_attr_rows.append(
            {
                "short_name": short_name,
                "label": label,
                "base_value": base_value,
                "min_value": int(attribute_limits.get(short_name, {}).get("min", 0)),
                "max_value": int(attribute_limits.get(short_name, {}).get("max", base_value)),
                "premium_threshold": (
                    int(attribute_limits.get(short_name, {}).get("original_max", base_value)) - 2
                    if vampire_strength_extension and short_name == ATTR_ST
                    else int(attribute_limits.get(short_name, {}).get("max", base_value)) - 2
                ),
            }
        )

    skill_groups: OrderedDict[str, list[dict]] = OrderedDict()

    def _skill_rank_learning_payload(skill: Skill, specification: str | None = None) -> dict[str, int]:
        max_level = int(engine.skill_rank_max(skill.slug, specification=specification))
        metadata = engine.skill_rank_cap_metadata(skill.slug, specification=specification)
        above_base_cost = int(metadata.get("above_base_cap_cost_ep") or metadata.get("above_base_cost_ep") or 2)
        return {
            "max_level": max(10, max_level),
            "above_base_cost": max(0, above_base_cost),
        }

    for skill in Skill.objects.select_related("category", "attribute").order_by("category__name", "name"):
        cs_entries = character_skills_by_skill_id.get(skill.id, [])
        desc = (skill.description or "").replace("\r\n", "\n").replace("\r", "\n")
        if skill.requires_specification:
            for cs in sorted(cs_entries, key=lambda x: (x.specification or "")):
                spec = (cs.specification or "").strip()
                if not spec or spec == "*":
                    continue
                rank_payload = _skill_rank_learning_payload(skill, spec)
                skill_groups.setdefault(skill.category.name, []).append(
                    {
                        "slug": skill.slug,
                        "name": f"{skill.name}: {spec}",
                        "description": desc,
                        "base_level": int(cs.level),
                        "max_level": rank_payload["max_level"],
                        "above_base_cost": rank_payload["above_base_cost"],
                        "cs_id": cs.id,
                        "spec": spec,
                        "kind": "skill-cs",
                    }
                )
            rank_payload = _skill_rank_learning_payload(skill)
            skill_groups.setdefault(skill.category.name, []).append(
                {
                    "slug": skill.slug,
                    "name": skill.name,
                    "description": desc,
                    "base_level": 0,
                    "max_level": rank_payload["max_level"],
                    "above_base_cost": rank_payload["above_base_cost"],
                    "kind": "skill-new-spec",
                }
            )
        else:
            base_level = int(cs_entries[0].level) if cs_entries else 0
            rank_payload = _skill_rank_learning_payload(skill)
            skill_groups.setdefault(skill.category.name, []).append(
                {
                    "slug": skill.slug,
                    "name": skill.name,
                    "description": desc,
                    "base_level": base_level,
                    "max_level": rank_payload["max_level"],
                    "above_base_cost": rank_payload["above_base_cost"],
                    "kind": "skill",
                }
            )

    learn_language_rows: list[dict] = []
    for language in Language.objects.order_by("name"):
        base_state = language_lookup.get(language.id, {"level": 0, "write": False, "mother": False})
        learn_language_rows.append(
            {
                "slug": language.slug,
                "name": language.name,
                "base_level": int(base_state["level"]),
                "max_level": int(language.max_level),
                "base_write": bool(base_state["write"]),
                "base_mother": bool(base_state["mother"]),
            }
        )

    spell_attribute_chart_by_school, spell_attribute_chart_by_aspect = _spell_attribute_chart_maps()
    divine_binding = magic_engine._divine_binding()
    divine_entity = divine_binding.entity if divine_binding is not None else None
    divine_primary_symbol = ""
    divine_primary_image_url = ""
    divine_aspect_symbols: list[str] = []
    divine_aspect_image_urls: list[str] = []
    if divine_entity is not None:
        divine_primary_symbol = str(divine_entity.name or "?").strip()[:1] or "?"
        divine_primary_image_url = _image_field_url(divine_entity, "symbol_image")
        if not divine_primary_image_url:
            divine_primary_symbol = str(getattr(divine_entity.school, "panel_symbol", "") or divine_primary_symbol).strip()
            divine_primary_image_url = _school_symbol_image_url(divine_entity.school)
        for link in divine_entity.aspects.select_related("aspect").order_by("aspect__name"):
            aspect = link.aspect
            divine_aspect_symbols.append(str(aspect.name or "?").strip()[:1] or "?")
            divine_aspect_image_urls.append(_aspect_image_url(aspect))

    school_level_caps = school_max_levels()
    school_groups: OrderedDict[str, list[dict]] = OrderedDict()
    learned_school_ids = {
        int(school_id) for school_id, level in school_levels.items() if int(level) > 0
    }
    active_clerical_school_ids = {
        int(school.id)
        for school in School.objects.filter(id__in=learned_school_ids).select_related("type")
        if is_clerical_school(school)
    }
    selected_religion_entity = selected_divine_entity(character)
    selected_religion_school_id = (
        int(selected_religion_entity.school_id)
        if selected_religion_entity is not None and selected_religion_entity.school_id
        else None
    )
    visible_clerical_school_ids = set(active_clerical_school_ids)
    if selected_religion_school_id is not None:
        visible_clerical_school_ids.add(selected_religion_school_id)
    for school in School.objects.select_related("type").order_by("type__name", "name"):
        base_level = int(school_levels.get(school.id, 0))
        if school.id in vampire_disallowed_school_ids and base_level <= 0:
            continue
        if (
            visible_clerical_school_ids
            and is_clerical_school(school)
            and int(school.id) not in visible_clerical_school_ids
            and base_level <= 0
        ):
            continue
        max_level = max(base_level, int(school_level_caps.get(school.id, DEFAULT_SCHOOL_MAX_LEVEL)))
        source_symbol = str(getattr(school, "panel_symbol", "") or "").strip()
        source_image_url = _school_symbol_image_url(school)
        secondary_symbols = ""
        secondary_image_urls = ""
        if divine_entity is not None and int(school.id) == int(divine_entity.school_id):
            source_symbol = divine_primary_symbol
            source_image_url = divine_primary_image_url
            secondary_symbols = ";".join(divine_aspect_symbols)
            secondary_image_urls = ";".join(divine_aspect_image_urls)
        description = _prepend_tooltip_source_symbol(
            school.description,
            source_symbol,
            source_image_url,
            secondary_symbols,
            secondary_image_urls,
        )
        description = _append_spell_attribute_chart(
            description,
            spell_attribute_chart_by_school.get(int(school.id), ""),
        )
        school_groups.setdefault(school.type.name, []).append(
            {
                "id": school.id,
                "name": school.name,
                "description": description,
                "type_name": school.type.name,
                "base_level": base_level,
                "max_level": max_level,
            }
        )

    trait_groups: OrderedDict[str, list[dict]] = OrderedDict()
    for trait in Trait.objects.order_by("trait_type", "name"):
        base_level = int(trait_levels.get(trait.id, 0))
        if (
            trait.slug == VAMPIRE_ANCHOR_TRAIT_SLUG
            and base_level <= 0
            and not (
                character.is_at_vampire_baptism_threshold
                and character.vampire_baptism_confirmed
            )
        ):
            continue
        group_name = "Vorteile" if trait.trait_type == Trait.TraitType.ADV else "Nachteile"
        trait_groups.setdefault(group_name, []).append(
            {
                "slug": trait.slug,
                "name": trait.name,
                "description": (trait.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "base_level": base_level,
                "min_level": int(trait.min_level),
                "max_level": int(trait.max_level),
                "points_per_level": int(trait.points_per_level),
                "points_display": trait.cost_display(),
                "points_by_level": list(trait.cost_curve()),
            }
        )

    magic_groups: OrderedDict[str, list[dict]] = OrderedDict()
    aspect_by_id = {
        aspect.id: aspect
        for aspect in Aspect.objects.all()
    }
    for group in build_learning_magic_groups(
        character,
        magic_engine=magic_engine,
        synchronize=synchronize,
    ):
        rows = []
        for row in group["rows"]:
            if row.get("kind") == "magic_aspect":
                aspect_id = int(row.get("aspect_id") or 0)
                aspect = aspect_by_id.get(aspect_id)
                aspect_symbol = str(row.get("name") or "?").strip()[:1] or "?"
                row = {
                    **row,
                    "description": _append_spell_attribute_chart(
                        _prepend_tooltip_source_symbol(
                            str(row.get("description") or ""),
                            divine_primary_symbol,
                            divine_primary_image_url,
                            aspect_symbol,
                            _aspect_image_url(aspect) if aspect else "",
                        ),
                        spell_attribute_chart_by_aspect.get(aspect_id, ""),
                    ),
                }
            rows.append(row)
        magic_groups[group["name"]] = rows

    magic_slot_summary = magic_engine.get_spell_learning_slot_summary()
    magic_slot_table_columns = list(range(1, 11))
    spent_spell_slots_by_source_grade: dict[tuple[str, int], int] = defaultdict(int)
    slot_spells = CharacterSpell.objects.filter(
        character=character,
        source_kind__in=(
            CharacterSpell.SourceKind.ARCANE_FREE,
            CharacterSpell.SourceKind.ARCANE_EXTRA,
            CharacterSpell.SourceKind.ARCANE_BONUS,
            CharacterSpell.SourceKind.DIVINE_EXTRA,
            CharacterSpell.SourceKind.DIVINE_BONUS,
            CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
        ),
    ).select_related("spell")
    for entry in slot_spells:
        spell = entry.spell
        grade = int(spell.grade or 0)
        if grade <= 0:
            continue
        if spell.school_id:
            spent_spell_slots_by_source_grade[(f"school:{spell.school_id}", grade)] += 1
        elif spell.aspect_id:
            spent_spell_slots_by_source_grade[(f"aspect:{spell.aspect_id}:grade:{grade}", grade)] += 1
    magic_slot_rows_by_key: OrderedDict[str, dict[str, object]] = OrderedDict()
    magic_school_slot_sources: list[dict[str, object]] = []

    def ensure_magic_slot_row(source: dict[str, object], label: str, row_key: str) -> dict[str, object]:
        if row_key not in magic_slot_rows_by_key:
            magic_slot_rows_by_key[row_key] = {
                "label": label,
                "symbol": source.get("symbol", "*"),
                "symbol_image_url": source.get("symbol_image_url", ""),
                "cells_by_grade": {
                    grade: {
                        "grade": grade,
                        "key": "",
                        "remaining": 0,
                    }
                    for grade in magic_slot_table_columns
                },
            }
        return magic_slot_rows_by_key[row_key]

    for source in magic_slot_summary.get("sources", {}).values():
        source_key = str(source.get("key", "") or "")
        source_kind = str(source.get("kind", "") or "")
        source_level = max(0, int(source.get("level", 0) or 0))
        slots_per_level = max(0, int(source.get("slots_per_level", 0) or 0))
        if source_kind in {"school", "divine_arcane"}:
            remaining_total = max(0, int(source.get("remaining", 0) or 0))
            if remaining_total > 0:
                magic_school_slot_sources.append(
                    {
                        "key": source_key,
                        "name": str(source.get("name", "") or ""),
                        "symbol": source.get("symbol", "*"),
                        "symbol_image_url": source.get("symbol_image_url", ""),
                        "remaining": remaining_total,
                    }
                )
        else:
            grade = int(source.get("grade", 0) or 0)
            if grade not in magic_slot_table_columns:
                continue
            source_label = str(source.get("name", "") or "")
            label = source_label.rsplit(" Grad ", 1)[0] if " Grad " in source_label else source_label
            row_key = f"{source_kind}:{source.get('id', '')}"
            row = ensure_magic_slot_row(source, label, row_key)
            row["cells_by_grade"][grade] = {
                "grade": grade,
                "key": source_key,
                "remaining": max(0, int(source.get("remaining", 0) or 0)),
            }
    magic_slot_rows = [
        {
            "label": row["label"],
            "symbol": row["symbol"],
            "symbol_image_url": row["symbol_image_url"],
            "cells": [row["cells_by_grade"][grade] for grade in magic_slot_table_columns],
        }
        for row in magic_slot_rows_by_key.values()
        if any(int(cell["remaining"]) > 0 for cell in row["cells_by_grade"].values())
    ]
    magic_slot_summary["slot_table_columns"] = magic_slot_table_columns
    magic_slot_summary["slot_table_rows"] = magic_slot_rows
    magic_slot_summary["school_slot_sources"] = magic_school_slot_sources
    learn_magic_grade_filters = sorted({
        int(row["grade"])
        for rows in magic_groups.values()
        for row in rows
        if row.get("kind") == "magic_spell" and row.get("grade") is not None
    })
    learn_magic_source_filter_map: OrderedDict[str, dict[str, str]] = OrderedDict()
    for rows in magic_groups.values():
        for row in rows:
            if row.get("kind") != "magic_spell":
                continue
            key = str(row.get("filter_source_key") or row.get("slot_source_key") or "")
            if not key or key in learn_magic_source_filter_map:
                continue
            learn_magic_source_filter_map[key] = {
                "key": key,
                "name": str(row.get("filter_source_name") or row.get("owner_name") or ""),
                "symbol": str(row.get("owner_symbol") or "*"),
                "symbol_image_url": str(row.get("owner_symbol_image_url") or ""),
            }
    has_magic_schools = any(
        (
            bool(magic_engine._magic_school_entries()),
            bool(magic_groups),
            bool(magic_engine._divine_binding()),
            int(magic_slot_summary.get("total", 0) or 0) > 0,
        )
    )

    return {
        "learn_attr_rows": learn_attr_rows,
        "learn_trait_groups": [
            {"name": group_name, "rows": rows}
            for group_name, rows in trait_groups.items()
        ],
        "learn_skill_groups": [
            {"name": category_name, "rows": rows}
            for category_name, rows in skill_groups.items()
        ],
        "learn_language_rows": learn_language_rows,
        "learn_school_groups": [
            {"name": type_name, "rows": rows}
            for type_name, rows in school_groups.items()
        ],
        "learn_magic_groups": [
            {"name": group_name, "rows": rows}
            for group_name, rows in magic_groups.items()
        ],
        "learn_magic_tab_visible": has_magic_schools,
        "learn_magic_slot_summary": magic_slot_summary,
        "learn_magic_grade_filters": learn_magic_grade_filters,
        "learn_magic_source_filters": list(learn_magic_source_filter_map.values()),
    }


def build_temporary_attribute_context(
    character: Character,
    *,
    read_only: bool = False,
) -> dict[str, object]:
    """Build only the sheet data affected by runtime attribute adjustments."""
    engine = character.engine
    attributes = engine.attributes()
    attr_mods = {
        short_name: format_modifier(engine.attribute_modifier(short_name))
        for short_name, _label in ATTRIBUTE_ORDER
    }
    attribute_rows = [
        {
            "short_name": short_name,
            "label": label,
            "value": attributes.get(short_name, 0),
            "modifier": attr_mods[short_name],
            "runtime_adjustment": int(engine.runtime_attribute_adjustments.get(short_name, 0)),
        }
        for short_name, label in ATTRIBUTE_ORDER
    ]

    load_penalty = engine.load_penalty()
    carry_state = ItemEngine.carry_state_for_character(character)
    carry_penalty = int(carry_state["penalty"])
    skill_rows, _character_skills, skill_manager_rows = _build_skill_rows(
        character,
        engine,
        load_penalty=load_penalty,
    )
    for row in skill_rows:
        if "with_load_total_value" not in row:
            continue
        base_with_load_total = int(row.get("with_load_total_value", 0) or 0)
        row["carry_with_load_total_value"] = base_with_load_total + carry_penalty
        row["carry_with_load_total"] = base_with_load_total + carry_penalty

    weapon_rows = _build_weapon_rows(engine)
    for row in weapon_rows:
        row["carry_with_bel_value"] = int(row.get("with_bel_value", 0) or 0) + carry_penalty
        row["carry_with_bel_display"] = format_modifier(int(row["carry_with_bel_value"]))
        row["carry_calculation_tooltip"] = _build_weapon_calculation_tooltip(
            engine,
            row,
            extra_load_penalty=carry_penalty,
        )
    battle_calculator_payload = BattleCalculatorEngine.build_payload(engine, skill_rows, weapon_rows)

    initiative_value = engine.calculate_initiative()
    initiative_wa_mod = engine.attribute_modifier(ATTR_WA)
    initiative_wound_penalty = engine.current_wound_penalty()
    current_wound_stage, _current_wound_penalty_stage = engine.current_wound_stage()
    current_wound_penalty = engine.current_wound_penalty_raw()
    current_wound_penalty_display = (
        "-" if current_wound_stage == "-" else format_modifier(current_wound_penalty)
    )
    can_act_while_out_of_action = engine.can_act_while_out_of_action()
    is_wound_stage_disabled = (
        engine.is_wound_penalty_ignored()
        and current_wound_stage not in {"Ausser Gefecht", "Außer Gefecht", "Koma", "Tod"}
    ) or (
        can_act_while_out_of_action
        and current_wound_stage in {"Ausser Gefecht", "Außer Gefecht"}
    )
    wound_threshold_data = engine.wound_thresholds()
    wound_threshold_rows = [
        {"threshold": threshold, "stage": stage, "penalty": penalty}
        for threshold, (stage, penalty) in sorted(wound_threshold_data.items())
    ]
    current_damage_max = max(wound_threshold_data.keys()) if wound_threshold_data else 0
    damage_gauge = _build_damage_gauge_data(
        current_damage=character.current_damage,
        threshold_rows=wound_threshold_rows,
        damage_max=current_damage_max,
        stun_damage=character.current_stun_damage,
        lethal_damage=character.current_lethal_damage,
    )

    vw_ge_mod = engine.attribute_modifier(ATTR_GE)
    vw_wa_mod = engine.attribute_modifier(ATTR_WA)
    if engine.resolve_flags().get("suppress_positive_vw_attribute_bonuses", False):
        vw_ge_mod = min(0, vw_ge_mod)
        vw_wa_mod = min(0, vw_wa_mod)
    sr_st_mod = engine.attribute_modifier(ATTR_ST)
    sr_kon_mod = engine.attribute_modifier(ATTR_KON)
    gw_int_mod = engine.attribute_modifier(ATTR_INT)
    gw_will_mod = engine.attribute_modifier(ATTR_WILL)
    vw_value = engine.vw()
    sr_value = engine.sr()
    gw_value = engine.gw()
    willpower = attributes.get(ATTR_WILL, 0)
    school_level_total = sum(int(entry.level) for entry in engine._school_entries.values())
    aspect_level_total = sum(
        int(entry.level)
        for entry in character.get_magic_engine().get_character_aspects()
        if entry.is_bonus_aspect
    )
    from charsheet.engine.vampire_engine import VampireRules

    vampire_rules = VampireRules(character)
    is_vampire = vampire_rules.is_vampire()
    if is_vampire:
        vampire_resource = vampire_rules.resource_state()
        arcane_power_value = vampire_resource.maximum
        potential_value = vampire_resource.potential
        current_arcane_power = vampire_resource.intelligent
        resource_label = "Blut intelligenter Wesen"
        vampire_traits, vampire_powers = _vampire_sheet_entries(vampire_rules)
        vampire_panel = {
            "age_cycle": vampire_rules.age_cycle(),
            "intelligent_blood": vampire_resource.intelligent,
            "animal_blood": vampire_resource.animal,
            "total_blood": vampire_resource.total,
            "total_meter_percent": f"{(0 if vampire_resource.maximum <= 0 else vampire_resource.total / vampire_resource.maximum * 100):.2f}",
            "intelligent_meter_percent": f"{(0 if vampire_resource.maximum <= 0 else vampire_resource.intelligent / vampire_resource.maximum * 100):.2f}",
            "animal_meter_percent": f"{(0 if vampire_resource.maximum <= 0 else vampire_resource.animal / vampire_resource.maximum * 100):.2f}",
            "capacity": vampire_resource.maximum,
            "potential": vampire_resource.potential,
            "state": character.vampire_state,
            "state_label": VAMPIRE_STATE_UI_LABELS.get(character.vampire_state, character.vampire_state),
            "day_count": character.vampire_day_count,
            "last_qualifying_kill_day": character.vampire_last_qualifying_kill_day,
            "recent_qualifying_kill": vampire_rules.has_recent_qualifying_kill(),
            "can_regenerate": vampire_rules.can_regenerate(),
            "regeneration_blood": character.vampire_regeneration_blood,
            "regeneration_target_cost": character.vampire_regeneration_target_cost,
            "pending_starvation": character.vampire_pending_starvation,
            "sacrament_age_bonus": character.vampire_sacrament_age_bonus,
            "sacrament_rounds_remaining": character.vampire_sacrament_rounds_remaining,
            "aggravated_damage": character.current_aggravated_damage,
            "traits": vampire_traits,
            "trait_groups": _vampire_trait_groups(vampire_traits),
            "powers": vampire_powers,
            "warnings": vampire_rules.warnings(),
            **_vampire_learning_payload(character, vampire_rules),
        }
    else:
        arcane_power_value = engine.calculate_arcane_power()
        potential_value = engine.calculate_potential()
        current_arcane_power = character.current_arcane_power
        if current_arcane_power is None:
            current_arcane_power = arcane_power_value
        current_arcane_power = min(max(0, int(current_arcane_power)), int(arcane_power_value))
        resource_label = "Arkane Macht"
        vampire_panel = None
    arcane_meter_percent = (
        0
        if arcane_power_value <= 0
        else (current_arcane_power / int(arcane_power_value)) * 100.0
    )
    if is_vampire:
        resource_tooltip_rows = [
            {"label": "Willenskraft", "value": vampire_rules.willpower()},
            {"label": "Magie-/Kampfschulen", "value": vampire_rules.school_ranks()},
            {"label": "Vampirkräfte", "value": vampire_rules.power_ranks()},
            {"label": "Alterszyklus", "value": vampire_rules.age_cycle()},
            {"label": "Zusatzkapazität", "value": vampire_rules.capacity_bonus()},
            {"label": "Permanenter Verlust", "value": -vampire_rules.capacity_loss()},
            {"label": "= Blutvorrat", "value": arcane_power_value, "tone": "total"},
        ]
    else:
        resource_tooltip_rows = [
            {"label": "Will", "value": willpower},
            {"label": "Stufen in Schulen", "value": school_level_total},
            {"label": "Bonus-Aspektstufen", "value": aspect_level_total},
            *_build_modifier_breakdown_rows(engine, ARCANE_POWER),
            {"label": "= Gesamt", "value": arcane_power_value, "tone": "total"},
        ]

    return {
        "character": character,
        "read_only": read_only,
        "attributes": attributes,
        "attr_mods": attr_mods,
        "attribute_rows": attribute_rows,
        "skill_rows": skill_rows,
        "skill_manager_rows": skill_manager_rows,
        "weapon_rows": weapon_rows,
        "battle_calculator_payload": battle_calculator_payload,
        "core_stats": {
            "load_value": load_penalty,
            "load_tooltip": _build_load_tooltip(engine),
            "load_value_with_carry": load_penalty + carry_penalty,
            "load_tooltip_with_carry": _build_combined_load_tooltip(engine, carry_state, carry_enabled=True),
            "initiative_display": format_modifier(initiative_value),
            "initiative_with_load_display": format_modifier(initiative_value + load_penalty),
            "initiative_with_load_value": initiative_value + load_penalty,
            "initiative_condition_badge": _build_core_stat_condition_badge(engine, INITIATIVE),
            "initiative_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "WA-Bonus/Malus", "value": format_modifier(initiative_wa_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "= Gesamt", "value": format_modifier(initiative_value), "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, INITIATIVE),
            ),
            "initiative_with_load_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "WA-Bonus/Malus", "value": format_modifier(initiative_wa_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "Belastung", "value": format_modifier(load_penalty)},
                    {"label": "= Gesamt", "value": format_modifier(initiative_value + load_penalty), "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, INITIATIVE),
            ),
            "initiative_with_load_tooltip_with_carry": _build_core_stat_tooltip(
                [
                    {"label": "WA-Bonus/Malus", "value": format_modifier(initiative_wa_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "Rüstungsbelastung", "value": format_modifier(load_penalty)},
                    {"label": "Traglast", "value": format_modifier(carry_penalty), "source": str(carry_state["state_label"])},
                    {"label": "= Gesamt", "value": format_modifier(initiative_value + load_penalty + carry_penalty), "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, INITIATIVE),
            ),
            "vw": vw_value,
            "vw_condition_badge": _build_core_stat_condition_badge(engine, DEFENSE_VW),
            "vw_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "GE-Bonus/Malus", "value": format_modifier(vw_ge_mod)},
                    {"label": "WA-Bonus/Malus", "value": format_modifier(vw_wa_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_VW),
                    {"label": "= Gesamt", "value": vw_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, DEFENSE_VW),
            ),
            "sr": sr_value,
            "sr_condition_badge": _build_core_stat_condition_badge(engine, DEFENSE_SR),
            "sr_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "ST-Bonus/Malus", "value": format_modifier(sr_st_mod)},
                    {"label": "KON-Bonus/Malus", "value": format_modifier(sr_kon_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_SR),
                    {"label": "= Gesamt", "value": sr_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, DEFENSE_SR),
            ),
            "gw": gw_value,
            "gw_condition_badge": _build_core_stat_condition_badge(engine, DEFENSE_GW),
            "gw_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "INT-Bonus/Malus", "value": format_modifier(gw_int_mod)},
                    {"label": "WILL-Bonus/Malus", "value": format_modifier(gw_will_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_GW),
                    {"label": "= Gesamt", "value": gw_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, DEFENSE_GW),
            ),
            "arcane_power": arcane_power_value,
            "arcane_power_condition_badge": _build_core_stat_condition_badge(engine, ARCANE_POWER),
            "arcane_power_tooltip": _build_core_stat_tooltip(
                resource_tooltip_rows,
                conditional_modifiers=_conditional_core_stat_modifiers(engine, ARCANE_POWER),
            ),
            "potential": potential_value,
            "potential_condition_badge": _build_core_stat_condition_badge(engine, POTENTIAL),
            "potential_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Will / 2", "value": willpower // 2},
                    *_build_modifier_breakdown_rows(engine, POTENTIAL),
                    {"label": "= Gesamt", "value": potential_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, POTENTIAL),
            ),
        },
        "current_wound_stage": current_wound_stage,
        "current_wound_penalty": current_wound_penalty_display,
        "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
        "can_act_while_out_of_action": can_act_while_out_of_action,
        "is_wound_stage_disabled": is_wound_stage_disabled,
        "current_damage_max": current_damage_max,
        "current_stun_damage": character.current_stun_damage,
        "current_lethal_damage": character.current_lethal_damage,
        "current_aggravated_damage": character.current_aggravated_damage,
        "damage_gauge_needle_angle": damage_gauge["needle_angle"],
        "damage_gauge_stun_needle_angle": damage_gauge["stun_needle_angle"],
        "damage_gauge_lethal_needle_angle": damage_gauge["lethal_needle_angle"],
        "damage_gauge_total_needle_angle": damage_gauge["total_needle_angle"],
        "damage_gauge_segments": damage_gauge["segments"],
        "damage_gauge_gradient_stops": damage_gauge["gradient_stops"],
        "wound_threshold_rows": wound_threshold_rows,
        "current_arcane_power": current_arcane_power,
        "current_arcane_power_max": int(arcane_power_value),
        "arcane_meter_percent": f"{arcane_meter_percent:.2f}",
        "resource_label": resource_label,
        "resource_type": "blood" if is_vampire else "arcane_power",
        "is_vampire": is_vampire,
        "vampire_panel": vampire_panel,
    }


def build_item_semantic_effect_partial_context(
    character: Character,
    partial_keys,
    *,
    read_only: bool = False,
) -> dict[str, object]:
    """Build only the sheet data needed after item semantic-effect toggles."""
    partial_key_set = set(partial_keys)
    context = build_temporary_attribute_context(character, read_only=read_only)
    engine = character.engine
    carry_state = ItemEngine.carry_state_for_character(character)
    carry_penalty = int(carry_state["penalty"])
    load_penalty = engine.load_penalty()

    if "movement_panel" in partial_key_set:
        context["movement_ground"] = _build_movement_ground(engine, character.race)

    if "damage_panel" in partial_key_set:
        current_wound_stage, _current_wound_penalty_stage = engine.current_wound_stage()
        current_wound_penalty = engine.current_wound_penalty_raw()
        current_wound_penalty_display = (
            "-"
            if current_wound_stage == "-"
            else format_modifier(current_wound_penalty)
        )
        can_act_while_out_of_action = engine.can_act_while_out_of_action()
        is_wound_stage_disabled = (
            engine.is_wound_penalty_ignored()
            and current_wound_stage not in {"Ausser Gefecht", "Außer Gefecht", "Koma", "Tod"}
        ) or (
            can_act_while_out_of_action
            and current_wound_stage in {"Ausser Gefecht", "Außer Gefecht"}
        )
        wound_threshold_data = engine.wound_thresholds()
        wound_threshold_rows = [
            {"threshold": threshold, "stage": stage, "penalty": penalty}
            for threshold, (stage, penalty) in sorted(wound_threshold_data.items())
        ]
        current_damage_max = max(wound_threshold_data.keys()) if wound_threshold_data else 0
        damage_gauge = _build_damage_gauge_data(
            current_damage=character.current_damage,
            threshold_rows=wound_threshold_rows,
            damage_max=current_damage_max,
            stun_damage=character.current_stun_damage,
            lethal_damage=character.current_lethal_damage,
        )

        from charsheet.engine.vampire_engine import VampireRules

        vampire_rules = VampireRules(character)
        is_vampire = vampire_rules.is_vampire()
        if is_vampire:
            vampire_resource = vampire_rules.resource_state()
            arcane_power_value = vampire_resource.maximum
            current_arcane_power = vampire_resource.intelligent
            resource_label = "Blut intelligenter Wesen"
            intelligent_meter_percent = (
                0
                if vampire_resource.maximum <= 0
                else vampire_resource.intelligent / vampire_resource.maximum * 100
            )
            animal_meter_percent = (
                0
                if vampire_resource.maximum <= 0
                else vampire_resource.animal / vampire_resource.maximum * 100
            )
            vampire_panel = {
                "intelligent_blood": vampire_resource.intelligent,
                "animal_blood": vampire_resource.animal,
                "total_blood": vampire_resource.total,
                "intelligent_meter_percent": f"{intelligent_meter_percent:.2f}",
                "animal_meter_percent": f"{animal_meter_percent:.2f}",
                "capacity": vampire_resource.maximum,
            }
        else:
            arcane_power_value = engine.calculate_arcane_power()
            current_arcane_power = character.current_arcane_power
            if current_arcane_power is None:
                current_arcane_power = arcane_power_value
            current_arcane_power = min(
                max(0, int(current_arcane_power)),
                int(arcane_power_value),
            )
            resource_label = "Arkane Macht"
            vampire_panel = None
        arcane_meter_percent = (
            0
            if arcane_power_value <= 0
            else (current_arcane_power / int(arcane_power_value)) * 100.0
        )
        context.update(
            {
                "character": character,
                "read_only": read_only,
                "current_wound_stage": current_wound_stage,
                "current_wound_penalty": current_wound_penalty_display,
                "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
                "can_act_while_out_of_action": can_act_while_out_of_action,
                "is_wound_stage_disabled": is_wound_stage_disabled,
                "current_damage_max": current_damage_max,
                "current_stun_damage": character.current_stun_damage,
                "current_lethal_damage": character.current_lethal_damage,
                "current_aggravated_damage": character.current_aggravated_damage,
                "damage_gauge_needle_angle": damage_gauge["needle_angle"],
                "damage_gauge_stun_needle_angle": damage_gauge["stun_needle_angle"],
                "damage_gauge_lethal_needle_angle": damage_gauge["lethal_needle_angle"],
                "damage_gauge_total_needle_angle": damage_gauge["total_needle_angle"],
                "damage_gauge_segments": damage_gauge["segments"],
                "damage_gauge_gradient_stops": damage_gauge["gradient_stops"],
                "wound_threshold_rows": wound_threshold_rows,
                "current_arcane_power": current_arcane_power,
                "current_arcane_power_max": int(arcane_power_value),
                "arcane_meter_percent": f"{arcane_meter_percent:.2f}",
                "resource_label": resource_label,
                "resource_type": "blood" if is_vampire else "arcane_power",
                "is_vampire": is_vampire,
                "vampire_panel": vampire_panel,
            }
        )

    if "inventory_panel" in partial_key_set:
        inventory_rows = _build_inventory_rows(character)
        inventory_total_weight_display = _build_inventory_total_weight_display(character)
        context.update(
            {
                "inventory_rows": [row for row in inventory_rows if not row.get("is_stored")],
                "stored_inventory_rows": [row for row in inventory_rows if row.get("is_stored")],
                "inventory_total_weight_display": inventory_total_weight_display,
                "carry_load": {
                    "enabled": bool(character.carry_load_enabled),
                    "update_url": reverse("update_carry_load_state", args=[character.pk]),
                    "weight": str(carry_state["weight"]),
                    "weight_display": inventory_total_weight_display,
                    "penalty": carry_penalty,
                    "state_label": str(carry_state["state_label"]),
                    "tooltip": _build_carry_load_tooltip(carry_state, active=False),
                    "tooltip_active": _build_carry_load_tooltip(carry_state, active=True),
                },
            }
        )

    if "armor_panel" in partial_key_set:
        armor_zone_protection = engine.armor_zone_protection()
        load_tooltip = _build_load_tooltip(engine)
        context.update(
            {
                "armor_rows": _build_armor_rows(engine),
                "armor_summary": {
                    "total_rs": engine.get_grs(),
                    "total_rs_tooltip": _build_total_armor_tooltip(engine),
                    "load_value": load_penalty,
                    "load_tooltip": load_tooltip,
                    "minimum_strength": engine.get_ms(),
                    "minimum_strength_tooltip": _build_minimum_strength_tooltip(engine),
                },
                "body_armor": {
                    "shield": engine.shield_protection(),
                    **armor_zone_protection,
                },
            }
        )

    if "wallet_panel" in partial_key_set:
        wallet_gold, wallet_silver, wallet_copper = engine.km_to_coins()
        context.update(
            {
                "wallet_total_ks": format_thousands(character.money),
                "wallet_gold_display": format_thousands(wallet_gold),
                "wallet_silver_display": format_thousands(wallet_silver),
                "wallet_copper_display": format_thousands(wallet_copper),
            }
        )

    if "fame_panel" in partial_key_set:
        manual_personal_fame_point = max(
            0,
            int(character.personal_fame_point) + int(engine.resolve_resource("personal_fame_point")),
        )
        manual_personal_fame_total = max(
            0,
            (int(character.personal_fame_rank) * 10) + int(character.personal_fame_point),
        )
        base_personal_fame_rank = max(
            0,
            int(character.personal_fame_rank) + int(engine.resolve_resource("personal_fame_rank")),
        )
        effective_artefact_rank = max(
            0,
            int(character.artefact_rank) + int(engine.resolve_resource("artefact_rank")),
        )
        auto_school_fame_point = engine.auto_school_fame_points()
        auto_lesson_fame_point = engine.auto_lesson_fame_points()
        auto_progression_fame_point = auto_school_fame_point + auto_lesson_fame_point
        total_personal_fame_point = manual_personal_fame_point + auto_progression_fame_point
        effective_personal_fame_point = total_personal_fame_point % 10
        effective_personal_fame_rank = base_personal_fame_rank + (total_personal_fame_point // 10)
        context.update(
            {
                "effective_personal_fame_point": effective_personal_fame_point,
                "effective_personal_fame_rank": effective_personal_fame_rank,
                "effective_artefact_rank": effective_artefact_rank,
                "auto_school_fame_point": auto_school_fame_point,
                "manual_personal_fame_total": manual_personal_fame_total,
                "auto_lesson_fame_point": auto_lesson_fame_point,
                "auto_progression_fame_point": auto_progression_fame_point,
                "fame_total_rank": effective_personal_fame_rank + int(character.sacrifice_rank) + effective_artefact_rank,
            }
        )

    if "spell_panel" in partial_key_set:
        spell_panel_data = character.get_magic_engine().get_spell_panel_data()
        context.update(
            {
                "spell_panel_enabled": bool(spell_panel_data["spell_panel_enabled"]),
                "spell_and_lessons_panel_enabled": bool(spell_panel_data["spell_and_lessons_panel_enabled"]),
                "has_castable_entries": bool(spell_panel_data["has_castable_entries"]),
                "spell_panel_groups": spell_panel_data["groups"],
                "spell_panel_filter_groups": spell_panel_data.get("filter_groups", []),
            }
        )

    if "lesson_panel" in partial_key_set:
        context.update(_build_lesson_context(character, engine=CharacterEngine(character), read_only=read_only))

    if "learning_budget" in partial_key_set:
        context["learn_magic_slot_summary"] = character.get_magic_engine().get_spell_learning_slot_summary()

    return context


def _build_movement_ground(engine, race) -> dict[str, str]:
    movement_profile = engine.resolve_movement()

    def _resolve_movement_value(base_value, target_key):
        if target_key in movement_profile.overrides:
            return max(0, int(movement_profile.overrides[target_key] or 0))
        base = int(base_value or 0)
        multiplier = float(movement_profile.multipliers.get(target_key, 1.0))
        additive = int(movement_profile.values.get(target_key, 0))
        return max(0, int(base * multiplier) + additive)

    ground_blocked = "ground" in movement_profile.blocked_modes
    swim_blocked = "swim" in movement_profile.blocked_modes
    ground_combat = None if ground_blocked else _resolve_movement_value(race.combat_speed, "ground_combat")
    ground_march = None if ground_blocked else _resolve_movement_value(race.march_speed, "ground_march")
    ground_sprint = None if ground_blocked else _resolve_movement_value(race.sprint_speed, "ground_sprint")
    swim_speed = None if swim_blocked else _resolve_movement_value(race.swimming_speed, "swim")
    swim_triplet_keys = ("swim_combat", "swim_march", "swim_sprint")
    has_swim_triplet = not swim_blocked and any(
        key in movement_profile.values or key in movement_profile.multipliers or key in movement_profile.overrides
        for key in swim_triplet_keys
    )
    swim_value = "-" if swim_speed is None else format_compact_number(swim_speed)
    if has_swim_triplet:
        swim_values = (
            _resolve_movement_value(race.swimming_speed, "swim_combat"),
            _resolve_movement_value(race.swimming_speed, "swim_march"),
            _resolve_movement_value(race.swimming_speed, "swim_sprint"),
        )
        formatted_swim_values = tuple(format_compact_number(value) for value in swim_values)
        swim_value = (
            formatted_swim_values[0]
            if len(set(formatted_swim_values)) == 1
            else " / ".join(formatted_swim_values)
        )
    fly_value = "-"
    has_flight = race.can_fly or any(
        key in movement_profile.values or key in movement_profile.multipliers or key in movement_profile.overrides
        for key in ("fly_combat", "fly_march", "fly_sprint")
    )
    if has_flight and "fly" not in movement_profile.blocked_modes:
        combat_fly = _resolve_movement_value(race.combat_fly_speed, "fly_combat")
        march_fly = _resolve_movement_value(race.march_fly_speed, "fly_march")
        sprint_fly = _resolve_movement_value(race.sprint_fly_speed, "fly_sprint")
        fly_value = " / ".join(
            (
                format_compact_number(combat_fly),
                format_compact_number(march_fly),
                format_compact_number(sprint_fly),
            )
        )
    return {
        "combat": "-" if ground_combat is None else format_compact_number(ground_combat),
        "march": "-" if ground_march is None else format_compact_number(ground_march),
        "sprint": "-" if ground_sprint is None else format_compact_number(ground_sprint),
        "swim": swim_value,
        "fly": fly_value,
    }


def build_inventory_partial_context(character: Character) -> dict[str, object]:
    """Build the minimal context needed to redraw the inventory panel."""
    inventory_rows = _build_inventory_rows(character)
    inventory_total_weight_display = _build_inventory_total_weight_display(character)
    carry_state = ItemEngine.carry_state_for_character(character)
    return {
        "character": character,
        "inventory_rows": [row for row in inventory_rows if not row.get("is_stored")],
        "stored_inventory_rows": [row for row in inventory_rows if row.get("is_stored")],
        "inventory_total_weight_display": inventory_total_weight_display,
        "carry_load": {
            "enabled": bool(character.carry_load_enabled),
            "update_url": reverse("update_carry_load_state", args=[character.pk]),
            "weight": str(carry_state["weight"]),
            "weight_display": inventory_total_weight_display,
            "penalty": int(carry_state["penalty"]),
            "state_label": str(carry_state["state_label"]),
            "tooltip": _build_carry_load_tooltip(carry_state, active=False),
            "tooltip_active": _build_carry_load_tooltip(carry_state, active=True),
        },
    }


def build_character_sheet_context(
    character: Character,
    *,
    close_learn_window_once: bool = False,
    read_only: bool = False,
    sl_effect_group_id: int | None = None,
) -> dict[str, object]:
    """Build the full character-sheet context without direct template calculations."""
    engine = character.engine
    base_engine = CharacterEngine(character)
    attributes = engine.attributes()
    attr_mods = {
        short_name: format_modifier(engine.attribute_modifier(short_name))
        for short_name, _label in ATTRIBUTE_ORDER
    }
    attribute_rows = [
        {
            "short_name": short_name,
            "label": label,
            "value": attributes.get(short_name, 0),
            "modifier": attr_mods[short_name],
            "runtime_adjustment": int(engine.runtime_attribute_adjustments.get(short_name, 0)),
        }
        for short_name, label in ATTRIBUTE_ORDER
    ]
    load_penalty = engine.load_penalty()
    carry_state = ItemEngine.carry_state_for_character(character)
    carry_penalty = int(carry_state["penalty"])
    skill_rows, character_skills, skill_manager_rows = _build_skill_rows(
        character,
        engine,
        load_penalty=load_penalty,
    )
    for row in skill_rows:
        if "with_load_total_value" not in row:
            continue
        base_with_load_total = int(row.get("with_load_total_value", 0) or 0)
        row["carry_with_load_total_value"] = base_with_load_total + carry_penalty
        row["carry_with_load_total"] = base_with_load_total + carry_penalty
    advantage_rows, disadvantage_rows = _build_trait_rows(character)
    inventory_rows = _build_inventory_rows(character, sl_effect_group_id=sl_effect_group_id)
    carried_inventory_rows = [row for row in inventory_rows if not row.get("is_stored")]
    stored_inventory_rows = [row for row in inventory_rows if row.get("is_stored")]
    inventory_total_weight_display = _build_inventory_total_weight_display(character)
    weapon_rows = _build_weapon_rows(engine, sl_effect_group_id=sl_effect_group_id)
    for row in weapon_rows:
        row["carry_with_bel_value"] = int(row.get("with_bel_value", 0) or 0) + carry_penalty
        row["carry_with_bel_display"] = format_modifier(int(row["carry_with_bel_value"]))
        row["carry_calculation_tooltip"] = _build_weapon_calculation_tooltip(
            engine,
            row,
            extra_load_penalty=carry_penalty,
        )
    battle_calculator_payload = BattleCalculatorEngine.build_payload(engine, skill_rows, weapon_rows)
    armor_rows = _build_armor_rows(engine, sl_effect_group_id=sl_effect_group_id)
    armor_zone_protection = engine.armor_zone_protection()
    body_armor = {
        "shield": engine.shield_protection(),
        **armor_zone_protection,
    }
    school_technique_rows, school_levels = _build_school_technique_rows(character, engine)
    cultist_corruption_level = _cultist_corruption_level(engine)
    school_race_rows, school_technique_groups = _group_school_technique_rows(
        school_technique_rows,
        school_levels,
        character,
    )
    language_rows, language_entries = _build_language_rows(character)
    weapon_mastery_arcana_panel = _build_weapon_mastery_arcana_panel(engine)
    daemonic_power_panel = _build_daemonic_power_panel(character, engine)

    initiative_value = engine.calculate_initiative()
    initiative_stat_mod = engine._resolve_stat_modifiers(INITIATIVE)
    initiative_wa_mod = engine.attribute_modifier(ATTR_WA)
    initiative_wound_penalty = engine.current_wound_penalty()
    current_wound_stage, _current_wound_penalty_stage = engine.current_wound_stage()
    current_wound_penalty = engine.current_wound_penalty_raw()
    current_wound_penalty_display = (
        "-"
        if current_wound_stage == "-"
        else format_modifier(current_wound_penalty)
    )
    can_act_while_out_of_action = engine.can_act_while_out_of_action()
    is_wound_stage_disabled = (
        engine.is_wound_penalty_ignored()
        and current_wound_stage not in {"Ausser Gefecht", "Außer Gefecht", "Koma", "Tod"}
    ) or (
        can_act_while_out_of_action
        and current_wound_stage in {"Ausser Gefecht", "Außer Gefecht"}
    )

    wound_threshold_data = engine.wound_thresholds()
    wound_threshold_rows = [
        {"threshold": threshold, "stage": stage, "penalty": penalty}
        for threshold, (stage, penalty) in sorted(wound_threshold_data.items())
    ]
    current_damage_max = max(wound_threshold_data.keys()) if wound_threshold_data else 0
    damage_gauge = _build_damage_gauge_data(
        current_damage=character.current_damage,
        threshold_rows=wound_threshold_rows,
        damage_max=current_damage_max,
        stun_damage=character.current_stun_damage,
        lethal_damage=character.current_lethal_damage,
    )
    wallet_gold, wallet_silver, wallet_copper = engine.km_to_coins()
    vw_ge_mod = engine.attribute_modifier(ATTR_GE)
    vw_wa_mod = engine.attribute_modifier(ATTR_WA)
    if engine.resolve_flags().get("suppress_positive_vw_attribute_bonuses", False):
        vw_ge_mod = min(0, vw_ge_mod)
        vw_wa_mod = min(0, vw_wa_mod)
    vw_stat_mod = engine._resolve_stat_modifiers(DEFENSE_VW)
    sr_st_mod = engine.attribute_modifier(ATTR_ST)
    sr_kon_mod = engine.attribute_modifier(ATTR_KON)
    sr_stat_mod = engine._resolve_stat_modifiers(DEFENSE_SR)
    sr_value = engine.sr()
    gw_int_mod = engine.attribute_modifier(ATTR_INT)
    gw_will_mod = engine.attribute_modifier(ATTR_WILL)
    gw_stat_mod = engine._resolve_stat_modifiers(DEFENSE_GW)
    gw_value = engine.gw()
    willpower = attributes.get(ATTR_WILL, 0)
    school_level_total = sum(school_levels.values())
    magic_engine = character.get_magic_engine()
    aspect_level_total = sum(
        int(entry.level)
        for entry in magic_engine.get_character_aspects()
        if entry.is_bonus_aspect
    )
    from charsheet.engine.vampire_engine import VampireRules

    vampire_rules = VampireRules(character)
    is_vampire = vampire_rules.is_vampire()
    if is_vampire:
        vampire_resource = vampire_rules.resource_state()
        arcane_power_value = vampire_resource.maximum
        potential_value = vampire_resource.potential
        current_arcane_power = vampire_resource.intelligent
        resource_label = "Blut intelligenter Wesen"
        vampire_traits, vampire_powers = _vampire_sheet_entries(vampire_rules)
        vampire_panel = {
            "age_cycle": vampire_rules.age_cycle(),
            "intelligent_blood": vampire_resource.intelligent,
            "animal_blood": vampire_resource.animal,
            "total_blood": vampire_resource.total,
            "total_meter_percent": f"{(0 if vampire_resource.maximum <= 0 else vampire_resource.total / vampire_resource.maximum * 100):.2f}",
            "intelligent_meter_percent": f"{(0 if vampire_resource.maximum <= 0 else vampire_resource.intelligent / vampire_resource.maximum * 100):.2f}",
            "animal_meter_percent": f"{(0 if vampire_resource.maximum <= 0 else vampire_resource.animal / vampire_resource.maximum * 100):.2f}",
            "capacity": vampire_resource.maximum,
            "potential": vampire_resource.potential,
            "state": character.vampire_state,
            "state_label": VAMPIRE_STATE_UI_LABELS.get(character.vampire_state, character.vampire_state),
            "day_count": character.vampire_day_count,
            "last_qualifying_kill_day": character.vampire_last_qualifying_kill_day,
            "recent_qualifying_kill": vampire_rules.has_recent_qualifying_kill(),
            "can_regenerate": vampire_rules.can_regenerate(),
            "regeneration_blood": character.vampire_regeneration_blood,
            "regeneration_target_cost": character.vampire_regeneration_target_cost,
            "pending_starvation": character.vampire_pending_starvation,
            "sacrament_age_bonus": character.vampire_sacrament_age_bonus,
            "sacrament_rounds_remaining": character.vampire_sacrament_rounds_remaining,
            "aggravated_damage": character.current_aggravated_damage,
            "warnings": vampire_rules.warnings(),
            "traits": vampire_traits,
            "trait_groups": _vampire_trait_groups(vampire_traits),
            "powers": vampire_powers,
            **_vampire_learning_payload(character, vampire_rules),
        }
    else:
        arcane_power_value = engine.calculate_arcane_power()
        potential_value = engine.calculate_potential()
        current_arcane_power = character.current_arcane_power
        if current_arcane_power is None:
            current_arcane_power = arcane_power_value
        current_arcane_power = max(0, int(current_arcane_power))
        current_arcane_power = min(current_arcane_power, int(arcane_power_value))
        resource_label = "Arkane Macht"
        vampire_panel = None
    arcane_power_display_max = int(arcane_power_value)
    arcane_meter_percent = 0 if arcane_power_display_max <= 0 else (current_arcane_power / arcane_power_display_max) * 100.0
    vw_value = engine.vw()

    race = character.race
    size_class = getattr(race, "size_class", None) or getattr(race, "height_class", "-") or "-"
    size_class_mod = (
        format_modifier(int(GK_MODS[size_class]))
        if size_class in GK_MODS
        else "-"
    )
    movement_ground = _build_movement_ground(engine, race)

    learning_context = _build_learning_rows(
        character,
        attributes,
        character_skills,
        language_entries,
        school_levels,
        engine=base_engine,
        synchronize=not read_only,
    )
    lesson_context = _build_lesson_context(character, engine=base_engine, read_only=read_only)
    learning_progression_context = build_learning_progression_context(
        character,
        engine=base_engine,
        synchronize=not read_only,
    )

    spell_panel_data = magic_engine.get_spell_panel_data()
    spell_panel_divine_summary = dict(spell_panel_data["divine_summary"])

    divine_binding = magic_engine._divine_binding()

    if (
        divine_binding is not None
        and is_clerical_school(divine_binding.entity.school)
    ):
        divine_school_id = int(divine_binding.entity.school_id)
        priest_aspects = list(
            spell_panel_divine_summary.get("aspects", [])
        )

        tooltip_lines = []

        entity_name = str(
            spell_panel_divine_summary.get("entity_name") or ""
        ).strip()
        entity_kind = str(
            spell_panel_divine_summary.get("entity_kind") or ""
        ).strip()

        if entity_name:
            tooltip_lines.append(
                " | ".join(
                    value
                    for value in (entity_name, entity_kind)
                    if value
                )
            )

        if priest_aspects:
            tooltip_lines.extend(["", "Aspekte:"])
            tooltip_lines.extend(
                f"- {aspect['name']} {aspect['level']}"
                for aspect in priest_aspects
            )

        for group in school_technique_groups:
            if int(group.get("school_id") or 0) == divine_school_id:
                group["priest_aspects"] = priest_aspects
                group["priest_tooltip"] = "\n".join(tooltip_lines)
                break

    visible_school_group_ids = {
        int(group["school_id"])
        for group in school_technique_groups
        if group.get("school_id")
    }
    spell_panel_arcane_schools = [
        school
        for school in spell_panel_data["arcane_schools"]
        if int(school.get("id") or 0) not in visible_school_group_ids
    ]
    divine_binding = magic_engine._divine_binding()
    if (
        divine_binding is not None
        and int(school_levels.get(divine_binding.entity.school_id, 0) or 0) <= 0
    ):
        divine_binding = None
    divine_entity = divine_binding.entity if divine_binding is not None else None
    druid_binding = (
        CharacterDruidCult.objects.filter(character=character)
        .select_related("cult", "cult__school")
        .prefetch_related("cult__aspects", "cult__aspects__aspect")
        .first()
    )
    druid_cult = druid_binding.cult if druid_binding is not None else None
    shaman_binding = (
        CharacterShamanPatron.objects.filter(character=character)
        .select_related("patron", "patron__school")
        .prefetch_related("patron__aspects", "patron__aspects__aspect", "core_aspects")
        .first()
    )
    shaman_patron = shaman_binding.patron if shaman_binding is not None else None
    divine_symbol_url = ""
    divine_card_image_url = ""
    divine_card_title = ""
    divine_card_kind_label = ""
    divine_card_typebar = ""
    divine_card_ability = ""
    divine_card_fluff = ""
    divine_card_aspects = []
    divine_card_show_aspect_placeholder = False
    divine_card_aspect_placeholders = []
    divine_card_editable = False
    divine_card_update_url = ""
    divine_card_aspect_options = []
    divine_card_storage_key = ""
    druid_card_image_url = ""
    druid_card_title = ""
    druid_card_kind_label = ""
    druid_card_typebar = ""
    druid_card_ability = ""
    druid_card_fluff = ""
    druid_card_aspects = []
    druid_card_show_aspect_placeholder = False
    druid_card_aspect_placeholders = []
    druid_card_editable = False
    druid_card_update_url = ""
    druid_card_aspect_options = []
    druid_card_storage_key = ""
    shaman_card_image_url = ""
    shaman_card_title = ""
    shaman_card_kind_label = ""
    shaman_card_kind_value = ""
    shaman_card_kind_options = []
    shaman_card_typebar = ""
    shaman_card_ability = ""
    shaman_card_fluff = ""
    shaman_card_aspects = []
    shaman_card_show_aspect_placeholder = False
    shaman_card_aspect_placeholders = []
    shaman_card_aspect_options = []
    shaman_card_editable = False
    shaman_card_update_url = ""
    shaman_card_storage_key = ""
    shaman_card_holo_kind = ""
    if divine_entity is not None and divine_entity.symbol_image:
        divine_symbol_url = divine_entity.symbol_image.url
    if divine_entity is not None:
        divine_card_storage_key = f"god.{divine_entity.pk}"
        divine_card_kind_label = _divine_entity_card_kind_label(divine_entity)
        if divine_binding is not None and divine_binding.custom_god_image:
            divine_card_image_url = divine_binding.custom_god_image.url
        elif divine_entity.god_image:
            divine_card_image_url = divine_entity.god_image.url
        divine_card_title = (
            divine_binding.custom_name
            if divine_binding is not None and divine_binding.custom_name
            else (divine_entity.card_name or divine_entity.name)
        )
        divine_card_typebar = divine_binding.tradition_name if divine_binding is not None and divine_binding.tradition_name else divine_entity.pantheon
        divine_card_ability = (
            divine_binding.custom_g_ability
            if divine_binding is not None and divine_binding.custom_g_ability
            else divine_entity.g_ability
        )
        divine_card_fluff = (
            divine_binding.custom_fluff
            if divine_binding is not None and divine_binding.custom_fluff
            else divine_entity.fluff
        )
        divine_card_editable = bool(divine_binding is not None and divine_entity.is_customizable)
        if divine_card_editable:
            divine_card_update_url = f"/character/{character.pk}/divine-card/update/"
        divine_card_aspects = [
            entry.aspect
            for entry in divine_entity.aspects.all()
            if entry.aspect_id and entry.is_starting_aspect
        ]
        if divine_binding is not None and divine_entity.aspect_selection_mode != "fixed":
            divine_card_aspects = list(divine_binding.core_aspects.all().order_by("name", "id"))
            open_aspect_slots = max(0, int(divine_entity.starting_aspect_count) - len(divine_card_aspects))
            divine_card_aspect_placeholders = list(range(open_aspect_slots))
            divine_card_show_aspect_placeholder = bool(divine_card_aspect_placeholders)
        if divine_card_editable and divine_entity.aspect_selection_mode == "choose_from_entity":
            divine_card_aspect_options = [
                entry.aspect
                for entry in divine_entity.aspects.all()
                if entry.aspect_id
            ]
        elif divine_card_editable and divine_entity.aspect_selection_mode == "free":
            divine_card_aspect_options = list(Aspect.objects.all().order_by("name", "id"))
    if druid_cult is not None:
        druid_card_storage_key = f"druid.{druid_cult.pk}"
        druid_card_kind_label = "Krafttier"
        if druid_binding is not None and druid_binding.custom_god_image:
            druid_card_image_url = druid_binding.custom_god_image.url
        elif druid_cult.god_image:
            druid_card_image_url = druid_cult.god_image.url
        druid_card_title = (
            druid_binding.custom_name
            if druid_binding is not None and druid_binding.custom_name
            else (druid_cult.card_name or druid_cult.name)
        )
        druid_card_typebar = (
            druid_binding.tradition_name
            if druid_binding is not None and druid_binding.tradition_name
            else druid_cult.name
        )
        druid_card_ability = (
            druid_binding.custom_g_ability
            if druid_binding is not None and druid_binding.custom_g_ability
            else (druid_cult.g_ability or druid_cult.description)
        )
        druid_card_fluff = (
            druid_binding.custom_fluff
            if druid_binding is not None and druid_binding.custom_fluff
            else druid_cult.fluff
        )
        druid_card_editable = bool(druid_binding is not None and druid_cult.is_customizable)
        if druid_card_editable:
            druid_card_update_url = f"/character/{character.pk}/druid-card/update/"
        druid_card_aspects = [
            entry.aspect
            for entry in druid_cult.aspects.all()
            if entry.aspect_id and entry.is_starting_aspect
        ]
        if druid_binding is not None and druid_cult.aspect_selection_mode != "fixed":
            druid_card_aspects = list(druid_binding.core_aspects.all().order_by("name", "id"))
            open_aspect_slots = max(0, int(druid_cult.starting_aspect_count) - len(druid_card_aspects))
            druid_card_aspect_placeholders = list(range(open_aspect_slots))
            druid_card_show_aspect_placeholder = bool(druid_card_aspect_placeholders)
        if druid_card_editable and druid_cult.aspect_selection_mode == "choose_from_entity":
            druid_card_aspect_options = [
                entry.aspect
                for entry in druid_cult.aspects.all()
                if entry.aspect_id
            ]
        elif druid_card_editable and druid_cult.aspect_selection_mode == "free":
            druid_card_aspect_options = list(Aspect.objects.all().order_by("name", "id"))
    if shaman_patron is not None:
        shaman_card_storage_key = f"shaman.{shaman_patron.pk}"
        shaman_card_kind_value = (
            shaman_binding.patron_kind_override
            if shaman_binding is not None and shaman_binding.patron_kind_override
            else shaman_patron.patron_kind
        )
        shaman_card_kind_label = "Ahnengeist" if shaman_card_kind_value == "ancestor_spirit" else "Totem"
        shaman_card_holo_kind = "ancestor-spirit" if shaman_card_kind_value == "ancestor_spirit" else "power-animal"
        shaman_card_editable = bool(shaman_binding is not None and shaman_patron.is_customizable)
        if shaman_card_editable:
            shaman_card_update_url = f"/character/{character.pk}/shaman-card/update/"
            if shaman_patron.slug == "ursprung":
                shaman_card_kind_options = [
                    {"value": "totem", "label": "Totem"},
                    {"value": "ancestor_spirit", "label": "Ahnengeist"},
                ]
        if shaman_binding is not None and shaman_binding.custom_god_image:
            shaman_card_image_url = shaman_binding.custom_god_image.url
        elif shaman_patron.god_image:
            shaman_card_image_url = shaman_patron.god_image.url
        shaman_card_title = (
            shaman_binding.custom_name if shaman_binding is not None and shaman_binding.custom_name is not None
            else shaman_patron.card_name or shaman_patron.name
        )
        shaman_card_typebar = (
            shaman_binding.tradition_name if shaman_binding is not None and shaman_binding.tradition_name is not None
            else shaman_patron.school.name if shaman_patron.school_id
            else shaman_patron.get_patron_kind_display()
        )
        shaman_card_ability = (
            shaman_binding.custom_g_ability if shaman_binding is not None and shaman_binding.custom_g_ability is not None
            else shaman_patron.g_ability
        )
        shaman_card_fluff = (
            shaman_binding.custom_fluff if shaman_binding is not None and shaman_binding.custom_fluff is not None
            else shaman_patron.fluff
        )
        shaman_card_aspects = list(shaman_patron.aspects.all().order_by("name", "id"))
        if shaman_patron.aspect_selection_mode != "fixed" and shaman_binding is not None:
            shaman_card_aspects = list(shaman_binding.core_aspects.all().order_by("name", "id"))
            open_aspect_slots = max(0, int(shaman_patron.starting_aspect_count) - len(shaman_card_aspects))
            shaman_card_aspect_placeholders = list(range(open_aspect_slots))
            shaman_card_show_aspect_placeholder = bool(shaman_card_aspect_placeholders)
        if shaman_card_editable and shaman_patron.aspect_selection_mode == "choose_from_entity":
            shaman_card_aspect_options = list(shaman_patron.aspects.all().order_by("name", "id"))
        elif shaman_card_editable and shaman_patron.aspect_selection_mode == "free":
            shaman_card_aspect_options = list(Aspect.objects.all().order_by("name", "id"))
    load_tooltip = _build_load_tooltip(engine)
    load_tooltip_with_carry = _build_combined_load_tooltip(engine, carry_state, carry_enabled=True)
    total_armor_tooltip = _build_total_armor_tooltip(engine)
    minimum_strength_tooltip = _build_minimum_strength_tooltip(engine)
    carry_toggle_tooltip = _build_carry_load_tooltip(carry_state, active=False)
    carry_toggle_tooltip_active = _build_carry_load_tooltip(carry_state, active=True)
    shop_quality_choices = [
        {
            "value": quality.code,
            "label": quality.name,
            "color": quality.hex_color,
        }
        for quality in Quality.objects.all()
    ]

    manual_personal_fame_point = max(
        0,
        int(character.personal_fame_point) + int(engine.resolve_resource("personal_fame_point")),
    )
    manual_personal_fame_total = max(
        0,
        (int(character.personal_fame_rank) * 10) + int(character.personal_fame_point),
    )
    base_personal_fame_rank = max(
        0,
        int(character.personal_fame_rank) + int(engine.resolve_resource("personal_fame_rank")),
    )
    effective_artefact_rank = max(
        0,
        int(character.artefact_rank) + int(engine.resolve_resource("artefact_rank")),
    )
    auto_school_fame_point = engine.auto_school_fame_points()
    auto_lesson_fame_point = engine.auto_lesson_fame_points()
    auto_progression_fame_point = auto_school_fame_point + auto_lesson_fame_point
    total_personal_fame_point = manual_personal_fame_point + auto_progression_fame_point
    effective_personal_fame_point = total_personal_fame_point % 10
    effective_personal_fame_rank = base_personal_fame_rank + (total_personal_fame_point // 10)
    fame_total_rank = effective_personal_fame_rank + int(character.sacrifice_rank) + effective_artefact_rank

    active_creature_cards = (
        sync_character_creatures(character)
        if not read_only
        else list(
            CharacterCreature.objects.filter(owner=character, active=True)
            .select_related("creature", "source_binding", "quality")
            .prefetch_related(
                "trait_overrides__trait",
                "commands__command",
                "skill_overrides__skill",
                "special_skill_overrides__skill",
                "hidden_skill_notes",
            )
        )
    )
    creature_card_contexts = []
    character_creature_card_rows = []
    for card in active_creature_cards:
        card_context = CreatureEngine(card).card_context()
        card_context["adjust_damage_url"] = reverse("adjust_creature_damage", kwargs={"pk": card.pk})
        card_context["training_update_url"] = reverse("update_character_creature_training", kwargs={"pk": card.pk})
        if (
            card.source_selection_completed
            and (
                card.semantic_effect_is_choice
                or (
                    card.source_binding_id
                    and card.source_binding.selection_mode == CreatureSourceBinding.SelectionMode.CHARACTER_CHOICE
                )
            )
        ):
            card_context["reset_choice_url"] = reverse(
                "reset_technique_creature_choice",
                kwargs={"pk": card.pk},
            )
        if read_only:
            card_context["adjust_damage_url"] = ""
            card_context.pop("training_update_url", None)
            card_context.pop("reset_choice_url", None)
        if (
            (
                card.semantic_effect_is_choice
                or (
                    card.source_binding_id
                    and card.source_binding.selection_mode == CreatureSourceBinding.SelectionMode.CHARACTER_CHOICE
                )
            )
            and not card.source_selection_completed
        ):
            choice_label = (
                "Kreatur"
                if card.semantic_effect_is_choice
                else (card.source_binding.choice_label or "Tiergestalt").strip()
            )
            card_context["is_creation_placeholder"] = True
            card_context["creation_title"] = choice_label
            card_context["creation_choice"] = {
                "label": choice_label,
                "create_url": (
                    reverse("choose_semantic_effect_creature", kwargs={"pk": card.pk})
                    if card.semantic_effect_is_choice
                    else reverse(
                        "choose_technique_creature",
                        kwargs={"character_id": character.pk, "binding_id": card.source_binding_id},
                    )
                ),
                "templates": list(Creature.objects.order_by("name", "id")),
            }
        mini_context = {**card_context, "adjust_damage_url": "", "damage_controls_disabled": True}
        mini_context.pop("training_update_url", None)
        mini_context.pop("reset_choice_url", None)
        mini_context.pop("creation_choice", None)
        training_context = build_creature_card_training_context(card)
        creature_card_contexts.append({"card": card, "context": card_context, "mini_context": mini_context, "training_context": training_context})
        character_creature_card_rows.append(
            {
                "name": card.display_name,
                "source": card.original_card_name,
                "trigger": card.trigger_label,
                "active": card.active,
                "has_source_deviations": bool(card.name_override or card.image_override),
            }
        )
    creature_choice_context = build_creature_choice_progression_context(active_creature_cards)
    if creature_choice_context["learn_choice_rows"]:
        learning_progression_context["learn_choice_rows"].extend(creature_choice_context["learn_choice_rows"])
        learning_progression_context["learn_pending_decisions"].extend(creature_choice_context["learn_pending_decisions"])
        learning_progression_context["learn_choice_groups"].append(
            {"name": "Kreaturen", "rows": creature_choice_context["learn_choice_rows"]}
        )
        learning_progression_context["learn_choice_count"] = len(learning_progression_context["learn_choice_rows"])
        learning_progression_context["learn_pending_choice_count"] = len(
            learning_progression_context["learn_pending_decisions"]
        )
        learning_progression_context["learn_has_pending_choices"] = bool(
            learning_progression_context["learn_pending_decisions"]
        )

    if read_only:
        divine_card_editable = False
        divine_card_update_url = ""
        druid_card_editable = False
        druid_card_update_url = ""
        shaman_card_editable = False
        shaman_card_update_url = ""

    return {
        "character": character,
        "read_only": read_only,
        "cultist_corruption_level": cultist_corruption_level,
        "effective_personal_fame_point": effective_personal_fame_point,
        "effective_personal_fame_rank": effective_personal_fame_rank,
        "effective_artefact_rank": effective_artefact_rank,
        "auto_school_fame_point": auto_school_fame_point,
        "manual_personal_fame_point": manual_personal_fame_point,
        "manual_personal_fame_total": manual_personal_fame_total,
        "auto_lesson_fame_point": auto_lesson_fame_point,
        "auto_progression_fame_point": auto_progression_fame_point,
        "char_info_form": CharacterInfoInlineForm(instance=character),
        "selected_divine_entity": divine_entity,
        "selected_divine_binding": divine_binding,
        "selected_divine_symbol_url": divine_symbol_url,
        "selected_divine_card_image_url": divine_card_image_url,
        "selected_divine_card_title": divine_card_title,
        "selected_divine_card_kind_label": divine_card_kind_label,
        "selected_divine_card_typebar": divine_card_typebar,
        "selected_divine_card_ability": divine_card_ability,
        "selected_divine_card_fluff": divine_card_fluff,
        "selected_divine_card_aspects": divine_card_aspects,
        "selected_divine_card_show_aspect_placeholder": divine_card_show_aspect_placeholder,
        "selected_divine_card_aspect_placeholders": divine_card_aspect_placeholders,
        "selected_divine_card_editable": divine_card_editable,
        "selected_divine_card_update_url": divine_card_update_url,
        "selected_divine_card_aspect_options": divine_card_aspect_options,
        "selected_divine_card_storage_key": divine_card_storage_key,
        "selected_druid_cult": druid_cult,
        "selected_druid_binding": druid_binding,
        "selected_druid_card_image_url": druid_card_image_url,
        "selected_druid_card_title": druid_card_title,
        "selected_druid_card_kind_label": druid_card_kind_label,
        "selected_druid_card_typebar": druid_card_typebar,
        "selected_druid_card_ability": druid_card_ability,
        "selected_druid_card_fluff": druid_card_fluff,
        "selected_druid_card_aspects": druid_card_aspects,
        "selected_druid_card_show_aspect_placeholder": druid_card_show_aspect_placeholder,
        "selected_druid_card_aspect_placeholders": druid_card_aspect_placeholders,
        "selected_druid_card_editable": druid_card_editable,
        "selected_druid_card_update_url": druid_card_update_url,
        "selected_druid_card_aspect_options": druid_card_aspect_options,
        "selected_druid_card_storage_key": druid_card_storage_key,
        "selected_shaman_patron": shaman_patron,
        "selected_shaman_binding": shaman_binding,
        "selected_shaman_card_image_url": shaman_card_image_url,
        "selected_shaman_card_title": shaman_card_title,
        "selected_shaman_card_kind_label": shaman_card_kind_label,
        "selected_shaman_card_kind_value": shaman_card_kind_value,
        "selected_shaman_card_kind_options": shaman_card_kind_options,
        "selected_shaman_card_typebar": shaman_card_typebar,
        "selected_shaman_card_ability": shaman_card_ability,
        "selected_shaman_card_fluff": shaman_card_fluff,
        "selected_shaman_card_aspects": shaman_card_aspects,
        "selected_shaman_card_show_aspect_placeholder": shaman_card_show_aspect_placeholder,
        "selected_shaman_card_aspect_placeholders": shaman_card_aspect_placeholders,
        "selected_shaman_card_aspect_options": shaman_card_aspect_options,
        "selected_shaman_card_editable": shaman_card_editable,
        "selected_shaman_card_update_url": shaman_card_update_url,
        "selected_shaman_card_storage_key": shaman_card_storage_key,
        "selected_shaman_card_holo_kind": shaman_card_holo_kind,
        "creature_card_contexts": creature_card_contexts,
        "character_creature_card_rows": character_creature_card_rows,
        "skill_specification_form": CharacterSkillSpecificationForm(),
        "technique_specification_form": CharacterTechniqueSpecificationForm(),
        "trait_specification_form": CharacterTraitSpecificationForm(),
        "fame_total_rank": fame_total_rank,
        "attributes": attributes,
        "attr_mods": attr_mods,
        "attribute_rows": attribute_rows,
        "skill_rows": skill_rows,
        "skill_manager_rows": skill_manager_rows,
        "advantage_rows": advantage_rows,
        "disadvantage_rows": disadvantage_rows,
        "inventory_rows": carried_inventory_rows,
        "stored_inventory_rows": stored_inventory_rows,
        "inventory_total_weight_display": inventory_total_weight_display,
        "carry_load": {
            "enabled": bool(character.carry_load_enabled),
            "update_url": reverse("update_carry_load_state", args=[character.pk]),
            "weight": str(carry_state["weight"]),
            "weight_display": inventory_total_weight_display,
            "penalty": carry_penalty,
            "state_label": str(carry_state["state_label"]),
            "tooltip": carry_toggle_tooltip,
            "tooltip_active": carry_toggle_tooltip_active,
        },
        "weapon_rows": weapon_rows,
        "battle_calculator_payload": battle_calculator_payload,
        "armor_rows": armor_rows,
        "school_technique_rows": school_technique_rows,
        "school_race_rows": school_race_rows,
        "school_technique_groups": school_technique_groups,
        "core_stats": {
            "load_value": load_penalty,
            "load_tooltip": load_tooltip,
            "load_value_with_carry": load_penalty + carry_penalty,
            "load_tooltip_with_carry": load_tooltip_with_carry,
            "initiative_display": format_modifier(initiative_value),
            "initiative_with_load_display": format_modifier(initiative_value + load_penalty),
            "initiative_with_load_value": initiative_value + load_penalty,
            "initiative_with_load_display_with_carry": format_modifier(initiative_value + load_penalty + carry_penalty),
            "initiative_condition_badge": _build_core_stat_condition_badge(engine, INITIATIVE),
            "initiative_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "WA-Bonus/Malus", "value": format_modifier(initiative_wa_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "= Gesamt", "value": format_modifier(initiative_value), "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, INITIATIVE),
            ),
            "initiative_with_load_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "WA-Bonus/Malus", "value": format_modifier(initiative_wa_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "Belastung", "value": format_modifier(load_penalty)},
                    {"label": "= Gesamt", "value": format_modifier(initiative_value + load_penalty), "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, INITIATIVE),
            ),
            "initiative_with_load_tooltip_with_carry": _build_core_stat_tooltip(
                [
                    {"label": "WA-Bonus/Malus", "value": format_modifier(initiative_wa_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "Rüstungsbelastung", "value": format_modifier(load_penalty)},
                    {"label": "Traglast", "value": format_modifier(carry_penalty), "source": str(carry_state["state_label"])},
                    {
                        "label": "= Gesamt",
                        "value": format_modifier(initiative_value + load_penalty + carry_penalty),
                        "tone": "total",
                    },
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, INITIATIVE),
            ),
            "vw": vw_value,
            "vw_condition_badge": _build_core_stat_condition_badge(engine, DEFENSE_VW),
            "vw_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "GE-Bonus/Malus", "value": format_modifier(vw_ge_mod)},
                    {"label": "WA-Bonus/Malus", "value": format_modifier(vw_wa_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_VW),
                    {"label": "= Gesamt", "value": vw_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, DEFENSE_VW),
            ),
            "sr": sr_value,
            "sr_condition_badge": _build_core_stat_condition_badge(engine, DEFENSE_SR),
            "sr_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "ST-Bonus/Malus", "value": format_modifier(sr_st_mod)},
                    {"label": "KON-Bonus/Malus", "value": format_modifier(sr_kon_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_SR),
                    {"label": "= Gesamt", "value": sr_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, DEFENSE_SR),
            ),
            "gw": gw_value,
            "gw_condition_badge": _build_core_stat_condition_badge(engine, DEFENSE_GW),
            "gw_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "INT-Bonus/Malus", "value": format_modifier(gw_int_mod)},
                    {"label": "WILL-Bonus/Malus", "value": format_modifier(gw_will_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_GW),
                    {"label": "= Gesamt", "value": gw_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, DEFENSE_GW),
            ),
            "arcane_power": arcane_power_value,
            "arcane_power_condition_badge": _build_core_stat_condition_badge(engine, ARCANE_POWER),
            "arcane_power_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Willenskraft", "value": vampire_rules.willpower()},
                    {"label": "Magie-/Kampfschulen", "value": vampire_rules.school_ranks()},
                    {"label": "Vampirkräfte", "value": vampire_rules.power_ranks()},
                    {"label": "Alterszyklus", "value": vampire_rules.age_cycle()},
                    {"label": "Zusatzkapazität", "value": vampire_rules.capacity_bonus()},
                    {"label": "Permanenter Verlust", "value": -vampire_rules.capacity_loss()},
                    {"label": "= Blutvorrat", "value": arcane_power_value, "tone": "total"},
                ]
                if is_vampire
                else [
                    {"label": "Will", "value": willpower},
                    {"label": "Stufen in Schulen", "value": school_level_total},
                    {"label": "Bonus-Aspektstufen", "value": aspect_level_total},
                    *_build_modifier_breakdown_rows(engine, ARCANE_POWER),
                    {"label": "= Gesamt", "value": arcane_power_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, ARCANE_POWER),
            ),
            "potential": potential_value,
            "potential_condition_badge": _build_core_stat_condition_badge(engine, POTENTIAL),
            "potential_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Will / 2", "value": willpower // 2},
                    *_build_modifier_breakdown_rows(engine, POTENTIAL),
                    {"label": "= Gesamt", "value": potential_value, "tone": "total"},
                ],
                conditional_modifiers=_conditional_core_stat_modifiers(engine, POTENTIAL),
            ),
        },
        "armor_summary": {
            "total_rs": engine.get_grs(),
            "total_rs_tooltip": total_armor_tooltip,
            "load_value": load_penalty,
            "load_tooltip": load_tooltip,
            "minimum_strength": engine.get_ms(),
            "minimum_strength_tooltip": minimum_strength_tooltip,
        },
        "body_armor": body_armor,
        "current_wound_stage": current_wound_stage,
        "current_wound_penalty": current_wound_penalty_display,
        "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
        "can_act_while_out_of_action": can_act_while_out_of_action,
        "is_wound_stage_disabled": is_wound_stage_disabled,
        "current_damage_max": current_damage_max,
        "current_stun_damage": character.current_stun_damage,
        "current_lethal_damage": character.current_lethal_damage,
        "current_aggravated_damage": character.current_aggravated_damage,
        "damage_gauge_needle_angle": damage_gauge["needle_angle"],
        "damage_gauge_stun_needle_angle": damage_gauge["stun_needle_angle"],
        "damage_gauge_lethal_needle_angle": damage_gauge["lethal_needle_angle"],
        "damage_gauge_total_needle_angle": damage_gauge["total_needle_angle"],
        "damage_gauge_segments": damage_gauge["segments"],
        "damage_gauge_gradient_stops": damage_gauge["gradient_stops"],
        "wound_threshold_rows": wound_threshold_rows,
        "current_arcane_power": current_arcane_power,
        "current_arcane_power_max": arcane_power_display_max,
        "arcane_meter_percent": f"{arcane_meter_percent:.2f}",
        "resource_label": resource_label,
        "resource_type": "blood" if is_vampire else "arcane_power",
        "is_vampire": is_vampire,
        "vampire_panel": vampire_panel,
        "wallet_gold": wallet_gold,
        "wallet_silver": wallet_silver,
        "wallet_copper": wallet_copper,
        "wallet_gold_display": format_thousands(wallet_gold),
        "wallet_silver_display": format_thousands(wallet_silver),
        "wallet_copper_display": format_thousands(wallet_copper),
        "wallet_total_ks": format_thousands(character.money),
        "size_class": size_class,
        "size_class_mod": size_class_mod,
        "movement_ground": movement_ground,
        "language_rows": language_rows,
        "shop_item_groups": _build_shop_item_groups(),
        "shop_sell_item_groups": _build_shop_sell_item_groups(character),
        "shop_quality_choices": shop_quality_choices,
        "shop_item_form_type_choices": [
            (item_type, dict(Item.ItemType.choices)[item_type])
            for item_type in SHOP_FORM_ORDER
        ],
        "shop_damage_type_choices": DAMAGE_TYPE_CHOICES,
        "shop_size_class_choices": GK_CHOICES,
        "shop_size_class_options": _size_class_options(),
        "shop_damage_source_choices": DamageSource.objects.order_by("name"),
        "shop_weapon_maneuver_attribute_choices": WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
        "shop_weapon_type_choices": [
            ("", "Nicht festgelegt"),
            *[(weapon_type.slug, weapon_type.name) for weapon_type in WeaponType.objects.order_by("sort_order", "name")],
        ],
        "shop_modifier_target_kind_choices": [
            (TEXT_TARGET_KIND, "Text"),
            (RULE_FLAG_TARGET_KIND, "Regel aktivieren"),
            ("attribute", "Attribut"),
            ("stat", "Wert auf dem Bogen"),
            ("movement", "Bewegung"),
            ("skill", "Einzelne Fertigkeit"),
            ("category", "Fertigkeitskategorie"),
            ("item", "Konkreter Gegenstand"),
            ("item_category", "Alle Gegenst\u00e4nde eines Typs"),
            ("specialization", "Spezialisierung"),
        ],
        "item_modifier_target_kind_choices": [
            (TEXT_TARGET_KIND, "Text"),
            (RULE_FLAG_TARGET_KIND, "Regel aktivieren"),
            ("attribute", "Attribut"),
            ("stat", "Wert auf dem Bogen"),
            ("movement", "Bewegung"),
            ("skill", "Einzelne Fertigkeit"),
            ("category", "Fertigkeitskategorie"),
            ("weapon_maneuver", "Bonus/Malus auf Man\u00f6ver"),
            ("weapon_damage", "Bonus/Malus auf Schaden"),
            ("weapon_damage_dice", "+ X W10"),
            (WEAPON_MANEUVER_DAMAGE, "Bonus/Malus auf Man\u00f6ver und Schaden"),
            (WEAPON_MASTERY_BONUS, WEAPON_MASTERY_EFFECT_DESCRIPTION),
            ("item", "Konkreter Gegenstand"),
            ("item_category", "Alle Gegenst\u00e4nde eines Typs"),
            ("specialization", "Spezialisierung"),
        ],
        "shop_modifier_attribute_choices": ATTRIBUTE_ORDER,
        "shop_modifier_stat_choices": STAT_SLUG_CHOICES,
        "shop_modifier_movement_choices": SHOP_MODIFIER_MOVEMENT_TARGET_CHOICES,
        "shop_modifier_rule_flag_choices": RULE_FLAG_CHOICES,
        "shop_modifier_skill_choices": Skill.objects.select_related("category").order_by("name"),
        "shop_modifier_skill_category_choices": SkillCategory.objects.order_by("name"),
        "shop_modifier_item_choices": Item.objects.order_by("name"),
        "shop_modifier_item_category_choices": [
            (value, label) for value, label in Item.ItemType.choices
        ],
        "shop_modifier_specialization_choices": Specialization.objects.order_by("name"),
        "shop_runes": Rune.objects.order_by("name"),
        "weapon_mastery_arcana_panel": weapon_mastery_arcana_panel,
        "daemonic_power_panel": daemonic_power_panel,
        "spell_panel_enabled": bool(spell_panel_data["spell_panel_enabled"]),
        "spell_and_lessons_panel_enabled": bool(spell_panel_data["spell_and_lessons_panel_enabled"]),
        "has_castable_entries": bool(spell_panel_data["has_castable_entries"]),
        "spell_panel_groups": spell_panel_data["groups"],
        "spell_panel_filter_groups": spell_panel_data.get("filter_groups", []),
        "spell_panel_arcane_schools": spell_panel_arcane_schools,
        "spell_panel_divine_summary": spell_panel_divine_summary,
        "rune_retrofit_choices": [
            {
                "id": rune.id,
                "name": rune.name,
                "description": _single_line(_rune_inline_description(rune)),
                "image": _rune_image_url(rune),
                "has_specialization": rune.has_specialization,
                "specialization_label": rune.specialization_label or "Bezeichnung",
                "allow_multiple": rune.allow_multiple,
            }
            for rune in Rune.objects.order_by("name")
        ],
        "close_learn_window_once": close_learn_window_once,
        "learn_skill_count": sum(len(group["rows"]) for group in learning_context["learn_skill_groups"]),
        "learn_trait_count": sum(len(group["rows"]) for group in learning_context["learn_trait_groups"]),
        "learn_school_count": sum(len(group["rows"]) for group in learning_context["learn_school_groups"]),
        "learn_magic_count": sum(len(group["rows"]) for group in learning_context["learn_magic_groups"]),
        **learning_context,
        **lesson_context,
        **learning_progression_context,
    }
