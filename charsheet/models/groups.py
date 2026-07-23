"""Persistent game-group, game-master, invitation, and membership models."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower


class GameGroupQuerySet(models.QuerySet):
    """Game groups are historical records and may only be archived."""

    def delete(self):
        raise ValidationError("Spielgruppen können nicht gelöscht, sondern nur archiviert werden.")


class GameGroup(models.Model):
    name = models.CharField(max_length=150)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_game_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uniq_game_group_name_ci")
        ]

    def delete(self, *args, **kwargs):
        raise ValidationError("Spielgruppen können nicht gelöscht, sondern nur archiviert werden.")

    def save(self, *args, **kwargs):
        creating = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if creating:
                GameGroupRole.objects.create(
                    group=self,
                    user=self.creator,
                    role=GameGroupRole.Role.LEADER,
                    is_active=True,
                )

    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.name


class GameGroupRole(models.Model):
    class Role(models.TextChoices):
        LEADER = "leader", "Gruppenleitung"
        GM = "gm", "Spielleiter"

    group = models.ForeignKey(
        GameGroup,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="game_group_roles",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.GM)
    is_active = models.BooleanField(default=True, db_index=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["group", "role", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="uniq_game_group_role_user",
            ),
            models.UniqueConstraint(
                fields=["group"],
                condition=Q(role="leader", is_active=True),
                name="uniq_active_game_group_leader",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_active and self.revoked_at is not None:
            raise ValidationError({"revoked_at": "Eine aktive Rolle darf nicht widerrufen sein."})

    @property
    def is_game_master(self) -> bool:
        """The leader is a game master with additional administration rights."""
        return self.is_active and self.role in {self.Role.LEADER, self.Role.GM}

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_leadership_transfer", False):
            previous = type(self).objects.filter(pk=self.pk).values("role", "is_active").first()
            if (
                previous
                and previous["role"] == self.Role.LEADER
                and previous["is_active"]
                and (self.role != self.Role.LEADER or not self.is_active)
            ):
                raise ValidationError("Die aktive Leitung kann nur atomar übertragen werden.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.group}: {self.user} ({self.get_role_display()})"


    def delete(self, *args, **kwargs):
        raise ValidationError("Gruppenrollen werden widerrufen und nicht physisch gelöscht.")


class GameGroupInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        ACCEPTED = "accepted", "Angenommen"
        DECLINED = "declined", "Abgelehnt"
        WITHDRAWN = "withdrawn", "Zurückgezogen"
        EXPIRED = "expired", "Abgelaufen"

    group = models.ForeignKey(
        GameGroup,
        on_delete=models.PROTECT,
        related_name="invitations",
    )
    character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.PROTECT,
        related_name="game_group_invitations",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_game_group_invitations",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True, default="", max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "character"],
                condition=Q(status="pending"),
                name="uniq_pending_group_character_invite",
            )
        ]

    def __str__(self):
        return f"{self.group} → {self.character}: {self.get_status_display()}"


class GameGroupMembership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        LEFT = "left", "Verlassen"
        REMOVED = "removed", "Entfernt"

    group = models.ForeignKey(
        GameGroup,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.PROTECT,
        related_name="game_group_memberships",
    )
    invitation = models.ForeignKey(
        GameGroupInvitation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="memberships",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["group", "character", "-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "character"],
                condition=Q(status="active"),
                name="uniq_active_group_character_member",
            )
        ]

    def clean(self):
        super().clean()
        if self.invitation_id and (
            self.invitation.group_id != self.group_id
            or self.invitation.character_id != self.character_id
        ):
            raise ValidationError({"invitation": "Die Einladung gehört nicht zu dieser Mitgliedschaft."})

    def __str__(self):
        return f"{self.group}: {self.character} ({self.get_status_display()})"
