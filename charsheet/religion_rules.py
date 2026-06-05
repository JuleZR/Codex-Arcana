"""Shared rules for divine religion bindings and clerical school locks."""

from __future__ import annotations

from charsheet.constants import SCHOOL_DIVINE


def is_clerical_school(school_or_entry) -> bool:
    """Return whether a school belongs to the clerical/divine school type."""
    school = getattr(school_or_entry, "school", school_or_entry)
    school_type = getattr(school, "type", None)
    if school_type is None:
        return False
    slug = str(getattr(school_type, "slug", "") or "").strip().lower()
    name = str(getattr(school_type, "name", "") or "").strip().lower()
    return slug in {SCHOOL_DIVINE, "school_divine"} or "kler" in name or "divin" in name or "priest" in name


def active_clerical_school_entries(character):
    """Return learned clerical school rows that currently lock religion."""
    from charsheet.models import CharacterSchool

    entries = list(
        CharacterSchool.objects.filter(
            character=character,
            level__gt=0,
        )
        .select_related("school", "school__type")
        .order_by("school__name")
    )
    return [entry for entry in entries if is_clerical_school(entry)]


def selected_divine_entity(character):
    """Return the selected divine entity from binding or legacy display text."""
    from charsheet.models import CharacterDivineEntity, DivineEntity

    binding = (
        CharacterDivineEntity.objects.filter(character=character)
        .select_related("entity", "entity__school", "entity__school__type")
        .first()
    )
    if binding is not None:
        return binding.entity
    religion_name = str(getattr(character, "religion", "") or "").strip()
    if not religion_name:
        return None
    return DivineEntity.objects.filter(name=religion_name).select_related("school", "school__type").first()


def unique_divine_entity_for_school(school_id: int):
    """Return the only entity for a school, or None if the mapping is ambiguous."""
    from charsheet.models import DivineEntity

    entities = list(
        DivineEntity.objects.filter(school_id=school_id)
        .select_related("school", "school__type")
        .order_by("name")[:2]
    )
    return entities[0] if len(entities) == 1 else None


def divine_entity_count_for_school(school_id: int) -> int:
    """Return how many divine entities point to one clerical school."""
    from charsheet.models import DivineEntity

    return DivineEntity.objects.filter(school_id=school_id).count()


def locked_religion_entity(character, *, repair: bool = False):
    """Return the entity that locks religion while a clerical school is active."""
    from charsheet.models import CharacterDivineEntity

    entries = active_clerical_school_entries(character)
    if len(entries) != 1:
        return None

    school_id = int(entries[0].school_id)
    entity = selected_divine_entity(character)
    if entity is None or int(entity.school_id) != school_id:
        entity = unique_divine_entity_for_school(school_id)
    if entity is None or int(entity.school_id) != school_id:
        return None

    if repair:
        CharacterDivineEntity.objects.update_or_create(
            character=character,
            defaults={"entity": entity},
        )
        if (character.religion or "") != entity.name:
            character.religion = entity.name
            character.save(update_fields=["religion"])
    return entity


def is_religion_locked(character) -> bool:
    """Return whether the character has an active clerical school lock."""
    return locked_religion_entity(character) is not None
