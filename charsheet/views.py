from __future__ import annotations
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Character, CharacterItem, CharacterLanguage, CharacterTrait, Technique


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
        .filter(owner=character)
        .select_related("item")
        .order_by("item__item_type", "item__name")
    )
    
    weapon_items = inventory_items.filter(
        item__item_type="weapon",
        equipped=True,
    ).select_related(
        "item__weaponstats",
        "item__weaponstats__damage_source",
    )
    
    weapon_rows: list[dict] = []
    bel_value = engine.get_bel()
    for weapon in weapon_items:
        dmg_slug = weapon.item.weaponstats.damage_source.slug
        dmg_mod = engine.get_dmg_modifier_sum(dmg_slug)
        bel_malus = -bel_value
        with_bel = dmg_mod + bel_malus

        weapon_rows.append({
            "character_item": weapon,
            "item": weapon.item,
            "stats": weapon.item.weaponstats,
            "dmg_mod": _format_modifier(dmg_mod),
            "bel_malus": _format_modifier(bel_malus),
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
