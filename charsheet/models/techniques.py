"""Technique rules and character technique choices."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .core import Skill, SkillCategory, Trait, Race, Attribute
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
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="techniques", blank=True, null=True)
    level = models.PositiveSmallIntegerField(blank=True, null=True)
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
    target_choice_definition = models.ForeignKey(
        "TechniqueChoiceDefinition",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="targeting_techniques",
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices, null=True, blank=True)
    usage_type = models.CharField(max_length=20, choices=UsageType.choices, null=True, blank=True)
    activation_cost = models.PositiveSmallIntegerField(null=True, blank=True)
    activation_cost_resource = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True, default="")

    has_specification = models.BooleanField(default=False)

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
        school_name = self.school.name if self.school_id and self.school else "RaceSkill"
        technique_name = self.name or "Unnamed Technique"
        path_suffix = f" [{self.path.name}]" if self.path_id and self.path else ""
        return f"{school_name}: {technique_name}{path_suffix}"


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
    allowed_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="technique_choice_definitions",
        )
    allowed_skill_family = models.SlugField(
        max_length=50,
        blank=True,
        default=""
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
        if self.target_kind != Technique.ChoiceTargetKind.SKILL:
            if self.allowed_skill_category_id:
                raise ValidationError({
                    "allowed_skill_category": "This filter is only valid for skill choices."
                })
            if self.allowed_skill_family:
                raise ValidationError({
                    "allowed_skill_family": "This filter is only valid for skill choices."
                })

    def __str__(self) -> str:
        return f"{self.technique.name}: {self.name}"


class RaceChoiceDefinition(models.Model):
    """A persistent decision that belongs directly to one race."""

    race = models.ForeignKey(
        Race,
        on_delete=models.CASCADE,
        related_name="choice_definitions",
    )
    name = models.CharField(
        max_length=120,
        help_text="Readable label that identifies this race choice in rulebook terms.",
    )
    target_kind = models.CharField(
        max_length=20,
        choices=Technique.ChoiceTargetKind.choices,
        help_text="What kind of thing must be selected for this race decision.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Short rulebook prompt that explains what exactly must be chosen.",
    )
    min_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Minimum number of stored selections required for this race decision.",
    )
    max_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of stored selections allowed for this race decision.",
    )
    is_required = models.BooleanField(
        default=True,
        help_text="If enabled, the race stays incomplete until this decision reaches min_choices.",
    )
    allowed_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="race_choice_definitions",
    )
    allowed_skill_family = models.SlugField(
        max_length=50,
        blank=True,
        default="",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["race__name", "sort_order", "name", "id"]

    def clean(self):
        """Prevent empty or contradictory race decision definitions."""
        super().clean()
        if self.target_kind == Technique.ChoiceTargetKind.NONE:
            raise ValidationError({"target_kind": "Choice definitions must point at a concrete target kind."})
        if self.max_choices < self.min_choices:
            raise ValidationError({"max_choices": "max_choices must be greater than or equal to min_choices."})
        if not self.is_required and self.min_choices != 0:
            raise ValidationError({"min_choices": "Optional choice definitions must use min_choices = 0."})
        if self.target_kind != Technique.ChoiceTargetKind.SKILL:
            if self.allowed_skill_category_id:
                raise ValidationError({
                    "allowed_skill_category": "This filter is only valid for skill choices."
                })
            if self.allowed_skill_family:
                raise ValidationError({
                    "allowed_skill_family": "This filter is only valid for skill choices."
                })

    def __str__(self) -> str:
        return f"{self.race.name}: {self.name}"


class CharacterTechnique(models.Model):
    """Explicitly learned technique ownership for one character."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="learned_techniques")
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="character_techniques")
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    specification_value = models.CharField(max_length=100, blank=True, default="")

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
        if (
            self.definition_id
            and expected_kind == Technique.ChoiceTargetKind.SKILL
            and self.selected_skill_id
        ):
            if (
                self.definition.allowed_skill_category_id
                and self.selected_skill.category_id != self.definition.allowed_skill_category_id
            ):
                raise ValidationError({
                    "selected_skill": "The selected skill does not belong to the allowed skill category."
                })

            if (
                self.definition.allowed_skill_family
                and self.selected_skill.family != self.definition.allowed_skill_family
            ):
                raise ValidationError({
                    "selected_skill": "The selected skill does not belong to the allowed skill family."
                })
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
        if self.definition_id and self.character_id:
            existing = CharacterTechniqueChoice.objects.filter(
                character=self.character,
                technique=self.technique,
                definition=self.definition,
            )

            if self.pk:
                existing = existing.exclude(pk=self.pk)

        if self.character_id and self.selected_specialization_id:
            duplicate_specialization_choice = CharacterTechniqueChoice.objects.filter(
                character_id=self.character_id,
                selected_specialization_id=self.selected_specialization_id,
            ).exclude(pk=self.pk)
            if duplicate_specialization_choice.exists():
                raise ValidationError(
                    {"selected_specialization": "This specialization has already been chosen for this character."}
                )

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


class CharacterRaceChoice(models.Model):
    """A persistent character-bound choice made for the active race."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="race_choices")
    definition = models.ForeignKey(
        RaceChoiceDefinition,
        on_delete=models.CASCADE,
        related_name="character_choices",
    )
    selected_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_race_choices",
    )
    selected_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_race_choices",
    )
    selected_item = models.ForeignKey(
        "Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_race_choices",
    )
    selected_item_category = models.CharField(max_length=30, blank=True, default="")
    selected_specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_race_choices",
    )
    selected_text = models.CharField(max_length=255, blank=True, default="")
    selected_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="character_race_choice_targets",
    )
    selected_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    selected_entity = GenericForeignKey("selected_content_type", "selected_object_id")

    class Meta:
        ordering = ["character__name", "definition__race__name", "definition__sort_order", "definition__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "definition", "selected_skill"],
                condition=models.Q(selected_skill__isnull=False),
                name="uniq_character_race_choice_selected_skill",
            ),
            models.UniqueConstraint(
                fields=["character", "definition", "selected_skill_category"],
                condition=models.Q(selected_skill_category__isnull=False),
                name="uniq_character_race_choice_selected_category",
            ),
            models.UniqueConstraint(
                fields=["character", "definition", "selected_item"],
                condition=models.Q(selected_item__isnull=False),
                name="uniq_character_race_choice_selected_item",
            ),
            models.UniqueConstraint(
                fields=["character", "definition", "selected_specialization"],
                condition=models.Q(selected_specialization__isnull=False),
                name="uniq_character_race_choice_selected_specialization",
            ),
            models.UniqueConstraint(
                fields=["character", "definition", "selected_item_category"],
                condition=~models.Q(selected_item_category=""),
                name="uniq_character_race_choice_selected_item_category",
            ),
            models.UniqueConstraint(
                fields=["character", "definition", "selected_content_type", "selected_object_id"],
                condition=models.Q(selected_object_id__isnull=False),
                name="uniq_character_race_choice_selected_entity",
            ),
        ]

    def clean(self):
        """Validate stored race choice targets with model-local checks only."""
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
            raise ValidationError("A race choice must select exactly one persistent target.")
        if self.character_id and self.definition_id and self.character.race_id != self.definition.race_id:
            raise ValidationError({"definition": "The selected race choice definition must belong to the character's race."})
        expected_kind = self.definition.target_kind if self.definition_id else Technique.ChoiceTargetKind.NONE
        if expected_kind == Technique.ChoiceTargetKind.NONE:
            raise ValidationError({"definition": "This race choice definition must point at a concrete target kind."})
        self._validate_target_kind(expected_kind)
        if (
            self.definition_id
            and expected_kind == Technique.ChoiceTargetKind.SKILL
            and self.selected_skill_id
        ):
            if (
                self.definition.allowed_skill_category_id
                and self.selected_skill.category_id != self.definition.allowed_skill_category_id
            ):
                raise ValidationError({
                    "selected_skill": "The selected skill does not belong to the allowed skill category."
                })
            if (
                self.definition.allowed_skill_family
                and self.selected_skill.family != self.definition.allowed_skill_family
            ):
                raise ValidationError({
                    "selected_skill": "The selected skill does not belong to the allowed skill family."
                })
        if self.definition_id and self.character_id:
            existing = CharacterRaceChoice.objects.filter(
                character=self.character,
                definition=self.definition,
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if self.definition.max_choices and existing.count() >= self.definition.max_choices:
                raise ValidationError("Maximum number of choices for this race definition exceeded.")

    def _validate_target_kind(self, expected_kind):
        """Ensure the selected target fields match the configured race choice kind."""
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
            raise ValidationError({"definition": "Unsupported race choice target kind."})
        if expected_kind == Technique.ChoiceTargetKind.ITEM_CATEGORY and (
            not self.selected_item_category or self.selected_item_category not in allowed_item_categories
        ):
            errors["selected_item_category"] = "Select a valid item category."
        elif expected_kind == Technique.ChoiceTargetKind.ENTITY:
            if not self.selected_content_type_id or self.selected_object_id is None:
                errors["selected_content_type"] = "This race choice requires another entity target."
        elif expected_kind == Technique.ChoiceTargetKind.TEXT:
            if not self.selected_text:
                errors["selected_text"] = "This race choice requires a free-text choice."
        elif getattr(self, f"{required_field}_id", None) is None and not getattr(self, required_field):
            errors[required_field] = f"This race choice requires a {expected_kind.replace('_', ' ')} selection."

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
        """Return a readable label for the chosen race target."""
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
        return f"{self.character.name} -> {self.definition.name}: {self.selected_target_display()}"


class RaceTechnique(models.Model):
    race = models.ForeignKey(
        Race,
        on_delete=models.CASCADE,
        related_name="techniques",
    )
    technique = models.ForeignKey(
        Technique,
        on_delete=models.CASCADE,
        related_name="race_links",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["race", "technique"],
                name="uniq_race_technique",
            )
        ]


class Aspect(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    opposite = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opposed_by",
    )

    class Meta:
        ordering = ["name"]

    def clean(self):
        super().clean()
        if self.opposite_id and self.opposite_id == self.id:
            raise ValidationError({"opposite": "An aspect cannot oppose itself."})

    def __str__(self):
        return self.name


class DivineEntity(models.Model):
    class EntityKind(models.TextChoices):
        GOD = "god", "God"
        ANCESTOR = "ancestor", "Ancestor Spirit"
        TOTEM = "totem", "Totem / Power Animal"

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="divine_entities",
        help_text="The divine school through which this entity is worshipped.",
    )

    entity_kind = models.CharField(max_length=20, choices=EntityKind.choices)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DivineEntityAspect(models.Model):
    entity = models.ForeignKey(
        DivineEntity,
        on_delete=models.CASCADE,
        related_name="aspects",
    )
    aspect = models.ForeignKey(
        Aspect,
        on_delete=models.CASCADE,
        related_name="divine_entities",
    )
    is_starting_aspect = models.BooleanField(
        default=True,
        help_text="Marks one of the default aspects granted by the entity.",
    )

    class Meta:
        ordering = ["entity__name", "aspect__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "aspect"],
                name="uniq_divine_entity_aspect",
            )
        ]

    def __str__(self):
        return f"{self.entity.name}: {self.aspect.name}"


class CharacterAspect(models.Model):
    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="aspect_entries",
    )
    aspect = models.ForeignKey(
        Aspect,
        on_delete=models.PROTECT,
        related_name="character_entries",
    )
    level = models.PositiveSmallIntegerField(default=1)

    source_entity = models.ForeignKey(
        DivineEntity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_character_aspects",
    )
    is_bonus_aspect = models.BooleanField(
        default=False,
        help_text="True if this aspect was purchased separately instead of granted by entity.",
    )

    class Meta:
        ordering = ["character", "aspect__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "aspect"],
                name="uniq_character_aspect",
            )
        ]

    def clean(self):
        super().clean()
        if self.level < 1:
            raise ValidationError({"level": "Aspect level must be at least 1."})

        if self.character_id and self.source_entity_id:
            if not CharacterSchool.objects.filter(
                character_id=self.character_id,
                school_id=self.source_entity.school_id,
            ).exists():
                raise ValidationError(
                    {"source_entity": "The character does not know the school of the granting entity."}
                )

        if self.character_id and self.aspect_id:
            opposite = self.aspect.opposite_id
            if opposite and CharacterAspect.objects.exclude(pk=self.pk).filter(
                character_id=self.character_id,
                aspect_id=opposite,
            ).exists():
                raise ValidationError(
                    {"aspect": "The character already knows the opposing aspect."}
                )

    def __str__(self):
        return f"{self.character.name}: {self.aspect.name} {self.level}"


class CharacterDivineEntity(models.Model):
    character = models.OneToOneField(
        "Character",
        on_delete=models.CASCADE,
        related_name="divine_entity_binding",
    )
    entity = models.ForeignKey(
        DivineEntity,
        on_delete=models.PROTECT,
        related_name="followers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character"],
                name="uniq_character_divine_entity",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.character_id
            and self.entity_id
            and not CharacterSchool.objects.filter(
                character_id=self.character_id,
                school_id=self.entity.school_id,
            ).exists()
        ):
            raise ValidationError(
                {"entity": "A character can only bind to a divine entity of a learned school."}
            )

    def __str__(self):
        return f"{self.character.name} -> {self.entity.name}"


class CharacterSpellSource(models.Model):
    class SourceKind(models.TextChoices):
        TRAIT = "trait", "Trait"
        ADMIN = "admin", "Admin"
        MANUAL = "manual", "Manual"

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="spell_bonus_sources",
    )
    source_kind = models.CharField(max_length=20, choices=SourceKind.choices, default=SourceKind.TRAIT)
    trait = models.ForeignKey(
        Trait,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="character_spell_sources",
    )
    label = models.CharField(max_length=120, blank=True, default="")
    capacity = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["character", "source_kind", "label", "id"]

    def clean(self):
        super().clean()
        if self.capacity < 1:
            raise ValidationError({"capacity": "Bonus spell capacity must be at least 1."})
        if self.source_kind == self.SourceKind.TRAIT and self.trait_id is None:
            raise ValidationError({"trait": "Trait-based bonus spell sources require a trait."})

    def __str__(self):
        label = self.label or (self.trait.name if self.trait_id else self.get_source_kind_display())
        return f"{self.character.name}: {label} ({self.capacity})"


class Spell(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="spells",
        null=True,
        blank=True,
        help_text="Used for arcane spells.",
    )
    aspect = models.ForeignKey(
        Aspect,
        on_delete=models.CASCADE,
        related_name="spells",
        null=True,
        blank=True,
        help_text="Used for divine spells.",
    )

    spell_attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        related_name="spells",
        null=True,
        blank=True,
        )
    grade = models.PositiveSmallIntegerField()
    grade_adds_school_level = models.BooleanField(
        default=False,
        help_text=(
            "Wenn aktiv, berechnet sich der effektive Grad als Grad + aktuelle Schulstufe des Charakters. "
            "Z.B. Grad 2 bei Schulstufe 3 = effektiver Grad 5."
        ),
    )
    is_base_spell = models.BooleanField(default=False)

    description = models.TextField(blank=True, default="")
    panel_badge_label = models.CharField(max_length=30, blank=True, default="Zauber")
    kp_cost = models.PositiveSmallIntegerField(default=0)
    cast_time = models.CharField(max_length=100, blank=True, default="")  # legacy

    class CastTimeUnit(models.TextChoices):
        ACTION = "Aktion", "Aktion"
        MINUTE = "Minute", "Minute"
        HOUR = "Stunde", "Stunde"

    cast_time_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Zeitaufwand")
    cast_time_unit = models.CharField(
        max_length=20, blank=True, default="", choices=CastTimeUnit.choices, verbose_name="Einheit",
    )
    range_text = models.CharField(max_length=100, blank=True, default="")  # legacy

    class RangeUnit(models.TextChoices):
        METER = "m", "Meter"
        KM = "km", "Kilometer"
        TOUCH = "Berührung", "Berührung"
        SELF = "selbst", "Selbst"

    range_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Reichweite")
    range_unit = models.CharField(
        max_length=20,
        blank=True,
        default="",
        choices=RangeUnit.choices,
        verbose_name="Einheit",
    )
    range_per_grade = models.BooleanField(default=False, verbose_name="pro Stufe")
    duration_text = models.CharField(max_length=100, blank=True, default="")  # legacy

    class DurationUnit(models.TextChoices):
        INSTANT = "sofort", "Sofort"
        ROUND = "Runde", "Runde"
        SCENE = "Szene", "Szene"
        PERMANENT = "permanent", "Permanent"
        HOUR = "Stunde", "Stunde"
        MINUTE = "Minute", "Minute"

    duration_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Wirkungsdauer")
    duration_unit = models.CharField(
        max_length=20, blank=True, default="", choices=DurationUnit.choices, verbose_name="Einheit",
    )
    duration_per_grade = models.BooleanField(default=False, verbose_name="pro Stufe")
    mw = models.PositiveSmallIntegerField("MW", null=True, blank=True)
    resistance_value = models.CharField("Widerstandswert", max_length=100, blank=True, default="")

    class Meta:
        ordering = ["school__name", "aspect__name", "grade", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "slug"],
                condition=models.Q(school__isnull=False),
                name="uniq_spell_school_slug",
            ),
            models.UniqueConstraint(
                fields=["aspect", "slug"],
                condition=models.Q(aspect__isnull=False),
                name="uniq_spell_aspect_slug",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.is_base_spell:
            if not self.school_id and not self.aspect_id:
                raise ValidationError("A spell must belong to either a school or an aspect.")
            if self.school_id and self.aspect_id:
                raise ValidationError("A spell cannot belong to both a school and an aspect.")

    def __str__(self):
        if self.school_id:
            owner = self.school.name
        elif self.aspect_id:
            owner = self.aspect.name
        else:
            owner = "Basis"
        return f"{owner} G{self.grade}: {self.name}"


class CharacterSpell(models.Model):
    class SourceKind(models.TextChoices):
        ARCANE_FREE = "arcane_free", "Arcane Free Choice"
        ARCANE_EXTRA = "arcane_extra", "Arcane Extra Spell"
        ARCANE_BONUS = "arcane_bonus", "Arcane Bonus Spell"
        DIVINE_GRANTED = "divine_granted", "Divine Granted"
        DIVINE_EXTRA = "divine_extra", "Divine Extra Spell"
        DIVINE_BONUS = "divine_bonus", "Divine Bonus Spell"
        BASE = "base", "Base Spell"
        MANUAL = "manual", "Manual"

    character = models.ForeignKey(
        "Character",
        on_delete=models.CASCADE,
        related_name="known_spells",
    )
    spell = models.ForeignKey(
        Spell,
        on_delete=models.PROTECT,
        related_name="character_entries",
    )
    source_kind = models.CharField(
        max_length=30,
        choices=SourceKind.choices,
        default=SourceKind.MANUAL,
    )
    bonus_source = models.ForeignKey(
        CharacterSpellSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_spells",
    )
    learned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["character", "spell__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "spell"],
                name="uniq_character_spell",
            )
        ]

    def clean(self):
        super().clean()

        if self.bonus_source_id and self.bonus_source.character_id != self.character_id:
            raise ValidationError({"bonus_source": "Bonus spell source must belong to the same character."})

        if self.character_id and self.spell_id and self.spell.school_id:
            if not CharacterSchool.objects.filter(
                character_id=self.character_id,
                school_id=self.spell.school_id,
            ).exists():
                raise ValidationError(
                    {"spell": "A character can only know arcane spells from learned schools."}
                )

        if self.character_id and self.spell_id and self.spell.aspect_id:
            if not CharacterAspect.objects.filter(
                character_id=self.character_id,
                aspect_id=self.spell.aspect_id,
            ).exists():
                raise ValidationError(
                    {"spell": "A character can only know divine spells from learned aspects."}
                )

    def __str__(self):
        return f"{self.character.name} knows {self.spell.name}"
