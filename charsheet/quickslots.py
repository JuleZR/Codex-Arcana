"""Current quickslot actions, resolved by the existing character engines."""

import json
import math
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import (
    require_GET, require_http_methods, require_POST,
)

from charsheet.engine.battle_calculator_engine import (
    BattleCalculatorEngine, DamageCalculationInput,
)

from charsheet.engine.character_equipment import weapon_rows_for_items
from charsheet.engine.item_engine import ItemEngine
from charsheet.models import CharacterItem, CharacterQuickslotLayout
from charsheet.sheet_context import _build_skill_rows


def _validated_debug_rolls(rolls, sides=10):
    if (type(sides) is not int or sides not in (10, 100)
            or not isinstance(rolls, list)
            or len(rolls) != 2
            or any(type(value) is not int
                   or not (0 <= value <= 9 if sides == 100
                           else 1 <= value <= 10)
                   for value in rolls)):
        raise ValueError
    return rolls


def _validated_layout(payload):
    slots = payload["slots"]
    if (not isinstance(slots, list) or len(slots) != 11
            or type(payload.get("collapsed")) is not bool):
        raise ValueError
    allowed = {
        "type", "id", "label", "sides", "count", "operator", "operand",
        "subentry", "specification", "profile", "mode", "attribute",
        "modifiers", "ignoreBonus", "labelPosition", "customLabel", "image",
        "target", "rolls",
    }
    clean = []
    for action in slots:
        if action is None:
            clean.append(None)
            continue
        if not isinstance(action, dict) or action.get("type") not in {
                "dice", "skill", "weapon", "initiative", "debug"}:
            raise ValueError
        action = {
            key: value for key, value in action.items() if key in allowed
        }
        if action["type"] == "dice":
            if (type(action.get("sides")) is not int
                    or action["sides"] not in (2, 4, 6, 8, 10, 12, 20, 100)
                    or type(action.get("count")) is not int
                    or not 1 <= action["count"] <= 100):
                raise ValueError
            if "operator" in action or "operand" in action:
                if (action.get("operator") not in ("+", "-", "*", "/")
                        or type(action.get("operand")) not in (int, float)
                        or not math.isfinite(action["operand"])):
                    raise ValueError
        elif (not isinstance(action.get("id"), str)
              or not action["id"]):
            raise ValueError
        if action["type"] == "debug":
            if action["id"] not in ("custom", "w100"):
                raise ValueError
            _validated_debug_rolls(
                action.get("rolls"), 100 if action["id"] == "w100" else 10,
            )
        for key in (
                "id", "label", "subentry", "specification", "profile",
                "mode", "attribute", "customLabel"):
            if key in action and (not isinstance(action[key], str)
                                  or len(action[key]) > 1024):
                raise ValueError
        if "image" in action and (
                not isinstance(action["image"], str)
                or len(action["image"]) > 120000
                or not re.fullmatch(
                    r"data:image/jpeg;base64,[A-Za-z0-9+/=]+", action["image"],
                )):
            raise ValueError
        if "ignoreBonus" in action and type(action["ignoreBonus"]) is not bool:
            raise ValueError
        if "target" in action and (
                type(action["target"]) not in (int, float)
                or not math.isfinite(action["target"])):
            raise ValueError
        if ("labelPosition" in action and action["labelPosition"]
                not in ("top", "center", "bottom", "hidden")):
            raise ValueError
        modifiers = action.get("modifiers", [])
        if not isinstance(modifiers, list) or len(modifiers) > 100:
            raise ValueError
        if any(not isinstance(entry, dict)
               or type(entry.get("value")) not in (int, float)
               or not math.isfinite(entry["value"])
               or not isinstance(entry.get("name"), str)
               or len(entry["name"]) > 80 for entry in modifiers):
            raise ValueError
        clean.append(action)
    return {"slots": clean, "collapsed": payload["collapsed"]}


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def quickslot_layout(request, character_id):
    from charsheet.views import _owned_character_or_404

    character = _owned_character_or_404(request, character_id)
    if request.method == "GET":
        layout = CharacterQuickslotLayout.objects.filter(
            user=request.user, character=character,
        ).first()
    else:
        try:
            payload = json.loads(request.body)
            state = _validated_layout(payload)
            if type(payload.get("initialize", False)) is not bool:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            return JsonResponse({"error": "Ungültige Hotbar-Belegung."},
                                status=400)
        lookup = {"user": request.user, "character": character}
        if payload.get("initialize"):
            layout, _ = CharacterQuickslotLayout.objects.get_or_create(
                **lookup, defaults=state,
            )
        else:
            layout, _ = CharacterQuickslotLayout.objects.update_or_create(
                **lookup, defaults=state,
            )
    return JsonResponse({"layout": None if layout is None else {
        "slots": layout.slots, "collapsed": layout.collapsed,
    }})


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
        actions.append({
            "type": "debug", "id": "custom", "label": "DEBUG",
            "rolls": [5, 5], "available": True,
        })
        actions.append({
            "type": "debug", "id": "w100", "label": "DEBUG W100",
            "rolls": [5, 0], "available": True,
        })
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
        payload = json.loads(request.body)
        sides = payload.get("sides", 10)
        rolls = _validated_debug_rolls(payload["rolls"], sides)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({"error": "Ungültiger DEBUG-Wurf."}, status=400)
    if sides == 100:
        rolls = [rolls[0] * 10 + rolls[1] or 100]
    return JsonResponse({"sides": sides, "count": len(rolls), "rolls": rolls,
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
