"""Shop helpers for custom item creation and cart purchases."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.constants import DEADLY
from charsheet.engine import ItemEngine
from charsheet.models import ArmorStats, Character, CharacterItem, Item, ShieldStats, WeaponStats


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


def create_custom_shop_item(post_data) -> bool:
    """Create one custom base item plus optional detail records."""
    name = (post_data.get("name") or "").strip()
    if not name:
        return False

    price = _read_int(post_data, "price", 0, minimum=0)
    item_type = (post_data.get("item_type") or Item.ItemType.MISC).strip()
    description = (post_data.get("description") or "").strip()
    stackable = bool(post_data.get("stackable"))
    default_quality = _read_quality(post_data, "default_quality", ItemEngine.normalize_quality(None))
    weight = _read_int(post_data, "weight", 0, minimum=0)
    size_class = str(post_data.get("size_class") or "M")
    is_consumable = item_type == Item.ItemType.CONSUM

    if item_type in (Item.ItemType.ARMOR, Item.ItemType.WEAPON, Item.ItemType.SHIELD):
        stackable = False
    if not stackable:
        is_consumable = False

    item = Item(
        name=name,
        price=max(0, price),
        item_type=item_type,
        description=description,
        stackable=stackable,
        is_consumable=is_consumable,
        default_quality=default_quality,
        weight=weight,
        size_class=size_class,
    )
    try:
        item.full_clean()
        item.save()

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
            h2_enabled = wield_mode in {"2h", "vh"}
            weapon_stats = WeaponStats(
                item=item,
                min_st=min_st,
                damage_dice_amount=_read_int(post_data, "weapon_damage_dice_amount", 1, minimum=1),
                damage_dice_faces=_read_int(post_data, "weapon_damage_dice_faces", 10, minimum=2),
                damage_flat_bonus=_read_int(post_data, "weapon_damage_flat_bonus", 0, minimum=0),
                damage_type=damage_type,
                wield_mode=wield_mode,
                h2_dice_amount=_read_int(post_data, "weapon_h2_dice_amount", 0, minimum=1) if h2_enabled else None,
                h2_dice_faces=_read_int(post_data, "weapon_h2_dice_faces", 0, minimum=2) if h2_enabled else None,
                h2_flat_bonus=_read_int(post_data, "weapon_h2_flat_bonus", 0, minimum=0) if h2_enabled else None,
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
    except (ValidationError, ValueError, DamageSource.DoesNotExist):
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
            else:
                for _index in range(qty):
                    created = CharacterItem(owner=character, item=item, amount=1, equipped=False, quality=quality)
                    created.full_clean()
                    created.save()

    return {"ok": True, "new_money": character.money, "spent": final_price}, 200
