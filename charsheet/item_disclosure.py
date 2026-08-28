"""Disclosure and identification helpers for concrete character items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db import transaction

from charsheet.engine.item_engine import ItemEngine
from charsheet.models import (
    CharacterItem,
    CharacterItemDisclosure,
    CharacterItemEffectIdentification,
    CharacterItemIdentificationState,
    CharacterItemSemanticEffect,
    ItemSemanticEffect,
)


DISCLOSURE_FIELD_KEYS = (
    "name",
    "image",
    "description",
    "item_type",
    "quality",
    "weight",
    "size_class",
    "price",
    "magic_status",
    "weapon_type",
    "weapon_skill",
    "weapon_damage",
    "weapon_minimums",
    "weapon_wield_mode",
    "weapon_maneuver_bonus",
    "weapon_damage_bonus",
    "weapon_range",
    "weapon_reload",
    "weapon_ammo",
    "weapon_flags",
)


@dataclass(frozen=True)
class ResolvedCharacterItemDisplay:
    """Resolved item display data safe for the intended viewer."""

    character_item: CharacterItem
    actual_name: str
    name: str
    description: str
    image_url: str
    item_type: str
    quality_label: str
    quality_color: str
    price: int | None
    weight: str
    size_class: str
    visible_field_keys: frozenset[str]
    hidden_field_keys: frozenset[str]
    identified_item_effect_ids: frozenset[int]
    identified_character_item_effect_ids: frozenset[int]


def _disclosures_by_field(character_item: CharacterItem) -> dict[str, CharacterItemDisclosure]:
    prefetched = getattr(character_item, "_prefetched_objects_cache", {}).get("disclosures")
    rows = prefetched if prefetched is not None else character_item.disclosures.all()
    return {row.field_key: row for row in rows}


def _field_value(
    *,
    field_key: str,
    actual_value,
    disclosures: dict[str, CharacterItemDisclosure],
    privileged: bool,
) -> tuple[object, bool]:
    if privileged:
        return actual_value, True
    disclosure = disclosures.get(field_key)
    if disclosure is None or disclosure.revealed:
        return actual_value, True
    alternative = str(disclosure.alternative_text or "")
    return alternative, False


def resolve_character_item_display(
    character_item: CharacterItem,
    viewer=None,
    *,
    preview_player: bool = False,
    include_controls: bool = False,
) -> ResolvedCharacterItemDisplay:
    """Return resolved item-card data without mutating the database."""
    del include_controls
    privileged = not preview_player and _viewer_can_see_actual_item(viewer, character_item)
    disclosures = _disclosures_by_field(character_item)
    item_engine = ItemEngine(character_item)
    actual_name = item_engine.get_name()
    actual_description = character_item.description or character_item.item.description or ""
    name, name_visible = _field_value(
        field_key="name",
        actual_value=actual_name,
        disclosures=disclosures,
        privileged=privileged,
    )
    description, description_visible = _field_value(
        field_key="description",
        actual_value=actual_description,
        disclosures=disclosures,
        privileged=privileged,
    )
    image_url = character_item.effective_image_url
    image_url, image_visible = _field_value(
        field_key="image",
        actual_value=image_url,
        disclosures=disclosures,
        privileged=privileged,
    )
    image_disclosure = disclosures.get("image")
    if (
        not privileged
        and image_disclosure is not None
        and not image_disclosure.revealed
        and image_disclosure.alternative_image
    ):
        try:
            image_url = image_disclosure.alternative_image.url or ""
        except ValueError:
            image_url = ""
    item_type, item_type_visible = _field_value(
        field_key="item_type",
        actual_value=character_item.item.get_item_type_display(),
        disclosures=disclosures,
        privileged=privileged,
    )
    quality_label, quality_visible = _field_value(
        field_key="quality",
        actual_value=str(item_engine.get_effective_quality_obj()),
        disclosures=disclosures,
        privileged=privileged,
    )
    price, price_visible = _field_value(
        field_key="price",
        actual_value=item_engine.get_price(),
        disclosures=disclosures,
        privileged=privileged,
    )
    weight, weight_visible = _field_value(
        field_key="weight",
        actual_value=str(item_engine.get_weight()),
        disclosures=disclosures,
        privileged=privileged,
    )
    size_class, size_visible = _field_value(
        field_key="size_class",
        actual_value=item_engine.get_size_class(),
        disclosures=disclosures,
        privileged=privileged,
    )
    visible_field_keys = {
        key
        for key, visible in {
            "name": name_visible,
            "description": description_visible,
            "image": image_visible,
            "item_type": item_type_visible,
            "quality": quality_visible,
            "price": price_visible,
            "weight": weight_visible,
            "size_class": size_visible,
        }.items()
        if visible
    }
    hidden_field_keys = set(DISCLOSURE_FIELD_KEYS) - visible_field_keys
    identified_item_effect_ids, identified_character_item_effect_ids = identified_effect_id_sets(character_item)
    return ResolvedCharacterItemDisplay(
        character_item=character_item,
        actual_name=actual_name,
        name=str(name or ""),
        description=str(description or ""),
        image_url=str(image_url or ""),
        item_type=str(item_type or ""),
        quality_label=str(quality_label or ""),
        quality_color=item_engine.get_quality_color() if quality_visible or privileged else "",
        price=int(price) if isinstance(price, int) else None,
        weight=str(weight or ""),
        size_class=str(size_class or ""),
        visible_field_keys=frozenset(visible_field_keys),
        hidden_field_keys=frozenset(hidden_field_keys),
        identified_item_effect_ids=frozenset(identified_item_effect_ids),
        identified_character_item_effect_ids=frozenset(identified_character_item_effect_ids),
    )


def _viewer_can_see_actual_item(viewer, character_item: CharacterItem) -> bool:
    if viewer is None:
        return False
    owner = getattr(character_item, "owner", None)
    if owner is not None and getattr(owner, "owner_id", None) == getattr(viewer, "id", None):
        return False
    return True


def item_identification_initialized(character_item: CharacterItem) -> bool:
    try:
        return bool(character_item.identification_state.initialized)
    except CharacterItemIdentificationState.DoesNotExist:
        return False


def relevant_item_effects(
    character_item: CharacterItem,
) -> tuple[list[ItemSemanticEffect], list[CharacterItemSemanticEffect]]:
    item_effects = list(
        ItemSemanticEffect.objects.filter(
            item_id=character_item.item_id,
            active_flag=True,
        ).order_by("sort_order", "id")
    )
    character_item_effects = list(
        CharacterItemSemanticEffect.objects.filter(
            character_item_id=character_item.id,
            active_flag=True,
        ).order_by("sort_order", "id")
    )
    return item_effects, character_item_effects


def identified_effect_id_sets(character_item: CharacterItem) -> tuple[set[int], set[int]]:
    """Return identified base and instance effect ids for display filtering."""
    if not item_identification_initialized(character_item):
        item_effects, character_item_effects = relevant_item_effects(character_item)
        return {effect.id for effect in item_effects}, {effect.id for effect in character_item_effects}
    identifications = CharacterItemEffectIdentification.objects.filter(
        character_item=character_item,
        identified=True,
    ).values_list("item_effect_id", "character_item_effect_id")
    item_effect_ids: set[int] = set()
    character_item_effect_ids: set[int] = set()
    for item_effect_id, character_item_effect_id in identifications:
        if item_effect_id:
            item_effect_ids.add(int(item_effect_id))
        if character_item_effect_id:
            character_item_effect_ids.add(int(character_item_effect_id))
    return item_effect_ids, character_item_effect_ids


def is_character_item_effect_identified(
    character_item: CharacterItem,
    effect: ItemSemanticEffect | CharacterItemSemanticEffect,
) -> bool:
    """Return whether one effect may be shown/applied for a concrete item."""
    if not item_identification_initialized(character_item):
        return True
    if isinstance(effect, ItemSemanticEffect):
        return CharacterItemEffectIdentification.objects.filter(
            character_item=character_item,
            item_effect=effect,
            identified=True,
        ).exists()
    return CharacterItemEffectIdentification.objects.filter(
        character_item=character_item,
        character_item_effect=effect,
        identified=True,
    ).exists()


@transaction.atomic
def initialize_item_identification(character_item: CharacterItem) -> None:
    """Enter explicit identification workflow and create rows for current effects."""
    CharacterItemIdentificationState.objects.update_or_create(
        character_item=character_item,
        defaults={"initialized": True},
    )
    item_effects, character_item_effects = relevant_item_effects(character_item)
    for effect in item_effects:
        CharacterItemEffectIdentification.objects.get_or_create(
            character_item=character_item,
            item_effect=effect,
            defaults={"identified": False},
        )
    for effect in character_item_effects:
        CharacterItemEffectIdentification.objects.get_or_create(
            character_item=character_item,
            character_item_effect=effect,
            defaults={"identified": False},
        )


@transaction.atomic
def set_item_disclosures(
    character_item: CharacterItem,
    updates: Iterable[dict[str, object]],
) -> None:
    for update in updates:
        field_key = str(update.get("field_key") or "").strip()
        if field_key not in DISCLOSURE_FIELD_KEYS:
            continue
        defaults = {
            "revealed": bool(update.get("revealed")),
        }
        if "alternative_text" in update:
            defaults["alternative_text"] = str(update.get("alternative_text") or "")
        if update.get("clear_alternative_image"):
            defaults["alternative_image"] = None
        alternative_image = update.get("alternative_image")
        if alternative_image:
            defaults["alternative_image"] = alternative_image
        CharacterItemDisclosure.objects.update_or_create(
            character_item=character_item,
            field_key=field_key,
            defaults=defaults,
        )


@transaction.atomic
def set_effect_identifications(
    character_item: CharacterItem,
    updates: Iterable[dict[str, object]],
) -> bool:
    """Persist effect identification changes. Return whether mechanics changed."""
    initialize_item_identification(character_item)
    changed = False
    for update in updates:
        source = str(update.get("source") or "").strip()
        effect_id = update.get("effect_id")
        try:
            effect_id = int(effect_id)
        except (TypeError, ValueError):
            continue
        identified = bool(update.get("identified"))
        alternative_text = str(update.get("alternative_text") or "")
        filters = {"character_item": character_item}
        if source == "item":
            filters["item_effect_id"] = effect_id
        elif source == "character_item":
            filters["character_item_effect_id"] = effect_id
        else:
            continue
        row = (
            CharacterItemEffectIdentification.objects
            .select_for_update(of=("self",))
            .filter(**filters)
            .first()
        )
        if row is None:
            continue
        if bool(row.identified) != identified:
            changed = True
        row.identified = identified
        row.alternative_text = alternative_text
        row.full_clean()
        row.save(update_fields=["identified", "alternative_text"])
    return changed


@transaction.atomic
def reveal_all_character_item(character_item: CharacterItem) -> bool:
    """Reveal all fields and identify all current effects. Return mechanics changed."""
    for field_key in DISCLOSURE_FIELD_KEYS:
        CharacterItemDisclosure.objects.update_or_create(
            character_item=character_item,
            field_key=field_key,
            defaults={"revealed": True},
        )
    initialize_item_identification(character_item)
    changed = False
    for row in CharacterItemEffectIdentification.objects.select_for_update(of=("self",)).filter(character_item=character_item):
        if not row.identified:
            changed = True
            row.identified = True
            row.save(update_fields=["identified"])
    return changed


@transaction.atomic
def hide_all_character_item(character_item: CharacterItem) -> bool:
    """Hide all fields and unidentify all current effects. Return mechanics changed."""
    for field_key in DISCLOSURE_FIELD_KEYS:
        CharacterItemDisclosure.objects.update_or_create(
            character_item=character_item,
            field_key=field_key,
            defaults={"revealed": False},
        )
    initialize_item_identification(character_item)
    changed = False
    for row in CharacterItemEffectIdentification.objects.select_for_update(of=("self",)).filter(character_item=character_item):
        if row.identified:
            changed = True
            row.identified = False
            row.save(update_fields=["identified"])
    return changed
