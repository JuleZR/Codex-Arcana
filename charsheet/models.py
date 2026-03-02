from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Attribute(models.Model):
    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=4, unique=True)
    
    def __str__(self):
        return f"{self.name} ({self.short_name})"


class SkillCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    
    def __str__(self) -> str:
        return self.name

class Skill(models.Model):
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
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class RaceAttributeLimit(models.Model):
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
        if self.min_value > self.max_value:
            raise ValidationError("min_value must be <= max_value")

    def __str__(self):
        return f"{self.race} - {self.attribute}: {self.min_value} to {self.max_value}"


class Character(models.Model):
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
        from .engine.engine import CharacterEngine
        return CharacterEngine(self)
    
class CharacterAttribute(models.Model):
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
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class School(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    type = models.ForeignKey(SchoolType, on_delete=models.PROTECT)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CharacterSchool(models.Model):
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
    """
    Generic numeric modifier from an arbitrary source object (school/technique/race/...)
    to a target (skill or category).
    """

    # Source (generic)
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")

    # Target
    TARGET_SKILL = "skill"
    TARGET_CATEGORY = "category"
    TARGET_CHOICES = [
        (TARGET_SKILL, "Skill"),
        (TARGET_CATEGORY, "Category"),
    ]
    target_kind = models.CharField(max_length=30, choices=TARGET_CHOICES)
    target_slug = models.CharField(max_length=120)

    value = models.SmallIntegerField()

    # Optional condition: needs school level >= x (only meaningful if source is a School)
    min_school_level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["source_content_type", "source_object_id"]),
            models.Index(fields=["target_kind", "target_slug"]),
        ]

    def __str__(self) -> str:
        src = f"{self.source_content_type.model}:{self.source_object_id}"
        return f"{src} -> {self.value} to {self.target_kind} {self.target_slug}"
    
class Technique(models.Model):
    """
    A technique that can be learned through a school.
    Not every technique modifies numeric values (many are narrative/utility).
    """

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
    