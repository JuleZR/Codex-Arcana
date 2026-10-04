"""Data-driven additional school careers and their paid progression."""

from copy import copy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    CareerPathTechnique,
    Character,
    CharacterCareerPathPurchase,
    CharacterSchoolPath,
    CharacterTechnique,
    SchoolPath,
    Technique,
)


def synchronize_career_paths(school_ids):
    """Infer additional careers from current and future school paths."""
    for path in SchoolPath.objects.filter(
        school_id__in=school_ids,
        school__type__slug__in=["combat", "school_combat"],
    ):
        techniques = list(
            path.techniques.filter(
                level__gte=1,
                level__lte=10,
            ).order_by("level", "id")
        )
        if not techniques:
            continue
        _synchronize_steps(path, techniques)
        if not path.additional_progression:
            path.additional_progression = True
            path.completion_purchase = techniques[-1].level < 10
            path.save(
                update_fields=["additional_progression", "completion_purchase"]
            )
    # A choice group spanning levels can describe a selectable career.
    groups = {}
    for technique in Technique.objects.filter(
        school_id__in=school_ids,
        school__type__slug__in=["combat", "school_combat"],
        path__isnull=True,
        is_choice_placeholder=False,
        level__gte=1,
        level__lte=10,
        acquisition_type=Technique.AcquisitionType.CHOICE,
    ):
        if technique.choice_group:
            groups.setdefault(
                (technique.school_id, technique.choice_group), []
            ).append(technique)
    for (school_id, group), techniques in groups.items():
        if len({technique.level for technique in techniques}) < 2:
            continue
        if len({technique.level for technique in techniques}) != len(
            techniques
        ):
            continue
        path, _ = SchoolPath.objects.get_or_create(
            school_id=school_id,
            name=group,
            defaults={
                "additional_progression": True,
                "additional_only": True,
                "completion_purchase": max(
                    technique.level for technique in techniques
                )
                < 10,
            },
        )
        _synchronize_steps(
            path, sorted(techniques, key=lambda row: (row.level, row.pk))
        )


@transaction.atomic
def _synchronize_steps(path, techniques):
    SchoolPath.objects.select_for_update().get(pk=path.pk)
    steps = {step.technique_id: step for step in path.career_steps.all()}
    expected = [
        (technique.pk, order, technique.level)
        for order, technique in enumerate(techniques, 1)
    ]
    if all(
        technique_id in steps
        and steps[technique_id].order == order
        and steps[technique_id].effective_level == level
        for technique_id, order, level in expected
    ):
        return
    # Leave room to insert newly imported earlier techniques.
    offset = max((step.order for step in steps.values()), default=0) + len(
        techniques
    )
    for index, step in enumerate(steps.values(), 1):
        step.order = offset + index
        step.save(update_fields=["order"])
    for technique_id, order, level in expected:
        CareerPathTechnique.objects.update_or_create(
            technique_id=technique_id,
            defaults={
                "path": path,
                "order": order,
                "effective_level": level,
            },
        )


def effective_level(character, path):
    selected = CharacterSchoolPath.objects.filter(
        character=character, path=path
    ).exists()
    if selected:
        entry = character.schools.filter(school_id=path.school_id).first()
        return int(entry.level) if entry else 0
    purchases = character.career_path_purchases.filter(
        path=path
    ).select_related("step")
    purchased_level = max(
        (row.step.effective_level if row.step_id else 10 for row in purchases),
        default=0,
    )
    learned_levels = path.career_steps.filter(
        technique__path__isnull=True,
        technique__character_techniques__character=character,
    ).values_list("effective_level", flat=True)
    return max(purchased_level, max(learned_levels, default=0))


def arcane_power_bonus(character):
    return (
        character.career_path_purchases.aggregate(
            total=Sum("arcane_power_increase")
        )["total"]
        or 0
    )


def next_purchase(character, path, *, engine=None):
    """Expose the next legal step with all existing prerequisites."""
    engine = engine or character.get_engine(refresh=True)
    synchronize_career_paths([path.school_id])
    path.refresh_from_db()
    if (
        not path.additional_progression
        or engine.school_level(path.school_id) < path.required_school_level
    ):
        return None
    selected = engine.selected_school_path(path.school_id)
    if selected and selected.pk == path.pk:
        return None
    steps = list(
        path.career_steps.select_related("technique").order_by("order")
    )
    if not steps:
        return None
    bought = set(
        character.career_path_purchases.filter(path=path).values_list(
            "step_id", flat=True
        )
    )
    for step in steps:
        if step.pk in bought:
            continue
        technique = step.technique
        # Do not silently purchase an already owned selectable ability again.
        if engine.has_technique_learned(technique):
            continue
        if not engine._requirements_met(
            technique, set(), set(), selected_path=path
        ):
            return None
        if engine._is_excluded_by_learned_techniques(technique, set(), set()):
            return None
        return step
    if (
        path.completion_purchase
        and steps[-1].effective_level < 10
        and None not in bought
    ):
        return "completion"
    return None


def available_purchases(character, *, engine=None, include_planned=False):
    engine = engine or character.get_engine(refresh=True)
    synchronize_career_paths(engine._school_entries)
    rows = []
    for path in SchoolPath.objects.filter(
        additional_progression=True,
        school_id__in=engine._school_entries,
    ).select_related("school"):
        step = next_purchase(character, path, engine=engine)
        if step is None:
            continue
        offered_steps = [step]
        if include_planned and step != "completion":
            simulation = copy(engine)
            simulation._manual_learned_technique_ids = set(
                engine._manual_learned_technique_ids
            )
            simulation._purchased_career_technique_ids = set(
                engine._purchased_career_technique_ids
            )
            for candidate in (
                path.career_steps.select_related("technique")
                .filter(
                    order__gte=step.order,
                )
                .order_by("order")
            ):
                for cache in (
                    "_technique_learned_cache",
                    "_technique_available_cache",
                    "_technique_requirement_cache",
                    "_technique_exclusion_cache",
                ):
                    setattr(simulation, cache, {})
                if simulation.has_technique_learned(candidate.technique):
                    continue
                if not simulation._requirements_met(
                    candidate.technique,
                    set(),
                    set(),
                    selected_path=path,
                ) or simulation._is_excluded_by_learned_techniques(
                    candidate.technique,
                    set(),
                    set(),
                ):
                    break
                if candidate.pk != step.pk:
                    offered_steps.append(candidate)
                simulation._manual_learned_technique_ids.add(
                    candidate.technique_id
                )
                simulation._purchased_career_technique_ids.add(
                    candidate.technique_id
                )
            else:
                final_step = path.career_steps.order_by("-order").first()
                if (
                    path.completion_purchase
                    and final_step.effective_level < 10
                    and not character.career_path_purchases.filter(
                        path=path,
                        step__isnull=True,
                    ).exists()
                ):
                    offered_steps.append("completion")
        previous_field_name = ""
        for step in offered_steps:
            completion = step == "completion"
            field_name = (
                f"learn_career_path_{path.pk}_"
                f"{'completion' if completion else step.pk}"
            )
            rows.append(
                {
                    "path_id": path.pk,
                    "path_name": path.name,
                    "school_name": path.school.name,
                    "effective_level": effective_level(character, path),
                    "target_level": 10 if completion else step.effective_level,
                    "technique_name": (
                        "Laufbahn abschließen"
                        if completion
                        else step.technique.name
                    ),
                    "step_id": None if completion else step.pk,
                    "ep_cost": path.ep_cost,
                    "arcane_power_increase": path.arcane_power_increase,
                    "field_name": field_name,
                    "previous_field_name": previous_field_name,
                    "value": "completion" if completion else str(step.pk),
                }
            )
            previous_field_name = field_name
    return rows


@transaction.atomic
def purchase(character, path_id, value):
    """Lock and validate purchases so submissions cannot skip steps."""
    locked = Character.objects.select_for_update().get(pk=character.pk)
    path = SchoolPath.objects.get(pk=path_id)
    step = next_purchase(locked, path)
    expected = (
        "completion"
        if step == "completion"
        else str(step.pk) if step else None
    )
    if value != expected or expected is None:
        raise ValidationError(
            "Ungültiger Laufbahnfortschritt oder fehlende Voraussetzungen."
        )
    if not locked.is_npc and locked.current_experience < path.ep_cost:
        raise ValidationError("Nicht genug aktuelle EP für diese Laufbahn.")
    if step != "completion":
        # Persist the technique while retaining normal technique choices.
        CharacterTechnique.objects.create(
            character=locked,
            technique=step.technique,
            learned_at=timezone.now(),
        )
    CharacterCareerPathPurchase.objects.create(
        character=locked,
        path=path,
        step=None if step == "completion" else step,
        paid_ep=path.ep_cost,
        arcane_power_increase=path.arcane_power_increase,
    )
    if not locked.is_npc:
        locked.current_experience -= path.ep_cost
    locked.used_experience += path.ep_cost
    locked.save(update_fields=["current_experience", "used_experience"])
    character.current_experience = locked.current_experience
    character.used_experience = locked.used_experience
    return path.ep_cost
