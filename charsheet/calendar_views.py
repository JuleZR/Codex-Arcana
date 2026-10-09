"""Character date persistence and server-calculated calendar navigation."""

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from charsheet.calendar_forms import month_options, season_payload
from charsheet.engine.calendar_engine import CalendarEngine
from charsheet.models import CalendarSystem, Character, CharacterDate


def integer(value):
    if type(value) is int:
        number = value
    elif isinstance(value, str) and value.lstrip("-").isdigit():
        number = int(value)
    else:
        raise ValueError("Eine Ganzzahl wird benötigt.")
    if not -(2**63) <= number < 2**63:
        raise ValueError(
            "Die Zahl liegt außerhalb des unterstützten Bereichs."
        )
    return number


def date_payload(engine, system, absolute):
    year, month, day = engine.from_absolute(system, absolute)
    months, _ = engine.structure(system.calendar_definition)
    date_text = f"{day:02d}. {months[month - 1].name} {year}"
    return {
        "system": system.pk,
        "year": str(year),
        "month": month,
        "month_name": months[month - 1].name,
        "day": day,
        "absolute_day": str(absolute),
        "day_month": f"{day}. {months[month - 1].name}",
        "date_text": date_text,
        "abbreviation": system.abbreviation,
        "system_name": system.name,
        "season": season_payload(months[month - 1]),
        "label": f"{date_text} {system.abbreviation}",
    }


def initial_date(engine, system, systems):
    source = next((s for s in systems.values() if s.real_date_reference), None)
    if source:
        try:
            engine.validate_real_date_calendar(source.calendar_definition)
        except ValidationError:
            source = None
    if source:
        today = timezone.localdate()
        return engine.to_absolute(source, today.year, today.month, today.day)
    if not system.reference_system_id:
        return 0  # The configured origin of this root, not an assumed date.
    return engine.to_absolute(
        system, system.anchor_year, system.anchor_month, system.anchor_day
    )


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def character_date(request, character_id):
    from charsheet.views import _owned_character_or_404

    character = _owned_character_or_404(request, character_id)
    engine = CalendarEngine()
    systems = {}
    for system in CalendarSystem.objects.select_related("calendar_definition"):
        try:
            engine.system_offset(system)
        except ValidationError:
            continue
        systems[system.pk] = system
    default_system = next(
        (s for s in systems.values() if s.default_for_characters), None
    )
    default_system = default_system or next(
        (s for s in systems.values() if not s.reference_system_id), None
    )
    try:
        if request.method == "POST":
            payload = json.loads(request.body)
            if not isinstance(payload, dict):
                raise ValueError("Ungültige Anfrage.")
            with transaction.atomic():
                Character.objects.select_for_update().get(pk=character.pk)
                stored = CharacterDate.objects.filter(
                    character=character
                ).first()
                action = payload.get("action")
                if action == "initialize":
                    if stored:
                        system = systems[stored.system_id]
                        absolute = stored.absolute_day
                    else:
                        system = (
                            systems[integer(payload["system"])]
                            if "system" in payload
                            else default_system
                        )
                        if system is None:
                            raise ValueError(
                                "Es ist noch kein gültiger "
                                "Kalender eingerichtet."
                            )
                        absolute = initial_date(engine, system, systems)
                elif action == "step":
                    delta = integer(payload["delta"])
                    if stored is None or delta not in (-1, 1):
                        raise ValueError("Bitte zuerst ein Datum festlegen.")
                    system = systems[stored.system_id]
                    absolute = stored.absolute_day + delta
                else:
                    system = systems[integer(payload["system"])]
                    if action == "switch":
                        if stored is None:
                            raise ValueError(
                                "Bitte zuerst ein Datum festlegen."
                            )
                        absolute = stored.absolute_day
                    elif action == "set":
                        absolute = engine.to_absolute(
                            system,
                            integer(payload["year"]),
                            integer(payload["month"]),
                            integer(payload["day"]),
                        )
                    else:
                        raise ValueError("Unbekannte Datumsaktion.")
                integer(absolute)
                if action != "initialize" or stored is None:
                    CharacterDate.objects.update_or_create(
                        character=character,
                        defaults={
                            "system": system,
                            "absolute_day": absolute,
                        },
                    )
        stored = CharacterDate.objects.filter(character=character).first()
        current = (
            date_payload(
                engine, systems[stored.system_id], stored.absolute_day
            )
            if stored
            else None
        )
        result = {
            "current": current,
            "default_system": default_system.pk if default_system else None,
            "systems": [
                {"id": s.pk, "name": s.name} for s in systems.values()
            ],
        }
        if request.method == "GET" and "system" in request.GET:
            system = systems[integer(request.GET["system"])]
            if "absolute" in request.GET:
                absolute = integer(request.GET["absolute"])
            elif "year" in request.GET:
                year = integer(request.GET["year"])
                month = integer(request.GET.get("month", "1"))
                day = integer(request.GET.get("day", "1"))
                lengths = engine.month_lengths(
                    system.calendar_definition, year
                )
                if not 1 <= month <= len(lengths):
                    raise ValueError("Ungültiger Monat.")
                absolute = engine.to_absolute(
                    system, year, month, min(max(day, 1), lengths[month - 1])
                )
            elif stored:
                absolute = stored.absolute_day
            else:
                raise ValueError("Bitte eine Jahreszahl eingeben.")
            preview = date_payload(engine, system, absolute)
            preview["months"] = month_options(
                system.calendar_definition,
                int(preview["year"]),
                engine,
            )
            preview["saved_date"] = (
                date_payload(engine, system, stored.absolute_day)
                if stored
                else None
            )
            result["preview"] = preview
        return JsonResponse(result)
    except (ValueError, TypeError, KeyError, ValidationError) as error:
        message = (
            " ".join(error.messages)
            if isinstance(error, ValidationError)
            else "Ungültige Kalenderangaben. " + str(error)
        )
        return JsonResponse({"error": message}, status=400)
