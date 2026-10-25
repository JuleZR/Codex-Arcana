"""Safe account deactivation and permanent-deletion rules."""

from dataclasses import dataclass

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import ImageField, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import (
    CharacterItem,
    CharacterLanguage,
    GameGroup,
    GameGroupCreature,
    GameGroupInvitation,
    GameGroupMembership,
    GameGroupRole,
    GameGroupTable,
    ItemOwnershipEvent,
    ItemPermissionGrant,
    ItemTransfer,
)


@dataclass(frozen=True)
class AccountDeletionBlocker:
    code: str
    label: str
    count: int


def _delete_account_image(storage, name):
    if storage.exists(name):
        storage.delete(name)


@receiver(pre_delete, sender=get_user_model(),
          dispatch_uid="charsheet.delete_account_images")
def schedule_account_image_deletion(sender, instance, using, **kwargs):
    """Remove private uploads after a successful account deletion commits."""
    owned_models = (
        ("Character", "owner_id"),
        ("CharacterItem", "owner__owner_id"),
        ("CharacterItemDisclosure", "character_item__owner__owner_id"),
        ("CharacterCreature", "owner__owner_id"),
        ("CharacterDivineEntity", "character__owner_id"),
        ("CharacterDruidCult", "character__owner_id"),
        ("CharacterShamanPatron", "character__owner_id"),
    )
    images = {}
    for model_name, owner_path in owned_models:
        model = apps.get_model("charsheet", model_name)
        fields = [
            field for field in model._meta.concrete_fields
            if isinstance(field, ImageField)
        ]
        for record in model._default_manager.using(using).filter(
            **{owner_path: instance.pk}
        ).only(*(field.name for field in fields)):
            for field in fields:
                picture = getattr(record, field.name)
                if picture:
                    images[(id(picture.storage), picture.name)] = (
                        picture.storage, picture.name
                    )
    for storage, name in images.values():
        transaction.on_commit(
            lambda storage=storage, name=name: _delete_account_image(
                storage, name
            ),
            using=using,
        )


def account_deletion_blockers(user):
    """Return readable safeguards that prevent permanent account deletion."""
    character_ids = user.character_set.values_list("pk", flat=True)
    character_creature_ids = user.character_set.values_list(
        "creatures__pk",
        flat=True,
    )
    checks = (
        (
            "created_groups",
            "Von dir erstellte Spielgruppen müssen ausdrücklich "
            "übertragen werden.",
            GameGroup.objects.filter(creator=user),
        ),
        (
            "group_roles",
            "Gruppenleitungen, SL-Rollen oder deren Historie verweisen "
            "auf dein Konto.",
            GameGroupRole.objects.filter(user=user),
        ),
        (
            "pending_invitations",
            "Von dir versendete offene Gruppeneinladungen müssen zuerst "
            "geklärt werden.",
            GameGroupInvitation.objects.filter(
                invited_by=user,
                status=GameGroupInvitation.Status.PENDING,
            ),
        ),
        (
            "invitation_history",
            "Abgeschlossene Gruppeneinladungen bewahren dich als Absender.",
            GameGroupInvitation.objects.filter(invited_by=user).exclude(
                status=GameGroupInvitation.Status.PENDING
            ),
        ),
        (
            "group_tables",
            "Von dir erstellte Gruppentabellen müssen ausdrücklich "
            "übertragen werden.",
            GameGroupTable.objects.filter(creator=user),
        ),
        (
            "character_group_invitations",
            "Gruppeneinladungen deiner Charaktere müssen zuerst geklärt "
            "werden.",
            GameGroupInvitation.objects.filter(character_id__in=character_ids),
        ),
        (
            "character_group_memberships",
            "Gruppenmitgliedschaften deiner Charaktere müssen zuerst "
            "geklärt werden.",
            GameGroupMembership.objects.filter(character_id__in=character_ids),
        ),
        (
            "group_creature_cards",
            "Gemeinsam genutzte Gruppenkarten verweisen auf Kreaturen "
            "deiner Charaktere.",
            GameGroupCreature.objects.filter(
                character_creature_id__in=character_creature_ids
            ),
        ),
        (
            "initiated_transfers",
            "Gegenstandsübergaben oder deren Historie verweisen auf dein "
            "Konto.",
            ItemTransfer.objects.filter(
                Q(initiated_by_user=user)
                | Q(sender_id__in=character_ids)
                | Q(recipient_id__in=character_ids)
            ).distinct(),
        ),
        (
            "ownership_history",
            "Die Eigentumschronik von Gegenständen verweist auf dein Konto.",
            ItemOwnershipEvent.objects.filter(
                Q(actor_user=user)
                | Q(actor_id__in=character_ids)
                | Q(original_owner_id__in=character_ids)
                | Q(from_character_id__in=character_ids)
                | Q(to_character_id__in=character_ids)
            ).distinct(),
        ),
        (
            "item_permissions",
            "Gegenstandsrechte verweisen auf einen deiner Charaktere.",
            ItemPermissionGrant.objects.filter(
                granted_by_id__in=character_ids
            ),
        ),
    )
    blockers = []
    for code, label, queryset in checks:
        count = queryset.count()
        if count:
            blockers.append(AccountDeletionBlocker(code, label, count))
    return blockers


@transaction.atomic
def delete_account_permanently(user):
    """Delete private account data only when shared references are resolved."""
    user = (
        get_user_model()._default_manager.select_for_update().get(pk=user.pk)
    )
    blockers = account_deletion_blockers(user)
    if blockers:
        return blockers

    schedule_account_image_deletion(
        sender=type(user), instance=user, using=user._state.db
    )
    characters = user.character_set.all()
    CharacterLanguage.objects.filter(owner__in=characters).delete()
    CharacterItem.objects.filter(owner__in=characters).delete()
    user.delete()
    return []
