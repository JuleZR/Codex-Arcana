"""Legacy rule modifier model used as source data by the modifier engine."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from ..constants import ATTRIBUTE_CODE_CHOICES, VALID_STAT_SLUGS
from .core import Skill, SkillCategory, Trait
from .items import Item
from .progression import School, Specialization


class Modifier(models.Model):
    """A rule modifier sourced from races, schools, traits, or techniques.

    This is the legacy modifier format.  The modifier engine translates these
    rows into typed modifiers at runtime.  New rule effects should use
    TraitSemanticEffect instead of adding rows here.
    """

    class TargetKind(models.TextChoices):
        SKILL = "skill", "Skill"
        CATEGORY = "category", "Skill Category"
        ATTRIBUTE = "attribute", "Attribute"
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
        SKILL_LEVEL = "skill_level", "Skill level"
        SKILL_TOTAL = "skill_total", "Skill total"
        RUNE_CRAFTER_LEVEL = "rune_crafter_level", "Rune crafter level"

    class RoundMode(models.TextChoices):
        FLOOR = "floor", "Floor"
        CEIL = "ceil", "Ceil"

    class CapMode(models.TextChoices):
        NONE = "none", "None"
        MIN = "min", "Min"
        MAX = "max", "Max"

    # --- Source (what grants this modifier) ---

    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="modifier_source_relations",
    )
    source_object_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_content_type", "source_object_id")

    # --- Target (what stat or entity is affected) ---

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
    # Optional: modifier targets the result of a persistent technique choice.
    target_choice_definition = models.ForeignKey(
        "TechniqueChoiceDefinition",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="targeting_modifiers",
    )
    # Optional: modifier targets the result of a persistent race choice.
    target_race_choice_definition = models.ForeignKey(
        "RaceChoiceDefinition",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="targeting_modifiers",
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

    # --- Value and scaling ---

    effect_description = models.CharField(max_length=255, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
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
    scale_skill = models.ForeignKey(
        Skill,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="scale_modifiers",
        help_text="Only used if scale_source or cap_source uses a skill-based value.",
    )
    mul = models.SmallIntegerField(default=1)
    div = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    round_mode = models.CharField(max_length=10, choices=RoundMode.choices, default=RoundMode.FLOOR)

    # --- Cap ---

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
        # Lazy import to avoid circular dependency: modifier.py ↔ techniques.py
        from .techniques import Technique

        super().clean()
        allowed_item_categories = {choice for choice, _label in Item.ItemType.choices}

        # Target content type and object id must be set together.
        if self.target_content_type_id and self.target_object_id is None:
            raise ValidationError({"target_object_id": "Set an object id when a target content type is selected."})
        if self.target_object_id is not None and not self.target_content_type_id:
            raise ValidationError({"target_content_type": "Select a content type when a target object id is set."})

        # Cannot point at both a technique choice and a race choice simultaneously.
        if self.target_choice_definition_id and self.target_race_choice_definition_id:
            raise ValidationError(
                {
                    "target_race_choice_definition": (
                        "Select either a technique choice definition or a race choice definition, not both."
                    )
                }
            )

        # Technique-choice-targeted modifiers must match the choice's target kind.
        if self.target_choice_definition_id:
            expected_kind = self.target_choice_definition.target_kind
            choice_kind_mapping = {
                Technique.ChoiceTargetKind.SKILL: self.TargetKind.SKILL,
                Technique.ChoiceTargetKind.SKILL_CATEGORY: self.TargetKind.CATEGORY,
                Technique.ChoiceTargetKind.ITEM: self.TargetKind.ITEM,
                Technique.ChoiceTargetKind.ITEM_CATEGORY: self.TargetKind.ITEM_CATEGORY,
                Technique.ChoiceTargetKind.SPECIALIZATION: self.TargetKind.SPECIALIZATION,
                Technique.ChoiceTargetKind.ENTITY: self.TargetKind.ENTITY,
            }
            mapped_kind = choice_kind_mapping.get(expected_kind)
            if mapped_kind is None:
                raise ValidationError(
                    {"target_choice_definition": "The selected choice definition target kind is not supported by modifiers."}
                )
            if self.target_kind != mapped_kind:
                raise ValidationError(
                    {"target_choice_definition": "The choice definition target kind must match the modifier target kind."}
                )

        # Race-choice-targeted modifiers must match the choice's target kind.
        if self.target_race_choice_definition_id:
            expected_kind = self.target_race_choice_definition.target_kind
            choice_kind_mapping = {
                Technique.ChoiceTargetKind.SKILL: self.TargetKind.SKILL,
                Technique.ChoiceTargetKind.SKILL_CATEGORY: self.TargetKind.CATEGORY,
                Technique.ChoiceTargetKind.ITEM: self.TargetKind.ITEM,
                Technique.ChoiceTargetKind.ITEM_CATEGORY: self.TargetKind.ITEM_CATEGORY,
                Technique.ChoiceTargetKind.SPECIALIZATION: self.TargetKind.SPECIALIZATION,
                Technique.ChoiceTargetKind.ENTITY: self.TargetKind.ENTITY,
            }
            mapped_kind = choice_kind_mapping.get(expected_kind)
            if mapped_kind is None:
                raise ValidationError(
                    {"target_race_choice_definition": "The selected race choice definition target kind is not supported."}
                )
            if self.target_kind != mapped_kind:
                raise ValidationError(
                    {"target_race_choice_definition": "The race choice definition target kind must match the modifier target kind."}
                )

        # Per-kind target field validation.
        valid_stat_or_attribute_slugs = VALID_STAT_SLUGS | {value for value, _label in ATTRIBUTE_CODE_CHOICES}

        if self.target_kind == self.TargetKind.ATTRIBUTE:
            if self.target_slug not in {value for value, _label in ATTRIBUTE_CODE_CHOICES}:
                raise ValidationError({"target_slug": "Invalid target slug for kind ATTRIBUTE."})
            self._require_empty_target_fields(
                "ATTRIBUTE",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_choice_definition",
                "target_race_choice_definition",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.STAT:
            if self.target_slug not in valid_stat_or_attribute_slugs:
                raise ValidationError({"target_slug": "Invalid target slug for kind STAT."})
            self._require_empty_target_fields(
                "STAT",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_choice_definition",
                "target_race_choice_definition",
                "target_content_type",
                "target_object_id",
            )
        elif self.target_kind == self.TargetKind.SKILL:
            self._validate_target_selector(
                label="SKILL",
                slug_field="target_slug",
                slug_validator=lambda slug: Skill.objects.filter(slug=slug).exists(),
                object_fields=("target_skill", "target_choice_definition", "target_race_choice_definition"),
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
                object_fields=("target_skill_category", "target_choice_definition", "target_race_choice_definition"),
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
            self._validate_target_selector(
                label="ITEM",
                slug_field="target_slug",
                slug_validator=lambda _slug: False,
                object_fields=("target_item", "target_choice_definition", "target_race_choice_definition"),
            )
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
            if (
                not self.target_choice_definition_id
                and not self.target_race_choice_definition_id
                and (not self.target_slug or self.target_slug not in allowed_item_categories)
            ):
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
            self._validate_target_selector(
                label="SPECIALIZATION",
                slug_field="target_slug",
                slug_validator=lambda _slug: False,
                object_fields=("target_specialization", "target_choice_definition", "target_race_choice_definition"),
            )
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
            if (
                not self.target_choice_definition_id
                and not self.target_race_choice_definition_id
                and (not self.target_content_type_id or self.target_object_id is None)
            ):
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

        # Scaling configuration.
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
        skill_scale_sources = {self.ScaleSource.SKILL_LEVEL, self.ScaleSource.SKILL_TOTAL}
        item_rune_scale_sources = {self.ScaleSource.RUNE_CRAFTER_LEVEL}
        non_school_scale_sources = skill_scale_sources | item_rune_scale_sources | {
            self.ScaleSource.FAME_TOTAL,
            self.ScaleSource.TRAIT_LVL,
        }

        if self.scale_school_id and self.scale_source != self.ScaleSource.SCHOOL_LEVEL:
            raise ValidationError({"scale_school": "scale_school is only allowed for school-level scaling."})
        if self.scale_skill_id and self.scale_source not in skill_scale_sources and self.cap_source not in skill_scale_sources:
            raise ValidationError({"scale_skill": "scale_skill is only allowed for skill-based scaling or caps."})
        if self.scale_source in skill_scale_sources and not self.scale_skill_id:
            raise ValidationError({"scale_skill": "scale_skill is required for skill-based scaling."})
        if self.cap_source in skill_scale_sources and not self.scale_skill_id:
            raise ValidationError({"scale_skill": "scale_skill is required for skill-based caps."})
        if (
            self.target_kind not in {self.TargetKind.ATTRIBUTE, self.TargetKind.STAT}
            and (self.scale_source in skill_scale_sources or self.cap_source in skill_scale_sources)
        ):
            raise ValidationError(
                {"target_kind": "Skill-based scaling and caps are currently only supported for attribute/stat targets."}
            )
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
            and self.scale_source not in non_school_scale_sources
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
        """Return the canonical lookup identifier used by the modifier engine."""
        if self.target_kind == self.TargetKind.ATTRIBUTE:
            return self.target_slug
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
        """Return a human-readable label for the configured target."""
        if self.target_choice_definition_id:
            choice_label = self.target_choice_definition.name
        elif self.target_race_choice_definition_id:
            choice_label = self.target_race_choice_definition.name
        else:
            choice_label = ""
        if self.target_kind == self.TargetKind.SKILL:
            value = self.target_skill.name if self.target_skill_id else self.target_slug
            return f"{value} [{choice_label}]" if choice_label else value
        if self.target_kind == self.TargetKind.ATTRIBUTE:
            value = dict(ATTRIBUTE_CODE_CHOICES).get(self.target_slug, self.target_slug)
            return f"{value} [{choice_label}]" if choice_label else value
        if self.target_kind == self.TargetKind.CATEGORY:
            value = self.target_skill_category.name if self.target_skill_category_id else self.target_slug
            return f"{value} [{choice_label}]" if choice_label else value
        if self.target_kind == self.TargetKind.ITEM and self.target_item_id:
            value = self.target_item.name
            return f"{value} [{choice_label}]" if choice_label else value
        if self.target_kind == self.TargetKind.SPECIALIZATION and self.target_specialization_id:
            value = self.target_specialization.name
            return f"{value} [{choice_label}]" if choice_label else value
        if self.target_kind == self.TargetKind.ENTITY and self.target is not None:
            value = str(self.target)
            return f"{value} [{choice_label}]" if choice_label else value
        value = self.target_slug or "-"
        return f"{value} [{choice_label}]" if choice_label else value

    def __str__(self):
        effect_suffix = f" [{self.effect_description}]" if self.effect_description else ""
        return f"{self.source} -> {self.target_kind}:{self.target_display()}{effect_suffix}"
