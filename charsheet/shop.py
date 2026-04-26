"""Shop helpers for custom item creation and cart purchases."""

from __future__ import annotations

import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.constants import DEADLY
from charsheet.engine import ItemEngine
from charsheet.models import (
    ArmorStats,
    Character,
    CharacterItem,
    CharacterItemRuneSpec,
    ItemRune,
    DamageSource,
    Item,
    MagicItemStats,
    Modifier,
    Rune,
    ShieldStats,
    Skill,
    SkillCategory,
    Specialization,
    WeaponStats,
)


def apply_rune_to_item(*, item: CharacterItem, rune: Rune, crafter_level: int) -> ItemRune:
    """Apply or improve one rune assignment on a concrete owned item."""
    allowed_item_types = set(rune.allowed_item_types or [])
    if allowed_item_types and item.item.item_type not in allowed_item_types:
        raise ValidationError({"rune": "Diese Rune ist fuer diesen Gegenstandstyp nicht erlaubt."})
    if rune.allow_multiple:
        return ItemRune.objects.create(
            item=item,
            rune=rune,
            crafter_level=crafter_level,
        )

    item_rune, created = ItemRune.objects.get_or_create(
        item=item,
        rune=rune,
        defaults={
            "crafter_level": crafter_level,
            "is_active": True,
        },
    )

    if not created:
        item_rune.crafter_level = crafter_level
        item_rune.is_active = True
        item_rune.save(
            update_fields=[
                "crafter_level",
                "is_active",
                "allows_duplicate",
                "updated_at",
            ]
        )

    return item_rune


def _read_int(post_data, name: str, default: int = 0, *, minimum: int | None = None) -> int:
    """Read one integer value from POST-like data and clamp it if needed."""
    try:
        value = int(post_data.get(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def _read_quality(post_data, name: str, default: str) -> str:
    """Read one normalized quality code from POST-like data."""
    raw_quality = str(post_data.get(name, default) or default)
    return ItemEngine.normalize_quality(raw_quality)


def _read_damage_operator(post_data, name: str, default: str = "") -> str:
    """Read one normalized damage operator from POST-like data."""
    raw_value = str(post_data.get(name, default) or default).strip()
    valid_values = {value for value, _label in WeaponStats.DamageOperator.choices}
    return raw_value if raw_value in valid_values else default


def _read_many_values(post_data, name: str) -> list[str]:
    """Read one POST multi-value field while also tolerating plain dict payloads."""
    if hasattr(post_data, "getlist"):
        return [str(value).strip() for value in post_data.getlist(name) if str(value).strip()]
    raw_value = post_data.get(name, [])
    if isinstance(raw_value, (list, tuple)):
        return [str(value).strip() for value in raw_value if str(value).strip()]
    if raw_value in (None, ""):
        return []
    return [str(raw_value).strip()]


def _build_magic_modifier_payload(target_kind: str, raw_value, row_data) -> dict[str, object] | None:
    """Resolve one normalized magic-item modifier payload from raw row data."""
    if not target_kind:
        return None

    try:
        value = int(raw_value or 0)
    except (TypeError, ValueError):
        value = 0

    payload: dict[str, object] = {
        "target_kind": target_kind,
        "value": value,
        "effect_description": str(row_data.get("effect_description") or "").strip(),
        "target_slug": "",
        "target_skill": None,
        "target_skill_category": None,
        "target_item": None,
        "target_specialization": None,
    }

    if target_kind == Modifier.TargetKind.ATTRIBUTE:
        target_slug = str(row_data.get("target_attribute") or "").strip()
        if not target_slug:
            return None
        payload["target_slug"] = target_slug
    elif target_kind == Modifier.TargetKind.STAT:
        target_slug = str(row_data.get("target_stat") or "").strip()
        if not target_slug:
            return None
        payload["target_slug"] = target_slug
    elif target_kind == Modifier.TargetKind.SKILL:
        skill_id = int(row_data.get("target_skill") or 0)
        if skill_id <= 0:
            return None
        payload["target_skill"] = Skill.objects.get(pk=skill_id)
        # target_slug must stay empty when target_skill FK is set (only one selector allowed)
    elif target_kind == Modifier.TargetKind.CATEGORY:
        category_id = int(row_data.get("target_skill_category") or 0)
        if category_id <= 0:
            return None
        payload["target_skill_category"] = SkillCategory.objects.get(pk=category_id)
        # target_slug must stay empty when target_skill_category FK is set (only one selector allowed)
    elif target_kind == Modifier.TargetKind.ITEM_CATEGORY:
        target_slug = str(row_data.get("target_item_category") or "").strip()
        if not target_slug:
            return None
        payload["target_slug"] = target_slug
    elif target_kind == Modifier.TargetKind.SPECIALIZATION:
        specialization_id = int(row_data.get("target_specialization") or 0)
        if specialization_id <= 0:
            return None
        payload["target_specialization"] = Specialization.objects.get(pk=specialization_id)
    else:
        raise ValidationError({"magic_modifier_target_kind": "Unsupported magic modifier target."})

    return payload


def _read_magic_modifier_payload(post_data) -> dict[str, object] | None:
    """Read one optional legacy magic-item modifier definition from the shop form."""
    return _build_magic_modifier_payload(
        str(post_data.get("magic_modifier_target_kind") or "").strip(),
        post_data.get("magic_modifier_value", 0),
        {
            "target_stat": post_data.get("magic_modifier_target_stat"),
            "target_attribute": post_data.get("magic_modifier_target_attribute"),
            "target_skill": post_data.get("magic_modifier_target_skill"),
            "target_skill_category": post_data.get("magic_modifier_target_skill_category"),
            "target_item_category": post_data.get("magic_modifier_target_item_category"),
            "target_specialization": post_data.get("magic_modifier_target_specialization"),
            "effect_description": post_data.get("magic_modifier_effect_description"),
        },
    )


def _read_magic_modifier_payloads(post_data) -> list[dict[str, object]]:
    """Read zero or more magic-item modifier definitions from the shop form."""
    raw_payloads = str(post_data.get("magic_modifier_payloads") or "").strip()
    if not raw_payloads:
        legacy_payload = _read_magic_modifier_payload(post_data)
        return [legacy_payload] if legacy_payload is not None else []

    try:
        decoded_payloads = json.loads(raw_payloads)
    except json.JSONDecodeError as exc:
        raise ValidationError({"magic_modifier_payloads": "Ungültige Magie-Effekte."}) from exc

    if not isinstance(decoded_payloads, list):
        raise ValidationError({"magic_modifier_payloads": "Ungültige Magie-Effekte."})

    payloads: list[dict[str, object]] = []
    for entry in decoded_payloads:
        if not isinstance(entry, dict):
            raise ValidationError({"magic_modifier_payloads": "Ungültige Magie-Effekte."})
        payload = _build_magic_modifier_payload(
            str(entry.get("target_kind") or "").strip(),
            entry.get("value", 0),
            entry,
        )
        if payload is not None:
            payloads.append(payload)
    return payloads


def _read_rune_payloads(post_data) -> list[dict[str, object]]:
    """Read rune payloads from POST data.

    Returns a list of dicts with keys: rune_id (int), specification (str), slot (int).
    Prefers the JSON ``rune_payloads`` field; falls back to legacy ``runes`` checkboxes.
    """
    raw = str(post_data.get("rune_payloads") or "").strip()
    if raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, list):
            return []
        payloads: list[dict[str, object]] = []
        for entry in decoded:
            if not isinstance(entry, dict):
                continue
            try:
                rune_id = int(entry.get("rune_id") or 0)
            except (TypeError, ValueError):
                continue
            if rune_id <= 0:
                continue
            try:
                slot = max(1, int(entry.get("slot") or 1))
            except (TypeError, ValueError):
                slot = 1
            try:
                crafter_level = max(0, int(entry.get("crafter_level") or 0))
            except (TypeError, ValueError):
                crafter_level = 0
            payloads.append({
                "rune_id": rune_id,
                "specification": str(entry.get("specification") or "").strip(),
                "slot": slot,
                "crafter_level": crafter_level,
            })
        return payloads

    # Legacy fallback: plain rune checkboxes, no specification, slot=1
    rune_ids: list[int] = []
    for raw_value in _read_many_values(post_data, "runes"):
        try:
            rune_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    return [
        {"rune_id": rune_id, "specification": "", "slot": 1, "crafter_level": 0}
        for rune_id in sorted(set(rune_ids))
    ]


def _save_magic_modifiers(*, source_model, source_id: int, magic_modifier_payloads: list[dict[str, object]]) -> None:
    """Replace all legacy modifier rows for one magic source."""
    source_content_type = ContentType.objects.get_for_model(source_model, for_concrete_model=False)
    Modifier.objects.filter(
        source_content_type=source_content_type,
        source_object_id=source_id,
    ).delete()
    for magic_modifier_payload in magic_modifier_payloads:
        modifier = Modifier(
            source_content_type=source_content_type,
            source_object_id=source_id,
            target_kind=str(magic_modifier_payload["target_kind"]),
            target_slug=str(magic_modifier_payload["target_slug"] or ""),
            target_skill=magic_modifier_payload["target_skill"],
            target_skill_category=magic_modifier_payload["target_skill_category"],
            target_item=magic_modifier_payload["target_item"],
            target_specialization=magic_modifier_payload["target_specialization"],
            effect_description=str(magic_modifier_payload.get("effect_description") or ""),
            mode=Modifier.Mode.FLAT,
            value=int(magic_modifier_payload["value"]),
        )
        modifier.full_clean()
        modifier.save()


def apply_character_item_modifications(character_item: CharacterItem, post_data) -> bool:
    """Persist one owned-item modification including quality, runes, magic, and costs."""
    quality = _read_quality(post_data, "quality", character_item.quality or character_item.item.default_quality)
    experience_cost = _read_int(post_data, "experience_cost", 0, minimum=0)
    money_cost = _read_int(post_data, "money_cost", 0, minimum=0)
    rune_payloads = _read_rune_payloads(post_data)
    description = str(post_data.get("description") or "").strip()
    magic_effect_summary = str(post_data.get("magic_effect_summary") or "").strip()
    magic_modifier_payloads = _read_magic_modifier_payloads(post_data)
    is_magic = bool(magic_modifier_payloads) or bool(magic_effect_summary)

    base_rune_ids = set(character_item.item.runes.values_list("id", flat=True))

    # Deduplicate (rune_id, slot) pairs and filter out base runes
    seen_slots: set[tuple[int, int]] = set()
    filtered_payloads: list[dict[str, object]] = []
    for payload in rune_payloads:
        rune_id = int(payload["rune_id"])
        slot = int(payload["slot"])
        if rune_id in base_rune_ids:
            continue
        key = (rune_id, slot)
        if key in seen_slots:
            continue
        seen_slots.add(key)
        filtered_payloads.append(payload)

    # Fetch valid rune objects
    payload_rune_ids = list({int(p["rune_id"]) for p in filtered_payloads})
    runes_by_id = {rune.id: rune for rune in Rune.objects.filter(pk__in=payload_rune_ids)}

    # Enforce allow_multiple: drop extra slots for runes that don't allow it
    final_payloads: list[tuple[Rune, str, int, int]] = []
    for payload in filtered_payloads:
        rune = runes_by_id.get(int(payload["rune_id"]))
        if rune is None:
            continue
        allowed_item_types = set(rune.allowed_item_types or [])
        if allowed_item_types and character_item.item.item_type not in allowed_item_types:
            continue
        slot = int(payload["slot"])
        if slot > 1 and not rune.allow_multiple:
            continue
        final_payloads.append((rune, str(payload["specification"]), slot, int(payload.get("crafter_level") or 0)))

    unique_runes = list({rune.id: rune for rune, _spec, _slot, _level in final_payloads}.values())

    if experience_cost > int(character_item.owner.current_experience) or money_cost > int(character_item.owner.money):
        return False

    try:
        with transaction.atomic():
            character_item.quality = quality
            character_item.runes.set(unique_runes)
            character_item.description = description
            character_item.is_magic = is_magic
            character_item.magic_effect_summary = magic_effect_summary
            character_item.full_clean()
            character_item.save(update_fields=["quality", "description", "is_magic", "magic_effect_summary"])

            # Replace rune spec records with the new payload
            character_item.rune_specs.all().delete()
            character_item.item_runes.filter(rune__allow_multiple=True).exclude(rune_id__in=base_rune_ids).delete()
            selected_non_multiple_ids = {
                rune.id for rune, _specification, _slot, _crafter_level in final_payloads if not rune.allow_multiple
            }
            protected_non_multiple_ids = selected_non_multiple_ids | base_rune_ids
            character_item.item_runes.filter(rune__allow_multiple=False).exclude(
                rune_id__in=protected_non_multiple_ids
            ).update(is_active=False)
            for rune, specification, slot, crafter_level in final_payloads:
                CharacterItemRuneSpec.objects.create(
                    character_item=character_item,
                    rune=rune,
                    specification=specification,
                    slot=slot,
                )
                apply_rune_to_item(item=character_item, rune=rune, crafter_level=crafter_level)

            _save_magic_modifiers(
                source_model=CharacterItem,
                source_id=character_item.id,
                magic_modifier_payloads=magic_modifier_payloads if is_magic else [],
            )
            if experience_cost or money_cost:
                character = character_item.owner
                character.current_experience = max(0, int(character.current_experience) - experience_cost)
                character.money = max(0, int(character.money) - money_cost)
                character.save(update_fields=["current_experience", "money"])
    except (
        ValidationError,
        ValueError,
        Skill.DoesNotExist,
        SkillCategory.DoesNotExist,
        Specialization.DoesNotExist,
        Item.DoesNotExist,
    ) as exc:
        logging.getLogger(__name__).exception(
            "apply_character_item_modifications failed for CharacterItem pk=%s: %s",
            character_item.pk,
            exc,
        )
        return False

    return True


def create_custom_shop_item(post_data) -> bool:
    """Create one custom base item plus optional detail records."""
    name = (post_data.get("name") or "").strip()
    if not name:
        return False

    price = _read_int(post_data, "price", 0, minimum=0)
    item_type = (post_data.get("item_type") or Item.ItemType.MISC).strip()
    description = (post_data.get("description") or "").strip()
    stackable = bool(post_data.get("stackable"))
    is_magic = bool(post_data.get("is_magic")) or item_type == Item.ItemType.MAGIC_ITEM
    default_quality = _read_quality(post_data, "default_quality", ItemEngine.normalize_quality(None))
    weight = _read_int(post_data, "weight", 0, minimum=0)
    size_class = str(post_data.get("size_class") or "M")
    is_consumable = item_type == Item.ItemType.CONSUM
    selected_runes = list(_read_runes(post_data))
    magic_modifier_payloads = _read_magic_modifier_payloads(post_data) if is_magic else []

    if item_type in (
        Item.ItemType.ARMOR,
        Item.ItemType.WEAPON,
        Item.ItemType.SHIELD,
        Item.ItemType.CLOTHING,
    ):
        stackable = False
    if is_magic:
        stackable = False
    if not stackable:
        is_consumable = False

    item = Item()
    try:
        with transaction.atomic():
            item = Item(
                name=name,
                price=max(0, price),
                item_type=item_type,
                description=description,
                stackable=stackable,
                is_consumable=is_consumable,
                is_magic=is_magic,
                default_quality=default_quality,
                weight=weight,
                size_class=size_class,
            )
            item.full_clean()
            item.save()
            if selected_runes:
                item.runes.set(selected_runes)

            if item.item_type == Item.ItemType.ARMOR:
                armor_mode = (post_data.get("armor_mode") or "total").strip()
                armor_encumbrance = _read_int(post_data, "armor_encumbrance", 0, minimum=0)
                armor_min_st = _read_int(post_data, "armor_min_st", 1, minimum=1)
                if armor_mode == "zones":
                    armor_stats = ArmorStats(
                        item=item,
                        rs_total=0,
                        rs_head=_read_int(post_data, "armor_rs_head", 0, minimum=0),
                        rs_torso=_read_int(post_data, "armor_rs_torso", 0, minimum=0),
                        rs_arm_left=_read_int(post_data, "armor_rs_arm_left", 0, minimum=0),
                        rs_arm_right=_read_int(post_data, "armor_rs_arm_right", 0, minimum=0),
                        rs_leg_left=_read_int(post_data, "armor_rs_leg_left", 0, minimum=0),
                        rs_leg_right=_read_int(post_data, "armor_rs_leg_right", 0, minimum=0),
                        encumbrance=armor_encumbrance,
                        min_st=armor_min_st,
                    )
                else:
                    armor_stats = ArmorStats(
                        item=item,
                        rs_total=_read_int(post_data, "armor_rs_total", 0, minimum=0),
                        rs_head=0,
                        rs_torso=0,
                        rs_arm_left=0,
                        rs_arm_right=0,
                        rs_leg_left=0,
                        rs_leg_right=0,
                        encumbrance=armor_encumbrance,
                        min_st=armor_min_st,
                    )
                armor_stats.full_clean()
                armor_stats.save()
            elif item.item_type == Item.ItemType.WEAPON:
                min_st = _read_int(post_data, "weapon_min_st", 1, minimum=1)
                damage_type = str(post_data.get("weapon_damage_type") or DEADLY)
                wield_mode = str(post_data.get("weapon_wield_mode") or "1h")
                h2_enabled = wield_mode == "vh"
                damage_source_id = _read_int(post_data, "weapon_damage_source", 0, minimum=1)
                damage_source = DamageSource.objects.get(pk=damage_source_id)
                weapon_stats = WeaponStats(
                    item=item,
                    min_st=min_st,
                    damage_source=damage_source,
                    damage_dice_amount=_read_int(post_data, "weapon_damage_dice_amount", 1, minimum=1),
                    damage_dice_faces=_read_int(post_data, "weapon_damage_dice_faces", 10, minimum=2),
                    damage_flat_bonus=abs(_read_int(post_data, "weapon_damage_flat_bonus", 0)),
                    damage_flat_operator=_read_damage_operator(post_data, "weapon_damage_flat_operator", ""),
                    damage_type=damage_type,
                    wield_mode=wield_mode,
                    h2_dice_amount=_read_int(post_data, "weapon_h2_dice_amount", 0, minimum=1) if h2_enabled else None,
                    h2_dice_faces=_read_int(post_data, "weapon_h2_dice_faces", 0, minimum=2) if h2_enabled else None,
                    h2_flat_bonus=abs(_read_int(post_data, "weapon_h2_flat_bonus", 0)) if h2_enabled else None,
                    h2_flat_operator=_read_damage_operator(post_data, "weapon_h2_flat_operator", "") if h2_enabled else "",
                )
                weapon_stats.full_clean()
                weapon_stats.save()
            elif item.item_type == Item.ItemType.SHIELD:
                shield_stats = ShieldStats(
                    item=item,
                    rs=_read_int(post_data, "shield_rs", 0, minimum=0),
                    encumbrance=_read_int(post_data, "shield_encumbrance", 0, minimum=0),
                    min_st=_read_int(post_data, "shield_min_st", 1, minimum=1),
                )
                shield_stats.full_clean()
                shield_stats.save()
            if item.is_magic_effective:
                magic_item_stats = MagicItemStats(
                    item=item,
                    effect_summary=(post_data.get("magic_effect_summary") or "").strip(),
                )
                magic_item_stats.full_clean()
                magic_item_stats.save()
                _save_magic_modifiers(
                    source_model=Item,
                    source_id=item.id,
                    magic_modifier_payloads=magic_modifier_payloads,
                )
    except (
        ValidationError,
        ValueError,
        DamageSource.DoesNotExist,
        Skill.DoesNotExist,
        SkillCategory.DoesNotExist,
        Specialization.DoesNotExist,
        Item.DoesNotExist,
    ):
        if item.pk:
            item.delete()
        return False

    return True


def buy_shop_cart(character: Character, payload: dict[str, object]) -> tuple[dict[str, object], int]:
    """Buy all cart entries atomically and return JSON payload plus status code."""
    cart_items = payload.get("items") or []
    discount = payload.get("discount") or 0
    try:
        discount_percent = max(-100, min(100, int(discount)))
    except (TypeError, ValueError):
        discount_percent = 0

    if not isinstance(cart_items, list) or not cart_items:
        return {"ok": False, "error": "empty_cart"}, 400

    normalized: list[tuple[Item, int, str]] = []
    subtotal = 0
    for entry in cart_items:
        try:
            item_id = int(entry.get("id"))
            qty = int(entry.get("qty"))
        except (TypeError, ValueError, AttributeError):
            return {"ok": False, "error": "invalid_item"}, 400
        if qty < 1:
            return {"ok": False, "error": "invalid_qty"}, 400

        item = Item.objects.filter(pk=item_id).first()
        if item is None:
            return {"ok": False, "error": "item_not_found"}, 400
        quality = ItemEngine.normalize_quality(str(entry.get("quality") or item.default_quality))
        if not item.stackable and qty != 1:
            return {"ok": False, "error": "non_stackable_qty"}, 400
        normalized.append((item, qty, quality))
        subtotal += ItemEngine.price_for_item_and_quality(item, quality) * qty

    final_price = max(0, round(subtotal * (100 - discount_percent) / 100))
    if final_price > character.money:
        return {"ok": False, "error": "insufficient_funds"}, 200

    with transaction.atomic():
        character.money -= final_price
        character.save(update_fields=["money"])
        for item, qty, quality in normalized:
            if item.stackable:
                existing = CharacterItem.objects.filter(owner=character, item=item, quality=quality).first()
                if existing:
                    existing.amount += qty
                    existing.full_clean()
                    existing.save(update_fields=["amount"])
                else:
                    created = CharacterItem(owner=character, item=item, amount=qty, equipped=False, quality=quality)
                    created.full_clean()
                    created.save()
                    for rune in item.runes.all():
                        apply_rune_to_item(item=created, rune=rune, crafter_level=0)
            else:
                for _index in range(qty):
                    created = CharacterItem(owner=character, item=item, amount=1, equipped=False, quality=quality)
                    created.full_clean()
                    created.save()
                    for rune in item.runes.all():
                        apply_rune_to_item(item=created, rune=rune, crafter_level=0)

    return {"ok": True, "new_money": character.money, "spent": final_price}, 200
