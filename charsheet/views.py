from __future__ import annotations
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Character, CharacterItem, CharacterTrait, Technique


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
    for weapon in weapon_items:
        dmg_slug = weapon.item.weaponstats.damage_source.slug
        dmg_mod = engine.get_dmg_modifier_sum(dmg_slug)

        weapon_rows.append({
            "character_item": weapon,
            "item": weapon.item,
            "stats": weapon.item.weaponstats,
            "dmg_mod": _format_modifier(dmg_mod)
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
