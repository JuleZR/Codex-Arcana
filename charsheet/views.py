from __future__ import annotations
import json
import random
from datetime import date as date_cls
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Max, Sum
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.urls import reverse_lazy
from .engine import CharacterCreationEngine, ItemEngine
from django.views.generic import TemplateView
from .constants import GK_MODS, QUALITY_CHOICES, QUALITY_COLOR_MAP
from .models import (
    Character,
    CharacterAttribute,
    CharacterDiaryEntry,
    CharacterItem,
    CharacterLanguage,
    CharacterSchool,
    CharacterSkill,
    CharacterTrait,
    Trait,
    CharacterCreationDraft,
    Technique,
    Item,
    Skill,
    School,
    Language,
    ArmorStats,
    ShieldStats,
    WeaponStats,
    DamageSource,
)
from .forms import AccountSettingsForm, CharacterCreateForm, CharacterUpdateForm, CharacterInfoInlineForm


ATTRIBUTE_ORDER = [
    ("ST", "Stärke (St)"),
    ("KON", "Konstitution (Kon)"),
    ("GE", "Geschick (Ge)"),
    ("WA", "Wahrnehmung (Wa)"),
    ("INT", "Intelligenz (Int)"),
    ("WILL", "Willenskraft (Will)"),
    ("CHA", "Charisma (Cha)"),
]
DEFAULT_SCHOOL_MAX_LEVEL = 10
DIARY_ENTRY_CHAR_LIMIT = 2200
QUALITY_LABELS = dict(QUALITY_CHOICES)


def _legal_context() -> dict:
    """Return legal page context from deployment-specific settings."""
    legal = dict(getattr(settings, "LEGAL_INFO", {}) or {})
    missing_required = not all(
        [
            (legal.get("operator_name") or "").strip(),
            (legal.get("address") or "").strip(),
            (legal.get("email") or "").strip(),
        ]
    )
    legal["missing_required"] = missing_required
    return {"legal": legal}


def _format_modifier(value: int) -> str:
    """Format signed modifier values for UI display."""
    if value > 0:
        return f"+{value}"
    return str(value)


def _format_thousands(value: int) -> str:
    """Format integers with dot-separated thousands."""
    return f"{value:,}".replace(",", ".")


def _quality_payload(quality: str) -> dict[str, str]:
    """Return normalized quality metadata for templates and JSON responses."""
    resolved_quality = ItemEngine.normalize_quality(quality)
    return {
        "value": resolved_quality,
        "label": QUALITY_LABELS.get(resolved_quality, QUALITY_LABELS[ItemEngine.normalize_quality(None)]),
        "color": QUALITY_COLOR_MAP.get(resolved_quality, QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)]),
    }


def _calc_skill_total_cost(level: int) -> int:
    """Return cumulative skill cost for one target level."""
    if level <= 5:
        return max(0, level)
    return 5 + ((max(0, level) - 5) * 2)


def _calc_language_total_cost(level: int, can_write: bool, is_mother_tongue: bool) -> int:
    """Return cumulative language cost for one language state."""
    base = 0 if is_mother_tongue else max(0, level)
    return base + (1 if can_write else 0)


def _calc_attribute_total_cost(target_level: int, max_value: int) -> int:
    """Return cumulative attribute cost for one target level."""
    level = max(0, target_level)
    threshold = max_value - 2
    if level <= threshold:
        return level * 10
    cost = threshold * 10
    for _value in range(threshold + 1, level + 1):
        cost += 20
    return cost


def _school_max_levels() -> dict[int, int]:
    """Return dynamic school level caps based on highest technique level per school."""
    caps: dict[int, int] = {}
    rows = (
        Technique.objects
        .values("school_id")
        .annotate(max_level=Max("level"))
    )
    for row in rows:
        school_id = int(row.get("school_id") or 0)
        if school_id <= 0:
            continue
        max_level = int(row.get("max_level") or DEFAULT_SCHOOL_MAX_LEVEL)
        caps[school_id] = max(1, max_level)
    return caps


def _owned_character_or_404(request, character_id: int) -> Character:
    """Return one character that belongs to the current authenticated user."""
    return get_object_or_404(
        Character.objects.select_related("race", "owner"),
        pk=character_id,
        owner=request.user,
    )


def _owned_character_item_or_404(request, pk: int) -> CharacterItem:
    """Return one inventory row whose character belongs to the current user."""
    return get_object_or_404(
        CharacterItem.objects.select_related("item", "owner"),
        pk=pk,
        owner__owner=request.user,
    )


def _owned_diary_entry_or_404(request, character_id: int, entry_id: int) -> tuple[Character, CharacterDiaryEntry]:
    """Return one diary entry that belongs to one owned character."""
    character = _owned_character_or_404(request, character_id)
    entry = get_object_or_404(
        CharacterDiaryEntry.objects.select_related("character"),
        pk=entry_id,
        character=character,
    )
    return character, entry


def _parse_iso_date(raw_value) -> date_cls | None:
    """Parse one HTML date input value into a Python date."""
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        return None


def _normalize_diary_entries(character: Character) -> list[CharacterDiaryEntry]:
    """Guarantee stable order and exactly one empty editable tail entry per character."""
    with transaction.atomic():
        entries = list(
            CharacterDiaryEntry.objects
            .select_for_update()
            .filter(character=character)
            .order_by("order_index", "id")
        )
        if not entries:
            CharacterDiaryEntry.objects.create(
                character=character,
                order_index=0,
                text="",
                entry_date=None,
                is_fixed=False,
            )
            return list(
                CharacterDiaryEntry.objects
                .filter(character=character)
                .order_by("order_index", "id")
            )

        trailing_blank_entries: list[CharacterDiaryEntry] = []
        for entry in reversed(entries):
            if entry.is_fixed or (entry.text or "").strip():
                break
            trailing_blank_entries.append(entry)
        trailing_blank_entries.reverse()

        if not trailing_blank_entries:
            entries.append(
                CharacterDiaryEntry.objects.create(
                    character=character,
                    order_index=len(entries),
                    text="",
                    entry_date=None,
                    is_fixed=False,
                )
            )
        elif len(trailing_blank_entries) > 1:
            stale_entries = trailing_blank_entries[:-1]
            CharacterDiaryEntry.objects.filter(pk__in=[entry.pk for entry in stale_entries]).delete()
            entries = entries[:len(entries) - len(trailing_blank_entries)] + [trailing_blank_entries[-1]]

        dirty_entries: list[CharacterDiaryEntry] = []
        for index, entry in enumerate(entries):
            if entry.order_index != index:
                entry.order_index = index
                dirty_entries.append(entry)
        if dirty_entries:
            CharacterDiaryEntry.objects.bulk_update(dirty_entries, ["order_index"])

        return list(
            CharacterDiaryEntry.objects
            .filter(character=character)
            .order_by("order_index", "id")
        )


def _serialize_diary_entry(entry: CharacterDiaryEntry) -> dict[str, object]:
    """Return one diary entry payload for the character-sheet frontend."""
    return {
        "id": entry.id,
        "order_index": entry.order_index,
        "text": entry.text,
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else "",
        "is_fixed": bool(entry.is_fixed),
        "is_empty": entry.is_empty,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def _diary_payload(character: Character, *, current_entry_id: int | None = None) -> dict[str, object]:
    """Return normalized diary state payload for one character."""
    entries = _normalize_diary_entries(character)
    if current_entry_id is None and entries:
        current_entry_id = entries[-1].id
    return {
        "ok": True,
        "entries": [_serialize_diary_entry(entry) for entry in entries],
        "current_entry_id": current_entry_id,
    }


def _read_json_payload(request) -> dict[str, object]:
    """Parse one JSON request body into a dictionary."""
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _character_dashboard_state(character: Character) -> dict[str, str]:
    """Build one compact status payload for dashboard character rows."""
    wound_stage, _penalty = character.engine.current_wound_stage()
    if wound_stage == "-":
        condition = "Unverletzt"
    else:
        condition = f"Wundstufe: {wound_stage}"
    return {
        "experience": f"{character.current_experience} / {character.overall_experience} EP",
        "condition": condition,
    }


@login_required
def character_sheet(request, character_id: int):
    """Render the complete character sheet view for one character."""
    character = _owned_character_or_404(request, character_id)
    character.last_opened_at = timezone.now()
    character.save(update_fields=["last_opened_at"])

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
    inventory_rows: list[dict] = []
    for character_item in inventory_items:
        item_engine = ItemEngine(character_item)
        quality = _quality_payload(item_engine.get_effective_quality())
        inventory_rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "quality": quality["value"],
                "quality_label": quality["label"],
                "quality_color": quality["color"],
            }
        )

    weapon_rows: list[dict] = []
    for row in engine.equipped_weapon_rows():
        quality = _quality_payload(str(row["quality"]))
        row["quality_label"] = quality["label"]
        row["quality_color"] = quality["color"]
        weapon_rows.append(row)

    equipped_armor: list[dict] = []
    for row in engine.equipped_armor_rows():
        quality = _quality_payload(str(row["quality"]))
        row["quality_label"] = quality["label"]
        row["quality_color"] = quality["color"]
        equipped_armor.append(row)

    equipped_shields: list[dict] = []
    for row in engine.equipped_shield_rows():
        quality = _quality_payload(str(row["quality"]))
        row["quality_label"] = quality["label"]
        row["quality_color"] = quality["color"]
        equipped_shields.append(row)

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
    size_class = getattr(race, "size_class", None) or getattr(race, "height_class", "-") or "-"
    size_class_mod = (
        _format_modifier(int(GK_MODS[size_class]))
        if size_class in GK_MODS
        else "-"
    )
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
    grouped_items: dict[str, list[dict]] = {}
    for item in buyable_items:
        item_engine = ItemEngine(item)
        quality = _quality_payload(item_engine.get_effective_quality())
        stats_payload: dict[str, object] = {
            "item_type": item.item_type,
            "size_class": item.size_class,
            "weight": str(item.weight),
            "min_st": None,
        }
        weapon_stats = getattr(item, "weaponstats", None)
        if weapon_stats is not None:
            stats_payload.update(
                {
                    "damage_dice_amount": weapon_stats.damage_dice_amount,
                    "damage_dice_faces": weapon_stats.damage_dice_faces,
                    "damage_flat_bonus": weapon_stats.damage_flat_bonus,
                    "h2_dice_amount": weapon_stats.h2_dice_amount,
                    "h2_dice_faces": weapon_stats.h2_dice_faces,
                    "h2_flat_bonus": weapon_stats.h2_flat_bonus,
                    "wield_mode": weapon_stats.wield_mode,
                    "min_st": weapon_stats.min_st,
                    "damage_source": weapon_stats.damage_source.short_name,
                }
            )
        armor_stats = getattr(item, "armorstats", None)
        if armor_stats is not None:
            stats_payload.update(
                {
                    "armor_rs": item_engine.get_armor_rs_raw() or 0,
                    "armor_bel": armor_stats.encumbrance,
                    "armor_min_st": armor_stats.min_st,
                    "min_st": armor_stats.min_st,
                }
            )
        shield_stats = getattr(item, "shieldstats", None)
        if shield_stats is not None:
            stats_payload.update(
                {
                    "shield_rs": shield_stats.rs,
                    "shield_bel": shield_stats.encumbrance,
                    "shield_min_st": shield_stats.min_st,
                    "min_st": shield_stats.min_st,
                }
            )
        grouped_items.setdefault(item.item_type, []).append(
            {
                "id": item.id,
                "name": item.name,
                "description": item.description or "",
                "item_type": item.item_type,
                "stackable": bool(item.stackable),
                "base_price": int(item.price),
                "default_price": item_engine.get_price(),
                "default_quality": quality["value"],
                "default_quality_label": quality["label"],
                "default_quality_color": quality["color"],
                "stats": stats_payload,
            }
        )

    category_order = [
        (Item.ItemType.WEAPON, "Waffen"),
        (Item.ItemType.ARMOR, "Rüstungen"),
        (Item.ItemType.SHIELD, "Schilde"),
        (Item.ItemType.CONSUM, "Verbrauchbar"),
        (Item.ItemType.MISC, "Sonstiges"),
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

    attribute_limits = {
        limit.attribute.short_name: {
            "min": int(limit.min_value),
            "max": int(limit.max_value),
        }
        for limit in character.race.raceattributelimit_set.select_related("attribute")
    }
    skill_levels = {entry.skill_id: entry.level for entry in character_skills}
    language_lookup = {
        entry.language_id: {
            "level": int(entry.levels),
            "write": bool(entry.can_write),
            "mother": bool(entry.is_mother_tongue),
        }
        for entry in language_entries
    }

    learn_attr_rows: list[dict] = []
    for short_name, label in ATTRIBUTE_ORDER:
        base_value = int(attributes.get(short_name, 0))
        learn_attr_rows.append(
            {
                "short_name": short_name,
                "label": label,
                "base_value": base_value,
                "min_value": int(attribute_limits.get(short_name, {}).get("min", 0)),
                "max_value": int(attribute_limits.get(short_name, {}).get("max", base_value)),
            }
        )

    learn_skill_rows: list[dict] = []
    for skill in Skill.objects.select_related("category", "attribute").order_by("category__name", "name"):
        learn_skill_rows.append(
            {
                "slug": skill.slug,
                "name": skill.name,
                "description": (skill.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "category_name": skill.category.name,
                "base_level": int(skill_levels.get(skill.id, 0)),
            }
        )

    learn_language_rows: list[dict] = []
    for language in Language.objects.order_by("name"):
        base_state = language_lookup.get(language.id, {"level": 0, "write": False, "mother": False})
        learn_language_rows.append(
            {
                "slug": language.slug,
                "name": language.name,
                "base_level": int(base_state["level"]),
                "max_level": int(language.max_level),
                "base_write": bool(base_state["write"]),
                "base_mother": bool(base_state["mother"]),
            }
        )

    school_level_caps = _school_max_levels()
    learn_school_rows: list[dict] = []
    for school in School.objects.select_related("type").order_by("type__name", "name"):
        base_level = int(school_levels.get(school.id, 0))
        max_level = max(base_level, int(school_level_caps.get(school.id, DEFAULT_SCHOOL_MAX_LEVEL)))
        learn_school_rows.append(
            {
                "id": school.id,
                "name": school.name,
                "description": (school.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "type_name": school.type.name,
                "base_level": base_level,
                "max_level": max_level,
            }
        )

    shop_quality_choices = [
        {
            "value": value,
            "label": label,
            "color": QUALITY_COLOR_MAP.get(value, QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)]),
        }
        for value, label in QUALITY_CHOICES
    ]

    context = {
        "character": character,
        "char_info_form": CharacterInfoInlineForm(instance=character),
        "fame_total_rank": int(character.personal_fame_rank) + int(character.sacrifice_rank) + int(character.artefact_rank),
        "attributes": attributes,
        "attr_mods": attr_mods,
        "skill_rows": skill_rows,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "inventory_items": inventory_items,
        "inventory_rows": inventory_rows,
        "weapon_rows": weapon_rows,
        "school_technique_rows": school_technique_rows,
        "equipped_armor": equipped_armor,
        "equipped_shields": equipped_shields,
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
        "size_class": size_class,
        "size_class_mod": size_class_mod,
        "movement_ground": movement_ground,
        "language_rows": language_rows,
        "shop_item_groups": shop_item_groups,
        "shop_quality_choices": shop_quality_choices,
        "shop_item_type_choices": category_order,
        "shop_item_form_type_choices": [
            (Item.ItemType.MISC, "Sonstiges"),
            (Item.ItemType.CONSUM, "Verbrauchbar"),
            (Item.ItemType.WEAPON, "Waffen"),
            (Item.ItemType.ARMOR, "Rüstungen"),
            (Item.ItemType.SHIELD, "Schilde"),
        ],
        "shop_damage_sources": DamageSource.objects.order_by("name"),
        "learn_attr_rows": learn_attr_rows,
        "learn_skill_rows": learn_skill_rows,
        "learn_language_rows": learn_language_rows,
        "learn_school_rows": learn_school_rows,
        "close_learn_window_once": bool(request.session.pop("close_learn_window_once", False)),
    }

    return render(request, "charsheet/charsheet.html", context)


@login_required
def character_diary_entries_api(request, character_id: int):
    """Return normalized diary-roll entries for one owned character as JSON."""
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)
    character = _owned_character_or_404(request, character_id)
    return JsonResponse(_diary_payload(character))


@login_required
@require_POST
def edit_character_diary_entry(request, character_id: int, entry_id: int):
    """Switch one fixed diary entry into explicit edit mode."""
    character, entry = _owned_diary_entry_or_404(request, character_id, entry_id)
    if entry.is_fixed:
        entry.is_fixed = False
        entry.save(update_fields=["is_fixed", "updated_at"])
    return JsonResponse(_diary_payload(character, current_entry_id=entry.id))


@login_required
@require_POST
def save_character_diary_entry(request, character_id: int, entry_id: int):
    """Persist one editable diary entry without fixing it yet."""
    character, entry = _owned_diary_entry_or_404(request, character_id, entry_id)
    if entry.is_fixed:
        return JsonResponse({"ok": False, "error": "entry_fixed"}, status=409)

    payload = _read_json_payload(request)
    text = str(payload.get("text", entry.text or ""))
    if len(text) > DIARY_ENTRY_CHAR_LIMIT:
        return JsonResponse({"ok": False, "error": "text_too_long"}, status=400)

    update_fields = ["text", "updated_at"]
    entry.text = text
    if entry.entry_date is None:
        requested_date = _parse_iso_date(payload.get("entry_date"))
        if requested_date is not None:
            entry.entry_date = requested_date
            update_fields.append("entry_date")
    entry.save(update_fields=update_fields)
    return JsonResponse(_diary_payload(character, current_entry_id=entry.id))


@login_required
@require_POST
def fix_character_diary_entry(request, character_id: int, entry_id: int):
    """Finalize one diary entry, freeze its date, and append a fresh tail draft if needed."""
    character, entry = _owned_diary_entry_or_404(request, character_id, entry_id)
    payload = _read_json_payload(request)
    text = str(payload.get("text", entry.text or ""))
    if len(text) > DIARY_ENTRY_CHAR_LIMIT:
        return JsonResponse({"ok": False, "error": "text_too_long"}, status=400)
    if not text.strip():
        return JsonResponse({"ok": False, "error": "empty_entry"}, status=400)

    entry.text = text
    entry.is_fixed = True
    if entry.entry_date is None:
        entry.entry_date = _parse_iso_date(payload.get("entry_date")) or timezone.localdate()
        entry.save(update_fields=["text", "is_fixed", "entry_date", "updated_at"])
    else:
        entry.save(update_fields=["text", "is_fixed", "updated_at"])
    return JsonResponse(_diary_payload(character, current_entry_id=entry.id))


@login_required
@require_POST
def delete_character_diary_entry(request, character_id: int, entry_id: int):
    """Delete one diary entry and keep the remaining roll normalized."""
    character, entry = _owned_diary_entry_or_404(request, character_id, entry_id)
    target_index = int(entry.order_index)
    entry.delete()
    entries = _normalize_diary_entries(character)
    fallback_index = min(target_index, max(0, len(entries) - 1))
    current_entry_id = entries[fallback_index].id if entries else None
    return JsonResponse(_diary_payload(character, current_entry_id=current_entry_id))


@login_required
@require_POST
def import_legacy_character_diary(request, character_id: int):
    """Import one legacy browser-local diary payload into the persistent diary model."""
    character = _owned_character_or_404(request, character_id)
    payload = _read_json_payload(request)
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    existing_entries = _normalize_diary_entries(character)
    has_real_server_entries = any(entry.is_fixed or not entry.is_empty for entry in existing_entries)
    if has_real_server_entries:
        return JsonResponse({"ok": False, "error": "server_diary_not_empty"}, status=409)

    import_rows: list[CharacterDiaryEntry] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            continue
        text = str(raw_entry.get("text", ""))
        if len(text) > DIARY_ENTRY_CHAR_LIMIT:
            text = text[:DIARY_ENTRY_CHAR_LIMIT]
        if not text.strip():
            continue
        entry_date = _parse_iso_date(raw_entry.get("entry_date") or raw_entry.get("createdAt"))
        legacy_saved = raw_entry.get("isSaved")
        legacy_fixed = raw_entry.get("is_fixed")
        if isinstance(legacy_saved, bool):
            is_fixed = legacy_saved
        elif isinstance(legacy_fixed, bool):
            is_fixed = legacy_fixed
        else:
            is_fixed = True
        import_rows.append(
            CharacterDiaryEntry(
                character=character,
                order_index=index,
                text=text,
                entry_date=entry_date,
                is_fixed=is_fixed,
            )
        )

    if not import_rows:
        return JsonResponse({"ok": False, "error": "no_legacy_entries"}, status=400)

    with transaction.atomic():
        CharacterDiaryEntry.objects.filter(character=character).delete()
        CharacterDiaryEntry.objects.bulk_create(import_rows)

    return JsonResponse(_diary_payload(character))


@login_required
@require_POST
def adjust_personal_fame_point(request, character_id: int):
    """Adjust personal fame points and convert 10 points into one personal fame rank."""
    character = _owned_character_or_404(request, character_id)
    try:
        delta = int(request.POST.get("delta", "0"))
    except (TypeError, ValueError):
        delta = 0

    if delta > 0:
        for _ in range(delta):
            character.personal_fame_point = int(character.personal_fame_point) + 1
            if int(character.personal_fame_point) >= 10:
                character.personal_fame_point = 0
                character.personal_fame_rank = int(character.personal_fame_rank) + 1
    elif delta < 0:
        for _ in range(abs(delta)):
            points = int(character.personal_fame_point)
            rank = int(character.personal_fame_rank)
            if points > 0:
                character.personal_fame_point = points - 1
            elif rank > 0:
                character.personal_fame_rank = rank - 1
                character.personal_fame_point = 9

    character.save(update_fields=["personal_fame_point", "personal_fame_rank"])
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def update_character_info(request, character_id: int):
    """Update character info fields directly from the character-sheet inline form."""
    character = _owned_character_or_404(request, character_id)
    form = CharacterInfoInlineForm(request.POST, instance=character)
    if form.is_valid():
        name = (form.cleaned_data.get("name") or "").strip()
        if Character.objects.filter(owner=request.user, name=name).exclude(pk=character.pk).exists():
            messages.error(request, "Du hast bereits einen Charakter mit diesem Namen.")
        else:
            form.save()
            messages.success(request, "Charakterinformation aktualisiert.")
    else:
        messages.error(request, "Charakterinformation konnte nicht gespeichert werden.")
    return redirect("character_sheet", character_id=character.id)

@login_required
def sheet(request):
    """Render the static character sheet template."""
    return render(request, "charsheet/charsheet.html")


@login_required
def dashboard(request):
    """Render the user-specific dashboard with owned character overview."""
    characters_qs = Character.objects.filter(
        owner=request.user,
        is_archived=False,
    ).select_related("race")
    characters = list(characters_qs.order_by("name"))
    archived_characters = list(
        Character.objects.filter(owner=request.user, is_archived=True)
        .select_related("race")
        .order_by("name")
    )
    totals = characters_qs.aggregate(
        total_money=Sum("money"),
        total_current_experience=Sum("current_experience"),
    )
    character_rows = [
        {
            "character": character,
            "status": _character_dashboard_state(character),
        }
        for character in characters
    ]
    recent_characters = list(
        characters_qs.filter(last_opened_at__isnull=False)
        .order_by("-last_opened_at")[:5]
    )

    warnings: list[dict] = []
    for character in characters:
        if character.current_experience > 0:
            warnings.append(
                {
                    "severity": "warning",
                    "text": f"{character.name}: {character.current_experience} unverteilte EP.",
                }
            )
        if character.current_damage > 0:
            stage, _ = character.engine.current_wound_stage()
            if stage == "-":
                warnings.append(
                    {
                        "severity": "warning",
                        "text": f"{character.name}: {character.current_damage} aktueller Schaden.",
                    }
                )
            else:
                warnings.append(
                    {
                        "severity": "warning",
                        "text": f"{character.name}: Wundstufe {stage} bei {character.current_damage} Schaden.",
                    }
                )

    draft_count = CharacterCreationDraft.objects.filter(owner=request.user).count()
    draft_rows = []
    for draft in CharacterCreationDraft.objects.filter(owner=request.user).select_related("race").order_by("-id"):
        meta = draft.state if isinstance(draft.state, dict) else {}
        meta_name = str(meta.get("meta", {}).get("name", "")).strip() if isinstance(meta.get("meta", {}), dict) else ""
        draft_rows.append(
            {
                "id": draft.id,
                "name": meta_name or "(ohne Namen)",
                "race_name": draft.race.name,
                "phase": draft.current_phase,
            }
        )
    if draft_count:
        warnings.append(
            {
                "severity": "info",
                "text": f"{draft_count} offene Schritte in der Charaktererstellung gefunden.",
            }
        )

    search_query = (request.GET.get("q") or "").strip()
    search_results = {}
    if search_query:
        search_results = {
            "items": Item.objects.filter(name__icontains=search_query).order_by("name")[:8],
            "skills": Skill.objects.filter(name__icontains=search_query).order_by("name")[:8],
            "schools": School.objects.filter(name__icontains=search_query).order_by("name")[:8],
            "languages": Language.objects.filter(name__icontains=search_query).order_by("name")[:8],
        }

    roll_count_raw = request.GET.get("roll_count")
    roll_sides_raw = request.GET.get("roll_sides")
    roll_data = None
    if roll_count_raw and roll_sides_raw:
        try:
            roll_count = max(1, min(20, int(roll_count_raw)))
            roll_sides = max(2, min(100, int(roll_sides_raw)))
            rolls = [random.randint(1, roll_sides) for _ in range(roll_count)]
            roll_data = {
                "count": roll_count,
                "sides": roll_sides,
                "rolls": rolls,
                "total": sum(rolls),
            }
        except (TypeError, ValueError):
            roll_data = {"error": "Ungültige Würfelwerte."}

    equipped_item_count = CharacterItem.objects.filter(
        owner__owner=request.user,
        equipped=True,
    ).count()

    context = {
        "character_rows": character_rows,
        "archived_characters": archived_characters,
        "recent_characters": recent_characters,
        "character_count": len(characters),
        "character_count_display": _format_thousands(len(characters)),
        "total_money": totals.get("total_money") or 0,
        "total_money_display": _format_thousands(int(totals.get("total_money") or 0)),
        "equipped_item_count": equipped_item_count,
        "equipped_item_count_display": _format_thousands(equipped_item_count),
        "system_counts": {
            "items": Item.objects.count(),
            "skills": Skill.objects.count(),
            "schools": School.objects.count(),
            "languages": Language.objects.count(),
        },
        "rulebook_preview": {
            "items": Item.objects.order_by("name")[:6],
            "skills": Skill.objects.order_by("name")[:6],
            "schools": School.objects.order_by("name")[:6],
            "languages": Language.objects.order_by("name")[:6],
        },
        "warnings": warnings,
        "draft_rows": draft_rows,
        "search_query": search_query,
        "search_results": search_results,
        "roll_data": roll_data,
    }
    return render(request, "charsheet/dashboard.html", context)


@login_required
def edit_character(request, character_id: int):
    """Update one owned character from a dashboard action."""
    character = _owned_character_or_404(request, character_id)
    if request.method == "POST":
        form = CharacterUpdateForm(request.POST, instance=character)
        if form.is_valid():
            name = (form.cleaned_data.get("name") or "").strip()
            if Character.objects.filter(owner=request.user, name=name).exclude(pk=character.pk).exists():
                form.add_error("name", "Du hast bereits einen Charakter mit diesem Namen.")
            else:
                form.save()
                messages.success(request, "Charakter aktualisiert.")
                return redirect("dashboard")
    else:
        form = CharacterUpdateForm(instance=character)

    return render(
        request,
        "charsheet/create_character.html",
        {
            "form": form,
            "edit_mode": True,
            "character": character,
        },
    )


@login_required
@require_POST
def archive_character(request, character_id: int):
    """Archive one owned character and hide it from active dashboard list."""
    character = _owned_character_or_404(request, character_id)
    character.is_archived = True
    character.save(update_fields=["is_archived"])
    messages.info(request, f"{character.name} wurde archiviert.")
    return redirect("dashboard")


@login_required
@require_POST
def unarchive_character(request, character_id: int):
    """Restore one archived character back into active dashboard list."""
    character = _owned_character_or_404(request, character_id)
    character.is_archived = False
    character.save(update_fields=["is_archived"])
    messages.info(request, f"{character.name} ist wieder aktiv.")
    return redirect("dashboard")


@login_required
@require_POST
def delete_character(request, character_id: int):
    """Delete one owned character permanently."""
    character = _owned_character_or_404(request, character_id)
    name = character.name
    try:
        with transaction.atomic():
            # CharacterLanguage uses PROTECT on owner; delete dependent entries first.
            CharacterLanguage.objects.filter(owner=character).delete()
            character.delete()
    except ProtectedError:
        messages.error(request, f"{name} konnte nicht geloescht werden (geschuetzte Verknuepfungen).")
        return redirect("dashboard")
    messages.info(request, f"{name} wurde gelöscht.")
    return redirect("dashboard")


@login_required
@require_POST
def delete_creation_draft(request, draft_id: int):
    """Delete one owned character creation draft."""
    draft = get_object_or_404(CharacterCreationDraft, pk=draft_id, owner=request.user)
    draft_name = ""
    if isinstance(draft.state, dict):
        meta = draft.state.get("meta", {})
        if isinstance(meta, dict):
            draft_name = str(meta.get("name", "")).strip()
    draft.delete()
    if draft_name:
        messages.info(request, f"Entwurf '{draft_name}' wurde verworfen.")
    else:
        messages.info(request, "Charakterentwurf wurde verworfen.")
    return redirect("dashboard")


@login_required
@require_POST
def update_account_settings(request):
    """Update current user's username/email and optionally password."""
    form = AccountSettingsForm(request.user, request.POST)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return redirect("dashboard")

    changed, password_changed = form.save()
    if password_changed:
        update_session_auth_hash(request, request.user)
    if changed:
        messages.success(request, "Kontoeinstellungen gespeichert.")
    else:
        messages.info(request, "Keine Änderungen erkannt.")
    return redirect("dashboard")


class AppLogoutView(LogoutView):
    """Log out current user and redirect to login with a short status message."""

    next_page = reverse_lazy("login")

    def post(self, request, *args, **kwargs):
        auth_logout(request)
        messages.info(request, "Sie wurden abgemeldet.")
        return HttpResponseRedirect(self.get_success_url())


@login_required
def create_character(request):
    """Create one character through the phase-based draft engine."""
    draft_id = request.GET.get("draft") or request.POST.get("draft_id")
    draft = None
    if draft_id:
        draft = CharacterCreationDraft.objects.filter(pk=draft_id, owner=request.user).first()
    if request.method == "GET" and draft and request.GET.get("cancel_draft") == "1":
        draft.delete()
        messages.info(request, "Charaktererstellung wurde abgebrochen.")
        return redirect("dashboard")

    if request.method == "POST" and request.POST.get("start_creation") == "1":
        form = CharacterCreateForm(request.POST)
        if form.is_valid():
            name = (form.cleaned_data.get("name") or "").strip()
            if Character.objects.filter(owner=request.user, name=name).exists():
                form.add_error("name", "Du hast bereits einen Charakter mit diesem Namen.")
            else:
                draft = CharacterCreationDraft.objects.create(
                    owner=request.user,
                    race=form.cleaned_data["race"],
                    current_phase=1,
                    state={
                        "meta": {
                            "name": name,
                            "gender": form.cleaned_data.get("gender") or "",
                        }
                    },
                )
                return redirect(f"{reverse_lazy('create_character')}?draft={draft.id}")
    elif request.method == "POST" and draft:
        state = dict(draft.state or {})
        phase = int(draft.current_phase)
        action = (request.POST.get("action") or "next").strip()

        if phase == 1:
            limits = draft.race.raceattributelimit_set.select_related("attribute")
            attrs: dict[str, int] = {}
            for limit in limits:
                key = limit.attribute.short_name
                posted = request.POST.get(f"attr_{key}", limit.min_value)
                attrs[key] = max(0, int(posted or 0))
            state["phase_1"] = {"attributes": attrs}
        elif phase == 2:
            skills_data: dict[str, int] = {}
            for skill in Skill.objects.order_by("name"):
                posted = int(request.POST.get(f"skill_{skill.slug}", "0") or 0)
                if posted > 0:
                    skills_data[skill.slug] = posted

            language_data: dict[str, dict] = {}
            for language in Language.objects.order_by("name"):
                level = int(request.POST.get(f"lang_{language.slug}_level", "0") or 0)
                write = bool(request.POST.get(f"lang_{language.slug}_write"))
                mother = bool(request.POST.get(f"lang_{language.slug}_mother"))
                if mother:
                    level = min(3, language.max_level)
                if level > 0 or write or mother:
                    language_data[language.slug] = {
                        "level": level,
                        "write": write,
                        "mother": mother,
                    }
            state["phase_2"] = {"skills": skills_data, "languages": language_data}
        elif phase == 3:
            disadvantages: dict[str, int] = {}
            for trait in Trait.objects.filter(trait_type=Trait.TraitType.DIS).order_by("name"):
                level = int(request.POST.get(f"dis_{trait.slug}", "0") or 0)
                if level > 0:
                    disadvantages[trait.slug] = level
            state["phase_3"] = {"disadvantages": disadvantages}
        elif phase == 4:
            advantages: dict[str, int] = {}
            for trait in Trait.objects.filter(trait_type=Trait.TraitType.ADV).order_by("name"):
                level = int(request.POST.get(f"adv_{trait.slug}", "0") or 0)
                if level > 0:
                    advantages[trait.slug] = level

            attribute_adds: dict[str, int] = {}
            for short_name, _label in ATTRIBUTE_ORDER:
                add = int(request.POST.get(f"attr_add_{short_name}", "0") or 0)
                if add > 0:
                    attribute_adds[short_name] = add

            skill_adds: dict[str, int] = {}
            for skill in Skill.objects.order_by("name"):
                add = int(request.POST.get(f"skill_add_{skill.slug}", "0") or 0)
                if add > 0:
                    skill_adds[skill.slug] = add

            language_adds: dict[str, int] = {}
            language_write_adds: dict[str, bool] = {}
            for language in Language.objects.order_by("name"):
                add = int(request.POST.get(f"lang_add_{language.slug}", "0") or 0)
                if add > 0:
                    language_adds[language.slug] = add
                write_add = bool(request.POST.get(f"lang_add_{language.slug}_write"))
                if write_add:
                    language_write_adds[language.slug] = True

            schools: dict[str, int] = {}
            for school in School.objects.order_by("name"):
                level = int(request.POST.get(f"school_{school.id}", "0") or 0)
                if level > 0:
                    schools[str(school.id)] = level

            state["phase_4"] = {
                "advantages": advantages,
                "attribute_adds": attribute_adds,
                "skill_adds": skill_adds,
                "language_adds": language_adds,
                "language_write_adds": language_write_adds,
                "schools": schools,
            }

        draft.state = state
        draft.save(update_fields=["state"])
        engine = CharacterCreationEngine(draft)

        phase_validators = {
            1: engine.validate_phase_1,
            2: engine.validate_phase_2,
            3: engine.validate_phase_3,
            4: engine.validate_phase_4,
        }

        if action == "back":
            draft.current_phase = max(1, phase - 1)
            draft.save(update_fields=["current_phase"])
            return redirect(f"{reverse_lazy('create_character')}?draft={draft.id}")

        if action == "next":
            if phase_validators[phase]():
                draft.current_phase = min(4, phase + 1)
                draft.save(update_fields=["current_phase"])
            else:
                messages.error(request, f"Phase {phase} ist ungültig. Bitte Punktverteilung prüfen.")
            return redirect(f"{reverse_lazy('create_character')}?draft={draft.id}")

        if action == "finalize":
            if all([engine.validate_phase_1(), engine.validate_phase_2(), engine.validate_phase_3(), engine.validate_phase_4()]):
                try:
                    character = engine.finalize_character()
                    return redirect("character_sheet", character_id=character.id)
                except ValueError as exc:
                    messages.error(request, str(exc))
            else:
                messages.error(request, "Charakter kann nicht finalisiert werden. Mindestens eine Phase ist ungültig.")
            return redirect(f"{reverse_lazy('create_character')}?draft={draft.id}")

    form = CharacterCreateForm()
    if not draft:
        return render(request, "charsheet/create_character.html", {"form": form})

    engine = CharacterCreationEngine(draft)
    limits = engine.attribute_min_max_limits()
    phase_1_values = engine.phase_1_attributes()
    phase_1_rows = []
    for short_name, label in ATTRIBUTE_ORDER:
        lim = limits.get(short_name, {"min": 0, "max": 0})
        value = phase_1_values.get(short_name, lim["min"])
        phase_1_rows.append(
            {
                "short_name": short_name,
                "label": label,
                "min": lim["min"],
                "max": lim["max"],
                "value": value,
                "cost": engine.calc_attribute_cost(value, lim["max"]) if lim["max"] else 0,
            }
        )

    phase_2_skills = engine.phase_2_skills()
    phase_2_languages = engine.phase_2_languages()
    phase_2_skill_rows = []
    for skill in Skill.objects.select_related("category").order_by("category__name", "name"):
        value = phase_2_skills.get(skill.slug, 0)
        description = (skill.description or "").replace("\r\n", "\n").replace("\r", "\n")
        phase_2_skill_rows.append(
            {
                "slug": skill.slug,
                "name": skill.name,
                "category_name": skill.category.name,
                "category_slug": skill.category.slug,
                "description": description,
                "value": value,
                "cost": engine.calc_skill_cost(value) if value > 0 else 0,
            }
        )
    phase_2_language_rows = []
    for language in Language.objects.order_by("name"):
        entry = phase_2_languages.get(language.slug, {"level": 0, "write": False, "mother": False})
        phase_2_language_rows.append(
            {
                "slug": language.slug,
                "name": language.name,
                "max_level": language.max_level,
                "level": entry.get("level", 0),
                "write": entry.get("write", False),
                "mother": entry.get("mother", False),
                "cost": engine.calc_language_cost(entry.get("level", 0), entry.get("write", False), entry.get("mother", False)),
            }
        )

    phase_3_values = engine.phase_3_disadvantages()
    phase_3_rows = []
    for trait in Trait.objects.filter(trait_type=Trait.TraitType.DIS).order_by("name"):
        description = (trait.description or "").replace("\r\n", "\n").replace("\r", "\n")
        phase_3_rows.append(
            {
                "slug": trait.slug,
                "name": trait.name,
                "min_level": trait.min_level,
                "max_level": trait.max_level,
                "points_per_level": trait.points_per_level,
                "description": description,
                "value": phase_3_values.get(trait.slug, 0),
            }
        )

    phase_4_values = engine.phase_4_advantages()
    phase_4_attr_adds = engine.phase_4_attribute_adds()
    phase_4_skill_adds = engine.phase_4_skill_adds()
    phase_4_lang_adds = engine.phase_4_language_adds()
    phase_4_lang_write_adds = engine.phase_4_language_write_adds()
    phase_4_schools = engine.phase_4_schools()
    phase_1_attr_values = engine.phase_1_attributes()
    phase_1_limits = engine.attribute_min_max_limits()
    phase_2_skill_values = engine.phase_2_skills()
    phase_2_language_values = engine.phase_2_languages()

    phase_4_adv_rows = []
    for trait in Trait.objects.filter(trait_type=Trait.TraitType.ADV).order_by("name"):
        description = (trait.description or "").replace("\r\n", "\n").replace("\r", "\n")
        phase_4_adv_rows.append(
            {
                "slug": trait.slug,
                "name": trait.name,
                "min_level": trait.min_level,
                "max_level": trait.max_level,
                "points_per_level": trait.points_per_level,
                "description": description,
                "value": phase_4_values.get(trait.slug, 0),
            }
        )

    phase_4_attr_rows = []
    for short_name, label in ATTRIBUTE_ORDER:
        limits = phase_1_limits.get(short_name, {"min": 0, "max": 0})
        base_value = phase_1_attr_values.get(short_name, limits["min"])
        add_value = phase_4_attr_adds.get(short_name, 0)
        phase_4_attr_rows.append(
            {
                "short_name": short_name,
                "label": label,
                "base_value": base_value,
                "max_value": limits["max"],
                "value": add_value,
            }
        )
    phase_4_skill_rows = []
    for skill in Skill.objects.order_by("name"):
        description = (skill.description or "").replace("\r\n", "\n").replace("\r", "\n")
        phase_4_skill_rows.append(
            {
                "slug": skill.slug,
                "name": skill.name,
                "base_level": phase_2_skill_values.get(skill.slug, 0),
                "description": description,
                "value": phase_4_skill_adds.get(skill.slug, 0),
            }
        )
    phase_4_language_rows = []
    for language in Language.objects.order_by("name"):
        base_payload = phase_2_language_values.get(language.slug, {"level": 0, "write": False, "mother": False})
        phase_4_language_rows.append(
            {
                "slug": language.slug,
                "name": language.name,
                "max_level": language.max_level,
                "base_level": int(base_payload.get("level", 0) or 0),
                "base_write": bool(base_payload.get("write", False)),
                "base_mother": bool(base_payload.get("mother", False)),
                "write_add": bool(phase_4_lang_write_adds.get(language.slug, False)),
                "value": phase_4_lang_adds.get(language.slug, 0),
            }
        )
    phase_4_school_rows = []
    for school in School.objects.order_by("name"):
        description = (school.description or "").replace("\r\n", "\n").replace("\r", "\n")
        phase_4_school_rows.append(
            {
                "id": school.id,
                "name": school.name,
                "description": description,
                "value": phase_4_schools.get(str(school.id), 0),
            }
        )

    return render(
        request,
        "charsheet/create_character.html",
        {
            "draft": draft,
            "draft_phase": draft.current_phase,
            "meta": draft.state.get("meta", {}),
            "phase_1_rows": phase_1_rows,
            "phase_1_spent": engine.sum_phase_1_attribute_costs(),
            "phase_2_skill_rows": phase_2_skill_rows,
            "phase_2_language_rows": phase_2_language_rows,
            "phase_2_skill_spent": engine.sum_phase_2_skill_cost(),
            "phase_2_language_spent": engine.sum_phase_2_language_cost(),
            "phase_3_rows": phase_3_rows,
            "phase_3_spent": engine.sum_phase_3_disadvantage_cost(),
            "phase_4_adv_rows": phase_4_adv_rows,
            "phase_4_attr_rows": phase_4_attr_rows,
            "phase_4_skill_rows": phase_4_skill_rows,
            "phase_4_language_rows": phase_4_language_rows,
            "phase_4_school_rows": phase_4_school_rows,
            "phase_4_spent": engine.sum_phase_4_total_cost(),
            "phase_4_budget": engine.calculate_phase_4_budget(),
            "phase_4_adv_spent": engine.sum_phase_4_advantages_cost(),
            "phase_4_adv_budget": engine.calculate_phase_4_advantages_budget(),
            "phase_4_rest_spent": engine.sum_phase_4_rest_cost(),
            "phase_4_rest_budget": engine.calculate_phase_4_rest_budget(),
            "phase_validity": {
                1: engine.validate_phase_1(),
                2: engine.validate_phase_2(),
                3: engine.validate_phase_3(),
                4: engine.validate_phase_4(),
            },
            "race": draft.race,
        },
    )

@login_required
@require_POST
def toggle_equip(request, pk):
    """Toggle equipped state for one armor, shield, or weapon inventory entry."""
    ci = _owned_character_item_or_404(request, pk)

    if ci.item.item_type not in (Item.ItemType.ARMOR, Item.ItemType.SHIELD, Item.ItemType.WEAPON):
        return redirect("character_sheet", character_id=ci.owner_id)

    ci.equipped = not ci.equipped
    ci.save(update_fields=["equipped"])

    return redirect("character_sheet", character_id=ci.owner_id)


@login_required
@require_POST
def consume_item(request, pk):
    """Consume one unit from a stackable inventory item."""
    ci = _owned_character_item_or_404(request, pk)

    owner_id = ci.owner_id
    if not ci.item.stackable or ci.item.item_type != Item.ItemType.CONSUM:
        return redirect("character_sheet", character_id=owner_id)

    if ci.amount > 1:
        ci.amount -= 1
        ci.save(update_fields=["amount"])
    else:
        ci.delete()

    return redirect("character_sheet", character_id=owner_id)


@login_required
@require_POST
def remove_item(request, pk):
    """Remove one unit or full stack from inventory, then redirect back to sheet."""
    ci = _owned_character_item_or_404(request, pk)

    owner_id = ci.owner_id
    remove_all = str(request.POST.get("all", "0")).lower() in {"1", "true", "on", "yes"}
    if remove_all:
        ci.delete()
    elif ci.item.stackable and ci.amount > 1:
        ci.amount -= 1
        ci.save(update_fields=["amount"])
    else:
        ci.delete()

    return redirect("character_sheet", character_id=owner_id)


@login_required
@require_POST
def adjust_current_damage(request, character_id: int):
    """Increase or decrease current damage and return updated damage state."""
    character = _owned_character_or_404(request, character_id)
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


@login_required
@require_POST
def adjust_money(request, character_id: int):
    """Apply a signed money delta while keeping balance non-negative."""
    character = _owned_character_or_404(request, character_id)
    try:
        delta = int(request.POST.get("delta", "0"))
    except (TypeError, ValueError):
        delta = 0

    if delta:
        character.money = max(0, character.money + delta)
        character.save(update_fields=["money"])

    return redirect("character_sheet", character_id=character_id)


@login_required
@require_POST
def adjust_experience(request, character_id: int):
    """Apply an experience delta to current and overall experience."""
    character = _owned_character_or_404(request, character_id)
    try:
        delta = int(request.POST.get("delta", "0"))
    except (TypeError, ValueError):
        delta = 0

    if delta:
        character.current_experience = max(0, character.current_experience + delta)
        character.overall_experience = max(0, character.overall_experience + delta)
        character.save(update_fields=["current_experience", "overall_experience"])

    return redirect("character_sheet", character_id=character_id)


@login_required
@require_POST
def apply_learning(request, character_id: int):
    """Apply learn-menu upgrades by spending current experience points."""
    character = _owned_character_or_404(request, character_id)

    def read_int(name: str, default: int = 0) -> int:
        try:
            return int(request.POST.get(name, str(default)))
        except (TypeError, ValueError):
            return default

    attribute_limits = {
        limit.attribute.short_name: {
            "min": int(limit.min_value),
            "max": int(limit.max_value),
        }
        for limit in character.race.raceattributelimit_set.select_related("attribute")
    }
    attribute_rows = {
        row.attribute.short_name: row
        for row in CharacterAttribute.objects.filter(character=character).select_related("attribute")
    }
    skill_defs = {skill.slug: skill for skill in Skill.objects.all()}
    skill_rows = {
        row.skill.slug: row
        for row in CharacterSkill.objects.filter(character=character).select_related("skill")
    }
    language_defs = {lang.slug: lang for lang in Language.objects.all()}
    language_rows = {
        row.language.slug: row
        for row in CharacterLanguage.objects.filter(owner=character).select_related("language")
    }
    school_defs = {str(school.id): school for school in School.objects.all()}
    school_rows = {
        str(row.school_id): row
        for row in CharacterSchool.objects.filter(character=character)
    }
    school_level_caps = _school_max_levels()
    total_cost = 0
    attr_plan: dict[str, int] = {}
    skill_plan: dict[str, int] = {}
    lang_plan: dict[str, dict[str, object]] = {}
    school_plan: dict[str, int] = {}

    if any(key.startswith("learn_adv_target_") for key in request.POST.keys()):
        messages.error(request, "Vorteile können nicht über EP gelernt werden.")
        return redirect("character_sheet", character_id=character.id)

    for short_name, bounds in attribute_limits.items():
        key = f"learn_attr_add_{short_name}"
        if key not in request.POST:
            continue
        add = read_int(key, 0)
        base_row = attribute_rows.get(short_name)
        base_value = int(base_row.base_value if base_row else 0)
        target_value = base_value + add
        min_value = int(bounds["min"])
        max_value = int(bounds["max"])
        if target_value < min_value:
            messages.error(request, f"{short_name}: Zielwert ist unter dem Minimum.")
            return redirect("character_sheet", character_id=character.id)
        if target_value > max_value:
            messages.error(request, f"{short_name}: Zielwert ist über dem Maximum.")
            return redirect("character_sheet", character_id=character.id)
        if add == 0:
            continue
        step_cost = _calc_attribute_total_cost(target_value, max_value) - _calc_attribute_total_cost(base_value, max_value)
        total_cost += step_cost
        attr_plan[short_name] = add

    for slug in skill_defs.keys():
        key = f"learn_skill_add_{slug}"
        if key not in request.POST:
            continue
        add = read_int(key, 0)
        base_value = int(skill_rows.get(slug).level if slug in skill_rows else 0)
        target_value = base_value + add
        if target_value < 0:
            messages.error(request, f"{skill_defs[slug].name}: Zielwert ist unter 0.")
            return redirect("character_sheet", character_id=character.id)
        if target_value > 10:
            messages.error(request, f"{skill_defs[slug].name}: Zielwert ist über 10.")
            return redirect("character_sheet", character_id=character.id)
        if add == 0:
            continue
        step_cost = _calc_skill_total_cost(target_value) - _calc_skill_total_cost(base_value)
        total_cost += step_cost
        skill_plan[slug] = add

    for slug, lang in language_defs.items():
        add_key = f"learn_lang_add_{slug}"
        write_key = f"learn_lang_write_{slug}"
        if add_key not in request.POST and write_key not in request.POST:
            continue
        add = read_int(add_key, 0)
        write_add = str(request.POST.get(write_key, "0")) in {"1", "true", "on"}
        base_row = language_rows.get(slug)
        base_level = int(base_row.levels if base_row else 0)
        base_write = bool(base_row.can_write if base_row else False)
        base_mother = bool(base_row.is_mother_tongue if base_row else False)
        target_level = base_level + add
        target_write = base_write or write_add
        if base_mother and target_level != int(lang.max_level):
            messages.error(request, f"{lang.name}: Muttersprache kann nicht unter Maximallevel reduziert werden.")
            return redirect("character_sheet", character_id=character.id)
        if target_level < 0:
            messages.error(request, f"{lang.name}: Zielwert ist unter 0.")
            return redirect("character_sheet", character_id=character.id)
        if target_level > int(lang.max_level):
            messages.error(request, f"{lang.name}: Zielwert ist über dem Maximum.")
            return redirect("character_sheet", character_id=character.id)
        if target_write and target_level < 1:
            messages.error(request, f"{lang.name}: Schreiben benötigt mindestens Level 1.")
            return redirect("character_sheet", character_id=character.id)
        if add == 0 and not write_add:
            continue
        step_cost = _calc_language_total_cost(target_level, target_write, base_mother) - _calc_language_total_cost(base_level, base_write, base_mother)
        total_cost += step_cost
        lang_plan[slug] = {"add": add, "write_add": write_add}

    for school_id in school_defs.keys():
        key = f"learn_school_add_{school_id}"
        if key not in request.POST:
            continue
        add = read_int(key, 0)
        base_level = int(school_rows.get(school_id).level if school_id in school_rows else 0)
        target_level = base_level + add
        max_level = max(base_level, int(school_level_caps.get(int(school_id), DEFAULT_SCHOOL_MAX_LEVEL)))
        if target_level < 0:
            messages.error(request, f"{school_defs[school_id].name}: Zielwert ist unter 0.")
            return redirect("character_sheet", character_id=character.id)
        if target_level > max_level:
            messages.error(request, f"{school_defs[school_id].name}: Zielwert ist über dem Maximum.")
            return redirect("character_sheet", character_id=character.id)
        if add == 0:
            continue
        total_cost += add * 8
        school_plan[school_id] = add

    if total_cost == 0:
        messages.info(request, "Keine Lernkosten erkannt.")
        return redirect("character_sheet", character_id=character.id)

    if total_cost > int(character.current_experience):
        messages.error(request, "Nicht genug aktuelle EP für diese Lernkosten.")
        return redirect("character_sheet", character_id=character.id)

    with transaction.atomic():
        for short_name, add in attr_plan.items():
            attr_row = attribute_rows.get(short_name)
            if attr_row is None:
                continue
            attr_row.base_value = int(attr_row.base_value) + add
            attr_row.save(update_fields=["base_value"])

        for slug, add in skill_plan.items():
            skill = skill_defs[slug]
            skill_row = skill_rows.get(slug)
            if skill_row is None:
                if add <= 0:
                    continue
                skill_row = CharacterSkill.objects.create(character=character, skill=skill, level=add)
                skill_rows[slug] = skill_row
            else:
                target_level = int(skill_row.level) + add
                if target_level <= 0:
                    skill_row.delete()
                    skill_rows.pop(slug, None)
                else:
                    skill_row.level = target_level
                    skill_row.save(update_fields=["level"])

        for slug, payload in lang_plan.items():
            add = int(payload["add"])
            write_add = bool(payload["write_add"])
            lang_row = language_rows.get(slug)
            if lang_row is None:
                if add < 1:
                    continue
                lang_row = CharacterLanguage.objects.create(
                    owner=character,
                    language=language_defs[slug],
                    levels=add,
                    can_write=write_add,
                    is_mother_tongue=False,
                )
                language_rows[slug] = lang_row
            else:
                target_level = int(lang_row.levels) + add
                target_write = bool(lang_row.can_write) or write_add
                if target_level <= 0 and not target_write and not bool(lang_row.is_mother_tongue):
                    lang_row.delete()
                    language_rows.pop(slug, None)
                    continue
                lang_row.levels = target_level
                if write_add:
                    lang_row.can_write = True
                lang_row.save(update_fields=["levels", "can_write"])

        for school_id, add in school_plan.items():
            school_row = school_rows.get(school_id)
            if school_row is None:
                if add <= 0:
                    continue
                school_row = CharacterSchool.objects.create(
                    character=character,
                    school=school_defs[school_id],
                    level=add,
                )
                school_rows[school_id] = school_row
            else:
                target_level = int(school_row.level) + add
                if target_level <= 0:
                    school_row.delete()
                    school_rows.pop(school_id, None)
                else:
                    school_row.level = target_level
                    school_row.save(update_fields=["level"])

        character.current_experience = max(0, int(character.current_experience) - total_cost)
        character.save(update_fields=["current_experience"])

    request.session["close_learn_window_once"] = True
    if total_cost > 0:
        messages.success(request, f"Lernen abgeschlossen: {total_cost} EP ausgegeben.")
    else:
        messages.success(request, f"Lernen abgeschlossen: {-total_cost} EP gutgeschrieben.")
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def create_shop_item(request, character_id: int):
    """Create a custom shop item and optional armor or weapon detail records."""
    character = _owned_character_or_404(request, character_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return redirect("character_sheet", character_id=character.id)

    def read_int(name: str, default: int = 0, *, minimum: int | None = None) -> int:
        try:
            value = int(request.POST.get(name, str(default)) or default)
        except (TypeError, ValueError):
            value = default
        if minimum is not None:
            value = max(minimum, value)
        return value

    def read_quality(name: str, default: str) -> str:
        raw_quality = str(request.POST.get(name, default) or default)
        return ItemEngine.normalize_quality(raw_quality)

    price = read_int("price", 0, minimum=0)
    item_type = (request.POST.get("item_type") or Item.ItemType.MISC).strip()
    description = (request.POST.get("description") or "").strip()
    stackable = bool(request.POST.get("stackable"))
    default_quality = read_quality("default_quality", ItemEngine.normalize_quality(None))
    weight = read_int("weight", 0, minimum=0)
    size_class = str(request.POST.get("size_class") or "M")
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
            armor_mode = (request.POST.get("armor_mode") or "total").strip()
            armor_encumbrance = read_int("armor_encumbrance", 0, minimum=0)
            armor_min_st = read_int("armor_min_st", 1, minimum=1)
            if armor_mode == "zones":
                armor_stats = ArmorStats(
                    item=item,
                    rs_total=0,
                    rs_head=read_int("armor_rs_head", 0, minimum=0),
                    rs_torso=read_int("armor_rs_torso", 0, minimum=0),
                    rs_arm_left=read_int("armor_rs_arm_left", 0, minimum=0),
                    rs_arm_right=read_int("armor_rs_arm_right", 0, minimum=0),
                    rs_leg_left=read_int("armor_rs_leg_left", 0, minimum=0),
                    rs_leg_right=read_int("armor_rs_leg_right", 0, minimum=0),
                    encumbrance=armor_encumbrance,
                    min_st=armor_min_st,
                )
            else:
                armor_stats = ArmorStats(
                    item=item,
                    rs_total=read_int("armor_rs_total", 0, minimum=0),
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
            min_st = read_int("weapon_min_st", 1, minimum=1)
            damage_source_id = read_int("weapon_damage_source", 0, minimum=0)
            wield_mode = str(request.POST.get("weapon_wield_mode") or "1h")
            h2_enabled = wield_mode in {"2h", "vh"}
            damage_source = DamageSource.objects.get(pk=damage_source_id)
            weapon_stats = WeaponStats(
                item=item,
                damage_source=damage_source,
                min_st=min_st,
                damage_dice_amount=read_int("weapon_damage_dice_amount", 1, minimum=1),
                damage_dice_faces=read_int("weapon_damage_dice_faces", 10, minimum=2),
                damage_flat_bonus=read_int("weapon_damage_flat_bonus", 0, minimum=0),
                wield_mode=wield_mode,
                h2_dice_amount=read_int("weapon_h2_dice_amount", 0, minimum=1) if h2_enabled else None,
                h2_dice_faces=read_int("weapon_h2_dice_faces", 0, minimum=2) if h2_enabled else None,
                h2_flat_bonus=read_int("weapon_h2_flat_bonus", 0, minimum=0) if h2_enabled else None,
            )
            weapon_stats.full_clean()
            weapon_stats.save()
        elif item.item_type == Item.ItemType.SHIELD:
            shield_stats = ShieldStats(
                item=item,
                rs=read_int("shield_rs", 0, minimum=0),
                encumbrance=read_int("shield_encumbrance", 0, minimum=0),
                min_st=read_int("shield_min_st", 1, minimum=1),
            )
            shield_stats.full_clean()
            shield_stats.save()
    except (ValidationError, ValueError, DamageSource.DoesNotExist):
        if item.pk:
            item.delete()

    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def buy_shop_cart(request, character_id: int):
    """Buy all cart entries atomically and update inventory plus wallet."""
    character = _owned_character_or_404(request, character_id)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    cart_items = payload.get("items") or []
    discount = payload.get("discount") or 0
    try:
        discount_percent = max(-100, min(100, int(discount)))
    except (TypeError, ValueError):
        discount_percent = 0

    if not isinstance(cart_items, list) or not cart_items:
        return JsonResponse({"ok": False, "error": "empty_cart"}, status=400)

    normalized: list[tuple[Item, int, str]] = []
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
        quality = ItemEngine.normalize_quality(str(entry.get("quality") or item.default_quality))
        if not item.stackable and qty != 1:
            return JsonResponse({"ok": False, "error": "non_stackable_qty"}, status=400)
        normalized.append((item, qty, quality))
        subtotal += ItemEngine.price_for_item_and_quality(item, quality) * qty

    final_price = max(0, round(subtotal * (100 - discount_percent) / 100))
    if final_price > character.money:
        return JsonResponse({"ok": False, "error": "insufficient_funds"}, status=200)

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
                for _ in range(qty):
                    created = CharacterItem(owner=character, item=item, amount=1, equipped=False, quality=quality)
                    created.full_clean()
                    created.save()

    return JsonResponse({"ok": True, "new_money": character.money, "spent": final_price}, status=200)


def impressum(request):
    """Render imprint page using configurable operator metadata."""
    return render(request, "legal/impressum.html", _legal_context())


def datenschutz(request):
    """Render privacy page with minimal data-processing information."""
    return render(request, "legal/datenschutz.html", _legal_context())
