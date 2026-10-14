"""Editable reference scales and reusable attribute portrait rules."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from ..narrative_templates import validate_narrative


class FlavorRange(models.Model):
    min_value = models.IntegerField("Gilt ab Wert", null=True, blank=True)
    max_value = models.IntegerField("Gilt bis Wert", null=True, blank=True)
    narrative_template = models.TextField("Eigener Erzähltext", blank=True)
    neutral_template = models.TextField(
        "Neutraler Ersatztext",
        blank=True,
        help_text="Für fehlendes oder anderes Geschlecht; ohne Marker.",
    )
    source_reference = models.CharField(
        "Quellenangabe",
        max_length=255,
        blank=True,
    )
    priority = models.IntegerField("Priorität", default=0)
    active = models.BooleanField("Aktiv", default=True)

    class Meta:
        abstract = True
        ordering = ["-priority", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(min_value__isnull=True)
                | Q(max_value__isnull=True)
                | Q(min_value__lte=F("max_value")),
                name="%(class)s_valid_range",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            errors["max_value"] = (
                "Die Obergrenze muss mindestens der Untergrenze entsprechen."
            )
        for field in ("narrative_template", "neutral_template"):
            try:
                validate_narrative(
                    getattr(self, field),
                    neutral=field == "neutral_template",
                )
            except ValidationError as exc:
                errors[field] = exc.messages
        scope = {}
        if hasattr(self, "attribute_id"):
            scope["attribute_id"] = self.attribute_id
        overlaps = (
            type(self)
            .objects.exclude(pk=self.pk)
            .filter(
                active=True,
                priority=self.priority,
                **scope,
            )
        )
        if not isinstance(self, RaceAttributeFlavor):
            overlaps = overlaps.filter(min_value=self.min_value)
        if self.min_value is not None:
            overlaps = overlaps.filter(
                Q(max_value__isnull=True) | Q(max_value__gte=self.min_value),
            )
        if self.max_value is not None:
            overlaps = overlaps.filter(
                Q(min_value__isnull=True) | Q(min_value__lte=self.max_value),
            )
        if self.active and overlaps.exists():
            errors["priority"] = (
                "Mehrdeutige aktive Regeln benötigen verschiedene Prioritäten."
            )
        if errors:
            raise ValidationError(errors)

    def matches(self, value):
        return (self.min_value is None or self.min_value <= value) and (
            self.max_value is None or value <= self.max_value
        )

    def __str__(self):
        lower = f"ab {self.min_value}" if self.min_value is not None else ""
        upper = f"bis {self.max_value}" if self.max_value is not None else ""
        bounds = (
            " ".join(part for part in (lower, upper) if part) or "Alle Werte"
        )
        return f"{bounds} (Priorität {self.priority})"


class AttributeRating(FlavorRange):
    min_value = models.IntegerField("Gilt ab Wert")
    attribute = models.ForeignKey(
        "Attribute",
        on_delete=models.PROTECT,
        verbose_name="Eigenschaft",
    )
    official_designation = models.CharField(
        "Offizielle Bezeichnung",
        max_length=200,
        blank=True,
    )
    official_description = models.TextField(
        "Offizieller Referenztext",
        blank=True,
    )

    class Meta(FlavorRange.Meta):
        abstract = False
        ordering = ["-min_value", "-priority", "pk"]
        verbose_name = "Eigenschaftsbeschreibung"
        verbose_name_plural = "Eigenschaftsbeschreibungen"

    def clean(self):
        super().clean()
        if (
            self.official_designation or self.official_description
        ) and not self.source_reference:
            raise ValidationError(
                {
                    "source_reference": (
                        "Die offizielle Referenz benötigt eine Quelle."
                    )
                }
            )


class GeneralAttributeMeaning(FlavorRange):
    official_meaning = models.CharField(
        "Offizielle Bedeutung",
        max_length=200,
        blank=True,
    )

    class Meta(FlavorRange.Meta):
        abstract = False
        ordering = ["-min_value", "-priority", "pk"]
        verbose_name = "Allgemeine Eigenschaftsbedeutung"
        verbose_name_plural = "Allgemeine Eigenschaftsbedeutungen"

    def clean(self):
        super().clean()
        if self.official_meaning and not self.source_reference:
            raise ValidationError(
                {
                    "source_reference": (
                        "Die offizielle Bedeutung benötigt eine Quelle."
                    )
                }
            )


class RaceAttributeFlavor(FlavorRange):
    min_value = models.IntegerField(
        "Abstand mindestens",
        null=True,
        blank=True,
    )
    max_value = models.IntegerField(
        "Abstand höchstens",
        null=True,
        blank=True,
    )
    attribute = models.ForeignKey(
        "Attribute",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Eigenschaft (optional)",
    )

    class Meta(FlavorRange.Meta):
        abstract = False
        verbose_name = "Eigenschaft im Rassenvergleich"
        verbose_name_plural = "Eigenschaften im Rassenvergleich"

    def clean(self):
        super().clean()
        if not self.narrative_template:
            raise ValidationError(
                {"narrative_template": "Ein Vergleichstext ist erforderlich."}
            )
