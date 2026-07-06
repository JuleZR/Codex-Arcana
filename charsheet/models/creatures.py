"""Creature definition and per-character creature instance models."""
import json

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils.text import slugify

from ..constants import (
    ATTRIBUTE_CODE_CHOICES,
    ATTR_CHA,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_SPEC,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DAMAGE_TYPE_CHOICES,
    GK_AVERAGE,
    GK_CHOICES,
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    PROFICIENCY_GROUP_CHOICES,
    QUALITY_COMMON,
    QUALITY_EXCELLENT,
    QUALITY_FINE,
    QUALITY_LEGENDARY,
    QUALITY_POOR,
    QUALITY_VERY_POOR,
    QUALITY_WRETCHED,
    RESOURCE_KEY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
    STAT_SLUG_CHOICES,
    TARGET_DOMAIN_CHOICES,
)
from .core import Attribute, Skill, SkillCategory
from .items import Item
from .progression import Specialization


ATTRIBUTE_FIELD_MAP = {
    ATTR_ST: "strength_mod",
    ATTR_KON: "constitution_mod",
    ATTR_GE: "dexterity_mod",
    ATTR_INT: "intelligence_mod",
    ATTR_WA: "perception_mod",
    ATTR_WILL: "willpower_mod",
    ATTR_CHA: "charisma_mod",
}

ATTRIBUTE_PROPERTY_CODES = {
    "strength_mod": ATTR_ST,
    "constitution_mod": ATTR_KON,
    "dexterity_mod": ATTR_GE,
    "intelligence_mod": ATTR_INT,
    "perception_mod": ATTR_WA,
    "willpower_mod": ATTR_WILL,
    "charisma_mod": ATTR_CHA,
}


CREATURE_CARD_QUALITY_TRAINING_BUDGETS = {
    QUALITY_WRETCHED: (0, 3),
    QUALITY_VERY_POOR: (0, 2),
    QUALITY_POOR: (0, 1),
    QUALITY_COMMON: (0, 0),
    QUALITY_FINE: (4, 0),
    QUALITY_EXCELLENT: (8, 0),
    QUALITY_LEGENDARY: (12, 0),
}


class Creature(models.Model):
    """Reusable creature template with Attribute-referenced creature stats."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    card_name = models.CharField(max_length=100, blank=True, default="")
    image = models.ImageField(upload_to="creatures/", blank=True, null=True)
    description = models.TextField(blank=True, default="")
    quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="quality",
        on_delete=models.PROTECT,
        related_name="creatures",
        default=QUALITY_COMMON,
    )
    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)
    size_modifier = models.IntegerField(default=0)
    initiative_override = models.IntegerField(blank=True, null=True)
    vw_override = models.IntegerField(blank=True, null=True)
    sr_override = models.IntegerField(blank=True, null=True)
    gw_override = models.IntegerField(blank=True, null=True)
    defense_extra_label = models.CharField("GW extra label", max_length=20, blank=True, default="")
    fear_resistance_bonus = models.IntegerField("GW extra value", blank=True, null=True)
    natural_rs = models.PositiveIntegerField(default=0)
    wound_step_override = models.PositiveIntegerField(blank=True, null=True)
    combat_speed = models.FloatField(blank=True, null=True, default=0, validators=[MinValueValidator(0)])
    march_speed = models.FloatField(blank=True, null=True, default=0, validators=[MinValueValidator(0)])
    sprint_speed = models.FloatField(blank=True, null=True, default=0, validators=[MinValueValidator(0)])
    swimming_speed = models.FloatField("Schwimmgeschwindigkeit", blank=True, null=True, validators=[MinValueValidator(0)])
    combat_swimming_speed = models.FloatField("Kampf-Schwimmen", blank=True, null=True, validators=[MinValueValidator(0)])
    march_swimming_speed = models.FloatField("Marsch-Schwimmen", blank=True, null=True, validators=[MinValueValidator(0)])
    sprint_swimming_speed = models.FloatField("Sprint-Schwimmen", blank=True, null=True, validators=[MinValueValidator(0)])
    combat_fly_speed = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    march_fly_speed = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    sprint_fly_speed = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    climate_and_occurrence = models.TextField(blank=True, default="")
    organization = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        blocks = {
            "Boden": ("combat_speed", "march_speed", "sprint_speed"),
            "Schwimmen": ("combat_swimming_speed", "march_swimming_speed", "sprint_swimming_speed"),
            "Flug": ("combat_fly_speed", "march_fly_speed", "sprint_fly_speed"),
        }
        complete_blocks = 0
        errors = {}
        for label, fields in blocks.items():
            filled_fields = [
                field_name
                for field_name in fields
                if getattr(self, field_name, None) not in (None, "")
            ]
            if not filled_fields:
                continue
            if len(filled_fields) == len(fields):
                complete_blocks += 1
                continue
            message = f"{label} muss entweder leer oder komplett ausgefuellt sein."
            for field_name in fields:
                errors[field_name] = message
        if complete_blocks == 0:
            message = "Mindestens ein Bewegungsblock muss komplett ausgefuellt sein."
            for field_name in blocks["Boden"]:
                errors.setdefault(field_name, message)
        if errors:
            raise ValidationError(errors)

    @property
    def display_name(self):
        return self.card_name or self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = (slugify(self.name) or "creature")[:90]
            slug = base_slug
            suffix = 2
            existing = Creature.objects.all()
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            while existing.filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)
        self.ensure_attribute_rows()

    def ensure_attribute_rows(self):
        """Create missing rows for all regular Attribute entries."""
        if not self.pk:
            return
        existing_ids = set(self.attributes.values_list("attribute_id", flat=True))
        CreatureAttribute.objects.bulk_create(
            CreatureAttribute(creature=self, attribute=attribute, base_value=0)
            for attribute in Attribute.objects.exclude(short_name=ATTR_SPEC)
            if attribute.pk not in existing_ids
        )

    def attribute_modifier(self, code):
        for row in self.attributes.select_related("attribute"):
            if row.attribute.slug == code or row.attribute.short_name == code:
                return row.base_value
        return None if code == ATTR_CHA else 0

    def _attribute_property(self, field_name):
        return self.attribute_modifier(ATTRIBUTE_PROPERTY_CODES[field_name])

    @property
    def strength_mod(self):
        return self._attribute_property("strength_mod")

    @property
    def constitution_mod(self):
        return self._attribute_property("constitution_mod")

    @property
    def dexterity_mod(self):
        return self._attribute_property("dexterity_mod")

    @property
    def intelligence_mod(self):
        return self._attribute_property("intelligence_mod")

    @property
    def perception_mod(self):
        return self._attribute_property("perception_mod")

    @property
    def willpower_mod(self):
        return self._attribute_property("willpower_mod")

    @property
    def charisma_mod(self):
        return self._attribute_property("charisma_mod")


class CreatureAttribute(models.Model):
    """Stores one creature attribute value, linked to the shared Attribute table."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="attributes")
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    base_value = models.IntegerField(blank=True, null=True, default=0)

    class Meta:
        ordering = ["creature", "attribute"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "attribute"], name="uniq_creature_attribute"),
        ]

    def __str__(self):
        value = "-" if self.base_value is None else f"{self.base_value:+d}"
        return f"{self.creature} - {self.attribute}: {value}"

    @property
    def modifier(self):
        return self.base_value


class CreatureAttack(models.Model):
    class DamageOperator(models.TextChoices):
        NONE = "", "Kein Operator"
        ADD = "+", "+"
        SUBTRACT = "-", "-"
        DIVIDE = "/", "/"

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="attacks")
    name = models.CharField(max_length=100)
    attack_value = models.IntegerField(default=0)
    damage_dice_amount = models.PositiveIntegerField(default=0)
    damage_dice_faces = models.PositiveIntegerField(default=0)
    damage_flat_operator = models.CharField(max_length=1, choices=DamageOperator.choices, default=DamageOperator.NONE, blank=True)
    damage_flat_bonus = models.IntegerField(default=0)
    damage_type = models.CharField(max_length=1, choices=DAMAGE_TYPE_CHOICES, blank=True, default="")
    notes = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.creature}: {self.name}"


class CreatureSkill(models.Model):
    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["creature", "skill"],
                name="uniq_creature_skill",
            )
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.level}"

    @property
    def value(self):
        return self.level


class CreatureSpecialSkill(models.Model):
    """Creature-only skill definition, separate from normal character skills."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CreatureSpecialSkillValue(models.Model):
    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="special_skills")
    skill = models.ForeignKey(CreatureSpecialSkill, on_delete=models.PROTECT)
    value = models.IntegerField(default=0)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [models.UniqueConstraint(fields=["creature", "skill"], name="uniq_creature_special_skill")]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.value:+d}"


class CreatureCommand(models.Model):
    """Separate creature command/action text."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    ep_cost = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    difficulty = models.PositiveIntegerField(blank=True, null=True)
    prerequisites = models.ManyToManyField(
        "self",
        through="CreatureCommandPrerequisite",
        symmetrical=False,
        related_name="unlocks",
        blank=True,
    )
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def training_days(self):
        return int(self.ep_cost * 10)

    @property
    def prerequisite_groups(self):
        groups = []
        current_group = None
        current_commands = []
        for link in self.prerequisite_links.select_related("prerequisite"):
            if current_group is None:
                current_group = link.alternative_group
            if link.alternative_group != current_group:
                groups.append(current_commands)
                current_group = link.alternative_group
                current_commands = []
            current_commands.append(link.prerequisite)
        if current_commands:
            groups.append(current_commands)
        return groups

    @property
    def prerequisite_display(self):
        return " & ".join("/".join(command.name for command in group) for group in self.prerequisite_groups)


class CreatureCommandPrerequisite(models.Model):
    command = models.ForeignKey(
        CreatureCommand,
        on_delete=models.CASCADE,
        related_name="prerequisite_links",
    )
    prerequisite = models.ForeignKey(
        CreatureCommand,
        on_delete=models.CASCADE,
        related_name="required_by_links",
    )
    alternative_group = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["alternative_group", "order", "prerequisite__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["command", "prerequisite", "alternative_group"],
                name="uniq_creature_command_prerequisite_group",
            ),
        ]

    def __str__(self):
        return f"{self.command}: {self.prerequisite}"


class CreatureCommandReference(models.Model):
    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="commands")
    command = models.ForeignKey(CreatureCommand, on_delete=models.PROTECT, related_name="creature_references")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "command__name"]
        constraints = [models.UniqueConstraint(fields=["creature", "command"], name="uniq_creature_command")]

    def __str__(self):
        return f"{self.creature}: {self.command}"


class CreatureTraitDefinition(models.Model):
    """Trait definition used only by creatures."""

    class TraitType(models.TextChoices):
        ADV = "advantage", "Advantage"
        DIS = "disadvantage", "Disadvantage"

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    trait_type = models.CharField(max_length=20, choices=TraitType.choices)
    description = models.TextField(blank=True, default="")
    min_level = models.PositiveIntegerField(default=1)
    max_level = models.PositiveIntegerField(default=1)
    points_per_level = models.PositiveIntegerField(default=1)
    points_by_level = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional comma-separated per-level costs such as '1,3' or '2,4,6'. Overrides points_per_level.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
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

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = (slugify(self.name) or "creature-trait")[:90]
            slug = base_slug
            suffix = 2
            existing = CreatureTraitDefinition.objects.all()
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            while existing.filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)


class CreatureTraitChoiceDefinition(models.Model):
    """A persistent choice definition belonging to one creature trait."""

    class TargetKind(models.TextChoices):
        ATTRIBUTE = "attribute", "Attribute"
        SKILL = "skill", "Skill"
        SKILL_CATEGORY = "skill_category", "Skill Category"
        DERIVED_STAT = "derived_stat", "Derived Stat"
        RESOURCE = "resource", "Resource"
        PROFICIENCY_GROUP = "proficiency_group", "Proficiency Group"
        ITEM = "item", "Item"
        ITEM_CATEGORY = "item_category", "Item Category"
        SPECIALIZATION = "specialization", "Specialization"
        TEXT = "text", "Free Text"
        ENTITY = "entity", "Other Entity"

    trait = models.ForeignKey(CreatureTraitDefinition, on_delete=models.CASCADE, related_name="choice_definitions")
    name = models.CharField(max_length=120)
    target_kind = models.CharField(max_length=20, choices=TargetKind.choices)
    description = models.TextField(blank=True, default="")
    min_choices = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(0)])
    max_choices = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    is_required = models.BooleanField(default=True)
    allowed_attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="creature_trait_choice_definitions",
    )
    allowed_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="creature_trait_choice_definitions",
    )
    allowed_skill_family = models.SlugField(max_length=50, blank=True, default="")
    allowed_derived_stat = models.CharField(max_length=50, blank=True, default="", choices=STAT_SLUG_CHOICES)
    allowed_resource = models.CharField(max_length=50, blank=True, default="", choices=RESOURCE_KEY_CHOICES)
    allowed_proficiency_group = models.CharField(max_length=50, blank=True, default="", choices=PROFICIENCY_GROUP_CHOICES)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["trait__trait_type", "trait__name", "sort_order", "name", "id"]

    def clean(self):
        super().clean()
        if self.max_choices < self.min_choices:
            raise ValidationError({"max_choices": "max_choices must be greater than or equal to min_choices."})
        if not self.is_required and self.min_choices != 0:
            raise ValidationError({"min_choices": "Optional choice definitions must use min_choices = 0."})
        if self.target_kind != self.TargetKind.ATTRIBUTE and self.allowed_attribute_id:
            raise ValidationError({"allowed_attribute": "This filter is only valid for attribute choices."})
        if self.target_kind != self.TargetKind.SKILL:
            if self.allowed_skill_category_id:
                raise ValidationError({"allowed_skill_category": "This filter is only valid for skill choices."})
            if self.allowed_skill_family:
                raise ValidationError({"allowed_skill_family": "This filter is only valid for skill choices."})
        if self.target_kind != self.TargetKind.DERIVED_STAT and self.allowed_derived_stat:
            raise ValidationError({"allowed_derived_stat": "This filter is only valid for derived-stat choices."})
        if self.target_kind != self.TargetKind.RESOURCE and self.allowed_resource:
            raise ValidationError({"allowed_resource": "This filter is only valid for resource choices."})
        if self.target_kind != self.TargetKind.PROFICIENCY_GROUP and self.allowed_proficiency_group:
            raise ValidationError({"allowed_proficiency_group": "This filter is only valid for proficiency-group choices."})

    def __str__(self) -> str:
        return f"{self.trait.name}: {self.name}"


class CreatureTraitSemanticEffect(models.Model):
    """Persisted semantic effect attached directly to one creature trait definition."""

    trait = models.ForeignKey(CreatureTraitDefinition, on_delete=models.CASCADE, related_name="semantic_effects")
    sort_order = models.PositiveIntegerField(default=0)
    target_choice_definition = models.ForeignKey(
        CreatureTraitChoiceDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="semantic_effects",
    )
    target_skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name="creature_trait_semantic_effects",
        help_text="Optional concrete skill targets. Use this instead of target_key for multi-skill effects.",
    )
    target_domain = models.CharField(max_length=40, choices=TARGET_DOMAIN_CHOICES, default="rule_flag")
    target_key = models.CharField(max_length=120, blank=True, default="")
    operator = models.CharField(max_length=40, choices=MODIFIER_OPERATOR_CHOICES, default="flat_add")
    mode = models.CharField(max_length=20, default="flat")
    value = models.CharField(max_length=200, blank=True, default="")
    value_min = models.IntegerField(null=True, blank=True)
    value_max = models.IntegerField(null=True, blank=True)
    formula = models.CharField(max_length=200, blank=True, default="")
    scaling = models.JSONField(default=dict, blank=True)
    stack_behavior = models.CharField(max_length=40, choices=STACK_BEHAVIOR_CHOICES, default="stack")
    condition_set = models.JSONField(default=dict, blank=True)
    active_flag = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    rules_text = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=20, choices=MODIFIER_VISIBILITY_CHOICES, default="public")
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
        super().clean()
        if self.scaling is not None and not isinstance(self.scaling, dict):
            raise ValidationError({"scaling": "Scaling must be a JSON object."})
        if self.condition_set is not None and not isinstance(self.condition_set, dict):
            raise ValidationError({"condition_set": "Condition set must be a JSON object."})
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "Metadata must be a JSON object."})
        if self.target_choice_definition_id and self.target_choice_definition.trait_id != self.trait_id:
            raise ValidationError({"target_choice_definition": "The selected choice definition must belong to the same creature trait."})

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
            ProficiencyGroupModifier,
            ResourceModifier,
            ResistanceModifier,
            RuleFlagModifier,
            SkillModifier,
            SocialModifier,
            TraitModifier,
        )

        modifier_map = {
            "skill": SkillModifier,
            "skill_rank": SkillModifier,
            "skill_rank_cap": SkillModifier,
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
                "kind": "creature_trait_choice_definition",
                "id": int(self.target_choice_definition_id),
            }
        if self.pk:
            selected_skill_slugs = list(self.target_skills.order_by("slug").values_list("slug", flat=True))
            if selected_skill_slugs:
                metadata["target_skill_slugs"] = selected_skill_slugs
        return modifier_cls(
            source_type="creature_trait",
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


class CreatureTrait(models.Model):
    """Purchased/listed creature-only trait level for a creature template."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="traits")
    trait = models.ForeignKey(CreatureTraitDefinition, on_delete=models.CASCADE)
    trait_level = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["creature", "trait"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_creature_trait"),
        ]

    def __str__(self):
        return f"{self.creature}: {self.trait} ({self.trait_level})"

    def clean(self):
        super().clean()
        if self.trait_level > self.trait.max_level:
            raise ValidationError({"trait_level": "You can't purchase more levels of a trait than max level"})
        if self.trait_level < self.trait.min_level:
            raise ValidationError({"trait_level": f"Level must be at least {self.trait.min_level}."})

    @property
    def display_name(self):
        return self.trait.name

    @property
    def level(self):
        return self.trait_level

    @property
    def description(self):
        return self.trait.description

    @property
    def order(self):
        return 0


class CreatureSourceBinding(models.Model):
    class TriggerType(models.TextChoices):
        ITEM = "item", "Item"
        TECHNIQUE = "technique", "Technique"

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="source_bindings", null=True)
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    item_trigger = models.ForeignKey(
        "charsheet.Item",
        on_delete=models.CASCADE,
        related_name="creature_source_bindings",
        blank=True,
        null=True,
    )
    technique_trigger = models.ForeignKey(
        "charsheet.Technique",
        on_delete=models.CASCADE,
        related_name="creature_source_bindings",
        blank=True,
        null=True,
    )
    quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="quality",
        on_delete=models.PROTECT,
        related_name="creature_source_bindings",
        default=QUALITY_COMMON,
        help_text="Quality used when this binding is triggered by a technique. Item-triggered creatures use the owned item's quality.",
    )
    active = models.BooleanField(default=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["creature__name", "trigger_type", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["creature", "item_trigger"],
                condition=models.Q(item_trigger__isnull=False),
                name="uniq_creature_source_item_binding",
            ),
            models.UniqueConstraint(
                fields=["creature", "technique_trigger"],
                condition=models.Q(technique_trigger__isnull=False),
                name="uniq_creature_source_technique_binding",
            ),
        ]

    def __str__(self):
        return f"{self.creature} via {self.trigger_label}"

    @property
    def trigger_label(self):
        if self.trigger_type == self.TriggerType.ITEM and self.item_trigger_id:
            return self.item_trigger.name
        if self.trigger_type == self.TriggerType.TECHNIQUE and self.technique_trigger_id:
            return self.technique_trigger.name
        return self.get_trigger_type_display()

    def clean(self):
        super().clean()
        if self.trigger_type == self.TriggerType.ITEM:
            if not self.item_trigger_id:
                raise ValidationError({"item_trigger": "Item-Trigger ist erforderlich."})
            if self.technique_trigger_id:
                raise ValidationError({"technique_trigger": "Bei Item-Trigger leer lassen."})
        if self.trigger_type == self.TriggerType.TECHNIQUE:
            if not self.technique_trigger_id:
                raise ValidationError({"technique_trigger": "Technik-Trigger ist erforderlich."})
            if self.item_trigger_id:
                raise ValidationError({"item_trigger": "Bei Technik-Trigger leer lassen."})


class CharacterCreature(models.Model):
    owner = models.ForeignKey("charsheet.Character", on_delete=models.CASCADE, related_name="creatures")
    creature = models.ForeignKey(Creature, on_delete=models.PROTECT, related_name="character_instances")
    source_binding = models.ForeignKey(
        CreatureSourceBinding,
        on_delete=models.PROTECT,
        related_name="character_creatures",
        blank=True,
        null=True,
    )
    source_character_item = models.ForeignKey(
        "charsheet.CharacterItem",
        on_delete=models.CASCADE,
        related_name="creatures",
        blank=True,
        null=True,
    )
    source_character_technique = models.ForeignKey(
        "charsheet.CharacterTechnique",
        on_delete=models.CASCADE,
        related_name="creatures",
        blank=True,
        null=True,
    )
    quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="quality",
        on_delete=models.PROTECT,
        related_name="character_creatures",
        default=QUALITY_COMMON,
    )
    name_override = models.CharField(max_length=100, blank=True, default="")
    image_override = models.ImageField(upload_to="character_creatures/", blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    current_damage = models.PositiveIntegerField(default=0)
    max_base_advantage_points = models.PositiveSmallIntegerField(default=0)
    max_base_disadvantage_points = models.PositiveSmallIntegerField(default=0)
    size_class_override = models.CharField(max_length=5, choices=GK_CHOICES, blank=True, default="")
    size_modifier_override = models.IntegerField(blank=True, null=True)
    strength_mod_override = models.IntegerField(blank=True, null=True)
    constitution_mod_override = models.IntegerField(blank=True, null=True)
    dexterity_mod_override = models.IntegerField(blank=True, null=True)
    intelligence_mod_override = models.IntegerField(blank=True, null=True)
    perception_mod_override = models.IntegerField(blank=True, null=True)
    willpower_mod_override = models.IntegerField(blank=True, null=True)
    charisma_mod_override = models.IntegerField(blank=True, null=True)
    initiative_override = models.IntegerField(blank=True, null=True)
    vw_override = models.IntegerField(blank=True, null=True)
    sr_override = models.IntegerField(blank=True, null=True)
    gw_override = models.IntegerField(blank=True, null=True)
    defense_extra_label_override = models.CharField("GW extra label override", max_length=20, blank=True, default="")
    fear_resistance_bonus_override = models.IntegerField("GW extra value override", blank=True, null=True)
    natural_rs_override = models.PositiveIntegerField(blank=True, null=True)
    wound_step_override = models.PositiveIntegerField(blank=True, null=True)
    combat_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    march_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    sprint_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    swimming_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    combat_fly_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    march_fly_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    sprint_fly_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["owner", "creature", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "source_binding"],
                condition=models.Q(source_binding__isnull=False, source_character_item__isnull=True, source_character_technique__isnull=True),
                name="uniq_character_creature_source_binding_legacy",
            ),
            models.UniqueConstraint(
                fields=["owner", "source_binding", "source_character_item"],
                condition=models.Q(source_character_item__isnull=False),
                name="uniq_character_creature_item_source",
            ),
            models.UniqueConstraint(
                fields=["owner", "source_binding", "source_character_technique"],
                condition=models.Q(source_character_technique__isnull=False),
                name="uniq_character_creature_technique_source",
            ),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.owner})"

    @property
    def display_name(self):
        return self.name_override or self.creature.display_name

    @property
    def image(self):
        return self.image_override or self.creature.image

    @property
    def trigger_label(self):
        if self.source_binding_id:
            return self.source_binding.trigger_label
        return ""

    @classmethod
    def training_budget_defaults(cls, quality):
        quality_code = getattr(quality, "code", quality) or QUALITY_COMMON
        advantage_points, disadvantage_points = CREATURE_CARD_QUALITY_TRAINING_BUDGETS.get(
            quality_code,
            CREATURE_CARD_QUALITY_TRAINING_BUDGETS[QUALITY_COMMON],
        )
        return {
            "max_base_advantage_points": advantage_points,
            "max_base_disadvantage_points": disadvantage_points,
        }

    @property
    def base_disadvantage_points_spent(self):
        return sum(row.point_cost for row in self.trait_overrides.all() if row.point_source == CharacterCreatureTrait.PointSource.BASE_DISADVANTAGE)

    @property
    def additional_disadvantage_points_spent(self):
        return sum(row.point_cost for row in self.trait_overrides.all() if row.point_source == CharacterCreatureTrait.PointSource.ADDITIONAL_DISADVANTAGE)

    @property
    def advantage_points_spent(self):
        return sum(row.point_cost for row in self.trait_overrides.all() if row.training_trait_type == CharacterCreatureTrait.TrainingTraitType.ADVANTAGE)

    @property
    def bonus_advantage_points(self):
        return min(self.additional_disadvantage_points_spent, 4)

    @property
    def effective_advantage_points(self):
        return int(self.max_base_advantage_points or 0) + self.bonus_advantage_points

    @property
    def effective_disadvantage_points(self):
        return int(self.max_base_disadvantage_points or 0) + 4


class CharacterCreatureItem(models.Model):
    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("charsheet.Item", on_delete=models.PROTECT)
    amount = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="quality",
        on_delete=models.PROTECT,
        related_name="creature_items",
        default=QUALITY_COMMON,
    )
    notes = models.TextField(blank=True, default="")
    armor_rs_head_override = models.PositiveIntegerField(blank=True, null=True)
    armor_rs_torso_override = models.PositiveIntegerField(blank=True, null=True)
    armor_rs_arm_left_override = models.PositiveIntegerField(blank=True, null=True)
    armor_rs_arm_right_override = models.PositiveIntegerField(blank=True, null=True)
    armor_rs_leg_left_override = models.PositiveIntegerField(blank=True, null=True)
    armor_rs_leg_right_override = models.PositiveIntegerField(blank=True, null=True)
    armor_rs_total_override = models.PositiveIntegerField(blank=True, null=True)
    armor_encumbrance_override = models.PositiveIntegerField(blank=True, null=True)
    armor_min_st_override = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["creature", "item__name"]

    def __str__(self):
        return f"{self.creature}: {self.item} x{self.amount}"


class CharacterCreatureSkill(models.Model):
    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="skill_overrides")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    level_override = models.IntegerField(validators=[MinValueValidator(0)])
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["creature", "skill"],
                name="uniq_character_creature_skill",
            )
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.level_override}"

    @property
    def value_override(self):
        return self.level_override

    @property
    def name(self):
        return self.skill.name

    @property
    def value(self):
        return self.level_override


class CharacterCreatureSpecialSkill(models.Model):
    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="special_skill_overrides")
    skill = models.ForeignKey(CreatureSpecialSkill, on_delete=models.PROTECT)
    value_override = models.IntegerField()
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "skill"], name="uniq_character_creature_special_skill")
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.value_override:+d}"


class CharacterCreatureTrait(models.Model):
    class TrainingTraitType(models.TextChoices):
        NONE = "", "Keine Ausbildung"
        ADVANTAGE = "advantage", "Vorzug"
        DISADVANTAGE = "disadvantage", "Schwäche"

    class PointSource(models.TextChoices):
        NONE = "", "Keine Budgetwirkung"
        BASE_DISADVANTAGE = "base_disadvantage", "Basis-Schwäche"
        ADDITIONAL_DISADVANTAGE = "additional_disadvantage", "Zusatzschwäche"

    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="trait_overrides")
    base_trait = models.ForeignKey(CreatureTrait, on_delete=models.PROTECT, blank=True, null=True)
    trait = models.ForeignKey(CreatureTraitDefinition, on_delete=models.CASCADE)
    trait_level = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    training_trait_type = models.CharField(max_length=20, choices=TrainingTraitType.choices, blank=True, default="")
    point_source = models.CharField(max_length=30, choices=PointSource.choices, blank=True, default="")
    point_cost_override = models.PositiveSmallIntegerField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["creature", "order", "trait"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "trait"], name="uniq_character_creature_trait"),
        ]

    def __str__(self):
        return f"{self.creature}: {self.trait} ({self.trait_level})"

    def clean(self):
        super().clean()
        if self.trait_level > self.trait.max_level:
            raise ValidationError({"trait_level": "You can't purchase more levels of a trait than max level"})
        if self.trait_level < self.trait.min_level:
            raise ValidationError({"trait_level": f"Level must be at least {self.trait.min_level}."})

    @property
    def display_name(self):
        return self.trait.name

    @property
    def level_override(self):
        return self.trait_level

    @property
    def level(self):
        return self.trait_level

    @property
    def description_override(self):
        return self.trait.description

    @property
    def description(self):
        return self.trait.description

    @property
    def point_cost(self):
        if self.point_cost_override is not None:
            return int(self.point_cost_override)
        return int(self.trait.cost_for_level(int(self.trait_level or 1)))


class CharacterCreatureCommand(models.Model):
    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="commands")
    command = models.ForeignKey(
        CreatureCommand,
        on_delete=models.PROTECT,
        related_name="character_creature_commands",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "command__name"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "command"], name="uniq_character_creature_command"),
        ]

    def __str__(self):
        return f"{self.creature}: {self.command}"

    @property
    def name(self):
        return self.command.name

    @property
    def slug(self):
        return self.command.slug

    @property
    def ep_cost(self):
        return self.command.ep_cost

    @property
    def difficulty(self):
        return self.command.difficulty

    @property
    def description(self):
        return self.command.description

    @property
    def prerequisite_groups(self):
        groups = []
        current_group = None
        current_commands = []
        for link in self.prerequisite_links.select_related("prerequisite__command"):
            if current_group is None:
                current_group = link.alternative_group
            if link.alternative_group != current_group:
                groups.append(current_commands)
                current_group = link.alternative_group
                current_commands = []
            current_commands.append(link.prerequisite)
        if current_commands:
            groups.append(current_commands)
        return groups

    @property
    def prerequisite_display(self):
        return " & ".join("/".join(command.name for command in group) for group in self.prerequisite_groups)

    @property
    def training_days(self):
        return self.command.training_days


class CharacterCreatureCommandPrerequisite(models.Model):
    command = models.ForeignKey(
        CharacterCreatureCommand,
        on_delete=models.CASCADE,
        related_name="prerequisite_links",
    )
    prerequisite = models.ForeignKey(
        CharacterCreatureCommand,
        on_delete=models.CASCADE,
        related_name="required_by_links",
    )
    alternative_group = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["alternative_group", "order", "prerequisite__command__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["command", "prerequisite", "alternative_group"],
                name="uniq_character_creature_command_prerequisite_group",
            ),
        ]

    def __str__(self):
        return f"{self.command}: {self.prerequisite}"

    def clean(self):
        super().clean()
        if self.command_id and self.prerequisite_id and self.command.creature_id != self.prerequisite.creature_id:
            raise ValidationError({"prerequisite": "Prerequisite must belong to the same character creature."})


class CharacterCreatureAttributeIncrease(models.Model):
    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="attribute_increases")
    attribute = models.CharField(max_length=10, choices=ATTRIBUTE_CODE_CHOICES)
    amount = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["attribute", "id"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "attribute"], name="uniq_character_creature_attribute_increase"),
        ]

    def __str__(self):
        return f"{self.creature}: {self.attribute} +{self.amount}"


class CreatureTraitChoiceSelection(models.Model):
    """Shared selected-target fields for concrete creature trait choices."""

    selected_attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    selected_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    selected_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    selected_derived_stat = models.CharField(max_length=50, blank=True, default="", choices=STAT_SLUG_CHOICES)
    selected_resource = models.CharField(max_length=50, blank=True, default="", choices=RESOURCE_KEY_CHOICES)
    selected_proficiency_group = models.CharField(max_length=50, blank=True, default="", choices=PROFICIENCY_GROUP_CHOICES)
    selected_item = models.ForeignKey(Item, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    selected_item_category = models.CharField(max_length=30, blank=True, default="")
    selected_specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    selected_text = models.CharField(max_length=255, blank=True, default="")
    selected_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    selected_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    selected_entity = GenericForeignKey("selected_content_type", "selected_object_id")

    class Meta:
        abstract = True

    def _clean_selected_target(self, *, owning_trait_id, existing_choices):
        if self.selected_content_type_id and self.selected_object_id is None:
            raise ValidationError({"selected_object_id": "Set an object id when selecting another entity."})
        if self.selected_object_id is not None and not self.selected_content_type_id:
            raise ValidationError({"selected_content_type": "Select a content type when using another entity."})
        populated_targets = [
            self.selected_attribute_id is not None,
            self.selected_skill_id is not None,
            self.selected_skill_category_id is not None,
            bool(self.selected_derived_stat),
            bool(self.selected_resource),
            bool(self.selected_proficiency_group),
            self.selected_item_id is not None,
            bool(self.selected_item_category),
            self.selected_specialization_id is not None,
            bool(self.selected_text),
            self.selected_object_id is not None,
        ]
        if sum(populated_targets) != 1:
            raise ValidationError("A creature trait choice must select exactly one persistent target.")
        if self.definition_id and owning_trait_id and owning_trait_id != self.definition.trait_id:
            raise ValidationError({"definition": "The selected choice definition must belong to the same creature trait."})
        self._validate_target_kind(self.definition.target_kind if self.definition_id else "")
        if (
            self.definition_id
            and self.definition.target_kind == CreatureTraitChoiceDefinition.TargetKind.ATTRIBUTE
            and self.selected_attribute_id
            and self.definition.allowed_attribute_id
            and self.selected_attribute_id != self.definition.allowed_attribute_id
        ):
            raise ValidationError({"selected_attribute": "The selected attribute does not match the allowed attribute."})
        if (
            self.definition_id
            and self.definition.target_kind == CreatureTraitChoiceDefinition.TargetKind.SKILL
            and self.selected_skill_id
        ):
            if (
                self.definition.allowed_skill_category_id
                and self.selected_skill.category_id != self.definition.allowed_skill_category_id
            ):
                raise ValidationError({"selected_skill": "The selected skill does not belong to the allowed skill category."})
            if self.definition.allowed_skill_family and self.selected_skill.family != self.definition.allowed_skill_family:
                raise ValidationError({"selected_skill": "The selected skill does not belong to the allowed skill family."})
        if (
            self.definition_id
            and self.definition.target_kind == CreatureTraitChoiceDefinition.TargetKind.DERIVED_STAT
            and self.definition.allowed_derived_stat
            and self.selected_derived_stat != self.definition.allowed_derived_stat
        ):
            raise ValidationError({"selected_derived_stat": "The selected derived stat does not match the allowed derived stat."})
        if (
            self.definition_id
            and self.definition.target_kind == CreatureTraitChoiceDefinition.TargetKind.RESOURCE
            and self.definition.allowed_resource
            and self.selected_resource != self.definition.allowed_resource
        ):
            raise ValidationError({"selected_resource": "The selected resource does not match the allowed resource."})
        if (
            self.definition_id
            and self.definition.target_kind == CreatureTraitChoiceDefinition.TargetKind.PROFICIENCY_GROUP
            and self.definition.allowed_proficiency_group
            and self.selected_proficiency_group != self.definition.allowed_proficiency_group
        ):
            raise ValidationError({"selected_proficiency_group": "The selected proficiency group does not match the allowed group."})
        if self.definition_id:
            existing = existing_choices.filter(definition=self.definition)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if self.definition.max_choices and existing.count() >= self.definition.max_choices:
                raise ValidationError({"definition": "Maximum number of choices for this creature trait definition exceeded."})

    def _validate_target_kind(self, expected_kind: str):
        errors = {}
        allowed_item_categories = {choice for choice, _label in Item.ItemType.choices}
        target_field_by_kind = {
            CreatureTraitChoiceDefinition.TargetKind.ATTRIBUTE: "selected_attribute",
            CreatureTraitChoiceDefinition.TargetKind.SKILL: "selected_skill",
            CreatureTraitChoiceDefinition.TargetKind.SKILL_CATEGORY: "selected_skill_category",
            CreatureTraitChoiceDefinition.TargetKind.DERIVED_STAT: "selected_derived_stat",
            CreatureTraitChoiceDefinition.TargetKind.RESOURCE: "selected_resource",
            CreatureTraitChoiceDefinition.TargetKind.PROFICIENCY_GROUP: "selected_proficiency_group",
            CreatureTraitChoiceDefinition.TargetKind.ITEM: "selected_item",
            CreatureTraitChoiceDefinition.TargetKind.ITEM_CATEGORY: "selected_item_category",
            CreatureTraitChoiceDefinition.TargetKind.SPECIALIZATION: "selected_specialization",
            CreatureTraitChoiceDefinition.TargetKind.TEXT: "selected_text",
            CreatureTraitChoiceDefinition.TargetKind.ENTITY: "selected_content_type",
        }
        required_field = target_field_by_kind.get(expected_kind)
        if required_field is None:
            raise ValidationError({"definition": "Unsupported creature trait choice target kind."})
        if expected_kind == CreatureTraitChoiceDefinition.TargetKind.ITEM_CATEGORY and (
            not self.selected_item_category or self.selected_item_category not in allowed_item_categories
        ):
            errors["selected_item_category"] = "Select a valid item category."
        elif expected_kind == CreatureTraitChoiceDefinition.TargetKind.ENTITY:
            if not self.selected_content_type_id or self.selected_object_id is None:
                errors["selected_content_type"] = "This creature trait choice requires another entity target."
        elif expected_kind == CreatureTraitChoiceDefinition.TargetKind.TEXT:
            if not self.selected_text:
                errors["selected_text"] = "This creature trait choice requires a free-text choice."
        elif getattr(self, f"{required_field}_id", None) is None and not getattr(self, required_field):
            errors[required_field] = f"This creature trait choice requires a {expected_kind.replace('_', ' ')} selection."

        disallowed_fields = {
            "selected_attribute",
            "selected_skill",
            "selected_skill_category",
            "selected_derived_stat",
            "selected_resource",
            "selected_proficiency_group",
            "selected_item",
            "selected_item_category",
            "selected_specialization",
            "selected_text",
            "selected_content_type",
            "selected_object_id",
        } - {required_field}
        if expected_kind == CreatureTraitChoiceDefinition.TargetKind.ENTITY:
            disallowed_fields -= {"selected_object_id"}
        for field_name in disallowed_fields:
            value = getattr(self, field_name)
            if value not in (None, "", 0):
                errors[field_name] = "This field does not match the configured choice kind."
        if errors:
            raise ValidationError(errors)

    def selected_target_display(self) -> str:
        if self.selected_attribute is not None:
            return f"{self.selected_attribute.name} ({self.selected_attribute.short_name})"
        if self.selected_skill is not None:
            return self.selected_skill.name
        if self.selected_skill_category is not None:
            return self.selected_skill_category.name
        if self.selected_derived_stat:
            return dict(STAT_SLUG_CHOICES).get(self.selected_derived_stat, self.selected_derived_stat)
        if self.selected_resource:
            return dict(RESOURCE_KEY_CHOICES).get(self.selected_resource, self.selected_resource)
        if self.selected_proficiency_group:
            return dict(PROFICIENCY_GROUP_CHOICES).get(self.selected_proficiency_group, self.selected_proficiency_group)
        if self.selected_item is not None:
            return self.selected_item.name
        if self.selected_item_category:
            return self.selected_item_category
        if self.selected_specialization is not None:
            return self.selected_specialization.name
        if self.selected_text:
            return self.selected_text
        if self.selected_entity is not None:
            return str(self.selected_entity)
        return "-"

    def resolved_modifier_target(self) -> tuple[str, str] | None:
        if self.selected_attribute is not None:
            return ("attribute", self.selected_attribute.short_name)
        if self.selected_skill is not None:
            return ("skill", self.selected_skill.slug)
        if self.selected_skill_category is not None:
            return ("skill_category", self.selected_skill_category.slug)
        if self.selected_derived_stat:
            return ("derived_stat", self.selected_derived_stat)
        if self.selected_resource:
            return ("resource", self.selected_resource)
        if self.selected_proficiency_group:
            return ("proficiency_group", self.selected_proficiency_group)
        if self.selected_item is not None:
            return ("item", str(self.selected_item_id))
        if self.selected_item_category:
            return ("item_category", self.selected_item_category)
        if self.selected_specialization is not None:
            return ("specialization", str(self.selected_specialization_id))
        if self.selected_text:
            return ("metadata", self.selected_text)
        if self.selected_object_id is not None:
            return ("entity", f"{self.selected_content_type_id}:{self.selected_object_id}")
        return None


class CreatureTraitChoice(CreatureTraitChoiceSelection):
    """A persisted choice made for one base creature trait row."""

    creature_trait = models.ForeignKey(CreatureTrait, on_delete=models.CASCADE, related_name="choices")
    definition = models.ForeignKey(
        CreatureTraitChoiceDefinition,
        on_delete=models.CASCADE,
        related_name="creature_choices",
    )

    class Meta:
        ordering = ["creature_trait__creature__name", "creature_trait__trait__name", "definition__sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_attribute"], condition=models.Q(selected_attribute__isnull=False), name="uniq_creature_trait_choice_attribute"),
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_skill"], condition=models.Q(selected_skill__isnull=False), name="uniq_creature_trait_choice_skill"),
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_skill_category"], condition=models.Q(selected_skill_category__isnull=False), name="uniq_creature_trait_choice_category"),
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_item"], condition=models.Q(selected_item__isnull=False), name="uniq_creature_trait_choice_item"),
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_specialization"], condition=models.Q(selected_specialization__isnull=False), name="uniq_creature_trait_choice_specialization"),
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_item_category"], condition=~models.Q(selected_item_category=""), name="uniq_creature_trait_choice_item_category"),
            models.UniqueConstraint(fields=["creature_trait", "definition", "selected_content_type", "selected_object_id"], condition=models.Q(selected_object_id__isnull=False), name="uniq_creature_trait_choice_entity"),
        ]

    def clean(self):
        super().clean()
        self._clean_selected_target(
            owning_trait_id=self.creature_trait.trait_id if self.creature_trait_id else None,
            existing_choices=CreatureTraitChoice.objects.filter(creature_trait=self.creature_trait) if self.creature_trait_id else CreatureTraitChoice.objects.none(),
        )

    def __str__(self) -> str:
        return f"{self.creature_trait.creature.name} -> {self.definition.name}: {self.selected_target_display()}"


class CharacterCreatureTraitChoice(CreatureTraitChoiceSelection):
    """A persisted choice made for one character-owned creature trait row."""

    character_creature_trait = models.ForeignKey(
        CharacterCreatureTrait,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    definition = models.ForeignKey(
        CreatureTraitChoiceDefinition,
        on_delete=models.CASCADE,
        related_name="character_creature_choices",
    )

    class Meta:
        ordering = [
            "character_creature_trait__creature__owner__name",
            "character_creature_trait__trait__name",
            "definition__sort_order",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_attribute"], condition=models.Q(selected_attribute__isnull=False), name="uniq_character_creature_trait_choice_attribute"),
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_skill"], condition=models.Q(selected_skill__isnull=False), name="uniq_character_creature_trait_choice_skill"),
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_skill_category"], condition=models.Q(selected_skill_category__isnull=False), name="uniq_character_creature_trait_choice_category"),
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_item"], condition=models.Q(selected_item__isnull=False), name="uniq_character_creature_trait_choice_item"),
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_specialization"], condition=models.Q(selected_specialization__isnull=False), name="uniq_character_creature_trait_choice_specialization"),
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_item_category"], condition=~models.Q(selected_item_category=""), name="uniq_character_creature_trait_choice_item_category"),
            models.UniqueConstraint(fields=["character_creature_trait", "definition", "selected_content_type", "selected_object_id"], condition=models.Q(selected_object_id__isnull=False), name="uniq_character_creature_trait_choice_entity"),
        ]

    def clean(self):
        super().clean()
        self._clean_selected_target(
            owning_trait_id=self.character_creature_trait.trait_id if self.character_creature_trait_id else None,
            existing_choices=CharacterCreatureTraitChoice.objects.filter(character_creature_trait=self.character_creature_trait) if self.character_creature_trait_id else CharacterCreatureTraitChoice.objects.none(),
        )

    def __str__(self) -> str:
        return f"{self.character_creature_trait.creature.display_name} -> {self.definition.name}: {self.selected_target_display()}"

