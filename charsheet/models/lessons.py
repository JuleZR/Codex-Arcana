"""Lesson definitions, costs, prerequisites, and character ownership."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from charsheet.constants import SCHOOL_COMBAT


COMBAT_SCHOOL_TYPE_SLUGS = {SCHOOL_COMBAT, "school_combat"}


def _is_combat_school(school) -> bool:
    school_type = getattr(school, "type", None)
    if school_type is None:
        return False
    return str(getattr(school_type, "slug", "") or "") in COMBAT_SCHOOL_TYPE_SLUGS or str(
        getattr(school_type, "name", "") or ""
    ).casefold() == "kampfschule"


class Lesson(models.Model):
    """A school-bound lesson that can be bought during or after creation."""

    class ActivationType(models.TextChoices):
        ACTION = "action", "Aktion"
        SPONTANEOUS = "spontaneous", "Spontan"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    school = models.ForeignKey(
        "charsheet.School",
        on_delete=models.PROTECT,
        related_name="lessons",
    )
    technique = models.ForeignKey(
        "charsheet.Technique",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lessons",
        help_text="Technik dieser Kampfschule, die zum Erlernen der Lektion vorausgesetzt wird.",
    )
    description = models.TextField(blank=True, default="")
    fluff_quote = models.TextField(
        blank=True,
        default="",
        help_text="Optionales Fluff-Zitat, das in Tooltips und auf dem Charakterbogen angezeigt wird.",
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
        help_text="CP bei der Charaktererschaffung und EP beim späteren Lernen.",
    )

    class Meta:
        ordering = ["school__name", "name", "id"]

    def clean(self):
        super().clean()
        errors: dict[str, str] = {}
        if self.school_id and not _is_combat_school(self.school):
            errors["school"] = "Lektionen gehoeren zu einer Kampfschule."
        if not self.technique_id:
            errors["technique"] = "Eine Lektion benoetigt eine Technik ihrer Schule."
        elif self.school_id and self.technique.school_id != self.school_id:
            errors["technique"] = "Die Technik muss zur Schule der Lektion gehoeren."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.school.name}: {self.name}"


class LessonCost(models.Model):
    """One application cost; equal alternative groups form OR choices."""

    class Operator(models.TextChoices):
        AND = "and", "UND"
        OR = "or", "ODER"

    class CostType(models.TextChoices):
        ARCANE_POWER = "kp", "KP"
        LIFE_POINTS = "lp", "LP"
        EXPERIENCE = "ep", "EP"
        FAME = "fame", "Ruhmpunkt"
        CUSTOM = "custom", "Frei definiert"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="costs")
    cost_type = models.CharField(max_length=20, choices=CostType.choices)
    value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    operator = models.CharField(max_length=8, choices=Operator.choices, default=Operator.AND)
    custom_label = models.CharField(max_length=100, blank=True, default="")
    description = models.CharField(max_length=250, blank=True, default="")
    alternative_group = models.PositiveSmallIntegerField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["lesson__school__name", "lesson__name", "sort_order", "id"]

    def clean(self):
        super().clean()
        if self.cost_type == self.CostType.CUSTOM and not self.custom_label.strip():
            raise ValidationError({"custom_label": "Freie Kostenarten benötigen eine Bezeichnung."})
        if self.cost_type != self.CostType.CUSTOM and self.custom_label.strip():
            raise ValidationError({"custom_label": "Eine freie Bezeichnung ist nur für freie Kostenarten erlaubt."})

        if self.operator == self.Operator.AND and self.alternative_group is not None:
            raise ValidationError({"alternative_group": "UND-Kosten verwenden keine ODER-Gruppe."})
        if self.operator == self.Operator.OR and self.alternative_group is None:
            raise ValidationError({"alternative_group": "ODER-Kosten benoetigen eine ODER-Gruppe."})

    @property
    def type_label(self) -> str:
        if self.cost_type == self.CostType.CUSTOM:
            return self.custom_label.strip() or "Sonderkosten"
        return self.get_cost_type_display()

    def __str__(self) -> str:
        return f"{self.lesson.name}: {self.value} {self.type_label}"


class LessonRequirementGroup(models.Model):
    """One explicitly grouped boolean clause within a lesson requirement expression."""

    class Operator(models.TextChoices):
        AND = "and", "UND"
        OR = "or", "ODER"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="requirement_groups")
    number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    operator = models.CharField(max_length=8, choices=Operator.choices, default=Operator.AND)

    class Meta:
        ordering = ["lesson__school__name", "lesson__name", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "number"],
                name="uniq_lesson_requirement_group_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.lesson.name}: Gruppe {self.number} ({self.get_operator_display()})"


class LessonRequirement(models.Model):
    """One atomic lesson prerequisite, optionally assigned to a boolean group."""

    class RequirementType(models.TextChoices):
        SCHOOL = "school", "Schule"
        SKILL = "skill", "Fertigkeit"
        TECHNIQUE = "technique", "Technik"
        LESSON = "lesson", "Lektion"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="requirements")
    requirement_type = models.CharField(max_length=20, choices=RequirementType.choices)
    required_school = models.ForeignKey(
        "charsheet.School",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lesson_requirements",
    )
    required_skill = models.ForeignKey(
        "charsheet.Skill",
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
    required_lesson = models.ForeignKey(
        Lesson,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="required_by_requirements",
    )
    minimum_value = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    group = models.ForeignKey(
        LessonRequirementGroup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="requirements",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["lesson__school__name", "lesson__name", "sort_order", "id"]

    def _would_create_lesson_cycle(self) -> bool:
        if not self.lesson_id or not self.required_lesson_id:
            return False
        target_id = int(self.lesson_id)
        stack = [int(self.required_lesson_id)]
        visited: set[int] = set()
        while stack:
            current = stack.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(
                LessonRequirement.objects.filter(
                    lesson_id=current,
                    requirement_type=self.RequirementType.LESSON,
                    required_lesson_id__isnull=False,
                ).values_list("required_lesson_id", flat=True)
            )
        return False

    def clean(self):
        super().clean()
        targets = {
            self.RequirementType.SCHOOL: self.required_school_id,
            self.RequirementType.SKILL: self.required_skill_id,
            self.RequirementType.TECHNIQUE: self.required_technique_id,
            self.RequirementType.LESSON: self.required_lesson_id,
        }
        errors: dict[str, str] = {}
        if not targets.get(self.requirement_type):
            errors["requirement_type"] = "Für den gewählten Typ muss ein passendes Ziel gesetzt werden."
        if sum(value is not None for value in targets.values()) != 1:
            errors["requirement_type"] = "Eine Voraussetzung muss genau ein Ziel besitzen."
        needs_minimum = self.requirement_type in {self.RequirementType.SCHOOL, self.RequirementType.SKILL}
        if needs_minimum and self.minimum_value is None:
            errors["minimum_value"] = "Schul- und Fertigkeitsvoraussetzungen benötigen einen Mindestwert."
        if not needs_minimum and self.minimum_value is not None:
            errors["minimum_value"] = "Dieser Voraussetzungstyp verwendet keinen Mindestwert."
        if self.group_id and self.lesson_id and self.group.lesson_id != self.lesson_id:
            errors["group"] = "Die Bedingungsgruppe muss zur selben Lektion gehören."
        if self.required_lesson_id and self.required_lesson_id == self.lesson_id:
            errors["required_lesson"] = "Eine Lektion kann sich nicht selbst voraussetzen."
        elif self._would_create_lesson_cycle():
            errors["required_lesson"] = "Diese Voraussetzung erzeugt einen Lektionszyklus."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        from charsheet.lesson_rules import format_requirement

        return f"{self.lesson.name}: {format_requirement(self)}"


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
        ordering = ["character", "lesson__school__name", "lesson__name"]
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
        if self.acquisition_type == self.AcquisitionType.EXPERIENCE and self.paid_ep <= 0:
            raise ValidationError({"paid_ep": "Mit EP gelernte Lektionen benötigen gespeicherte Lernkosten."})
        if self.acquisition_type != self.AcquisitionType.EXPERIENCE and self.paid_ep:
            raise ValidationError({"paid_ep": "Nur mit EP gelernte Lektionen speichern erstattbare EP."})

    def __str__(self) -> str:
        return f"{self.character.name}: {self.lesson.name}"
