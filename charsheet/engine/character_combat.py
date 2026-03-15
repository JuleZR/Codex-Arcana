"""Combat- and wound-related CharacterEngine methods."""

from __future__ import annotations

from charsheet.constants import (
    ARCANE_POWER,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DEFENSE_GW,
    DEFENSE_SR,
    DEFENSE_VW,
    INITIATIVE,
    WOUND_PENALTY_IGNORE,
    WOUND_STAGE,
)


def fame_total(engine) -> int:
    """Return the combined fame-related score used by scaling rules."""
    return (
        engine.character.personal_fame_point
        + engine.character.personal_fame_rank
        + engine.character.sacrifice_rank
        + engine.character.artefact_rank
    )


def calculate_initiative(engine) -> int:
    """Calculate the character's initiative value."""
    return engine.attribute_modifier(ATTR_GE) + engine.current_wound_penalty() + engine._resolve_stat_modifiers(INITIATIVE)


def calculate_arcane_power(engine) -> int:
    """Calculate the character's arcane power value."""
    willpower = engine.attributes().get(ATTR_WILL, 0)
    school_levels = sum(entry.level for entry in engine._school_entries.values())
    return willpower + school_levels + engine._resolve_stat_modifiers(ARCANE_POWER)


def calculate_potential(engine) -> int:
    """Calculate the character's potential value."""
    willpower = engine.attributes().get(ATTR_WILL, 0)
    return willpower // 2


def wound_thresholds(engine) -> dict[int, tuple[str, int]]:
    """Build the wound-stage threshold table for the current character."""
    constitution = engine.attributes().get(ATTR_KON, 0)
    additional_stages = engine._resolve_stat_modifiers(WOUND_STAGE)
    amount_threshold = 6 + additional_stages

    stage_numbers = [number * constitution for number in range(1, amount_threshold + 1)]
    stage_names = [
        "Angeschlagen",
        "Verletzt",
        "Verwundet",
        "Schwer verwundet",
        "Ausser Gefecht",
        "Koma",
    ]
    stage_penalties = [0, -2, -4, -6, 0, 0]

    missing = max(0, len(stage_numbers) - len(stage_names))
    stages = ["-"] * missing + stage_names
    penalties = [0] * missing + stage_penalties

    return {
        threshold: (stage, penalty)
        for threshold, stage, penalty in zip(stage_numbers, stages, penalties)
    }


def calculate_defense(engine, mod1: str, mod2: str, slug: str) -> int:
    """Resolve one defense value from two attributes and stat modifiers."""
    return (
        14
        + engine.attribute_modifier(mod1)
        + engine.attribute_modifier(mod2)
        + engine._resolve_stat_modifiers(slug)
    )


def vw(engine) -> int:
    """Return the avoidance defense."""
    return engine.calculate_defense(ATTR_GE, ATTR_WA, DEFENSE_VW)


def gw(engine) -> int:
    """Return the mental resistance defense."""
    return engine.calculate_defense(ATTR_INT, ATTR_WILL, DEFENSE_GW)


def sr(engine) -> int:
    """Return the physical resistance defense."""
    return engine.calculate_defense(ATTR_ST, ATTR_KON, DEFENSE_SR)


def current_wound_stage(engine) -> tuple[str, int | None]:
    """Return the current wound stage and its raw penalty."""
    wound_dict = engine.wound_thresholds()
    threshold_numbers = sorted(wound_dict.keys())
    if not threshold_numbers:
        return ("-", None)

    damage = engine.character.current_damage
    if damage < threshold_numbers[0]:
        return ("-", None)
    if damage > threshold_numbers[-1]:
        return ("Tod", 0)

    current_stage: tuple[str, int | None] = ("-", None)
    for threshold in threshold_numbers:
        if damage >= threshold:
            stage_name, penalty = wound_dict[threshold]
            current_stage = (stage_name, penalty)
        else:
            break
    return current_stage


def current_wound_penalty(engine) -> int:
    """Return the effective wound penalty after ignore effects."""
    penalty = engine.current_wound_stage()[1]
    if penalty is None:
        return 0
    if engine.is_wound_penalty_ignored():
        return 0
    return penalty


def current_wound_penalty_raw(engine) -> int:
    """Return the raw wound penalty without ignore effects."""
    penalty = engine.current_wound_stage()[1]
    if penalty is None:
        return 0
    return penalty


def is_wound_penalty_ignored(engine) -> bool:
    """Return whether wound penalties are currently ignored."""
    return bool(engine._resolve_stat_modifiers(WOUND_PENALTY_IGNORE))
