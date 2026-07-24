"""Shared lesson requirements, costs, display, and activation rules."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from django.db import transaction

from charsheet.models.lessons import (
    CharacterLesson,
    Lesson,
    LessonCost,
    LessonRequirement,
    LessonRequirementGroup,
)


class LessonRuleError(Exception):
    """Raised when a lesson rule expression or activation is invalid."""


class LessonCostHandler:
    """Extension point for one automatically managed application-cost type."""

    cost_type = ""

    def display(self, cost: LessonCost) -> str:
        return f"{int(cost.value)} {cost.type_label}"

    def is_available(self, character, costs: list[LessonCost], context: dict) -> tuple[bool, str]:
        return True, ""

    def deduct(self, character, costs: list[LessonCost], context: dict) -> None:
        return None


class ArcanePowerLessonCostHandler(LessonCostHandler):
    cost_type = LessonCost.CostType.ARCANE_POWER

    def is_available(self, character, costs: list[LessonCost], context: dict) -> tuple[bool, str]:
        amount = sum(int(cost.value) for cost in costs)
        return int(context["current_arcane_power"]) >= amount, "Nicht genug KP für diese Lektion."

    def deduct(self, character, costs: list[LessonCost], context: dict) -> None:
        amount = sum(int(cost.value) for cost in costs)
        context["current_arcane_power"] = int(context["current_arcane_power"]) - amount
        character.current_arcane_power = int(context["current_arcane_power"])


LESSON_COST_HANDLERS: dict[str, LessonCostHandler] = {}


def register_lesson_cost_handler(handler: LessonCostHandler) -> None:
    """Register or replace the automatic handler for one cost type."""
    if not handler.cost_type:
        raise ValueError("Ein Kosten-Handler benötigt eine Kostenart.")
    LESSON_COST_HANDLERS[str(handler.cost_type)] = handler


register_lesson_cost_handler(ArcanePowerLessonCostHandler())


def format_requirement(requirement: LessonRequirement) -> str:
    kind = requirement.requirement_type
    if kind == LessonRequirement.RequirementType.SCHOOL and requirement.required_school_id:
        return f"{requirement.required_school.name} {int(requirement.minimum_value or 0)}"
    if kind == LessonRequirement.RequirementType.SKILL and requirement.required_skill_id:
        return f"{requirement.required_skill.name} {int(requirement.minimum_value or 0)}"
    if kind == LessonRequirement.RequirementType.TECHNIQUE and requirement.required_technique_id:
        return requirement.required_technique.name
    if kind == LessonRequirement.RequirementType.LESSON and requirement.required_lesson_id:
        return requirement.required_lesson.name
    return "Ungültige Voraussetzung"


def _join_expression(parts: list[str], operator: str) -> str:
    label = " UND " if operator == LessonRequirementGroup.Operator.AND else " ODER "
    return label.join(part for part in parts if part)


def _to_roman(value: int | None) -> str:
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


def format_lesson_requirements(lesson: Lesson) -> str:
    if lesson.technique_id:
        level_label = _to_roman(lesson.technique.level)
        school_label = f"{lesson.school.name} {level_label}".strip()
        return f"{school_label} - {lesson.technique.name}"
    return "Keine Technik zugeordnet"


def format_cost(cost: LessonCost) -> str:
    suffix = f" – {cost.description}" if cost.description.strip() else ""
    handler = LESSON_COST_HANDLERS.get(str(cost.cost_type))
    label = handler.display(cost) if handler is not None else f"{int(cost.value)} {cost.type_label}"
    return f"{label}{suffix}"


def validate_cost_groups(costs: Iterable[LessonCost]) -> dict[int, list[LessonCost]]:
    grouped: dict[int, list[LessonCost]] = defaultdict(list)
    for cost in costs:
        if cost.operator == LessonCost.Operator.OR:
            if cost.alternative_group is None:
                raise LessonRuleError("ODER-Kosten benoetigen eine ODER-Gruppe.")
            grouped[int(cost.alternative_group)].append(cost)
        elif cost.alternative_group is not None:
            raise LessonRuleError("UND-Kosten verwenden keine ODER-Gruppe.")
    invalid = [number for number, rows in grouped.items() if len(rows) < 2]
    if invalid:
        labels = ", ".join(str(number) for number in sorted(invalid))
        raise LessonRuleError(f"Alternativgruppen benötigen mindestens zwei Einträge: {labels}.")
    return grouped


def format_lesson_costs(lesson: Lesson) -> str:
    costs = list(lesson.costs.all())
    if not costs:
        return "Keine"
    grouped = validate_cost_groups(costs)
    parts = [format_cost(cost) for cost in costs if cost.operator == LessonCost.Operator.AND]
    for number in sorted(grouped):
        parts.append(f"({' ODER '.join(format_cost(cost) for cost in grouped[number])})")
    return " + ".join(parts)


def _character_school_levels(character) -> dict[int, int]:
    return {
        int(school_id): int(level)
        for school_id, level in character.schools.values_list("school_id", "level")
    }


def _character_skill_levels(character) -> dict[int, int]:
    levels: dict[int, int] = {}
    for skill_id, level in character.characterskill_set.values_list("skill_id", "level"):
        levels[int(skill_id)] = max(levels.get(int(skill_id), 0), int(level))
    return levels


def requirement_met(
    requirement: LessonRequirement,
    *,
    character=None,
    learned_lesson_ids: set[int] | None = None,
    school_levels: Mapping[int, int] | None = None,
    skill_levels: Mapping[int, int] | None = None,
    learned_technique_ids: set[int] | None = None,
    engine=None,
) -> bool:
    if character is not None:
        if school_levels is None:
            school_levels = _character_school_levels(character)
        if skill_levels is None:
            skill_levels = _character_skill_levels(character)
        if learned_lesson_ids is None:
            learned_lesson_ids = set(character.learned_lessons.values_list("lesson_id", flat=True))
        engine = engine or character.get_engine(refresh=True)
    if school_levels is None:
        school_levels = {}
    if skill_levels is None:
        skill_levels = {}
    if learned_lesson_ids is None:
        learned_lesson_ids = set()
    kind = requirement.requirement_type
    if kind == LessonRequirement.RequirementType.SCHOOL:
        return int(school_levels.get(int(requirement.required_school_id or 0), 0)) >= int(
            requirement.minimum_value or 0
        )
    if kind == LessonRequirement.RequirementType.SKILL:
        return int(skill_levels.get(int(requirement.required_skill_id or 0), 0)) >= int(
            requirement.minimum_value or 0
        )
    if kind == LessonRequirement.RequirementType.TECHNIQUE:
        if learned_technique_ids is not None:
            return int(requirement.required_technique_id or 0) in learned_technique_ids
        return bool(engine and engine.has_technique_learned(requirement.required_technique_id))
    if kind == LessonRequirement.RequirementType.LESSON:
        return int(requirement.required_lesson_id or 0) in learned_lesson_ids
    return False


def lesson_requirements_met(
    lesson: Lesson,
    *,
    character=None,
    learned_lesson_ids: set[int] | None = None,
    school_levels: Mapping[int, int] | None = None,
    skill_levels: Mapping[int, int] | None = None,
    learned_technique_ids: set[int] | None = None,
    engine=None,
) -> bool:
    if not lesson.technique_id:
        return False
    if character is not None:
        engine = engine or character.get_engine(refresh=True)
    if learned_technique_ids is not None:
        return int(lesson.technique_id) in learned_technique_ids
    return bool(engine and engine.has_technique_learned(lesson.technique_id))


def missing_requirement_labels(lesson: Lesson, **state) -> list[str]:
    """Return readable failing clauses without flattening OR groups incorrectly."""
    return [] if lesson_requirements_met(lesson, **state) else [format_lesson_requirements(lesson)]


def potential_budget_guard(character, kp_cost: int) -> dict[str, object]:
    """Future extension hook: no per-round KP ledger exists yet."""
    return {
        "supported": False,
        "allowed": True,
        "required_kp": max(0, int(kp_cost)),
        "remaining_potential": None,
    }


def resolve_activation_costs(
    lesson: Lesson,
    selected_cost_ids: Mapping[int, int] | None = None,
) -> tuple[list[LessonCost], list[LessonCost]]:
    costs = list(lesson.costs.all())
    grouped = validate_cost_groups(costs)
    selected_cost_ids = {int(key): int(value) for key, value in (selected_cost_ids or {}).items()}
    if set(selected_cost_ids) != set(grouped):
        raise LessonRuleError("Für jede Alternativgruppe muss genau eine Kostenoption gewählt werden.")
    selected = [cost for cost in costs if cost.operator == LessonCost.Operator.AND]
    for number, options in grouped.items():
        selected_id = selected_cost_ids[number]
        option = next((cost for cost in options if int(cost.id) == selected_id), None)
        if option is None:
            raise LessonRuleError(f"Ungültige Auswahl für Alternativgruppe {number}.")
        selected.append(option)
    automatic = [cost for cost in selected if str(cost.cost_type) in LESSON_COST_HANDLERS]
    manual = [cost for cost in selected if str(cost.cost_type) not in LESSON_COST_HANDLERS]
    return automatic, manual


@transaction.atomic
def activate_lesson(
    character,
    lesson_id: int,
    selected_cost_ids: Mapping[int, int] | None = None,
    *,
    manual_costs_confirmed: bool = False,
) -> dict:
    character = type(character).objects.select_for_update().get(pk=character.pk)
    entry = (
        CharacterLesson.objects.select_related("lesson")
        .filter(character=character, lesson_id=lesson_id)
        .first()
    )
    if entry is None:
        return {"ok": False, "error": "unknown_lesson", "message": "Diese Lektion wurde nicht erlernt."}
    learned_ids = set(character.learned_lessons.values_list("lesson_id", flat=True))
    if not lesson_requirements_met(entry.lesson, character=character, learned_lesson_ids=learned_ids):
        return {
            "ok": False,
            "error": "requirements_not_met",
            "message": "Die Voraussetzungen dieser Lektion sind nicht mehr erfüllt.",
        }
    try:
        automatic, manual = resolve_activation_costs(entry.lesson, selected_cost_ids)
    except LessonRuleError as exc:
        return {"ok": False, "error": "invalid_cost_selection", "message": str(exc)}
    if manual and not manual_costs_confirmed:
        return {
            "ok": False,
            "error": "manual_confirmation_required",
            "message": "Manuelle Kosten müssen vor der Aktivierung bestätigt werden.",
            "manual_costs": [format_cost(cost) for cost in manual],
        }
    automatic_by_type: dict[str, list[LessonCost]] = defaultdict(list)
    for cost in automatic:
        automatic_by_type[str(cost.cost_type)].append(cost)
    kp_cost = sum(
        int(cost.value)
        for cost in automatic_by_type.get(LessonCost.CostType.ARCANE_POWER, [])
    )
    potential_check = potential_budget_guard(character, kp_cost)
    if potential_check.get("supported") and not potential_check.get("allowed"):
        return {
            "ok": False,
            "error": "potential_exceeded",
            "message": "Die KP-Kosten überschreiten das verbleibende Potential dieser Runde.",
            "potential_check": potential_check,
        }
    engine = character.get_engine(refresh=True)
    current_max = max(0, int(engine.calculate_arcane_power()))
    current = current_max if character.current_arcane_power is None else max(0, int(character.current_arcane_power))
    if current < kp_cost:
        return {"ok": False, "error": "not_enough_kp", "message": "Nicht genug KP für diese Lektion."}
    handler_context = {
        "engine": engine,
        "current_arcane_power": current,
        "current_arcane_power_max": current_max,
    }
    for cost_type, costs in automatic_by_type.items():
        handler = LESSON_COST_HANDLERS[cost_type]
        available, message = handler.is_available(character, costs, handler_context)
        if not available:
            error = "not_enough_kp" if cost_type == LessonCost.CostType.ARCANE_POWER else "cost_unavailable"
            return {"ok": False, "error": error, "message": message or "Kosten nicht verfügbar."}
    for cost_type, costs in automatic_by_type.items():
        LESSON_COST_HANDLERS[cost_type].deduct(character, costs, handler_context)
    if LessonCost.CostType.ARCANE_POWER in automatic_by_type:
        character.save(update_fields=["current_arcane_power"])
    return {
        "ok": True,
        "lesson_id": int(entry.lesson_id),
        "lesson_name": entry.lesson.name,
        "spent_kp": kp_cost,
        "current_arcane_power": int(handler_context["current_arcane_power"]),
        "current_arcane_power_max": current_max,
        "automatic_costs": [format_cost(cost) for cost in automatic],
        "manual_costs": [format_cost(cost) for cost in manual],
        "cost_summary": format_lesson_costs(entry.lesson),
        "potential_check": potential_check,
    }
