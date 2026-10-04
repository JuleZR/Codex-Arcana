"""Shared presentation order for semantic-effect and modifier editors."""

from charsheet.constants import (
    ARTIFACT_RANK,
    MELEE_MANEUVERS,
    STAT_SLUG_CHOICES,
    WEAPON_DAMAGE,
    WEAPON_DAMAGE_DICE,
    WEAPON_MANEUVER_DAMAGE,
    WEAPON_MASTERY_BONUS,
    WOUND_STAGE,
    WOUND_STAGE_POSITION_CHOICES,
    WOUND_STAGE_POSITION_METADATA_KEY,
    WOUND_STAGE_TARGET_PREFIX,
)


SEMANTIC_EFFECT_AREA_GROUPS = (
    ("Text / Anzeige", ("text",)),
    ("Eigenschaften & Zustände", (
        "attribute", "derived_stat", "attribute_cap", "defense",
        "wound_stage", "resource",
    )),
    ("Fertigkeiten", (
        "skill", "multi_skill", "skill_category", "special_skill",
        "specialization", "proficiency_group",
    )),
    ("Kampf & Waffen", (
        "combat", "damage_source", "attack_type_damage",
        "choice_attack_damage", "weapon", "weapon_range",
    )),
    ("Bewegung", ("movement", "creature_movement", "movement_exclusion")),
    ("Gegenstände", ("item", "item_category")),
    ("Auswahl & Zuweisung", (
        "choice_binding", "choice", "creature_card", "entity",
    )),
    ("Lernen & Progression", ("learning_slot",)),
    ("Mächte & Spezialsysteme", ("daemonic_power", "disallow_schools")),
    ("Regeln & Sonderlogik", ("rule_flag",)),
)

EFFECT_AREA_ALIASES = {
    "none": "choice",
    "creature_attack": "combat",
    ARTIFACT_RANK: "resource",
    "stat": "derived_stat",
    "category": "skill_category",
    "creature_special_skill": "special_skill",
    "damage": "combat",
    "creature_attack_type_damage": "attack_type_damage",
    "creature_attack_damage": "choice_attack_damage",
    "weapon_maneuver": "combat",
    WEAPON_DAMAGE: "combat",
    WEAPON_DAMAGE_DICE: "combat",
    WEAPON_MANEUVER_DAMAGE: "combat",
    WEAPON_MASTERY_BONUS: "combat",
}


def semantic_effect_area_optgroups(area_choices):
    """Group supplied choices, preserving their stored values and labels."""
    choices = list(area_choices or ())
    blanks = [(value, label) for value, label in choices if value == ""]
    return blanks + [
        (name, grouped)
        for name, areas in SEMANTIC_EFFECT_AREA_GROUPS
        if (grouped := [
            (value, label)
            for area in areas for value, label in choices
            if EFFECT_AREA_ALIASES.get(value, value) == area
        ])
    ]


def is_combat_stat(key):
    return key in {
        MELEE_MANEUVERS, WEAPON_DAMAGE, WEAPON_DAMAGE_DICE,
        WEAPON_MANEUVER_DAMAGE, WEAPON_MASTERY_BONUS,
    } or str(key).startswith("dmg_")


def semantic_stat_choices(choices=STAT_SLUG_CHOICES, *, combat=False):
    """Keep generic wound stages out of every new target selection."""
    return [
        (key, label) for key, label in choices
        if key != WOUND_STAGE and is_combat_stat(key) == combat
    ]


def semantic_stat_optgroups(choices):
    """Group concrete stat keys using the same domain order as effect areas."""
    choices = list(choices or ())
    targets = {
        "derived_stat": semantic_stat_choices(choices),
        "combat": semantic_stat_choices(choices, combat=True),
    }
    return [
        (name, targets[area])
        for name, areas in SEMANTIC_EFFECT_AREA_GROUPS
        for area in areas if area in targets and targets[area]
    ]


def wound_stage_position(target_key, metadata=None):
    """Read positional and legacy wound effects without changing saved data."""
    key = str(target_key or "")
    if key != WOUND_STAGE and not key.startswith(WOUND_STAGE_TARGET_PREFIX):
        return ""
    encoded = key[len(WOUND_STAGE_TARGET_PREFIX):]
    position = (
        encoded if key.startswith(WOUND_STAGE_TARGET_PREFIX)
        else (metadata or {}).get(WOUND_STAGE_POSITION_METADATA_KEY)
    ) or "unverletzt"
    return position if position in dict(WOUND_STAGE_POSITION_CHOICES) else ""
