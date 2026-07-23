"""Shop helpers for custom item creation and cart purchases."""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from charsheet.constants import (
    DEADLY,
    MELEE_MANEUVERS,
    RULE_FLAG_TARGET_KIND,
    RULE_FLAG_CHOICES,
    TWO_HANDED,
    VERSATILE,
    WEAPON_DAMAGE,
    WEAPON_DAMAGE_DICE,
    WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
    WEAPON_MANEUVER_ATTRIBUTE_ST,
    WEAPON_MANEUVER_DAMAGE,
    WEAPON_MASTERY_BONUS,
    WEAPON_MASTERY_EFFECT_DESCRIPTION,
)
from charsheet.engine import ItemEngine
from charsheet.magic_effects import TEXT_TARGET_KIND, pack_magic_effect_summary
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
    WeaponType,
    WeaponStats,
)
from charsheet.item_transfers import has_item_permission, item_is_pending, record_item_destruction
from charsheet.models import ItemPermissionGrant


def _read_weapon_type(raw_value) -> WeaponType | None:
    slug = str(raw_value or "").strip().lower()
    if not slug:
        return None
    return WeaponType.objects.filter(slug=slug).first()


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
    raw_quality = post_data.get(name, default) or default
    return ItemEngine.normalize_quality(raw_quality)


def _read_damage_operator(post_data, name: str, default: str = "") -> str:
    """Read one normalized damage operator from POST-like data."""
    raw_value = str(post_data.get(name, default) or default).strip()
    valid_values = {value for value, _label in WeaponStats.DamageOperator.choices}
    return raw_value if raw_value in valid_values else default


def _read_weapon_maneuver_attribute(post_data, name: str, default: str = WEAPON_MANEUVER_ATTRIBUTE_ST) -> str:
    """Read one normalized maneuver-attribute mode from POST-like data."""
    raw_value = str(post_data.get(name, default) or default).strip()
    valid_values = {value for value, _label in WEAPON_MANEUVER_ATTRIBUTE_CHOICES}
    return raw_value if raw_value in valid_values else default


def _read_decimal(post_data, name: str, default: Decimal | int | str = 0) -> Decimal:
    """Read one decimal value from POST-like data."""
    raw_value = str(post_data.get(name, default) or default).strip()
    try:
        value = Decimal(raw_value)
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal(default)
    return max(Decimal("0"), value)


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


def _read_skill_ids(post_data, name: str) -> list[int]:
    """Read one multi-value skill field and return deduplicated integer ids."""
    skill_ids: list[int] = []
    for raw_value in _read_many_values(post_data, name):
        try:
            skill_id = int(raw_value)
        except (TypeError, ValueError):
            continue
        if skill_id > 0 and skill_id not in skill_ids:
            skill_ids.append(skill_id)
    return skill_ids


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
        "display_order": int(row_data.get("display_order") or 0),
        "target_slug": "",
        "target_skill": None,
        "target_skill_category": None,
        "target_item": None,
        "target_specialization": None,
    }

    rule_flag_keys = {value for value, _label in RULE_FLAG_CHOICES}

    if target_kind == TEXT_TARGET_KIND:
        if not payload["effect_description"]:
            return None
        payload["value"] = 0
    elif target_kind == RULE_FLAG_TARGET_KIND:
        target_slug = str(row_data.get("target_rule_flag") or "").strip()
        if target_slug not in rule_flag_keys:
            return None
        payload["target_kind"] = Modifier.TargetKind.STAT
        payload["target_slug"] = target_slug
        payload["value"] = 1
    elif target_kind == Modifier.TargetKind.ATTRIBUTE:
        target_slug = str(row_data.get("target_attribute") or "").strip()
        if not target_slug:
            return None
        payload["target_slug"] = target_slug
    elif target_kind == Modifier.TargetKind.STAT:
        target_slug = str(row_data.get("target_stat") or "").strip()
        if not target_slug:
            return None
        payload["target_slug"] = target_slug
    elif target_kind == "weapon_maneuver":
        payload["target_kind"] = Modifier.TargetKind.STAT
        payload["target_slug"] = MELEE_MANEUVERS
    elif target_kind == "weapon_damage":
        payload["target_kind"] = Modifier.TargetKind.STAT
        payload["target_slug"] = WEAPON_DAMAGE
    elif target_kind == "weapon_damage_dice":
        payload["target_kind"] = Modifier.TargetKind.STAT
        payload["target_slug"] = WEAPON_DAMAGE_DICE
    elif target_kind == WEAPON_MANEUVER_DAMAGE:
        payload["target_kind"] = WEAPON_MANEUVER_DAMAGE
    elif target_kind == WEAPON_MASTERY_BONUS:
        payload["target_kind"] = WEAPON_MASTERY_BONUS
        payload["effect_description"] = payload["effect_description"] or WEAPON_MASTERY_EFFECT_DESCRIPTION
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
            "target_rule_flag": post_data.get("magic_modifier_target_rule_flag"),
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
    for index, entry in enumerate(decoded_payloads):
        if not isinstance(entry, dict):
            raise ValidationError({"magic_modifier_payloads": "Ungültige Magie-Effekte."})
        entry = dict(entry)
        entry["display_order"] = index
        payload = _build_magic_modifier_payload(
            str(entry.get("target_kind") or "").strip(),
            entry.get("value", 0),
            entry,
        )
        if payload is not None:
            if payload.get("target_kind") in {WEAPON_MANEUVER_DAMAGE, WEAPON_MASTERY_BONUS}:
                value = int(payload.get("value", 0) or 0)
                effect_description = str(payload.get("effect_description") or "").strip()
                payloads.extend(
                    [
                        {
                            "target_kind": Modifier.TargetKind.STAT,
                            "value": value,
                            "effect_description": effect_description,
                            "display_order": index,
                            "target_slug": MELEE_MANEUVERS,
            "target_skill": None,
                            "target_skill_category": None,
                            "target_item": None,
                            "target_specialization": None,
                        },
                        {
                            "target_kind": Modifier.TargetKind.STAT,
                            "value": value,
                            "effect_description": effect_description,
                            "display_order": index,
                            "target_slug": WEAPON_DAMAGE,
                            "target_skill": None,
                            "target_skill_category": None,
                            "target_item": None,
                            "target_specialization": None,
                        },
                    ]
                )
            else:
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
                crafter_level = min(10, max(0, int(entry.get("crafter_level") or 0)))
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
        if str(magic_modifier_payload.get("target_kind") or "") == TEXT_TARGET_KIND:
            continue
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
            display_order=int(magic_modifier_payload.get("display_order") or 0),
            mode=Modifier.Mode.FLAT,
            value=int(magic_modifier_payload["value"]),
        )
        modifier.full_clean()
        modifier.save()


def _normalize_redundant_character_item_overrides(character_item: CharacterItem) -> None:
    """Keep concrete overrides sparse by clearing values equal to base data."""
    item = character_item.item
    comparisons = {
        "name_override": item.name,
        "price_override": item.price,
        "weight_override": item.weight,
        "size_class_override": item.size_class,
        "description": item.description or "",
    }
    weapon = getattr(item, "weaponstats", None)
    if weapon is not None:
        comparisons.update(
            {
                "weapon_type_override": weapon.weapon_type,
                "weapon_min_st_override": weapon.min_st,
                "weapon_maneuver_attribute_override": weapon.maneuver_attribute_mode,
                "weapon_damage_source_override": weapon.damage_source,
                "weapon_damage_dice_amount_override": weapon.damage_dice_amount,
                "weapon_damage_dice_faces_override": weapon.damage_dice_faces,
                "weapon_damage_flat_bonus_override": weapon.damage_flat_bonus,
                "weapon_damage_flat_operator_override": weapon.damage_flat_operator,
                "weapon_damage_type_override": weapon.damage_type,
                "weapon_wield_mode_override": weapon.wield_mode,
                "weapon_h2_dice_amount_override": weapon.h2_dice_amount,
                "weapon_h2_dice_faces_override": weapon.h2_dice_faces,
                "weapon_h2_flat_bonus_override": weapon.h2_flat_bonus,
                "weapon_h2_flat_operator_override": weapon.h2_flat_operator,
                "weapon_h2_damage_type_override": weapon.h2_damage_type,
            }
        )
    armor = getattr(item, "armorstats", None)
    if armor is not None:
        comparisons.update(
            {
                "armor_rs_head_override": armor.rs_head,
                "armor_rs_torso_override": armor.rs_torso,
                "armor_rs_arm_left_override": armor.rs_arm_left,
                "armor_rs_arm_right_override": armor.rs_arm_right,
                "armor_rs_leg_left_override": armor.rs_leg_left,
                "armor_rs_leg_right_override": armor.rs_leg_right,
                "armor_rs_total_override": armor.rs_total,
                "armor_encumbrance_override": armor.encumbrance,
                "armor_min_st_override": armor.min_st,
            }
        )
    shield = getattr(item, "shieldstats", None)
    if shield is not None:
        comparisons.update(
            {
                "shield_rs_override": shield.rs,
                "shield_encumbrance_override": shield.encumbrance,
                "shield_min_st_override": shield.min_st,
            }
        )
    for field_name, base_value in comparisons.items():
        current = getattr(character_item, field_name)
        current_id = getattr(current, "pk", current)
        base_id = getattr(base_value, "pk", base_value)
        if current_id == base_id:
            model_field = character_item._meta.get_field(field_name)
            setattr(character_item, field_name, "" if getattr(model_field, "empty_strings_allowed", False) else None)


def apply_character_item_modifications(
    character_item: CharacterItem,
    post_data,
    files_data=None,
    *,
    charge_character_costs: bool = True,
    allow_catalog_flags: bool = True,
) -> bool:
    """Persist one owned-item modification including quality, runes, magic, and costs."""
    item = character_item.item
    name = str(post_data.get("name") or "").strip() or item.name
    price = _read_int(post_data, "price", item.price, minimum=0)
    weight = _read_decimal(post_data, "weight", item.weight)
    size_class = str(post_data.get("size_class") or item.size_class).strip() or item.size_class
    quality = _read_quality(post_data, "quality", character_item.quality or character_item.item.default_quality)
    experience_cost = _read_int(post_data, "experience_cost", 0, minimum=0)
    money_cost = _read_int(post_data, "money_cost", 0, minimum=0)
    not_buyable = bool(post_data.get("not_buyable"))
    not_sellable = bool(post_data.get("not_sellable"))
    image = None if files_data is None else files_data.get("image")
    remove_image = bool(post_data.get("remove_image"))
    rune_payloads = _read_rune_payloads(post_data)
    description = str(post_data.get("description") or "").strip()
    visible_magic_effect_summary = str(post_data.get("magic_effect_summary") or "").strip()
    magic_modifier_payloads = _read_magic_modifier_payloads(post_data)
    text_effect_descriptions = [
        {
            "effect_description": str(payload.get("effect_description") or "").strip(),
            "display_order": int(payload.get("display_order") or 0),
        }
        for payload in magic_modifier_payloads
        if str(payload.get("target_kind") or "") == TEXT_TARGET_KIND
        and str(payload.get("effect_description") or "").strip()
    ]
    magic_effect_summary = pack_magic_effect_summary(visible_magic_effect_summary, text_effect_descriptions)
    is_magic = bool(magic_modifier_payloads) or bool(visible_magic_effect_summary) or bool(text_effect_descriptions)
    weapon_stats = getattr(item, "weaponstats", None)
    armor_stats = getattr(item, "armorstats", None)
    shield_stats = getattr(item, "shieldstats", None)
    weapon_damage_source = None
    if weapon_stats is not None:
        damage_source_id = _read_int(post_data, "weapon_damage_source", getattr(weapon_stats.damage_source, "id", 0), minimum=0)
        if damage_source_id > 0:
            weapon_damage_source = DamageSource.objects.get(pk=damage_source_id)

    # Deduplicate (rune_id, slot) pairs
    seen_slots: set[tuple[int, int]] = set()
    filtered_payloads: list[dict[str, object]] = []
    for payload in rune_payloads:
        rune_id = int(payload["rune_id"])
        slot = int(payload["slot"])
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

    if len(final_payloads) > 5:
        return False

    unique_runes = list({rune.id: rune for rune, _spec, _slot, _level in final_payloads}.values())

    if not charge_character_costs:
        experience_cost = 0
        money_cost = 0
    if charge_character_costs and (
        character_item.owner is None
        or experience_cost > int(character_item.owner.current_experience)
        or money_cost > int(character_item.owner.money)
    ):
        return False

    try:
        with transaction.atomic():
            if allow_catalog_flags:
                item.not_buyable = not_buyable
                item.not_sellable = not_sellable
                item.full_clean()
                item.save(update_fields=["not_buyable", "not_sellable"])
            if remove_image and character_item.image_override:
                character_item.image_override.delete(save=False)
                character_item.image_override = None
                character_item.full_clean()
                character_item.save(update_fields=["image_override"])
            if image:
                character_item.image_override = image
                character_item.full_clean()
                character_item.save(update_fields=["image_override"])
            character_item.name_override = name
            character_item.price_override = price
            character_item.weight_override = weight
            character_item.size_class_override = size_class
            character_item.quality_id = quality
            character_item.runes.set(unique_runes)
            character_item.description = description
            character_item.is_magic = is_magic
            character_item.magic_effect_summary = magic_effect_summary
            if weapon_stats is not None:
                character_item.weapon_type_override = (
                    _read_weapon_type(post_data.get("weapon_type")) or getattr(weapon_stats, "weapon_type", None)
                )
                character_item.weapon_min_st_override = _read_int(post_data, "weapon_min_st", weapon_stats.min_st, minimum=1)
                character_item.weapon_maneuver_attribute_override = _read_weapon_maneuver_attribute(
                    post_data,
                    "weapon_maneuver_attribute",
                    getattr(weapon_stats, "maneuver_attribute_mode", WEAPON_MANEUVER_ATTRIBUTE_ST),
                )
                character_item.weapon_damage_source_override = weapon_damage_source
                character_item.weapon_damage_dice_amount_override = _read_int(
                    post_data, "weapon_damage_dice_amount", weapon_stats.damage_dice_amount, minimum=1
                )
                character_item.weapon_damage_dice_faces_override = _read_int(
                    post_data, "weapon_damage_dice_faces", weapon_stats.damage_dice_faces, minimum=2
                )
                character_item.weapon_damage_flat_bonus_override = _read_int(
                    post_data, "weapon_damage_flat_bonus", weapon_stats.damage_flat_bonus
                )
                character_item.weapon_damage_flat_operator_override = _read_damage_operator(
                    post_data, "weapon_damage_flat_operator", weapon_stats.damage_flat_operator
                )
                character_item.weapon_damage_type_override = str(
                    post_data.get("weapon_damage_type") or weapon_stats.damage_type
                ).strip() or weapon_stats.damage_type
                character_item.weapon_wield_mode_override = str(
                    post_data.get("weapon_wield_mode") or weapon_stats.wield_mode
                ).strip() or weapon_stats.wield_mode
                character_item.weapon_h2_dice_amount_override = _read_int(
                    post_data, "weapon_h2_dice_amount", weapon_stats.h2_dice_amount or 1, minimum=1
                )
                character_item.weapon_h2_dice_faces_override = _read_int(
                    post_data, "weapon_h2_dice_faces", weapon_stats.h2_dice_faces or 2, minimum=2
                )
                character_item.weapon_h2_flat_bonus_override = _read_int(
                    post_data, "weapon_h2_flat_bonus", weapon_stats.h2_flat_bonus or 0
                )
                character_item.weapon_h2_flat_operator_override = _read_damage_operator(
                    post_data, "weapon_h2_flat_operator", weapon_stats.h2_flat_operator
                )
                character_item.weapon_h2_damage_type_override = str(
                    post_data.get("weapon_h2_damage_type") or getattr(weapon_stats, "h2_damage_type", weapon_stats.damage_type)
                ).strip() or getattr(weapon_stats, "h2_damage_type", weapon_stats.damage_type)
            if armor_stats is not None:
                character_item.armor_rs_total_override = _read_int(post_data, "armor_rs_total", armor_stats.rs_total, minimum=0)
                character_item.armor_rs_head_override = _read_int(post_data, "armor_rs_head", armor_stats.rs_head, minimum=0)
                character_item.armor_rs_torso_override = _read_int(post_data, "armor_rs_torso", armor_stats.rs_torso, minimum=0)
                character_item.armor_rs_arm_left_override = _read_int(
                    post_data, "armor_rs_arm_left", armor_stats.rs_arm_left, minimum=0
                )
                character_item.armor_rs_arm_right_override = _read_int(
                    post_data, "armor_rs_arm_right", armor_stats.rs_arm_right, minimum=0
                )
                character_item.armor_rs_leg_left_override = _read_int(
                    post_data, "armor_rs_leg_left", armor_stats.rs_leg_left, minimum=0
                )
                character_item.armor_rs_leg_right_override = _read_int(
                    post_data, "armor_rs_leg_right", armor_stats.rs_leg_right, minimum=0
                )
                character_item.armor_encumbrance_override = _read_int(
                    post_data, "armor_encumbrance", armor_stats.encumbrance, minimum=0
                )
                character_item.armor_min_st_override = _read_int(post_data, "armor_min_st", armor_stats.min_st, minimum=1)
            if shield_stats is not None:
                character_item.shield_rs_override = _read_int(post_data, "shield_rs", shield_stats.rs, minimum=0)
                character_item.shield_encumbrance_override = _read_int(
                    post_data, "shield_encumbrance", shield_stats.encumbrance, minimum=0
                )
                character_item.shield_min_st_override = _read_int(post_data, "shield_min_st", shield_stats.min_st, minimum=1)
            _normalize_redundant_character_item_overrides(character_item)
            character_item.full_clean()
            character_item.save()

            # Replace rune spec records with the new payload
            character_item.rune_specs.all().delete()
            character_item.item_runes.filter(rune__allow_multiple=True).delete()
            character_item.item_runes.filter(rune__allow_multiple=False).update(is_active=False)
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
            if charge_character_costs and (experience_cost or money_cost):
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


def create_custom_shop_item(post_data, files_data=None, *, catalog_group=None):
    """Create one custom base item plus optional detail records."""
    name = (post_data.get("name") or "").strip()
    if not name:
        return False

    price = _read_int(post_data, "price", 0, minimum=0)
    item_type = (post_data.get("item_type") or Item.ItemType.MISC).strip()
    description = (post_data.get("description") or "").strip()
    stackable = bool(post_data.get("stackable"))
    is_magic = bool(post_data.get("is_magic")) or item_type == Item.ItemType.MAGIC_ITEM
    not_buyable = bool(post_data.get("not_buyable"))
    not_sellable = bool(post_data.get("not_sellable"))
    default_quality = _read_quality(post_data, "default_quality", ItemEngine.normalize_quality(None))
    weight = _read_decimal(post_data, "weight", 0)
    size_class = str(post_data.get("size_class") or "M")
    is_consumable = item_type == Item.ItemType.CONSUM
    image = None if files_data is None else files_data.get("image")
    rune_payloads = _read_rune_payloads(post_data)
    selected_rune_ids = sorted({int(payload["rune_id"]) for payload in rune_payloads if int(payload["rune_id"]) > 0})
    selected_runes = list(Rune.objects.filter(pk__in=selected_rune_ids))
    selected_weapon_skill_ids = _read_skill_ids(post_data, "weapon_skills")
    magic_modifier_payloads = _read_magic_modifier_payloads(post_data) if is_magic else []
    text_effect_descriptions = [
        {
            "effect_description": str(payload.get("effect_description") or "").strip(),
            "display_order": int(payload.get("display_order") or 0),
        }
        for payload in magic_modifier_payloads
        if str(payload.get("target_kind") or "") == TEXT_TARGET_KIND
        and str(payload.get("effect_description") or "").strip()
    ]
    magic_effect_summary = pack_magic_effect_summary(
        str(post_data.get("magic_effect_summary") or "").strip(),
        text_effect_descriptions,
    )

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
                not_buyable=not_buyable,
                not_sellable=not_sellable,
                default_quality_id=default_quality,
                weight=weight,
                size_class=size_class,
                image=image,
                catalog_group=catalog_group,
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
                h2_damage_type = str(post_data.get("weapon_h2_damage_type") or damage_type)
                wield_mode = str(post_data.get("weapon_wield_mode") or "1h")
                h2_enabled = wield_mode in {TWO_HANDED, VERSATILE}
                damage_source_id = _read_int(post_data, "weapon_damage_source", 0, minimum=1)
                damage_source = DamageSource.objects.get(pk=damage_source_id)
                weapon_skills = list(Skill.objects.filter(pk__in=selected_weapon_skill_ids).order_by("name"))
                if len(weapon_skills) != len(selected_weapon_skill_ids):
                    raise ValidationError({"weapon_skills": "Mindestens eine ausgewaehlte Fertigkeit ist ungueltig."})
                weapon_stats = WeaponStats(
                    item=item,
                    min_st=min_st,
                    weapon_type=_read_weapon_type(post_data.get("weapon_type")),
                    maneuver_attribute_mode=_read_weapon_maneuver_attribute(post_data, "weapon_maneuver_attribute"),
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
                    h2_damage_type=h2_damage_type if h2_enabled else damage_type,
                )
                weapon_stats.full_clean()
                weapon_stats.save()
                if weapon_skills:
                    weapon_stats.skills.set(weapon_skills)
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
                    effect_summary=magic_effect_summary,
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

    return item


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

        item = Item.objects.filter(pk=item_id, catalog_group__isnull=True).first()
        if item is None:
            return {"ok": False, "error": "item_not_found"}, 400
        if item.not_buyable:
            return {"ok": False, "error": "item_not_buyable"}, 400
        quality = ItemEngine.normalize_quality(entry.get("quality") or item.default_quality)
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
                existing = CharacterItem.objects.filter(owner=character, original_owner_character=character, item=item, quality_id=quality).exclude(transfers__status="pending").first()
                if existing:
                    existing.amount += qty
                    existing.full_clean()
                    existing.save(update_fields=["amount"])
                else:
                    created = CharacterItem(owner=character, original_owner_character=character, item=item, amount=qty, equipped=False, quality_id=quality)
                    created.full_clean()
                    created.save()
                    for rune in item.runes.all():
                        apply_rune_to_item(item=created, rune=rune, crafter_level=0)
            else:
                for _index in range(qty):
                    created = CharacterItem(owner=character, original_owner_character=character, item=item, amount=1, equipped=False, quality_id=quality)
                    created.full_clean()
                    created.save()
                    for rune in item.runes.all():
                        apply_rune_to_item(item=created, rune=rune, crafter_level=0)

    return {"ok": True, "new_money": character.money, "spent": final_price}, 200


@transaction.atomic
def sell_shop_cart(character: Character, payload: dict[str, object]) -> tuple[dict[str, object], int]:
    """Sell cart entries atomically and return JSON payload plus status code."""
    cart_items = payload.get("items") or []
    if not isinstance(cart_items, list) or not cart_items:
        return {"ok": False, "error": "empty_cart"}, 400

    requested_quantities: dict[int, int] = {}
    for entry in cart_items:
        try:
            character_item_id = int(entry.get("character_item_id"))
            qty = int(entry.get("qty"))
        except (TypeError, ValueError, AttributeError):
            return {"ok": False, "error": "invalid_item"}, 400
        if character_item_id <= 0 or qty < 1:
            return {"ok": False, "error": "invalid_qty"}, 400
        requested_quantities[character_item_id] = requested_quantities.get(character_item_id, 0) + qty

    character_items = {
        item.id: item
        for item in CharacterItem.objects.select_for_update().select_related("item", "owner", "original_owner_character").filter(
            owner=character,
            pk__in=requested_quantities.keys(),
        )
    }
    if len(character_items) != len(requested_quantities):
        return {"ok": False, "error": "item_not_found"}, 400

    normalized: list[tuple[CharacterItem, int, int]] = []
    payout = 0
    for character_item_id, qty in requested_quantities.items():
        character_item = character_items[character_item_id]
        if character_item.item.not_sellable:
            return {"ok": False, "error": "item_not_sellable"}, 400
        if item_is_pending(character_item):
            return {"ok": False, "error": "item_pending"}, 409
        if not has_item_permission(character_item, ItemPermissionGrant.Permission.SELL, character):
            return {"ok": False, "error": "sell_permission_required"}, 403
        if qty > character_item.amount:
            return {"ok": False, "error": "invalid_qty"}, 400
        unit_price = ItemEngine(character_item).get_price()
        normalized.append((character_item, qty, unit_price))
        payout += unit_price * qty

    with transaction.atomic():
        character.money += payout
        character.save(update_fields=["money"])
        for character_item, qty, _unit_price in normalized:
            if qty >= character_item.amount:
                record_item_destruction(character_item, character, "sell")
                character_item.delete()
                continue
            character_item.amount -= qty
            character_item.full_clean()
            character_item.save(update_fields=["amount"])

    return {"ok": True, "new_money": character.money, "earned": payout}, 200


@transaction.atomic
def trade_shop_cart(character: Character, payload: dict[str, object]) -> tuple[dict[str, object], int]:
    """Process one mixed buy/sell cart atomically and return JSON payload plus status code."""
    buy_items = payload.get("buy_items") or []
    sell_items = payload.get("sell_items") or []
    discount = payload.get("discount") or 0

    if not isinstance(buy_items, list) or not isinstance(sell_items, list) or (not buy_items and not sell_items):
        return {"ok": False, "error": "empty_cart"}, 400

    try:
        discount_percent = max(-100, min(100, int(discount)))
    except (TypeError, ValueError):
        discount_percent = 0

    normalized_buys: list[tuple[Item, int, str]] = []
    buy_subtotal = 0
    for entry in buy_items:
        try:
            item_id = int(entry.get("id"))
            qty = int(entry.get("qty"))
        except (TypeError, ValueError, AttributeError):
            return {"ok": False, "error": "invalid_item"}, 400
        if qty < 1:
            return {"ok": False, "error": "invalid_qty"}, 400

        item = Item.objects.filter(pk=item_id, catalog_group__isnull=True).first()
        if item is None:
            return {"ok": False, "error": "item_not_found"}, 400
        if item.not_buyable:
            return {"ok": False, "error": "item_not_buyable"}, 400
        quality = ItemEngine.normalize_quality(entry.get("quality") or item.default_quality)
        if not item.stackable and qty != 1:
            return {"ok": False, "error": "non_stackable_qty"}, 400
        normalized_buys.append((item, qty, quality))
        buy_subtotal += ItemEngine.price_for_item_and_quality(item, quality) * qty

    requested_sell_quantities: dict[int, int] = {}
    for entry in sell_items:
        try:
            character_item_id = int(entry.get("character_item_id"))
            qty = int(entry.get("qty"))
        except (TypeError, ValueError, AttributeError):
            return {"ok": False, "error": "invalid_item"}, 400
        if character_item_id <= 0 or qty < 1:
            return {"ok": False, "error": "invalid_qty"}, 400
        requested_sell_quantities[character_item_id] = requested_sell_quantities.get(character_item_id, 0) + qty

    character_items = {
        item.id: item
        for item in CharacterItem.objects.select_for_update().select_related("item", "owner", "original_owner_character").filter(
            owner=character,
            pk__in=requested_sell_quantities.keys(),
        )
    }
    if len(character_items) != len(requested_sell_quantities):
        return {"ok": False, "error": "item_not_found"}, 400

    normalized_sells: list[tuple[CharacterItem, int, int]] = []
    sell_total = 0
    for character_item_id, qty in requested_sell_quantities.items():
        character_item = character_items[character_item_id]
        if character_item.item.not_sellable:
            return {"ok": False, "error": "item_not_sellable"}, 400
        if item_is_pending(character_item):
            return {"ok": False, "error": "item_pending"}, 409
        if not has_item_permission(character_item, ItemPermissionGrant.Permission.SELL, character):
            return {"ok": False, "error": "sell_permission_required"}, 403
        if qty > character_item.amount:
            return {"ok": False, "error": "invalid_qty"}, 400
        unit_price = ItemEngine(character_item).get_price()
        normalized_sells.append((character_item, qty, unit_price))
        sell_total += unit_price * qty

    buy_total = max(0, round(buy_subtotal * (100 - discount_percent) / 100))
    net_total = buy_total - sell_total
    if net_total > character.money:
        return {"ok": False, "error": "insufficient_funds"}, 200

    with transaction.atomic():
        character.money = int(character.money) - buy_total + sell_total
        character.save(update_fields=["money"])

        for character_item, qty, _unit_price in normalized_sells:
            if qty >= character_item.amount:
                record_item_destruction(character_item, character, "trade_sell")
                character_item.delete()
            else:
                character_item.amount -= qty
                character_item.full_clean()
                character_item.save(update_fields=["amount"])

        for item, qty, quality in normalized_buys:
            if item.stackable:
                existing = CharacterItem.objects.filter(owner=character, original_owner_character=character, item=item, quality_id=quality).exclude(transfers__status="pending").first()
                if existing:
                    existing.amount += qty
                    existing.full_clean()
                    existing.save(update_fields=["amount"])
                else:
                    created = CharacterItem(owner=character, original_owner_character=character, item=item, amount=qty, equipped=False, quality_id=quality)
                    created.full_clean()
                    created.save()
                    for rune in item.runes.all():
                        apply_rune_to_item(item=created, rune=rune, crafter_level=0)
            else:
                for _index in range(qty):
                    created = CharacterItem(owner=character, original_owner_character=character, item=item, amount=1, equipped=False, quality_id=quality)
                    created.full_clean()
                    created.save()
                    for rune in item.runes.all():
                        apply_rune_to_item(item=created, rune=rune, crafter_level=0)

    return {
        "ok": True,
        "new_money": character.money,
        "buy_total": buy_total,
        "sell_total": sell_total,
        "net_total": net_total,
    }, 200
