"""Database models for characters, progression, and modifiers."""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from .constants import *

class Attribute(models.Model):
    """Primary character attribute with a human-readable and short code."""

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=4, unique=True, choices=ATTRIBUTE_CODE_CHOICES)
    
    def __str__(self):
        return f"{self.name} ({self.short_name})"


class SkillCategory(models.Model):
    """Top-level grouping for related skills."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, choices=SKILL_CATEGORY_CHOICES)
    
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
        """Default ordering for skill listings."""

        ordering = ['category', 'name']

    def __str__(self):
        return self.name

class Race(models.Model):
    """Playable race entry used for character creation and constraints."""

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
    
    
    def __str__(self):
        return self.name

class RaceAttributeLimit(models.Model):
    """Per-race minimum and maximum values for one attribute."""

    race = models.ForeignKey(Race, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    min_value = models.IntegerField()
    max_value = models.IntegerField()
    
    class Meta:
        """Enforce one limit tuple per race/attribute pair."""

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
    class Gender(models.TextChoices):
        """Allowed gender values for character profiles."""
        M = "männlich", "Männlich"
        W = "weiblich", "Weiblich"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    race = models.ForeignKey(Race, on_delete=models.PROTECT)
    gender = models.CharField(max_length=15, choices=Gender, null=True, blank=True)
    age = models.PositiveIntegerField(default=20, null=True, blank=True)
    height = models.IntegerField(default=170)
    # TODO: Race depending height class
    # TODO: height class mod (?)
    skin_color = models.CharField(max_length=25, null=True, blank=True)
    hair_color = models.CharField(max_length=25, null=True, blank=True)
    eye_color = models.CharField(max_length=25, null=True, blank=True)
    country_of_origin = models.CharField(max_length=25, null=True, blank=True)
    weight = models.IntegerField(default=60, null=True, blank=True)
    religion = models.CharField(max_length=25, null=True, blank=True)
    appearance = models.TextField(max_length=85, null=True, blank=True)
    
    money = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    overall_experience = models.PositiveIntegerField(default=0)
    current_experience = models.PositiveIntegerField(default=0)
    
    current_damage = models.PositiveBigIntegerField(default=0)
    
    class Meta:
        """Set stable ordering and owner/name uniqueness."""

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
        """Prevent duplicate attribute rows per character."""

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
        """Prevent duplicate skill rows per character."""

        ordering = ["character", "skill"]
        constraints = [
            models.UniqueConstraint(fields=["character", "skill"], name="uniq_character_skill")
        ]

    def __str__(self):
        return f"{self.character} learned {self.skill}: {self.level}"

class SchoolType(models.Model):
    """Domain grouping for schools and progression rule definitions."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, choices=SCHOOL_TYPE_CHOICES)

    def __str__(self):
        return self.name

class School(models.Model):
    """Trainable school assigned to a school type."""

    name = models.CharField(max_length=100, unique=True)
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
        """Ensure one entry per character and school."""

        constraints = [
            models.UniqueConstraint(
                fields=["character", "school"],
                name="uniq_character_school"
            )
        ]

    def __str__(self) -> str:
        return f"{self.character.name} - {self.school.name} (L{self.level})"

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
        """Supported modifier targets."""
        SKILL = "skill", "Skill"
        CATEGORY = "category", "Category"
        STAT = "stat", "Stat"

    class Mode(models.TextChoices):
        """Supported modifier calculation modes."""
        FLAT = "flat", "Flat"
        SCALED = "scaled", "Scaled"

    class ScaleSource(models.TextChoices):
        """Available scaling source definitions."""
        SCHOOL_LEVEL = "school_level", "School level"
        FAME_TOTAL = "fame_total", "Fame total"
        TRAIT_LVL = "trait_level", "Trait Level"

    class RoundMode(models.TextChoices):
        """Rounding modes for scaled modifier values."""
        FLOOR = "floor", "Floor"
        CEIL = "ceil", "Ceil"

    class CapMode(models.TextChoices):
        """Capping strategies for scaled modifier values."""
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

    value = models.SmallIntegerField(default=0)  # fÃ¼r FLAT

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
    div = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    round_mode = models.CharField(max_length=10, choices=RoundMode.choices, default=RoundMode.FLOOR)

    cap_mode = models.CharField(max_length=10, choices=CapMode.choices, default=CapMode.NONE)
    cap_source = models.CharField(
        max_length=30,
        choices=ScaleSource.choices,
        null=True,
        blank=True,
    )

    min_school_level = models.PositiveSmallIntegerField(null=True, blank=True)
    def clean(self):
        """Validate target references and mode-dependent scaling configuration."""
        super().clean()
        if self.target_kind == self.TargetKind.STAT:
            if self.target_slug not in VALID_STAT_SLUGS:
                raise ValidationError(
                    {"target_slug": "Invalid target slug for kind STAT"}
                )
        elif self.target_kind == self.TargetKind.SKILL:
            if not Skill.objects.filter(slug=self.target_slug).exists():
                raise ValidationError(
                    {"target_slug": "Invalid target slug for kind SKILL. Slug in skill slugs not found."}
                )
        elif self.target_kind == self.TargetKind.CATEGORY:
            if not SkillCategory.objects.filter(slug=self.target_slug).exists():
                raise ValidationError(
                    {"target_slug": "Invalid target slug for kind CATEGORY. Slug in skill category slugs not found."}
                )
                
        if self.mode == self.Mode.FLAT and self.scale_source:
            raise ValidationError (
                {"scale_source": "In mode FLAT scale source must be blank"}
            )
        elif self.mode == self.Mode.SCALED and not self.scale_source:
            raise ValidationError (
                {"scale_source": "In mode SCALES scale source must be set"}
            )

    def __str__(self):
        return f"{self.source} â†’ {self.target_kind}:{self.target_slug}"

class Technique(models.Model):
    """Technique learned through a school at a required school level."""
    
    name = models.CharField(max_length=200)

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="techniques",
    )

    level = models.PositiveSmallIntegerField()

    description = models.TextField(blank=True, default="")  # Regel-/Flufftext, z.B. "Der Schwur"

    class Meta:
        """Keep technique lists grouped by school and level."""

        ordering = ["school__name", "level", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "level", "name"], name="uniq_technique_school_level_name"),
        ]

    def __str__(self) -> str:
        return f" {self.school.name} ({self.level})"
    
class Item(models.Model):
    """Inventory item with type and stackability rules."""

    class ItemType(models.TextChoices):
        """Supported item categories."""

        ARMOR = "armor", "Armor"
        WEAPON = "weapon", "Weapon"
        MISC = "misc", "Misc"

    name = models.CharField(max_length=200, unique=True)
    price = models.IntegerField(default=1)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.TextField(null=True, blank=True)
    stackable = models.BooleanField(default=True)

    def clean(self):
        """Validate constraints between item type and stackability."""

        super().clean()
        if self.item_type == self.ItemType.ARMOR and self.stackable:
            raise ValidationError({"stackable": "Type: ARMOR can't be stackable."})
            
    def __str__(self):
        return f"{self.item_type.upper()}: {self.name}"

class CharacterItem(models.Model):
    """Inventory ownership relation between a character and an item."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    
    class Meta:
        """Disallow duplicate item ownership rows per character."""

        constraints = [
            models.UniqueConstraint(
                fields=["owner", "item"],
                name = "unique_item_per_character"
            )
        ]
    def clean(self):
        """Validate amount and equip constraints against item settings."""

        super().clean()
        if not self.item.stackable and self.amount != 1:
            raise ValidationError({"amount": "Item is flagged non stackable. amount must be 1" })
        if self.item.item_type == self.item.ItemType.ARMOR and self.amount != 1:
            raise ValidationError({"amount": "Type: ARMOR is not stackable, amount must be 1"})
        if self.item.stackable and self.equipped:
            raise ValidationError({"equipped": "Stackable Items can't be equipped"})
        
    def __str__(self):
        return f"{self.owner} owns {self.item}"

class ArmorStats(models.Model):
    """Armor protection values as either zone-based stats or one total value."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    
    rs_head = models.PositiveIntegerField(default=0)
    rs_torso = models.PositiveIntegerField(default=0)
    rs_arm_left = models.PositiveIntegerField(default=0)
    rs_arm_right = models.PositiveIntegerField(default=0)
    rs_leg_left = models.PositiveIntegerField(default=0)
    rs_leg_right = models.PositiveIntegerField(default=0)
    
    rs_total = models.PositiveIntegerField(default=0)

    def rs_sum(self):
        """Return the summed RS value across all explicit armor zones."""

        rs_fields = [
            f.name for f in self._meta.concrete_fields
            if f.name.startswith("rs_") and f.name != "rs_total"
        ]

        return sum(getattr(self, f) for f in rs_fields)

    def clean(self):
        """Validate armor linkage and exclusive RS input strategy."""

        super().clean()

        if self.item.item_type != Item.ItemType.ARMOR:
            raise ValidationError({"item_type": "Non armor items can't have ArmorStats"})

        zones_sum = self.rs_sum()

        if zones_sum == 0 and not self.rs_total:
            raise ValidationError("Armor must have at either total or zone RS")
        
        if zones_sum > 0 and self.rs_total:
            raise ValidationError("Armor must have either total or zone RS")
    
    def __str__(self):
        return f"{self.item}: {self.rs_sum() // 6}{self.rs_total}"

class DamageSource(models.Model):
    """Damage category used for weapon stats and related modifiers."""
    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name

class WeaponStats(models.Model):
    """Weapon-specific stats attached to exactly one item."""
    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    damage = models.CharField(max_length=20)
    damage_source = models.ForeignKey(DamageSource, on_delete=models.PROTECT)
    
    min_st = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    # TODO: GK
    
    def clean(self):
        """Ensure weapon stats are only linked to weapon items."""
        super().clean()
        if self.item.item_type != Item.ItemType.WEAPON:
            raise ValidationError({"item_type": "Non weapon items can't have WeaponStats"})

    def __str__(self):
        return f"{self.item}: DMG {self.damage} ({self.damage_source})"

class Trait(models.Model):
    """Advantage or disadvantage definition with level-based point cost."""
    class TraitType(models.TextChoices):
        """Supported trait categories."""
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
        """Validate that configured level bounds are ordered correctly."""
        super().clean()
        if self.max_level < self.min_level:
            raise ValidationError("Max level < min level is prohibited.")

    def __str__(self):
        return self.name

class CharacterTrait(models.Model):
    """Purchased trait level for one character."""
    trait = models.ForeignKey(Trait, on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    trait_level = models.PositiveIntegerField(default=1)
       
    class Meta:
        """Allow each trait at most once per character."""
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "trait"],
                name="unique_trait_per_character"
            )
        ]
    
    def clean(self):
        """Validate purchased trait levels against trait limits."""
        super().clean()
        if self.trait_level > self.trait.max_level:
            raise ValidationError(
                {"trait_level": "You can't purchase more levels of a trait than max level"}
                )
        if self.trait_level < self.trait.min_level:
            raise ValidationError(
                {"trait_level": f"Level must be at least {self.trait.min_level}."}
            )
    
    def __str__(self):
        return f"{self.owner}: {self.trait} ({self.trait_level})"
    
class Language(models.Model):
    """Language definition with capped proficiency level."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    
    max_level = models.PositiveIntegerField(default=3)
    
    def __str__(self):
        return self.name

class CharacterLanguage(models.Model):
    """Language proficiency entry for one character."""
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    owner = models.ForeignKey(Character, on_delete=models.PROTECT)
    
    levels = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    
    can_write = models.BooleanField(default=False)
    is_mother_tongue = models.BooleanField(default=False)
    
    class Meta:
        """Allow each language at most once per character."""
        constraints = [models.UniqueConstraint(
            fields = ["owner", "language"],
            name= "unique_language_per_charater"
            )
        ]
    
    def clean(self):
        """Validate level bounds and mother-tongue consistency."""
        super().clean()
        if self.levels > self.language.max_level:
            raise ValidationError(
                {"levels" : "levels can't be greater dan max_level"}
            )
        if self.is_mother_tongue and self.levels != self.language.max_level:
            raise ValidationError(
                {"levels": "Levels of mother tongue must be max_ level"}
            )
    
    def __str__(self):
        return f"{self.owner} speaks {self.language.name} {'(Mother tongue)' if self.is_mother_tongue else ''}"
    
class CharacterCreationDraft(models.Model):
    """Persisted multi-phase character creation state per user."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
            related_name="character_drafts"
            )
    race = models.ForeignKey(Race, on_delete=models.CASCADE)
    current_phase = models.PositiveIntegerField(
        default=1, 
        validators=[MaxValueValidator(4)]
        )
    state = models.JSONField(default=dict, blank=True)

