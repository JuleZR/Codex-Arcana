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
    screen_note_html = models.TextField(blank=True, default="")
    screen_note_position = models.PositiveIntegerField(null=True, blank=True)
    screen_note_is_visible = models.BooleanField(default=True)
    screen_note_is_wide = models.BooleanField(default=False)
    screen_note_is_detached = models.BooleanField(default=False)
    screen_note_x = models.PositiveIntegerField(default=24)
    screen_note_y = models.PositiveIntegerField(default=24)
    screen_inventory_is_collapsed = models.BooleanField(default=False)

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
    screen_position = models.PositiveIntegerField(null=True, blank=True)
    screen_is_collapsed = models.BooleanField(default=False)
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


class GameGroupCreature(models.Model):
    """One independently placeable creature card on a game group's SL screen."""

    group = models.ForeignKey(
        GameGroup,
        on_delete=models.CASCADE,
        related_name="screen_creatures",
    )
    creature = models.ForeignKey(
        "charsheet.Creature",
        on_delete=models.PROTECT,
        related_name="game_group_screen_instances",
    )
    character_creature = models.ForeignKey(
        "charsheet.CharacterCreature",
        on_delete=models.CASCADE,
        related_name="game_group_screen_cards",
        null=True,
        blank=True,
    )
    screen_position = models.PositiveIntegerField(null=True, blank=True)
    screen_is_collapsed = models.BooleanField(default=False)
    current_stun_damage = models.PositiveIntegerField(default=0)
    current_lethal_damage = models.PositiveIntegerField(default=0)
    current_kp = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["group", "screen_position", "id"]

    def __str__(self):
        return f"{self.group}: {self.creature} (Karte {self.pk or 'neu'})"

    @property
    def current_damage(self) -> int:
        return int(self.current_stun_damage or 0) + int(
            self.current_lethal_damage or 0
        )

    def adjust_damage(
        self,
        *,
        damage_type: str,
        action: str,
        amount: int,
        stun_max: int,
    ) -> None:
        """Apply the same B/T damage and overflow rules as character cards."""
        amount = max(0, int(amount or 0))
        stun_max = max(0, int(stun_max or 0))
        if damage_type == "T":
            if action == "damage":
                self.current_lethal_damage += amount
            elif action == "heal":
                self.current_lethal_damage = max(
                    0,
                    self.current_lethal_damage - amount,
                )
            return
        if damage_type != "B":
            return
        if action == "heal":
            self.current_stun_damage = max(
                0,
                self.current_stun_damage - amount,
            )
            return
        if action != "damage" or amount == 0:
            return

        available_total = max(0, stun_max - self.current_damage)
        fill = min(amount, available_total)
        self.current_stun_damage += fill
        overflow_steps = amount - fill
        converted = min(overflow_steps, self.current_stun_damage)
        self.current_stun_damage -= converted
        self.current_lethal_damage += overflow_steps

    def adjust_kp(self, *, action: str, amount: int, maximum: int) -> None:
        """Spend or restore this screen card's KP within its current maximum."""
        amount = max(0, int(amount or 0))
        maximum = max(0, int(maximum or 0))
        current = maximum if self.current_kp is None else int(self.current_kp)
        current = max(0, min(maximum, current))
        if action == "spend":
            current = max(0, current - amount)
        elif action == "restore":
            current = min(maximum, current + amount)
        self.current_kp = current


class GameGroupTable(models.Model):
    """A freely configurable data table shown in a group's SL screen."""

    group = models.ForeignKey(
        GameGroup,
        on_delete=models.CASCADE,
        related_name="data_tables",
    )
    title = models.CharField(max_length=150)
    position = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.group}: {self.title}"


class GameGroupTableColumn(models.Model):
    table = models.ForeignKey(
        GameGroupTable,
        on_delete=models.CASCADE,
        related_name="columns",
    )
    heading = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["table", "position"],
                name="uniq_game_group_table_column_position",
            ),
        ]

    def __str__(self):
        return f"{self.table.title}: {self.heading}"


class GameGroupTableRow(models.Model):
    table = models.ForeignKey(
        GameGroupTable,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["table", "position"],
                name="uniq_game_group_table_row_position",
            ),
        ]

    def __str__(self):
        return f"{self.table.title}: Zeile {self.position + 1}"


class GameGroupTableCell(models.Model):
    class ValueType(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Zahl"

    class Alignment(models.TextChoices):
        LEFT = "left", "Linksbündig"
        CENTER = "center", "Zentriert"
        RIGHT = "right", "Rechtsbündig"

    row = models.ForeignKey(
        GameGroupTableRow,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    column = models.ForeignKey(
        GameGroupTableColumn,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    value_type = models.CharField(
        max_length=10,
        choices=ValueType.choices,
        default=ValueType.TEXT,
    )
    text_value = models.TextField(blank=True, default="")
    number_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    number_show_plus = models.BooleanField(default=False)
    number_suffix = models.CharField(max_length=100, blank=True, default="")
    alignment = models.CharField(
        max_length=6,
        choices=Alignment.choices,
        default=Alignment.LEFT,
    )
    row_span = models.PositiveSmallIntegerField(default=1)
    column_span = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["row__position", "column__position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["row", "column"],
                name="uniq_game_group_table_cell",
            ),
        ]

    def clean(self):
        super().clean()
        if self.row_id and self.column_id and self.row.table_id != self.column.table_id:
            raise ValidationError("Zeile und Spalte müssen zur selben Tabelle gehören.")
        if self.value_type == self.ValueType.NUMBER:
            self.text_value = ""
        else:
            self.number_value = None
            self.number_show_plus = False
            self.number_suffix = ""

    @property
    def value(self):
        return self.number_value if self.value_type == self.ValueType.NUMBER else self.text_value

    def __str__(self):
        return str(self.value)
