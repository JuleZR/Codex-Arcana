"""Lesson definitions, costs, prerequisites, and character ownership."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from charsheet.constants import SCHOOL_ARCANE, SCHOOL_COMBAT

COMBAT_SCHOOL_TYPE_SLUGS = {SCHOOL_COMBAT, "school_combat"}


def _is_combat_school(school) -> bool:
    school_type = getattr(school, "type", None)
    if school_type is None:
        return False
    return (
        str(getattr(school_type, "slug", "") or "") in COMBAT_SCHOOL_TYPE_SLUGS
        or str(getattr(school_type, "name", "") or "").casefold()
        == "kampfschule"
    )


class Lesson(models.Model):
    """A lesson that can be bought during or after creation."""

    class ActivationType(models.TextChoices):
        ACTION = "action", "Aktion"
        SPONTANEOUS = "spontaneous", "Spontan"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    fluff_quote = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Optionales Fluff-Zitat, das in Tooltips und auf dem "
            "Charakterbogen angezeigt wird."
        ),
    )
    fluff_quote_speaker = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optionale Person oder Quelle des Fluff-Zitats.",
    )
    source_reference = models.CharField(
        max_length=250,
        blank=True,
        default="",
        verbose_name="Herkunft",
        help_text="Optional: Buch und Seite, z. B. 'Grundregelwerk, S. 285'.",
    )
    activation_type = models.CharField(
        max_length=20,
        choices=ActivationType.choices,
        default=ActivationType.ACTION,
    )
    purchase_cost = models.PositiveSmallIntegerField(
        default=8,
        validators=[MinValueValidator(1)],
        help_text=(
            "CP bei der Charaktererschaffung und EP beim späteren Lernen."
        ),
    )

    class Meta:
        ordering = ["name", "id"]

    def requirements_satisfied_by(self, character, *, context=None):
        from charsheet.lesson_rules import lesson_requirements_met

        return lesson_requirements_met(
            self, character=character, context=context
        )

    def __str__(self) -> str:
        return self.name


class LessonCost(models.Model):
    """One cost in an AND package; distinct packages are OR alternatives."""

    class CostType(models.TextChoices):
        ARCANE_POWER = "kp", "KP"
        LIFE_POINTS = "lp", "LP"
        EXPERIENCE = "ep", "EP"
        FAME = "fame", "Ruhmpunkt"
        CUSTOM = "custom", "Frei definiert"

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="costs"
    )
    cost_type = models.CharField(max_length=20, choices=CostType.choices)
    value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    custom_label = models.CharField(max_length=100, blank=True, default="")
    description = models.CharField(max_length=250, blank=True, default="")
    cost_group = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text=(
            "Kosten derselben Gruppe gelten gemeinsam (UND). "
            "Verschiedene Gruppen sind Alternativen (ODER)."
        ),
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["lesson__name", "sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cost_group__gte=1),
                name="lesson_cost_group_gte_1",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.cost_type == self.CostType.CUSTOM
            and not self.custom_label.strip()
        ):
            raise ValidationError(
                {
                    "custom_label": (
                        "Freie Kostenarten benötigen eine Bezeichnung."
                    )
                }
            )
        if (
            self.cost_type != self.CostType.CUSTOM
            and self.custom_label.strip()
        ):
            raise ValidationError(
                {
                    "custom_label": (
                        "Eine freie Bezeichnung ist nur für freie "
                        "Kostenarten erlaubt."
                    )
                }
            )

    @property
    def type_label(self) -> str:
        if self.cost_type == self.CostType.CUSTOM:
            return self.custom_label.strip() or "Sonderkosten"
        return self.get_cost_type_display()

    def __str__(self) -> str:
        return f"{self.lesson.name}: {self.value} {self.type_label}"


class LessonRequirement(models.Model):
    """One mandatory prerequisite for acquiring a lesson."""

    class RequirementType(models.TextChoices):
        SCHOOL_TECHNIQUE = "school_technique", "School + Technique"
        SCHOOL_SPECIALISATION = (
            "school_specialisation",
            "School + Specialisation",
        )
        MAGIC_SCHOOL_LEVEL = "magic_school_level", "Magic School"
        CLERICAL_MAGIC_LEVEL = "clerical_magic_level", "Clerical Magic"
        DRUID_CIRCLE_LEVEL = "druid_circle_level", "Druid Circle"
        SPECIFIC_CREATURE = "specific_creature", "Creature"

    TYPE_FIELDS = {
        RequirementType.SCHOOL_TECHNIQUE: (
            "required_school",
            "required_technique",
        ),
        RequirementType.SCHOOL_SPECIALISATION: (
            "required_school",
            "specialisation",
        ),
        RequirementType.MAGIC_SCHOOL_LEVEL: ("magic_school", "minimum_value"),
        RequirementType.CLERICAL_MAGIC_LEVEL: ("minimum_value",),
        RequirementType.DRUID_CIRCLE_LEVEL: ("druid_circle", "minimum_value"),
        RequirementType.SPECIFIC_CREATURE: ("creature",),
    }
    TARGET_FIELDS = (
        "required_school",
        "required_technique",
        "specialisation",
        "magic_school",
        "druid_circle",
        "creature",
        "minimum_value",
    )

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="requirements"
    )
    requirement_type = models.CharField(
        max_length=24, choices=RequirementType.choices
    )
    required_school = models.ForeignKey(
        "charsheet.School",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lesson_requirements",
    )
    required_technique = models.ForeignKey(
        "charsheet.Technique",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lesson_requirements",
    )
    specialisation = models.ForeignKey(
        "charsheet.Specialization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lesson_requirements",
    )
    magic_school = models.ForeignKey(
        "charsheet.School",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="magic_lesson_requirements",
    )
    druid_circle = models.ForeignKey(
        "charsheet.DruidCult",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lesson_requirements",
    )
    creature = models.ForeignKey(
        "charsheet.Creature",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lesson_requirements",
    )
    minimum_value = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Level",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        requirement_type="school_technique",
                        required_school__isnull=False,
                        required_technique__isnull=False,
                        specialisation__isnull=True,
                        magic_school__isnull=True,
                        druid_circle__isnull=True,
                        creature__isnull=True,
                        minimum_value__isnull=True,
                    )
                    | models.Q(
                        requirement_type="school_specialisation",
                        required_school__isnull=False,
                        required_technique__isnull=True,
                        specialisation__isnull=False,
                        magic_school__isnull=True,
                        druid_circle__isnull=True,
                        creature__isnull=True,
                        minimum_value__isnull=True,
                    )
                    | models.Q(
                        requirement_type="magic_school_level",
                        required_school__isnull=True,
                        required_technique__isnull=True,
                        specialisation__isnull=True,
                        magic_school__isnull=False,
                        druid_circle__isnull=True,
                        creature__isnull=True,
                        minimum_value__isnull=False,
                        minimum_value__gte=1,
                    )
                    | models.Q(
                        requirement_type="clerical_magic_level",
                        required_school__isnull=True,
                        required_technique__isnull=True,
                        specialisation__isnull=True,
                        magic_school__isnull=True,
                        druid_circle__isnull=True,
                        creature__isnull=True,
                        minimum_value__isnull=False,
                        minimum_value__gte=1,
                    )
                    | models.Q(
                        requirement_type="druid_circle_level",
                        required_school__isnull=True,
                        required_technique__isnull=True,
                        specialisation__isnull=True,
                        magic_school__isnull=True,
                        druid_circle__isnull=False,
                        creature__isnull=True,
                        minimum_value__isnull=False,
                        minimum_value__gte=1,
                    )
                    | models.Q(
                        requirement_type="specific_creature",
                        required_school__isnull=True,
                        required_technique__isnull=True,
                        specialisation__isnull=True,
                        magic_school__isnull=True,
                        druid_circle__isnull=True,
                        creature__isnull=False,
                        minimum_value__isnull=True,
                    )
                ),
                name="lesson_requirement_valid_fields",
            ),
        ]

    def clean(self):
        super().clean()
        required = self.TYPE_FIELDS.get(self.requirement_type)
        if required is None:
            raise ValidationError(
                {"requirement_type": "Unbekannter Voraussetzungstyp."}
            )
        errors = {}
        for field in self.TARGET_FIELDS:
            value = getattr(
                self, field if field == "minimum_value" else f"{field}_id"
            )
            if field in required and value is None:
                errors[field] = (
                    "Dieses Feld ist für den gewählten Typ erforderlich."
                )
            elif field not in required and value is not None:
                errors[field] = (
                    "Dieses Feld ist für den gewählten Typ nicht erlaubt."
                )
        if self.required_school_id and not _is_combat_school(
            self.required_school
        ):
            errors["required_school"] = "Eine Kampfschule ist erforderlich."
        if (
            self.required_technique_id
            and self.required_technique.school_id != self.required_school_id
        ):
            errors["required_technique"] = (
                "Die Technik muss zur gewählten Schule gehören."
            )
        if (
            self.specialisation_id
            and self.specialisation.school_id != self.required_school_id
        ):
            errors["specialisation"] = (
                "Die Spezialisierung muss zur gewählten Schule gehören."
            )
        if self.magic_school_id and not is_arcane_lesson_school(
            self.magic_school
        ):
            errors["magic_school"] = (
                "Eine arkane Magieschule ist erforderlich."
            )
        if self.druid_circle_id and not self.druid_circle.school_id:
            errors["druid_circle"] = (
                "Der Druidenzirkel benötigt eine Schulzuordnung."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def is_satisfied_by(self, character, *, context=None):
        from charsheet.lesson_rules import requirement_met

        return requirement_met(self, character=character, context=context)

    def __str__(self) -> str:
        from charsheet.lesson_rules import format_requirement

        return format_requirement(self)


def is_arcane_lesson_school(school):
    """Use existing magic classification, excluding clerical progressions."""
    from charsheet.engine.magic_engine import MagicEngine
    from charsheet.religion_rules import is_clerical_school

    return MagicEngine._school_matches_magic_type(
        school, SCHOOL_ARCANE
    ) and not is_clerical_school(school)


class CharacterLesson(models.Model):
    """One lesson owned by a character, including acquisition provenance."""

    class AcquisitionType(models.TextChoices):
        CREATION = "creation", "Charaktererschaffung"
        EXPERIENCE = "experience", "Mit EP gelernt"
        MANUAL = "manual", "Manuell vergeben"

    character = models.ForeignKey(
        "charsheet.Character",
        on_delete=models.CASCADE,
        related_name="learned_lessons",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.PROTECT,
        related_name="character_entries",
    )
    acquisition_type = models.CharField(
        max_length=20,
        choices=AcquisitionType.choices,
        default=AcquisitionType.MANUAL,
    )
    paid_ep = models.PositiveIntegerField(default=0)
    learned_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["character", "lesson__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "lesson"],
                name="uniq_character_lesson",
            ),
        ]

    @property
    def can_unlearn(self) -> bool:
        return self.acquisition_type == self.AcquisitionType.EXPERIENCE

    def clean(self):
        super().clean()
        if (
            self.acquisition_type == self.AcquisitionType.EXPERIENCE
            and self.paid_ep <= 0
        ):
            raise ValidationError(
                {
                    "paid_ep": (
                        "Mit EP gelernte Lektionen benötigen "
                        "gespeicherte Lernkosten."
                    )
                }
            )
        if (
            self.acquisition_type != self.AcquisitionType.EXPERIENCE
            and self.paid_ep
        ):
            raise ValidationError(
                {
                    "paid_ep": (
                        "Nur mit EP gelernte Lektionen speichern "
                        "erstattbare EP."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.character.name}: {self.lesson.name}"
