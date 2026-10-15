"""Read-only previews using the persisted item card's effect presentation."""

import json
from collections import defaultdict
from copy import copy
from decimal import InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from charsheet.models import (
    CharacterItemRuneSpec, CharacterItemSemanticEffect, ItemRune, Race, Rune,
    School,
)
from charsheet.sheet_context import (
    _build_character_item_magic_tooltip_rows,
    _collapse_weapon_mastery_bonus_payloads,
    _serialize_item_semantic_effect_payload,
    build_character_item_card_context,
)
from charsheet.shop import (
    _magic_payload_to_semantic_effect_kwargs, _read_decimal, _read_int,
    _read_magic_modifier_payloads, _read_quality, _read_rune_payloads,
)
from charsheet.views import _owned_character_item_or_404


def _preview_lines(payloads):
    """Use the card formatter for individual effects and complete groups."""
    rows = _build_character_item_magic_tooltip_rows(
        effect_summary="",
        modifier_payloads=_collapse_weapon_mastery_bonus_payloads(payloads),
        include_condition_blocked=True,
    )
    lines = []
    for label, detail in rows:
        if detail == "[[EMPTY]]":
            detail = ""
        if label not in {"Effekt", "Effekte", "[[EMPTY]]"}:
            lines.append(f"{label} · {detail}" if detail else label)
        elif detail:
            lines.append(str(detail))
    return lines


def _preview_item_card(owned, post, effect_payloads, viewer):
    """Render the shared card from an in-memory draft, without saving it."""
    draft = copy(owned)
    draft.name_override = str(post.get("name") or owned.item.name).strip()
    draft.price_override = _read_int(
        post, "price", owned.item.price, minimum=0,
    )
    draft.weight_override = _read_decimal(post, "weight", owned.item.weight)
    draft.size_class_override = str(
        post.get("size_class") or owned.item.size_class,
    )
    draft.quality_id = _read_quality(
        post, "quality", owned.quality or owned.item.default_quality,
    )
    draft.description = str(post.get("description") or "").strip()
    draft.invested_cp = _read_int(post, "invested_cp", minimum=0)
    draft.is_magic = bool(effect_payloads)
    draft.magic_effect_summary = ""
    if post.get("remove_image"):
        draft.image_override = None
    if "rune_payloads" in post:
        slots = _read_rune_payloads(post)[:5]
        runes = Rune.objects.in_bulk([slot["rune_id"] for slot in slots])
        assignments, specs = [], []
        for slot in slots:
            rune = runes.get(slot["rune_id"])
            if rune is None:
                continue
            assignments.append(ItemRune(
                item=draft, rune=rune, crafter_level=slot["crafter_level"],
                is_active=True,
            ))
            specs.append(CharacterItemRuneSpec(
                character_item=draft, rune=rune, slot=slot["slot"],
                specification=slot["specification"],
            ))
        draft._prefetched_objects_cache = {
            **getattr(draft, "_prefetched_objects_cache", {}),
            "item_runes": assignments, "rune_specs": specs,
            "runes": list(runes.values()),
        }
    card = build_character_item_card_context(
        draft, viewer, preview_player=False,
        modifier_payloads=_collapse_weapon_mastery_bonus_payloads(
            effect_payloads,
        ),
    )
    return render_to_string(
        "charsheet/partials/_shared_item_card.html", {"item_card": card},
    )


@login_required
@require_POST
def preview_item_effects(request, pk):
    """Format drafts without saving items, effects, or conditions."""
    owned = _owned_character_item_or_404(request, pk)
    try:
        raw = json.loads(request.POST.get("magic_modifier_payloads", "[]"))
        if not isinstance(raw, list) or len(raw) > 100:
            raise ValueError
        payloads = _read_magic_modifier_payloads(request.POST)
        invested_cp = max(0, int(request.POST.get("invested_cp") or 0))
    except (ValidationError, ValueError, TypeError):
        return JsonResponse({"error": "Ungültige Effekte."}, status=400)

    school_ids = set(owned.owner.schools.values_list("school_id", flat=True))
    grouped = defaultdict(list)
    display_groups = defaultdict(list)
    card_payloads = []
    for payload in payloads:
        kwargs = _magic_payload_to_semantic_effect_kwargs(payload)
        if kwargs is None:
            continue
        draft = CharacterItemSemanticEffect(character_item=owned, **kwargs)
        serialized = _serialize_item_semantic_effect_payload(
            draft,
            invested_cp=invested_cp,
            character_race_id=owned.owner.race_id,
            character_school_ids=school_ids,
            condition_races=list(Race.objects.filter(
                pk__in=payload.get("condition_races", []),
            )),
            condition_schools=list(School.objects.filter(
                pk__in=payload.get("condition_schools", []),
            )),
        )
        grouped[payload["display_order"]].append(serialized)
        card_payloads.append(serialized)
        if serialized.get("display_group") is not None:
            display_groups[serialized["display_group"]].append(serialized)

    previews = []
    for index in range(len(raw)):
        effects = grouped[index]
        group = effects[0].get("display_group") if effects else None
        if group is not None:
            effects = display_groups[group]
        previews.append(_preview_lines(effects))
    result = {"previews": previews}
    if request.POST.get("include_item_card"):
        try:
            result["item_card_html"] = _preview_item_card(
                owned, request.POST, card_payloads, request.user,
            )
        except (ValidationError, InvalidOperation, ValueError, TypeError):
            return JsonResponse({"error": "Ungültige Grunddaten."}, status=400)
    return JsonResponse(result)
