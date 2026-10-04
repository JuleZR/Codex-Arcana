"""Paid school selections using existing progression and ownership models."""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.utils import timezone

from charsheet.constants import SCHOOL_COMBAT
from charsheet.models import (
    CharacterSpecialization,
    CreatureSourceBinding,
    Lesson,
    ProgressionRule,
    Specialization,
    Technique,
)

GRANT_KIND = "advanced_simple"
PURCHASE_PREFIX = "advanced_simple:"


def purchase_data(entry):
    """Read paid costs and unlock conditions from existing ownership notes."""
    if not entry.notes.startswith(PURCHASE_PREFIX):
        return None
    try:
        payload = entry.notes.removeprefix(PURCHASE_PREFIX)
        data = json.loads(payload)
        if not isinstance(data, dict):
            return None
        for key in ("paid_ep", "required_level", "arcane_power"):
            if type(data.get(key)) is not int or data[key] < 0:
                return None
        return data
    except (ValueError, TypeError):
        return None


def purchases(character):
    """Return paid selections, independent of later configuration changes."""
    return [
        (entry, data)
        for entry in character.learned_specializations.select_related(
            "specialization", "specialization__school"
        )
        .filter(notes__startswith=PURCHASE_PREFIX)
        .order_by("learned_at", "id")
        if (data := purchase_data(entry)) is not None
    ]


def arcane_power_bonus(character):
    return sum(data["arcane_power"] for entry, data in purchases(character))


def configured_options(character):
    """Resolve opt-in school selections; no school-name logic in the engine."""
    engine = character.get_engine(refresh=True)
    school_entries = {
        entry.school_id: entry
        for entry in character.schools.select_related("school", "school__type")
    }
    owned_ids = set(
        character.learned_specializations.values_list(
            "specialization_id", flat=True
        )
    )
    owned_ids.update(
        character.technique_choices.filter(
            selected_specialization__isnull=False
        ).values_list("selected_specialization_id", flat=True)
    )
    owned_abilities = {
        (school_id, name.strip().casefold())
        for school_id, name in Specialization.objects.filter(
            pk__in=owned_ids
        ).values_list("school_id", "name")
    }
    options = {}
    for rule in ProgressionRule.objects.filter(grant_kind=GRANT_KIND):
        params = rule.params
        if not isinstance(params, dict):
            continue
        school_entry = school_entries.get(params.get("school_id"))
        if (
            school_entry is None
            or school_entry.school.type_id != rule.school_type_id
        ):
            continue
        school = school_entry.school
        if school.type.slug not in {SCHOOL_COMBAT, "school_combat"}:
            continue
        # Weaponsmaster grants belong to the independent progression flow.
        if school.name.casefold() in {"waffenmeister", "weaponsmaster"}:
            continue
        if school_entry.level < rule.min_level:
            continue
        path_id = params.get("path_id")
        selected_path = engine.selected_school_path(school)
        if path_id and (selected_path is None or selected_path.pk != path_id):
            continue
        for selection in params.get("options", []):
            if not isinstance(selection, dict):
                continue
            specialization = Specialization.objects.filter(
                pk=selection.get("specialization_id"),
                school=school,
                is_active=True,
            ).first()
            if specialization is None:
                continue
            technique_id = selection.get("source_technique_id")
            technique = (
                Technique.objects.filter(
                    pk=technique_id, school=school
                ).first()
                if technique_id
                else None
            )
            if technique_id and technique is None:
                continue
            available = not (
                not specialization.allow_multiple
                and (school.pk, specialization.name.strip().casefold())
                in owned_abilities
            )
            if technique is not None:
                available &= bool(
                    engine.technique_state(technique)["available"]
                )
            required_ids = selection.get("required_specialization_ids", [])
            available &= set(required_ids).issubset(owned_ids)
            requirement_lesson_id = selection.get("requirement_lesson_id")
            if requirement_lesson_id:
                lesson = Lesson.objects.filter(
                    pk=requirement_lesson_id
                ).first()
                available &= bool(
                    lesson and lesson.requirements_satisfied_by(character)
                )
            binding_id = selection.get("creature_source_binding_id")
            binding = None
            if binding_id:
                binding = CreatureSourceBinding.objects.filter(
                    pk=binding_id,
                    active=True,
                    technique_trigger__school=school,
                    selection_mode="character_choice",
                ).first()
                if binding is None:
                    continue
                binding_state = engine.technique_state(
                    binding.technique_trigger
                )
                available &= bool(
                    binding_state["available"] and binding_state["learned"]
                )
            cost = selection.get("ep_cost", params.get("ep_cost", 20))
            power = selection.get(
                "arcane_power", params.get("arcane_power", 1)
            )
            if type(cost) is not int or cost < 1:
                continue
            if type(power) is not int or power < 0:
                continue
            key = f"{rule.pk}_{specialization.pk}"
            options[key] = {
                "key": key,
                "specialization": specialization,
                "school_name": school.name,
                "name": specialization.name,
                "description": specialization.description,
                "cost": cost,
                "arcane_power": power,
                "available": available,
                "repeatable": specialization.allow_multiple,
                "source_technique": technique,
                "snapshot": {
                    "paid_ep": cost,
                    "arcane_power": power,
                    "required_level": int(rule.min_level),
                    "path_id": path_id,
                    "creature_source_binding_id": binding_id,
                },
            }
    return options


def learning_context(character):
    from charsheet.advanced_bonus_specializations import (
        learning_context as bonus_learning_context,
    )

    bonus_context = bonus_learning_context(character)
    options = sorted(
        (
            option
            for option in configured_options(character).values()
            if option["available"]
        ),
        key=lambda option: (option["school_name"], option["name"]),
    )
    owned = [
        {
            "id": entry.pk,
            "name": entry.specialization.name,
            "school_name": entry.specialization.school.name,
            "cost": -data["paid_ep"],
            "description": entry.specialization.description,
        }
        for entry, data in purchases(character)
    ]
    return {
        **bonus_context,
        "learn_advanced_options": options,
        "learn_advanced_owned": owned,
        "learn_advanced_tab_visible": bool(
            options or owned or bonus_context["learn_advanced_bonus_options"]
        ),
    }


def plan_submission(character, post_data, school_levels):
    """Validate all selections before mutation, including automatic refunds."""
    options = configured_options(character)
    owned = {entry.pk: (entry, data) for entry, data in purchases(character)}
    removals = {}
    additions = []
    for entry, data in owned.values():
        level = school_levels.get(str(entry.specialization.school_id), 0)
        if level < data["required_level"]:
            removals[entry.pk] = (entry, data)
    selected_abilities = set()
    for key in post_data:
        key = str(key)
        if not key.startswith(
            ("learn_advanced_buy_", "learn_advanced_remove_")
        ):
            continue
        try:
            count = int(post_data.get(key, 0))
        except (TypeError, ValueError):
            raise ValidationError("Ungültige Spezialisierungs-Auswahl.")
        if not count:
            continue
        if key.startswith("learn_advanced_remove_"):
            try:
                entry_id = int(key.removeprefix("learn_advanced_remove_"))
            except ValueError:
                raise ValidationError("Ungültige Spezialisierungs-Auswahl.")
            if entry_id not in owned or count != 1:
                raise ValidationError(
                    "Ungültige Spezialisierung zum Verlernen."
                )
            removals[entry_id] = owned[entry_id]
            continue
        option = options.get(key.removeprefix("learn_advanced_buy_"))
        if (
            option is None
            or not option["available"]
            or count < 1
            or count > 100
        ):
            raise ValidationError(
                "Spezialisierung nicht verfügbar oder "
                "Voraussetzungen nicht erfüllt."
            )
        specialization = option["specialization"]
        ability_key = (
            specialization.school_id, specialization.name.strip().casefold()
        )
        if (
            school_levels.get(str(specialization.school_id), 0)
            < option["snapshot"]["required_level"]
        ):
            raise ValidationError(
                "Die erforderliche Schulstufe ist nicht erreicht."
            )
        if not option["repeatable"] and (
            count > 1 or ability_key in selected_abilities
        ):
            raise ValidationError(
                "Diese Fähigkeit darf nur einmal gelernt werden."
            )
        if any(
            entry.specialization_id == specialization.pk
            for entry, data in removals.values()
        ):
            raise ValidationError(
                "Eine Fähigkeit kann nicht zugleich "
                "gelernt und verlernt werden."
            )
        selected_abilities.add(ability_key)
        additions.extend([option] * count)
    cost = sum(option["cost"] for option in additions)
    cost -= sum(data["paid_ep"] for entry, data in removals.values())
    return additions, removals, cost


def apply_submission(character, additions, removals):
    """Persist purchases and remove choices in the caller's transaction."""
    for entry, data in removals.values():
        entry.delete()
    for option in additions:
        # Recheck after removals and earlier purchases in the same transaction.
        current = configured_options(character).get(option["key"])
        if current is None or not current["available"]:
            raise ValidationError(
                "Voraussetzungen der Spezialisierung nicht erfüllt."
            )
        CharacterSpecialization.objects.create(
            character=character,
            specialization=option["specialization"],
            source_technique=option["source_technique"],
            learned_at=timezone.now(),
            notes=PURCHASE_PREFIX + json.dumps(option["snapshot"]),
        )
