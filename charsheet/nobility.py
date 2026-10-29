"""Country title editing for an acquired trait, without progression changes."""

import json

from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.models import (
    CharacterTrait, CharacterTraitChoice, CharacterTraitNobilityTitle, Country,
)


def nobility_editor_payload(entry):
    """Supply the shared CP and current catalog to the title editor."""
    if not entry.trait.choice_definitions.filter(
        is_active=True, uses_nobility_ranks=True,
    ).exists():
        return None
    points = entry.trait.cost_for_level(entry.trait_level)
    return {
        "points": points,
        "titles": entry.resolved_nobility_titles or [{
            "country_id": None, "specification": entry.specification,
        }],
        "countries": [{
            "id": country.pk, "name": country.name,
            "rank": country.nobility_rank_system.resolve_rank(
                points,
            ),
            "rank_options": list(country.nobility_rank_system.ranks.filter(
                cp_threshold__lte=points,
            ).values_list("title", flat=True)),
        } for country in Country.objects.filter(
            nobility_rank_system__isnull=False,
        ).select_related("nobility_rank_system")],
    }


@transaction.atomic
def save_nobility_titles(entry, raw_titles):
    """Replace an owned trait's titles atomically after server validation."""
    entry = CharacterTrait.objects.select_for_update().get(pk=entry.pk)
    definition = entry.trait.choice_definitions.filter(
        is_active=True, uses_nobility_ranks=True,
    ).first()
    if definition is None:
        raise ValidationError("Dieser Trait unterstützt keine Adelstitel.")
    try:
        data = json.loads(raw_titles)
    except (ValueError, TypeError):
        raise ValidationError("Ungültige Titelauswahl.")
    if not isinstance(data, list) or not data:
        raise ValidationError("Mindestens einen Titel angeben.")
    titles = []
    points = entry.trait.cost_for_level(entry.trait_level)
    for index, row in enumerate(data):
        if not isinstance(row, dict) or not isinstance(
            row.get("specification", ""), str,
        ):
            raise ValidationError("Ungültige Titelauswahl.")
        country_id = row.get("country_id")
        is_custom_title = country_id in (None, "")
        if isinstance(country_id, bool) or not isinstance(
            country_id, (str, int, type(None)),
        ):
            raise ValidationError("Ein Land mit Adelsrangsystem auswählen.")
        selection = (
            definition.entity_selection_payload(country_id)
            if not is_custom_title else None
        )
        selected_rank = row.get("selected_rank", "")
        if not isinstance(selected_rank, str):
            raise ValidationError("Ungültiger Rang.")
        title = CharacterTraitNobilityTitle(
            character_trait=entry,
            country_id=selection["selected_object_id"] if selection else None,
            is_custom_title=is_custom_title,
            specification=" ".join(row.get("specification", "").split()),
            selected_rank=selected_rank.strip(),
            sort_order=index,
        )
        title.full_clean()
        if (
            not is_custom_title
            and "selected_rank" in row and not title.selected_rank
        ):
            if title.country.nobility_rank_system.ranks.filter(
                cp_threshold__lte=points,
            ).exists():
                raise ValidationError("Einen verfügbaren Rang auswählen.")
        titles.append(title)
    entry.nobility_titles.all().delete()
    for title in titles:
        title.save()
    # Keep the original acquisition choice usable by creation/learning flows.
    entry.choices.filter(definition=definition).delete()
    country_title = next((title for title in titles if title.country_id), None)
    if country_title is not None:
        choice = CharacterTraitChoice(
            character_trait=entry, definition=definition,
            **definition.entity_selection_payload(country_title.country_id),
        )
        choice.full_clean()
        choice.save()
    if entry.trait.has_specification:
        entry.specification = titles[0].specification
        entry.save(update_fields=["specification"])
