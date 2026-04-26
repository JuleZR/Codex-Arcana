"""Reference models shared across the character sheet domain."""

import json

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ..constants import (
    ATTRIBUTE_CODE_CHOICES,
    GK_AVERAGE,
    GK_CHOICES,
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    SKILL_CATEGORY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
    TARGET_DOMAIN_CHOICES,
)


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
    family = models.SlugField(max_length=50, blank=True)
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
    swimming_speed = models.FloatField(default=0, validators=[MinValueValidator(0)])

    can_fly = models.BooleanField(default=False)
    combat_fly_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)], null=True, blank=True)
    march_fly_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)], null=True, blank=True)
    sprint_fly_speed = models.IntegerField(default=0, validators=[MinValueValidator(0)], null=True, blank=True)

    phase_1_points = models.PositiveIntegerField(default=40)
    phase_2_points = models.PositiveIntegerField(default=50)
    phase_3_points = models.PositiveIntegerField(default=20, validators=[MaxValueValidator(20)])
    phase_4_points = models.PositiveIntegerField(default=30)

    size_class = models.CharField("SizeClass", max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)

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
    points_by_level = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional comma-separated per-level costs such as '1,3' or '2,4,6'. Overrides points_per_level.",
    )
    excluded_traits = models.ManyToManyField(
        "self",
        through="TraitExclusion",
        symmetrical=False,
        related_name="excluded_by_traits",
        blank=True,
    )

    def clean(self):
        """Keep configured trait level bounds consistent."""
        super().clean()
        if self.max_level < self.min_level:
            raise ValidationError("Max level < min level is prohibited.")
        try:
            curve = self.cost_curve()
        except ValueError:
            raise ValidationError({"points_by_level": "Use a comma-separated list of whole numbers."})
        if curve and len(curve) != int(self.max_level):
            raise ValidationError({"points_by_level": "Provide exactly one cost per level up to max_level."})
        if any(value < 0 for value in curve):
            raise ValidationError({"points_by_level": "Trait costs must be non-negative."})

    def cost_curve(self) -> tuple[int, ...]:
        """Return explicit per-level costs when configured."""
        raw = str(self.points_by_level or "").strip()
        if not raw:
            return ()
        values: list[int] = []
        for part in raw.split(","):
            token = str(part).strip()
            if not token:
                continue
            values.append(int(token))
        return tuple(values)

    def uses_cost_curve(self) -> bool:
        """Return whether this trait uses explicit per-level costs."""
        return bool(self.cost_curve())

    def cost_for_level(self, level: int) -> int:
        """Return the cumulative cost/refund for the selected level."""
        rank = int(level)
        if rank <= 0:
            return 0
        curve = self.cost_curve()
        if curve:
            return int(sum(curve[:rank]))
        return rank * int(self.points_per_level)

    def level_cost(self, level: int) -> int:
        """Return the incremental cost of exactly one selected level."""
        rank = int(level)
        if rank <= 0:
            return 0
        curve = self.cost_curve()
        if curve:
            return int(curve[rank - 1])
        return int(self.points_per_level)

    def cost_display(self) -> str:
        """Return a compact editor-facing cost label."""
        curve = self.cost_curve()
        if curve:
            return ",".join(str(value) for value in curve)
        return f"{int(self.points_per_level)}/Lvl"

    def __str__(self):
        return self.name


class TraitExclusion(models.Model):
    """A symmetric exclusion relation between two traits."""

    trait = models.ForeignKey(Trait, on_delete=models.CASCADE, related_name="exclusions")
    excluded_trait = models.ForeignKey(Trait, on_delete=models.CASCADE, related_name="excluded_by")

    class Meta:
        ordering = ["trait__trait_type", "trait__name", "excluded_trait__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["trait", "excluded_trait"],
                name="uniq_trait_exclusion_direction",
            ),
        ]

    def clean(self):
        """Block self-references and mirrored duplicates."""
        super().clean()
        if self.trait_id and self.excluded_trait_id and self.trait_id == self.excluded_trait_id:
            raise ValidationError({"excluded_trait": "A trait cannot exclude itself."})
        if (
            self.trait_id
            and self.excluded_trait_id
            and TraitExclusion.objects.exclude(pk=self.pk).filter(
                trait_id=self.excluded_trait_id,
                excluded_trait_id=self.trait_id,
            ).exists()
        ):
            raise ValidationError("This exclusion pair already exists in reverse order.")

    def __str__(self) -> str:
        return f"{self.trait.name} excludes {self.excluded_trait.name}"


class TraitSemanticEffect(models.Model):
    """Persisted new-system semantic effect attached directly to one trait."""

    trait = models.ForeignKey(Trait, on_delete=models.CASCADE, related_name="semantic_effects")
    sort_order = models.PositiveIntegerField(default=0)
    target_choice_definition = models.ForeignKey(
        "TraitChoiceDefinition",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="semantic_effects",
    )

    target_domain = models.CharField(
        max_length=40,
        choices=TARGET_DOMAIN_CHOICES,
        default="rule_flag",
    )
    target_key = models.CharField(max_length=120, blank=True, default="")
    operator = models.CharField(
        max_length=40,
        choices=MODIFIER_OPERATOR_CHOICES,
        default="flat_add",
    )
    mode = models.CharField(max_length=20, default="flat")

    value = models.CharField(max_length=200, blank=True, default="")
    value_min = models.IntegerField(null=True, blank=True)
    value_max = models.IntegerField(null=True, blank=True)
    formula = models.CharField(max_length=200, blank=True, default="")

    scaling = models.JSONField(default=dict, blank=True)
    stack_behavior = models.CharField(
        max_length=40,
        choices=STACK_BEHAVIOR_CHOICES,
        default="stack",
    )
    condition_set = models.JSONField(default=dict, blank=True)

    active_flag = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    rules_text = models.TextField(blank=True, default="")
    visibility = models.CharField(
        max_length=20,
        choices=MODIFIER_VISIBILITY_CHOICES,
        default="public",
    )
    hidden = models.BooleanField(default=False)
    sheet_relevant = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["trait", "sort_order", "id"]

    def __str__(self):
        return f"{self.trait.slug}: {self.target_domain}/{self.target_key} ({self.operator})"

    @staticmethod
    def _coerce_scalar(raw_value):
        """Coerce admin-entered text values into bool, int, float, JSON, or plain text."""
        text = str(raw_value or "").strip()
        if text == "":
            return None
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        try:
            return json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        try:
            return int(text)
        except (TypeError, ValueError):
            pass
        try:
            return float(text)
        except (TypeError, ValueError):
            pass
        return text

    def clean(self):
        """Validate JSON-like admin payloads before save."""
        super().clean()
        if self.scaling is not None and not isinstance(self.scaling, dict):
            raise ValidationError({"scaling": "Scaling must be a JSON object."})
        if self.condition_set is not None and not isinstance(self.condition_set, dict):
            raise ValidationError({"condition_set": "Condition set must be a JSON object."})
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "Metadata must be a JSON object."})
        if self.target_choice_definition_id and self.target_choice_definition.trait_id != self.trait_id:
            raise ValidationError({"target_choice_definition": "The selected trait choice definition must belong to the same trait."})
        if not self.target_choice_definition_id and not str(self.target_key or "").strip():
            raise ValidationError({"target_key": "Set a target key unless the effect is bound to a trait choice definition."})

    def to_modifier(self):
        """Materialize this persisted effect as one typed modifier instance."""
        from ..modifiers.definitions import (
            AttributeCapModifier,
            AttributeModifier,
            BaseModifier,
            CombatModifier,
            ConditionSet,
            DerivedStatModifier,
            EconomyModifier,
            LanguageModifier,
            MovementModifier,
            PerceptionModifier,
            ResourceModifier,
            ResistanceModifier,
            RuleFlagModifier,
            SkillModifier,
            SocialModifier,
            ProficiencyGroupModifier,
            TraitModifier,
        )

        modifier_map = {
            "skill": SkillModifier,
            "trait": TraitModifier,
            "language": LanguageModifier,
            "proficiency_group": ProficiencyGroupModifier,
            "attribute": AttributeModifier,
            "attribute_cap": AttributeCapModifier,
            "derived_stat": DerivedStatModifier,
            "resource": ResourceModifier,
            "resistance": ResistanceModifier,
            "movement": MovementModifier,
            "combat": CombatModifier,
            "perception": PerceptionModifier,
            "economy": EconomyModifier,
            "social": SocialModifier,
            "rule_flag": RuleFlagModifier,
        }
        modifier_cls = modifier_map.get(self.target_domain, BaseModifier)
        metadata = dict(self.metadata or {})
        if self.target_choice_definition_id:
            metadata["choice_binding"] = {
                "kind": "trait_choice_definition",
                "id": int(self.target_choice_definition_id),
            }
        return modifier_cls(
            source_type="trait",
            source_id=self.trait.slug,
            target_domain=self.target_domain,
            target_key=self.target_key,
            mode=self.mode,
            value=self._coerce_scalar(self.value),
            value_min=self.value_min,
            value_max=self.value_max,
            formula=self.formula,
            scaling=dict(self.scaling or {}),
            operator=self.operator,
            stack_behavior=self.stack_behavior,
            condition_set=ConditionSet(**dict(self.condition_set or {})),
            active_flag=bool(self.active_flag),
            priority=int(self.priority),
            notes=self.notes,
            rules_text=self.rules_text,
            visibility=self.visibility,
            hidden=bool(self.hidden),
            sheet_relevant=bool(self.sheet_relevant),
            metadata=metadata,
        )


class Language(models.Model):
    """Language definition with a configurable maximum mastery level."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    max_level = models.PositiveIntegerField(default=3)

    def __str__(self):
        return self.name
