"""Shared lesson requirements, costs, display, and activation rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from django.db import transaction
from django.db.models import Prefetch

from charsheet.models.lessons import (
    CharacterLesson,
    Lesson,
    LessonCost,
    LessonRequirement,
)


class LessonRuleError(Exception):
    """Raised when a lesson rule expression or activation is invalid."""


class LessonCostHandler:
    """Extension point for one automatically managed application-cost type."""

    cost_type = ""

    def display(self, cost: LessonCost) -> str:
        return f"{int(cost.value)} {cost.type_label}"

    def is_available(
        self, character, costs: list[LessonCost], context: dict
    ) -> tuple[bool, str]:
        return True, ""

    def deduct(
        self, character, costs: list[LessonCost], context: dict
    ) -> None:
        return None


class ArcanePowerLessonCostHandler(LessonCostHandler):
    cost_type = LessonCost.CostType.ARCANE_POWER

    def is_available(
        self, character, costs: list[LessonCost], context: dict
    ) -> tuple[bool, str]:
        amount = sum(int(cost.value) for cost in costs)
        label = (
            "Blut intelligenter Wesen"
            if context.get("resource_type") == "blood"
            else "KP"
        )
        return (
            int(context["current_arcane_power"]) >= amount,
            f"Nicht genug {label} für diese Lektion.",
        )

    def deduct(
        self, character, costs: list[LessonCost], context: dict
    ) -> None:
        amount = sum(int(cost.value) for cost in costs)
        context["current_arcane_power"] = (
            int(context["current_arcane_power"]) - amount
        )
        if context.get("resource_type") == "blood":
            character.vampire_intelligent_blood = int(
                context["current_arcane_power"]
            )
        else:
            character.current_arcane_power = int(
                context["current_arcane_power"]
            )


LESSON_COST_HANDLERS: dict[str, LessonCostHandler] = {}


def register_lesson_cost_handler(handler: LessonCostHandler) -> None:
    """Register or replace the automatic handler for one cost type."""
    if not handler.cost_type:
        raise ValueError("Ein Kosten-Handler benötigt eine Kostenart.")
    LESSON_COST_HANDLERS[str(handler.cost_type)] = handler


register_lesson_cost_handler(ArcanePowerLessonCostHandler())


def format_requirement(requirement: LessonRequirement) -> str:
    kind = requirement.requirement_type
    types = LessonRequirement.RequirementType
    if kind == types.SCHOOL_TECHNIQUE:
        return (
            f"{requirement.required_school.name} – "
            f"{requirement.required_technique.name}"
        )
    if kind == types.SCHOOL_SPECIALISATION:
        return (
            f"{requirement.required_school.name} – "
            f"{requirement.specialisation.name}"
        )
    if kind == types.MAGIC_SCHOOL_LEVEL:
        return f"{requirement.magic_school.name} {requirement.minimum_value}"
    if kind == types.CLERICAL_MAGIC_LEVEL:
        return f"Klerikale Magie {requirement.minimum_value}"
    if kind == types.DRUID_CIRCLE_LEVEL:
        return f"{requirement.druid_circle.name} {requirement.minimum_value}"
    if kind == types.SPECIFIC_CREATURE:
        return requirement.creature.name
    return "Ungültige Voraussetzung"


def format_lesson_requirements(lesson: Lesson) -> str:
    return (
        " UND ".join(
            format_requirement(row) for row in lesson.requirements.all()
        )
        or "Keine"
    )


def lesson_queryset():
    """Load definitions and display targets in a fixed number of queries."""
    requirements = LessonRequirement.objects.select_related(
        "required_school__type",
        "required_technique",
        "specialisation",
        "magic_school__type",
        "druid_circle__school",
        "creature",
    )
    return Lesson.objects.prefetch_related(
        "costs",
        Prefetch("requirements", queryset=requirements),
    ).order_by("name", "id")


def format_cost(cost: LessonCost) -> str:
    suffix = f" – {cost.description}" if cost.description.strip() else ""
    handler = LESSON_COST_HANDLERS.get(str(cost.cost_type))
    label = (
        handler.display(cost)
        if handler is not None
        else f"{int(cost.value)} {cost.type_label}"
    )
    return f"{label}{suffix}"


def validate_cost_groups(
    costs: Iterable[LessonCost],
) -> dict[int, list[LessonCost]]:
    grouped: dict[int, list[LessonCost]] = defaultdict(list)
    for cost in costs:
        number = int(cost.cost_group or 0)
        if number < 1:
            raise LessonRuleError("Kostengruppen müssen mindestens 1 sein.")
        grouped[number].append(cost)
    return grouped


def format_lesson_costs(lesson: Lesson) -> str:
    costs = list(lesson.costs.all())
    if not costs:
        return "Keine"
    grouped = validate_cost_groups(costs)
    packages = [
        " UND ".join(format_cost(cost) for cost in grouped[number])
        for number in sorted(grouped)
    ]
    if len(packages) == 1:
        return packages[0]
    return " ODER ".join(f"({package})" for package in packages)


@dataclass
class LessonRequirementContext:
    """Request-local snapshot; rebuild after progression changes."""

    school_levels: Mapping[int, int] = field(default_factory=dict)
    learned_technique_ids: set[int] = field(default_factory=set)
    specialization_ids: set[int] = field(default_factory=set)
    creature_ids: set[int] = field(default_factory=set)
    druid_cult_id: int | None = None
    clerical_level: int = 0

    @classmethod
    def from_state(cls, school_levels, learned_technique_ids):
        from charsheet.models import School
        from charsheet.religion_rules import is_clerical_school

        schools = (
            School.objects.filter(pk__in=school_levels)
            .select_related("type")
            .prefetch_related(
                "druid_cults",
                "shaman_patrons",
            )
        )
        return cls(
            school_levels=school_levels,
            learned_technique_ids=learned_technique_ids,
            clerical_level=max(
                (
                    school_levels[school.pk]
                    for school in schools
                    if is_clerical_school(school)
                ),
                default=0,
            ),
        )

    @classmethod
    def from_character(cls, character, *, engine=None):
        levels = dict(character.schools.values_list("school_id", "level"))
        engine = engine or character.get_engine(refresh=True)
        context = cls.from_state(
            levels,
            {
                row["technique_id"]
                for row in engine.technique_states()
                if row["learned"]
            },
        )
        context.specialization_ids = set(
            character.learned_specializations.values_list(
                "specialization_id", flat=True
            )
        )
        context.creature_ids = set(
            character.creatures.exclude(creature_id=None).values_list(
                "creature_id", flat=True
            )
        )
        from charsheet.models import CharacterDruidCult

        context.druid_cult_id = (
            CharacterDruidCult.objects.filter(character=character)
            .values_list(
                "cult_id",
                flat=True,
            )
            .first()
        )
        return context


def _requirement_context(
    character=None,
    context=None,
    engine=None,
    school_levels=None,
    learned_technique_ids=None,
):
    if context is not None:
        return context
    if character is not None:
        return LessonRequirementContext.from_character(
            character, engine=engine
        )
    return LessonRequirementContext.from_state(
        school_levels or {}, learned_technique_ids or set()
    )


def requirement_met(
    requirement: LessonRequirement,
    *,
    character=None,
    context=None,
    engine=None,
    school_levels=None,
    learned_technique_ids=None,
) -> bool:
    state = _requirement_context(
        character,
        context,
        engine,
        school_levels,
        learned_technique_ids,
    )
    kind = requirement.requirement_type
    types = LessonRequirement.RequirementType
    if kind == types.SCHOOL_TECHNIQUE:
        return (
            state.school_levels.get(requirement.required_school_id, 0) > 0
            and requirement.required_technique.school_id
            == requirement.required_school_id
            and requirement.required_technique_id
            in state.learned_technique_ids
        )
    if kind == types.SCHOOL_SPECIALISATION:
        return (
            state.school_levels.get(requirement.required_school_id, 0) > 0
            and requirement.specialisation.school_id
            == requirement.required_school_id
            and requirement.specialisation_id in state.specialization_ids
        )
    if kind == types.MAGIC_SCHOOL_LEVEL:
        return (
            state.school_levels.get(requirement.magic_school_id, 0)
            >= requirement.minimum_value
        )
    if kind == types.CLERICAL_MAGIC_LEVEL:
        return state.clerical_level >= requirement.minimum_value
    if kind == types.DRUID_CIRCLE_LEVEL:
        return (
            state.druid_cult_id == requirement.druid_circle_id
            and state.school_levels.get(requirement.druid_circle.school_id, 0)
            >= requirement.minimum_value
        )
    if kind == types.SPECIFIC_CREATURE:
        return requirement.creature_id in state.creature_ids
    return False


def lesson_requirements_met(
    lesson: Lesson,
    *,
    character=None,
    context=None,
    engine=None,
    school_levels=None,
    learned_technique_ids=None,
) -> bool:
    state = _requirement_context(
        character,
        context,
        engine,
        school_levels,
        learned_technique_ids,
    )
    return all(
        requirement_met(row, context=state)
        for row in lesson.requirements.all()
    )


def missing_requirement_labels(lesson: Lesson, **state) -> list[str]:
    context = _requirement_context(**state)
    return [
        format_requirement(row)
        for row in lesson.requirements.all()
        if not requirement_met(row, context=context)
    ]


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
    selected_cost_group: int | None = None,
) -> tuple[list[LessonCost], list[LessonCost]]:
    costs = list(lesson.costs.all())
    grouped = validate_cost_groups(costs)
    if not grouped:
        if selected_cost_group is not None:
            raise LessonRuleError("Diese Lektion besitzt keine Kostengruppe.")
        selected = []
    elif len(grouped) == 1:
        only_group = next(iter(grouped))
        if selected_cost_group not in {None, only_group}:
            raise LessonRuleError("Ungültige Kostengruppe.")
        selected = grouped[only_group]
    else:
        if selected_cost_group not in grouped:
            raise LessonRuleError(
                "Es muss genau eine Kostengruppe gewählt werden."
            )
        selected = grouped[selected_cost_group]
    automatic = [
        cost
        for cost in selected
        if str(cost.cost_type) in LESSON_COST_HANDLERS
    ]
    manual = [
        cost
        for cost in selected
        if str(cost.cost_type) not in LESSON_COST_HANDLERS
    ]
    return automatic, manual


@transaction.atomic
def activate_lesson(
    character,
    lesson_id: int,
    selected_cost_group: int | None = None,
    *,
    manual_costs_confirmed: bool = False,
) -> dict:
    character = (
        type(character).objects.select_for_update().get(pk=character.pk)
    )
    entry = (
        CharacterLesson.objects.select_related("lesson")
        .filter(character=character, lesson_id=lesson_id)
        .first()
    )
    if entry is None:
        return {
            "ok": False,
            "error": "unknown_lesson",
            "message": "Diese Lektion wurde nicht erlernt.",
        }
    try:
        automatic, manual = resolve_activation_costs(
            entry.lesson, selected_cost_group
        )
    except LessonRuleError as exc:
        return {
            "ok": False,
            "error": "invalid_cost_selection",
            "message": str(exc),
        }
    if manual and not manual_costs_confirmed:
        return {
            "ok": False,
            "error": "manual_confirmation_required",
            "message": (
                "Manuelle Kosten müssen vor der Aktivierung bestätigt werden."
            ),
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
            "message": (
                "Die KP-Kosten überschreiten das verbleibende "
                "Potential dieser Runde."
            ),
            "potential_check": potential_check,
        }
    engine = character.get_engine(refresh=True)
    from charsheet.engine.vampire_engine import VampireRules

    vampire_rules = VampireRules(character)
    if vampire_rules.is_vampire():
        blood = vampire_rules.resource_state()
        current_max = blood.maximum
        current = blood.intelligent
        resource_type = "blood"
        if kp_cost > blood.potential:
            return {
                "ok": False,
                "error": "potential_exceeded",
                "message": (
                    "Die Blutkosten überschreiten das Potential "
                    "dieser Handlung."
                ),
            }
    else:
        current_max = max(0, int(engine.calculate_arcane_power()))
        current = (
            current_max
            if character.current_arcane_power is None
            else max(0, int(character.current_arcane_power))
        )
        resource_type = "arcane_power"
    if current < kp_cost:
        return {
            "ok": False,
            "error": "not_enough_kp",
            "message": "Nicht genug KP für diese Lektion.",
        }
    handler_context = {
        "engine": engine,
        "current_arcane_power": current,
        "current_arcane_power_max": current_max,
        "resource_type": resource_type,
    }
    for cost_type, costs in automatic_by_type.items():
        handler = LESSON_COST_HANDLERS[cost_type]
        available, message = handler.is_available(
            character, costs, handler_context
        )
        if not available:
            error = (
                "not_enough_kp"
                if cost_type == LessonCost.CostType.ARCANE_POWER
                else "cost_unavailable"
            )
            return {
                "ok": False,
                "error": error,
                "message": message or "Kosten nicht verfügbar.",
            }
    for cost_type, costs in automatic_by_type.items():
        LESSON_COST_HANDLERS[cost_type].deduct(
            character, costs, handler_context
        )
    if LessonCost.CostType.ARCANE_POWER in automatic_by_type:
        update_field = (
            "vampire_intelligent_blood"
            if resource_type == "blood"
            else "current_arcane_power"
        )
        character.save(update_fields=[update_field])
    return {
        "ok": True,
        "lesson_id": int(entry.lesson_id),
        "lesson_name": entry.lesson.name,
        "spent_kp": kp_cost,
        "current_arcane_power": int(handler_context["current_arcane_power"]),
        "current_arcane_power_max": current_max,
        "resource_type": resource_type,
        "automatic_costs": [format_cost(cost) for cost in automatic],
        "manual_costs": [format_cost(cost) for cost in manual],
        "cost_summary": format_lesson_costs(entry.lesson),
        "potential_check": potential_check,
    }
