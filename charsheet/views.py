from __future__ import annotations
import json
import random
from datetime import date as date_cls
from django.conf import settings
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
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from .engine import CharacterCreationEngine
from .engine.dice_engine import DiceEngine
from .models import (
    Character,
    CharacterDiaryEntry,
    CharacterItem,
    CharacterLanguage,
    CharacterSkill,
    CharacterTechnique,
    CharacterCreationDraft,
    Item,
    Language,
    Rune,
    School,
    Skill,
    Technique,
    Trait,
)
from .models.user import UserSettings
from .forms import (
    AccountSettingsForm,
    CharacterCreateForm,
    CharacterUpdateForm,
    CharacterInfoInlineForm,
    CharacterSkillSpecificationForm,
    CharacterTechniqueSpecificationForm,
    UserSettingsForm
)
from .constants import ATTRIBUTE_ORDER
from .learning import process_learning_submission
from .sheet_context import build_character_sheet_context
from .shop import buy_shop_cart as buy_shop_cart_payload
from .shop import create_custom_shop_item
from .view_utils import format_thousands


DIARY_ENTRY_CHAR_LIMIT = 2200
SHEET_PARTIAL_TEMPLATES = {
    "load_panel": ("sheetLoadPanel", "charsheet/partials/_load_panel.html"),
    "core_stats_panel": ("sheetCoreStatsPanel", "charsheet/partials/_core_stats_panel.html"),
    "damage_panel": ("sheetDamagePanel", "charsheet/partials/_damage_panel.html"),
    "wallet_panel": ("sheetWalletPanel", "charsheet/partials/_wallet_panel.html"),
    "experience_panel": ("sheetExperiencePanel", "charsheet/partials/_experience_panel.html"),
    "fame_panel": ("sheetFamePanel", "charsheet/partials/_fame_panel.html"),
    "inventory_panel": ("sheetInventoryPanel", "charsheet/partials/_inventory_panel.html"),
    "armor_panel": ("sheetArmorPanel", "charsheet/partials/_armor_panel.html"),
    "weapon_panel": ("sheetWeaponPanel", "charsheet/partials/_weapon_table.html"),
    "learning_budget": ("learnBudgetPanel", "charsheet/partials/_learning_budget.html"),
}


@login_required
@require_POST
def update_account_settings(request):
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

    account_form = AccountSettingsForm(request.user, request.POST)
    settings_form = UserSettingsForm(request.POST, instance=user_settings)

    account_valid = account_form.is_valid()
    settings_valid = settings_form.is_valid()

    if not account_valid or not settings_valid:
        for field_errors in account_form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        for field_errors in settings_form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return redirect("dashboard")

    changed, password_changed = account_form.save()
    settings_changed = settings_form.has_changed()
    settings_form.save()

    if password_changed:
        update_session_auth_hash(request, request.user)

    if changed or settings_changed:
        messages.success(request, "Kontoeinstellungen gespeichert.")
    else:
        messages.info(request, "Keine Änderungen erkannt.")

    return redirect("dashboard")


@require_POST
def roll_dice_view(request):
    try:
        data = json.loads(request.body or "{}")
        sides = int(data.get("sides", 10))
        count = int(data.get("count", 2))

        if sides < 2 or count < 1:
            return JsonResponse(
                {"error": "Invalid dice configuration."},
                status=400,
            )

        engine = DiceEngine(dice_sides=sides, dice_rolls=count)
        result = engine.roll()

        return JsonResponse(result)

    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid request body."},
            status=400,
        )


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
        CharacterItem.objects.select_related("item", "owner").prefetch_related("item__runes", "runes"),
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


def _owned_character_skill_or_404(request, character_id: int, character_skill_id: int) -> tuple[Character, CharacterSkill]:
    """Return one learned skill row that belongs to one owned character."""
    character = _owned_character_or_404(request, character_id)
    character_skill = get_object_or_404(
        CharacterSkill.objects.select_related("character", "skill"),
        pk=character_skill_id,
        character=character,
    )
    return character, character_skill


def _owned_technique_for_character_or_404(
    request,
    character_id: int,
    technique_id: int,
) -> tuple[Character, Technique]:
    """Return one technique that belongs to one owned character's learned schools."""
    character = _owned_character_or_404(request, character_id)
    technique = get_object_or_404(
        Technique.objects.select_related("school", "path"),
        pk=technique_id,
        school_id__in=character.schools.values_list("school_id", flat=True),
    )
    return character, technique


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


def _is_partial_request(request) -> bool:
    """Return whether the caller expects JSON-wrapped rendered partials."""
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
        or request.POST.get("ajax") == "1"
    )


def _build_sheet_context_for_request(request, character: Character, *, close_learn_window_once: bool = False) -> dict[str, object]:
    """Build the full sheet context including request-specific dice settings."""
    context = build_character_sheet_context(
        character,
        close_learn_window_once=close_learn_window_once,
    )
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
    context["dddice_enabled"] = user_settings.dddice_enabled
    context["dddice_config"] = {
        "apiKey": user_settings.dddice_api_key,
        "roomId": user_settings.dddice_room_id,
        "roomPassword": user_settings.dddice_room_password,
        "themeId": user_settings.dddice_theme_id,
    }
    context["request"] = request
    return context


def _sheet_partials_response(request, character: Character, *partial_keys: str) -> JsonResponse:
    """Render one or more server-truth sheet partials for targeted DOM replacement."""
    context = _build_sheet_context_for_request(request, character)
    partials: list[dict[str, str]] = []
    for key in partial_keys:
        target_id, template_name = SHEET_PARTIAL_TEMPLATES[key]
        partials.append(
            {
                "target": target_id,
                "html": render_to_string(template_name, context, request=request),
            }
        )
    return JsonResponse({"ok": True, "partials": partials})


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
    context = _build_sheet_context_for_request(
        request,
        character,
        close_learn_window_once=bool(request.session.pop("close_learn_window_once", False)),
    )

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
    if _is_partial_request(request):
        return _sheet_partials_response(request, character, "fame_panel")
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
@require_POST
def update_skill_specification(request, character_id: int, character_skill_id: int):
    """Persist the specification text for one learned skill from the character sheet."""
    character, character_skill = _owned_character_skill_or_404(request, character_id, character_skill_id)
    if not character_skill.skill.requires_specification:
        messages.error(request, "Diese Fertigkeit besitzt keine Spezifikation.")
        return redirect("character_sheet", character_id=character.id)

    form = CharacterSkillSpecificationForm(request.POST, instance=character_skill)
    if form.is_valid():
        form.save()
        messages.success(request, f"{character_skill.skill.name} wurde aktualisiert.")
    else:
        messages.error(request, "Die Spezifikation konnte nicht gespeichert werden.")
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def update_technique_specification(request, character_id: int, technique_id: int):
    """Persist the specification text for one learned technique from the character sheet."""
    character, technique = _owned_technique_for_character_or_404(
        request,
        character_id,
        technique_id,
    )
    if not technique.has_specification:
        messages.error(request, "Diese Technik besitzt keine Spezifikation.")
        return redirect("character_sheet", character_id=character.id)

    character_technique, _created = CharacterTechnique.objects.get_or_create(
        character=character,
        technique=technique,
    )
    form = CharacterTechniqueSpecificationForm(request.POST, instance=character_technique)
    if form.is_valid():
        form.save()
        messages.success(request, f"{technique.name} wurde aktualisiert.")
    else:
        messages.error(request, "Die Technik-Spezifikation konnte nicht gespeichert werden.")
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
        "character_count_display": format_thousands(len(characters)),
        "total_money": totals.get("total_money") or 0,
        "total_money_display": format_thousands(int(totals.get("total_money") or 0)),
        "equipped_item_count": equipped_item_count,
        "equipped_item_count_display": format_thousands(equipped_item_count),
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
                "points_display": trait.cost_display(),
                "points_by_level": list(trait.cost_curve()),
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
                "points_display": trait.cost_display(),
                "points_by_level": list(trait.cost_curve()),
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

    if ci.equip_locked:
        if not ci.equipped:
            ci.equipped = True
            ci.save(update_fields=["equipped"])
    else:
        ci.equipped = not ci.equipped
        ci.save(update_fields=["equipped"])
    if _is_partial_request(request):
        return _sheet_partials_response(
            request,
            ci.owner,
            "load_panel",
            "core_stats_panel",
            "inventory_panel",
            "armor_panel",
            "weapon_panel",
        )

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
    if _is_partial_request(request):
        character = _owned_character_or_404(request, owner_id)
        return _sheet_partials_response(request, character, "inventory_panel")

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
    if _is_partial_request(request):
        character = _owned_character_or_404(request, owner_id)
        return _sheet_partials_response(request, character, "inventory_panel")

    return redirect("character_sheet", character_id=owner_id)


@login_required
@require_POST
def adjust_current_damage(request, character_id: int):
    """Increase or decrease current damage and return updated damage partials."""
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

    if _is_partial_request(request):
        return _sheet_partials_response(request, character, "damage_panel")

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

    if _is_partial_request(request):
        return _sheet_partials_response(request, character, "wallet_panel")
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

    if _is_partial_request(request):
        return _sheet_partials_response(request, character, "experience_panel", "learning_budget")
    return redirect("character_sheet", character_id=character_id)


@login_required
@require_POST
def apply_learning(request, character_id: int):
    """Apply learn-menu upgrades by spending current experience points."""
    character = _owned_character_or_404(request, character_id)

    level, message = process_learning_submission(character, request.POST)
    request.session["close_learn_window_once"] = True
    if level == "error":
        messages.error(request, message)
    elif level == "info":
        messages.info(request, message)
    else:
        messages.success(request, message)
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def create_shop_item(request, character_id: int):
    """Create a custom shop item and optional armor or weapon detail records."""
    character = _owned_character_or_404(request, character_id)
    create_custom_shop_item(request.POST)
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def update_character_item_runes(request, pk: int):
    """Persist rune retrofits for one owned supported inventory entry."""
    character_item = _owned_character_item_or_404(request, pk)
    if character_item.item.item_type not in {Item.ItemType.WEAPON, Item.ItemType.ARMOR, Item.ItemType.MISC}:
        return redirect("character_sheet", character_id=character_item.owner_id)

    selected_ids = []
    for raw_value in request.POST.getlist("runes"):
        try:
            selected_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue

    base_rune_ids = set(character_item.item.runes.values_list("id", flat=True))
    available_runes = Rune.objects.filter(pk__in=sorted(set(selected_ids))).exclude(pk__in=base_rune_ids)
    character_item.runes.set(available_runes)

    if _is_partial_request(request):
        return _sheet_partials_response(
            request,
            character_item.owner,
            "inventory_panel",
            "armor_panel",
            "weapon_panel",
        )
    return redirect("character_sheet", character_id=character_item.owner_id)


@login_required
@require_POST
def buy_shop_cart(request, character_id: int):
    """Buy all cart entries atomically and update inventory plus wallet."""
    character = _owned_character_or_404(request, character_id)
    payload = _read_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)
    response_payload, status_code = buy_shop_cart_payload(character, payload)
    if response_payload.get("ok"):
        context = _build_sheet_context_for_request(request, character)
        response_payload["partials"] = [
            {
                "target": "sheetWalletPanel",
                "html": render_to_string("charsheet/partials/_wallet_panel.html", context, request=request),
            },
            {
                "target": "sheetInventoryPanel",
                "html": render_to_string("charsheet/partials/_inventory_panel.html", context, request=request),
            },
        ]
    return JsonResponse(response_payload, status=status_code)


def impressum(request):
    """Render imprint page using configurable operator metadata."""
    return render(request, "legal/impressum.html", _legal_context())


def datenschutz(request):
    """Render privacy page with minimal data-processing information."""
    return render(request, "legal/datenschutz.html", _legal_context())
