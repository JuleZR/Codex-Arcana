from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Attribute(models.Model):
    """Primary character attribute with a human-readable and short code."""

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=4, unique=True)
    
    def __str__(self):
        return f"{self.name} ({self.short_name})"


class SkillCategory(models.Model):
    """Top-level grouping for related skills."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    
    def __str__(self) -> str:
        return self.name

class Skill(models.Model):
    """Character skill tied to one category and one governing attribute."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.ForeignKey(SkillCategory, on_delete=models.PROTECT)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class Race(models.Model):
    """Playable race entry used for character creation and constraints."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class RaceAttributeLimit(models.Model):
    """Per-race minimum and maximum values for one attribute."""

    race = models.ForeignKey(Race, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    min_value = models.IntegerField()
    max_value = models.IntegerField()
    
    class Meta:
        ordering = ["race", "attribute"]
        constraints = [
            models.UniqueConstraint(fields=["race", "attribute"], name="uniq_race_attribute_limit")
        ]

    def clean(self):
        """Validate that configured bounds are logically ordered.

        Raises:
            ValidationError: If ``min_value`` is greater than ``max_value``.
        """
        if self.min_value > self.max_value:
            raise ValidationError("min_value must be <= max_value")

    def __str__(self):
        return f"{self.race} - {self.attribute}: {self.min_value} to {self.max_value}"


class Character(models.Model):
    """Player-owned character with race and derived rule engine access."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    race = models.ForeignKey(Race, on_delete=models.PROTECT)
    
    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="uniq_character_owner_name")
        ]

    def __str__(self):
        return f"{self.name} ({self.race.name})"
    
    @property
    def engine(self):
        """Build a transient rule engine for this character instance.

        Returns:
            CharacterEngine: Rule calculation helper bound to this character.
        """
        from .engine.engine import CharacterEngine
        return CharacterEngine(self)
    
class CharacterAttribute(models.Model):
    """Stored base value for one character attribute pair."""

    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    base_value = models.IntegerField()

    class Meta:
        ordering = ["character", "attribute"]
        constraints = [
            models.UniqueConstraint(fields=["character", "attribute"], name="uniq_character_attribute")
        ]

    def __str__(self):
        return f"{self.character} - {self.attribute}: {self.base_value}"


class CharacterSkill(models.Model):
    """Stored level value for one character skill pair."""

    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])

    class Meta:
        ordering = ["character", "skill"]
        constraints = [
            models.UniqueConstraint(fields=["character", "skill"], name="uniq_character_skill")
        ]

    def __str__(self):
        return f"{self.character} learned {self.skill}: {self.level}"


class SchoolType(models.Model):
    """Domain grouping for schools and progression rule definitions."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class School(models.Model):
    """Trainable school assigned to a school type."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    type = models.ForeignKey(SchoolType, on_delete=models.PROTECT)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CharacterSchool(models.Model):
    """Character membership and level within one school."""

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="schools",
    )

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="character_entries",
    )

    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character", "school"],
                name="uniq_character_school"
            )
        ]

    def __str__(self) -> str:
        return f"{self.character.name} – {self.school.slug} (L{self.level})"


class ProgressionRule(models.Model):
    """Level-based reward rule for a school type."""

    school_type = models.ForeignKey(SchoolType, on_delete=models.CASCADE)
    min_level = models.PositiveBigIntegerField(default=1)
    grant_kind = models.CharField(max_length=30, choices=[
        ("technique_choice", "Technique Choice"),
        ("spell_choice", "Spell Choice"),
        ("aspect_access", "Aspect Access"),
        ("aspect_spell", "Aspect Spell")
        ]
    )
    amount = models.PositiveBigIntegerField(default=1)
    params = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.school_type} level {self.min_level}+ grants {self.amount} {self.grant_kind}"
    
class Modifier(models.Model):
    """Generic modifier resolved from a source model to a target token."""

    class TargetKind(models.TextChoices):
        SKILL = "skill", "Skill"
        CATEGORY = "category", "Category"
        STAT = "stat", "Stat"

    class Mode(models.TextChoices):
        FLAT = "flat", "Flat"
        SCALED = "scaled", "Scaled"

    class ScaleSource(models.TextChoices):
        SCHOOL_LEVEL = "school_level", "School level"
        # später:
        FAME_TOTAL = "fame_total", "Fame total"

    class RoundMode(models.TextChoices):
        FLOOR = "floor", "Floor"
        CEIL = "ceil", "Ceil"

    class CapMode(models.TextChoices):
        NONE = "none", "None"
        MIN = "min", "Min"
        MAX = "max", "Max"

    # Source (generic)
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")

    # Target
    target_kind = models.CharField(max_length=30, choices=TargetKind.choices)
    target_slug = models.CharField(max_length=120)

    # Value / Scaling
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.FLAT)

    value = models.SmallIntegerField(default=0)  # für FLAT

    scale_source = models.CharField(
        max_length=30,
        choices=ScaleSource.choices,
        null=True,
        blank=True,
    )
    scale_school = models.ForeignKey(
        "School",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="scale_modifiers",
        help_text="Only used if scale_source == school_level",
    )
    mul = models.SmallIntegerField(default=1)
    div = models.PositiveSmallIntegerField(default=1)
    round_mode = models.CharField(max_length=10, choices=RoundMode.choices, default=RoundMode.FLOOR)

    cap_mode = models.CharField(max_length=10, choices=CapMode.choices, default=CapMode.NONE)
    cap_source = models.CharField(
        max_length=30,
        choices=ScaleSource.choices,
        null=True,
        blank=True,
    )

    min_school_level = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.source} → {self.target_kind}:{self.target_slug}"

class Technique(models.Model):
    """Technique learned through a school at a required school level."""

    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="techniques",
    )

    level = models.PositiveSmallIntegerField()

    description = models.TextField(blank=True, default="")  # Regel-/Flufftext, z.B. "Der Schwur"

    class Meta:
        ordering = ["school__name", "level", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "level", "name"], name="uniq_technique_school_level_name"),
        ]

    def __str__(self) -> str:
        return f"{self.school.slug} L{self.level}: {self.name}"
    
