"""Persistent item transfer, provenance, notification, and permission models."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ItemTransfer(models.Model):
    class TransferKind(models.TextChoices):
        OWNERSHIP = "ownership", "Gegenstandsübergabe"
        GM_EDIT = "gm_edit", "SL-Bearbeitung"

    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        ACCEPTED = "accepted", "Angenommen"
        DECLINED = "declined", "Abgelehnt"
        EXPIRED = "expired", "Abgelaufen"
        RECALLED = "recalled", "Zurückgerufen"

    item = models.ForeignKey(
        "charsheet.CharacterItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers",
    )
    item_provenance_id = models.UUIDField(db_index=True)
    sender = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_item_transfers",
    )
    sender_group = models.ForeignKey(
        "charsheet.GameGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sent_item_transfers",
    )
    initiated_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="initiated_group_item_transfers",
    )
    recipient = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_item_transfers",
    )
    recipient_group = models.ForeignKey(
        "charsheet.GameGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="received_item_transfers",
    )
    transfer_kind = models.CharField(
        max_length=16,
        choices=TransferKind.choices,
        default=TransferKind.OWNERSHIP,
    )
    quantity = models.PositiveIntegerField(default=1)
    message = models.TextField(blank=True, default="", max_length=1000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    item_snapshot = models.JSONField(default=dict)
    sender_snapshot = models.JSONField(default=dict)
    recipient_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "status"], name="transfer_recipient_status"),
            models.Index(fields=["sender", "status"], name="transfer_sender_status"),
            models.Index(fields=["recipient_group", "status"], name="transfer_group_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(status="pending", item__isnull=False),
                name="uniq_pending_transfer_per_item",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(transfer_kind="ownership", recipient_group__isnull=True)
                    | models.Q(transfer_kind="gm_edit", recipient__isnull=True, recipient_group__isnull=False)
                ),
                name="transfer_recipient_matches_kind",
            ),
        ]

    def __str__(self):
        return f"{self.item_snapshot.get('name', self.item_provenance_id)}: {self.get_status_display()}"


class ItemOwnershipEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Übergabe erstellt"
        ACCEPTED = "accepted", "Übergabe angenommen"
        DECLINED = "declined", "Übergabe abgelehnt"
        EXPIRED = "expired", "Automatisch zurückgegeben"
        RECALLED = "recalled", "Übergabe zurückgerufen"
        RETURNED = "returned", "An Eigentümer zurückgegeben"
        ENFORCED = "enforced", "Zwangsvollstreckung"
        PERMISSION_GRANTED = "permission_granted", "Recht erteilt"
        PERMISSION_REVOKED = "permission_revoked", "Recht widerrufen"
        PERMISSION_INVALIDATED = "permission_invalidated", "Recht durch Besitzerwechsel beendet"
        DESTROYED = "destroyed", "Item endgültig entfernt"

    item = models.ForeignKey(
        "charsheet.CharacterItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ownership_events",
    )
    item_provenance_id = models.UUIDField(db_index=True)
    transfer = models.ForeignKey(
        ItemTransfer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    actor = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_ownership_actions",
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="group_item_ownership_actions",
    )
    original_owner = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_origin_history",
    )
    original_owner_group = models.ForeignKey(
        "charsheet.GameGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="item_origin_history",
    )
    from_character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_ownership_departures",
    )
    from_group = models.ForeignKey(
        "charsheet.GameGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="item_ownership_departures",
    )
    to_character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_ownership_arrivals",
    )
    to_group = models.ForeignKey(
        "charsheet.GameGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="item_ownership_arrivals",
    )
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ItemPermissionGrant(models.Model):
    class Permission(models.TextChoices):
        CONSUME_FINAL = "consume_final", "Letzte Einheit verbrauchen"
        SELL = "sell", "Verkaufen"
        DESTROY = "destroy", "Zerstören"

    item = models.ForeignKey(
        "charsheet.CharacterItem",
        on_delete=models.CASCADE,
        related_name="permission_grants",
    )
    permission = models.CharField(max_length=20, choices=Permission.choices)
    granted_by = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.PROTECT,
        related_name="granted_item_permissions",
    )
    grantee = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="received_item_permissions",
    )
    ownership_version = models.PositiveIntegerField(null=True, blank=True)
    irrevocable = models.BooleanField(default=False)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["item", "permission", "-granted_at"]
        indexes = [models.Index(fields=["item", "permission"], name="item_permission_lookup")]

    def clean(self):
        super().clean()
        if self.item_id and self.granted_by_id != self.item.original_owner_character_id:
            raise ValidationError({"granted_by": "Only the original owner may grant item rights."})
        if self.permission == self.Permission.CONSUME_FINAL:
            if self.grantee_id is not None or self.ownership_version is not None:
                raise ValidationError("The final-consumption permission follows the item, not a holder.")
        elif not self.grantee_id or self.ownership_version is None:
            raise ValidationError("Holder-bound permissions require a grantee and ownership version.")

    @property
    def active(self):
        return self.revoked_at is None and self.invalidated_at is None


class ItemTransferNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="item_transfer_notifications",
    )
    transfer = models.ForeignKey(
        ItemTransfer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notifications",
    )
    item_provenance_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=32)
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
