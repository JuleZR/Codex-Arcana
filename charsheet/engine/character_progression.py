"""Progression-related CharacterEngine methods."""

from __future__ import annotations


def school_level(engine, school) -> int:
    """Return the learned level for a school-like input."""
    school_id = engine._coerce_school_id(school)
    entry = engine._school_entries.get(school_id)
    return entry.level if entry else 0


def selected_school_path(engine, school):
    """Return the selected path for a school if one exists."""
    school_id = engine._coerce_school_id(school)
    entry = engine._selected_paths.get(school_id)
    return entry.path if entry else None


def specialization_slot_count(engine, school) -> int:
    """Return how many specialization slots learned techniques grant for one school."""
    school_id = engine._coerce_school_id(school)
    return engine._specialization_slot_counts_by_school_id.get(school_id, 0)


def character_specializations(engine, school) -> list:
    """Return all learned specializations of the character for one school."""
    school_id = engine._coerce_school_id(school)
    return list(engine._specialization_entries_by_school_id.get(school_id, []))


def open_specialization_slot_count(engine, school) -> int:
    """Return the number of still-unfilled specialization slots for one school."""
    school_id = engine._coerce_school_id(school)
    total_slots = engine.specialization_slot_count(school_id)
    filled_slots = len(engine._specialization_entries_by_school_id.get(school_id, []))
    return max(0, total_slots - filled_slots)


def available_specializations(engine, school) -> list:
    """Return active, not-yet-learned specializations of one learned school."""
    school_id = engine._coerce_school_id(school)
    if school_id not in engine._school_entries:
        return []

    learned_ids = engine._learned_specialization_ids_by_school_id.get(school_id, set())
    return [
        specialization
        for specialization in engine._specialization_definitions_by_school_id.get(school_id, [])
        if specialization.is_active and specialization.id not in learned_ids
    ]


def technique_choice_blocks(engine, school=None) -> list[dict]:
    """Return generic technique choice block states for one school or all learned schools."""
    if school is None:
        return list(engine._choice_block_states_cache)
    school_id = engine._coerce_school_id(school)
    return [state for state in engine._choice_block_states_cache if state["school_id"] == school_id]


def active_technique_choice_blocks(engine, school=None) -> list[dict]:
    """Return choice blocks that are currently active for the character."""
    return [state for state in engine.technique_choice_blocks(school) if state["active"]]


def open_technique_choice_blocks(engine, school=None) -> list[dict]:
    """Return active choice blocks that still need additional learned techniques."""
    return [state for state in engine.technique_choice_blocks(school) if state["open"]]


def fulfilled_technique_choice_blocks(engine, school=None) -> list[dict]:
    """Return active choice blocks whose learned count is inside the valid window."""
    return [state for state in engine.technique_choice_blocks(school) if state["fulfilled"]]


def violated_technique_choice_blocks(engine, school=None) -> list[dict]:
    """Return choice blocks whose learned techniques exceed the configured maximum."""
    return [state for state in engine.technique_choice_blocks(school) if state["violated"]]


def build_choice_block_state(engine, block) -> dict:
    """Resolve active/open/fulfilled/violated state for one technique choice block."""
    school_level_value = engine.school_level(block.school_id)
    selected_path = engine.selected_school_path(block.school_id)
    techniques = engine._techniques_by_choice_block_id.get(block.id, [])
    technique_ids = [technique.id for technique in techniques]
    learned_technique_ids = [
        technique.id
        for technique in techniques
        if engine._technique_state_map.get(technique.id, {}).get("learned")
    ]
    available_technique_ids = [
        technique.id
        for technique in techniques
        if engine._technique_state_map.get(technique.id, {}).get("available")
        and technique.id not in learned_technique_ids
    ]
    active = school_level_value > 0
    if block.level is not None:
        active = active and school_level_value >= block.level
    if block.path_id is not None:
        active = active and selected_path is not None and selected_path.id == block.path_id

    learned_choice_count = len(learned_technique_ids)
    open_block = active and learned_choice_count < block.min_choices
    fulfilled = active and block.min_choices <= learned_choice_count <= block.max_choices
    violated = active and learned_choice_count > block.max_choices

    return {
        "block_id": block.id,
        "block_name": block.name or None,
        "block_description": block.description or None,
        "school_id": block.school_id,
        "school_name": block.school.name,
        "school_level": school_level_value,
        "level": block.level,
        "path_id": block.path_id,
        "path_name": block.path.name if block.path_id else None,
        "selected_path_id": selected_path.id if selected_path else None,
        "selected_path_name": selected_path.name if selected_path else None,
        "min_choices": block.min_choices,
        "max_choices": block.max_choices,
        "learned_choice_count": learned_choice_count,
        "available_choice_count": len(available_technique_ids),
        "remaining_required_choices": max(0, block.min_choices - learned_choice_count),
        "remaining_optional_choices": max(0, block.max_choices - learned_choice_count),
        "active": active,
        "open": open_block,
        "fulfilled": fulfilled,
        "violated": violated,
        "technique_ids": technique_ids,
        "learned_technique_ids": learned_technique_ids,
        "available_technique_ids": available_technique_ids,
    }


def active_progression_rules(engine) -> list[dict]:
    """Return all progression rules activated by the character's schools."""
    result: list[dict] = []
    for entry in engine._school_entries.values():
        rules = engine._progression_rules_by_type.get(entry.school.type_id, [])
        for rule in rules:
            if rule.min_level > entry.level:
                continue
            result.append(
                {
                    "school_id": entry.school_id,
                    "school_name": entry.school.name,
                    "school_level": entry.level,
                    "rule": rule,
                }
            )
    return result
