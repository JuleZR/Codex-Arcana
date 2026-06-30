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
from .engine.creature_engine import CreatureCardEngine, CreatureEngine
from .engine.dice_engine import DiceEngine
from .learning_progression import weapon_mastery_weapon_type_definitions
from .models import (
    Character,
    CharacterDiaryEntry,
    CharacterAspect,
    CharacterDruidCult,
    CharacterShamanPatron,
    CharacterItem,
    CharacterItemRuneSpec,
    CharacterLanguage,
    CharacterSkill,
    CharacterSpell,
    CharacterTechnique,
    CharacterCreationDraft,
    CharacterCreature,
    CharacterCreatureCard,
    CharacterCreatureCardAttributeIncrease,
    CharacterCreatureCardCommand,
    CharacterCreatureCardCommandPrerequisite,
    CharacterCreatureCardTrait,
    Creature,
    CreatureCommand,
    CreatureSpecialSkill,
    CreatureTraitDefinition,
    Aspect,
    CharacterDivineEntity,
    DivineEntity,
    DruidCult,
    DruidCultAspect,
    Item,
    Language,
    Rune,
    School,
    ShamanPatron,
    Skill,

    Technique,
    Trait,
    Quality,
)
from .models.user import UserSettings
from .forms import (
    AccountSettingsForm,
    CharacterCreateForm,
    CharacterUpdateForm,
    CharacterInfoInlineForm,
    CharacterItemRuneSpecForm,
    CharacterSkillSpecificationForm,
    CharacterTechniqueSpecificationForm,
    UserSettingsForm
)
from .constants import ATTRIBUTE_CODE_CHOICES, ATTRIBUTE_ORDER, RESOURCE_KEY_CHOICES, is_allowed_trait_attribute_choice
from .models.creatures import CREATURE_CARD_QUALITY_TRAINING_BUDGETS, CharacterCreatureCardSkill
from .learning import process_learning_submission
from .sheet_context import build_character_sheet_context, build_creature_card_training_context
from .shop import (
    apply_character_item_modifications,
    buy_shop_cart as buy_shop_cart_payload,
    sell_shop_cart as sell_shop_cart_payload,
    trade_shop_cart as trade_shop_cart_payload,
)
from .shop import create_custom_shop_item
from .view_utils import format_modifier, format_thousands


DIARY_ENTRY_CHAR_LIMIT = 2200
SHEET_PARTIAL_TEMPLATES = {
    "character_header": ("sheetCharacterHeader", "charsheet/partials/_character_header.html"),
    "secondary_page": ("sheetSecondaryPage", "charsheet/partials/_sheet_secondary_page.html"),
    "card_hand": ("sheetCardHand", "charsheet/partials/_card_hand_host.html"),
    "load_panel": ("sheetLoadPanel", "charsheet/partials/_load_panel.html"),
    "core_stats_panel": ("sheetCoreStatsPanel", "charsheet/partials/_core_stats_panel.html"),
    "damage_panel": ("sheetDamagePanel", "charsheet/partials/_damage_panel.html"),
    "wallet_panel": ("sheetWalletPanel", "charsheet/partials/_wallet_panel.html"),
    "experience_panel": ("sheetExperiencePanel", "charsheet/partials/_experience_panel.html"),
    "fame_panel": ("sheetFamePanel", "charsheet/partials/_fame_panel.html"),
    "inventory_panel": ("sheetInventoryPanel", "charsheet/partials/_inventory_panel.html"),
    "armor_panel": ("sheetArmorPanel", "charsheet/partials/_armor_panel.html"),
    "weapon_panel": ("sheetWeaponPanel", "charsheet/partials/_weapon_table.html"),
    "spell_panel": ("sheetSpellPanel", "charsheet/partials/_spell_panel.html"),
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
        CharacterItem.objects.select_related("item", "owner").prefetch_related("item__runes", "runes", "item_runes__rune"),
        pk=pk,
        owner__owner=request.user,
    )


def _owned_character_creature_or_404(request, pk: int) -> CharacterCreature:
    """Return one creature instance whose character belongs to the current user."""
    return get_object_or_404(
        CharacterCreature.objects.select_related("owner", "owner__owner", "creature"),
        pk=pk,
        owner__owner=request.user,
    )


def _owned_character_creature_card_or_404(request, pk: int) -> CharacterCreatureCard:
    """Return one concrete creature card whose character belongs to the current user."""
    return get_object_or_404(
        CharacterCreatureCard.objects.select_related("character", "character__owner", "creature", "binding", "quality"),
        pk=pk,
        character__owner=request.user,
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


def _build_sheet_context_for_request(
    request, character: Character, *, close_learn_window_once: bool = False, skip_magic_sync: bool = False
) -> dict[str, object]:
    """Build the full sheet context including request-specific dice settings."""
    skip_magic_sync = skip_magic_sync or request.session.pop("skip_magic_sync_once", False)
    magic_engine = character.get_magic_engine(refresh=True)
    if not skip_magic_sync:
        magic_engine.sync_character_magic()
    magic_engine.normalize_current_arcane_power(persist=True)
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


def _divine_card_can_edit(binding: CharacterDivineEntity) -> bool:
    return bool(binding.entity_id and binding.entity.is_customizable)


def _allowed_divine_card_aspect_ids(binding: CharacterDivineEntity) -> set[int]:
    entity = binding.entity
    if entity.aspect_selection_mode == DivineEntity.AspectSelectionMode.CHOOSE_FROM_ENTITY:
        return set(
            entity.aspects.filter(aspect_id__isnull=False).values_list("aspect_id", flat=True)
        )
    if entity.aspect_selection_mode == DivineEntity.AspectSelectionMode.FREE:
        return set(Aspect.objects.values_list("id", flat=True))
    return set()


def _druid_card_can_edit(binding: CharacterDruidCult) -> bool:
    return bool(binding.cult_id and binding.cult.is_customizable)


def _allowed_druid_card_aspect_ids(binding: CharacterDruidCult) -> set[int]:
    cult = binding.cult
    if cult.aspect_selection_mode == DivineEntity.AspectSelectionMode.CHOOSE_FROM_ENTITY:
        return set(
            cult.aspects.filter(aspect_id__isnull=False).values_list("aspect_id", flat=True)
        )
    if cult.aspect_selection_mode == DivineEntity.AspectSelectionMode.FREE:
        return set(Aspect.objects.values_list("id", flat=True))
    return set()


def _shaman_card_can_edit(binding: CharacterShamanPatron) -> bool:
    return bool(binding.patron_id and binding.patron.is_customizable)


def _allowed_shaman_card_aspect_ids(binding: CharacterShamanPatron) -> set[int]:
    patron = binding.patron
    if patron.aspect_selection_mode == DivineEntity.AspectSelectionMode.CHOOSE_FROM_ENTITY:
        return set(patron.aspects.values_list("id", flat=True))
    if patron.aspect_selection_mode == DivineEntity.AspectSelectionMode.FREE:
        return set(Aspect.objects.values_list("id", flat=True))
    return set()


def _render_shaman_card(request, character: Character) -> str:
    context = _build_sheet_context_for_request(request, character)
    return render_to_string(
        "charsheet/partials/_god_card.html",
        {
            **context,
            "divine_entity": context["selected_shaman_patron"],
            "card_aspects": context["selected_shaman_card_aspects"],
            "selected_divine_card_aspects": context["selected_shaman_card_aspects"],
            "selected_divine_card_image_url": context["selected_shaman_card_image_url"],
            "selected_divine_card_title": context["selected_shaman_card_title"],
            "selected_divine_card_kind_label": context["selected_shaman_card_kind_label"],
            "selected_divine_card_kind_value": context["selected_shaman_card_kind_value"],
            "selected_divine_card_kind_options": context["selected_shaman_card_kind_options"],
            "selected_divine_card_typebar": context["selected_shaman_card_typebar"],
            "selected_divine_card_ability": context["selected_shaman_card_ability"],
            "selected_divine_card_fluff": context["selected_shaman_card_fluff"],
            "selected_divine_card_editable": context["selected_shaman_card_editable"],
            "selected_divine_card_update_url": context["selected_shaman_card_update_url"],
            "selected_divine_card_show_aspect_placeholder": context["selected_shaman_card_show_aspect_placeholder"],
            "selected_divine_card_aspect_placeholders": context["selected_shaman_card_aspect_placeholders"],
            "selected_divine_card_aspect_options": context["selected_shaman_card_aspect_options"],
            "selected_divine_binding": context["selected_shaman_binding"],
            "selected_divine_card_holo": True,
            "selected_divine_card_holo_kind": context["selected_shaman_card_holo_kind"],
        },
        request=request,
    )


@login_required
@require_POST
def update_divine_card(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id, owner=request.user)
    binding = get_object_or_404(
        CharacterDivineEntity.objects.select_related("entity", "entity__school", "character"),
        character=character,
    )
    if not _divine_card_can_edit(binding):
        return JsonResponse({"ok": False, "error": "card_not_editable"}, status=403)

    entity = binding.entity
    if request.POST.get("action") == "choose_aspect":
        if entity.aspect_selection_mode == DivineEntity.AspectSelectionMode.FIXED:
            return JsonResponse({"ok": False, "error": "aspects_not_editable"}, status=403)
        allowed_ids = _allowed_divine_card_aspect_ids(binding)
        selected_aspect_ids: list[int] = []
        for raw_id in request.POST.getlist("core_aspects"):
            try:
                aspect_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if aspect_id in allowed_ids and aspect_id not in selected_aspect_ids:
                selected_aspect_ids.append(aspect_id)
        selected_aspect_ids = selected_aspect_ids[: int(entity.starting_aspect_count)]
        with transaction.atomic():
            binding.core_aspects.set(selected_aspect_ids)
        context = _build_sheet_context_for_request(request, character)
        card_html = render_to_string(
            "charsheet/partials/_god_card.html",
            {
                **context,
                "divine_entity": context["selected_divine_entity"],
                "card_aspects": context["selected_divine_card_aspects"],
            },
            request=request,
        )
        return JsonResponse({"ok": True, "cardHtml": card_html})

    binding.custom_name = str(request.POST.get("custom_name", ""))[:160].strip()
    binding.tradition_name = str(request.POST.get("tradition_name", ""))[:160].strip()
    binding.custom_g_ability = str(request.POST.get("custom_g_ability", binding.custom_g_ability)).strip()
    binding.custom_fluff = str(request.POST.get("custom_fluff", binding.custom_fluff)).strip()
    binding.custom_description = str(request.POST.get("custom_description", binding.custom_description)).strip()
    if request.POST.get("remove_custom_god_image") == "1":
        if binding.custom_god_image:
            binding.custom_god_image.delete(save=False)
        binding.custom_god_image = None
    if request.FILES.get("custom_god_image"):
        binding.custom_god_image = request.FILES["custom_god_image"]

    selected_aspect_ids: list[int] = []
    should_update_aspects = "core_aspects" in request.POST
    if should_update_aspects and entity.aspect_selection_mode != DivineEntity.AspectSelectionMode.FIXED:
        allowed_ids = _allowed_divine_card_aspect_ids(binding)
        for raw_id in request.POST.getlist("core_aspects"):
            try:
                aspect_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if aspect_id in allowed_ids and aspect_id not in selected_aspect_ids:
                selected_aspect_ids.append(aspect_id)
        selected_aspect_ids = selected_aspect_ids[: int(entity.starting_aspect_count)]

    with transaction.atomic():
        binding.full_clean()
        binding.save()
        if should_update_aspects and entity.aspect_selection_mode != DivineEntity.AspectSelectionMode.FIXED:
            binding.core_aspects.set(selected_aspect_ids)

    context = _build_sheet_context_for_request(request, character)
    card_html = render_to_string(
        "charsheet/partials/_god_card.html",
        {
            **context,
            "divine_entity": context["selected_divine_entity"],
            "card_aspects": context["selected_divine_card_aspects"],
        },
        request=request,
    )
    return JsonResponse({"ok": True, "cardHtml": card_html})


@login_required
@require_POST
def update_druid_card(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id, owner=request.user)
    binding = get_object_or_404(
        CharacterDruidCult.objects.select_related("cult", "cult__school", "character"),
        character=character,
    )
    if not _druid_card_can_edit(binding):
        return JsonResponse({"ok": False, "error": "card_not_editable"}, status=403)

    cult = binding.cult
    if request.POST.get("action") == "choose_aspect":
        if cult.aspect_selection_mode == DivineEntity.AspectSelectionMode.FIXED:
            return JsonResponse({"ok": False, "error": "aspects_not_editable"}, status=403)
        allowed_ids = _allowed_druid_card_aspect_ids(binding)
        selected_aspect_ids: list[int] = []
        for raw_id in request.POST.getlist("core_aspects"):
            try:
                aspect_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if aspect_id in allowed_ids and aspect_id not in selected_aspect_ids:
                selected_aspect_ids.append(aspect_id)
        selected_aspect_ids = selected_aspect_ids[: int(cult.starting_aspect_count)]
        with transaction.atomic():
            binding.core_aspects.set(selected_aspect_ids)
    else:
        update_fields = []
        if "custom_name" in request.POST:
            binding.custom_name = str(request.POST.get("custom_name", ""))[:160].strip()
            update_fields.append("custom_name")
        if "tradition_name" in request.POST:
            binding.tradition_name = str(request.POST.get("tradition_name", ""))[:160].strip()
            update_fields.append("tradition_name")
        if "custom_g_ability" in request.POST:
            binding.custom_g_ability = str(request.POST.get("custom_g_ability", binding.custom_g_ability)).strip()
            update_fields.append("custom_g_ability")
        if "custom_fluff" in request.POST:
            binding.custom_fluff = str(request.POST.get("custom_fluff", binding.custom_fluff)).strip()
            update_fields.append("custom_fluff")
        if "custom_description" in request.POST:
            binding.custom_description = str(request.POST.get("custom_description", binding.custom_description)).strip()
            update_fields.append("custom_description")
        if request.POST.get("remove_custom_god_image") == "1":
            if binding.custom_god_image:
                binding.custom_god_image.delete(save=False)
            binding.custom_god_image = None
            update_fields.append("custom_god_image")
        if request.FILES.get("custom_god_image"):
            binding.custom_god_image = request.FILES["custom_god_image"]
            update_fields.append("custom_god_image")
        binding.full_clean()
        if update_fields:
            binding.save(update_fields=sorted(set(update_fields)))

    context = _build_sheet_context_for_request(request, character)
    card_html = render_to_string(
        "charsheet/partials/_god_card.html",
        {
            **context,
            "divine_entity": context["selected_druid_cult"],
            "card_aspects": context["selected_druid_card_aspects"],
            "selected_divine_card_aspects": context["selected_druid_card_aspects"],
            "selected_divine_card_image_url": context["selected_druid_card_image_url"],
            "selected_divine_card_title": context["selected_druid_card_title"],
            "selected_divine_card_kind_label": context["selected_druid_card_kind_label"],
            "selected_divine_card_typebar": context["selected_druid_card_typebar"],
            "selected_divine_card_ability": context["selected_druid_card_ability"],
            "selected_divine_card_fluff": context["selected_druid_card_fluff"],
            "selected_divine_card_editable": context["selected_druid_card_editable"],
            "selected_divine_card_update_url": context["selected_druid_card_update_url"],
            "selected_divine_card_show_aspect_placeholder": context["selected_druid_card_show_aspect_placeholder"],
            "selected_divine_card_aspect_placeholders": context["selected_druid_card_aspect_placeholders"],
            "selected_divine_card_aspect_options": context["selected_druid_card_aspect_options"],
            "selected_divine_binding": context["selected_druid_binding"],
            "selected_divine_card_holo": True,
            "selected_divine_card_holo_kind": "power-animal",
        },
        request=request,
    )
    return JsonResponse(
        {
            "ok": True,
            "cardHtml": card_html,
            "druidCultDisplayName": context["selected_druid_card_typebar"],
        }
    )


@login_required
@require_POST
def update_shaman_card(request, character_id: int):
    character = get_object_or_404(Character, pk=character_id, owner=request.user)
    binding = get_object_or_404(
        CharacterShamanPatron.objects.select_related("patron", "patron__school", "character"),
        character=character,
    )
    if not _shaman_card_can_edit(binding):
        return JsonResponse({"ok": False, "error": "card_not_editable"}, status=403)

    patron = binding.patron
    if request.POST.get("action") == "choose_aspect":
        if patron.aspect_selection_mode == DivineEntity.AspectSelectionMode.FIXED:
            return JsonResponse({"ok": False, "error": "aspects_not_editable"}, status=403)
        allowed_ids = _allowed_shaman_card_aspect_ids(binding)
        selected_ids = []
        for raw_id in request.POST.getlist("core_aspects"):
            try:
                aspect_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if aspect_id in allowed_ids and aspect_id not in selected_ids:
                selected_ids.append(aspect_id)
        binding.core_aspects.set(selected_ids[: int(patron.starting_aspect_count)])
    else:
        update_fields = []
        if "patron_kind_override" in request.POST and patron.slug == "ursprung":
            patron_kind = str(request.POST.get("patron_kind_override", "")).strip()
            allowed_kinds = {
                CharacterShamanPatron.PatronKindOverride.TOTEM,
                CharacterShamanPatron.PatronKindOverride.ANCESTOR_SPIRIT,
            }
            if patron_kind not in allowed_kinds:
                return JsonResponse({"ok": False, "error": "invalid_patron_kind"}, status=400)
            binding.patron_kind_override = patron_kind
            update_fields.append("patron_kind_override")
        for field_name, max_length in (("custom_name", 160), ("tradition_name", 160)):
            if field_name in request.POST:
                setattr(binding, field_name, str(request.POST.get(field_name, ""))[:max_length].strip())
                update_fields.append(field_name)
        for field_name in ("custom_description", "custom_g_ability", "custom_fluff"):
            if field_name in request.POST:
                setattr(binding, field_name, str(request.POST.get(field_name, "")).strip())
                update_fields.append(field_name)
        if request.POST.get("remove_custom_god_image") == "1":
            if binding.custom_god_image:
                binding.custom_god_image.delete(save=False)
            binding.custom_god_image = None
            update_fields.append("custom_god_image")
        if request.FILES.get("custom_god_image"):
            binding.custom_god_image = request.FILES["custom_god_image"]
            update_fields.append("custom_god_image")
        binding.full_clean()
        if update_fields:
            binding.save(update_fields=sorted(set(update_fields)))

    return JsonResponse({"ok": True, "cardHtml": _render_shaman_card(request, character)})


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
    form = CharacterInfoInlineForm(request.POST, request.FILES, instance=character)
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
def add_visible_skill(request, character_id: int, skill_id: int):
    """Persist one unlearned skill so it stays visible in the sheet list."""
    character = _owned_character_or_404(request, character_id)
    skill = get_object_or_404(Skill.objects.select_related("category", "attribute"), pk=skill_id)
    character_skill, created = CharacterSkill.objects.get_or_create(
        character=character,
        skill=skill,
        specification="*",
        defaults={"level": 0},
    )
    if created:
        messages.success(request, f"{skill.name} wurde zur Liste hinzugefügt.")
    else:
        messages.info(request, f"{skill.name} ist bereits in der Liste vorhanden.")
    if _is_partial_request(request):
        return _sheet_partials_response(request, character, "character_header")
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def remove_visible_skill(request, character_id: int, skill_id: int):
    """Remove one manually shown unlearned skill from the sheet list."""
    character = _owned_character_or_404(request, character_id)
    skill = get_object_or_404(Skill, pk=skill_id)
    character_skill = CharacterSkill.objects.filter(
        character=character,
        skill=skill,
        specification="*",
    ).first()
    if character_skill is None:
        messages.info(request, f"{skill.name} ist nicht manuell eingeblendet.")
    elif int(character_skill.level) > 0:
        messages.error(request, "Geskillte Fertigkeiten können nicht aus der Liste entfernt werden.")
    else:
        character_skill.delete()
        messages.success(request, f"{skill.name} wurde aus der Liste entfernt.")
    if _is_partial_request(request):
        return _sheet_partials_response(request, character, "character_header")
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def update_rune_specification(request, character_item_id: int, rune_id: int):
    """Persist the specialization text for one rune on an owned item."""
    character_item = get_object_or_404(
        CharacterItem.objects.select_related("owner", "item"),
        pk=character_item_id,
        owner__user=request.user,
    )
    rune = get_object_or_404(Rune, pk=rune_id, has_specialization=True)
    if (
        not character_item.runes.filter(pk=rune_id).exists()
        and not character_item.item_runes.filter(rune_id=rune_id, is_active=True).exists()
    ):
        messages.error(request, "Diese Rune gehört nicht zu diesem Gegenstand.")
        return redirect("character_sheet", character_id=character_item.owner_id)

    spec, _created = CharacterItemRuneSpec.objects.get_or_create(
        character_item=character_item,
        rune=rune,
    )
    form = CharacterItemRuneSpecForm(request.POST, instance=spec)
    if form.is_valid():
        form.save()
        messages.success(request, f"{rune.name} wurde aktualisiert.")
    else:
        messages.error(request, "Die Spezifikation konnte nicht gespeichert werden.")
    return redirect("character_sheet", character_id=character_item.owner_id)


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


def _reset_druid_cult_slot_progress(character: Character, cult_ids: list[int]) -> int:
    """Remove paid aspect progress learned through a removed or replaced druid circle."""
    aspect_ids = set()
    if cult_ids:
        aspect_ids.update(
            DruidCultAspect.objects.filter(cult_id__in=cult_ids).values_list("aspect_id", flat=True)
        )
    bonus_aspect_ids = set(
        CharacterAspect.objects.filter(character=character, is_bonus_aspect=True).values_list("aspect_id", flat=True)
    )
    aspect_ids.update(bonus_aspect_ids)
    if not aspect_ids:
        return 0
    deleted_count, _ = CharacterSpell.objects.filter(
        character=character,
        source_kind__in=(
            CharacterSpell.SourceKind.DIVINE_EXTRA,
            CharacterSpell.SourceKind.DIVINE_BONUS,
        ),
        spell__aspect_id__in=list(aspect_ids),
    ).delete()
    CharacterAspect.objects.filter(
        character=character,
        is_bonus_aspect=True,
        aspect_id__in=list(bonus_aspect_ids),
    ).delete()
    if deleted_count:
        character.spent_spell_learning_slots = max(
            0,
            int(character.spent_spell_learning_slots or 0) - deleted_count,
        )
        character.save(update_fields=["spent_spell_learning_slots"])
    return int(deleted_count)


@login_required
@require_POST
def update_druid_cult(request, character_id: int):
    """Persist the druid circle selected from the learned school panel."""
    character = _owned_character_or_404(request, character_id)
    try:
        school_id = int(request.POST.get("school_id", "0"))
    except (TypeError, ValueError):
        school_id = 0
    if school_id <= 0 or not character.schools.filter(school_id=school_id, level__gt=0).exists():
        messages.error(request, "Druidenzirkel konnte nicht gespeichert werden.")
        return redirect("character_sheet", character_id=character.id)

    raw_cult_id = str(request.POST.get("druid_cult", "")).strip()
    current_binding = CharacterDruidCult.objects.filter(character=character).select_related("cult").first()
    if not raw_cult_id:
        if current_binding is not None and int(current_binding.cult.school_id or 0) == school_id:
            _reset_druid_cult_slot_progress(character, [current_binding.cult_id])
            current_binding.delete()
            character.get_magic_engine(refresh=True).sync_character_magic()
            messages.success(request, "Druidenzirkel entfernt.")
        else:
            messages.info(request, "Keine Aenderung erkannt.")
        return redirect("character_sheet", character_id=character.id)

    cult = DruidCult.objects.filter(pk=raw_cult_id, school_id=school_id).first()
    if cult is None:
        messages.error(request, "Druidenzirkel passt nicht zu dieser Schule.")
        return redirect("character_sheet", character_id=character.id)

    cult_changed = current_binding is None or int(current_binding.cult_id) != int(cult.id)
    if current_binding is not None and cult_changed:
        _reset_druid_cult_slot_progress(character, [current_binding.cult_id])
        if current_binding.custom_god_image:
            current_binding.custom_god_image.delete(save=False)
    defaults = {"cult": cult}
    if cult_changed:
        defaults.update(
            {
                "custom_name": "",
                "tradition_name": "",
                "custom_description": "",
                "custom_g_ability": "",
                "custom_fluff": "",
                "custom_god_image": None,
            }
        )
    CharacterDruidCult.objects.update_or_create(character=character, defaults=defaults)
    character.get_magic_engine(refresh=True).sync_character_magic()
    messages.success(request, "Druidenzirkel gespeichert.")
    return redirect("character_sheet", character_id=character.id)


@login_required
def sheet(request):
    """Render the static character sheet template."""
    return render(request, "charsheet/charsheet.html")


@login_required
def dashboard(request):
    """Render the user-specific dashboard with owned character overview."""
    UserSettings.objects.get_or_create(user=request.user)
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
            trait_choices: dict[str, dict[str, list[str]]] = {}
            for trait in Trait.objects.filter(trait_type=Trait.TraitType.DIS).order_by("name"):
                level = int(request.POST.get(f"dis_{trait.slug}", "0") or 0)
                if level > 0:
                    disadvantages[trait.slug] = level
                    choice_payload: dict[str, list[str]] = {}
                    for definition in trait.choice_definitions.filter(target_kind="attribute").order_by("sort_order", "id"):
                        selected = (request.POST.get(f"dis_choice_{trait.slug}_{definition.id}") or "").strip()
                        if selected:
                            choice_payload[str(definition.id)] = [selected]
                    if choice_payload:
                        trait_choices[trait.slug] = choice_payload
            state["phase_3"] = {"disadvantages": disadvantages, "trait_choices": trait_choices}
        elif phase == 4:
            advantages: dict[str, int] = {}
            trait_choices: dict[str, dict[str, list[str]]] = {}
            for trait in Trait.objects.filter(trait_type=Trait.TraitType.ADV).order_by("name"):
                level = int(request.POST.get(f"adv_{trait.slug}", "0") or 0)
                if level > 0:
                    advantages[trait.slug] = level
                    choice_payload: dict[str, list[str]] = {}
                    for definition in trait.choice_definitions.filter(target_kind="attribute").order_by("sort_order", "id"):
                        selected = (request.POST.get(f"adv_choice_{trait.slug}_{definition.id}") or "").strip()
                        if selected:
                            choice_payload[str(definition.id)] = [selected]
                    for definition in trait.choice_definitions.filter(target_kind="resource").order_by("sort_order", "id"):
                        selected = (request.POST.get(f"adv_choice_{trait.slug}_{definition.id}") or "").strip()
                        if selected:
                            choice_payload[str(definition.id)] = [selected]
                    if choice_payload:
                        trait_choices[trait.slug] = choice_payload

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

            weapon_masteries_by_slot: dict[int, dict[str, object]] = {}
            weapon_arcana_by_slot: dict[int, dict[str, object]] = {}
            for key in request.POST.keys():
                if str(key).startswith("wm_mastery_weapon_"):
                    slot = str(key).rsplit("_", 1)[-1]
                    slot_index = int(slot or 0)
                    weapon_type = str(request.POST.get(key, "") or "").strip().lower()
                    first_bonus_kind = str(request.POST.get(f"wm_mastery_first_{slot}", "") or "").strip().lower()
                    if weapon_type or first_bonus_kind:
                        weapon_masteries_by_slot[slot_index] = {
                            "weapon_type": weapon_type,
                            "first_bonus_kind": first_bonus_kind,
                        }
                elif str(key).startswith("wm_arcana_"):
                    slot_index = int(str(key).rsplit("_", 1)[-1] or 0)
                    raw_value = str(request.POST.get(key, "") or "").strip()
                    if not raw_value:
                        continue
                    if raw_value == "bonus_capacity":
                        weapon_arcana_by_slot[slot_index] = {"kind": "bonus_capacity", "rune_id": 0}
                    elif raw_value.startswith("rune:"):
                        weapon_arcana_by_slot[slot_index] = {"kind": "rune", "rune_id": int(raw_value.split(":", 1)[1])}

            weapon_masteries = [weapon_masteries_by_slot[index] for index in sorted(weapon_masteries_by_slot)]
            weapon_arcana = [weapon_arcana_by_slot[index] for index in sorted(weapon_arcana_by_slot)]

            state["phase_4"] = {
                "advantages": advantages,
                "trait_choices": trait_choices,
                "attribute_adds": attribute_adds,
                "skill_adds": skill_adds,
                "language_adds": language_adds,
                "language_write_adds": language_write_adds,
                "schools": schools,
                "weapon_masteries": weapon_masteries,
                "weapon_arcana": weapon_arcana,
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
        free_base = engine.phase_2_free_skills().get(skill.slug, 0)
        phase_2_skill_rows.append(
            {
                "slug": skill.slug,
                "name": skill.name,
                "category_name": skill.category.name,
                "category_slug": skill.category.slug,
                "description": description,
                "value": value,
                "cost": engine.calc_phase_2_skill_cost(skill.slug, value) if value > 0 else 0,
                "free_base": free_base,
                "min_value": free_base if free_base > 0 else 0,
                "locked": free_base > 0,
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
    phase_3_trait_choices = engine.phase_3_trait_choices()
    phase_3_rows = []
    for trait in Trait.objects.filter(trait_type=Trait.TraitType.DIS).order_by("name"):
        description = (trait.description or "").replace("\r\n", "\n").replace("\r", "\n")
        attribute_choice_definitions = [
            {
                "id": definition.id,
                "name": definition.name,
                "selected": ((phase_3_trait_choices.get(trait.slug, {}).get(definition.id, [""]) or [""])[0]),
                "options": [
                    {"value": short_name, "label": label}
                    for short_name, label in ATTRIBUTE_ORDER
                    if is_allowed_trait_attribute_choice(trait.slug, short_name)
                ],
            }
            for definition in trait.choice_definitions.filter(target_kind="attribute").order_by("sort_order", "id")
        ]
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
                "attribute_choice_definitions": attribute_choice_definitions,
                "attribute_choice_definitions_json": json.dumps(attribute_choice_definitions),
            }
        )

    phase_4_values = engine.phase_4_advantages()
    phase_4_trait_choices = engine.phase_4_trait_choices()
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
        attribute_choice_definitions = [
            {
                "id": definition.id,
                "name": definition.name,
                "selected": ((phase_4_trait_choices.get(trait.slug, {}).get(definition.id, [""]) or [""])[0]),
                "options": [
                    {"value": short_name, "label": label}
                    for short_name, label in ATTRIBUTE_ORDER
                    if is_allowed_trait_attribute_choice(trait.slug, short_name)
                ],
            }
            for definition in trait.choice_definitions.filter(target_kind="attribute").order_by("sort_order", "id")
        ]
        resource_choice_definitions = [
            {
                "id": definition.id,
                "name": definition.name,
                "selected": ((phase_4_trait_choices.get(trait.slug, {}).get(definition.id, [""]) or [""])[0]),
                "options": (
                    [
                        {
                            "value": definition.allowed_resource,
                            "label": dict(RESOURCE_KEY_CHOICES).get(definition.allowed_resource, definition.allowed_resource),
                        }
                    ]
                    if definition.allowed_resource
                    else [{"value": value, "label": label} for value, label in RESOURCE_KEY_CHOICES]
                ),
            }
            for definition in trait.choice_definitions.filter(target_kind="resource").order_by("sort_order", "id")
        ]
        phase_4_adv_rows.append(
            {
                "slug": trait.slug,
                "name": trait.name,
                "min_level": trait.min_level,
                "max_level": trait.max_level,
                "points_per_level": trait.points_per_level,
                "points_display": trait.cost_display(),
                "points_by_level": list(trait.cost_curve()),
                "attribute_choice_definitions": attribute_choice_definitions,
                "attribute_choice_definitions_json": json.dumps(attribute_choice_definitions),
                "resource_choice_definitions": resource_choice_definitions,
                "resource_choice_definitions_json": json.dumps(resource_choice_definitions),
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
    weapon_master_school = School.objects.filter(name__iexact="Waffenmeister").first()
    phase_4_weapon_mastery_rows = []
    if weapon_master_school is not None:
        required_wm_count = min(phase_4_schools.get(str(weapon_master_school.id), 0), 10)
        draft_weapon_masteries = engine.phase_4_weapon_masteries()
        draft_weapon_arcana = engine.phase_4_weapon_mastery_arcana()
        weapon_options = weapon_mastery_weapon_type_definitions()
        rune_options = list(Rune.objects.order_by("name").values("id", "name"))
        for slot_index in range(required_wm_count):
            mastery_payload = draft_weapon_masteries[slot_index] if slot_index < len(draft_weapon_masteries) else {}
            arcana_payload = draft_weapon_arcana[slot_index] if slot_index < len(draft_weapon_arcana) else {}
            selected_arcana_value = (
                "bonus_capacity"
                if arcana_payload.get("kind") == "bonus_capacity"
                else (
                    f"rune:{arcana_payload.get('rune_id')}"
                    if arcana_payload.get("kind") == "rune" and arcana_payload.get("rune_id")
                    else ""
                )
            )
            phase_4_weapon_mastery_rows.append(
                {
                    "slot": slot_index + 1,
                    "weapon_name": f"wm_mastery_weapon_{slot_index + 1}",
                    "first_name": f"wm_mastery_first_{slot_index + 1}",
                    "selected_weapon_id": mastery_payload.get("weapon_type", ""),
                    "selected_first_bonus_kind": mastery_payload.get("first_bonus_kind", ""),
                    "weapon_options": weapon_options,
                    "arcana_name": f"wm_arcana_{slot_index + 1}",
                    "selected_value": selected_arcana_value,
                    "rune_options": [
                        {
                            **rune,
                            "selected": selected_arcana_value == f"rune:{rune['id']}",
                        }
                        for rune in rune_options
                    ],
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
            "phase_4_weapon_mastery_rows": phase_4_weapon_mastery_rows,
            "phase_4_weapon_mastery_school": weapon_master_school,
            "phase_4_spent": engine.sum_phase_4_total_cost(),
            "phase_4_budget": engine.calculate_phase_4_budget(),
            "phase_4_adv_spent": engine.sum_phase_4_advantages_cost(),
            "phase_4_adv_budget": engine.calculate_phase_4_advantages_budget(),
            "phase_4_rest_spent": engine.sum_phase_4_rest_cost(),
            "phase_4_rest_budget": engine.calculate_phase_4_rest_budget(),
            "attribute_order": ATTRIBUTE_ORDER,
            "resource_key_choices": RESOURCE_KEY_CHOICES,
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
    """Toggle equipped state for one equippable inventory entry."""
    ci = _owned_character_item_or_404(request, pk)

    if ci.item.item_type not in (
        Item.ItemType.ARMOR,
        Item.ItemType.SHIELD,
        Item.ItemType.WEAPON,
        Item.ItemType.CLOTHING,
        Item.ItemType.MAGIC_ITEM,
    ) and not ci.item.is_magic_effective:
        return redirect("character_sheet", character_id=ci.owner_id)

    if ci.equip_locked:
        if not ci.equipped:
            ci.equipped = True
            ci.stored = False
            ci.save(update_fields=["equipped", "stored"])
    else:
        ci.equipped = not ci.equipped
        update_fields = ["equipped"]
        if ci.equipped and ci.stored:
            ci.stored = False
            update_fields.append("stored")
        ci.save(update_fields=update_fields)
    if _is_partial_request(request):
        return _sheet_partials_response(
            request,
            ci.owner,
            "character_header",
            "load_panel",
            "core_stats_panel",
            "damage_panel",
            "inventory_panel",
            "armor_panel",
            "weapon_panel",
            "card_hand",
        )

    return redirect("character_sheet", character_id=ci.owner_id)


@login_required
@require_POST
def set_item_storage(request, pk):
    """Persist whether one inventory item is carried or stored."""
    ci = _owned_character_item_or_404(request, pk)
    if ci.equipped or ci.equip_locked:
        return redirect("character_sheet", character_id=ci.owner_id)

    ci.stored = str(request.POST.get("stored", "0")).lower() in {"1", "true", "on", "yes"}
    ci.save(update_fields=["stored"])
    if _is_partial_request(request):
        return _sheet_partials_response(
            request,
            ci.owner,
            "character_header",
            "load_panel",
            "core_stats_panel",
            "inventory_panel",
            "card_hand",
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
        return _sheet_partials_response(
            request,
            character,
            "character_header",
            "load_panel",
            "core_stats_panel",
            "inventory_panel",
            "card_hand",
        )

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
        return _sheet_partials_response(
            request,
            character,
            "character_header",
            "load_panel",
            "core_stats_panel",
            "inventory_panel",
            "card_hand",
        )

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

    requested_current_damage = request.POST.get("current_damage")
    if requested_current_damage is not None:
        try:
            character.current_damage = max(0, int(requested_current_damage))
        except (TypeError, ValueError):
            pass
    elif action == "damage":
        character.current_damage += amount
    elif action == "heal":
        character.current_damage = max(0, character.current_damage - amount)

    character.save(update_fields=["current_damage"])

    if _is_partial_request(request):
        engine = character.engine
        thresholds = engine.wound_thresholds()
        current_stage, _raw_penalty = engine.current_wound_stage()
        is_penalty_ignored = engine.is_wound_penalty_ignored()
        effective_penalty = engine.current_wound_penalty()
        partials = []
        if request.POST.get("partials") != "0":
            context = _build_sheet_context_for_request(request, character)
            partial_keys = ("character_header", "load_panel", "core_stats_panel", "armor_panel", "weapon_panel")
            for key in partial_keys:
                target_id, template_name = SHEET_PARTIAL_TEMPLATES[key]
                partials.append(
                    {
                        "target": target_id,
                        "html": render_to_string(template_name, context, request=request),
                    }
                )
        return JsonResponse(
            {
                "ok": True,
                "current_damage": character.current_damage,
                "current_damage_max": max(1, max(thresholds.keys(), default=0)),
                "current_wound_stage": current_stage,
                "current_wound_penalty": format_modifier(effective_penalty),
                "is_wound_penalty_ignored": is_penalty_ignored,
                "partials": partials,
            }
        )

    return redirect("character_sheet", character_id=character_id)


@login_required
@require_POST
def adjust_creature_damage(request, pk: int):
    """Increase or decrease current damage on one owned creature instance."""
    character_creature = _owned_character_creature_or_404(request, pk)
    action = request.POST.get("action")
    try:
        amount = max(1, int(request.POST.get("amount", "1")))
    except (TypeError, ValueError):
        amount = 1

    if action == "damage":
        character_creature.current_damage += amount
    elif action == "heal":
        character_creature.current_damage = max(0, character_creature.current_damage - amount)

    character_creature.save(update_fields=["current_damage"])

    if _is_partial_request(request):
        return JsonResponse({"ok": True, "current_damage": character_creature.current_damage})

    next_url = str(request.POST.get("next") or "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(f"/debug/card/?instance={character_creature.pk}")


@login_required
@require_POST
def adjust_creature_card_damage(request, pk: int):
    """Increase or decrease current damage on one concrete character creature card."""
    creature_card = _owned_character_creature_card_or_404(request, pk)
    action = request.POST.get("action")
    try:
        amount = max(1, int(request.POST.get("amount", "1")))
    except (TypeError, ValueError):
        amount = 1

    if action == "damage":
        creature_card.current_damage += amount
    elif action == "heal":
        creature_card.current_damage = max(0, creature_card.current_damage - amount)

    creature_card.save(update_fields=["current_damage"])

    if _is_partial_request(request):
        return JsonResponse({"ok": True, "current_damage": creature_card.current_damage})

    next_url = str(request.POST.get("next") or "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("character_sheet", character_id=creature_card.character_id)


def _parse_positive_int(raw_value, fallback=0):
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return fallback


def _parse_int(raw_value, fallback=0):
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return fallback


def _parse_nonnegative_float(raw_value, fallback=0):
    try:
        return max(0, float(raw_value))
    except (TypeError, ValueError):
        return fallback


def _clamped_trait_level(request, trait: CreatureTraitDefinition, prefix: str) -> int:
    level = _parse_positive_int(request.POST.get(f"{prefix}_{trait.pk}"), int(trait.min_level or 1))
    return min(max(level, int(trait.min_level or 1)), int(trait.max_level or 1))


def _render_creature_training_payload(request, card: CharacterCreatureCard) -> dict:
    card_context = CreatureCardEngine(card).card_context()
    card_context["adjust_damage_url"] = reverse_lazy("adjust_creature_card_damage", kwargs={"pk": card.pk})
    card_context["training_update_url"] = reverse_lazy("update_creature_card_training", kwargs={"pk": card.pk})
    mini_context = {**card_context, "adjust_damage_url": "", "damage_controls_disabled": True}
    mini_context.pop("training_update_url", None)
    return {
        "ok": True,
        "cardKey": f"creature-{card.pk}",
        "cardTitle": card_context["name"],
        "cardHtml": render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": card_context},
            request=request,
        ),
        "miniCardHtml": render_to_string(
            "charsheet/partials/_creature_card.html",
            {"creature_card": mini_context},
            request=request,
        ),
        "drawerHtml": render_to_string(
            "charsheet/partials/_creature_training_drawer.html",
            {"training": build_creature_card_training_context(card)},
            request=request,
        ),
    }


@login_required
@require_POST
def update_creature_card_training(request, pk: int):
    card = _owned_character_creature_card_or_404(request, pk)
    card_update_fields = []
    if "custom_name" in request.POST:
        default_name = getattr(card.creature, "display_name", "") or card.name
        card.name = str(request.POST.get("custom_name", ""))[:100].strip() or default_name
        card_update_fields.append("name")
    if request.POST.get("remove_custom_creature_image") == "1":
        if card.image:
            card.image.delete(save=False)
        card.image = None
        card_update_fields.append("image")
    if request.FILES.get("custom_creature_image"):
        card.image = request.FILES["custom_creature_image"]
        card_update_fields.append("image")
    if "quality" in request.POST:
        selected_quality = Quality.objects.filter(code=str(request.POST.get("quality") or "")).first()
        if selected_quality is not None:
            card.quality = selected_quality
            card_update_fields.append("quality")
            quality_budget = CREATURE_CARD_QUALITY_TRAINING_BUDGETS.get(selected_quality.code, (0, 0))
            card.max_base_advantage_points = int(quality_budget[0])
            card.max_base_disadvantage_points = int(quality_budget[1])
            card_update_fields.extend(["max_base_advantage_points", "max_base_disadvantage_points"])
    movement_int_fields = ("combat_speed", "march_speed", "sprint_speed")
    for field_name in movement_int_fields:
        if field_name in request.POST:
            setattr(card, field_name, _parse_positive_int(request.POST.get(field_name), getattr(card, field_name, 0)))
            card_update_fields.append(field_name)
    if "swimming_speed" in request.POST:
        card.swimming_speed = _parse_nonnegative_float(request.POST.get("swimming_speed"), card.swimming_speed or 0)
        card_update_fields.append("swimming_speed")
    can_fly = request.POST.get("can_fly") == "1"
    for field_name in ("combat_fly_speed", "march_fly_speed", "sprint_fly_speed"):
        if can_fly:
            setattr(card, field_name, _parse_positive_int(request.POST.get(field_name), getattr(card, field_name, None) or 0))
        else:
            setattr(card, field_name, None)
        card_update_fields.append(field_name)
    selected_command_ids = {_parse_positive_int(raw_id) for raw_id in request.POST.getlist("commands") if _parse_positive_int(raw_id)}
    selected_advantage_ids = {_parse_positive_int(raw_id) for raw_id in request.POST.getlist("advantages") if _parse_positive_int(raw_id)}
    selected_disadvantage_ids = {_parse_positive_int(raw_id) for raw_id in request.POST.getlist("disadvantages") if _parse_positive_int(raw_id)}
    commands = list(
        CreatureCommand.objects.filter(pk__in=selected_command_ids)
        .prefetch_related("prerequisite_links__prerequisite")
        .order_by("name")
    )
    traits_by_id = {
        trait.pk: trait
        for trait in CreatureTraitDefinition.objects.filter(
            pk__in=selected_advantage_ids | selected_disadvantage_ids
        )
    }
    new_trait_rows = []
    spent_advantage_points = 0
    spent_disadvantage_points = 0
    order = 1000
    for trait_id in selected_advantage_ids:
        trait = traits_by_id.get(trait_id)
        if trait is None or trait.trait_type != CreatureTraitDefinition.TraitType.ADV:
            continue
        level = _clamped_trait_level(request, trait, "advantage_level")
        spent_advantage_points += trait.cost_for_level(level)
        new_trait_rows.append(
            CharacterCreatureCardTrait(
                card=card,
                trait_definition=trait,
                name=trait.name,
                level=level,
                description=trait.description,
                training_trait_type=CharacterCreatureCardTrait.TrainingTraitType.ADVANTAGE,
                order=order,
            )
        )
        order += 1
    for trait_id in selected_disadvantage_ids:
        trait = traits_by_id.get(trait_id)
        if trait is None or trait.trait_type != CreatureTraitDefinition.TraitType.DIS:
            continue
        level = _clamped_trait_level(request, trait, "disadvantage_level")
        spent_disadvantage_points += trait.cost_for_level(level)
        new_trait_rows.append(
            CharacterCreatureCardTrait(
                card=card,
                trait_definition=trait,
                name=trait.name,
                level=level,
                description=trait.description,
                training_trait_type=CharacterCreatureCardTrait.TrainingTraitType.DISADVANTAGE,
                order=order,
            )
        )
        order += 1

    attribute_codes = {code for code, _label in ATTRIBUTE_CODE_CHOICES}
    card_attribute_values = {
        "ST": card.strength_mod,
        "KON": card.constitution_mod,
        "GE": card.dexterity_mod,
        "INT": card.intelligence_mod,
        "WA": card.perception_mod,
        "WILL": card.willpower_mod,
        "CHA": card.charisma_mod,
    }
    attribute_rows = []
    for code in attribute_codes:
        target_value = _parse_positive_int(request.POST.get(f"attribute_{code}"), 0)
        base_modifier = card_attribute_values.get(code)
        if base_modifier is None:
            continue
        base_attribute_value = int(base_modifier) + 5
        amount = max(0, target_value - base_attribute_value)
        if amount:
            attribute_rows.append(CharacterCreatureCardAttributeIncrease(card=card, attribute=code, amount=amount))

    skill_updates = []
    remove_skill_ids = {
        _parse_positive_int(raw_id)
        for raw_id in request.POST.getlist("remove_skill_ids")
        if _parse_positive_int(raw_id)
    }
    for skill_row in card.skills.all():
        if skill_row.pk in remove_skill_ids:
            continue
        field_name = f"skill_value_{skill_row.pk}"
        if field_name not in request.POST:
            continue
        skill_row.value = _parse_int(request.POST.get(field_name), skill_row.value)
        skill_updates.append(skill_row)
    new_skill_rows = []
    existing_skill_names = {
        row.name.casefold()
        for row in card.skills.exclude(pk__in=remove_skill_ids)
    }
    new_skill_ids = request.POST.getlist("new_skill_id")
    new_skill_values = request.POST.getlist("new_skill_value")
    normal_skill_ids = [
        _parse_positive_int(str(raw_id).split(":", 1)[1], 0)
        for raw_id in new_skill_ids
        if str(raw_id).startswith("skill:")
    ]
    special_skill_ids = [
        _parse_positive_int(str(raw_id).split(":", 1)[1], 0)
        for raw_id in new_skill_ids
        if str(raw_id).startswith("special:")
    ]
    selected_normal_skills = {
        skill.pk: skill
        for skill in Skill.objects.filter(pk__in=normal_skill_ids)
    }
    selected_special_skills = {
        skill.pk: skill
        for skill in CreatureSpecialSkill.objects.filter(pk__in=special_skill_ids)
    }
    next_skill_order = card.skills.count() + 1000
    for index, raw_skill_ref in enumerate(new_skill_ids):
        raw_skill_ref = str(raw_skill_ref or "")
        if raw_skill_ref.startswith("special:"):
            skill_id = _parse_positive_int(raw_skill_ref.split(":", 1)[1], 0)
            selected_skill = selected_special_skills.get(skill_id)
        else:
            skill_id = _parse_positive_int(raw_skill_ref.split(":", 1)[-1], 0)
            selected_skill = selected_normal_skills.get(skill_id)
        if selected_skill is None or selected_skill.name.casefold() in existing_skill_names:
            continue
        existing_skill_names.add(selected_skill.name.casefold())
        new_skill_rows.append(
            CharacterCreatureCardSkill(
                card=card,
                name=selected_skill.name,
                value=_parse_int(new_skill_values[index] if index < len(new_skill_values) else 0, 0),
                notes=getattr(selected_skill, "description", ""),
                order=next_skill_order,
            )
        )
        next_skill_order += 1

    with transaction.atomic():
        if card_update_fields:
            card.save(update_fields=sorted(set(card_update_fields)))
        if remove_skill_ids:
            card.skills.filter(pk__in=remove_skill_ids).delete()
        if skill_updates:
            CharacterCreatureCardSkill.objects.bulk_update(skill_updates, ["value"])
        if new_skill_rows:
            CharacterCreatureCardSkill.objects.bulk_create(new_skill_rows)
        card.commands.all().delete()
        created_commands = list(
            CharacterCreatureCardCommand.objects.bulk_create(
                CharacterCreatureCardCommand(
                    card=card,
                    command=command,
                    name=command.name,
                    slug=command.slug,
                    ep_cost=command.ep_cost,
                    difficulty=command.difficulty,
                    description=command.description,
                    order=index,
                )
                for index, command in enumerate(commands)
            )
        )
        command_by_slug = {command.slug: command for command in created_commands}
        CharacterCreatureCardCommandPrerequisite.objects.bulk_create(
            CharacterCreatureCardCommandPrerequisite(
                command=command_by_slug[command.slug],
                prerequisite=command_by_slug[link.prerequisite.slug],
                alternative_group=link.alternative_group,
                order=link.order,
            )
            for command in commands
            for link in command.prerequisite_links.all()
            if command.slug in command_by_slug and link.prerequisite.slug in command_by_slug
        )
        card.traits.exclude(training_trait_type="").delete()
        card.traits.exclude(point_source="").delete()
        card.traits.filter(trait_definition__isnull=False).delete()
        CharacterCreatureCardTrait.objects.bulk_create(new_trait_rows)
        card.attribute_increases.all().delete()
        CharacterCreatureCardAttributeIncrease.objects.bulk_create(attribute_rows)

    card = (
        CharacterCreatureCard.objects.select_related("character", "character__owner", "creature", "binding", "quality")
        .prefetch_related(
            "attacks",
            "skills",
            "traits__trait_definition",
            "commands__command",
            "commands__prerequisite_links__prerequisite",
            "attribute_increases",
        )
        .get(pk=card.pk)
    )
    return JsonResponse(_render_creature_training_payload(request, card))


@login_required
@require_POST
def adjust_current_arcane_power(request, character_id: int):
    """Increase or decrease current arcane power without a full sheet reload."""
    character = _owned_character_or_404(request, character_id)
    action = request.POST.get("action")
    try:
        amount = max(1, int(request.POST.get("amount", "1")))
    except (TypeError, ValueError):
        amount = 1

    calculated_arcane_power = max(0, int(character.engine.calculate_arcane_power()))
    current_arcane_power = character.current_arcane_power
    if current_arcane_power is None:
        current_arcane_power = calculated_arcane_power
    current_arcane_power = max(0, int(current_arcane_power))
    arcane_power_max = max(calculated_arcane_power, current_arcane_power)

    requested_current_arcane_power = request.POST.get("current_arcane_power")
    if requested_current_arcane_power is not None:
        try:
            current_arcane_power = max(0, min(arcane_power_max, int(requested_current_arcane_power)))
        except (TypeError, ValueError):
            pass
    elif action == "spend":
        current_arcane_power = max(0, current_arcane_power - amount)
    elif action == "restore":
        current_arcane_power = min(arcane_power_max, current_arcane_power + amount)

    character.current_arcane_power = current_arcane_power
    character.save(update_fields=["current_arcane_power"])

    if _is_partial_request(request):
        return JsonResponse(
            {
                "ok": True,
                "current_arcane_power": current_arcane_power,
                "current_arcane_power_max": arcane_power_max,
            }
        )

    return redirect("character_sheet", character_id=character_id)


@login_required
@require_POST
def cast_spell(request, character_id: int, spell_id: int):
    """Cast one known spell and spend KP atomically via the magic engine."""
    character = _owned_character_or_404(request, character_id)
    known_spell = get_object_or_404(
        CharacterSpell.objects.select_related("spell"),
        character=character,
        spell_id=spell_id,
    )
    result = character.get_magic_engine(refresh=True).cast_spell(known_spell.spell_id)
    if not result.get("ok"):
        status_code = 400 if result.get("error") in {"unknown_spell", "not_enough_kp", "spell_not_found"} else 409
        if _is_partial_request(request):
            return JsonResponse(result, status=status_code)
        messages.error(request, str(result.get("message") or "Zauber konnte nicht gewirkt werden."))
        return redirect("character_sheet", character_id=character_id)

    if _is_partial_request(request):
        character.refresh_from_db()
        context = _build_sheet_context_for_request(request, character)
        partials = []
        for key in ("damage_panel", "spell_panel"):
            target_id, template_name = SHEET_PARTIAL_TEMPLATES[key]
            partials.append(
                {
                    "target": target_id,
                    "html": render_to_string(template_name, context, request=request),
                }
            )
        return JsonResponse({**result, "partials": partials})

    messages.success(request, f"{result['spell_name']} gewirkt ({result['spent_kp']} KP).")
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
    if _is_partial_request(request):
        context = _build_sheet_context_for_request(request, character, skip_magic_sync=True)
        partials = []
        for key in (
            "character_header",
            "load_panel",
            "core_stats_panel",
            "damage_panel",
            "wallet_panel",
            "experience_panel",
            "inventory_panel",
            "armor_panel",
            "weapon_panel",
            "spell_panel",
            "secondary_page",
            "card_hand",
            "learning_budget",
        ):
            target_id, template_name = SHEET_PARTIAL_TEMPLATES[key]
            partials.append(
                {
                    "target": target_id,
                    "html": render_to_string(template_name, context, request=request),
                }
            )
        return JsonResponse(
            {
                "ok": True,
                "level": level,
                "message": message,
                "learningFeedback": {"level": level, "message": message},
                "learningPanelHtml": (
                    render_to_string("charsheet/partials/_learning_panel.html", context, request=request)
                    if level != "error"
                    else ""
                ),
                "partials": partials,
            }
        )
    request.session["skip_magic_sync_once"] = True
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
    create_custom_shop_item(request.POST, request.FILES)
    return redirect("character_sheet", character_id=character.id)


@login_required
@require_POST
def update_character_item_runes(request, pk: int):
    """Persist one owned-item modification dialog for a supported inventory entry."""
    character_item = _owned_character_item_or_404(request, pk)
    if not apply_character_item_modifications(character_item, request.POST, request.FILES):
        if _is_partial_request(request):
            return JsonResponse({"ok": False, "error": "modification_failed"}, status=400)
        return redirect("character_sheet", character_id=character_item.owner_id)

    if _is_partial_request(request):
        return _sheet_partials_response(
            request,
            character_item.owner,
            "character_header",
            "load_panel",
            "core_stats_panel",
            "damage_panel",
            "wallet_panel",
            "experience_panel",
            "learning_budget",
            "inventory_panel",
            "armor_panel",
            "weapon_panel",
            "card_hand",
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
                "target": "sheetCharacterHeader",
                "html": render_to_string("charsheet/partials/_character_header.html", context, request=request),
            },
            {
                "target": "sheetLoadPanel",
                "html": render_to_string("charsheet/partials/_load_panel.html", context, request=request),
            },
            {
                "target": "sheetCoreStatsPanel",
                "html": render_to_string("charsheet/partials/_core_stats_panel.html", context, request=request),
            },
            {
                "target": "sheetWalletPanel",
                "html": render_to_string("charsheet/partials/_wallet_panel.html", context, request=request),
            },
            {
                "target": "sheetInventoryPanel",
                "html": render_to_string("charsheet/partials/_inventory_panel.html", context, request=request),
            },
            {
                "target": "sheetCardHand",
                "html": render_to_string("charsheet/partials/_card_hand_host.html", context, request=request),
            },
        ]
    return JsonResponse(response_payload, status=status_code)


@login_required
@require_POST
def sell_shop_cart(request, character_id: int):
    """Sell all cart entries atomically and update inventory plus wallet."""
    character = _owned_character_or_404(request, character_id)
    payload = _read_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)
    response_payload, status_code = sell_shop_cart_payload(character, payload)
    if response_payload.get("ok"):
        context = _build_sheet_context_for_request(request, character)
        response_payload["partials"] = [
            {
                "target": "sheetCharacterHeader",
                "html": render_to_string("charsheet/partials/_character_header.html", context, request=request),
            },
            {
                "target": "sheetLoadPanel",
                "html": render_to_string("charsheet/partials/_load_panel.html", context, request=request),
            },
            {
                "target": "sheetCoreStatsPanel",
                "html": render_to_string("charsheet/partials/_core_stats_panel.html", context, request=request),
            },
            {
                "target": "sheetWalletPanel",
                "html": render_to_string("charsheet/partials/_wallet_panel.html", context, request=request),
            },
            {
                "target": "sheetInventoryPanel",
                "html": render_to_string("charsheet/partials/_inventory_panel.html", context, request=request),
            },
            {
                "target": "sheetCardHand",
                "html": render_to_string("charsheet/partials/_card_hand_host.html", context, request=request),
            },
        ]
    return JsonResponse(response_payload, status=status_code)


@login_required
@require_POST
def trade_shop_cart(request, character_id: int):
    """Process one mixed shop cart with buys and sells atomically."""
    character = _owned_character_or_404(request, character_id)
    payload = _read_json_payload(request)
    if not payload:
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)
    response_payload, status_code = trade_shop_cart_payload(character, payload)
    if response_payload.get("ok"):
        context = _build_sheet_context_for_request(request, character)
        response_payload["partials"] = [
            {
                "target": "sheetCharacterHeader",
                "html": render_to_string("charsheet/partials/_character_header.html", context, request=request),
            },
            {
                "target": "sheetLoadPanel",
                "html": render_to_string("charsheet/partials/_load_panel.html", context, request=request),
            },
            {
                "target": "sheetCoreStatsPanel",
                "html": render_to_string("charsheet/partials/_core_stats_panel.html", context, request=request),
            },
            {
                "target": "sheetWalletPanel",
                "html": render_to_string("charsheet/partials/_wallet_panel.html", context, request=request),
            },
            {
                "target": "sheetInventoryPanel",
                "html": render_to_string("charsheet/partials/_inventory_panel.html", context, request=request),
            },
            {
                "target": "sheetCardHand",
                "html": render_to_string("charsheet/partials/_card_hand_host.html", context, request=request),
            },
        ]
    return JsonResponse(response_payload, status=status_code)


def impressum(request):
    """Render imprint page using configurable operator metadata."""
    return render(request, "legal/impressum.html", _legal_context())


def datenschutz(request):
    """Render privacy page with minimal data-processing information."""
    return render(request, "legal/datenschutz.html", _legal_context())


def debug_creature_card(request):
    """Render a standalone creature card preview."""
    creature_ref = str(request.GET.get("creature") or request.GET.get("slug") or "").strip()
    instance_ref = str(request.GET.get("instance") or request.GET.get("character_creature") or "").strip()
    source = None

    if instance_ref:
        queryset = CharacterCreature.objects.select_related("creature")
        source = queryset.filter(pk=instance_ref).first() if instance_ref.isdigit() else None
    elif creature_ref:
        queryset = Creature.objects.all()
        if creature_ref.isdigit():
            source = queryset.filter(pk=creature_ref).first()
        if source is None:
            source = queryset.filter(slug=creature_ref).first()
    else:
        source = Creature.objects.order_by("name").first()

    if source is not None:
        creature_card = CreatureEngine(source).card_context()
        if (
            isinstance(source, CharacterCreature)
            and request.user.is_authenticated
            and source.owner.owner_id == request.user.id
        ):
            creature_card["adjust_damage_url"] = reverse_lazy("adjust_creature_damage", kwargs={"pk": source.pk})
        return render(
            request,
            "charsheet/debug_creature_card.html",
            {
                "creature_card": creature_card,
                "creature_debug_source": source,
            },
        )

    creature_card = {
        "name": "Baer, gross",
        "creature_name": "Baer, gross",
        "image": None,
        "size_class": "G",
        "size_modifier": -1,
        "initiative": -1,
        "vw": 12,
        "sr": 29,
        "gw": 10,
        "gw_extra": 16,
        "gw_extra_label": "F",
        "gw_fear": 16,
        "fear_bonus": 6,
        "rs_natural": 3,
        "rs_armor": 0,
        "rs_total": 3,
        "encumbrance": 0,
        "attacks": [
            {"name": "Biss", "attack_value": 3, "damage": "2w10+3 T", "notes": ""},
            {"name": "Pranke", "attack_value": 6, "damage": "3w10 B", "notes": ""},
            {"name": "Umklammerung", "attack_value": 4, "damage": "-", "notes": ""},
        ],
        "wounds": [
            {"label": "0", "threshold": 12},
            {"label": "-2", "threshold": 24},
            {"label": "-4", "threshold": 36},
            {"label": "-6", "threshold": 48},
            {"label": "Ausser Gefecht", "threshold": 60},
            {"label": "Koma", "threshold": 72},
        ],
        "current_damage": 0,
        "wound_max": 72,
        "wound_zone": {"label": "-", "threshold": 0, "penalty": 0},
        "wound_penalty": 0,
        "attributes": [
            {"label": "ST", "value": 8, "display": "+8"},
            {"label": "KON", "value": 7, "display": "+7"},
            {"label": "GE", "value": 0, "display": "+0"},
            {"label": "INT", "value": -5, "display": "-5"},
            {"label": "WA", "value": -1, "display": "-1"},
            {"label": "WILL", "value": 1, "display": "+1"},
            {"label": "CHA", "value": None, "display": "-"},
        ],
        "skills": [
            {"name": "Aufmerksamkeit", "value": 4},
            {"name": "Ausdauer", "value": 8},
            {"name": "Kraftakt", "value": 13},
            {"name": "Spuren lesen", "value": 6},
            {"name": "Verbergen", "value": 2},
        ],
        "special_skills": [],
        "commands": [
            {"name": "Fass", "slug": "fass", "description": "Greift das markierte Ziel an."},
            {"name": "Zurueck", "slug": "zurueck", "description": "Loest sich vom Ziel und kehrt zurueck."},
        ],
        "traits": [
            {"name": "Festbeissen", "level": None},
            {"name": "Furchtlos", "level": 6},
        ],
        "movement": {
            "combat": 5,
            "march": 10,
            "sprint": 40,
            "swim": 6,
            "fly_combat": None,
            "fly_march": None,
            "fly_sprint": None,
        },
        "movement_display": {
            "combat": "5",
            "march": "10",
            "sprint": "40",
            "swim": "6",
            "fly_combat": None,
            "fly_march": None,
            "fly_sprint": None,
        },
        "organization": "1",
        "climate_and_occurrence": "Mediterrane, gemaessigte und kalte Klimazonen; Waelder, Ebenen, Huegel, Arktis; selten",
    }
    return render(
        request,
        "charsheet/debug_creature_card.html",
        {
            "creature_card": creature_card,
            "creature_debug_source": None,
        },
    )


def encyclopedia(request):
    divine_entities = list(
        DivineEntity.objects.select_related("school")
        .prefetch_related("aspects__aspect")
        .order_by("name")
    )
    selected_entity_id = request.GET.get("entity")
    divine_entity = None
    if selected_entity_id:
        divine_entity = next(
            (
                entity
                for entity in divine_entities
                if str(entity.pk) == str(selected_entity_id)
            ),
            None,
        )
    if divine_entity is None and divine_entities:
        divine_entity = divine_entities[0]

    card_aspects = []
    if divine_entity is not None:
        card_aspects = [
            entry.aspect
            for entry in divine_entity.aspects.all()
            if entry.aspect_id and entry.is_starting_aspect
        ]

    return render(
        request,
        "charsheet/encyclopedia.html",
        {
            "divine_entity": divine_entity,
            "divine_entities": divine_entities,
            "card_aspects": card_aspects,
            "encyclopedia_sections": [
                {
                    "key": "divine_entities",
                    "label": "Gottheiten",
                    "url": request.path,
                    "is_active": True,
                },
            ],
        },
    )
