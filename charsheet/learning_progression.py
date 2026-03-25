"""Shared helpers for progression-oriented learning panel data."""

from __future__ import annotations

from collections import OrderedDict

from charsheet.models import Item, Skill, SkillCategory, Specialization, Technique


CHOICE_FIELD_PREFIX_BY_KIND = {
    Technique.ChoiceTargetKind.SKILL: "learn_choice_skill",
    Technique.ChoiceTargetKind.SKILL_CATEGORY: "learn_choice_skill_category",
    Technique.ChoiceTargetKind.ITEM: "learn_choice_item",
    Technique.ChoiceTargetKind.ITEM_CATEGORY: "learn_choice_item_category",
    Technique.ChoiceTargetKind.SPECIALIZATION: "learn_choice_specialization",
    Technique.ChoiceTargetKind.TEXT: "learn_choice_text",
}

CHOICE_KIND_LABELS = {
    Technique.ChoiceTargetKind.SKILL: "Fertigkeit",
    Technique.ChoiceTargetKind.SKILL_CATEGORY: "Fertigkeitskategorie",
    Technique.ChoiceTargetKind.ITEM: "Gegenstand",
    Technique.ChoiceTargetKind.ITEM_CATEGORY: "Gegenstandskategorie",
    Technique.ChoiceTargetKind.SPECIALIZATION: "Spezialisierung",
    Technique.ChoiceTargetKind.TEXT: "Freitext",
    Technique.ChoiceTargetKind.ENTITY: "Andere Entitaet",
}


def choice_field_name(target_kind: str, technique_id: int, definition_id: int | None = None) -> str:
    """Return the POST field name for one technique-choice target."""
    prefix = CHOICE_FIELD_PREFIX_BY_KIND.get(target_kind)
    if not prefix:
        return ""
    suffix = str(definition_id) if definition_id is not None else "legacy"
    return f"{prefix}_{technique_id}_{suffix}"


def _build_decision_option(
    *,
    option_id: str,
    label: str,
    submit_name: str,
    submit_value: str,
    meta: str = "",
    description: str = "",
) -> dict[str, str]:
    """Return one serialized option for the choice modal payload."""
    return {
        "id": str(option_id),
        "label": label,
        "meta": meta,
        "description": description,
        "submit_name": submit_name,
        "submit_value": submit_value,
    }


def _build_pending_decision(
    *,
    decision_id: str,
    kind: str,
    title: str,
    summary: str,
    prompt: str,
    description: str = "",
    input_type: str = "options",
    options: list[dict[str, str]] | None = None,
    text_submit_name: str = "",
    text_placeholder: str = "",
    supported: bool = True,
    selection_group_id: str = "",
) -> dict[str, object]:
    """Return one structured pending decision for the learning modal flow."""
    return {
        "decision_id": decision_id,
        "kind": kind,
        "title": title,
        "summary": summary,
        "description": description,
        "prompt": prompt,
        "input_type": input_type,
        "options": options or [],
        "text_submit_name": text_submit_name,
        "text_placeholder": text_placeholder,
        "supported": supported,
        "selection_group_id": selection_group_id,
    }


def build_learning_progression_context(character, *, engine) -> dict[str, object]:
    """Build open progression decisions for the learning window."""
    path_groups: OrderedDict[str, list[dict]] = OrderedDict()
    technique_groups: OrderedDict[str, list[dict]] = OrderedDict()
    specialization_groups: OrderedDict[str, list[dict]] = OrderedDict()
    choice_groups: OrderedDict[str, list[dict]] = OrderedDict()
    pending_decisions: list[dict[str, object]] = []

    learned_school_entries = list(
        character.schools.select_related("school", "school__type").order_by("school__type__name", "school__name")
    )
    learned_school_ids = [entry.school_id for entry in learned_school_entries]
    technique_states = list(engine.technique_states())

    skill_definitions = list(Skill.objects.select_related("category").order_by("category__name", "name"))
    skill_categories = list(SkillCategory.objects.order_by("name"))
    item_definitions = list(Item.objects.order_by("name"))
    item_category_options = [{"value": value, "label": label} for value, label in Item.ItemType.choices]

    for entry in learned_school_entries:
        school = entry.school
        selected_path = engine.selected_school_path(school)
        available_paths = list(school.paths.order_by("name"))
        if available_paths and selected_path is None:
            row = {
                "field_name": f"learn_school_path_{school.id}",
                "school_id": school.id,
                "school_name": school.name,
                "school_type_name": school.type.name,
                "school_level": entry.level,
                "options": [
                    {
                        "id": path.id,
                        "name": path.name,
                        "description": path.description or "",
                    }
                    for path in available_paths
                ],
            }
            path_groups.setdefault(school.type.name, []).append(row)
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"school-path-{school.id}",
                    kind="school_path",
                    title=f"Pfadwahl: {school.name}",
                    summary=f"Schulstufe {entry.level} | {school.type.name}",
                    description="Lege den noch offenen Schulpfad fest.",
                    prompt="Pfad waehlen",
                    selection_group_id=f"school-path:{school.id}",
                    options=[
                        _build_decision_option(
                            option_id=str(option["id"]),
                            label=option["name"],
                            meta=school.type.name,
                            description=option["description"],
                            submit_name=row["field_name"],
                            submit_value=str(option["id"]),
                        )
                        for option in row["options"]
                    ],
                )
            )

    technique_choice_states = []
    for state in technique_states:
        if state["school_id"] not in learned_school_ids:
            continue
        if not state["available"] or state["learned"]:
            continue
        if state["acquisition_type"] != Technique.AcquisitionType.CHOICE:
            continue
        if state["is_choice_placeholder"]:
            continue
        technique_choice_states.append(state)
        technique_groups.setdefault(state["school_name"], []).append(
            {
                "field_name": f"learn_take_technique_{state['technique_id']}",
                "technique_id": state["technique_id"],
                "technique_name": state["technique_name"],
                "school_id": state["school_id"],
                "school_name": state["school_name"],
                "required_level": state["required_level"],
                "path_name": state["path_name"],
                "choice_block_name": state["choice_block_name"],
                "selection_notes": state["selection_notes"] or "",
                "support_level": state["support_level"],
            }
        )

    handled_technique_ids: set[int] = set()
    technique_states_by_block_id: dict[int, list[dict[str, object]]] = {}
    for state in technique_choice_states:
        block_id = state.get("choice_block_id")
        if block_id:
            technique_states_by_block_id.setdefault(block_id, []).append(state)

    for block_state in engine.open_technique_choice_blocks():
        block_id = int(block_state["block_id"])
        available_states = technique_states_by_block_id.get(block_id, [])
        if not available_states:
            continue
        handled_technique_ids.update(int(state["technique_id"]) for state in available_states)
        for slot_index in range(int(block_state["remaining_required_choices"])):
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"technique-block-{block_id}-{slot_index}",
                    kind="technique_pick",
                    title=block_state["block_name"] or f"Technikwahl: {block_state['school_name']}",
                    summary=(
                        f"{block_state['school_name']} | "
                        f"Pflichtwahl {slot_index + 1} von {block_state['remaining_required_choices']}"
                    ),
                    description=block_state["block_description"] or "Waehle eine Technik fuer diesen offenen Wahlblock.",
                    prompt="Technik waehlen",
                    selection_group_id=f"technique-block:{block_id}",
                    options=[
                        _build_decision_option(
                            option_id=str(state["technique_id"]),
                            label=state["technique_name"],
                            meta=(
                                f"Stufe {state['required_level']}"
                                + (f" | Pfad {state['path_name']}" if state["path_name"] else "")
                            ),
                            description=state["selection_notes"] or "",
                            submit_name=f"learn_take_technique_{state['technique_id']}",
                            submit_value="1",
                        )
                        for state in available_states
                    ],
                )
            )

    for row in [row for rows in technique_groups.values() for row in rows]:
        if row["technique_id"] in handled_technique_ids:
            continue
        pending_decisions.append(
            _build_pending_decision(
                decision_id=f"technique-single-{row['technique_id']}",
                kind="technique_pick",
                title=f"Technikwahl: {row['technique_name']}",
                summary=(
                    f"{row['school_name']} | Stufe {row['required_level']}"
                    + (f" | Pfad {row['path_name']}" if row["path_name"] else "")
                ),
                description=row["selection_notes"] or "Diese Technik wird als eigene Auswahlentscheidung behandelt.",
                prompt="Technik bestaetigen",
                selection_group_id=f"technique-single:{row['technique_id']}",
                options=[
                    _build_decision_option(
                        option_id=str(row["technique_id"]),
                        label=row["technique_name"],
                        meta=row["school_name"],
                        description=row["selection_notes"] or "",
                        submit_name=row["field_name"],
                        submit_value="1",
                    )
                ],
            )
        )

    for entry in learned_school_entries:
        school = entry.school
        open_slots = engine.open_specialization_slot_count(school)
        available_specializations = list(engine.available_specializations(school))
        if open_slots <= 0 or not available_specializations:
            continue
        specialization_groups.setdefault(school.name, [])
        for slot_index in range(open_slots):
            row = {
                "field_name": f"learn_specialization_pick_{school.id}_{slot_index}",
                "school_id": school.id,
                "school_name": school.name,
                "slot_index": slot_index,
                "slot_number": slot_index + 1,
                "slot_count": engine.specialization_slot_count(school),
                "open_slot_count": open_slots,
                "options": [
                    {
                        "id": specialization.id,
                        "name": specialization.name,
                        "support_level": specialization.get_support_level_display(),
                        "description": specialization.description or "",
                    }
                    for specialization in available_specializations
                ],
            }
            specialization_groups[school.name].append(row)
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"specialization-{school.id}-{slot_index}",
                    kind="specialization",
                    title=f"Spezialisierung: {school.name}",
                    summary=f"Freier Slot {slot_index + 1} von {engine.specialization_slot_count(school)}",
                    description="Vergib die noch offene Spezialisierung fuer diesen Slot.",
                    prompt="Spezialisierung waehlen",
                    selection_group_id=f"specialization:{school.id}",
                    options=[
                        _build_decision_option(
                            option_id=str(option["id"]),
                            label=option["name"],
                            meta=option["support_level"],
                            description=option["description"],
                            submit_name=row["field_name"],
                            submit_value=str(option["id"]),
                        )
                        for option in row["options"]
                    ],
                )
            )

    incomplete_states = [
        state
        for state in technique_states
        if state["learned"] and state["available"] and not state["choices_complete"]
    ]
    incomplete_technique_ids = [state["technique_id"] for state in incomplete_states]
    if incomplete_technique_ids:
        technique_map = {
            technique.id: technique
            for technique in (
                Technique.objects.filter(id__in=incomplete_technique_ids)
                .select_related("school")
                .prefetch_related("choice_definitions", "choice_definitions__allowed_skill_category")
            )
        }
        for state in incomplete_states:
            technique = technique_map.get(state["technique_id"])
            if technique is None:
                continue
            existing_choices = engine.technique_choices(technique)
            active_definitions = [definition for definition in technique.choice_definitions.all() if definition.is_active]
            if active_definitions:
                for definition in active_definitions:
                    existing_count = len([choice for choice in existing_choices if choice.definition_id == definition.id])
                    required_count = definition.min_choices if definition.is_required else 0
                    missing_count = max(0, required_count - existing_count)
                    for missing_index in range(missing_count):
                        row = _build_choice_row(
                            technique=technique,
                            engine=engine,
                            target_kind=definition.target_kind,
                            label=definition.name,
                            description=definition.description or technique.selection_notes or "",
                            definition_id=definition.id,
                            slot_index=missing_index,
                            skill_definitions=skill_definitions,
                            skill_categories=skill_categories,
                            item_definitions=item_definitions,
                            item_category_options=item_category_options,
                            allowed_skill_category_id=definition.allowed_skill_category_id,
                            allowed_skill_family=definition.allowed_skill_family or "",
                        )
                        if row is not None:
                            choice_groups.setdefault(technique.school.name, []).append(row)
            else:
                existing_count = len([choice for choice in existing_choices if choice.definition_id is None])
                missing_count = max(0, technique.choice_limit - existing_count)
                for missing_index in range(missing_count):
                    row = _build_choice_row(
                        technique=technique,
                        engine=engine,
                        target_kind=technique.choice_target_kind,
                        label=technique.name,
                        description=technique.selection_notes or "",
                        definition_id=None,
                        slot_index=missing_index,
                        skill_definitions=skill_definitions,
                        skill_categories=skill_categories,
                        item_definitions=item_definitions,
                        item_category_options=item_category_options,
                        allowed_skill_category_id=None,
                        allowed_skill_family="",
                    )
                    if row is not None:
                        choice_groups.setdefault(technique.school.name, []).append(row)

    for row in [row for rows in choice_groups.values() for row in rows]:
        input_type = "text" if row.get("allows_text_input") else "options"
        if not row["supported"]:
            input_type = "unsupported"
        if row.get("allows_text_input"):
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=(
                        f"technique-choice-{row['technique_id']}-{row['definition_id'] or 'legacy'}-{row['slot_index']}"
                    ),
                    kind="technique_choice",
                    title=f"Choice: {row['technique_name']}",
                    summary=f"{row['label']} | {row['target_label']}",
                    description=row["description"],
                    prompt="Eintrag festlegen",
                    input_type=input_type,
                    text_submit_name=row["field_name"],
                    text_placeholder="Eintrag",
                    supported=row["supported"],
                    selection_group_id=(
                        f"technique-choice:{row['technique_id']}:{row['definition_id'] or 'legacy'}"
                    ),
                )
            )
            continue

        pending_decisions.append(
            _build_pending_decision(
                decision_id=f"technique-choice-{row['technique_id']}-{row['definition_id'] or 'legacy'}-{row['slot_index']}",
                kind="technique_choice",
                title=f"Choice: {row['technique_name']}",
                summary=f"{row['label']} | {row['target_label']}",
                description=(
                    row["description"]
                    or ("Dieser Auswahltyp ist derzeit im Lernmenue noch nicht direkt belegbar." if not row["supported"] else "")
                ),
                prompt="Auswahl treffen",
                input_type=input_type,
                supported=row["supported"],
                selection_group_id=f"technique-choice:{row['technique_id']}:{row['definition_id'] or 'legacy'}",
                options=[
                    _build_decision_option(
                        option_id=str(option["value"]),
                        label=option["label"],
                        meta=option["meta"],
                        submit_name=row["field_name"],
                        submit_value=str(option["value"]),
                    )
                    for option in row["options"]
                ],
            )
        )

    return {
        "learn_school_path_groups": [{"name": name, "rows": rows} for name, rows in path_groups.items()],
        "learn_school_path_rows": [row for rows in path_groups.values() for row in rows],
        "learn_school_path_count": sum(len(rows) for rows in path_groups.values()),
        "learn_technique_groups": [{"name": name, "rows": rows} for name, rows in technique_groups.items()],
        "learn_technique_rows": [row for rows in technique_groups.values() for row in rows],
        "learn_technique_count": sum(len(rows) for rows in technique_groups.values()),
        "learn_specialization_groups": [{"name": name, "rows": rows} for name, rows in specialization_groups.items()],
        "learn_specialization_rows": [row for rows in specialization_groups.values() for row in rows],
        "learn_specialization_count": sum(len(rows) for rows in specialization_groups.values()),
        "learn_choice_groups": [{"name": name, "rows": rows} for name, rows in choice_groups.items()],
        "learn_choice_rows": [row for rows in choice_groups.values() for row in rows],
        "learn_choice_count": sum(len(rows) for rows in choice_groups.values()),
        "learn_pending_decisions": pending_decisions,
        "learn_pending_choice_count": len(pending_decisions),
        "learn_has_pending_choices": bool(pending_decisions),
    }


def _build_choice_row(
    *,
    technique,
    engine,
    target_kind: str,
    label: str,
    description: str,
    definition_id: int | None,
    slot_index: int,
    skill_definitions,
    skill_categories,
    item_definitions,
    item_category_options,
    allowed_skill_category_id: int | None,
    allowed_skill_family: str,
) -> dict[str, object] | None:
    """Return one rendered choice row for a still-missing technique decision."""
    field_name = choice_field_name(target_kind, technique.id, definition_id)
    if not field_name:
        return {
            "field_name": "",
            "supported": False,
            "target_kind": target_kind,
            "target_label": CHOICE_KIND_LABELS.get(target_kind, target_kind),
            "technique_id": technique.id,
            "technique_name": technique.name,
            "school_id": technique.school_id,
            "school_name": technique.school.name,
            "definition_id": definition_id,
            "label": label,
            "description": description,
            "slot_index": slot_index,
            "options": [],
        }

    options: list[dict[str, object]] = []
    if target_kind == Technique.ChoiceTargetKind.SKILL:
        filtered_skills = skill_definitions
        if allowed_skill_category_id is not None:
            filtered_skills = [
                skill for skill in filtered_skills if skill.category_id == allowed_skill_category_id
            ]
        if allowed_skill_family:
            filtered_skills = [skill for skill in filtered_skills if skill.family == allowed_skill_family]
        options = [
            {
                "value": skill.id,
                "label": skill.name,
                "meta": skill.category.name,
            }
            for skill in filtered_skills
        ]
    elif target_kind == Technique.ChoiceTargetKind.SKILL_CATEGORY:
        options = [{"value": category.id, "label": category.name, "meta": ""} for category in skill_categories]
    elif target_kind == Technique.ChoiceTargetKind.ITEM:
        options = [{"value": item.id, "label": item.name, "meta": item.get_item_type_display()} for item in item_definitions]
    elif target_kind == Technique.ChoiceTargetKind.ITEM_CATEGORY:
        options = [{"value": row["value"], "label": row["label"], "meta": ""} for row in item_category_options]
    elif target_kind == Technique.ChoiceTargetKind.SPECIALIZATION:
        options = [
            {
                "value": specialization.id,
                "label": specialization.name,
                "meta": specialization.get_support_level_display(),
            }
            for specialization in (
                Specialization.objects.filter(school_id=technique.school_id, is_active=True)
                .order_by("sort_order", "name")
            )
        ]
    elif target_kind == Technique.ChoiceTargetKind.TEXT:
        options = []

    return {
        "field_name": field_name,
        "supported": target_kind != Technique.ChoiceTargetKind.ENTITY,
        "target_kind": target_kind,
        "target_label": CHOICE_KIND_LABELS.get(target_kind, target_kind),
        "technique_id": technique.id,
        "technique_name": technique.name,
        "school_id": technique.school_id,
        "school_name": technique.school.name,
        "definition_id": definition_id,
        "label": label,
        "description": description,
        "slot_index": slot_index,
        "options": options,
        "allows_text_input": target_kind == Technique.ChoiceTargetKind.TEXT,
    }
