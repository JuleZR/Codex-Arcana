"""Current quickslot actions, resolved by the existing character engines."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from charsheet.engine.battle_calculator_engine import (
    BattleCalculatorEngine, DamageCalculationInput,
)

from charsheet.engine.character_equipment import weapon_rows_for_items
from charsheet.engine.item_engine import ItemEngine
from charsheet.models import CharacterItem
from charsheet.sheet_context import _build_skill_rows


def build_quickslot_actions(character, engine):
    skill_rows, _, _ = _build_skill_rows(
        character, engine, load_penalty=engine.load_penalty(),
    )
    actions = []
    for row in skill_rows:
        if not row.get("quickslot_id"):
            continue
        character_skill_id = (
            row.get("character_skill_id")
            if row.get("is_specification_child") else None
        )
        actions.append({
            "type": "skill",
            "id": row["quickslot_id"],
            "subentry": row.get("quickslot_subentry", ""),
            "specification": (
                row.get("quickslot_specification", "")
                if row.get("is_context_row") else (
                    row.get("specification", "")
                    if row.get("is_specification_child")
                    and not character_skill_id else ""
                )
            ),
            "label": row.get("quickslot_label") or row["display_name"],
            "modifier": row["with_load_total_value"],
            "available": True,
        })

    items = list(CharacterItem.objects.filter(
        owner=character, item__item_type__is_weapon=True,
    ).select_related("item", "item__item_type", "quality"))
    resolved_items = set()
    for row in weapon_rows_for_items(engine, items):
        character_item = row["character_item"]
        resolved_items.add(character_item.pk)
        for option in row["maneuver_options"]:
            attribute = option["attribute_code"]
            actions.append({
                "type": "weapon",
                "id": str(character_item.pk),
                "profile": str(row["weapon_stats_id"] or ""),
                "mode": row["mode"],
                "attribute": attribute,
                "label": row["item_name"],
                "detail": " · ".join(filter(None, [
                    row["mode_label"], attribute,
                ])),
                "count": row["damage_data"][0],
                "sides": row["damage_data"][1],
                "flat_bonus": row["damage_data"][2],
                "flat_operator": row["damage_data"][3] or "+",
                "damage_modifier": row["dmg_mod"],
                "available": True,
            })
    for item in items:
        if item.pk not in resolved_items:
            actions.append({
                "type": "weapon", "id": str(item.pk),
                "label": ItemEngine(item).get_name(), "available": False,
            })
    actions.append({
        "type": "initiative", "id": "initiative", "label": "Initiative",
        "modifier": engine.calculate_initiative() + engine.load_penalty(),
        "available": True,
    })
    return actions


@login_required
@require_GET
@never_cache
def quickslot_actions(request, character_id):
    from charsheet.views import (
        _owned_character_or_404, _temporary_attribute_adjustments,
    )

    character = _owned_character_or_404(request, character_id)
    engine = character.get_engine(
        refresh=True,
        runtime_attribute_adjustments=_temporary_attribute_adjustments(
            request, character.pk,
        ),
    )
    actions = build_quickslot_actions(character, engine)
    if request.user.is_staff:
        actions.extend([
            {"type": "debug", "id": "krit", "label": "DEBUG - Krit",
             "available": True},
            {"type": "debug", "id": "mis", "label": "DEBUG - MIS",
             "available": True},
        ])
    return JsonResponse({"actions": actions})


@login_required
@require_POST
@never_cache
def quickslot_debug_result(request, character_id):
    from charsheet.views import _owned_character_or_404

    if not request.user.is_staff:
        return JsonResponse({"error": "Nur für Staff verfügbar."}, status=403)
    _owned_character_or_404(request, character_id)
    try:
        mode = json.loads(request.body)["debug"]
        if mode not in ("krit", "mis"):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        return JsonResponse({"error": "Ungültiger DEBUG-Wurf."}, status=400)
    rolls = [10, 10] if mode == "krit" else [1, 1]
    return JsonResponse({"sides": 10, "count": 2, "rolls": rolls,
                         "total": sum(rolls)})


@login_required
@require_POST
@never_cache
def quickslot_weapon_result(request, character_id):
    from charsheet.views import (
        _owned_character_or_404, _temporary_attribute_adjustments,
    )

    character = _owned_character_or_404(request, character_id)
    engine = character.get_engine(
        refresh=True,
        runtime_attribute_adjustments=_temporary_attribute_adjustments(
            request, character.pk,
        ),
    )
    try:
        payload = json.loads(request.body)
        reference = payload["action"]
        action = next(a for a in build_quickslot_actions(character, engine)
                      if a["type"] == "weapon" and a.get("available")
                      and all(a.get(key, "") == reference.get(key, "")
                              for key in (
                                  "id", "profile", "mode", "attribute",
                              )))
        rolls = payload["rolls"]
        if (payload.get("sides") != action["sides"]
                or not isinstance(rolls, list) or len(rolls) != action["count"]
                or any(type(value) is not int
                       or not 1 <= value <= action["sides"]
                       for value in rolls)):
            raise ValueError
        result = BattleCalculatorEngine.calculate_damage_result(
            DamageCalculationInput(
                dice_values=tuple(rolls), flat_bonus=action["flat_bonus"],
                flat_operator=action["flat_operator"],
                manual_bonus=action["damage_modifier"],
            ),
        )
        modifiers = []
        if action["flat_bonus"]:
            operator = action["flat_operator"]
            modifiers.append({
                "type": "modifier",
                "value": (-1 if operator == "-" else 1)
                * action["flat_bonus"],
                "operator": operator,
                "label": "Waffenschaden",
            })
        if action["damage_modifier"]:
            modifiers.append({
                "type": "modifier", "value": action["damage_modifier"],
                "label": "Schadensbonus",
            })
        return JsonResponse({"total": result["total"],
                             "modifiers": modifiers, "critical": False})
    except (ValueError, TypeError, KeyError, AttributeError, StopIteration):
        return JsonResponse({"error": "Waffenwurf nicht verfügbar."},
                            status=400)
