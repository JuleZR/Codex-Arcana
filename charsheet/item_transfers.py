"""Transactional item-transfer and permanent original-owner rights."""

from __future__ import annotations

from datetime import timedelta
import json

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    Character,
    CharacterCreature,
    CharacterCreatureTrait,
    CharacterCreatureTraitChoice,
    CharacterItem,
    CharacterItemRuneSpec,
    ItemOwnershipEvent,
    ItemPermissionGrant,
    ItemRune,
    ItemTransfer,
    ItemTransferNotification,
    Modifier,
)


class TransferError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def pending_transfer_for_item(item: CharacterItem):
    prefetched = getattr(item, "_prefetched_objects_cache", {}).get("transfers")
    if prefetched is not None:
        return next((row for row in prefetched if row.status == ItemTransfer.Status.PENDING), None)
    return item.transfers.filter(status=ItemTransfer.Status.PENDING).select_related(
        "recipient", "recipient_group", "sender"
    ).first()


def item_is_pending(item: CharacterItem) -> bool:
    return pending_transfer_for_item(item) is not None


def _character_snapshot(character: Character) -> dict:
    return {
        "id": character.pk,
        "name": character.name,
        "race": character.race.name if character.race_id else "",
        "username": character.owner.get_username(),
    }


def _item_snapshot(item: CharacterItem) -> dict:
    return {
        "id": item.pk,
        "provenance_id": str(item.provenance_id),
        "name": item.effective_name,
        "base_name": item.item.name,
        "quantity": item.amount,
        "quality": item.quality_id,
        "item_type": item.item.item_type,
        "image": item.effective_image_url,
    }


def _creature_choice_snapshot(item: CharacterItem) -> list[dict]:
    """Capture concrete creature choices as a transfer integrity fallback."""
    snapshot = []
    choices = CharacterCreatureTraitChoice.objects.filter(
        character_creature_trait__creature__source_character_item=item
    )
    excluded = {"id", "character_creature_trait"}
    for choice in choices:
        values = {
            field.attname: getattr(choice, field.attname)
            for field in choice._meta.concrete_fields
            if field.name not in excluded
        }
        snapshot.append(
            {
                "id": choice.pk,
                "character_creature_trait_id": choice.character_creature_trait_id,
                "values": values,
            }
        )
    return snapshot


def _restore_creature_choices(item: CharacterItem, snapshot: list[dict]):
    """Restore choices lost by an unrelated concurrent/form synchronization path."""
    valid_trait_ids = set(
        CharacterCreatureTrait.objects.filter(
            creature__source_character_item=item
        ).values_list("pk", flat=True)
    )
    for entry in snapshot or []:
        trait_id = entry.get("character_creature_trait_id")
        choice_id = entry.get("id")
        if trait_id not in valid_trait_ids or not choice_id:
            continue
        if CharacterCreatureTraitChoice.objects.filter(pk=choice_id).exists():
            continue
        CharacterCreatureTraitChoice.objects.create(
            id=choice_id,
            character_creature_trait_id=trait_id,
            **entry.get("values", {}),
        )


def _notify(user, item, kind: str, message: str, transfer=None):
    return ItemTransferNotification.objects.create(
        user=user,
        transfer=transfer,
        item_provenance_id=item.provenance_id,
        kind=kind,
        message=message[:500],
    )


def _event(
    item,
    event_type: str,
    *,
    transfer=None,
    actor=None,
    actor_user=None,
    from_character=None,
    from_group=None,
    to_character=None,
    to_group=None,
    details=None,
):
    return ItemOwnershipEvent.objects.create(
        item=item,
        item_provenance_id=item.provenance_id,
        transfer=transfer,
        event_type=event_type,
        actor=actor,
        actor_user=actor_user,
        original_owner=item.original_owner_character,
        original_owner_group=item.original_owner_group,
        from_character=from_character,
        from_group=from_group,
        to_character=to_character,
        to_group=to_group,
        details=details or {},
    )


def _notify_group_game_masters(group, item, kind: str, message: str, transfer=None):
    from charsheet.models import GameGroupRole

    user_ids = (
        GameGroupRole.objects.filter(
            group=group,
            is_active=True,
            role__in=[GameGroupRole.Role.LEADER, GameGroupRole.Role.GM],
        )
        .values_list("user_id", flat=True)
        .distinct()
    )
    for user_id in user_ids:
        ItemTransferNotification.objects.create(
            user_id=user_id,
            transfer=transfer,
            item_provenance_id=item.provenance_id,
            kind=kind,
            message=message[:500],
        )


def _clone_related_rows(source: CharacterItem, target: CharacterItem):
    target.runes.set(source.runes.all())
    for row in source.item_runes.all():
        ItemRune.objects.create(
            item=target,
            rune=row.rune,
            crafter_level=row.crafter_level,
            allows_duplicate=row.allows_duplicate,
            is_active=row.is_active,
        )
    for row in source.rune_specs.all():
        CharacterItemRuneSpec.objects.create(
            character_item=target,
            rune=row.rune,
            specification=row.specification,
            slot=row.slot,
        )
    content_type = ContentType.objects.get_for_model(CharacterItem)
    for modifier in Modifier.objects.filter(source_content_type=content_type, source_object_id=source.pk):
        modifier.pk = None
        modifier.source_object_id = target.pk
        modifier.save()
    for grant in source.permission_grants.filter(
        permission=ItemPermissionGrant.Permission.CONSUME_FINAL,
        revoked_at__isnull=True,
        invalidated_at__isnull=True,
    ):
        ItemPermissionGrant.objects.create(
            item=target,
            permission=grant.permission,
            granted_by=grant.granted_by,
            irrevocable=grant.irrevocable,
        )


def _split_item(source: CharacterItem, quantity: int) -> CharacterItem:
    values = {}
    excluded = {
        "id",
        "owner",
        "group_owner",
        "amount",
        "provenance_id",
        "ownership_version",
        "original_owner_character",
        "original_owner_group",
    }
    for field in source._meta.concrete_fields:
        if field.name in excluded:
            continue
        values[field.attname] = getattr(source, field.attname)
    target = CharacterItem.objects.create(
        owner=source.owner,
        group_owner=source.group_owner,
        original_owner_character=source.original_owner_character,
        original_owner_group=source.original_owner_group,
        ownership_version=source.ownership_version,
        amount=quantity,
        **values,
    )
    _clone_related_rows(source, target)
    # A concrete creature is individualized state belonging to the transferred
    # item instance.  Keep that exact instance (and therefore its traits,
    # choices, notes, damage, etc.) with the split-off item instead of letting
    # the recipient sync create a fresh, unconfigured creature.
    CharacterCreature.objects.select_for_update().filter(
        source_character_item=source
    ).update(source_character_item=target)
    source.amount -= quantity
    source.save(update_fields=["amount"])
    return target


def _invalidate_holder_permissions(item: CharacterItem, *, now=None):
    now = now or timezone.now()
    grants = ItemPermissionGrant.objects.filter(
        item=item,
        permission__in=[ItemPermissionGrant.Permission.SELL, ItemPermissionGrant.Permission.DESTROY],
        revoked_at__isnull=True,
        invalidated_at__isnull=True,
    )
    for grant in grants.select_related("grantee"):
        grant.invalidated_at = now
        grant.save(update_fields=["invalidated_at"])
        _event(
            item,
            ItemOwnershipEvent.EventType.PERMISSION_INVALIDATED,
            actor=item.original_owner_character,
            details={"permission": grant.permission, "grantee": grant.grantee.name if grant.grantee else ""},
        )


def _move_item(item: CharacterItem, destination: Character, *, activate_creatures=True):
    previous = item.owner
    previous_group = item.group_owner
    if previous is not None and previous.pk == destination.pk:
        return previous
    _invalidate_holder_permissions(item)
    item.owner = destination
    item.group_owner = None
    item.ownership_version = F("ownership_version") + 1
    item.equipped = False
    item.equip_locked = False
    item.stored = False
    item.save(update_fields=["owner", "group_owner", "ownership_version", "equipped", "equip_locked", "stored"])
    item.refresh_from_db(fields=["owner", "group_owner", "ownership_version"])
    CharacterCreature.objects.filter(source_character_item=item).update(
        owner=destination,
        active=activate_creatures,
    )
    return previous or previous_group


def _signature_value(value):
    if hasattr(value, "name"):
        return str(value.name or "")
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, default=str)
    return value


def _row_signature(row, *, excluded_fields=()):
    return tuple(
        (field.name, _signature_value(getattr(row, field.attname)))
        for field in row._meta.concrete_fields
        if not field.primary_key and field.name not in set(excluded_fields)
    )


def _related_stack_signature(item: CharacterItem):
    """Build a defensive signature from all discoverable instance state.

    History relations are intentionally excluded because they are rewired on a
    merge. Unknown related state is included by default, so future instance
    fields cannot silently disappear from merge comparison.
    """
    content_type = ContentType.objects.get_for_model(CharacterItem)
    components = []

    try:
        for field in item._meta.many_to_many:
            through = field.remote_field.through
            source_field_name = field.m2m_field_name()
            rows = through._default_manager.filter(**{source_field_name: item})
            components.append(
                (
                    f"m2m:{field.name}",
                    tuple(
                        sorted(
                            (
                                _row_signature(row, excluded_fields={source_field_name})
                                for row in rows
                            ),
                            key=repr,
                        )
                    ),
                )
            )

        history_accessors = {"transfers", "ownership_events"}
        for relation in item._meta.related_objects:
            accessor = relation.get_accessor_name()
            if not accessor or accessor in history_accessors:
                continue
            if relation.one_to_one:
                try:
                    manager = getattr(item, accessor)
                except relation.related_model.DoesNotExist:
                    manager = None
                rows = [manager] if manager is not None else []
            else:
                manager = getattr(item, accessor)
                rows = list(manager.all())
            row_signatures = tuple(
                sorted(
                    (
                        _row_signature(
                            row,
                            excluded_fields={
                                relation.field.name,
                                "granted_at",
                                "created_at",
                                "updated_at",
                            },
                        )
                        for row in rows
                    ),
                    key=repr,
                )
            )
            components.append((f"related:{accessor}", row_signatures))

        for relation in (
            field for field in item._meta.private_fields if isinstance(field, GenericRelation)
        ):
            rows = getattr(item, relation.name).all()
            components.append(
                (
                    f"generic-relation:{relation.name}",
                    tuple(
                        sorted(
                            (
                                _row_signature(
                                    row,
                                    excluded_fields={
                                        relation.content_type_field_name,
                                        relation.object_id_field_name,
                                        "created_at",
                                        "updated_at",
                                    },
                                )
                                for row in rows
                            ),
                            key=repr,
                        )
                    ),
                )
            )

        modifier_rows = Modifier.objects.filter(
            source_content_type=content_type,
            source_object_id=item.pk,
        )
        components.append(
            (
                "generic:modifiers",
                tuple(
                    sorted(
                        (
                            _row_signature(
                                row,
                                excluded_fields={"source_content_type", "source_object_id"},
                            )
                            for row in modifier_rows
                        ),
                        key=repr,
                    )
                ),
            )
        )
    except (AttributeError, ObjectDoesNotExist, TypeError, ValueError):
        return None
    return tuple(sorted(components, key=lambda entry: entry[0]))


def _concrete_stack_signature(item: CharacterItem):
    ignored_fields = {
        "id",
        "amount",
        "provenance_id",
        "ownership_version",
    }
    values = []
    for field in CharacterItem._meta.concrete_fields:
        if field.primary_key or field.name in ignored_fields:
            continue
        value = getattr(item, field.attname)
        values.append((field.name, (value.name or "") if hasattr(value, "name") else value))
    return tuple(values)


def _merge_compatible_stack(item: CharacterItem) -> CharacterItem:
    """Merge a returned split into an identical local stack without losing history."""
    if not item.item.stackable or item.transfers.filter(status=ItemTransfer.Status.PENDING).exists():
        return item
    if item.creatures.exists():
        return item

    candidates = (
        CharacterItem.objects.select_for_update()
        .filter(
            item_id=item.item_id,
            owner_id=item.owner_id,
            group_owner_id=item.group_owner_id,
        )
        .exclude(pk=item.pk)
        .exclude(
            pk__in=ItemTransfer.objects.filter(
                status=ItemTransfer.Status.PENDING,
                item_id__isnull=False,
            ).values("item_id")
        )
        .select_related("item")
        .order_by("pk")
    )
    item_concrete_signature = _concrete_stack_signature(item)
    item_signature = _related_stack_signature(item)
    if item_signature is None:
        return item
    target = next(
        (
            candidate
            for candidate in candidates
            if not candidate.creatures.exists()
            and _concrete_stack_signature(candidate) == item_concrete_signature
            and (candidate_signature := _related_stack_signature(candidate)) is not None
            and candidate_signature == item_signature
        ),
        None,
    )
    if target is None:
        return item

    target.amount += item.amount
    target.save(update_fields=["amount"])
    ItemTransfer.objects.filter(item=item).update(item=target)
    ItemOwnershipEvent.objects.filter(item=item).update(item=target)
    content_type = ContentType.objects.get_for_model(CharacterItem)
    Modifier.objects.filter(
        source_content_type=content_type,
        source_object_id=item.pk,
    ).delete()
    item.delete()
    return target


@transaction.atomic
def create_transfer(
    *,
    item_id: int,
    sender: Character,
    recipient: Character,
    quantity: int,
    message: str = "",
    permissions=None,
    transfer_original_ownership: bool = False,
):
    item = CharacterItem.objects.select_for_update(of=("self",)).select_related(
        "owner__owner", "owner__race", "original_owner_character", "item", "quality"
    ).get(pk=item_id)
    if item.owner_id != sender.pk:
        raise TransferError("not_owner", "Das Item gehört nicht diesem Charakter.", status=403)
    if recipient.pk == sender.pk or (
        recipient.is_archived and recipient.pk != item.original_owner_character_id
    ):
        raise TransferError("invalid_recipient", "Dieser Empfänger ist nicht zulässig.")
    if quantity < 1 or quantity > item.amount:
        raise TransferError("invalid_quantity", "Die gewählte Menge ist nicht verfügbar.")
    if item.equipped or item.equip_locked:
        raise TransferError("item_equipped", "Das Item muss vor dem Versand abgelegt werden.")
    existing_transfer = ItemTransfer.objects.select_for_update().filter(
        item=item, status=ItemTransfer.Status.PENDING
    ).first()
    if existing_transfer:
        if existing_transfer.expires_at <= timezone.now():
            _expire_locked(existing_transfer)
        else:
            raise TransferError("already_pending", "Für dieses Item besteht bereits eine Übergabe.", status=409)
    message = (message or "").strip()
    if len(message) > 1000:
        raise TransferError("message_too_long", "Die Nachricht darf höchstens 1000 Zeichen enthalten.")
    if quantity < item.amount:
        item = _split_item(item, quantity)
    requested_permissions = []
    for permission, irrevocable in (permissions or {}).items():
        if permission not in ItemPermissionGrant.Permission.values:
            raise TransferError("invalid_permission", "Unbekanntes Itemrecht.")
        requested_permissions.append(
            {
                "permission": permission,
                "label": ItemPermissionGrant.Permission(permission).label,
                "irrevocable": bool(irrevocable),
            }
        )
    if requested_permissions and item.original_owner_character_id != sender.pk:
        raise TransferError(
            "not_original_owner",
            "Nur der Ursprungsbesitzer darf Rechte mit der Übergabe erteilen.",
            status=403,
        )
    transfer_original_ownership = bool(transfer_original_ownership)
    if transfer_original_ownership and item.group_origin_finalized:
        raise TransferError(
            "group_origin_locked",
            "Der nach einer SL-Übergabe festgelegte Ursprungsbesitz ist dauerhaft.",
            status=409,
        )
    if transfer_original_ownership and item.original_owner_character_id != sender.pk:
        raise TransferError(
            "not_original_owner",
            "Nur der Originaleigentümer darf das Eigentum übertragen.",
            status=403,
        )
    if transfer_original_ownership and requested_permissions:
        raise TransferError(
            "ownership_transfer_with_permissions",
            "Bei einer Eigentumsübertragung sind einzelne Freigaben nicht erforderlich.",
        )
    now = timezone.now()
    item_snapshot = _item_snapshot(item)
    item_snapshot["creature_choices"] = _creature_choice_snapshot(item)
    item_snapshot["requested_permissions"] = requested_permissions
    item_snapshot["transfer_original_ownership"] = transfer_original_ownership
    transfer = ItemTransfer.objects.create(
        item=item,
        item_provenance_id=item.provenance_id,
        sender=sender,
        recipient=recipient,
        quantity=item.amount,
        message=message,
        item_snapshot=item_snapshot,
        sender_snapshot=_character_snapshot(sender),
        recipient_snapshot=_character_snapshot(recipient),
        expires_at=now + timedelta(days=7),
    )
    CharacterCreature.objects.filter(source_character_item=item).update(active=False)
    _event(item, ItemOwnershipEvent.EventType.CREATED, transfer=transfer, actor=sender, from_character=sender, to_character=recipient, details={"message": message})
    _notify(recipient.owner, item, "offer", f"{sender.name} möchte dir {item.effective_name} übergeben.", transfer)
    return transfer


@transaction.atomic
def create_gm_edit_transfer(
    *,
    item_id: int,
    sender: Character,
    group,
    message: str = "",
):
    """Share an owned item with the active GMs of one membership group for editing."""
    from charsheet.models import GameGroup, GameGroupMembership

    locked_group = GameGroup.objects.select_for_update().get(pk=group.pk)
    item = (
        CharacterItem.objects.select_for_update(of=("self",))
        .select_related("owner__owner", "owner__race", "item", "quality")
        .get(pk=item_id)
    )
    if item.owner_id != sender.pk:
        raise TransferError("not_owner", "Das Item gehört nicht diesem Charakter.", status=403)
    if item.equipped or item.equip_locked:
        raise TransferError("item_equipped", "Das Item muss vor der SL-Bearbeitung abgelegt werden.")
    if locked_group.is_archived or sender.is_archived:
        raise TransferError("group_archived", "Archivierte Gruppen oder Charaktere können keine SL-Bearbeitung erhalten.", status=409)
    if not GameGroupMembership.objects.select_for_update().filter(
        group=locked_group,
        character=sender,
        status=GameGroupMembership.Status.ACTIVE,
    ).exists():
        raise TransferError("group_membership_required", "Der Charakter ist kein aktives Mitglied dieser Gruppe.", status=403)
    if ItemTransfer.objects.select_for_update().filter(
        item=item,
        sender=sender,
        recipient_group=locked_group,
        transfer_kind=ItemTransfer.TransferKind.GM_EDIT,
        status=ItemTransfer.Status.PENDING,
    ).exists():
        raise TransferError("already_shared_with_gm", "Dieses Item liegt dieser Gruppenleitung bereits zur Bearbeitung vor.", status=409)
    message = str(message or "").strip()
    if len(message) > 1000:
        raise TransferError("message_too_long", "Die Nachricht darf höchstens 1000 Zeichen enthalten.")
    now = timezone.now()
    item_snapshot = _item_snapshot(item)
    item_snapshot["gm_edit"] = True
    transfer = ItemTransfer.objects.create(
        item=item,
        item_provenance_id=item.provenance_id,
        sender=sender,
        recipient=None,
        recipient_group=locked_group,
        transfer_kind=ItemTransfer.TransferKind.GM_EDIT,
        quantity=item.amount,
        message=message,
        status=ItemTransfer.Status.PENDING,
        item_snapshot=item_snapshot,
        sender_snapshot=_character_snapshot(sender),
        recipient_snapshot={"type": "gm_group", "id": locked_group.pk, "name": f"SL @ {locked_group.name}"},
        expires_at=now + timedelta(days=7),
    )
    _event(
        item,
        ItemOwnershipEvent.EventType.CREATED,
        transfer=transfer,
        actor=sender,
        from_character=sender,
        to_character=sender,
        details={"gm_edit": True, "group_id": locked_group.pk, "group_name": locked_group.name},
    )
    _notify_group_game_masters(
        locked_group,
        item,
        "gm_edit",
        f"{sender.name} hat {item.effective_name} zur SL-Bearbeitung gesendet.",
        transfer,
    )
    return transfer


@transaction.atomic
def complete_gm_edit_transfer(*, transfer_id: int, group, actor):
    """Finish an active GM editing handoff without moving the item."""
    from charsheet.game_groups import require_game_master
    from charsheet.models import GameGroup

    locked_group = GameGroup.objects.select_for_update().get(pk=group.pk)
    require_game_master(actor, locked_group, write=True)
    transfer = (
        ItemTransfer.objects.select_for_update(of=("self",))
        .select_related("item__owner__owner", "recipient_group", "sender__owner")
        .get(pk=transfer_id)
    )
    if (
        transfer.transfer_kind != ItemTransfer.TransferKind.GM_EDIT
        or transfer.recipient_group_id != locked_group.pk
        or transfer.status != ItemTransfer.Status.PENDING
        or not transfer.item_id
    ):
        raise TransferError("gm_edit_closed", "Diese SL-Bearbeitung ist nicht mehr aktiv.", status=409)
    item = CharacterItem.objects.select_for_update(of=("self",)).get(pk=transfer.item_id)
    if item.owner_id != transfer.sender_id:
        raise TransferError("ownership_changed", "Der Besitzer des Items hat sich geändert.", status=409)
    transfer.status = ItemTransfer.Status.ACCEPTED
    transfer.resolved_at = timezone.now()
    transfer.save(update_fields=["status", "resolved_at"])
    _event(
        item,
        ItemOwnershipEvent.EventType.ACCEPTED,
        transfer=transfer,
        actor_user=actor,
        from_character=transfer.sender,
        to_character=transfer.sender,
        details={"gm_edit": True, "group_id": locked_group.pk, "completed": True},
    )
    _notify(
        transfer.sender.owner,
        item,
        "gm_edit_completed",
        f"Die SL-Bearbeitung von {item.effective_name} ist abgeschlossen.",
        transfer,
    )
    return transfer


@transaction.atomic
def create_group_transfer(
    *,
    item_id: int,
    group,
    actor,
    recipient: Character,
    quantity: int,
    message: str = "",
):
    from charsheet.game_groups import require_game_master
    from charsheet.models import GameGroupMembership

    locked_group = type(group).objects.select_for_update().get(pk=group.pk)
    require_game_master(actor, locked_group, write=True)
    item = (
        CharacterItem.objects.select_for_update(of=("self",))
        .select_related("group_owner", "original_owner_group", "item", "quality")
        .get(pk=item_id)
    )
    if item.group_owner_id != locked_group.pk or item.original_owner_group_id != locked_group.pk:
        raise TransferError("not_owner", "Das Item gehört nicht diesem Gruppeninventar.", status=403)
    if item.owner_id is not None or item.original_owner_character_id is not None:
        raise TransferError("invalid_group_item", "Der Gruppenbesitz dieses Items ist inkonsistent.", status=409)
    if recipient.is_archived or not GameGroupMembership.objects.select_for_update().filter(
        group=locked_group,
        character=recipient,
        status=GameGroupMembership.Status.ACTIVE,
    ).exists():
        raise TransferError("invalid_recipient", "Empfänger muss aktives Mitglied dieser Gruppe sein.")
    if quantity < 1 or quantity > item.amount:
        raise TransferError("invalid_quantity", "Die gewählte Menge ist nicht verfügbar.")
    if item.equipped or item.equip_locked:
        raise TransferError("item_equipped", "Das Item kann in diesem Zustand nicht versendet werden.")
    existing = ItemTransfer.objects.select_for_update().filter(
        item=item,
        status=ItemTransfer.Status.PENDING,
    ).first()
    if existing:
        if existing.expires_at <= timezone.now():
            _expire_locked(existing)
        else:
            raise TransferError("already_pending", "Für dieses Item besteht bereits eine Übergabe.", status=409)
    message = str(message or "").strip()
    if len(message) > 1000:
        raise TransferError("message_too_long", "Die Nachricht darf höchstens 1000 Zeichen enthalten.")
    if quantity < item.amount:
        item = _split_item(item, quantity)
    now = timezone.now()
    item_snapshot = _item_snapshot(item)
    item_snapshot["creature_choices"] = _creature_choice_snapshot(item)
    item_snapshot["requested_permissions"] = []
    item_snapshot["transfer_original_ownership"] = True
    transfer = ItemTransfer.objects.create(
        item=item,
        item_provenance_id=item.provenance_id,
        sender=None,
        sender_group=locked_group,
        initiated_by_user=actor,
        recipient=recipient,
        quantity=item.amount,
        message=message,
        item_snapshot=item_snapshot,
        sender_snapshot={"type": "group", "id": locked_group.pk, "name": locked_group.name},
        recipient_snapshot=_character_snapshot(recipient),
        expires_at=now + timedelta(days=7),
    )
    _event(
        item,
        ItemOwnershipEvent.EventType.CREATED,
        transfer=transfer,
        actor_user=actor,
        from_group=locked_group,
        to_character=recipient,
        details={"message": message},
    )
    _notify(
        recipient.owner,
        item,
        "offer",
        f"{locked_group.name} möchte dir {item.effective_name} übergeben.",
        transfer,
    )
    return transfer


def _lock_pending_transfer(transfer_id: int):
    transfer = ItemTransfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.status != ItemTransfer.Status.PENDING or transfer.item_id is None:
        raise TransferError("transfer_closed", "Diese Übergabe ist bereits abgeschlossen.", status=409)
    if transfer.expires_at <= timezone.now():
        _expire_locked(transfer)
        raise TransferError("transfer_expired", "Diese Übergabe ist abgelaufen.", status=409)
    CharacterItem.objects.select_for_update().get(pk=transfer.item_id)
    return transfer


@transaction.atomic
def accept_transfer(*, transfer_id: int, recipient: Character):
    preliminary = ItemTransfer.objects.select_related("sender_group").get(pk=transfer_id)
    if preliminary.sender_group_id:
        from charsheet.models import GameGroup, GameGroupMembership

        group = GameGroup.objects.select_for_update().get(pk=preliminary.sender_group_id)
        membership_exists = GameGroupMembership.objects.select_for_update().filter(
            group=group,
            character=recipient,
            status=GameGroupMembership.Status.ACTIVE,
        ).exists()
        recipient = Character.objects.select_for_update().get(pk=recipient.pk)
        if group.is_archived:
            raise TransferError("group_archived", "Die absendende Gruppe ist archiviert.", status=409)
        if recipient.is_archived or not membership_exists:
            raise TransferError(
                "group_membership_required",
                "Der Charakter ist kein aktives Mitglied der absendenden Gruppe.",
                status=409,
            )
    transfer = _lock_pending_transfer(transfer_id)
    if transfer.recipient_id != recipient.pk:
        raise TransferError("not_recipient", "Nur der Empfänger kann diese Übergabe annehmen.", status=403)
    item = CharacterItem.objects.select_for_update().get(pk=transfer.item_id)
    previous = item.owner
    previous_group = item.group_owner
    previous_original_owner = item.original_owner_character
    previous_original_group = item.original_owner_group
    _move_item(item, recipient)
    _restore_creature_choices(
        item,
        transfer.item_snapshot.get("creature_choices", []),
    )
    transfers_original_ownership = bool(
        transfer.item_snapshot.get("transfer_original_ownership")
    )
    if transfers_original_ownership:
        now = timezone.now()
        active_grants = ItemPermissionGrant.objects.select_for_update().filter(
            item=item,
            revoked_at__isnull=True,
            invalidated_at__isnull=True,
        )
        active_grants.update(invalidated_at=now)
        CharacterItem.objects.filter(pk=item.pk).update(
            original_owner_character=recipient,
            original_owner_group=None,
            group_origin_finalized=bool(previous_original_group),
        )
        item.original_owner_character = recipient
        item.original_owner_character_id = recipient.pk
        item.original_owner_group = None
        item.original_owner_group_id = None
        if previous_original_group:
            item.group_origin_finalized = True
    else:
        for requested in transfer.item_snapshot.get("requested_permissions", []):
            set_item_permission(
                item_id=item.pk,
                original_owner=item.original_owner_character,
                permission=requested.get("permission", ""),
                enabled=True,
                irrevocable=bool(requested.get("irrevocable")),
            )
        now = timezone.now()
    transfer.status = ItemTransfer.Status.ACCEPTED
    transfer.resolved_at = now
    transfer.save(update_fields=["status", "resolved_at"])
    _event(
        item,
        ItemOwnershipEvent.EventType.ACCEPTED,
        transfer=transfer,
        actor=recipient,
        from_character=previous,
        from_group=previous_group,
        to_character=recipient,
        details={
            "original_ownership_transferred": transfers_original_ownership,
            "previous_original_owner_id": previous_original_owner.pk if previous_original_owner else None,
            "previous_original_owner_name": previous_original_owner.name if previous_original_owner else "",
            "previous_original_owner_group_id": previous_original_group.pk if previous_original_group else None,
            "previous_original_owner_group_name": previous_original_group.name if previous_original_group else "",
        },
    )
    if previous_group:
        _notify_group_game_masters(
            previous_group,
            item,
            "accepted",
            f"{recipient.name} hat {item.effective_name} angenommen.",
            transfer,
        )
    else:
        _notify(previous.owner, item, "accepted", f"{recipient.name} hat {item.effective_name} angenommen.", transfer)
    _merge_compatible_stack(item)
    return transfer


@transaction.atomic
def decline_transfer(*, transfer_id: int, recipient: Character):
    transfer = _lock_pending_transfer(transfer_id)
    if transfer.recipient_id != recipient.pk:
        raise TransferError("not_recipient", "Nur der Empfänger kann diese Übergabe ablehnen.", status=403)
    item = transfer.item
    transfer.status = ItemTransfer.Status.DECLINED
    transfer.resolved_at = timezone.now()
    transfer.save(update_fields=["status", "resolved_at"])
    CharacterCreature.objects.filter(source_character_item=item).update(active=True)
    _event(
        item,
        ItemOwnershipEvent.EventType.DECLINED,
        transfer=transfer,
        actor=recipient,
        from_character=recipient,
        to_character=transfer.sender,
        to_group=transfer.sender_group,
    )
    if transfer.sender_group_id:
        _notify_group_game_masters(
            transfer.sender_group,
            item,
            "declined",
            f"{recipient.name} hat die Übergabe von {item.effective_name} abgelehnt.",
            transfer,
        )
    else:
        _notify(transfer.sender.owner, item, "declined", f"{recipient.name} hat die Übergabe von {item.effective_name} abgelehnt.", transfer)
    _merge_compatible_stack(item)
    return transfer


@transaction.atomic
def recall_transfer(*, transfer_id: int, sender: Character):
    """Withdraw one pending offer without changing the current item owner."""
    transfer = _lock_pending_transfer(transfer_id)
    if transfer.transfer_kind == ItemTransfer.TransferKind.GM_EDIT:
        raise TransferError(
            "gm_edit_in_progress",
            "Eine laufende SL-Bearbeitung kann nicht zurückgerufen werden.",
            status=409,
        )
    if transfer.sender_id != sender.pk:
        raise TransferError(
            "not_sender",
            "Nur der Absender kann diese Übergabe zurückziehen.",
            status=403,
        )
    item = CharacterItem.objects.select_for_update().get(pk=transfer.item_id)
    if item.owner_id != sender.pk:
        raise TransferError(
            "ownership_changed",
            "Der Besitzer des Items hat sich inzwischen geändert.",
            status=409,
        )
    transfer.status = ItemTransfer.Status.RECALLED
    transfer.resolved_at = timezone.now()
    transfer.save(update_fields=["status", "resolved_at"])
    CharacterCreature.objects.filter(source_character_item=item).update(active=True)
    _event(
        item,
        ItemOwnershipEvent.EventType.RECALLED,
        transfer=transfer,
        actor=sender,
        from_character=transfer.recipient,
        to_character=sender,
    )
    _notify(
        transfer.recipient.owner,
        item,
        "recalled",
        f"{sender.name} hat das Angebot für {item.effective_name} zurückgezogen.",
        transfer,
    )
    _merge_compatible_stack(item)
    return transfer


def recall_group_transfer_locked(*, transfer_id: int, reason: str = "recalled"):
    """Recall a group offer while preserving group ownership and origin."""
    transfer = (
        ItemTransfer.objects.select_for_update(of=("self",))
        .select_related("sender_group", "recipient__owner", "initiated_by_user")
        .get(pk=transfer_id)
    )
    if transfer.status != ItemTransfer.Status.PENDING or not transfer.item_id:
        return transfer
    if not transfer.sender_group_id:
        raise TransferError("not_group_transfer", "Diese Übergabe stammt nicht aus einer Gruppe.", status=409)
    item = CharacterItem.objects.select_for_update().get(pk=transfer.item_id)
    if item.group_owner_id != transfer.sender_group_id:
        raise TransferError("ownership_changed", "Der Gruppenbesitz hat sich geändert.", status=409)
    transfer.status = ItemTransfer.Status.RECALLED
    transfer.resolved_at = timezone.now()
    transfer.save(update_fields=["status", "resolved_at"])
    _event(
        item,
        ItemOwnershipEvent.EventType.RECALLED,
        transfer=transfer,
        actor_user=transfer.initiated_by_user,
        from_character=transfer.recipient,
        to_group=transfer.sender_group,
        details={"reason": reason},
    )
    _notify(
        transfer.recipient.owner,
        item,
        "recalled",
        f"{transfer.sender_group.name} hat das Angebot für {item.effective_name} zurückgezogen.",
        transfer,
    )
    _merge_compatible_stack(item)
    return transfer


@transaction.atomic
def recall_group_transfer(*, transfer_id: int, group, actor):
    from charsheet.game_groups import require_game_master

    locked_group = type(group).objects.select_for_update().get(pk=group.pk)
    require_game_master(actor, locked_group, write=True)
    transfer = ItemTransfer.objects.select_for_update().get(pk=transfer_id)
    if transfer.sender_group_id != locked_group.pk:
        raise TransferError("not_sender", "Diese Übergabe stammt nicht aus dieser Gruppe.", status=403)
    return recall_group_transfer_locked(transfer_id=transfer_id)


@transaction.atomic
def return_to_original_owner(*, item_id: int, holder: Character):
    """Return a borrowed item immediately without creating another offer."""
    item = CharacterItem.objects.select_for_update(of=("self",)).select_related(
        "owner__owner", "original_owner_character__owner"
    ).get(pk=item_id)
    if item.owner_id != holder.pk:
        raise TransferError(
            "not_holder",
            "Nur der aktuelle Besitzer kann dieses Item zurückgeben.",
            status=403,
        )
    if item.original_owner_character_id == holder.pk:
        raise TransferError(
            "already_home",
            "Das Item befindet sich bereits beim Eigentümer.",
            status=409,
        )
    if ItemTransfer.objects.select_for_update().filter(
        item=item,
        status=ItemTransfer.Status.PENDING,
    ).exists():
        raise TransferError(
            "already_pending",
            "Eine laufende Übergabe muss zuerst zurückgezogen werden.",
            status=409,
        )
    original_owner = item.original_owner_character
    _move_item(item, original_owner)
    _event(
        item,
        ItemOwnershipEvent.EventType.RETURNED,
        actor=holder,
        from_character=holder,
        to_character=original_owner,
    )
    _notify(
        original_owner.owner,
        item,
        "returned",
        f"{holder.name} hat {item.effective_name} direkt zurückgegeben.",
    )
    return _merge_compatible_stack(item)


def _expire_locked(transfer: ItemTransfer):
    if transfer.status != ItemTransfer.Status.PENDING or not transfer.item_id:
        return False
    item = transfer.item
    transfer.status = ItemTransfer.Status.EXPIRED
    transfer.resolved_at = timezone.now()
    transfer.save(update_fields=["status", "resolved_at"])
    CharacterCreature.objects.filter(source_character_item=item).update(active=True)
    if transfer.transfer_kind == ItemTransfer.TransferKind.GM_EDIT:
        _event(
            item,
            ItemOwnershipEvent.EventType.EXPIRED,
            transfer=transfer,
            from_character=transfer.sender,
            to_character=transfer.sender,
            details={
                "gm_edit": True,
                "group_id": transfer.recipient_group_id,
                "reason": "editing_window_expired",
            },
        )
        _notify(
            transfer.sender.owner,
            item,
            "expired",
            f"Die SL-Bearbeitung von {item.effective_name} ist abgelaufen.",
            transfer,
        )
        return True
    _event(
        item,
        ItemOwnershipEvent.EventType.EXPIRED,
        transfer=transfer,
        from_character=transfer.recipient,
        to_character=transfer.sender,
        to_group=transfer.sender_group,
    )
    if transfer.sender_group_id:
        _notify_group_game_masters(
            transfer.sender_group,
            item,
            "expired",
            f"Die Übergabe von {item.effective_name} ist abgelaufen.",
            transfer,
        )
    else:
        _notify(transfer.sender.owner, item, "expired", f"Die Übergabe von {item.effective_name} ist abgelaufen.", transfer)
    _notify(transfer.recipient.owner, item, "expired", f"Das Angebot für {item.effective_name} ist abgelaufen.", transfer)
    _merge_compatible_stack(item)
    return True


def expire_due_transfers(*, limit=250):
    expired = 0
    due_ids = list(ItemTransfer.objects.filter(status=ItemTransfer.Status.PENDING, expires_at__lte=timezone.now()).values_list("pk", flat=True)[:limit])
    for transfer_id in due_ids:
        with transaction.atomic():
            transfer = ItemTransfer.objects.select_for_update().filter(pk=transfer_id).first()
            if transfer and _expire_locked(transfer):
                expired += 1
    return expired


@transaction.atomic
def enforce_original_ownership(*, item_id: int, original_owner: Character):
    item = CharacterItem.objects.select_for_update(of=("self",)).select_related("owner__owner", "original_owner_character__owner").get(pk=item_id)
    if item.original_owner_character_id != original_owner.pk:
        raise TransferError("not_original_owner", "Nur der Ursprungsbesitzer darf die Zwangsvollstreckung ausführen.", status=403)
    pending = ItemTransfer.objects.select_for_update().filter(item=item, status=ItemTransfer.Status.PENDING).first()
    if pending:
        pending.status = ItemTransfer.Status.RECALLED
        pending.resolved_at = timezone.now()
        pending.save(update_fields=["status", "resolved_at"])
        _event(item, ItemOwnershipEvent.EventType.RECALLED, transfer=pending, actor=original_owner, from_character=pending.sender, to_character=original_owner)
        _notify(pending.recipient.owner, item, "recalled", f"Das Angebot für {item.effective_name} wurde zurückgezogen.", pending)
        if item.owner_id == original_owner.pk:
            CharacterCreature.objects.filter(source_character_item=item).update(active=True)
            return _merge_compatible_stack(item)
    if item.owner_id == original_owner.pk:
        raise TransferError("already_home", "Das Item befindet sich bereits beim Ursprungsbesitzer.", status=409)
    previous = item.owner
    _move_item(item, original_owner)
    _event(item, ItemOwnershipEvent.EventType.ENFORCED, actor=original_owner, from_character=previous, to_character=original_owner)
    _notify(previous.owner, item, "enforced", f"{item.effective_name} wurde von {original_owner.name} zwangsweise zurückgeholt.")
    return _merge_compatible_stack(item)


def has_item_permission(item: CharacterItem, permission: str, character: Character | None = None) -> bool:
    character = character or item.owner
    if character.pk == item.original_owner_character_id:
        return True
    grants = ItemPermissionGrant.objects.filter(item=item, permission=permission, revoked_at__isnull=True, invalidated_at__isnull=True)
    if permission == ItemPermissionGrant.Permission.CONSUME_FINAL:
        return grants.filter(grantee__isnull=True).exists()
    return grants.filter(grantee=character, ownership_version=item.ownership_version).exists()


@transaction.atomic
def set_item_permission(*, item_id: int, original_owner: Character, permission: str, enabled: bool, irrevocable=False):
    item = CharacterItem.objects.select_for_update(of=("self",)).select_related("owner", "original_owner_character").get(pk=item_id)
    if item.original_owner_character_id != original_owner.pk:
        raise TransferError("not_original_owner", "Nur der Ursprungsbesitzer darf Rechte verwalten.", status=403)
    if permission not in ItemPermissionGrant.Permission.values:
        raise TransferError("invalid_permission", "Unbekanntes Itemrecht.")
    filters = {"item": item, "permission": permission, "revoked_at__isnull": True, "invalidated_at__isnull": True}
    if permission == ItemPermissionGrant.Permission.CONSUME_FINAL:
        filters["grantee__isnull"] = True
    else:
        filters.update({"grantee": item.owner, "ownership_version": item.ownership_version})
    active = ItemPermissionGrant.objects.select_for_update().filter(**filters).first()
    if enabled:
        if not active:
            active = ItemPermissionGrant.objects.create(
                item=item,
                permission=permission,
                granted_by=original_owner,
                grantee=None if permission == ItemPermissionGrant.Permission.CONSUME_FINAL else item.owner,
                ownership_version=None if permission == ItemPermissionGrant.Permission.CONSUME_FINAL else item.ownership_version,
                irrevocable=bool(irrevocable),
            )
            _event(item, ItemOwnershipEvent.EventType.PERMISSION_GRANTED, actor=original_owner, to_character=item.owner, details={"permission": permission, "irrevocable": bool(irrevocable)})
        return active
    if active:
        if active.irrevocable:
            raise TransferError("permission_irrevocable", "Dieses Recht wurde unwiderruflich erteilt.", status=409)
        active.revoked_at = timezone.now()
        active.save(update_fields=["revoked_at"])
        _event(item, ItemOwnershipEvent.EventType.PERMISSION_REVOKED, actor=original_owner, to_character=item.owner, details={"permission": permission})
    return active


def record_item_destruction(item: CharacterItem, actor: Character, reason: str):
    _event(item, ItemOwnershipEvent.EventType.DESTROYED, actor=actor, from_character=actor, details={"reason": reason, "snapshot": _item_snapshot(item)})
