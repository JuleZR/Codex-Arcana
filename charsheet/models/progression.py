"""School, specialization, and progression models."""

from django.core.exceptions import ValidationError
from django.db import models

from ..constants import SCHOOL_TYPE_CHOICES


class SchoolType(models.Model):
    """High-level classification for schools used by progression rules."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, choices=SCHOOL_TYPE_CHOICES)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class School(models.Model):
    """A combat school or similar progression track."""

    name = models.CharField(max_length=100, unique=True)
    type = models.ForeignKey(SchoolType, on_delete=models.PROTECT)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["type__name", "name"]

    def __str__(self):
        return self.name


class CharacterSchool(models.Model):
    """The learned level of a specific school for one character."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="schools")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="character_entries")
    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["character", "school__type__name", "school__name"]
        constraints = [
            models.UniqueConstraint(fields=["character", "school"], name="uniq_character_school")
        ]

    def __str__(self) -> str:
        return f"{self.character.name} - {self.school.name} (L{self.level})"


class SchoolPath(models.Model):
    """A specialization path that belongs to one school."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="paths")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["school__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_school_path_name")
        ]

    def __str__(self) -> str:
        return f"{self.school.name}: {self.name}"


class CharacterSchoolPath(models.Model):
    """The selected specialization path of a character within a school."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="selected_school_paths")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="character_path_choices")
    path = models.ForeignKey(SchoolPath, on_delete=models.PROTECT, related_name="character_choices")

    class Meta:
        ordering = ["character", "school__type__name", "school__name"]
        constraints = [
            models.UniqueConstraint(fields=["character", "school"], name="uniq_character_school_path")
        ]

    def clean(self):
        """Validate school ownership and that the character knows the school."""
        super().clean()
        if self.path_id and self.school_id and self.path.school_id != self.school_id:
            raise ValidationError({"path": "The selected path must belong to the selected school."})
        if self.character_id and self.school_id and not CharacterSchool.objects.filter(
            character_id=self.character_id,
            school_id=self.school_id,
        ).exists():
            raise ValidationError({"school": "A character can only choose a path for a learned school."})

    def __str__(self) -> str:
        return f"{self.character.name} - {self.school.name}: {self.path.name}"


class Specialization(models.Model):
    """A generic school-bound specialization definition."""

    class SupportLevel(models.TextChoices):
        """Describe how fully the engine can resolve a specialization's rules."""

        COMPUTED = "computed", "Automated"
        STRUCTURED = "structured", "Partially Automated"
        DESCRIPTIVE = "descriptive", "Manual (Rule Text Only)"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="specializations")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    support_level = models.CharField(
        max_length=20,
        choices=SupportLevel.choices,
        default=SupportLevel.STRUCTURED,
        help_text="How far the engine can resolve this specialization beyond basic status tracking.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["school__name", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "slug"], name="uniq_specialization_school_slug"),
        ]

    def __str__(self) -> str:
        return f"{self.school.name}: {self.name}"


class CharacterSpecialization(models.Model):
    """A specialization selected by a character for one learned school."""

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="learned_specializations",
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        related_name="character_specializations",
    )
    source_technique = models.ForeignKey(
        "Technique",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_specializations",
    )
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = [
            "character",
            "specialization__school__name",
            "specialization__sort_order",
            "specialization__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "specialization"],
                name="uniq_character_specialization",
            ),
        ]

    def clean(self):
        """Validate school ownership and an optional source-technique school match."""
        super().clean()
        if (
            self.character_id
            and self.specialization_id
            and not CharacterSchool.objects.filter(
                character_id=self.character_id,
                school_id=self.specialization.school_id,
            ).exists()
        ):
            raise ValidationError(
                {"specialization": "A character can only choose specializations from learned schools."}
            )
        if (
            self.source_technique_id
            and self.specialization_id
            and self.source_technique.school_id != self.specialization.school_id
        ):
            raise ValidationError(
                {"source_technique": "The source technique must belong to the same school as the specialization."}
            )

    def __str__(self) -> str:
        return f"{self.character.name} - {self.specialization.school.name}: {self.specialization.name}"


class ProgressionRule(models.Model):
    """Rule-based grants that unlock from school type and minimum level."""

    school_type = models.ForeignKey(SchoolType, on_delete=models.CASCADE)
    min_level = models.PositiveBigIntegerField(default=1)
    grant_kind = models.CharField(
        max_length=30,
        choices=[
            ("technique_choice", "Technique Choice"),
            ("spell_choice", "Spell Choice"),
            ("aspect_access", "Aspect Access"),
            ("aspect_spell", "Aspect Spell"),
        ],
    )
    amount = models.PositiveBigIntegerField(default=1)
    params = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["school_type", "min_level", "grant_kind", "id"]

    def __str__(self):
        return f"{self.school_type} level {self.min_level}+ grants {self.amount} {self.grant_kind}"
