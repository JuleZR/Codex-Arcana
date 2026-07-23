"""Transactional game-group workflows and centralized authorization."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from charsheet.models import (
    Character,
    CharacterItem,
    GameGroup,
    GameGroupInvitation,
    GameGroupMembership,
    GameGroupRole,
    ItemTransfer,
    ItemTransferNotification,
    ItemOwnershipEvent,
)


class GroupError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def active_role_for(user, group: GameGroup) -> GameGroupRole | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return GameGroupRole.objects.filter(
        group=group,
        user=user,
        is_active=True,
        role__in=[GameGroupRole.Role.LEADER, GameGroupRole.Role.GM],
    ).first()


def require_game_master(user, group: GameGroup, *, write: bool = False) -> GameGroupRole:
    role = active_role_for(user, group)
    if role is None:
        raise PermissionDenied
    if write and group.is_archived:
        raise GroupError("group_archived", "Archivierte Gruppen können nicht verändert werden.", status=409)
    return role


def require_leader(user, group: GameGroup, *, write: bool = False) -> GameGroupRole:
    role = require_game_master(user, group, write=write)
    if role.role != GameGroupRole.Role.LEADER:
        raise PermissionDenied
    return role


def user_can_view_group(user, group: GameGroup) -> bool:
    if active_role_for(user, group):
        return True
    return GameGroupMembership.objects.filter(
        group=group,
        status=GameGroupMembership.Status.ACTIVE,
        character__owner=user,
    ).exists()


def require_sl_character_access(user, group: GameGroup, character: Character) -> GameGroupRole:
    """Authorize the dedicated SL read route without consulting Character.owner."""
    role = require_game_master(user, group, write=False)
    if not GameGroupMembership.objects.filter(
        group=group,
        character=character,
        status=GameGroupMembership.Status.ACTIVE,
    ).exists():
        raise PermissionDenied
    if character.is_archived:
        raise PermissionDenied
    return role


@transaction.atomic
def create_group(*, creator, name: str) -> GameGroup:
    normalized = " ".join(str(name or "").split())
    if not normalized:
        base_name = "Neue Spielgruppe"
        normalized = base_name
        suffix = 2
        while GameGroup.objects.filter(name__iexact=normalized).exists():
            normalized = f"{base_name} {suffix}"
            suffix += 1
    normalized = normalized[:150]
    if GameGroup.objects.filter(name__iexact=normalized).exists():
        raise GroupError("duplicate_name", "Dieser Gruppenname wird bereits verwendet.", status=409)
    try:
        return GameGroup.objects.create(name=normalized, creator=creator)
    except IntegrityError as exc:
        raise GroupError("duplicate_name", "Dieser Gruppenname wird bereits verwendet.", status=409) from exc


@transaction.atomic
def rename_group(*, group_id: int, actor, name: str) -> GameGroup:
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_leader(actor, group, write=True)
    normalized = " ".join(str(name or "").split())[:150]
    if not normalized:
        raise GroupError("name_required", "Bitte einen Gruppennamen angeben.")
    if GameGroup.objects.filter(name__iexact=normalized).exclude(pk=group.pk).exists():
        raise GroupError("duplicate_name", "Dieser Gruppenname wird bereits verwendet.", status=409)
    group.name = normalized
    try:
        group.full_clean()
        group.save(update_fields=["name"])
    except (IntegrityError, ValidationError) as exc:
        raise GroupError("duplicate_name", "Dieser Gruppenname wird bereits verwendet.", status=409) from exc
    return group


@transaction.atomic
def delete_group(*, group_id: int, actor) -> str:
    """Physically delete a group while protecting items already owned by characters."""
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_leader(actor, group, write=False)
    if CharacterItem.objects.filter(
        item__catalog_group=group,
        owner__isnull=False,
    ).exists():
        raise GroupError(
            "group_catalog_item_in_character_inventory",
            "Mindestens ein gruppeneigenes Basisitem befindet sich in einem Charakterinventar. Diese Gegenstände müssen zuerst geklärt werden.",
            status=409,
        )
    name = group.name
    transfer_ids = ItemTransfer.objects.filter(
        Q(sender_group=group) | Q(recipient_group=group)
    ).values("id")
    ItemTransferNotification.objects.filter(transfer_id__in=transfer_ids).delete()
    ItemOwnershipEvent.objects.filter(
        Q(transfer_id__in=transfer_ids)
        | Q(original_owner_group=group)
        | Q(from_group=group)
        | Q(to_group=group)
    ).delete()
    ItemTransfer.objects.filter(
        Q(sender_group=group) | Q(recipient_group=group)
    ).delete()
    CharacterItem.objects.filter(
        Q(group_owner=group) | Q(original_owner_group=group)
    ).delete()
    try:
        group.catalog_items.all().delete()
    except ProtectedError as exc:
        raise GroupError(
            "group_catalog_item_protected",
            "Mindestens ein gruppeneigenes Basisitem wird noch außerhalb der Gruppe verwendet.",
            status=409,
        ) from exc
    GameGroupMembership.objects.filter(group=group).delete()
    GameGroupInvitation.objects.filter(group=group).delete()
    GameGroupRole.objects.filter(group=group).delete()
    group.delete()
    return name


@transaction.atomic
def add_game_master(*, group_id: int, actor, user) -> GameGroupRole:
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_leader(actor, group, write=True)
    role, _created = GameGroupRole.objects.select_for_update().get_or_create(
        group=group,
        user=user,
        defaults={"role": GameGroupRole.Role.GM, "is_active": True},
    )
    if role.role == GameGroupRole.Role.LEADER and role.is_active:
        return role
    role.role = GameGroupRole.Role.GM
    role.is_active = True
    role.revoked_at = None
    role.full_clean()
    role.save(update_fields=["role", "is_active", "revoked_at"])
    return role


@transaction.atomic
def revoke_game_master(*, group_id: int, actor, user) -> GameGroupRole:
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_leader(actor, group, write=True)
    role = GameGroupRole.objects.select_for_update().get(group=group, user=user, is_active=True)
    if role.role == GameGroupRole.Role.LEADER:
        raise GroupError("leader_cannot_be_revoked", "Die Leitung muss zuerst übertragen werden.", status=409)
    role.is_active = False
    role.revoked_at = timezone.now()
    role.save(update_fields=["is_active", "revoked_at"])
    return role


@transaction.atomic
def transfer_leadership(*, group_id: int, actor, new_leader) -> GameGroup:
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    current = require_leader(actor, group, write=True)
    target = GameGroupRole.objects.select_for_update().filter(
        group=group,
        user=new_leader,
        is_active=True,
        role=GameGroupRole.Role.GM,
    ).first()
    if target is None:
        raise GroupError("target_not_gm", "Die neue Leitung muss bereits aktiver SL sein.", status=409)
    # Avoid the partial unique constraint while preserving one leader at transaction end.
    current._leadership_transfer = True
    current.role = GameGroupRole.Role.GM
    current.save(update_fields=["role"])
    target.role = GameGroupRole.Role.LEADER
    target.save(update_fields=["role"])
    return group


def _expire_invitation_locked(invitation: GameGroupInvitation) -> bool:
    if (
        invitation.status == GameGroupInvitation.Status.PENDING
        and invitation.expires_at is not None
        and invitation.expires_at <= timezone.now()
    ):
        invitation.status = GameGroupInvitation.Status.EXPIRED
        invitation.resolved_at = timezone.now()
        invitation.save(update_fields=["status", "resolved_at"])
        return True
    return False


@transaction.atomic
def create_invitation(
    *, group_id: int, actor, character: Character, message: str = "", expires_at=None
) -> GameGroupInvitation:
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_game_master(actor, group, write=True)
    if character.is_archived:
        raise GroupError("character_archived", "Archivierte Charaktere können nicht eingeladen werden.")
    if GameGroupMembership.objects.filter(
        group=group,
        character=character,
        status=GameGroupMembership.Status.ACTIVE,
    ).exists():
        raise GroupError("already_member", "Dieser Charakter gehört bereits zur Gruppe.", status=409)
    pending = GameGroupInvitation.objects.select_for_update().filter(
        group=group,
        character=character,
        status=GameGroupInvitation.Status.PENDING,
    ).first()
    if pending and not _expire_invitation_locked(pending):
        raise GroupError("invite_pending", "Für diesen Charakter besteht bereits eine Einladung.", status=409)
    return GameGroupInvitation.objects.create(
        group=group,
        character=character,
        invited_by=actor,
        message=str(message or "").strip()[:1000],
        expires_at=expires_at,
    )


def _recall_character_group_offers_locked(character: Character) -> None:
    from charsheet.item_transfers import recall_group_transfer_locked

    transfer_ids = list(
        ItemTransfer.objects.select_for_update()
        .filter(
            recipient=character,
            sender_group__isnull=False,
            status=ItemTransfer.Status.PENDING,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    for transfer_id in transfer_ids:
        recall_group_transfer_locked(transfer_id=transfer_id, reason="membership_changed")


@transaction.atomic
def recall_character_group_offers(*, character_id: int) -> Character:
    """Recall all pending group offers before an external character-state change."""
    character = Character.objects.select_for_update().get(pk=character_id)
    _recall_character_group_offers_locked(character)
    return character


@transaction.atomic
def accept_invitation(*, invitation_id: int, user) -> GameGroupMembership:
    invitation = (
        GameGroupInvitation.objects.select_for_update()
        .select_related("group", "character", "character__owner")
        .get(pk=invitation_id)
    )
    Character.objects.select_for_update().get(pk=invitation.character_id)
    group = GameGroup.objects.select_for_update().get(pk=invitation.group_id)
    if invitation.character.owner_id != user.pk:
        raise PermissionDenied
    if invitation.status != GameGroupInvitation.Status.PENDING:
        raise GroupError("invite_closed", "Diese Einladung ist nicht mehr offen.", status=409)
    if _expire_invitation_locked(invitation):
        raise GroupError("invite_expired", "Diese Einladung ist abgelaufen.", status=409)
    if group.is_archived:
        raise GroupError("group_archived", "Die Gruppe ist archiviert.", status=409)
    if invitation.character.is_archived:
        raise GroupError("character_archived", "Archivierte Charaktere können nicht beitreten.", status=409)
    _recall_character_group_offers_locked(invitation.character)
    if GameGroupMembership.objects.filter(
        group=group,
        character=invitation.character,
        status=GameGroupMembership.Status.ACTIVE,
    ).exists():
        raise GroupError("already_member", "Dieser Charakter gehört bereits zur Gruppe.", status=409)
    try:
        membership = GameGroupMembership.objects.create(
            group=group,
            character=invitation.character,
            invitation=invitation,
        )
    except IntegrityError as exc:
        raise GroupError("membership_conflict", "Die Mitgliedschaft wurde bereits geändert.", status=409) from exc
    invitation.status = GameGroupInvitation.Status.ACCEPTED
    invitation.resolved_at = timezone.now()
    invitation.save(update_fields=["status", "resolved_at"])
    return membership


@transaction.atomic
def decline_invitation(*, invitation_id: int, user) -> GameGroupInvitation:
    invitation = GameGroupInvitation.objects.select_for_update().select_related("character").get(pk=invitation_id)
    if invitation.character.owner_id != user.pk:
        raise PermissionDenied
    if invitation.status != GameGroupInvitation.Status.PENDING:
        raise GroupError("invite_closed", "Diese Einladung ist nicht mehr offen.", status=409)
    invitation.status = GameGroupInvitation.Status.DECLINED
    invitation.resolved_at = timezone.now()
    invitation.save(update_fields=["status", "resolved_at"])
    return invitation


@transaction.atomic
def withdraw_invitation(*, invitation_id: int, actor) -> GameGroupInvitation:
    invitation = GameGroupInvitation.objects.select_for_update().select_related("group").get(pk=invitation_id)
    require_game_master(actor, invitation.group, write=True)
    if invitation.status != GameGroupInvitation.Status.PENDING:
        raise GroupError("invite_closed", "Diese Einladung ist nicht mehr offen.", status=409)
    invitation.status = GameGroupInvitation.Status.WITHDRAWN
    invitation.resolved_at = timezone.now()
    invitation.save(update_fields=["status", "resolved_at"])
    return invitation


@transaction.atomic
def end_membership(*, membership_id: int, actor=None, owner=None) -> GameGroupMembership:
    membership = (
        GameGroupMembership.objects.select_for_update()
        .select_related("group", "character", "character__owner")
        .get(pk=membership_id)
    )
    Character.objects.select_for_update().get(pk=membership.character_id)
    if membership.status != GameGroupMembership.Status.ACTIVE:
        raise GroupError("membership_closed", "Diese Mitgliedschaft ist nicht mehr aktiv.", status=409)
    if owner is not None:
        if membership.character.owner_id != owner.pk:
            raise PermissionDenied
        next_status = GameGroupMembership.Status.LEFT
        if membership.group.is_archived:
            raise GroupError("group_archived", "Archivierte Gruppen können nicht verändert werden.", status=409)
    else:
        require_game_master(actor, membership.group, write=True)
        next_status = GameGroupMembership.Status.REMOVED
    _recall_character_group_offers_locked(membership.character)
    membership.status = next_status
    membership.ended_at = timezone.now()
    membership.save(update_fields=["status", "ended_at"])
    return membership


@transaction.atomic
def archive_group(*, group_id: int, actor) -> GameGroup:
    from charsheet.item_transfers import recall_group_transfer_locked

    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_leader(actor, group, write=True)
    now = timezone.now()
    GameGroupInvitation.objects.select_for_update().filter(
        group=group,
        status=GameGroupInvitation.Status.PENDING,
    ).update(status=GameGroupInvitation.Status.WITHDRAWN, resolved_at=now)
    transfer_ids = list(
        ItemTransfer.objects.select_for_update()
        .filter(sender_group=group, status=ItemTransfer.Status.PENDING)
        .order_by("id")
        .values_list("id", flat=True)
    )
    for transfer_id in transfer_ids:
        recall_group_transfer_locked(transfer_id=transfer_id, reason="group_archived")
    group.is_archived = True
    group.save(update_fields=["is_archived"])
    return group


@transaction.atomic
def reactivate_group(*, group_id: int, actor) -> GameGroup:
    group = GameGroup.objects.select_for_update().get(pk=group_id)
    require_leader(actor, group, write=False)
    group.is_archived = False
    group.save(update_fields=["is_archived"])
    return group
