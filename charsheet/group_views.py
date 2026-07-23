"""HTTP endpoints for game groups and the dedicated game-master UI."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from charsheet.game_groups import (
    GroupError,
    accept_invitation,
    active_role_for,
    add_game_master,
    archive_group,
    create_group,
    create_invitation,
    decline_invitation,
    delete_group,
    end_membership,
    reactivate_group,
    rename_group,
    require_game_master,
    require_leader,
    require_sl_character_access,
    revoke_game_master,
    transfer_leadership,
    user_can_view_group,
    withdraw_invitation,
)
from charsheet.item_transfers import (
    TransferError,
    complete_gm_edit_transfer,
    create_group_transfer,
    recall_group_transfer,
)
from charsheet.engine import ItemEngine
from charsheet.models import (
    Character,
    CharacterDiaryEntry,
    CharacterItem,
    DamageSource,
    GameGroup,
    GameGroupInvitation,
    GameGroupMembership,
    GameGroupRole,
    Item,
    ItemOwnershipEvent,
    ItemTransfer,
    Modifier,
    Rune,
    Quality,
    Skill,
    SkillCategory,
    Specialization,
    WeaponType,
)
from charsheet.constants import (
    ATTRIBUTE_CODE_CHOICES,
    DAMAGE_TYPE_CHOICES,
    GK_CHOICES,
    RULE_FLAG_CHOICES,
    STAT_SLUG_CHOICES,
    WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
    WEAPON_MANEUVER_DAMAGE,
    WEAPON_MASTERY_BONUS,
    WEAPON_MASTERY_EFFECT_DESCRIPTION,
)
from charsheet.shop import (
    _read_magic_modifier_payloads,
    _save_magic_modifiers,
    create_custom_shop_item,
)
from charsheet.magic_effects import TEXT_TARGET_KIND, pack_magic_effect_summary
from charsheet.sheet_context import (
    _load_character_item_modifier_payloads,
    _merge_magic_effect_payloads,
)
from charsheet.views import _build_sheet_context_for_request, _serialize_diary_entry
from charsheet.view_utils import format_modifier


def _group_action(view):
    """Convert domain errors into user-facing messages without weakening services."""
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except (GroupError, TransferError) as exc:
            messages.error(request, exc.message)
            group_id = kwargs.get("group_id")
            if request.POST.get("_sl_screen") == "1" and group_id:
                return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")
            if request.POST.get("_dashboard") == "1":
                return redirect(f"{reverse('dashboard')}#sl-inventar")
            return redirect("game_group_detail", group_id=group_id) if group_id else redirect("dashboard")
    return wrapped


@login_required
@require_POST
@_group_action
def create_game_group(request):
    group = create_group(creator=request.user, name="")
    messages.success(request, "Spielgruppe erstellt.")
    return redirect(f"{reverse('dashboard')}?open_group={group.pk}")


@login_required
@require_POST
@_group_action
def rename_game_group(request, group_id: int):
    group = rename_group(
        group_id=group_id,
        actor=request.user,
        name=request.POST.get("name", ""),
    )
    messages.success(request, "Gruppenname gespeichert.")
    return redirect("game_group_detail", group_id=group.pk)


@login_required
@require_GET
def game_group_detail(request, group_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    if not user_can_view_group(request.user, group):
        raise PermissionDenied
    role = active_role_for(request.user, group)
    is_gm = bool(role)
    is_leader = bool(role and role.role == GameGroupRole.Role.LEADER)
    memberships = list(
        group.memberships.filter(status=GameGroupMembership.Status.ACTIVE)
        .select_related("character", "character__owner", "character__race")
        .order_by("character__name")
    )
    context = {
        "group": group,
        "role": role,
        "is_gm": is_gm,
        "is_leader": is_leader,
        "memberships": memberships,
        "roles": group.role_assignments.filter(is_active=True).select_related("user"),
        "invitations": (
            group.invitations.filter(status=GameGroupInvitation.Status.PENDING)
            .select_related("character", "invited_by")
            if is_gm
            else []
        ),
    }
    return render(request, "charsheet/game_group.html", context)


@login_required
@require_GET
def group_character_search(request, group_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    require_game_master(request.user, group, write=False)
    query = str(request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    mode = str(request.GET.get("mode") or "invite").strip()
    characters = Character.objects.filter(
        is_archived=False,
        name__istartswith=query,
    ).select_related("race", "owner")
    if mode == "recipient":
        characters = characters.filter(
            game_group_memberships__group=group,
            game_group_memberships__status=GameGroupMembership.Status.ACTIVE,
        )
    else:
        active_ids = GameGroupMembership.objects.filter(
            group=group,
            status=GameGroupMembership.Status.ACTIVE,
        ).values("character_id")
        pending_ids = GameGroupInvitation.objects.filter(
            group=group,
            status=GameGroupInvitation.Status.PENDING,
        ).values("character_id")
        characters = characters.exclude(pk__in=active_ids).exclude(pk__in=pending_ids)
    results = [
        {
            "id": character.pk,
            "name": character.name,
            "race": character.race.name,
            "username": character.owner.get_username(),
        }
        for character in characters.order_by("name", "owner__username", "id").distinct()[:20]
    ]
    return JsonResponse({"results": results})


@login_required
@require_GET
def group_character_search(request, group_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    require_game_master(request.user, group, write=False)
    query = str(request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    mode = str(request.GET.get("mode") or "invite").strip()
    characters = Character.objects.filter(
        is_archived=False,
        name__istartswith=query,
    ).select_related("race", "owner")
    if mode == "recipient":
        characters = characters.filter(
            game_group_memberships__group=group,
            game_group_memberships__status=GameGroupMembership.Status.ACTIVE,
        )
    else:
        active_ids = GameGroupMembership.objects.filter(
            group=group,
            status=GameGroupMembership.Status.ACTIVE,
        ).values("character_id")
        pending_ids = GameGroupInvitation.objects.filter(
            group=group,
            status=GameGroupInvitation.Status.PENDING,
        ).values("character_id")
        characters = characters.exclude(pk__in=active_ids).exclude(pk__in=pending_ids)
    results = [
        {
            "id": character.pk,
            "name": character.name,
            "race": character.race.name,
            "username": character.owner.get_username(),
        }
        for character in characters.order_by("name", "owner__username", "id").distinct()[:20]
    ]
    return JsonResponse({"results": results})


@login_required
@require_POST
@_group_action
def invite_group_character(request, group_id: int):
    character = get_object_or_404(Character, pk=request.POST.get("character_id"))
    create_invitation(
        group_id=group_id,
        actor=request.user,
        character=character,
        message=request.POST.get("message", ""),
    )
    messages.success(request, "Einladung versendet.")
    return redirect(f"{reverse('game_group_detail', args=[group_id])}?dashboard_refresh=quiet")


@login_required
@require_POST
@_group_action
def accept_group_invitation(request, invitation_id: int):
    accept_invitation(invitation_id=invitation_id, user=request.user)
    messages.success(request, "Einladung angenommen.")
    return redirect("dashboard")


@login_required
@require_POST
@_group_action
def decline_group_invitation(request, invitation_id: int):
    decline_invitation(invitation_id=invitation_id, user=request.user)
    messages.success(request, "Einladung abgelehnt.")
    return redirect("dashboard")


@login_required
@require_POST
@_group_action
def withdraw_group_invitation(request, group_id: int, invitation_id: int):
    withdraw_invitation(invitation_id=invitation_id, actor=request.user)
    messages.success(request, "Einladung zurückgezogen.")
    return redirect(f"{reverse('game_group_detail', args=[group_id])}?dashboard_refresh=quiet")


@login_required
@require_POST
@_group_action
def leave_game_group(request, group_id: int, membership_id: int):
    end_membership(membership_id=membership_id, owner=request.user)
    messages.success(request, "Gruppe verlassen.")
    group = get_object_or_404(GameGroup, pk=group_id)
    if user_can_view_group(request.user, group):
        return redirect(f"{reverse('game_group_detail', args=[group_id])}?dashboard_refresh=quiet")
    return redirect("dashboard")


@login_required
@require_POST
@_group_action
def remove_group_member(request, group_id: int, membership_id: int):
    end_membership(membership_id=membership_id, actor=request.user)
    messages.success(request, "Mitglied entfernt.")
    return redirect(f"{reverse('game_group_detail', args=[group_id])}?dashboard_refresh=quiet")


@login_required
@require_POST
@_group_action
def add_group_gm(request, group_id: int):
    user = get_object_or_404(get_user_model(), username=request.POST.get("username", "").strip())
    add_game_master(group_id=group_id, actor=request.user, user=user)
    messages.success(request, "SL-Rolle vergeben.")
    return redirect("game_group_detail", group_id=group_id)


@login_required
@require_POST
@_group_action
def revoke_group_gm(request, group_id: int, user_id: int):
    user = get_object_or_404(get_user_model(), pk=user_id)
    revoke_game_master(group_id=group_id, actor=request.user, user=user)
    messages.success(request, "SL-Rolle entzogen.")
    return redirect("game_group_detail", group_id=group_id)


@login_required
@require_POST
@_group_action
def transfer_group_leader(request, group_id: int, user_id: int):
    user = get_object_or_404(get_user_model(), pk=user_id)
    transfer_leadership(group_id=group_id, actor=request.user, new_leader=user)
    messages.success(request, "Gruppenleitung übertragen.")
    return redirect("game_group_detail", group_id=group_id)


@login_required
@require_POST
@_group_action
def archive_game_group(request, group_id: int):
    archive_group(group_id=group_id, actor=request.user)
    messages.success(request, "Spielgruppe archiviert.")
    return redirect("game_group_detail", group_id=group_id)


@login_required
@require_POST
@_group_action
def reactivate_game_group(request, group_id: int):
    reactivate_group(group_id=group_id, actor=request.user)
    messages.success(request, "Spielgruppe reaktiviert.")
    return redirect("game_group_detail", group_id=group_id)


@login_required
@require_POST
@_group_action
def delete_game_group(request, group_id: int):
    name = delete_group(group_id=group_id, actor=request.user)
    messages.success(request, f"Spielgruppe {name} wurde gelöscht.")
    return redirect("dashboard")


@login_required
@require_GET
def game_master_screen(request, group_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    require_game_master(request.user, group)
    roster = []
    memberships = (
        group.memberships.filter(
            status=GameGroupMembership.Status.ACTIVE,
            character__is_archived=False,
        )
        .select_related("character", "character__race")
        .order_by("character__name")
    )
    for membership in memberships:
        character = membership.character
        engine = character.get_engine(refresh=True)
        thresholds = engine.wound_thresholds()
        max_lp = max(thresholds, default=0)
        stun_damage = max(0, int(character.current_stun_damage or 0))
        lethal_damage = max(0, int(character.current_lethal_damage or 0))
        displayed_stun_damage = min(stun_damage, max_lp)
        displayed_lethal_damage = min(lethal_damage, max(0, max_lp - displayed_stun_damage))
        max_kp = max(0, int(engine.calculate_arcane_power()))
        current_kp = min(max_kp, max(0, int(character.current_arcane_power or 0)))
        initiative = int(engine.calculate_initiative())
        armor_load_penalty = int(engine.load_penalty())
        carry_state = ItemEngine.carry_state_for_character(character)
        carry_penalty = int(carry_state["penalty"]) if character.carry_load_enabled else 0
        load_penalty = armor_load_penalty + carry_penalty
        wound_stage, _wound_stage_penalty = engine.current_wound_stage()
        wound_penalty = engine.current_wound_penalty()
        is_dead = wound_stage == "Tod"
        is_incapacitated = wound_stage in {"Ausser Gefecht", "Außer Gefecht", "Koma"}
        attributes = engine.attributes()
        roster.append(
            {
                "membership": membership,
                "character": character,
                "attributes": {
                    key: {
                        "value": value,
                        "modifier": format_modifier(engine.attribute_modifier(key)),
                    }
                    for key, value in attributes.items()
                },
                "vw": engine.vw(),
                "gw": engine.gw(),
                "sr": engine.sr(),
                "potential": engine.calculate_potential(),
                "total_armor": engine.get_grs(),
                "initiative": initiative,
                "initiative_with_load": initiative + load_penalty,
                "initiative_display": format_modifier(initiative),
                "initiative_with_load_display": format_modifier(
                    initiative + load_penalty
                ),
                "load_penalty": load_penalty,
                "wound_stage": wound_stage,
                "wound_penalty_display": format_modifier(wound_penalty),
                "is_incapacitated": is_incapacitated,
                "is_dead": is_dead,
                "current_kp": current_kp,
                "max_kp": max_kp,
                "max_lp": max_lp,
                "current_lp": max(0, max_lp - stun_damage - lethal_damage),
                "stun_damage": stun_damage,
                "lethal_damage": lethal_damage,
                "stun_damage_percent": f"{displayed_stun_damage / max_lp * 100:.4f}" if max_lp else "0",
                "lethal_damage_percent": f"{displayed_lethal_damage / max_lp * 100:.4f}" if max_lp else "0",
            }
        )
    inventory_items = list(
        CharacterItem.objects.filter(group_owner=group)
        .select_related(
            "item",
            "quality",
            "item__weaponstats__weapon_type",
            "item__weaponstats__damage_source",
            "item__armorstats",
            "item__shieldstats",
        )
        .prefetch_related("runes", "item_runes", "rune_specs")
        .order_by("item__name", "id")
    )
    shared_edit_transfers = list(
        ItemTransfer.objects.filter(
            recipient_group=group,
            transfer_kind=ItemTransfer.TransferKind.GM_EDIT,
            status=ItemTransfer.Status.PENDING,
            item__owner__is_archived=False,
            item__owner__game_group_memberships__group=group,
            item__owner__game_group_memberships__status=GameGroupMembership.Status.ACTIVE,
        )
        .select_related(
            "item__owner",
            "item__item",
            "item__quality",
            "item__item__weaponstats__weapon_type",
            "item__item__weaponstats__damage_source",
            "item__item__armorstats",
            "item__item__shieldstats",
        )
        .prefetch_related("item__runes", "item__item_runes", "item__rune_specs")
        .order_by("item__item__name", "item_id")
    )
    known_item_ids = {row.id for row in inventory_items}
    for edit_transfer in shared_edit_transfers:
        if (
            not edit_transfer.item_id
            or edit_transfer.item_id in known_item_ids
            or edit_transfer.sender_id != edit_transfer.item.owner_id
        ):
            continue
        edit_transfer.item.sl_edit_access = True
        edit_transfer.item.sl_edit_owner_name = edit_transfer.item.owner.name
        edit_transfer.item.sl_edit_transfer_id = edit_transfer.id
        inventory_items.append(edit_transfer.item)
        known_item_ids.add(edit_transfer.item_id)
    for inventory_item in inventory_items:
        item = inventory_item.item
        weapon = getattr(item, "weaponstats", None)
        armor = getattr(item, "armorstats", None)
        shield = getattr(item, "shieldstats", None)
        inventory_item.base_values = {
            "price": item.price,
            "weight": item.weight,
            "size_class": item.get_size_class_display(),
            "weapon_type": getattr(getattr(weapon, "weapon_type", None), "name", "Nicht festgelegt"),
            "weapon_damage_source": getattr(getattr(weapon, "damage_source", None), "name", "Nicht festgelegt"),
            "weapon_maneuver_attribute": weapon.get_maneuver_attribute_mode_display() if weapon else "Nicht festgelegt",
            "weapon_wield_mode": weapon.get_wield_mode_display() if weapon else "Nicht festgelegt",
            "weapon_damage_dice_amount": getattr(weapon, "damage_dice_amount", ""),
            "weapon_damage_dice_faces": getattr(weapon, "damage_dice_faces", ""),
            "weapon_damage_flat_bonus": getattr(weapon, "damage_flat_bonus", ""),
            "weapon_damage_flat_operator": (
                weapon.get_damage_flat_operator_display() if weapon else "Kein Operator"
            ),
            "weapon_damage_type": weapon.get_damage_type_display() if weapon else "Nicht festgelegt",
            "weapon_min_st": getattr(weapon, "min_st", ""),
            "weapon_h2_dice_amount": getattr(weapon, "h2_dice_amount", "") or "Nicht festgelegt",
            "weapon_h2_dice_faces": getattr(weapon, "h2_dice_faces", "") or "Nicht festgelegt",
            "weapon_h2_flat_bonus": getattr(weapon, "h2_flat_bonus", "") if weapon else "",
            "weapon_h2_flat_operator": (
                weapon.get_h2_flat_operator_display() if weapon else "Kein Operator"
            ),
            "weapon_h2_damage_type": weapon.get_h2_damage_type_display() if weapon else "Nicht festgelegt",
            "armor_rs_total": getattr(armor, "rs_total", ""),
            "armor_rs_head": getattr(armor, "rs_head", ""),
            "armor_rs_torso": getattr(armor, "rs_torso", ""),
            "armor_rs_arm_left": getattr(armor, "rs_arm_left", ""),
            "armor_rs_arm_right": getattr(armor, "rs_arm_right", ""),
            "armor_rs_leg_left": getattr(armor, "rs_leg_left", ""),
            "armor_rs_leg_right": getattr(armor, "rs_leg_right", ""),
            "armor_encumbrance": getattr(armor, "encumbrance", ""),
            "armor_min_st": getattr(armor, "min_st", ""),
            "shield_rs": getattr(shield, "rs", ""),
            "shield_encumbrance": getattr(shield, "encumbrance", ""),
            "shield_min_st": getattr(shield, "min_st", ""),
        }
    modifier_payloads_by_item = _load_character_item_modifier_payloads(inventory_items)
    for inventory_item in inventory_items:
        _visible_summary, magic_payloads = _merge_magic_effect_payloads(
            effect_summary=inventory_item.magic_effect_summary or "",
            modifier_payloads=modifier_payloads_by_item.get(inventory_item.id, []),
        )
        inventory_item.magic_modifier_payloads_json = json.dumps(magic_payloads)
    pending_transfers = list(
        ItemTransfer.objects.filter(
            sender_group=group,
            status=ItemTransfer.Status.PENDING,
        )
        .select_related("recipient", "item__item")
        .order_by("-created_at")
    )
    pending_transfer_by_item_id = {
        transfer.item_id: transfer
        for transfer in pending_transfers
        if transfer.item_id
    }
    for inventory_item in inventory_items:
        inventory_item.sl_pending_transfer = pending_transfer_by_item_id.get(
            inventory_item.id
        )
    screen_state_signature = "|".join(
        [
            ",".join(str(transfer.id) for transfer in pending_transfers),
            ";".join(
                f"{row['character'].id}:{row['character'].current_stun_damage}:"
                f"{row['character'].current_lethal_damage}:"
                f"{row['character'].current_arcane_power}:"
                f"{row['load_penalty']}:{row['total_armor']}:"
                f"{int(row['character'].carry_load_enabled)}"
                for row in roster
            ),
        ]
    )
    inventory_row = {
        "group": group,
        "memberships": list(memberships),
        "inventory_items": inventory_items,
        "catalog_items": list(Item.objects.filter(catalog_group=group).order_by("name")),
        "pending_transfers": pending_transfers,
        "screen_state_signature": screen_state_signature,
    }
    return render(
        request,
        "charsheet/game_master_screen.html",
        {
            "group": group,
            "roster": roster,
            "sl_inventory_groups": [inventory_row],
            "group_inventory_global_items": Item.objects.filter(
                catalog_group__isnull=True
            ).order_by("name"),
            "group_inventory_qualities": Quality.objects.all(),
            "group_inventory_item_types": Item.ItemType.choices,
            "group_inventory_size_classes": GK_CHOICES,
            "group_inventory_damage_types": DAMAGE_TYPE_CHOICES,
            "group_inventory_maneuver_attributes": WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
            "group_inventory_damage_sources": DamageSource.objects.order_by("name"),
            "group_inventory_weapon_types": WeaponType.objects.order_by("sort_order", "name"),
            "group_inventory_weapon_skills": Skill.objects.select_related("category").order_by("name"),
            "group_inventory_runes": Rune.objects.order_by("name"),
            "group_inventory_effect_kinds": [
                ("text", "Nur Beschreibung"),
                ("rule_flag", "Regel aktivieren"),
                ("attribute", "Attribut"),
                ("stat", "Wert auf dem Bogen"),
                ("skill", "Einzelne Fertigkeit"),
                ("category", "Fertigkeitskategorie"),
                ("weapon_maneuver", "Bonus/Malus auf Manöver"),
                ("weapon_damage", "Bonus/Malus auf Schaden"),
                ("weapon_damage_dice", "Zusätzliche Schadenswürfel"),
                (WEAPON_MANEUVER_DAMAGE, "Bonus/Malus auf Manöver und Schaden"),
                (WEAPON_MASTERY_BONUS, WEAPON_MASTERY_EFFECT_DESCRIPTION),
                ("item_category", "Alle Gegenstände eines Typs"),
                ("specialization", "Spezialisierung"),
            ],
            "group_inventory_effect_attributes": ATTRIBUTE_CODE_CHOICES,
            "group_inventory_effect_stats": STAT_SLUG_CHOICES,
            "group_inventory_effect_rules": RULE_FLAG_CHOICES,
            "group_inventory_skill_categories": SkillCategory.objects.order_by("name"),
            "group_inventory_specializations": Specialization.objects.order_by("name"),
        },
    )


@login_required
@require_GET
def group_inventory_transfer_state(request, group_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    require_game_master(request.user, group)
    pending_ids = list(
        ItemTransfer.objects.filter(
            sender_group=group,
            status=ItemTransfer.Status.PENDING,
        )
        .order_by("-created_at")
        .values_list("id", flat=True)
    )
    active_memberships = GameGroupMembership.objects.filter(
        group=group,
        status=GameGroupMembership.Status.ACTIVE,
        character__is_archived=False,
    ).select_related("character").order_by("character__name")
    character_states = []
    for membership in active_memberships:
        character = membership.character
        engine = character.get_engine(refresh=True)
        character_states.append(
            (
                character.id,
                character.current_stun_damage,
                character.current_lethal_damage,
                character.current_arcane_power,
                int(engine.load_penalty())
                + (
                    int(ItemEngine.carry_state_for_character(character)["penalty"])
                    if character.carry_load_enabled
                    else 0
                ),
                engine.get_grs(),
                int(character.carry_load_enabled),
            )
        )
    return JsonResponse(
        {
            "signature": "|".join(
                [
                    ",".join(str(transfer_id) for transfer_id in pending_ids),
                    ";".join(":".join(str(value) for value in row) for row in character_states),
                ]
            )
        }
    )


@login_required
@require_GET
def game_master_character_sheet(request, group_id: int, character_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    character = get_object_or_404(Character, pk=character_id)
    require_sl_character_access(request.user, group, character)
    context = _build_sheet_context_for_request(request, character, read_only=True)
    context["read_only_diary_url"] = reverse(
        "game_master_character_diary", args=[group.pk, character.pk]
    )
    return render(request, "charsheet/charsheet.html", context)


@login_required
@require_GET
def game_master_character_diary(request, group_id: int, character_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    character = get_object_or_404(Character, pk=character_id)
    require_sl_character_access(request.user, group, character)
    entries = [
        _serialize_diary_entry(entry)
        for entry in CharacterDiaryEntry.objects.filter(character=character).order_by("order_index", "id")
    ]
    return JsonResponse({"ok": True, "entries": entries, "current_entry_id": entries[-1]["id"] if entries else None})


@login_required
@require_POST
@_group_action
def add_group_inventory_item(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        item = get_object_or_404(Item, pk=request.POST.get("item_id"))
        if item.catalog_group_id not in (None, group.id):
            raise PermissionDenied
        amount = max(1, int(request.POST.get("amount") or 1))
        if not item.stackable:
            amount = 1
        quality_id = request.POST.get("quality") or item.default_quality_id
        instance = CharacterItem(
            item=item,
            owner=None,
            group_owner=group,
            original_owner_character=None,
            original_owner_group=group,
            amount=amount,
            quality_id=quality_id,
        )
        instance.full_clean()
        instance.save()
    messages.success(request, "Gegenstand ins Gruppeninventar gelegt.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def create_group_catalog_item(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        is_magic = bool(request.POST.get("is_magic")) or request.POST.get("item_type") == Item.ItemType.MAGIC_ITEM
        try:
            magic_effects = json.loads(request.POST.get("magic_modifier_payloads") or "[]")
        except json.JSONDecodeError as exc:
            raise GroupError("invalid_item", "Die magischen Effekte sind ungültig.") from exc
        if is_magic and (not isinstance(magic_effects, list) or not magic_effects):
            raise GroupError(
                "missing_magic_effect",
                "Ein magischer Gegenstand benötigt mindestens einen definierten Effekt.",
            )
        item = create_custom_shop_item(request.POST, request.FILES, catalog_group=group)
        if not item:
            raise GroupError("invalid_item", "Das Basisitem konnte nicht angelegt werden.")
        instance = CharacterItem(
            item=item,
            group_owner=group,
            original_owner_group=group,
            amount=max(1, int(request.POST.get("amount") or 1)) if item.stackable else 1,
            quality=item.default_quality,
        )
        instance.full_clean()
        instance.save()
    messages.success(request, "Gruppenprivates Basisitem und Instanz angelegt.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def edit_group_catalog_item(request, group_id: int, catalog_item_id: int):
    """Edit group-owned master data on Item and its existing detail models."""
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        item = get_object_or_404(
            Item.objects.select_for_update(),
            pk=catalog_item_id,
            catalog_group=group,
        )
        item.name = str(request.POST.get("name") or item.name).strip()[:200]
        item.description = str(request.POST.get("description") or "").strip()
        try:
            item.price = max(0, int(request.POST.get("price") or 0))
            item.weight = max(Decimal("0"), Decimal(str(request.POST.get("weight") or "0")))
        except (ValueError, InvalidOperation) as exc:
            raise GroupError("invalid_item", "Preis oder Gewicht ist ungültig.") from exc
        item.size_class = str(request.POST.get("size_class") or item.size_class)
        item.default_quality = get_object_or_404(
            Quality, pk=request.POST.get("default_quality") or item.default_quality_id
        )
        item.full_clean()
        item.save()
        if "rune_ids" in request.POST:
            item.runes.set(Rune.objects.filter(pk__in=request.POST.getlist("rune_ids")))
        detail = (
            getattr(item, "weaponstats", None)
            or getattr(item, "armorstats", None)
            or getattr(item, "shieldstats", None)
        )
        if detail is not None:
            numeric_fields = {
                field.name
                for field in detail._meta.concrete_fields
                if field.name not in {"id", "item"} and field.get_internal_type() in {
                    "IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField"
                }
            }
            for field_name in numeric_fields:
                if field_name in request.POST and str(request.POST[field_name]).strip():
                    setattr(detail, field_name, int(request.POST[field_name]))
            if hasattr(detail, "damage_source_id") and request.POST.get("damage_source"):
                detail.damage_source = get_object_or_404(DamageSource, pk=request.POST["damage_source"])
            for field_name in ("damage_type", "h2_damage_type", "wield_mode", "maneuver_attribute_mode"):
                if hasattr(detail, field_name) and request.POST.get(field_name):
                    setattr(detail, field_name, request.POST[field_name])
            detail.full_clean()
            detail.save()
        magic_stats = getattr(item, "magicitemstats", None)
        if magic_stats is not None and "magic_effect_summary" in request.POST:
            magic_stats.effect_summary = str(request.POST.get("magic_effect_summary") or "").strip()
            magic_stats.full_clean()
            magic_stats.save(update_fields=["effect_summary"])
    messages.success(request, "Basisitem-Stammdaten gespeichert.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def edit_group_inventory_item(request, group_id: int, item_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        instance = get_object_or_404(
            CharacterItem.objects.select_for_update(of=("self",)).select_related("item", "owner"),
            pk=item_id,
        )
        is_group_item = instance.group_owner_id == group.id
        has_gm_edit_access = (
            instance.owner_id is not None
            and GameGroupMembership.objects.select_for_update().filter(
                group=group,
                character_id=instance.owner_id,
                status=GameGroupMembership.Status.ACTIVE,
            ).exists()
            and ItemTransfer.objects.select_for_update().filter(
                item=instance,
                sender_id=instance.owner_id,
                recipient_group=group,
                transfer_kind=ItemTransfer.TransferKind.GM_EDIT,
                status=ItemTransfer.Status.PENDING,
            ).exists()
        )
        if not is_group_item and not has_gm_edit_access:
            raise GroupError("not_authorized", "Dieses Item wurde der Gruppenleitung nicht zur Bearbeitung freigegeben.", status=403)
        if instance.transfers.filter(status=ItemTransfer.Status.PENDING).exclude(
            transfer_kind=ItemTransfer.TransferKind.GM_EDIT,
            recipient_group=group,
        ).exists():
            raise GroupError("pending_transfer", "Eine angebotene Instanz kann nicht verändert werden.", status=409)
        amount = max(1, int(request.POST.get("amount") or instance.amount))
        if not instance.item.stackable and amount != 1:
            raise GroupError("not_stackable", "Nicht stapelbare Gegenstände haben immer Menge 1.")
        quality = get_object_or_404(Quality, pk=request.POST.get("quality") or instance.quality_id)
        name = str(request.POST.get("name") or "").strip()
        description = str(request.POST.get("description") or "").strip()
        try:
            magic_modifier_payloads = _read_magic_modifier_payloads(request.POST)
        except (ValidationError, ValueError) as exc:
            raise GroupError("invalid_magic_effect", "Mindestens ein magischer Effekt ist ungültig.") from exc
        text_effect_descriptions = [
            {
                "effect_description": str(payload.get("effect_description") or "").strip(),
                "display_order": int(payload.get("display_order") or 0),
            }
            for payload in magic_modifier_payloads
            if str(payload.get("target_kind") or "") == TEXT_TARGET_KIND
            and str(payload.get("effect_description") or "").strip()
        ]
        magic_summary = pack_magic_effect_summary("", text_effect_descriptions)
        instance.amount = amount
        instance.quality = quality
        instance.name_override = "" if not name or name == instance.item.name else name
        instance.description = "" if description == str(instance.item.description or "").strip() else description
        instance.magic_effect_summary = magic_summary
        instance.is_magic = bool(magic_modifier_payloads)
        if request.FILES.get("image_override"):
            instance.image_override = request.FILES["image_override"]
        raw_price = str(request.POST.get("price_override") or "").strip()
        raw_weight = str(request.POST.get("weight_override") or "").strip()
        try:
            instance.price_override = max(0, int(raw_price)) if raw_price else None
            instance.weight_override = max(Decimal("0"), Decimal(raw_weight)) if raw_weight else None
        except (ValueError, InvalidOperation) as exc:
            raise GroupError("invalid_item", "Preis oder Gewicht ist ungültig.") from exc
        instance.size_class_override = str(request.POST.get("size_class_override") or "")

        typed_override_fields = {
            Item.ItemType.WEAPON: (
                "weapon_damage_dice_amount_override",
                "weapon_damage_dice_faces_override",
                "weapon_damage_flat_bonus_override",
                "weapon_min_st_override",
                "weapon_h2_dice_amount_override",
                "weapon_h2_dice_faces_override",
                "weapon_h2_flat_bonus_override",
            ),
            Item.ItemType.ARMOR: (
                "armor_rs_total_override",
                "armor_rs_head_override",
                "armor_rs_torso_override",
                "armor_rs_arm_left_override",
                "armor_rs_arm_right_override",
                "armor_rs_leg_left_override",
                "armor_rs_leg_right_override",
                "armor_encumbrance_override",
                "armor_min_st_override",
            ),
            Item.ItemType.SHIELD: (
                "shield_rs_override",
                "shield_encumbrance_override",
                "shield_min_st_override",
            ),
        }
        active_override_fields = typed_override_fields.get(instance.item.item_type, ())
        for field_name in active_override_fields:
            raw_value = str(request.POST.get(field_name) or "").strip()
            try:
                setattr(instance, field_name, int(raw_value) if raw_value else None)
            except ValueError as exc:
                raise GroupError("invalid_item", "Ein Instanzwert ist ungültig.") from exc
        if instance.item.item_type == Item.ItemType.WEAPON:
            instance.weapon_type_override_id = request.POST.get("weapon_type_override") or None
            instance.weapon_damage_source_override_id = request.POST.get("weapon_damage_source_override") or None
            instance.weapon_damage_type_override = str(request.POST.get("weapon_damage_type_override") or "")
            instance.weapon_maneuver_attribute_override = str(
                request.POST.get("weapon_maneuver_attribute_override") or ""
            )
            instance.weapon_wield_mode_override = str(request.POST.get("weapon_wield_mode_override") or "")
            instance.weapon_damage_flat_operator_override = str(
                request.POST.get("weapon_damage_flat_operator_override") or ""
            )
            instance.weapon_h2_flat_operator_override = str(
                request.POST.get("weapon_h2_flat_operator_override") or ""
            )
            instance.weapon_h2_damage_type_override = str(
                request.POST.get("weapon_h2_damage_type_override") or ""
            )
        instance.full_clean()
        instance.save(
            update_fields=[
                "amount", "quality", "name_override", "description",
                "magic_effect_summary", "is_magic", "price_override",
                "weight_override", "size_class_override", "image_override",
                *active_override_fields,
                *(
                    (
                        "weapon_type_override",
                        "weapon_damage_source_override",
                        "weapon_damage_type_override",
                        "weapon_maneuver_attribute_override",
                        "weapon_wield_mode_override",
                        "weapon_damage_flat_operator_override",
                        "weapon_h2_flat_operator_override",
                        "weapon_h2_damage_type_override",
                    )
                    if instance.item.item_type == Item.ItemType.WEAPON
                    else ()
                ),
            ]
        )
        instance.runes.set(Rune.objects.filter(pk__in=request.POST.getlist("instance_runes")))
        _save_magic_modifiers(
            source_model=CharacterItem,
            source_id=instance.id,
            magic_modifier_payloads=magic_modifier_payloads,
        )
    messages.success(request, "Instanzanpassung gespeichert.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def delete_group_inventory_item(request, group_id: int, item_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        instance = get_object_or_404(
            CharacterItem.objects.select_for_update().select_related("item", "quality"),
            pk=item_id,
            group_owner=group,
        )
        if instance.transfers.filter(status=ItemTransfer.Status.PENDING).exists():
            raise GroupError(
                "pending_transfer",
                "Eine angebotene Instanz kann nicht gelöscht werden.",
                status=409,
            )
        ItemOwnershipEvent.objects.create(
            item=instance,
            item_provenance_id=instance.provenance_id,
            event_type=ItemOwnershipEvent.EventType.DESTROYED,
            actor_user=request.user,
            original_owner_group=group,
            from_group=group,
            details={
                "reason": "group_inventory_delete",
                "snapshot": {
                    "name": instance.effective_name,
                    "item_id": instance.item_id,
                    "item_type": instance.item.item_type,
                    "quality": str(instance.quality),
                    "amount": instance.amount,
                },
            },
        )
        source_type = ContentType.objects.get_for_model(CharacterItem, for_concrete_model=False)
        Modifier.objects.filter(
            source_content_type=source_type,
            source_object_id=instance.id,
        ).delete()
        instance.delete()
    messages.success(request, "Gegenstand aus dem Gruppeninventar gelöscht.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def send_group_inventory_item(request, group_id: int, item_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    recipient = get_object_or_404(Character, pk=request.POST.get("recipient_id"))
    transfer = create_group_transfer(
        item_id=item_id,
        group=group,
        actor=request.user,
        recipient=recipient,
        quantity=max(1, int(request.POST.get("quantity") or 1)),
        message=request.POST.get("message", ""),
    )
    messages.success(request, f"Angebot an {transfer.recipient.name} versendet.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def complete_group_item_edit(request, group_id: int, transfer_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    complete_gm_edit_transfer(transfer_id=transfer_id, group=group, actor=request.user)
    messages.success(request, "Bearbeitung abgeschlossen und Gegenstand zurückgesendet.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")


@login_required
@require_POST
@_group_action
def recall_group_inventory_transfer(request, group_id: int, transfer_id: int):
    group = get_object_or_404(GameGroup, pk=group_id)
    recall_group_transfer(transfer_id=transfer_id, group=group, actor=request.user)
    messages.success(request, "Angebot zurückgerufen.")
    return redirect(f"{reverse('game_master_screen', args=[group_id])}#sl-inventar")
