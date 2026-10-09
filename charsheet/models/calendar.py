"""Configurable calendars; no calendar data is supplied by the application."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Value


def used_system_ids():
    parents = dict(
        CalendarSystem.objects.values_list("pk", "reference_system_id")
    )
    used = set()
    for system_id in CharacterDate.objects.values_list("system_id", flat=True):
        while system_id and system_id not in used:
            used.add(system_id)
            system_id = parents.get(system_id)
    return used


class CalendarDefinition(models.Model):
    name = models.CharField("Kalendername", max_length=120)
    months_per_year = models.PositiveIntegerField(
        default=12,
        validators=[MinValueValidator(1)],
        verbose_name="Anzahl der Monate",
    )
    days_per_year = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Tage pro Jahr",
        help_text="Reguläre Jahreslänge ohne zusätzliche Schalttage.",
    )

    class Meta:
        verbose_name = "Kalenderdefinition"
        verbose_name_plural = "Kalenderdefinitionen"

    def __str__(self):
        return self.name

    def is_used(self):
        return bool(
            self.pk and self.systems.filter(pk__in=used_system_ids()).exists()
        )

    def validate_structure(self):
        self.full_clean()
        months = list(self.months.select_related("season"))
        if len(months) != self.months_per_year:
            raise ValidationError(
                f"{len(months)} Monate sind angelegt; vorgesehen sind "
                f"{self.months_per_year} Monate."
            )
        if sum(month.days for month in months) != self.days_per_year:
            raise ValidationError(
                f"Die {len(months)} Monate umfassen zusammen "
                f"{sum(month.days for month in months)} Tage. Für dieses "
                f"Kalenderjahr sind jedoch {self.days_per_year} "
                "Tage festgelegt."
            )
        if len({month.sort_order for month in months}) != len(months):
            raise ValidationError("Monatspositionen müssen eindeutig sein.")
        if any(month.days < 1 for month in months):
            raise ValidationError("Monate benötigen mindestens einen Tag.")
        if any(
            month.sort_order < 1 or not month.name.strip() for month in months
        ):
            raise ValidationError("Ungültiger Monatsname oder Monatsposition.")
        for rule in self.leap_rules.all():
            rule.full_clean()
            for exception in rule.exceptions.all():
                exception.full_clean()
        return months

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CalendarSeason(models.Model):
    class Style(models.TextChoices):
        NEUTRAL = "neutral", "Arkanes Metall"
        SPRING = "spring", "Frühling – Blüten und Smaragd"
        SUMMER = "summer", "Sommer – Gold und Glut"
        AUTUMN = "autumn", "Herbst – Kupfer und Blätter"
        WINTER = "winter", "Winter – Silber und Schnee"

    name = models.CharField(max_length=80, unique=True)
    visual_style = models.CharField(
        "Erscheinungsbild des Kalenders",
        max_length=7,
        choices=Style.choices,
        default=Style.NEUTRAL,
        help_text="Die Monatszuordnung bestimmt, wann dieses Erscheinungsbild "
        "auf dem Charakterbogen verwendet wird.",
    )

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "Jahreszeit"
        verbose_name_plural = "Jahreszeiten"

    def __str__(self):
        return self.name


class CalendarMonth(models.Model):
    calendar = models.ForeignKey(
        CalendarDefinition,
        on_delete=models.CASCADE,
        related_name="months",
        verbose_name="Kalender",
    )
    name = models.CharField("Monatsname", max_length=80)
    season = models.ForeignKey(
        CalendarSeason,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="months",
        verbose_name="Jahreszeit",
    )
    days = models.PositiveIntegerField(
        "Anzahl der Tage",
        validators=[MinValueValidator(1)],
    )
    sort_order = models.PositiveIntegerField(
        "Reihenfolge",
        validators=[MinValueValidator(1)],
        help_text="Aufsteigende Position im Jahr; jede Position nur einmal.",
    )

    class Meta:
        verbose_name = "Monat"
        verbose_name_plural = "Monate"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=("calendar", "sort_order"),
                name="calendar_month_position",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.calendar.is_used():
            raise ValidationError(
                "Monate verwendeter Kalender können nicht gelöscht werden."
            )
        return super().delete(*args, **kwargs)


class CalendarLeapRule(models.Model):
    calendar = models.ForeignKey(
        CalendarDefinition,
        on_delete=models.CASCADE,
        related_name="leap_rules",
        verbose_name="Kalender",
    )
    month = models.ForeignKey(
        CalendarMonth,
        on_delete=models.PROTECT,
        verbose_name="Monat mit Schalttagen",
    )
    added_days = models.PositiveIntegerField(
        "Zusätzliche Tage",
        validators=[MinValueValidator(1)],
    )
    period = models.PositiveIntegerField(
        "Wiederholung alle X Jahre",
        validators=[MinValueValidator(1)],
    )
    offset = models.IntegerField(
        "Versatz der Schaltjahrregel",
        default=0,
        help_text="0: Jahre 0, X, 2X …; 1: Jahre 1, X+1, 2X+1 … "
        "Die Regel gilt ebenso für negative Jahre.",
    )

    class Meta:
        verbose_name = "Schaltjahrregel"
        verbose_name_plural = "Schaltjahrregeln"

    def __str__(self):
        return (
            f"{self.calendar}: alle {self.period} Jahre "
            f"{self.added_days} zusätzliche Tage im Monat {self.month}"
        )

    def clean(self):
        super().clean()
        if not self.calendar_id or not self.month_id:
            return
        if self.month_id and self.month.calendar_id != self.calendar_id:
            raise ValidationError(
                {"month": "Der Monat gehört zu einem anderen Kalender."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.calendar.is_used():
            raise ValidationError(
                "Die Schaltregeln dieses Kalenders sind gesperrt."
            )
        return super().delete(*args, **kwargs)


class CalendarLeapException(models.Model):
    class Effect(models.TextChoices):
        EXCLUDE = "exclude", "Schalttage entfallen"
        INCLUDE = "include", "Schalttage gelten trotzdem"

    rule = models.ForeignKey(
        CalendarLeapRule,
        on_delete=models.CASCADE,
        related_name="exceptions",
        verbose_name="Schaltjahrregel",
    )
    effect = models.CharField(
        "Wirkung",
        max_length=7,
        choices=Effect.choices,
        default=Effect.EXCLUDE,
        help_text="‚Gelten trotzdem‘ hat Vorrang vor ‚entfallen‘. "
        "Beide gelten nur in Jahren der Grundregel.",
    )
    period = models.PositiveIntegerField(
        "Wiederholung alle X Jahre",
        validators=[MinValueValidator(1)],
    )
    offset = models.IntegerField(
        "Versatz der Ausnahme",
        default=0,
        help_text="0: Jahre 0, X, 2X …; 1: Jahre 1, X+1, 2X+1 … "
        "Optional; auch negative Werte sind erlaubt.",
    )

    class Meta:
        verbose_name = "Ausnahme von der Schaltjahrregel"
        verbose_name_plural = "Ausnahmen von der Schaltjahrregel"

    def __str__(self):
        return f"Alle {self.period} Jahre: {self.get_effect_display()}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.rule.calendar.is_used():
            raise ValidationError(
                "Die Schaltausnahmen dieses Kalenders sind gesperrt."
            )
        return super().delete(*args, **kwargs)


class CalendarSystem(models.Model):
    name = models.CharField("Name der Zeitrechnung", max_length=120)
    abbreviation = models.CharField(
        "Kürzel", max_length=20, help_text="Darf mehrfach verwendet werden."
    )
    calendar_definition = models.ForeignKey(
        CalendarDefinition,
        on_delete=models.PROTECT,
        related_name="systems",
        verbose_name="Verwendeter Kalender",
        help_text="Legt fest, wie viele Monate und Tage ein Jahr besitzt.",
    )
    reference_system = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="referencing_systems",
        verbose_name="Bezugszeitrechnung",
        help_text="Legt fest, auf welche andere Zeitrechnung sich diese "
        "Zeitrechnung bezieht. Leer: Ausgangszeitrechnung.",
    )
    anchor_year = models.BigIntegerField("Jahr", default=0)
    anchor_month = models.PositiveIntegerField("Monat", default=1)
    anchor_day = models.PositiveIntegerField("Tag", default=1)
    reference_year = models.BigIntegerField("Jahr", default=0)
    reference_month = models.PositiveIntegerField("Monat", default=1)
    reference_day = models.PositiveIntegerField("Tag", default=1)
    # Existing roots used local day zero regardless of their anchor fields.
    # Keeping this value separate preserves their historical day axis.
    root_origin_day = models.BigIntegerField(default=0, editable=False)
    default_for_characters = models.BooleanField(
        "Standardzeitrechnung für neue Charakterdaten",
        default=False,
        help_text="Wird bei der erstmaligen Datumsinitialisierung verwendet. "
        "Ohne Auswahl wird die Ausgangszeitrechnung verwendet.",
    )
    real_date_reference = models.BooleanField(
        "Gregorianische Bezugszeitrechnung für das reale Datum",
        default=False,
        help_text="Nur für einen vollständig gregorianisch konfigurierten "
        "Kalender. Ermöglicht die einmalige Übernahme des heutigen "
        "Datums; bestehende Charakterdaten laufen nicht automatisch weiter.",
    )

    class Meta:
        verbose_name = "Zeitrechnung"
        verbose_name_plural = "Zeitrechnungen"
        ordering = ("name", "pk")
        constraints = [
            models.UniqueConstraint(
                Value(1),
                condition=Q(reference_system__isnull=True),
                name="single_calendar_timeline_root",
            ),
            models.UniqueConstraint(
                Value(1),
                condition=Q(default_for_characters=True),
                name="single_character_default_calendar",
            ),
            models.UniqueConstraint(
                Value(1),
                condition=Q(real_date_reference=True),
                name="single_real_date_calendar",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        from charsheet.engine.calendar_engine import CalendarEngine

        dates = (
            self.anchor_year,
            self.anchor_month,
            self.anchor_day,
            self.reference_year,
            self.reference_month,
            self.reference_day,
        )
        if not self.calendar_definition_id or any(
            value is None for value in dates
        ):
            return
        seen = {self.pk} if self.pk else set()
        reference = self.reference_system
        while reference:
            if reference.pk in seen:
                raise ValidationError(
                    {
                        "reference_system": (
                            "Diese Zeitrechnung kann nicht auf sich selbst "
                            "verweisen."
                            if reference.pk == self.pk
                            and reference == self.reference_system
                            else "Die gewählte Bezugszeitrechnung würde einen "
                            "ungültigen Verweiskreis erzeugen."
                        )
                    }
                )
            seen.add(reference.pk)
            reference = reference.reference_system
        engine = CalendarEngine()
        if self.real_date_reference:
            engine.validate_real_date_calendar(self.calendar_definition)
        own_day = engine.local_day(
            self.calendar_definition,
            self.anchor_year,
            self.anchor_month,
            self.anchor_day,
        )
        if self.reference_system:
            engine.to_absolute(
                self.reference_system,
                self.reference_year,
                self.reference_month,
                self.reference_day,
            )
        elif (
            CalendarSystem.objects.filter(reference_system=None)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                "Es kann nur eine Ausgangszeitrechnung geben."
            )
        else:
            self.root_origin_day = own_day

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CharacterDate(models.Model):
    character = models.OneToOneField(
        "Character",
        on_delete=models.CASCADE,
        related_name="calendar_date",
    )
    system = models.ForeignKey(CalendarSystem, on_delete=models.PROTECT)
    absolute_day = models.BigIntegerField()

    def clean(self):
        super().clean()
        from charsheet.engine.calendar_engine import CalendarEngine

        if not self.system_id or self.absolute_day is None:
            return
        CalendarEngine().from_absolute(self.system, self.absolute_day)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
