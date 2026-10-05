"""Load archetype content into the existing creation draft input format."""

from copy import deepcopy
import json
import logging
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.utils.text import slugify

from .models import Aspect, Country, Lesson, Race, Rune, School, Trait

logger = logging.getLogger(__name__)


def _reference(queryset, value):
    """Resolve a stable slug or name; never interpret content as a DB pk."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Eine stabile Referenz fehlt.")
    fields = {field.name for field in queryset.model._meta.fields}
    if "slug" in fields:
        return queryset.get(slug=value)
    matches = [
        obj for obj in queryset
        if obj.name == value or slugify(obj.name) == value
    ]
    if len(matches) != 1:
        raise ValueError(f"Referenz „{value}“ ist unbekannt oder mehrdeutig.")
    return matches[0]


def archetype_state(raw_state):
    """Copy content and resolve its stable references to local draft ids."""
    if not isinstance(raw_state, dict):
        raise ValueError("Der Creation-State muss ein Objekt sein.")
    state = deepcopy(raw_state)
    for key in ("meta", "phase_1", "phase_2", "phase_3", "phase_4"):
        if not isinstance(state.get(key), dict):
            raise ValueError(f"Der Bereich „{key}“ fehlt oder ist ungültig.")
    meta = state["meta"]
    if not isinstance(meta.get("name"), str) or not meta["name"].strip():
        raise ValueError("Der Charaktername fehlt.")
    if len(meta["name"]) > 100:
        raise ValueError("Der Charaktername ist zu lang.")
    if meta.get("country_of_origin"):
        meta["country_of_origin"] = _reference(
            Country.objects.all(), meta["country_of_origin"]
        ).pk
    phase_4 = state["phase_4"]
    for key, model in (("schools", School), ("aspects", Aspect)):
        if key in phase_4:
            if not isinstance(phase_4[key], dict):
                raise ValueError(
                    f"phase_4.{key} muss ein JSON-Objekt sein "
                    "(für eine leere Auswahl: {}).",
                )
            phase_4[key] = {
                str(_reference(model.objects.all(), ref).pk): level
                for ref, level in phase_4[key].items()
            }
    if "lessons" in phase_4:
        phase_4["lessons"] = [
            _reference(Lesson.objects.all(), ref).pk
            for ref in phase_4["lessons"]
        ]
    for row in phase_4.get("weapon_arcana", []):
        if row.get("rune_id"):
            row["rune_id"] = _reference(
                Rune.objects.all(), row["rune_id"]
            ).pk
    for phase_key in ("phase_3", "phase_4"):
        phase = state[phase_key]
        for slug, payload in phase.get("trait_specifications", {}).items():
            if payload.get("option_id"):
                trait = Trait.objects.get(slug=slug)
                payload["option_id"] = _reference(
                    trait.specification_options.all(), payload["option_id"]
                ).pk
        for slug, choices in phase.get("trait_choices", {}).items():
            trait = Trait.objects.get(slug=slug)
            resolved = {}
            for ref, values in choices.items():
                definition = _reference(trait.choice_definitions.all(), ref)
                if definition.target_kind == "entity":
                    selected = []
                    for value in values:
                        matches = [
                            option
                            for option in definition.entity_options.all()
                            if (
                                option.entity is not None
                                and option.content_type.model == value["model"]
                                and _entity_reference(option.entity)
                                == value["ref"]
                            )
                        ]
                        if len(matches) != 1:
                            raise ValueError(
                                "Die Entitätsauswahl ist ungültig.",
                            )
                        selected.append(str(matches[0].pk))
                    values = selected
                resolved[str(definition.pk)] = values
            phase.setdefault("trait_choices", {})[slug] = resolved
    return state


def _entity_reference(entity):
    return getattr(entity, "slug", None) or getattr(entity, "name", None)


def load_archetypes():
    """Ignore malformed/unresolvable files; rules are checked by the engine."""
    directory = Path(settings.BASE_DIR) / "archetypes"
    archetypes = {}
    duplicates = set()
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            slug = payload["slug"]
            name = payload["name"]
            if (
                not isinstance(slug, str) or not slug
                or slugify(slug) != slug
                or not isinstance(name, str) or not name.strip()
            ):
                raise ValueError("Slug oder Anzeigename ist ungültig.")
            race = _reference(Race.objects.all(), payload["race"])
            state = archetype_state(payload["state"])
            if slug in archetypes or slug in duplicates:
                logger.warning(
                    "Archetyp %s übersprungen: "
                    "Slug %s ist mehrfach vorhanden.",
                    path.name, slug,
                )
                archetypes.pop(slug, None)
                duplicates.add(slug)
                continue
            archetypes[slug] = {
                "slug": slug, "name": name, "race": race, "state": state,
                "description": str(payload.get("description") or ""),
            }
        except (
            OSError, UnicodeError, ValueError, TypeError, KeyError,
            AttributeError, ObjectDoesNotExist, MultipleObjectsReturned,
        ) as exc:
            logger.warning(
                "Archetyp %s übersprungen: %s", path.name, exc,
            )
            continue
    return sorted(
        archetypes.values(), key=lambda item: item["name"].casefold(),
    )
