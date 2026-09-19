"""Combat-, fame-, and wound-related CharacterEngine methods."""

from __future__ import annotations

from charsheet.constants import (
    ARCANE_POWER,
    CAN_ACT_WHILE_OUT_OF_ACTION,
    COMA_IGNORE,
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
    POTENTIAL,
    WOUND_PENALTY_MOD,
    WOUND_PENALTY_IGNORE,
    WOUND_STAGE,
    WOUND_STAGE_DEFINITIONS,
)


def fame_total(engine) -> int:
    """Return the combined fame-related score used by scaling rules."""
    return (
        max(0, int(engine.character.personal_fame_point) + int(engine.resolve_resource("personal_fame_point")))
        + engine.auto_school_fame_points()
        + engine.auto_lesson_fame_points()
        + max(0, int(engine.character.personal_fame_rank) + int(engine.resolve_resource("personal_fame_rank")))
        + engine.character.sacrifice_rank
        + max(0, int(engine.character.artefact_rank) + int(engine.resolve_resource("artefact_rank")))
    )


def auto_school_fame_points(engine) -> int:
    """Return the automatic fame points granted by learned school levels."""
    return sum(max(0, int(entry.level)) for entry in engine._school_entries.values())


def auto_lesson_fame_points(engine) -> int:
    """Return the automatic fame point granted by each learned lesson."""
    return engine.character.learned_lessons.count()


def calculate_initiative(engine) -> int:
    """Calculate the character's initiative value."""
    return (
        engine.attribute_modifier(ATTR_WA)
        + engine.current_wound_penalty()
        + engine._resolve_stat_modifiers(INITIATIVE)
        + engine.carry_penalty("initiative")
    )


def calculate_arcane_power(engine) -> int:
    """Calculate the character's arcane power value."""
    willpower = engine.attributes().get(ATTR_WILL, 0)
    school_levels = sum(entry.level for entry in engine._school_entries.values())
    aspect_levels = sum(
        int(entry.level)
        for entry in engine.character.get_magic_engine(refresh=True).get_character_aspects()
        if entry.is_bonus_aspect
    )
    lesson_levels = engine.character.learned_lessons.count()
    return willpower + school_levels + aspect_levels + lesson_levels + engine._resolve_stat_modifiers(ARCANE_POWER)


def calculate_potential(engine) -> int:
    """Calculate the character's potential value."""
    willpower = engine.attributes().get(ATTR_WILL, 0)
    return willpower // 2 + engine._resolve_stat_modifiers(POTENTIAL)


def wound_thresholds(engine) -> dict[int, tuple[str, int]]:
    """Build the wound-stage threshold table for the current character."""
    constitution = engine.attributes().get(ATTR_KON, 0)
    wound_effects = engine.modifier_engine.resolve_wound_stage_effects()
    legacy_additional_stages = int(wound_effects["legacy"])
    positional_additions = dict(wound_effects["positions"])

    base_stages = [
        (key, label, penalty)
        for key, label, penalty in WOUND_STAGE_DEFINITIONS
    ]
    amount_threshold = len(base_stages) + legacy_additional_stages
    if amount_threshold <= 0:
        return {}

    if amount_threshold > len(base_stages):
        stage_sequence = [
            (None, "-", 0)
            for _index in range(amount_threshold - len(base_stages))
        ] + base_stages
    else:
        # Preserve the legacy wound_stage behavior for non-positional effects:
        # negative values shorten the track from the end.
        stage_sequence = base_stages[:amount_threshold]

    expanded_sequence = []
    for stage_key, stage_name, penalty in stage_sequence:
        expanded_sequence.append((stage_name, penalty))
        if stage_key is None:
            continue
        extra_count = max(0, int(positional_additions.get(stage_key, 0) or 0))
        expanded_sequence.extend((stage_name, penalty) for _index in range(extra_count))

    return {
        index * constitution: (stage_name, penalty)
        for index, (stage_name, penalty) in enumerate(expanded_sequence, start=1)
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
    ge_bonus = engine.attribute_modifier(ATTR_GE)
    wa_bonus = engine.attribute_modifier(ATTR_WA)
    if engine.resolve_flags().get("suppress_positive_vw_attribute_bonuses", False):
        ge_bonus = min(0, ge_bonus)
        wa_bonus = min(0, wa_bonus)
    return 14 + ge_bonus + wa_bonus + engine.size_modifier() + engine._resolve_stat_modifiers(DEFENSE_VW)


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
    return penalty + engine._resolve_stat_modifiers(WOUND_PENALTY_MOD)


def current_wound_penalty_raw(engine) -> int:
    """Return the raw wound penalty without ignore effects."""
    penalty = engine.current_wound_stage()[1]
    if penalty is None:
        return 0
    return penalty + engine._resolve_stat_modifiers(WOUND_PENALTY_MOD)


def is_wound_penalty_ignored(engine) -> bool:
    """Return whether wound penalties are currently ignored."""
    return bool(engine.resolve_flags().get(WOUND_PENALTY_IGNORE, False))


def can_act_while_out_of_action(engine) -> bool:
    """Return whether the out-of-action stage still permits acting."""
    return bool(engine.resolve_flags().get(CAN_ACT_WHILE_OUT_OF_ACTION, False))


def is_wound_incapacitated(engine, wound_stage: str | None = None) -> bool:
    """Resolve wound incapacitation while keeping coma unconditional."""
    stage = wound_stage if wound_stage is not None else engine.current_wound_stage()[0]
    if stage == "Koma":
        return not bool(engine.resolve_flags().get(COMA_IGNORE, False))
    if stage in {"Ausser Gefecht", "Außer Gefecht"}:
        return not engine.can_act_while_out_of_action()
    return False
