from __future__ import annotations
import json
from itertools import groupby
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import (
    Character,
    CharacterItem,
    CharacterLanguage,
    CharacterTrait,
    Technique,
    Item,
    ArmorStats,
    WeaponStats,
    DamageSource,
)


ATTRIBUTE_ORDER = [
    ("ST", "Stärke (St)"),
    ("KON", "Konstitution (Kon)"),
    ("GE", "Geschick (Ge)"),
    ("WA", "Wahrnehmung (Wa)"),
    ("INT", "Intelligenz (Int)"),
    ("WILL", "Willenskraft (Will)"),
    ("CHA", "Charisma (Cha)"),
]


def _format_modifier(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def _format_thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def character_sheet(request, character_id: int):
    character = get_object_or_404(
        Character.objects.select_related("race", "owner"),
        pk=character_id,
    )

    engine = character.engine

    attributes = engine.attributes()
    attr_mods = {
        short_name: _format_modifier(engine.attribute_modifier(short_name))
        for short_name, _label in ATTRIBUTE_ORDER
    }

    skill_rows: list[dict] = []
    character_skills = (
        character.characterskill_set
        .select_related("skill", "skill__attribute", "skill__category")
        .order_by("skill__name")
    )

    for cs in character_skills:
        breakdown = engine.skill_breakdown(cs.skill.slug)
        if "error" in breakdown:
            continue

        skill_rows.append(
            {
                "name": cs.skill.name,
                "description": cs.skill.description,
                "attribute": cs.skill.attribute.short_name,
                "attribute_mod": _format_modifier(breakdown["attribute_modifier"]),
                "rank": cs.level,
                "misc_mod": _format_modifier(breakdown["modifiers"]),
                "total": breakdown["total"],
            }
        )

    traits_qs = (
        CharacterTrait.objects
        .filter(owner=character)
        .select_related("trait")
        .order_by("trait__trait_type", "trait__name")
    )
    advantages = traits_qs.filter(trait__trait_type=CharacterTrait.trait.field.model.TraitType.ADV) if False else traits_qs.filter(trait__trait_type="advantage")
    disadvantages = traits_qs.filter(trait__trait_type="disadvantage")

    inventory_items = (
        CharacterItem.objects
        .filter(owner=character, equipped=False)
        .select_related("item")
        .order_by("item__name")
    )
    
    weapon_items = CharacterItem.objects.filter(
        owner=character,
        item__item_type="weapon",
        equipped=True,
    ).select_related(
        "item",
        "item__weaponstats",
        "item__weaponstats__damage_source",
    )
    
    weapon_rows: list[dict] = []
    bel_value = engine.get_bel()
    for weapon in weapon_items:
        dmg_slug = weapon.item.weaponstats.damage_source.slug
        dmg_mod = engine.get_dmg_modifier_sum(dmg_slug)
        bel = -bel_value
        with_bel = dmg_mod + bel

        weapon_rows.append({
            "character_item": weapon,
            "item": weapon.item,
            "stats": weapon.item.weaponstats,
            "dmg_mod": _format_modifier(dmg_mod),
            "bel": _format_modifier(bel),
            "with_bel": _format_modifier(with_bel),
        })


    equipped_armor = engine.equipped_armor_items().select_related("item")

    schools = (
        character.schools
        .select_related("school", "school__type")
        .order_by("school__type__name", "school__name")
    )
    school_levels = {entry.school_id: entry.level for entry in schools}
    school_technique_rows: list[dict] = []
    if school_levels:
        techniques = (
            Technique.objects
            .filter(school_id__in=school_levels.keys())
            .select_related("school")
            .order_by("school__name", "level", "name")
        )
        for tech in techniques:
            if tech.level <= school_levels.get(tech.school_id, 0):
                school_technique_rows.append(
                    {
                        "level": tech.level,
                        "school_name": tech.school.name,
                        "technique_name": tech.name,
                        "description": tech.description,
                    }
                )

    current_wound_stage, _current_wound_penalty_stage = engine.current_wound_stage()
    current_wound_penalty = engine.current_wound_penalty_raw()
    current_wound_penalty_display = (
        "-"
        if current_wound_stage == "-"
        else _format_modifier(current_wound_penalty)
    )

    wound_thresholds = engine.wound_thresholds()
    wound_threshold_rows = [
        {"threshold": threshold, "stage": stage, "penalty": penalty}
        for threshold, (stage, penalty) in sorted(wound_thresholds.items())
    ]
    wallet_gold, wallet_silver, wallet_copper = engine.km_to_coins()
    race = character.race
    fly_value = "-"
    if race.can_fly:
        combat_fly = race.combat_fly_speed if race.combat_fly_speed is not None else 0
        march_fly = race.march_fly_speed if race.march_fly_speed is not None else 0
        sprint_fly = race.sprint_fly_speed if race.sprint_fly_speed is not None else 0
        fly_value = f"{combat_fly} | {march_fly} | {sprint_fly}"
    movement_ground = {
        "combat": race.combat_speed,
        "march": race.march_speed,
        "sprint": race.sprint_speed,
        "swim": race.swimming_speed,
        "fly": fly_value,
    }

    language_entries = (
        CharacterLanguage.objects
        .filter(owner=character)
        .select_related("language")
        .order_by("-is_mother_tongue", "language__name")
    )
    language_rows: list[dict] = []
    for entry in language_entries:
        level_count = max(0, min(3, entry.levels))
        language_rows.append(
            {
                "name": entry.language.name,
                "level_1": level_count >= 1,
                "level_2": level_count >= 2,
                "level_3": level_count >= 3,
                "can_write": bool(entry.can_write),
            }
        )

    buyable_items = Item.objects.order_by("item_type", "name")
    grouped_items: dict[str, list[Item]] = {}
    for item_type, items_iter in groupby(buyable_items, key=lambda item: item.item_type):
        grouped_items[item_type] = list(items_iter)

    category_order = [
        ("weapon", "Waffen"),
        ("armor", "Rüstungen"),
        ("misc", "Sonstiges"),
    ]
    shop_item_groups: list[dict] = []
    for item_type, label in category_order:
        items = grouped_items.get(item_type, [])
        if not items:
            continue
        shop_item_groups.append(
            {
                "key": item_type,
                "label": label,
                "items": items,
            }
        )

    context = {
        "character": character,
        "attributes": attributes,
        "attr_mods": attr_mods,
        "skill_rows": skill_rows,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "inventory_items": inventory_items,
        "weapon_rows": weapon_rows,
        "school_technique_rows": school_technique_rows,
        "equipped_armor": equipped_armor,
        "initiative_display": _format_modifier(engine.calculate_initiative()),
        "initiative_with_bel_display": _format_modifier(
            engine.calculate_initiative() - engine.get_bel()
            ),
        "current_wound_stage": current_wound_stage,
        "current_wound_penalty": current_wound_penalty_display,
        "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
        "current_damage_max": max(wound_thresholds.keys()) if wound_thresholds else 0,
        "wound_threshold_rows": wound_threshold_rows,
        "wallet_gold": wallet_gold,
        "wallet_silver": wallet_silver,
        "wallet_copper": wallet_copper,
        "wallet_total_ks": _format_thousands(character.money),
        "movement_ground": movement_ground,
        "language_rows": language_rows,
        "shop_item_groups": shop_item_groups,
        "shop_item_type_choices": category_order,
        "shop_item_form_type_choices": [
            ("misc", "Sonstiges"),
            ("weapon", "Waffen"),
            ("armor", "Rüstungen"),
        ],
        "shop_damage_sources": DamageSource.objects.order_by("name"),
    }

    return render(request, "charsheet/charsheet.html", context)

def sheet(request):
    return render(request, "charsheet/charsheet.html")

@require_POST
def toggle_equip(request, pk):
    ci = get_object_or_404(
        CharacterItem.objects.select_related("item"),
        pk=pk,
    )

    if ci.item.item_type not in ("armor", "weapon"):
        return redirect("character_sheet", character_id=ci.owner_id)

    ci.equipped = not ci.equipped
    ci.save(update_fields=["equipped"])

    return redirect("character_sheet", character_id=ci.owner_id)


@require_POST
def consume_item(request, pk):
    ci = get_object_or_404(
        CharacterItem.objects.select_related("item"),
        pk=pk,
    )

    owner_id = ci.owner_id
    if not ci.item.stackable:
        return redirect("character_sheet", character_id=owner_id)

    if ci.amount > 1:
        ci.amount -= 1
        ci.save(update_fields=["amount"])
    else:
        ci.delete()

    return redirect("character_sheet", character_id=owner_id)


@require_POST
def adjust_current_damage(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id)
    action = request.POST.get("action")
    try:
        amount = max(1, int(request.POST.get("amount", "1")))
    except (TypeError, ValueError):
        amount = 1

    if action == "damage":
        character.current_damage += amount
    elif action == "heal":
        character.current_damage = max(0, character.current_damage - amount)

    character.save(update_fields=["current_damage"])

    is_ajax = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
        or request.POST.get("ajax") == "1"
    )
    if is_ajax:
        engine = character.engine
        wound_stage, _ = engine.current_wound_stage()
        wound_penalty_display = (
            "-"
            if wound_stage == "-"
            else _format_modifier(engine.current_wound_penalty_raw())
        )
        wound_thresholds = engine.wound_thresholds()
        return JsonResponse(
            {
                "current_damage": character.current_damage,
                "current_wound_stage": wound_stage,
                "current_wound_penalty": wound_penalty_display,
                "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
                "current_damage_max": max(wound_thresholds.keys()) if wound_thresholds else 0,
            }
        )

    return redirect("character_sheet", character_id=character_id)


@require_POST
def adjust_money(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id)
    try:
        delta = int(request.POST.get("delta", "0"))
    except (TypeError, ValueError):
        delta = 0

    if delta:
        character.money = max(0, character.money + delta)
        character.save(update_fields=["money"])

    return redirect("character_sheet", character_id=character_id)


@require_POST
def adjust_experience(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id)
    try:
        delta = int(request.POST.get("delta", "0"))
    except (TypeError, ValueError):
        delta = 0

    if delta:
        character.current_experience = max(0, character.current_experience + delta)
        character.overall_experience = max(0, character.overall_experience + delta)
        character.save(update_fields=["current_experience", "overall_experience"])

    return redirect("character_sheet", character_id=character_id)


@require_POST
def create_shop_item(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect("character_sheet", character_id=character.id)

    try:
        price = int(request.POST.get("price", "0"))
    except (TypeError, ValueError):
        price = 0

    item_type = (request.POST.get("item_type") or "misc").strip()
    description = (request.POST.get("description") or "").strip()
    stackable = bool(request.POST.get("stackable"))
    if item_type in (Item.ItemType.ARMOR, Item.ItemType.WEAPON):
        stackable = False

    item = Item(
        name=name,
        price=max(0, price),
        item_type=item_type,
        description=description,
        stackable=stackable,
    )
    try:
        item.full_clean()
        item.save()

        if item.item_type == Item.ItemType.ARMOR:
            armor_mode = (request.POST.get("armor_mode") or "total").strip()
            if armor_mode == "zones":
                armor_stats = ArmorStats(
                    item=item,
                    rs_total=0,
                    rs_head=max(0, int(request.POST.get("armor_rs_head", "0") or 0)),
                    rs_torso=max(0, int(request.POST.get("armor_rs_torso", "0") or 0)),
                    rs_arm_left=max(0, int(request.POST.get("armor_rs_arm_left", "0") or 0)),
                    rs_arm_right=max(0, int(request.POST.get("armor_rs_arm_right", "0") or 0)),
                    rs_leg_left=max(0, int(request.POST.get("armor_rs_leg_left", "0") or 0)),
                    rs_leg_right=max(0, int(request.POST.get("armor_rs_leg_right", "0") or 0)),
                )
            else:
                armor_stats = ArmorStats(
                    item=item,
                    rs_total=max(0, int(request.POST.get("armor_rs_total", "0") or 0)),
                    rs_head=0,
                    rs_torso=0,
                    rs_arm_left=0,
                    rs_arm_right=0,
                    rs_leg_left=0,
                    rs_leg_right=0,
                )
            armor_stats.full_clean()
            armor_stats.save()
        elif item.item_type == Item.ItemType.WEAPON:
            damage = (request.POST.get("weapon_damage") or "").strip()
            min_st = max(1, int(request.POST.get("weapon_min_st", "1") or 1))
            damage_source_id = int(request.POST.get("weapon_damage_source", "0") or 0)
            damage_source = DamageSource.objects.get(pk=damage_source_id)
            weapon_stats = WeaponStats(
                item=item,
                damage=damage,
                damage_source=damage_source,
                min_st=min_st,
            )
            weapon_stats.full_clean()
            weapon_stats.save()
    except (ValidationError, ValueError, DamageSource.DoesNotExist):
        if item.pk:
            item.delete()

    return redirect("character_sheet", character_id=character.id)


@require_POST
def buy_shop_cart(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    cart_items = payload.get("items") or []
    discount = payload.get("discount") or 0
    try:
        discount_percent = max(0, min(100, int(discount)))
    except (TypeError, ValueError):
        discount_percent = 0

    if not isinstance(cart_items, list) or not cart_items:
        return JsonResponse({"ok": False, "error": "empty_cart"}, status=400)

    normalized: list[tuple[Item, int]] = []
    subtotal = 0
    for entry in cart_items:
        try:
            item_id = int(entry.get("id"))
            qty = int(entry.get("qty"))
        except (TypeError, ValueError, AttributeError):
            return JsonResponse({"ok": False, "error": "invalid_item"}, status=400)
        if qty < 1:
            return JsonResponse({"ok": False, "error": "invalid_qty"}, status=400)

        item = Item.objects.filter(pk=item_id).first()
        if item is None:
            return JsonResponse({"ok": False, "error": "item_not_found"}, status=400)
        if not item.stackable and qty != 1:
            return JsonResponse({"ok": False, "error": "non_stackable_qty"}, status=400)
        normalized.append((item, qty))
        subtotal += item.price * qty

    final_price = max(0, round(subtotal * (100 - discount_percent) / 100))
    if final_price > character.money:
        return JsonResponse({"ok": False, "error": "insufficient_funds"}, status=200)

    with transaction.atomic():
        character.money -= final_price
        character.save(update_fields=["money"])
        for item, qty in normalized:
            existing = CharacterItem.objects.filter(owner=character, item=item).first()
            if existing:
                if item.stackable:
                    existing.amount += qty
                    existing.full_clean()
                    existing.save(update_fields=["amount"])
                else:
                    existing.amount = 1
                    existing.full_clean()
                    existing.save(update_fields=["amount"])
            else:
                amount = qty if item.stackable else 1
                created = CharacterItem(owner=character, item=item, amount=amount, equipped=False)
                created.full_clean()
                created.save()

    return JsonResponse({"ok": True, "new_money": character.money}, status=200)
