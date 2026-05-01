"""Shared helpers for progression-oriented learning panel data."""

from __future__ import annotations

from collections import OrderedDict

from charsheet.constants import (
    RESOURCE_KEY_CHOICES,
    is_allowed_trait_attribute_choice,
)
from charsheet.models import (
    Attribute,
    CharacterTrait,
    DivineEntity,
    Item,
    Rune,
    Skill,
    SkillCategory,
    Spell,
    Specialization,
    Technique,
    TraitChoiceDefinition,
    WeaponType,
)

WEAPON_MASTERY_EXCLUDED_ITEM_NAMES = {
    "Bissattacke",
    "Schwanz",
}


def weapon_mastery_weapon_type_definitions() -> list[dict[str, str]]:
    """Return weapon-type options that exist on real weapon definitions."""
    weapon_types = (
        WeaponType.objects.filter(
            weapon_stats__item__item_type=Item.ItemType.WEAPON,
        )
        .exclude(weapon_stats__item__name__in=WEAPON_MASTERY_EXCLUDED_ITEM_NAMES)
        .distinct()
        .order_by("sort_order", "name")
    )
    return [
        {
            "value": str(weapon_type.slug),
            "label": str(weapon_type.name),
        }
        for weapon_type in weapon_types
    ]


CHOICE_FIELD_PREFIX_BY_KIND = {
    TraitChoiceDefinition.TargetKind.ATTRIBUTE: "learn_choice_attribute",
    TraitChoiceDefinition.TargetKind.RESOURCE: "learn_choice_resource",
    Technique.ChoiceTargetKind.SKILL: "learn_choice_skill",
    Technique.ChoiceTargetKind.SKILL_CATEGORY: "learn_choice_skill_category",
    Technique.ChoiceTargetKind.ITEM: "learn_choice_item",
    Technique.ChoiceTargetKind.ITEM_CATEGORY: "learn_choice_item_category",
    Technique.ChoiceTargetKind.SPECIALIZATION: "learn_choice_specialization",
    Technique.ChoiceTargetKind.TEXT: "learn_choice_text",
}

CHOICE_KIND_LABELS = {
    TraitChoiceDefinition.TargetKind.ATTRIBUTE: "Attribut",
    TraitChoiceDefinition.TargetKind.RESOURCE: "Ressource",
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


def race_choice_field_name(target_kind: str, definition_id: int) -> str:
    """Return the POST field name for one race-choice target."""
    prefix = CHOICE_FIELD_PREFIX_BY_KIND.get(target_kind)
    if not prefix:
        return ""
    return f"{prefix}_race_{definition_id}"


def trait_choice_field_name(target_kind: str, trait_id: int, definition_id: int) -> str:
    """Return the POST field name for one trait-choice target."""
    prefix = CHOICE_FIELD_PREFIX_BY_KIND.get(target_kind)
    if not prefix:
        return ""
    return f"{prefix}_trait_{trait_id}_{definition_id}"


def _build_decision_option(
    *,
    option_id: str,
    label: str,
    submit_name: str,
    submit_value: str,
    grade: int | None = None,
    meta: str = "",
    description: str = "",
    badge: str = "",
    facts: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """Return one serialized option for the choice modal payload."""
    return {
        "id": str(option_id),
        "label": label,
        "grade": "" if grade is None else str(int(grade)),
        "meta": meta,
        "badge": badge,
        "facts": facts or [],
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
    grade_filter_options: list[int] | None = None,
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
        "grade_filter_options": grade_filter_options or [],
    }


def _spell_within_current_level(spell: Spell, *, school_levels: dict[int, int], aspect_levels: dict[int, int]) -> bool:
    """Return whether a spell is legal for the character's current learned magic level."""
    if spell.school_id:
        return int(spell.grade) <= int(school_levels.get(spell.school_id, 0))
    if spell.aspect_id:
        return int(spell.grade) <= int(aspect_levels.get(spell.aspect_id, 0))
    return True


def _spell_unit_label(unit_display: str, number: int) -> str:
    plural_map = {
        "Aktion": "Aktionen",
        "Minute": "Minuten",
        "Stunde": "Stunden",
        "Tag": "Tage",
        "Runde": "Runden",
    }
    if number != 1 and unit_display in plural_map:
        return plural_map[unit_display]
    return unit_display


def _spell_cost_facts(spell: Spell) -> str:
    parts = [f"{int(spell.kp_cost)} KP"]
    if spell.ep_cost:
        parts.append(f"oder {int(spell.ep_cost)} EP")
    if spell.extra_cost_type == getattr(Spell.ExtraCostType, "WOUND_GRADE", "") and spell.extra_cost_value:
        amount = int(spell.extra_cost_value)
        parts.append(f"und {amount} {'Wundgrad' if amount == 1 else 'Wundgrade'}")
    return " ".join(parts)


def _spell_cast_time_facts(spell: Spell) -> str:
    parts: list[str] = []
    if spell.cast_time_number is not None and spell.cast_time_unit:
        unit = Spell.CastTimeUnit(spell.cast_time_unit).label
        parts.append(f"{spell.cast_time_number} {_spell_unit_label(unit, int(spell.cast_time_number))}")
    if spell.cast_time2_number is not None and spell.cast_time2_unit:
        unit = Spell.CastTimeUnit(spell.cast_time2_unit).label
        parts.append(f"{spell.cast_time2_number} {_spell_unit_label(unit, int(spell.cast_time2_number))}")
    return " oder ".join(parts) or str(spell.cast_time or "").strip() or "-"


def _spell_range_facts(spell: Spell) -> str:
    if spell.range_number is not None and spell.range_unit:
        unit = Spell.RangeUnit(spell.range_unit).label
        return f"{spell.range_number} {_spell_unit_label(unit, int(spell.range_number))}"
    return str(spell.range_text or "").strip() or "-"


def _spell_duration_facts(spell: Spell) -> str:
    def _part(number, unit_key) -> str:
        if unit_key in ("sofort", "permanent", "Szene", "Konzentration"):
            return Spell.DurationUnit(unit_key).label
        if number is not None and unit_key:
            unit = Spell.DurationUnit(unit_key).label
            return f"{number} {_spell_unit_label(unit, int(number))}"
        return ""

    parts = [part for part in [
        _part(spell.duration_number, spell.duration_unit),
        _part(spell.duration2_number, spell.duration2_unit),
    ] if part]
    return " oder ".join(parts) or str(spell.duration_text or "").strip() or "-"


def _spell_choice_facts(spell: Spell) -> list[dict[str, str]]:
    mw_label = "-" if spell.mw is None else str(int(spell.mw))
    resistance_label = str(spell.resistance_value or "-").strip() or "-"
    return [
        {"label": "Grad", "value": str(int(spell.grade))},
        {"label": "MW/RW", "value": f"{mw_label}/{resistance_label}"},
        {"label": "Kosten", "value": _spell_cost_facts(spell)},
        {"label": "Zeitaufwand", "value": _spell_cast_time_facts(spell)},
        {"label": "Reichweite", "value": _spell_range_facts(spell)},
        {"label": "Wirkungsdauer", "value": _spell_duration_facts(spell)},
    ]


def _spell_grade_filter_options(spells: list[Spell]) -> list[int]:
    return sorted({int(spell.grade) for spell in spells if getattr(spell, "grade", None) is not None})


def _current_school_grade_filter_options(current_level: int) -> list[int]:
    current_level = int(current_level or 0)
    if current_level <= 0:
        return []
    return list(range(1, current_level + 1))


def build_learning_progression_context(character, *, engine) -> dict[str, object]:
    """Build open progression decisions for the learning window."""
    path_groups: OrderedDict[str, list[dict]] = OrderedDict()
    technique_groups: OrderedDict[str, list[dict]] = OrderedDict()
    specialization_groups: OrderedDict[str, list[dict]] = OrderedDict()
    choice_groups: OrderedDict[str, list[dict]] = OrderedDict()
    arcane_free_spell_groups: OrderedDict[str, list[dict]] = OrderedDict()
    bonus_spell_groups: OrderedDict[str, list[dict]] = OrderedDict()
    base_spell_rows: list[dict[str, object]] = []
    divine_entity_rows: list[dict[str, object]] = []
    pending_decisions: list[dict[str, object]] = []
    magic_engine = character.get_magic_engine(refresh=True)
    magic_engine.sync_character_magic()


    learned_school_entries = list(
        character.schools.select_related("school", "school__type").order_by("school__type__name", "school__name")
    )
    learned_school_ids = [entry.school_id for entry in learned_school_entries]
    technique_states = list(engine.technique_states())

    skill_definitions = list(Skill.objects.select_related("category").order_by("category__name", "name"))
    skill_categories = list(SkillCategory.objects.order_by("name"))
    item_definitions = list(Item.objects.order_by("name"))
    weapon_type_definitions = weapon_mastery_weapon_type_definitions()
    item_category_options = [{"value": value, "label": label} for value, label in Item.ItemType.choices]
    rune_definitions = list(Rune.objects.order_by("name"))
    attribute_definitions = list(Attribute.objects.order_by("name"))

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

    binding = magic_engine._divine_binding()
    if binding is None:
        divine_entities = list(
            DivineEntity.objects.filter(school_id__in=[entry.school_id for entry in magic_engine._divine_school_entries()])
            .select_related("school")
            .order_by("school__name", "name")
        )
        if divine_entities:
            row = {
                "field_name": "learn_divine_entity",
                "options": [
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description or "",
                        "school_name": entity.school.name,
                    }
                    for entity in divine_entities
                ],
            }
            divine_entity_rows.append(row)
            pending_decisions.append(
                _build_pending_decision(
                    decision_id="divine-entity",
                    kind="divine_entity",
                    title="Klerikale Entitaet",
                    summary="Waehle die verehrte Entitaet",
                    description="Diese Wahl bestimmt die automatisch gewaehrten Startaspekte.",
                    prompt="Entitaet waehlen",
                    options=[
                        _build_decision_option(
                            option_id=str(option["id"]),
                            label=option["name"],
                            meta=option["school_name"],
                            description=option["description"],
                            submit_name=row["field_name"],
                            submit_value=str(option["id"]),
                        )
                        for option in row["options"]
                    ],
                )
            )

    arcane_school_levels = {
        entry.school_id: int(entry.level)
        for entry in magic_engine._arcane_school_entries()
    }
    aspect_levels = {
        entry.aspect_id: int(entry.level)
        for entry in magic_engine.get_character_aspects()
    }

    for school_entry in magic_engine._arcane_school_entries():
        choice_state = magic_engine.get_available_arcane_spell_choices(school_entry.school)
        options = [
            spell for spell in choice_state["options"]
            if _spell_within_current_level(
                spell,
                school_levels=arcane_school_levels,
                aspect_levels=aspect_levels,
            )
        ]
        if not options:
            continue
        for slot_index in range(int(choice_state["remaining"])):
            row = {
                "field_name": f"learn_arcane_free_spell_{school_entry.school_id}_{slot_index}",
                "school_id": school_entry.school_id,
                "school_name": choice_state["school_name"],
                "school_level": choice_state["school_level"],
                "options": options,
            }
            arcane_free_spell_groups.setdefault(choice_state["school_name"], []).append(row)
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"arcane-free-spell-{school_entry.school_id}-{slot_index}",
                    kind="arcane_free_spell",
                    title=f"Zauber: {choice_state['school_name']}",
                    summary=f"Freier Zauber {slot_index + 1} von {choice_state['remaining']}",
                    description="Waehle einen arkanen Zauber derselben oder niedrigeren Stufe.",
                    prompt="Zauber waehlen",
                    selection_group_id=f"arcane-free-spell:{school_entry.school_id}",
                    grade_filter_options=_current_school_grade_filter_options(choice_state["school_level"]) or _spell_grade_filter_options(options),
                    options=[
                        _build_decision_option(
                            option_id=str(spell.id),
                            label=spell.name,
                            grade=int(spell.grade),
                            meta=f"Grad {spell.grade}",
                            badge=(spell.panel_badge_label or "").strip(),
                            facts=_spell_choice_facts(spell),
                            description=spell.description or "",
                            submit_name=row["field_name"],
                            submit_value=str(spell.id),
                        )
                        for spell in options
                    ],
                )
            )

    for source_row in magic_engine.get_available_bonus_spells():
        source = source_row["source"]
        options = [
            spell for spell in source_row["options"]
            if _spell_within_current_level(
                spell,
                school_levels=arcane_school_levels,
                aspect_levels=aspect_levels,
            )
        ]
        if not options:
            continue
        for slot_index in range(int(source["remaining"])):
            row = {
                "field_name": f"learn_bonus_spell_{source['id']}_{slot_index}",
                "bonus_source_id": source["id"],
                "source_label": source["label"],
                "options": options,
            }
            bonus_spell_groups.setdefault(source["label"], []).append(row)
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"bonus-spell-{source['id']}-{slot_index}",
                    kind="bonus_spell",
                    title=f"Bonuszauber: {source['label']}",
                    summary=f"Freier Bonuszauber {slot_index + 1} von {source['remaining']}",
                    description="Waehle einen legalen Zusatzzauber aus den verfuegbaren Schulen oder Aspekten.",
                    prompt="Bonuszauber waehlen",
                    selection_group_id=f"bonus-spell:{source['id']}",
                    grade_filter_options=_spell_grade_filter_options(options),
                    options=[
                        _build_decision_option(
                            option_id=str(spell.id),
                            label=spell.name,
                            grade=int(spell.grade),
                            meta=f"{spell.school.name if spell.school_id else spell.aspect.name} | Grad {spell.grade}",
                            badge=(spell.panel_badge_label or "").strip(),
                            facts=_spell_choice_facts(spell),
                            description=spell.description or "",
                            submit_name=row["field_name"],
                            submit_value=str(spell.id),
                        )
                        for spell in options
                    ],
                )
            )

    weapon_master_school = engine._weapon_master_school
    for entry in learned_school_entries:
        school = entry.school
        if weapon_master_school is None or school.id != weapon_master_school.id:
            continue

        mastered_entries = list(engine._weapon_mastery_entries_by_type.values())
        required_mastery_count = min(int(entry.level), 10)
        missing_mastery_count = max(0, required_mastery_count - len(mastered_entries))
        used_weapon_types = {mastery.effective_weapon_type() for mastery in mastered_entries}

        for slot_offset in range(missing_mastery_count):
            pick_order = len(mastered_entries) + slot_offset + 1
            weapon_field_name = f"learn_weapon_mastery_weapon_{school.id}_{pick_order}"
            side_field_name = f"learn_weapon_mastery_side_{school.id}_{pick_order}"
            weapon_options = []
            for weapon_type_row in weapon_type_definitions:
                weapon_type = str(weapon_type_row["value"])
                if weapon_type in used_weapon_types:
                    continue
                weapon_options.append(
                    _build_decision_option(
                        option_id=weapon_type,
                        label=str(weapon_type_row["label"]),
                        meta="Waffentyp",
                        description="Waffentyp, den der Waffenmeister meistert.",
                        submit_name=weapon_field_name,
                        submit_value=weapon_type,
                    )
                )
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"weapon-mastery-weapon-{school.id}-{pick_order}",
                    kind="weapon_mastery_weapon",
                    title=f"Waffenmeister: Waffentyp {pick_order}",
                    summary=f"{school.name} | Typwahl {pick_order} von {required_mastery_count}",
                    description="Waehle den Waffentyp fuer diesen Meisterschaftsplatz.",
                    prompt="Waffentyp waehlen",
                    selection_group_id=f"weapon-mastery-weapon:{school.id}",
                    options=weapon_options,
                )
            )
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"weapon-mastery-side-{school.id}-{pick_order}",
                    kind="weapon_mastery_side",
                    title=f"Waffenmeister: Bonusseite {pick_order}",
                    summary=f"{school.name} | Startbonus {pick_order} von {required_mastery_count}",
                    description="Lege fest, ob der erste Punkt dieser Waffe auf Manoever oder Schaden geht.",
                    prompt="Startbonus waehlen",
                    selection_group_id=f"weapon-mastery-side:{school.id}:{pick_order}",
                    options=[
                        _build_decision_option(
                            option_id="maneuver",
                            label="Manoever zuerst",
                            meta="Startbonus",
                            description="Der erste Punkt geht auf den Manoeverbonus.",
                            submit_name=side_field_name,
                            submit_value="maneuver",
                        ),
                        _build_decision_option(
                            option_id="damage",
                            label="Schaden zuerst",
                            meta="Startbonus",
                            description="Der erste Punkt geht auf den Schadensbonus.",
                            submit_name=side_field_name,
                            submit_value="damage",
                        ),
                    ],
                )
            )

        required_arcana_count = min(int(entry.level), 10)
        existing_arcana_entries = list(engine._weapon_mastery_arcana_entries)
        missing_arcana_count = max(0, required_arcana_count - len(existing_arcana_entries))
        used_rune_ids = {
            entry.rune_id
            for entry in existing_arcana_entries
            if getattr(entry, "rune_id", None)
        }
        for slot_offset in range(missing_arcana_count):
            arcana_index = len(existing_arcana_entries) + slot_offset + 1
            field_name = f"learn_weapon_mastery_arcana_{school.id}_{arcana_index}"
            options = [
                _build_decision_option(
                    option_id=f"bonus-{arcana_index}",
                    label="+1/+1 Bonuskapazitaet",
                    meta="Arkane Meisterschaft",
                    description="Erhoeht die beherrschbare magische Bonuskapazitaet um +1/+1.",
                    submit_name=field_name,
                    submit_value="bonus_capacity",
                )
            ]
            for rune in rune_definitions:
                if rune.id in used_rune_ids:
                    continue
                options.append(
                    _build_decision_option(
                        option_id=f"rune-{rune.id}",
                        label=rune.name,
                        meta="Rune",
                        description=rune.description or "",
                        submit_name=field_name,
                        submit_value=f"rune:{rune.id}",
                    )
                )
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"weapon-arcana-{school.id}-{arcana_index}",
                    kind="weapon_mastery_arcana",
                    title=f"Waffenmeister: Arkane Meisterschaft {arcana_index}",
                    summary=f"{school.name} | Arkanum {arcana_index} von {required_arcana_count}",
                    description="Waehle pro Schulstufe entweder eine neue Rune oder +1/+1 Bonuskapazitaet.",
                    prompt="Arkanum waehlen",
                    selection_group_id=f"weapon-arcana:{school.id}",
                    options=options,
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

    # Fulfilled and violated blocks: their remaining available techniques must not appear as
    # standalone single-technique choices, because the block requirement is already satisfied.
    for block_state in list(engine.fulfilled_technique_choice_blocks()) + list(engine.violated_technique_choice_blocks()):
        block_id = int(block_state["block_id"])
        available_states = technique_states_by_block_id.get(block_id, [])
        handled_technique_ids.update(int(state["technique_id"]) for state in available_states)

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
                            group_name=technique.school.name,
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
                        group_name=technique.school.name,
                    )
                    if row is not None:
                        choice_groups.setdefault(technique.school.name, []).append(row)

    race = character.race
    if race is not None:
        active_race_definitions = list(
            race.choice_definitions.filter(is_active=True)
            .select_related("allowed_skill_category")
            .order_by("sort_order", "name", "id")
        )
        for definition in active_race_definitions:
            existing_count = len(engine.race_choices(definition))
            required_count = definition.min_choices if definition.is_required else 0
            missing_count = max(0, required_count - existing_count)
            for missing_index in range(missing_count):
                row = _build_race_choice_row(
                    race=race,
                    target_kind=definition.target_kind,
                    label=definition.name,
                    description=definition.description or "",
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
                    choice_groups.setdefault(race.name, []).append(row)

    trait_entries = list(
        CharacterTrait.objects.filter(owner=character)
        .select_related("trait")
        .prefetch_related("trait__choice_definitions")
        .order_by("trait__trait_type", "trait__name", "id")
    )
    for trait_entry in trait_entries:
        trait = trait_entry.trait
        active_trait_definitions = list(
            trait.choice_definitions.filter(is_active=True).order_by("sort_order", "name", "id")
        )
        for definition in active_trait_definitions:
            if definition.target_kind not in {
                TraitChoiceDefinition.TargetKind.ATTRIBUTE,
                TraitChoiceDefinition.TargetKind.RESOURCE,
            }:
                continue
            existing_count = len(engine._trait_choices_by_definition_id.get(definition.id, []))
            required_count = definition.min_choices if definition.is_required else 0
            missing_count = max(0, required_count - existing_count)
            if definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE:
                options = [
                    {
                        "value": attribute.short_name,
                        "label": attribute.name,
                        "meta": attribute.short_name,
                    }
                    for attribute in attribute_definitions
                    if is_allowed_trait_attribute_choice(trait.slug, attribute.short_name)
                ]
            else:
                resource_options = (
                    [(definition.allowed_resource,
                      dict(RESOURCE_KEY_CHOICES).get(definition.allowed_resource, definition.allowed_resource))]
                    if definition.allowed_resource
                    else list(RESOURCE_KEY_CHOICES)
                )
                options = [
                    {
                        "value": value,
                        "label": label,
                        "meta": "",
                    }
                    for value, label in resource_options
                ]

            for missing_index in range(missing_count):
                choice_groups.setdefault(trait.name, []).append(
                    {
                        "choice_scope": "trait",
                        "trait_id": trait.id,
                        "trait_name": trait.name,
                        "trait_slug": trait.slug,
                        "definition_id": definition.id,
                        "target_kind": definition.target_kind,
                        "target_label": CHOICE_KIND_LABELS.get(definition.target_kind, definition.target_kind),
                        "label": definition.name,
                        "description": definition.description or "",
                        "field_name": trait_choice_field_name(definition.target_kind, trait.id, definition.id),
                        "slot_index": missing_index,
                        "supported": True,
                        "options": options,
                    }
                )

    for row in [row for rows in choice_groups.values() for row in rows]:
        input_type = "text" if row.get("allows_text_input") else "options"
        if not row["supported"]:
            input_type = "unsupported"
        choice_scope = row.get("choice_scope")
        if choice_scope == "race":
            decision_prefix = "race-choice"
            decision_kind = "race_choice"
            decision_title = f"Choice: {row['race_name']}"
            selection_group_id = f"race-choice:{row['definition_id']}"
            decision_key = f"{row['definition_id']}-{row['slot_index']}"
        elif choice_scope == "trait":
            decision_prefix = "trait-choice"
            decision_kind = "trait_choice"
            decision_title = f"Choice: {row['trait_name']}"
            selection_group_id = f"trait-choice:{row['trait_id']}:{row['definition_id']}"
            decision_key = f"{row['trait_id']}-{row['definition_id']}-{row['slot_index']}"
        else:
            decision_prefix = "technique-choice"
            decision_kind = "technique_choice"
            decision_title = f"Choice: {row['technique_name']}"
            if row["target_kind"] == Technique.ChoiceTargetKind.SPECIALIZATION:
                selection_group_id = f"technique-specialization:{row['school_id']}"
            else:
                selection_group_id = f"technique-choice:{row['technique_id']}:{row['definition_id'] or 'legacy'}"
            decision_key = f"{row['technique_id']}-{row['definition_id'] or 'legacy'}-{row['slot_index']}"
        if row.get("allows_text_input"):
            pending_decisions.append(
                _build_pending_decision(
                    decision_id=f"{decision_prefix}-{decision_key}",
                    kind=decision_kind,
                    title=decision_title,
                    summary=f"{row['label']} | {row['target_label']}",
                    description=row["description"],
                    prompt="Eintrag festlegen",
                    input_type=input_type,
                    text_submit_name=row["field_name"],
                    text_placeholder="Eintrag",
                    supported=row["supported"],
                    selection_group_id=selection_group_id,
                )
            )
            continue

        pending_decisions.append(
            _build_pending_decision(
                decision_id=f"{decision_prefix}-{decision_key}",
                kind=decision_kind,
                title=decision_title,
                summary=f"{row['label']} | {row['target_label']}",
                description=(
                    row["description"]
                    or ("Dieser Auswahltyp ist derzeit im Lernmenue noch nicht direkt belegbar." if not row["supported"] else "")
                ),
                prompt="Auswahl treffen",
                input_type=input_type,
                supported=row["supported"],
                selection_group_id=selection_group_id,
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
        "learn_divine_entity_rows": divine_entity_rows,
        "learn_base_spell_rows": base_spell_rows,
        "learn_arcane_free_spell_groups": [{"name": name, "rows": rows} for name, rows in arcane_free_spell_groups.items()],
        "learn_arcane_free_spell_rows": [row for rows in arcane_free_spell_groups.values() for row in rows],
        "learn_bonus_spell_groups": [{"name": name, "rows": rows} for name, rows in bonus_spell_groups.items()],
        "learn_bonus_spell_rows": [row for rows in bonus_spell_groups.values() for row in rows],
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
    group_name: str,
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
            "school_name": group_name,
            "definition_id": definition_id,
            "label": label,
            "description": description,
            "slot_index": slot_index,
            "options": [],
            "choice_scope": "technique",
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
        used_specialization_ids = {
            choice.selected_specialization_id
            for choice in engine.character.technique_choices.filter(selected_specialization__isnull=False)
        }
        used_specialization_ids.update(
            engine.character.learned_specializations.values_list("specialization_id", flat=True)
        )
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
            if specialization.id not in used_specialization_ids
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
        "school_name": group_name,
        "definition_id": definition_id,
        "label": label,
        "description": description,
        "slot_index": slot_index,
        "options": options,
        "allows_text_input": target_kind == Technique.ChoiceTargetKind.TEXT,
        "choice_scope": "technique",
    }


def _build_race_choice_row(
    *,
    race,
    target_kind: str,
    label: str,
    description: str,
    definition_id: int,
    slot_index: int,
    skill_definitions,
    skill_categories,
    item_definitions,
    item_category_options,
    allowed_skill_category_id: int | None,
    allowed_skill_family: str,
) -> dict[str, object] | None:
    """Return one rendered choice row for a still-missing race decision."""
    field_name = race_choice_field_name(target_kind, definition_id)
    if not field_name:
        return {
            "field_name": "",
            "supported": False,
            "target_kind": target_kind,
            "target_label": CHOICE_KIND_LABELS.get(target_kind, target_kind),
            "definition_id": definition_id,
            "label": label,
            "description": description,
            "slot_index": slot_index,
            "options": [],
            "race_id": race.id,
            "race_name": race.name,
            "school_name": race.name,
            "choice_scope": "race",
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
    elif target_kind == Technique.ChoiceTargetKind.TEXT:
        options = []

    return {
        "field_name": field_name,
        "supported": target_kind in {
            Technique.ChoiceTargetKind.SKILL,
            Technique.ChoiceTargetKind.SKILL_CATEGORY,
            Technique.ChoiceTargetKind.ITEM,
            Technique.ChoiceTargetKind.ITEM_CATEGORY,
            Technique.ChoiceTargetKind.TEXT,
        },
        "target_kind": target_kind,
        "target_label": CHOICE_KIND_LABELS.get(target_kind, target_kind),
        "definition_id": definition_id,
        "label": label,
        "description": description,
        "slot_index": slot_index,
        "options": options,
        "allows_text_input": target_kind == Technique.ChoiceTargetKind.TEXT,
        "race_id": race.id,
        "race_name": race.name,
        "school_name": race.name,
        "choice_scope": "race",
    }
