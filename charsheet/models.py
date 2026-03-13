"""Database models for characters, progression, and modifiers."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .constants import *


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


class SkillFamily(models.Model):
    """A reusable grouping for skills that can be chosen as a permanent focus."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name

class Skill(models.Model):
    """A learnable skill linked to one category and one governing attribute."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.ForeignKey(SkillCategory, on_delete=models.PROTECT)
    family = models.ForeignKey(SkillFamily, on_delete=models.PROTECT, null=True, blank=True)
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


class Character(models.Model):
    """A persisted player character with progression and status data."""

    class Gender(models.TextChoices):
        M = "männlich", "Männlich"
        W = "weiblich", "Weiblich"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    race = models.ForeignKey(Race, on_delete=models.PROTECT)
    gender = models.CharField(max_length=15, choices=Gender, null=True, blank=True)
    age = models.PositiveIntegerField(default=20, null=True, blank=True)
    height = models.IntegerField(default=170)
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

    current_damage = models.PositiveIntegerField(default=0)
    is_archived = models.BooleanField(default=False)
    last_opened_at = models.DateTimeField(null=True, blank=True)

    personal_fame_point = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(10)])
    personal_fame_rank = models.PositiveIntegerField(default=0)
    sacrifice_rank = models.PositiveIntegerField(default=0)
    artefact_rank = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="uniq_character_owner_name")
        ]

    def __str__(self):
        return f"{self.name} ({self.race.name})"

    @property
    def engine(self):
        """Return the cached calculation engine for this character instance."""
        return self.get_engine()

    def get_engine(self, *, refresh: bool = False):
        """Return a reusable engine instance for repeated calculations."""
        cache_key = "_character_engine"
        if refresh or cache_key not in self.__dict__:
            from .engine import CharacterEngine

            self.__dict__[cache_key] = CharacterEngine(self)
        return self.__dict__[cache_key]


class CharacterDiaryEntry(models.Model):
    """One persisted diary segment for a character's parchment-roll journal."""

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="diary_entries",
    )
    order_index = models.PositiveIntegerField(default=0)
    text = models.TextField(blank=True, default="")
    entry_date = models.DateField(null=True, blank=True)
    is_fixed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["character", "order_index", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "order_index"],
                name="uniq_character_diary_entry_order",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character.name} diary #{self.order_index + 1}"

    @property
    def is_empty(self) -> bool:
        """Return whether the entry currently contains no visible text."""
        return not (self.text or "").strip()


class CharacterAttribute(models.Model):
    """Stores the purchased base value of one attribute for a character."""

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
    """Stores the learned rating of one skill for a character."""

    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])

    specification = models.CharField(max_length=25, blank=True, default="*")
    class Meta:
        ordering = ["character", "skill"]
        constraints = [
            models.UniqueConstraint(fields=["character", "skill"], name="uniq_character_skill")
        ]

    def __str__(self):
        return f"{self.character} learned {self.skill}: {self.level}"


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

    @property
    def school_type(self):
        """Backward-compatible alias for the school's type relation."""
        return self.type


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


class Modifier(models.Model):
    """A rule modifier sourced from races, schools, traits, or techniques."""

    class TargetKind(models.TextChoices):
        SKILL = "skill", "Skill"
        CATEGORY = "category", "Category"
        STAT = "stat", "Stat"

    class Mode(models.TextChoices):
        FLAT = "flat", "Flat"
        SCALED = "scaled", "Scaled"

    class ScaleSource(models.TextChoices):
        SCHOOL_LEVEL = "school_level", "School level"
        FAME_TOTAL = "fame_total", "Fame total"
        TRAIT_LVL = "trait_level", "Trait Level"

    class RoundMode(models.TextChoices):
        FLOOR = "floor", "Floor"
        CEIL = "ceil", "Ceil"

    class CapMode(models.TextChoices):
        NONE = "none", "None"
        MIN = "min", "Min"
        MAX = "max", "Max"

    # Generic source on purpose: currently used for Race, School, Trait, and Technique,
    # and intentionally open for later sources such as items or temporary effects.
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")

    target_kind = models.CharField(max_length=30, choices=TargetKind.choices)
    target_slug = models.CharField(max_length=120)

    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.FLAT)
    value = models.SmallIntegerField(default=0)
    scale_source = models.CharField(max_length=30, choices=ScaleSource.choices, null=True, blank=True)
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
    cap_source = models.CharField(max_length=30, choices=ScaleSource.choices, null=True, blank=True)
    min_school_level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["target_kind", "target_slug", "source_content_type", "source_object_id"]
        indexes = [
            models.Index(fields=["source_content_type", "source_object_id"]),
            models.Index(fields=["target_kind", "target_slug"]),
        ]

    def clean(self):
        """Validate target integrity and scaled modifier configuration."""
        super().clean()
        if self.target_kind == self.TargetKind.STAT and self.target_slug not in VALID_STAT_SLUGS:
            raise ValidationError({"target_slug": "Invalid target slug for kind STAT."})
        if self.target_kind == self.TargetKind.SKILL and not Skill.objects.filter(slug=self.target_slug).exists():
            raise ValidationError({"target_slug": "Invalid target slug for kind SKILL."})
        if self.target_kind == self.TargetKind.CATEGORY and not SkillCategory.objects.filter(slug=self.target_slug).exists():
            raise ValidationError({"target_slug": "Invalid target slug for kind CATEGORY."})

        if self.mode == self.Mode.FLAT:
            if self.scale_source:
                raise ValidationError({"scale_source": "In mode FLAT scale_source must be blank."})
            if self.scale_school_id:
                raise ValidationError({"scale_school": "In mode FLAT scale_school must be blank."})
            if self.cap_mode != self.CapMode.NONE or self.cap_source:
                raise ValidationError("Cap configuration is only valid for scaled modifiers.")
        elif not self.scale_source:
            raise ValidationError({"scale_source": "In mode SCALED scale_source must be set."})

        source_model = self.source_content_type.model_class() if self.source_content_type_id else None
        source_is_school_bound = source_model in {School, Technique}

        if self.scale_school_id and self.scale_source != self.ScaleSource.SCHOOL_LEVEL:
            raise ValidationError({"scale_school": "scale_school is only allowed for school-level scaling."})
        if (
            self.scale_source == self.ScaleSource.SCHOOL_LEVEL
            and not self.scale_school_id
            and not source_is_school_bound
        ):
            raise ValidationError({"scale_school": "scale_school is required unless the source is a school or technique."})
        if (
            self.cap_source == self.ScaleSource.SCHOOL_LEVEL
            and not self.scale_school_id
            and not source_is_school_bound
        ):
            raise ValidationError({"cap_source": "A school-level cap needs scale_school or a school/technique source."})
        if (
            self.min_school_level is not None
            and not self.scale_school_id
            and not source_is_school_bound
        ):
            raise ValidationError({"min_school_level": "A school gate needs either scale_school or a school/technique source."})
        if self.cap_mode == self.CapMode.NONE and self.cap_source:
            raise ValidationError({"cap_source": "cap_source must be blank when cap_mode is NONE."})
        if self.cap_mode != self.CapMode.NONE and not self.cap_source:
            raise ValidationError({"cap_source": "cap_source must be set when cap_mode is MIN or MAX."})

    def __str__(self):
        return f"{self.source} -> {self.target_kind}:{self.target_slug}"


class Technique(models.Model):
    """A school technique with acquisition, path, and activation metadata."""

    class TechniqueType(models.TextChoices):
        PASSIVE = "passive", "Passive"
        ACTIVE = "active", "Active"
        SITUATIONAL = "situational", "Situational"

    class AcquisitionType(models.TextChoices):
        AUTOMATIC = "automatic", "Automatic"
        CHOICE = "choice", "Choice"

    class ActionType(models.TextChoices):
        ACTION = "action", "Action"
        REACTION = "reaction", "Reaction"
        FREE = "free", "Free"
        PREPARATION = "preparation", "Preparation"

    class UsageType(models.TextChoices):
        AT_WILL = "at_will", "At Will"
        PER_SCENE = "per_scene", "Per Scene"
        PER_COMBAT = "per_combat", "Per Combat"
        PER_DAY = "per_day", "Per Day"

    class SupportLevel(models.TextChoices):
        """Describe how fully the engine can resolve a technique's rules."""

        COMPUTED = "computed", "Computed"
        STRUCTURED = "structured", "Structured"
        DESCRIPTIVE = "descriptive", "Descriptive"

    class ChoiceTargetKind(models.TextChoices):
        """Describe which persistent build choice, if any, a technique requires."""

        NONE = "none", "None"
        SKILL = "skill", "Skill"
        SKILL_FAMILY = "skill_family", "Skill Family"

    name = models.CharField(max_length=200)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="techniques")
    level = models.PositiveSmallIntegerField()
    path = models.ForeignKey(SchoolPath, on_delete=models.PROTECT, null=True, blank=True, related_name="techniques")
    technique_type = models.CharField(max_length=20, choices=TechniqueType.choices, default=TechniqueType.PASSIVE)
    acquisition_type = models.CharField(max_length=20, choices=AcquisitionType.choices, default=AcquisitionType.AUTOMATIC)
    support_level = models.CharField(
        max_length=20,
        choices=SupportLevel.choices,
        default=SupportLevel.COMPUTED,
        help_text="How far the engine can resolve this technique beyond status and requirements.",
    )
    is_choice_placeholder = models.BooleanField(
        default=False,
        help_text="Mark placeholder rows such as 'choose one technique' or 'pick a skill'.",
    )
    # Editorial metadata only: used for admin/UI grouping of alternatives, not for rule enforcement.
    choice_group = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Optional group key for alternative techniques or shared choice buckets on the same level.",
    )
    selection_notes = models.TextField(
        blank=True,
        default="",
        help_text="Short editor-facing note that explains what exactly must be chosen.",
    )
    choice_target_kind = models.CharField(
        max_length=20,
        choices=ChoiceTargetKind.choices,
        default=ChoiceTargetKind.NONE,
        help_text="Persistent choice type that must be stored for this technique, if any.",
    )
    choice_limit = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="How many persistent character choices this technique may store.",
    )
    choice_bonus_value = models.SmallIntegerField(
        default=0,
        help_text="Fixed computed bonus applied to the chosen skill or skill family.",
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices, null=True, blank=True)
    usage_type = models.CharField(max_length=20, choices=UsageType.choices, null=True, blank=True)
    activation_cost = models.PositiveSmallIntegerField(null=True, blank=True)
    activation_cost_resource = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["school__name", "level", "name"]
        constraints = [
            models.UniqueConstraint(fields=["school", "level", "name"], name="uniq_technique_school_level_name")
        ]

    def clean(self):
        """Validate path ownership, support semantics, and activation consistency."""
        super().clean()
        if self.path_id and self.school_id and self.path.school_id != self.school_id:
            raise ValidationError({"path": "The selected path must belong to the technique school."})
        if self.choice_target_kind == self.ChoiceTargetKind.NONE and self.choice_limit != 1:
            raise ValidationError({"choice_limit": "Non-choice techniques must keep the default choice limit of 1."})
        if (
            self.is_choice_placeholder
            and self.support_level == self.SupportLevel.COMPUTED
        ):
            raise ValidationError(
                {"support_level": "Choice placeholder techniques cannot be marked as fully computed."}
            )
        if self.is_choice_placeholder and not (self.choice_group or self.selection_notes):
            raise ValidationError(
                {
                    "selection_notes": (
                        "Choice placeholder techniques should explain the available choice "
                        "with an organizational group key or selection note."
                    )
                }
            )
        if self.choice_target_kind != self.ChoiceTargetKind.NONE and not (
            self.is_choice_placeholder or self.selection_notes or self.choice_group
        ):
            raise ValidationError(
                {
                    "selection_notes": (
                        "Choice techniques should document the permanent choice with notes "
                        "or an organizational choice group."
                    )
                }
            )
        if self.choice_bonus_value and self.choice_target_kind == self.ChoiceTargetKind.NONE:
            raise ValidationError({"choice_bonus_value": "Choice bonuses require an explicit choice target kind."})
        if self.choice_bonus_value and self.support_level != self.SupportLevel.COMPUTED:
            raise ValidationError({"choice_bonus_value": "Choice bonuses are only supported for computed techniques."})
        if self.choice_bonus_value and self.technique_type != self.TechniqueType.PASSIVE:
            raise ValidationError({"choice_bonus_value": "Fixed choice bonuses are only supported on passive techniques."})
        if self.technique_type == self.TechniqueType.PASSIVE:
            errors = {}
            if self.action_type:
                errors["action_type"] = "Passive techniques cannot define an action type."
            if self.usage_type:
                errors["usage_type"] = "Passive techniques cannot define a usage type."
            if self.activation_cost is not None:
                errors["activation_cost"] = "Passive techniques cannot define activation costs."
            if self.activation_cost_resource:
                errors["activation_cost_resource"] = "Passive techniques cannot define a cost resource."
            if errors:
                raise ValidationError(errors)
        if self.activation_cost_resource and self.activation_cost is None:
            raise ValidationError({"activation_cost": "Set an activation cost when a cost resource is defined."})

    def __str__(self) -> str:
        path_suffix = f" [{self.path.name}]" if self.path_id else ""
        return f"{self.school.name}: {self.name} (L{self.level}){path_suffix}"


class TechniqueRequirement(models.Model):
    """One atomic prerequisite that must be met before a technique is available."""

    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="requirements")
    minimum_school_level = models.PositiveSmallIntegerField(null=True, blank=True)
    required_technique = models.ForeignKey(
        Technique,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="required_for_requirements",
    )
    required_path = models.ForeignKey(
        SchoolPath,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="required_for_techniques",
    )
    required_skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="required_for_techniques",
    )
    required_skill_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    required_trait = models.ForeignKey(
        "Trait",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="required_for_techniques",
    )
    required_trait_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["technique__school__name", "technique__level", "technique__name", "id"]

    def clean(self):
        """Require exactly one structured prerequisite family per requirement row."""
        super().clean()
        populated_fields = [
            self.minimum_school_level is not None,
            self.required_technique_id is not None,
            self.required_path_id is not None,
            self.required_skill_id is not None or self.required_skill_level is not None,
            self.required_trait_id is not None or self.required_trait_level is not None,
        ]
        if sum(populated_fields) != 1:
            raise ValidationError("Each technique requirement must define exactly one requirement type.")
        if self.required_technique_id and self.technique_id == self.required_technique_id:
            raise ValidationError({"required_technique": "A technique cannot require itself."})
        if (
            self.required_path_id
            and self.technique_id
            and self.required_path.school_id != self.technique.school_id
        ):
            raise ValidationError({"required_path": "A required path must belong to the same school as the technique."})
        if self.required_skill_id is None and self.required_skill_level is not None:
            raise ValidationError({"required_skill": "Set a skill when a required skill level is defined."})
        if self.required_skill_id is not None and self.required_skill_level is None:
            raise ValidationError({"required_skill_level": "Set a required skill level when a skill is defined."})
        if self.required_trait_id is None and self.required_trait_level is not None:
            raise ValidationError({"required_trait": "Set a trait when a required trait level is defined."})
        if self.required_trait_id is not None and self.required_trait_level is None:
            raise ValidationError({"required_trait_level": "Set a required trait level when a trait is defined."})

    def __str__(self) -> str:
        if self.minimum_school_level is not None:
            return f"{self.technique.name} requires school level {self.minimum_school_level}+"
        if self.required_technique_id is not None:
            return f"{self.technique.name} requires technique {self.required_technique.name}"
        if self.required_skill_id is not None:
            return f"{self.technique.name} requires skill {self.required_skill.name} {self.required_skill_level}+"
        if self.required_trait_id is not None:
            return f"{self.technique.name} requires trait {self.required_trait.name} {self.required_trait_level}+"
        return f"{self.technique.name} requires path {self.required_path.name}"


class TechniqueExclusion(models.Model):
    """A symmetric exclusion relation between two techniques."""

    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="exclusions")
    excluded_technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="excluded_by")

    class Meta:
        ordering = ["technique__school__name", "technique__name", "excluded_technique__name"]
        constraints = [
            models.UniqueConstraint(fields=["technique", "excluded_technique"], name="uniq_technique_exclusion_direction"),
        ]

    def clean(self):
        """Block self-references and mirrored duplicate exclusions."""
        super().clean()
        if self.technique_id and self.excluded_technique_id and self.technique_id == self.excluded_technique_id:
            raise ValidationError({"excluded_technique": "A technique cannot exclude itself."})
        if (
            self.technique_id
            and self.excluded_technique_id
            and TechniqueExclusion.objects.exclude(pk=self.pk).filter(
                technique_id=self.excluded_technique_id,
                excluded_technique_id=self.technique_id,
            ).exists()
        ):
            raise ValidationError("This exclusion pair already exists in reverse order.")

    def __str__(self) -> str:
        return f"{self.technique.name} excludes {self.excluded_technique.name}"


class CharacterTechnique(models.Model):
    """Explicitly learned technique ownership for one character."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="learned_techniques")
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="character_techniques")
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["character", "technique__school__name", "technique__level", "technique__name"]
        constraints = [
            models.UniqueConstraint(fields=["character", "technique"], name="uniq_character_technique")
        ]

    def clean(self):
        """Validate that the character knows the school and persisted path fits."""
        super().clean()
        if self.character_id and self.technique_id and not CharacterSchool.objects.filter(
            character_id=self.character_id,
            school_id=self.technique.school_id,
        ).exists():
            raise ValidationError({"technique": "A character can only learn techniques from learned schools."})
        if self.character_id and self.technique_id and self.technique.path_id:
            selected_path = CharacterSchoolPath.objects.filter(
                character_id=self.character_id,
                school_id=self.technique.school_id,
            ).first()
            if selected_path and selected_path.path_id != self.technique.path_id:
                raise ValidationError(
                    {"technique": "The persisted school path does not allow this technique."}
                )

    def __str__(self) -> str:
        return f"{self.character.name} learned {self.technique.name}"


class CharacterTechniqueChoice(models.Model):
    """A persistent character-bound choice made for one technique."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="technique_choices")
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="character_choices")
    selected_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_technique_choices",
    )
    selected_skill_family = models.ForeignKey(
        SkillFamily,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_technique_choices",
    )

    class Meta:
        ordering = ["character__name", "technique__school__name", "technique__level", "technique__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "technique", "selected_skill"],
                condition=models.Q(selected_skill__isnull=False),
                name="uniq_character_technique_selected_skill",
            ),
            models.UniqueConstraint(
                fields=["character", "technique", "selected_skill_family"],
                condition=models.Q(selected_skill_family__isnull=False),
                name="uniq_character_technique_selected_family",
            ),
        ]

    def clean(self):
        """Validate stored choice targets with model-local technique and school checks."""
        super().clean()
        populated_targets = [
            self.selected_skill_id is not None,
            self.selected_skill_family_id is not None,
        ]
        if sum(populated_targets) != 1:
            raise ValidationError("A technique choice must select exactly one persistent target.")
        if self.technique_id and self.technique.choice_target_kind == Technique.ChoiceTargetKind.NONE:
            raise ValidationError({"technique": "This technique does not store persistent character choices."})
        if self.technique_id and self.technique.choice_target_kind == Technique.ChoiceTargetKind.SKILL:
            if self.selected_skill_id is None:
                raise ValidationError({"selected_skill": "This technique requires a skill choice."})
            if self.selected_skill_family_id is not None:
                raise ValidationError({"selected_skill_family": "This technique only allows a skill choice."})
        if self.technique_id and self.technique.choice_target_kind == Technique.ChoiceTargetKind.SKILL_FAMILY:
            if self.selected_skill_family_id is None:
                raise ValidationError({"selected_skill_family": "This technique requires a skill family choice."})
            if self.selected_skill_id is not None:
                raise ValidationError({"selected_skill": "This technique only allows a skill family choice."})
        if self.character_id and self.technique_id:
            if not CharacterSchool.objects.filter(
                character_id=self.character_id,
                school_id=self.technique.school_id,
            ).exists():
                raise ValidationError({"technique": "Persistent choices require the character to know the technique's school."})
            if self.technique.path_id:
                selected_path = CharacterSchoolPath.objects.filter(
                    character_id=self.character_id,
                    school_id=self.technique.school_id,
                ).first()
                if selected_path and selected_path.path_id != self.technique.path_id:
                    raise ValidationError(
                        {"technique": "The character's persisted school path does not allow this technique choice."}
                    )
            existing_count = (
                CharacterTechniqueChoice.objects.filter(character_id=self.character_id, technique_id=self.technique_id)
                .exclude(pk=self.pk)
                .count()
            )
            if existing_count >= self.technique.choice_limit:
                raise ValidationError({"technique": "The configured choice limit for this technique has already been reached."})

    def __str__(self) -> str:
        selected = self.selected_skill or self.selected_skill_family
        return f"{self.character.name} -> {self.technique.name}: {selected}"


class Item(models.Model):
    """Inventory item that may be owned, stacked, or equipped."""

    class ItemType(models.TextChoices):
        ARMOR = "armor", "Armor"
        WEAPON = "weapon", "Weapon"
        MISC = "misc", "Misc"

    name = models.CharField(max_length=200, unique=True)
    price = models.IntegerField(default=1)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.TextField(null=True, blank=True)
    stackable = models.BooleanField(default=True)
    is_consumable = models.BooleanField(default=False)

    def clean(self):
        """Prevent invalid stackable armor definitions."""
        super().clean()
        if self.item_type == self.ItemType.ARMOR and self.stackable:
            raise ValidationError({"stackable": "Type: ARMOR can't be stackable."})

    def __str__(self):
        return f"{self.item_type.upper()}: {self.name}"


class CharacterItem(models.Model):
    """Ownership state of one item for one character."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "item"], name="unique_item_per_character")
        ]

    def clean(self):
        """Enforce stackability and equipment consistency."""
        super().clean()
        if not self.item.stackable and self.amount != 1:
            raise ValidationError({"amount": "Item is flagged non stackable. amount must be 1"})
        if self.item.item_type == self.item.ItemType.ARMOR and self.amount != 1:
            raise ValidationError({"amount": "Type: ARMOR is not stackable, amount must be 1"})
        if self.item.stackable and self.equipped:
            raise ValidationError({"equipped": "Stackable Items can't be equipped"})

    def __str__(self):
        return f"{self.owner} owns {self.item}"


class ArmorStats(models.Model):
    """Armor-specific protection values for an item."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)

    rs_head = models.PositiveIntegerField(default=0)
    rs_torso = models.PositiveIntegerField(default=0)
    rs_arm_left = models.PositiveIntegerField(default=0)
    rs_arm_right = models.PositiveIntegerField(default=0)
    rs_leg_left = models.PositiveIntegerField(default=0)
    rs_leg_right = models.PositiveIntegerField(default=0)

    rs_total = models.PositiveIntegerField(default=0)

    def rs_sum(self):
        """Sum all zone-based armor values without using rs_total."""
        rs_fields = [
            field.name
            for field in self._meta.concrete_fields
            if field.name.startswith("rs_") and field.name != "rs_total"
        ]
        return sum(getattr(self, field_name) for field_name in rs_fields)

    def clean(self):
        """Ensure armor stats only exist on armor items and use one RS mode."""
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
    """Damage type or source used by weapon definitions."""

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class WeaponStats(models.Model):
    """Weapon-specific combat data attached to an item."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    damage = models.CharField(max_length=20)
    damage_source = models.ForeignKey(DamageSource, on_delete=models.PROTECT)
    min_st = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)
    two_handed = models.BooleanField(default=False)
    two_handed_damage = models.CharField(max_length=20, null=True, blank=True)

    def clean(self):
        """Ensure weapon stats are only attached to weapon items."""
        super().clean()
        if self.item.item_type != Item.ItemType.WEAPON:
            raise ValidationError({"item_type": "Non weapon items can't have WeaponStats"})

    def __str__(self):
        return f"{self.item}: DMG {self.damage} ({self.damage_source})"


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


class CharacterTrait(models.Model):
    """Purchased trait level of a character."""

    trait = models.ForeignKey(Trait, on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    trait_level = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "trait"], name="unique_trait_per_character")
        ]

    def clean(self):
        """Validate the chosen trait level against its allowed range."""
        super().clean()
        if self.trait_level > self.trait.max_level:
            raise ValidationError({"trait_level": "You can't purchase more levels of a trait than max level"})
        if self.trait_level < self.trait.min_level:
            raise ValidationError({"trait_level": f"Level must be at least {self.trait.min_level}."})

    def __str__(self):
        return f"{self.owner}: {self.trait} ({self.trait_level})"


class Language(models.Model):
    """Language definition with a configurable maximum mastery level."""

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
        constraints = [
            models.UniqueConstraint(fields=["owner", "language"], name="unique_language_per_charater")
        ]

    def clean(self):
        """Validate level bounds and mother-tongue requirements."""
        super().clean()
        if self.levels > self.language.max_level:
            raise ValidationError({"levels": "levels can't be greater dan max_level"})
        if self.is_mother_tongue and self.levels != self.language.max_level:
            raise ValidationError({"levels": "Levels of mother tongue must be max_ level"})

    def __str__(self):
        suffix = " (Mother tongue)" if self.is_mother_tongue else ""
        return f"{self.owner} speaks {self.language.name}{suffix}"


class CharacterCreationDraft(models.Model):
    """Persisted in-progress state for the character creation flow."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="character_drafts",
    )
    race = models.ForeignKey(Race, on_delete=models.CASCADE)
    current_phase = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(4)])
    state = models.JSONField(default=dict, blank=True)
