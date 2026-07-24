"""HTTP endpoints for game groups and the dedicated game-master UI."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from html import escape
from html.parser import HTMLParser

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Max, Q
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
from charsheet.engine.creature_engine import CreatureEngine
from charsheet.models import (
    Character,
    CharacterCreature,
    CharacterDiaryEntry,
    CharacterItem,
    DamageSource,
    Creature,
    GameGroup,
    GameGroupCreature,
    GameGroupInvitation,
    GameGroupMembership,
    GameGroupRole,
    GameGroupTable,
    GameGroupTableCell,
    GameGroupTableColumn,
    GameGroupTableRow,
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
                anchor = request.POST.get("_sl_anchor")
                if anchor not in {"sl-charaktere", "sl-inventar", "sl-tabellen"}:
                    anchor = "sl-inventar"
                screen_url = reverse("game_master_screen", args=[group_id])
                edit_table_id = request.POST.get("_edit_table_id")
                if anchor == "sl-tabellen" and str(edit_table_id or "").isdigit():
                    screen_url = f"{screen_url}?edit_table={edit_table_id}"
                return redirect(f"{screen_url}#{anchor}")
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
        .order_by(
            F("screen_position").asc(nulls_last=True),
            "character__name",
            "id",
        )
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
        subtitle = character.race.name
        if wound_stage != "-":
            subtitle += f" · {wound_stage}"
            if format_modifier(wound_penalty) != "0":
                subtitle += f" ({format_modifier(wound_penalty)})"
        roster.append(
            {
                "card_kind": "character",
                "card_id": f"character:{membership.id}",
                "screen_position": membership.screen_position,
                "screen_is_collapsed": membership.screen_is_collapsed,
                "screen_state_url": reverse(
                    "set_group_membership_screen_state",
                    args=[group.id, membership.id],
                ),
                "kind_label": "Charakter",
                "name": character.name,
                "subtitle": subtitle,
                "image": character.char_picture,
                "fallback_letter": character.name[:1],
                "potential_label": "Pot",
                "show_arcane": True,
                "footer_label": "Vollständigen Bogen öffnen",
                "detail_url": reverse(
                    "game_master_character_sheet",
                    args=[group.id, character.id],
                ),
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
    creature_cards = list(
        group.screen_creatures.select_related(
            "creature",
            "creature__quality",
            "character_creature",
            "character_creature__owner",
            "character_creature__creature",
            "character_creature__quality",
            "character_creature__source_binding",
        ).prefetch_related(
            "creature__attributes__attribute",
        )
    )
    for creature_card in creature_cards:
        creature = creature_card.creature
        character_creature = creature_card.character_creature
        creature_source = character_creature or creature
        engine = CreatureEngine(creature_source)
        wound_rows = engine.wound_rows()
        max_lp = wound_rows[-1]["threshold"] if wound_rows else 0
        stun_damage = max(0, int(creature_card.current_stun_damage or 0))
        lethal_damage = max(0, int(creature_card.current_lethal_damage or 0))
        current_damage = stun_damage + lethal_damage
        displayed_stun_damage = min(stun_damage, max_lp)
        displayed_lethal_damage = min(
            lethal_damage,
            max(0, max_lp - displayed_stun_damage),
        )
        wound_stage = "-"
        wound_penalty = 0
        for wound_row in wound_rows:
            if current_damage < int(wound_row["threshold"]):
                break
            wound_stage = wound_row["label"]
            wound_penalty = int(wound_row["penalty"])
        if max_lp and current_damage > max_lp:
            wound_stage = "Tod"
            wound_penalty = 0
        is_dead = wound_stage == "Tod"
        is_incapacitated = wound_stage in {
            "Ausser Gefecht",
            "Außer Gefecht",
            "Koma",
        }
        creature_attributes = {}
        for attribute in engine.attribute_rows():
            modifier = attribute["value"]
            creature_attributes[attribute["label"]] = {
                "value": "-" if modifier is None else int(modifier) + 5,
                "modifier": attribute["display"],
            }
        subtitle_parts = []
        if character_creature:
            subtitle_parts.append(character_creature.owner.name)
        if wound_stage != "-":
            wound_status = wound_stage
            if format_modifier(wound_penalty) != "0":
                wound_status += f" ({format_modifier(wound_penalty)})"
            subtitle_parts.append(wound_status)
        subtitle = " · ".join(subtitle_parts)
        movement = engine.movement_display()
        movement_values = [
            movement.get(key)
            for key in ("combat", "march", "sprint")
            if movement.get(key) not in (None, "")
        ]
        creature_kp = engine.kp()
        creature_potential = engine.potential()
        has_creature_kp = creature_kp is not None
        creature_kp_max = max(0, int(creature_kp or 0))
        creature_current_kp = (
            creature_kp_max
            if creature_card.current_kp is None
            else max(0, min(creature_kp_max, int(creature_card.current_kp)))
        )
        roster.append(
            {
                "card_kind": "creature",
                "card_id": f"creature:{creature_card.id}",
                "screen_position": creature_card.screen_position,
                "screen_is_collapsed": creature_card.screen_is_collapsed,
                "screen_state_url": reverse(
                    "set_group_creature_screen_state",
                    args=[group.id, creature_card.id],
                ),
                "kind_label": (
                    character_creature.source_binding.choice_label
                    if character_creature
                    and character_creature.source_binding
                    and character_creature.source_binding.choice_label
                    else "Kreatur"
                ),
                "name": creature_source.display_name,
                "subtitle": subtitle,
                "image": creature_source.image,
                "fallback_letter": creature_source.display_name[:1],
                "potential_label": "Pot" if has_creature_kp else "GK",
                "show_arcane": has_creature_kp,
                "secondary_status_label": "Bewegung",
                "secondary_status_value": " / ".join(movement_values) or "–",
                "creature_damage_rows": (
                    ("B", stun_damage),
                    ("T", lethal_damage),
                ),
                "footer_label": (
                    creature.organization.strip()
                    or f"Kreatur · {creature.quality.name}"
                ),
                "detail_url": "",
                "group_creature": creature_card,
                "creature": creature,
                "character_creature": character_creature,
                "attributes": creature_attributes,
                "vw": engine.vw(),
                "gw": engine.gw(),
                "sr": engine.sr(),
                "potential": creature_potential if has_creature_kp else engine.size_class(),
                "total_armor": engine.armor_totals().total_rs,
                "initiative": engine.initiative(),
                "initiative_with_load": engine.initiative(),
                "initiative_display": format_modifier(engine.initiative()),
                "initiative_with_load_display": format_modifier(engine.initiative()),
                "load_penalty": 0,
                "wound_stage": wound_stage,
                "wound_penalty_display": format_modifier(wound_penalty),
                "is_incapacitated": is_incapacitated,
                "is_dead": is_dead,
                "current_kp": creature_current_kp,
                "max_kp": creature_kp_max,
                "max_lp": max_lp,
                "current_lp": max(0, max_lp - current_damage),
                "stun_damage": stun_damage,
                "lethal_damage": lethal_damage,
                "stun_damage_percent": (
                    f"{displayed_stun_damage / max_lp * 100:.4f}"
                    if max_lp
                    else "0"
                ),
                "lethal_damage_percent": (
                    f"{displayed_lethal_damage / max_lp * 100:.4f}"
                    if max_lp
                    else "0"
                ),
            }
        )
    roster.sort(
        key=lambda row: (
            row["screen_position"] is None,
            row["screen_position"] if row["screen_position"] is not None else 0,
            row["name"].casefold(),
            row["card_id"],
        )
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
                if row["card_kind"] == "character"
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
    all_data_tables = list(
        group.data_tables.prefetch_related(
            "columns",
            "rows__cells",
        )
    )
    data_tables = [
        data_table
        for data_table in all_data_tables
        if data_table.is_visible
    ]
    hidden_data_tables = [
        data_table
        for data_table in all_data_tables
        if not data_table.is_visible
    ]
    for data_table in data_tables:
        data_table.render_columns = list(data_table.columns.all())
        data_table.render_rows = list(data_table.rows.all())
        data_table.render_card_width = max(
            320,
            (len(data_table.render_columns) * 140) + 20,
        )
        data_table.render_editor_width = data_table.render_card_width * 2
        occupied_coordinates = set()
        for data_row in data_table.render_rows:
            cells_by_column = {
                cell.column_id: cell
                for cell in data_row.cells.all()
            }
            data_row.render_cells = [
                cells_by_column.get(column.id)
                for column in data_table.render_columns
            ]
        for row_index, data_row in enumerate(data_table.render_rows):
            data_row.render_display_cells = []
            for column_index, cell in enumerate(data_row.render_cells):
                if cell is None:
                    continue
                cell.render_row_index = row_index
                cell.render_column_index = column_index
                cell.render_is_covered = (
                    row_index,
                    column_index,
                ) in occupied_coordinates
                if cell.render_is_covered:
                    continue
                row_span = min(
                    max(1, int(cell.row_span or 1)),
                    len(data_table.render_rows) - row_index,
                )
                column_span = min(
                    max(1, int(cell.column_span or 1)),
                    len(data_table.render_columns) - column_index,
                )
                while any(
                    (covered_row, covered_column) in occupied_coordinates
                    for covered_row in range(row_index, row_index + row_span)
                    for covered_column in range(column_index, column_index + column_span)
                ):
                    if column_span > 1:
                        column_span -= 1
                    elif row_span > 1:
                        row_span -= 1
                    else:
                        break
                cell.render_row_span = row_span
                cell.render_column_span = column_span
                data_row.render_display_cells.append(cell)
                occupied_coordinates.update(
                    (covered_row, covered_column)
                    for covered_row in range(row_index, row_index + row_span)
                    for covered_column in range(column_index, column_index + column_span)
                )
    try:
        editing_table_id = int(request.GET.get("edit_table") or 0)
    except (TypeError, ValueError):
        editing_table_id = 0
    character_creature_options = (
        CharacterCreature.objects.filter(
            owner_id__in=[membership.character_id for membership in memberships],
            active=True,
        )
        .exclude(
            Q(creature__slug="system-leere-tierform")
            & Q(source_selection_completed=False)
        )
        .select_related(
            "owner",
            "creature",
            "quality",
            "source_binding",
        )
        .order_by(
            "owner__name",
            "name_override",
            "creature__name",
            "id",
        )
    )
    return render(
        request,
        "charsheet/game_master_screen.html",
        {
            "group": group,
            "roster": roster,
            "character_count": len(memberships),
            "creature_count": len(creature_cards),
            "creature_options": (
                Creature.objects.exclude(slug="system-leere-tierform")
                .select_related("quality")
                .order_by("name")
            ),
            "character_creature_options": character_creature_options,
            "has_collapsed_roster": any(row["screen_is_collapsed"] for row in roster),
            "data_tables": data_tables,
            "hidden_data_tables": hidden_data_tables,
            "hidden_screen_item_count": (
                len(hidden_data_tables)
                + (0 if group.screen_note_is_visible else 1)
            ),
            "editing_table_id": editing_table_id,
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
@require_POST
@_group_action
def add_group_creature(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        creature_reference = str(request.POST.get("creature_ref", "")).strip()
        character_creature = None
        if creature_reference.startswith("character:"):
            try:
                character_creature_id = int(
                    creature_reference.partition(":")[2]
                )
            except (TypeError, ValueError) as exc:
                raise GroupError(
                    "creature_required",
                    "Bitte eine Kreatur auswählen.",
                ) from exc
            character_creature = get_object_or_404(
                CharacterCreature.objects.select_related("creature"),
                pk=character_creature_id,
                active=True,
                owner__game_group_memberships__group=group,
                owner__game_group_memberships__status=GameGroupMembership.Status.ACTIVE,
                owner__is_archived=False,
            )
            if (
                character_creature.creature.slug == "system-leere-tierform"
                and not character_creature.source_selection_completed
            ):
                raise GroupError(
                    "creature_required",
                    "Unvollständige Tierformen können nicht hinzugefügt werden.",
                )
            creature = character_creature.creature
        else:
            raw_creature_id = (
                creature_reference.partition(":")[2]
                if creature_reference.startswith("base:")
                else request.POST.get("creature_id", "")
            )
            try:
                creature_id = int(raw_creature_id)
            except (TypeError, ValueError) as exc:
                raise GroupError(
                    "creature_required",
                    "Bitte eine Kreatur auswählen.",
                ) from exc
            creature = get_object_or_404(
                Creature.objects.exclude(slug="system-leere-tierform"),
                pk=creature_id,
            )
        membership_position = (
            GameGroupMembership.objects.filter(
                group=group,
                status=GameGroupMembership.Status.ACTIVE,
                character__is_archived=False,
            ).aggregate(value=Max("screen_position"))["value"]
        )
        creature_position = group.screen_creatures.aggregate(
            value=Max("screen_position")
        )["value"]
        last_position = max(
            value
            for value in (membership_position, creature_position, -1)
            if value is not None
        )
        creature_kp = CreatureEngine(
            character_creature or creature
        ).kp()
        GameGroupCreature.objects.create(
            group=group,
            creature=creature,
            character_creature=character_creature,
            screen_position=last_position + 1,
            current_kp=(
                max(0, int(creature_kp))
                if creature_kp is not None
                else None
            ),
        )

    return redirect(
        f"{reverse('game_master_screen', args=[group.id])}#sl-charaktere"
    )


@login_required
@require_POST
@_group_action
def delete_group_creature(request, group_id: int, creature_card_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        creature_card = get_object_or_404(
            GameGroupCreature.objects.select_for_update(),
            pk=creature_card_id,
            group=group,
        )
        creature_card.delete()

    return redirect(
        f"{reverse('game_master_screen', args=[group.id])}#sl-charaktere"
    )


@login_required
@require_POST
@_group_action
def adjust_group_creature_damage(request, group_id: int, creature_card_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        creature_card = get_object_or_404(
            GameGroupCreature.objects.select_for_update(of=("self",)).select_related(
                "creature",
                "character_creature",
                "character_creature__creature",
            ),
            pk=creature_card_id,
            group=group,
        )
        action = request.POST.get("action")
        damage_type = request.POST.get("damage_type")
        try:
            amount = max(1, int(request.POST.get("amount", "1")))
        except (TypeError, ValueError):
            amount = 1
        wound_rows = CreatureEngine(
            creature_card.character_creature or creature_card.creature
        ).wound_rows()
        max_lp = int(wound_rows[-1]["threshold"]) if wound_rows else 0
        if damage_type in {"B", "T"} and action in {"damage", "heal"}:
            creature_card.adjust_damage(
                damage_type=damage_type,
                action=action,
                amount=amount,
                stun_max=max_lp,
            )
            creature_card.save(
                update_fields=[
                    "current_stun_damage",
                    "current_lethal_damage",
                ]
            )

    return redirect(
        f"{reverse('game_master_screen', args=[group.id])}#sl-charaktere"
    )


@login_required
@require_POST
@_group_action
def adjust_group_creature_kp(request, group_id: int, creature_card_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        creature_card = get_object_or_404(
            GameGroupCreature.objects.select_for_update(of=("self",)).select_related(
                "creature",
                "character_creature",
                "character_creature__creature",
            ),
            pk=creature_card_id,
            group=group,
        )
        maximum = CreatureEngine(
            creature_card.character_creature or creature_card.creature
        ).kp()
        if maximum is not None:
            try:
                amount = max(1, int(request.POST.get("amount", "1")))
            except (TypeError, ValueError):
                amount = 1
            creature_card.adjust_kp(
                action=str(request.POST.get("action") or ""),
                amount=amount,
                maximum=max(0, int(maximum)),
            )
            creature_card.save(update_fields=["current_kp"])

    return redirect(
        f"{reverse('game_master_screen', args=[group.id])}#sl-charaktere"
    )


@login_required
@require_POST
def reorder_group_memberships(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        try:
            require_game_master(request.user, group, write=True)
        except GroupError as exc:
            return JsonResponse(
                {"ok": False, "error": exc.message},
                status=exc.status,
            )
        memberships = list(
            GameGroupMembership.objects.select_for_update()
            .filter(
                group=group,
                status=GameGroupMembership.Status.ACTIVE,
                character__is_archived=False,
            )
            .order_by(
                F("screen_position").asc(nulls_last=True),
                "character__name",
                "id",
            )
        )
        creature_cards = list(
            GameGroupCreature.objects.select_for_update()
            .filter(group=group)
            .order_by(
                F("screen_position").asc(nulls_last=True),
                "creature__name",
                "id",
            )
        )
        ordered_tokens = request.POST.getlist("ordered_ids")
        if (
            not creature_cards
            and ordered_tokens
            and all(str(token).isdigit() for token in ordered_tokens)
        ):
            ordered_tokens = [
                f"character:{token}"
                for token in ordered_tokens
            ]

        membership_by_token = {
            f"character:{membership.id}": membership
            for membership in memberships
        }
        creature_by_token = {
            f"creature:{creature_card.id}": creature_card
            for creature_card in creature_cards
        }
        expected_tokens = set(membership_by_token) | set(creature_by_token)
        if (
            len(ordered_tokens) != len(expected_tokens)
            or len(ordered_tokens) != len(set(ordered_tokens))
            or set(ordered_tokens) != expected_tokens
        ):
            return JsonResponse(
                {"ok": False, "error": "Die Kartenreihenfolge ist unvollständig."},
                status=400,
            )

        for position, token in enumerate(ordered_tokens):
            if token in membership_by_token:
                membership_by_token[token].screen_position = position
            else:
                creature_by_token[token].screen_position = position
        GameGroupMembership.objects.bulk_update(
            memberships,
            ["screen_position"],
        )
        GameGroupCreature.objects.bulk_update(
            creature_cards,
            ["screen_position"],
        )

    return JsonResponse({"ok": True})


@login_required
@require_POST
def set_group_membership_screen_state(
    request,
    group_id: int,
    membership_id: int,
):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        try:
            require_game_master(request.user, group, write=True)
        except GroupError as exc:
            return JsonResponse(
                {"ok": False, "error": exc.message},
                status=exc.status,
            )
        membership = get_object_or_404(
            GameGroupMembership.objects.select_for_update(),
            pk=membership_id,
            group=group,
            status=GameGroupMembership.Status.ACTIVE,
            character__is_archived=False,
        )
        membership.screen_is_collapsed = (
            request.POST.get("is_collapsed", "").lower()
            in {"1", "true", "yes", "on"}
        )
        membership.save(update_fields=["screen_is_collapsed"])

    return JsonResponse(
        {
            "ok": True,
            "membership_id": membership.id,
            "is_collapsed": membership.screen_is_collapsed,
        }
    )


@login_required
@require_POST
def set_group_creature_screen_state(
    request,
    group_id: int,
    creature_card_id: int,
):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        try:
            require_game_master(request.user, group, write=True)
        except GroupError as exc:
            return JsonResponse(
                {"ok": False, "error": exc.message},
                status=exc.status,
            )
        creature_card = get_object_or_404(
            GameGroupCreature.objects.select_for_update(),
            pk=creature_card_id,
            group=group,
        )
        creature_card.screen_is_collapsed = (
            request.POST.get("is_collapsed", "").lower()
            in {"1", "true", "yes", "on"}
        )
        creature_card.save(update_fields=["screen_is_collapsed"])

    return JsonResponse(
        {
            "ok": True,
            "card_id": f"creature:{creature_card.id}",
            "is_collapsed": creature_card.screen_is_collapsed,
        }
    )


@login_required
@require_POST
def set_group_inventory_screen_state(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        try:
            require_game_master(request.user, group, write=True)
        except GroupError as exc:
            return JsonResponse(
                {"ok": False, "error": exc.message},
                status=exc.status,
            )
        group.screen_inventory_is_collapsed = (
            request.POST.get("is_collapsed", "").lower()
            in {"1", "true", "yes", "on"}
        )
        group.save(update_fields=["screen_inventory_is_collapsed"])

    return JsonResponse(
        {
            "ok": True,
            "is_collapsed": group.screen_inventory_is_collapsed,
        }
    )


class _GroupNoteHTMLSanitizer(HTMLParser):
    allowed_tags = {
        "b",
        "blockquote",
        "br",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "i",
        "li",
        "ol",
        "p",
        "strong",
        "u",
        "ul",
    }
    void_tags = {"br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        normalized_tag = str(tag or "").lower()
        if normalized_tag in self.allowed_tags:
            self.parts.append(f"<{normalized_tag}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        normalized_tag = str(tag or "").lower()
        if (
            normalized_tag in self.allowed_tags
            and normalized_tag not in self.void_tags
        ):
            self.parts.append(f"</{normalized_tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data, quote=False))


def _sanitize_group_note_html(raw_html: str) -> str:
    sanitizer = _GroupNoteHTMLSanitizer()
    sanitizer.feed(str(raw_html or "")[:50000])
    sanitizer.close()
    return "".join(sanitizer.parts)[:50000]


def _table_screen_redirect(group_id: int, *, edit_table_id: int | None = None):
    url = reverse("game_master_screen", args=[group_id])
    if edit_table_id:
        url = f"{url}?edit_table={edit_table_id}"
    return redirect(f"{url}#sl-tabellen")


def _normalized_table_title(raw_title: str) -> str:
    title = " ".join(str(raw_title or "").split())[:150]
    if not title:
        raise GroupError("table_title_required", "Bitte eine Tabellenüberschrift angeben.")
    return title


def _bounded_table_size(raw_value, *, default: int) -> int:
    try:
        value = int(raw_value or default)
    except (TypeError, ValueError) as exc:
        raise GroupError("invalid_table_size", "Zeilen und Spalten müssen als Zahl angegeben werden.") from exc
    return max(1, min(value, 20))


def _bounded_cell_span(raw_value) -> int:
    try:
        value = int(raw_value or 1)
    except (TypeError, ValueError) as exc:
        raise GroupError("invalid_cell_span", "Rowspan und Colspan müssen Zahlen sein.") from exc
    return max(1, min(value, 20))


@login_required
@require_POST
@_group_action
def create_group_table(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        title = _normalized_table_title(request.POST.get("title", ""))
        column_count = _bounded_table_size(request.POST.get("column_count"), default=3)
        row_count = _bounded_table_size(request.POST.get("row_count"), default=3)
        max_position = group.data_tables.aggregate(value=Max("position"))["value"]
        data_table = GameGroupTable.objects.create(
            group=group,
            title=title,
            position=(max_position + 1) if max_position is not None else 0,
        )
        columns = GameGroupTableColumn.objects.bulk_create(
            [
                GameGroupTableColumn(
                    table=data_table,
                    heading=f"Spalte {position + 1}",
                    position=position,
                )
                for position in range(column_count)
            ]
        )
        rows = GameGroupTableRow.objects.bulk_create(
            [
                GameGroupTableRow(table=data_table, position=position)
                for position in range(row_count)
            ]
        )
        GameGroupTableCell.objects.bulk_create(
            [
                GameGroupTableCell(row=row, column=column)
                for row in rows
                for column in columns
            ]
        )
    messages.success(request, "Tabelle angelegt.")
    return _table_screen_redirect(group_id)


@login_required
@require_POST
def update_group_note(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        try:
            require_game_master(request.user, group, write=True)
        except GroupError as exc:
            return JsonResponse(
                {"ok": False, "error": exc.message},
                status=exc.status,
            )
        update_fields = []
        if "note_html" in request.POST:
            group.screen_note_html = _sanitize_group_note_html(
                request.POST.get("note_html", "")
            )
            update_fields.append("screen_note_html")

        boolean_layout_fields = {
            "note_is_wide": "screen_note_is_wide",
            "note_is_detached": "screen_note_is_detached",
        }
        for request_name, field_name in boolean_layout_fields.items():
            if request_name not in request.POST:
                continue
            setattr(
                group,
                field_name,
                request.POST.get(request_name, "").lower()
                in {"1", "true", "yes", "on"},
            )
            update_fields.append(field_name)

        coordinate_fields = {
            "note_x": "screen_note_x",
            "note_y": "screen_note_y",
        }
        for request_name, field_name in coordinate_fields.items():
            if request_name not in request.POST:
                continue
            try:
                coordinate = int(request.POST.get(request_name, "24"))
            except (TypeError, ValueError):
                coordinate = 24
            setattr(group, field_name, max(0, min(coordinate, 10000)))
            update_fields.append(field_name)

        if update_fields:
            group.save(update_fields=update_fields)

    return JsonResponse(
        {
            "ok": True,
            "html": group.screen_note_html,
            "is_wide": group.screen_note_is_wide,
            "is_detached": group.screen_note_is_detached,
            "x": group.screen_note_x,
            "y": group.screen_note_y,
        }
    )


@login_required
@require_POST
def reorder_group_tables(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        try:
            require_game_master(request.user, group, write=True)
        except GroupError as exc:
            return JsonResponse(
                {"ok": False, "error": exc.message},
                status=exc.status,
            )
        tables = list(
            GameGroupTable.objects.select_for_update()
            .filter(group=group)
            .order_by("position", "id")
        )
        note_position = (
            group.screen_note_position
            if group.screen_note_position is not None
            else max([table.position for table in tables], default=-1) + 1
        )
        screen_items = [
            ("table", table)
            for table in tables
        ] + [("note", group)]
        screen_items.sort(
            key=lambda item: (
                item[1].position if item[0] == "table" else note_position,
                0 if item[0] == "table" else 1,
                item[1].id,
            )
        )

        visible_items = [
            item
            for item in screen_items
            if (
                group.screen_note_is_visible
                if item[0] == "note"
                else item[1].is_visible
            )
        ]
        item_tokens = {
            (
                f"table:{item[1].id}"
                if item[0] == "table"
                else "note"
            ): item
            for item in visible_items
        }
        ordered_tokens = request.POST.getlist("ordered_ids")
        if (
            len(ordered_tokens) != len(visible_items)
            or len(ordered_tokens) != len(set(ordered_tokens))
            or set(ordered_tokens) != set(item_tokens)
        ):
            return JsonResponse(
                {"ok": False, "error": "Die Kartenreihenfolge ist unvollständig."},
                status=400,
            )

        ordered_visible = iter(item_tokens[token] for token in ordered_tokens)
        normalized_items = [
            next(ordered_visible)
            if (
                group.screen_note_is_visible
                if item[0] == "note"
                else item[1].is_visible
            )
            else item
            for item in screen_items
        ]
        for position, item in enumerate(normalized_items):
            if item[0] == "table":
                item[1].position = position
            else:
                group.screen_note_position = position
        GameGroupTable.objects.bulk_update(tables, ["position"])
        group.save(update_fields=["screen_note_position"])

    return JsonResponse({"ok": True})


@login_required
@require_POST
@_group_action
def update_group_table(request, group_id: int, table_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(
            GameGroupTable.objects.select_for_update(),
            pk=table_id,
            group=group,
        )
        data_table.title = _normalized_table_title(request.POST.get("title", ""))
        data_table.full_clean()
        data_table.save(update_fields=["title", "updated_at"])

        columns = list(data_table.columns.all())
        rows = list(data_table.rows.all())
        for column in columns:
            heading = " ".join(
                str(request.POST.get(f"column_{column.id}_heading", "")).split()
            )[:100]
            column.heading = heading or f"Spalte {column.position + 1}"
            column.full_clean()
            column.save(update_fields=["heading"])

        existing_cells = {
            (cell.row_id, cell.column_id): cell
            for cell in GameGroupTableCell.objects.filter(
                row__table=data_table,
                column__table=data_table,
            )
        }
        for row in rows:
            for column in columns:
                cell = existing_cells.get((row.id, column.id))
                if cell is None:
                    cell = GameGroupTableCell(row=row, column=column)
                field_prefix = f"cell_{row.id}_{column.id}"
                if (
                    f"{field_prefix}_alignment" not in request.POST
                    and f"{field_prefix}_type" not in request.POST
                    and f"{field_prefix}_value" not in request.POST
                ):
                    continue
                alignment = request.POST.get(
                    f"{field_prefix}_alignment",
                    cell.alignment or GameGroupTableCell.Alignment.LEFT,
                )
                valid_alignments = {
                    choice
                    for choice, _label in GameGroupTableCell.Alignment.choices
                }
                cell.alignment = (
                    alignment
                    if alignment in valid_alignments
                    else GameGroupTableCell.Alignment.LEFT
                )
                raw_value = str(request.POST.get(f"{field_prefix}_value", "")).strip()
                cell.row_span = _bounded_cell_span(
                    request.POST.get(f"{field_prefix}_rowspan")
                )
                cell.column_span = _bounded_cell_span(
                    request.POST.get(f"{field_prefix}_colspan")
                )
                number_match = (
                    re.fullmatch(
                        r"([+-]?)(\d+(?:[.,]\d+)?)\s*(.*)",
                        raw_value,
                    )
                    if raw_value
                    else None
                )
                if number_match:
                    try:
                        cell.number_value = Decimal(
                            f"{number_match.group(1)}{number_match.group(2)}".replace(
                                ",",
                                ".",
                            )
                        )
                    except InvalidOperation as exc:
                        raise GroupError(
                            "invalid_table_number",
                            f"„{raw_value}“ ist keine gültige Zahl.",
                        ) from exc
                    cell.value_type = GameGroupTableCell.ValueType.NUMBER
                    cell.text_value = ""
                    cell.number_show_plus = number_match.group(1) == "+"
                    cell.number_suffix = number_match.group(3).strip()[:100]
                else:
                    cell.value_type = GameGroupTableCell.ValueType.TEXT
                    cell.text_value = raw_value
                    cell.number_value = None
                    cell.number_show_plus = False
                    cell.number_suffix = ""
                try:
                    cell.full_clean()
                except ValidationError as exc:
                    raise GroupError("invalid_table_cell", "Ein Tabellenwert ist ungültig.") from exc
                cell.save()
        table_action = request.POST.get("_table_action", "")
        if table_action == "add_row":
            if data_table.rows.count() >= 20:
                raise GroupError("table_row_limit", "Eine Tabelle kann höchstens 20 Zeilen enthalten.")
            max_position = data_table.rows.aggregate(value=Max("position"))["value"]
            new_row = GameGroupTableRow.objects.create(
                table=data_table,
                position=(max_position + 1) if max_position is not None else 0,
            )
            GameGroupTableCell.objects.bulk_create(
                [
                    GameGroupTableCell(row=new_row, column=column)
                    for column in data_table.columns.all()
                ]
            )
        elif table_action == "add_column":
            if data_table.columns.count() >= 20:
                raise GroupError("table_column_limit", "Eine Tabelle kann höchstens 20 Spalten enthalten.")
            max_position = data_table.columns.aggregate(value=Max("position"))["value"]
            position = (max_position + 1) if max_position is not None else 0
            new_column = GameGroupTableColumn.objects.create(
                table=data_table,
                heading=f"Spalte {position + 1}",
                position=position,
            )
            GameGroupTableCell.objects.bulk_create(
                [
                    GameGroupTableCell(row=row, column=new_column)
                    for row in data_table.rows.all()
                ]
            )
        elif table_action.startswith("delete_row:"):
            if data_table.rows.count() <= 1:
                raise GroupError("last_table_row", "Eine Tabelle benötigt mindestens eine Zeile.")
            try:
                row_id = int(table_action.partition(":")[2])
            except (TypeError, ValueError) as exc:
                raise GroupError("invalid_table_row", "Die Tabellenzeile ist ungültig.") from exc
            get_object_or_404(GameGroupTableRow, pk=row_id, table=data_table).delete()
        elif table_action.startswith("delete_column:"):
            if data_table.columns.count() <= 1:
                raise GroupError("last_table_column", "Eine Tabelle benötigt mindestens eine Spalte.")
            try:
                column_id = int(table_action.partition(":")[2])
            except (TypeError, ValueError) as exc:
                raise GroupError("invalid_table_column", "Die Tabellenspalte ist ungültig.") from exc
            get_object_or_404(GameGroupTableColumn, pk=column_id, table=data_table).delete()
        elif table_action.startswith(("move_row_up:", "move_row_down:")):
            direction, _, raw_row_id = table_action.partition(":")
            try:
                row_id = int(raw_row_id)
            except (TypeError, ValueError) as exc:
                raise GroupError("invalid_table_row", "Die Tabellenzeile ist ungültig.") from exc
            ordered_rows = list(data_table.rows.select_for_update().order_by("position", "id"))
            row_index = next(
                (index for index, candidate in enumerate(ordered_rows) if candidate.id == row_id),
                None,
            )
            if row_index is None:
                raise GroupError("invalid_table_row", "Die Tabellenzeile wurde nicht gefunden.")
            target_index = row_index - 1 if direction == "move_row_up" else row_index + 1
            if 0 <= target_index < len(ordered_rows):
                moving_row = ordered_rows[row_index]
                target_row = ordered_rows[target_index]
                moving_position = moving_row.position
                target_position = target_row.position
                temporary_position = (
                    data_table.rows.aggregate(value=Max("position"))["value"] or 0
                ) + 1
                moving_row.position = temporary_position
                moving_row.save(update_fields=["position"])
                target_row.position = moving_position
                target_row.save(update_fields=["position"])
                moving_row.position = target_position
                moving_row.save(update_fields=["position"])
    messages.success(request, "Tabelle gespeichert.")
    return _table_screen_redirect(
        group_id,
        edit_table_id=data_table.id if table_action else None,
    )


@login_required
@require_POST
@_group_action
def add_group_table_row(request, group_id: int, table_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        if data_table.rows.count() >= 20:
            raise GroupError("table_row_limit", "Eine Tabelle kann höchstens 20 Zeilen enthalten.")
        max_position = data_table.rows.aggregate(value=Max("position"))["value"]
        row = GameGroupTableRow.objects.create(
            table=data_table,
            position=(max_position + 1) if max_position is not None else 0,
        )
        GameGroupTableCell.objects.bulk_create(
            [
                GameGroupTableCell(row=row, column=column)
                for column in data_table.columns.all()
            ]
        )
    return _table_screen_redirect(group_id, edit_table_id=data_table.id)


@login_required
@require_POST
@_group_action
def add_group_table_column(request, group_id: int, table_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        if data_table.columns.count() >= 20:
            raise GroupError("table_column_limit", "Eine Tabelle kann höchstens 20 Spalten enthalten.")
        max_position = data_table.columns.aggregate(value=Max("position"))["value"]
        position = (max_position + 1) if max_position is not None else 0
        column = GameGroupTableColumn.objects.create(
            table=data_table,
            heading=f"Spalte {position + 1}",
            position=position,
        )
        GameGroupTableCell.objects.bulk_create(
            [
                GameGroupTableCell(row=row, column=column)
                for row in data_table.rows.all()
            ]
        )
    return _table_screen_redirect(group_id, edit_table_id=data_table.id)


@login_required
@require_POST
@_group_action
def delete_group_table_row(request, group_id: int, table_id: int, row_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        if data_table.rows.count() <= 1:
            raise GroupError("last_table_row", "Eine Tabelle benötigt mindestens eine Zeile.")
        row = get_object_or_404(GameGroupTableRow, pk=row_id, table=data_table)
        row.delete()
    return _table_screen_redirect(group_id, edit_table_id=data_table.id)


@login_required
@require_POST
@_group_action
def delete_group_table_column(request, group_id: int, table_id: int, column_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        if data_table.columns.count() <= 1:
            raise GroupError("last_table_column", "Eine Tabelle benötigt mindestens eine Spalte.")
        column = get_object_or_404(GameGroupTableColumn, pk=column_id, table=data_table)
        column.delete()
    return _table_screen_redirect(group_id, edit_table_id=data_table.id)


@login_required
@require_POST
@_group_action
def delete_group_table(request, group_id: int, table_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        data_table.delete()
    messages.success(request, "Tabelle gelöscht.")
    return _table_screen_redirect(group_id)


@login_required
@require_POST
@_group_action
def show_group_table(request, group_id: int, table_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        data_table.is_visible = True
        data_table.save(update_fields=["is_visible", "updated_at"])
    return _table_screen_redirect(group_id)


@login_required
@require_POST
@_group_action
def hide_group_table(request, group_id: int, table_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        data_table = get_object_or_404(GameGroupTable, pk=table_id, group=group)
        data_table.is_visible = False
        data_table.save(update_fields=["is_visible", "updated_at"])
    return _table_screen_redirect(group_id)


@login_required
@require_POST
@_group_action
def show_group_note(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        group.screen_note_is_visible = True
        group.save(update_fields=["screen_note_is_visible"])
    return _table_screen_redirect(group_id)


@login_required
@require_POST
@_group_action
def hide_group_note(request, group_id: int):
    with transaction.atomic():
        group = GameGroup.objects.select_for_update().get(pk=group_id)
        require_game_master(request.user, group, write=True)
        group.screen_note_is_visible = False
        group.save(update_fields=["screen_note_is_visible"])
    return _table_screen_redirect(group_id)


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
    ).select_related("character").order_by(
        F("screen_position").asc(nulls_last=True),
        "character__name",
        "id",
    )
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
