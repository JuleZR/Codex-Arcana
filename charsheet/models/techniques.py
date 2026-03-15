"""Technique rules, modifiers, and character choices."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from ..constants import VALID_STAT_SLUGS
from .core import Skill, SkillCategory, Trait
from .items import Item
from .progression import CharacterSchool, CharacterSchoolPath, School, SchoolPath, Specialization


class TechniqueChoiceBlock(models.Model):
    """A generic rule block that groups mutually limited technique picks."""

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="technique_choice_blocks",
    )
    name = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Short editor-facing label used to identify the rulebook choice block.",
    )
    level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional school level at which this choice block becomes relevant.",
    )
    path = models.ForeignKey(
        SchoolPath,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="technique_choice_blocks",
        help_text="Optional school path restriction for this block.",
    )
    min_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Minimum number of techniques that must be learned from this block.",
    )
    max_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of techniques that may be learned from this block.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Rulebook wording that explains what the player must choose here.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["school__name", "level", "sort_order", "name", "id"]

    def clean(self):
        """Keep school/path wiring and min/max choice semantics consistent."""
        super().clean()
        if self.path_id and self.school_id and self.path.school_id != self.school_id:
            raise ValidationError({"path": "The selected path must belong to the same school as the choice block."})
        if self.max_choices < self.min_choices:
            raise ValidationError({"max_choices": "max_choices must be greater than or equal to min_choices."})

    def __str__(self) -> str:
        label = self.name or self.description or "Choice Block"
        level = f" L{self.level}" if self.level is not None else ""
        path = f" [{self.path.name}]" if self.path_id else ""
        return f"{self.school.name}:{level}{path} {label}".strip()


class Modifier(models.Model):
    """A rule modifier sourced from races, schools, traits, or techniques."""

    class TargetKind(models.TextChoices):
        SKILL = "skill", "Skill"
        CATEGORY = "category", "Skill Category"
        STAT = "stat", "Stat"
        ITEM = "item", "Item"
        ITEM_CATEGORY = "item_category", "Item Category"
        SPECIALIZATION = "specialization", "Specialization"
        ENTITY = "entity", "Other Entity"

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

    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="modifier_source_relations",
    )
    source_object_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")

    target_kind = models.CharField(max_length=30, choices=TargetKind.choices)
    target_slug = models.CharField(max_length=120, blank=True, default="")
    target_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modifiers",
    )
    target_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modifiers",
    )
    target_item = models.ForeignKey(
        "Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modifiers",
    )
    target_specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modifiers",
    )
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="modifier_target_relations",
    )
    target_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

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
            models.Index(fields=["target_content_type", "target_object_id"]),
        ]

    def clean(self):
        """Validate target integrity and scaled modifier configuration."""
        super().clean()
        allowed_item_categories = {choice for choice, _label in Item.ItemType.choices}
        if self.target_content_type_id and self.target_object_id is None:
            raise ValidationError({"target_object_id": "Set an object id when a target content type is selected."})
        if self.target_object_id is not None and not self.target_content_type_id:
            raise ValidationError({"target_content_type": "Select a content type when a target object id is set."})

        if self.target_kind == self.TargetKind.STAT:
            if self.target_slug not in VALID_STAT_SLUGS:
                raise ValidationError({"target_slug": "Invalid target slug for kind STAT."})
            self._require_empty_target_fields(
                "STAT",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.SKILL:
            self._validate_target_selector(
                label="SKILL",
                slug_field="target_slug",
                slug_validator=lambda slug: Skill.objects.filter(slug=slug).exists(),
                object_fields=("target_skill",),
            )
            self._require_empty_target_fields(
                "SKILL",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.CATEGORY:
            self._validate_target_selector(
                label="CATEGORY",
                slug_field="target_slug",
                slug_validator=lambda slug: SkillCategory.objects.filter(slug=slug).exists(),
                object_fields=("target_skill_category",),
            )
            self._require_empty_target_fields(
                "CATEGORY",
                "target_skill",
                "target_item",
                "target_specialization",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.ITEM:
            if self.target_item_id is None:
                raise ValidationError({"target_item": "Select an item target for kind ITEM."})
            self._require_empty_target_fields(
                "ITEM",
                "target_slug",
                "target_skill",
                "target_skill_category",
                "target_specialization",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.ITEM_CATEGORY:
            if not self.target_slug or self.target_slug not in allowed_item_categories:
                raise ValidationError({"target_slug": "Invalid item category key for kind ITEM_CATEGORY."})
            self._require_empty_target_fields(
                "ITEM_CATEGORY",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.SPECIALIZATION:
            if self.target_specialization_id is None:
                raise ValidationError({"target_specialization": "Select a specialization target for kind SPECIALIZATION."})
            self._require_empty_target_fields(
                "SPECIALIZATION",
                "target_slug",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.ENTITY:
            if not self.target_content_type_id or self.target_object_id is None:
                raise ValidationError(
                    {"target_content_type": "Select a content type and object id for kind ENTITY."}
                )
            self._require_empty_target_fields(
                "ENTITY",
                "target_slug",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
            )

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

    def _validate_target_selector(self, *, label, slug_field, slug_validator, object_fields):
        """Require exactly one selector mode for targets that allow slug or FK addressing."""
        slug_value = getattr(self, slug_field)
        object_values = [getattr(self, f"{field}_id") is not None for field in object_fields]
        populated_count = int(bool(slug_value)) + sum(object_values)
        if populated_count != 1:
            raise ValidationError(f"{label} targets require exactly one concrete selector.")
        if slug_value and not slug_validator(slug_value):
            raise ValidationError({slug_field: f"Invalid target slug for kind {label}."})

    def _require_empty_target_fields(self, label, *field_names):
        """Reject selectors that do not belong to the configured target kind."""
        errors = {}
        for field_name in field_names:
            value = getattr(self, field_name)
            if value not in (None, "", 0):
                errors[field_name] = f"{field_name} is not used for target kind {label}."
        if errors:
            raise ValidationError(errors)

    def target_identifier(self) -> str:
        """Return the canonical lookup identifier used by the engine."""
        if self.target_kind == self.TargetKind.SKILL:
            return self.target_skill.slug if self.target_skill_id else self.target_slug
        if self.target_kind == self.TargetKind.CATEGORY:
            return self.target_skill_category.slug if self.target_skill_category_id else self.target_slug
        if self.target_kind == self.TargetKind.ITEM:
            return str(self.target_item_id)
        if self.target_kind == self.TargetKind.SPECIALIZATION:
            return str(self.target_specialization_id)
        if self.target_kind == self.TargetKind.ENTITY:
            return f"{self.target_content_type_id}:{self.target_object_id}"
        return self.target_slug

    def target_display(self) -> str:
        """Return a readable label for the configured target."""
        if self.target_kind == self.TargetKind.SKILL:
            return self.target_skill.name if self.target_skill_id else self.target_slug
        if self.target_kind == self.TargetKind.CATEGORY:
            return self.target_skill_category.name if self.target_skill_category_id else self.target_slug
        if self.target_kind == self.TargetKind.ITEM and self.target_item_id:
            return self.target_item.name
        if self.target_kind == self.TargetKind.SPECIALIZATION and self.target_specialization_id:
            return self.target_specialization.name
        if self.target_kind == self.TargetKind.ENTITY and self.target is not None:
            return str(self.target)
        return self.target_slug or "-"

    def __str__(self):
        return f"{self.source} -> {self.target_kind}:{self.target_display()}"


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

        COMPUTED = "computed", "Automated"
        STRUCTURED = "structured", "Partially Automated"
        DESCRIPTIVE = "descriptive", "Manual (Rule Text Only)"

    class ChoiceTargetKind(models.TextChoices):
        """Describe which persistent build choice, if any, a technique requires."""

        NONE = "none", "None"
        SKILL = "skill", "Skill"
        SKILL_CATEGORY = "skill_category", "Skill Category"
        ITEM = "item", "Item"
        ITEM_CATEGORY = "item_category", "Item Category"
        SPECIALIZATION = "specialization", "Specialization"
        TEXT = "text", "Free Text"
        ENTITY = "entity", "Other Entity"

    name = models.CharField(max_length=200)
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="techniques")
    level = models.PositiveSmallIntegerField()
    path = models.ForeignKey(SchoolPath, on_delete=models.PROTECT, null=True, blank=True, related_name="techniques")
    choice_block = models.ForeignKey(
        TechniqueChoiceBlock,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="techniques",
        help_text="Optional rule choice block that defines mandatory or limited technique picks.",
    )
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
        help_text="Fixed computed bonus applied to the chosen skill.",
    )
    specialization_slot_grants = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "How many school-bound specialization slots this technique unlocks once it is "
            "learned and currently available."
        ),
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
        if self.choice_block_id:
            if self.school_id and self.choice_block.school_id != self.school_id:
                raise ValidationError({"choice_block": "The selected choice block must belong to the same school."})
            if self.choice_block.level is not None and self.choice_block.level != self.level:
                raise ValidationError({"choice_block": "A level-bound choice block must match the technique level."})
            if self.choice_block.path_id is not None and self.choice_block.path_id != self.path_id:
                raise ValidationError({"choice_block": "A path-bound choice block must match the technique path."})
        if self.choice_target_kind == self.ChoiceTargetKind.NONE and self.choice_limit != 1:
            raise ValidationError({"choice_limit": "Non-choice techniques must keep the default choice limit of 1."})
        if self.is_choice_placeholder and self.support_level == self.SupportLevel.COMPUTED:
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
        Trait,
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
            models.UniqueConstraint(
                fields=["technique", "excluded_technique"],
                name="uniq_technique_exclusion_direction",
            ),
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


class TechniqueChoiceDefinition(models.Model):
    """A generic persistent decision that must be stored for one technique."""

    technique = models.ForeignKey(
        Technique,
        on_delete=models.CASCADE,
        related_name="choice_definitions",
    )
    name = models.CharField(
        max_length=120,
        help_text="Readable label that identifies this choice requirement in rulebook terms.",
    )
    target_kind = models.CharField(
        max_length=20,
        choices=Technique.ChoiceTargetKind.choices,
        help_text="What kind of thing must be selected for this technique decision.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Short rulebook prompt that explains what exactly must be chosen.",
    )
    min_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Minimum number of stored selections required for this one decision.",
    )
    max_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of stored selections allowed for this one decision.",
    )
    is_required = models.BooleanField(
        default=True,
        help_text="If enabled, the technique stays incomplete until this decision reaches min_choices.",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = [
            "technique__school__name",
            "technique__level",
            "technique__name",
            "sort_order",
            "name",
            "id",
        ]

    def clean(self):
        """Prevent empty or contradictory decision definitions."""
        super().clean()
        if self.target_kind == Technique.ChoiceTargetKind.NONE:
            raise ValidationError({"target_kind": "Choice definitions must point at a concrete target kind."})
        if self.max_choices < self.min_choices:
            raise ValidationError({"max_choices": "max_choices must be greater than or equal to min_choices."})
        if not self.is_required and self.min_choices != 0:
            raise ValidationError({"min_choices": "Optional choice definitions must use min_choices = 0."})

    def __str__(self) -> str:
        return f"{self.technique.name}: {self.name}"


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
    definition = models.ForeignKey(
        TechniqueChoiceDefinition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="character_choices",
    )
    selected_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_technique_choices",
    )
    selected_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_technique_choices",
    )
    selected_item = models.ForeignKey(
        "Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_technique_choices",
    )
    selected_item_category = models.CharField(max_length=30, blank=True, default="")
    selected_specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_technique_choices",
    )
    selected_text = models.CharField(max_length=255, blank=True, default="")
    selected_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="character_technique_choice_targets",
    )
    selected_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    selected_entity = GenericForeignKey("selected_content_type", "selected_object_id")

    class Meta:
        ordering = ["character__name", "technique__school__name", "technique__level", "technique__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "technique", "selected_skill"],
                condition=models.Q(selected_skill__isnull=False),
                name="uniq_character_technique_selected_skill",
            ),
            models.UniqueConstraint(
                fields=["character", "technique", "definition", "selected_skill_category"],
                condition=models.Q(selected_skill_category__isnull=False),
                name="uniq_character_technique_selected_category",
            ),
            models.UniqueConstraint(
                fields=["character", "technique", "definition", "selected_item"],
                condition=models.Q(selected_item__isnull=False),
                name="uniq_character_technique_selected_item",
            ),
            models.UniqueConstraint(
                fields=["character", "technique", "definition", "selected_specialization"],
                condition=models.Q(selected_specialization__isnull=False),
                name="uniq_character_technique_selected_specialization",
            ),
            models.UniqueConstraint(
                fields=["character", "technique", "definition", "selected_item_category"],
                condition=~models.Q(selected_item_category=""),
                name="uniq_character_technique_selected_item_category",
            ),
            models.UniqueConstraint(
                fields=["character", "technique", "definition", "selected_content_type", "selected_object_id"],
                condition=models.Q(selected_object_id__isnull=False),
                name="uniq_character_technique_selected_entity",
            ),
        ]

    def clean(self):
        """Validate stored choice targets with model-local technique and school checks."""
        super().clean()
        if self.selected_content_type_id and self.selected_object_id is None:
            raise ValidationError({"selected_object_id": "Set an object id when selecting another entity."})
        if self.selected_object_id is not None and not self.selected_content_type_id:
            raise ValidationError({"selected_content_type": "Select a content type when using another entity."})
        populated_targets = [
            self.selected_skill_id is not None,
            self.selected_skill_category_id is not None,
            self.selected_item_id is not None,
            bool(self.selected_item_category),
            self.selected_specialization_id is not None,
            bool(self.selected_text),
            self.selected_object_id is not None,
        ]
        if sum(populated_targets) != 1:
            raise ValidationError("A technique choice must select exactly one persistent target.")
        if self.definition_id and self.technique_id and self.definition.technique_id != self.technique_id:
            raise ValidationError({"definition": "The selected choice definition must belong to the same technique."})
        expected_kind = self._expected_target_kind()
        if self.technique_id and expected_kind == Technique.ChoiceTargetKind.NONE:
            raise ValidationError({"technique": "This technique does not store persistent character choices."})
        self._validate_target_kind(expected_kind)
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
            if self.definition_id:
                existing_count = (
                    CharacterTechniqueChoice.objects.filter(
                        character_id=self.character_id,
                        technique_id=self.technique_id,
                        definition_id=self.definition_id,
                    )
                    .exclude(pk=self.pk)
                    .count()
                )
                if existing_count >= self.definition.max_choices:
                    raise ValidationError(
                        {"definition": "The configured choice limit for this technique decision has already been reached."}
                    )
            elif self.technique.choice_definitions.filter(is_active=True).exists():
                raise ValidationError({"definition": "This technique uses explicit choice definitions. Pick one definition."})
            existing_count = (
                CharacterTechniqueChoice.objects.filter(
                    character_id=self.character_id,
                    technique_id=self.technique_id,
                    definition__isnull=True,
                )
                .exclude(pk=self.pk)
                .count()
            )
            if not self.definition_id and existing_count >= self.technique.choice_limit:
                raise ValidationError({"technique": "The configured choice limit for this technique has already been reached."})

    def _expected_target_kind(self):
        """Return the target kind enforced by the definition or legacy technique fields."""
        if self.definition_id:
            return self.definition.target_kind
        if self.technique_id:
            return self.technique.choice_target_kind
        return Technique.ChoiceTargetKind.NONE

    def _validate_target_kind(self, expected_kind):
        """Ensure the selected target fields match the configured choice kind."""
        errors = {}
        allowed_item_categories = {choice for choice, _label in Item.ItemType.choices}
        target_field_by_kind = {
            Technique.ChoiceTargetKind.SKILL: "selected_skill",
            Technique.ChoiceTargetKind.SKILL_CATEGORY: "selected_skill_category",
            Technique.ChoiceTargetKind.ITEM: "selected_item",
            Technique.ChoiceTargetKind.ITEM_CATEGORY: "selected_item_category",
            Technique.ChoiceTargetKind.SPECIALIZATION: "selected_specialization",
            Technique.ChoiceTargetKind.TEXT: "selected_text",
            Technique.ChoiceTargetKind.ENTITY: "selected_content_type",
        }
        required_field = target_field_by_kind.get(expected_kind)
        if required_field is None:
            raise ValidationError({"technique": "Unsupported choice target kind."})
        if expected_kind == Technique.ChoiceTargetKind.ITEM_CATEGORY and (
            not self.selected_item_category or self.selected_item_category not in allowed_item_categories
        ):
            errors["selected_item_category"] = "Select a valid item category."
        elif expected_kind == Technique.ChoiceTargetKind.SPECIALIZATION:
            if self.selected_specialization_id is None:
                errors["selected_specialization"] = "This technique requires a specialization choice."
            elif self.technique_id and self.selected_specialization.school_id != self.technique.school_id:
                errors["selected_specialization"] = "The selected specialization must belong to the same school."
        elif expected_kind == Technique.ChoiceTargetKind.ENTITY:
            if not self.selected_content_type_id or self.selected_object_id is None:
                errors["selected_content_type"] = "This technique requires another entity target."
        elif expected_kind == Technique.ChoiceTargetKind.TEXT:
            if not self.selected_text:
                errors["selected_text"] = "This technique requires a free-text choice."
        elif getattr(self, f"{required_field}_id", None) is None and not getattr(self, required_field):
            errors[required_field] = f"This technique requires a {expected_kind.replace('_', ' ')} choice."

        disallowed_fields = {
            "selected_skill",
            "selected_skill_category",
            "selected_item",
            "selected_item_category",
            "selected_specialization",
            "selected_text",
            "selected_content_type",
            "selected_object_id",
        } - {required_field}
        if expected_kind == Technique.ChoiceTargetKind.ENTITY:
            disallowed_fields -= {"selected_object_id"}
        for field_name in disallowed_fields:
            value = getattr(self, field_name)
            if value not in (None, "", 0):
                errors[field_name] = "This field does not match the configured choice kind."
        if errors:
            raise ValidationError(errors)

    def selected_target_display(self) -> str:
        """Return a readable label for the chosen target."""
        if self.selected_skill_id:
            return self.selected_skill.name
        if self.selected_skill_category_id:
            return self.selected_skill_category.name
        if self.selected_item_id:
            return self.selected_item.name
        if self.selected_item_category:
            return self.selected_item_category
        if self.selected_specialization_id:
            return self.selected_specialization.name
        if self.selected_text:
            return self.selected_text
        if self.selected_entity is not None:
            return str(self.selected_entity)
        return "-"

    def __str__(self) -> str:
        return f"{self.character.name} -> {self.technique.name}: {self.selected_target_display()}"
