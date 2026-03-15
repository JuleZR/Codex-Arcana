"""Reference models shared across the character sheet domain."""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ..constants import ATTRIBUTE_CODE_CHOICES, GK_AVERAGE, GK_CHOICES, SKILL_CATEGORY_CHOICES


class Attribute(models.Model):
    """A base attribute that can be referenced by skills and character values."""

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=4, unique=True, choices=ATTRIBUTE_CODE_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.short_name})"


class SkillCategory(models.Model):
    """A grouping for skills that can also receive shared modifiers."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, choices=SKILL_CATEGORY_CHOICES)

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    """A learnable skill linked to one category and one governing attribute."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.ForeignKey(SkillCategory, on_delete=models.PROTECT)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    requires_specification = models.BooleanField(default=False)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class Race(models.Model):
    """Species template with movement and creation defaults."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    combat_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    march_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    sprint_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    swimming_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    can_fly = models.BooleanField(default=False)
    combat_fly_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)], null=True, blank=True)
    march_fly_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)], null=True, blank=True)
    sprint_fly_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)], null=True, blank=True)

    phase_1_points = models.PositiveIntegerField(default=40)
    phase_2_points = models.PositiveIntegerField(default=50)
    phase_3_points = models.PositiveIntegerField(default=20, validators=[MaxValueValidator(20)])
    phase_4_points = models.PositiveIntegerField(default=30)

    size_class = models.CharField(GK_CHOICES, max_length=5, default=GK_AVERAGE)

    def __str__(self):
        return self.name


class RaceAttributeLimit(models.Model):
    """Allowed minimum and maximum values for one race/attribute pair."""

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
        """Ensure the configured minimum does not exceed the maximum."""
        if self.min_value > self.max_value:
            raise ValidationError("min_value must be <= max_value")

    def __str__(self):
        return f"{self.race} - {self.attribute}: {self.min_value} to {self.max_value}"


class DamageSource(models.Model):
    """Damage type or source used by weapon definitions."""

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Trait(models.Model):
    """Advantage or disadvantage definition with level bounds."""

    class TraitType(models.TextChoices):
        ADV = "advantage", "Advantage"
        DIS = "disadvantage", "Disadvantage"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    trait_type = models.CharField(max_length=20, choices=TraitType.choices)
    description = models.TextField()

    min_level = models.PositiveIntegerField(default=1)
    max_level = models.PositiveIntegerField(default=1)
    points_per_level = models.PositiveIntegerField(default=1)

    def clean(self):
        """Keep configured trait level bounds consistent."""
        super().clean()
        if self.max_level < self.min_level:
            raise ValidationError("Max level < min level is prohibited.")

    def __str__(self):
        return self.name


class Language(models.Model):
    """Language definition with a configurable maximum mastery level."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    max_level = models.PositiveIntegerField(default=3)

    def __str__(self):
        return self.name
