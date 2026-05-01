"""Character-owned models and draft state."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ..constants import (
    DAMAGE_TYPE_CHOICES,
    GK_CHOICES,
    PROFICIENCY_GROUP_CHOICES,
    QUALITY_CHOICES,
    QUALITY_COMMON,
    RESOURCE_KEY_CHOICES,
    STAT_SLUG_CHOICES,
    WIELD_MODES,
)
from .core import Attribute, DamageSource, Language, Race, Skill, SkillCategory, Trait
from .items import Item, Rune
from .progression import Specialization


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
    appearance = models.TextField(max_length=100, null=True, blank=True)

    money = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    overall_experience = models.PositiveIntegerField(default=0)
    current_experience = models.PositiveIntegerField(default=0)

    current_damage = models.PositiveIntegerField(default=0)
    current_arcane_power = models.IntegerField(null=True, blank=True, default=0)
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

    def get_engine(self, *, refresh: bool = False, modifier_resolution_mode: str | None = None):
        """Return a reusable engine instance for repeated calculations."""
        cache_key = "_character_engine"
        cached_engine = self.__dict__.get(cache_key)
        normalized_mode = None if modifier_resolution_mode is None else str(modifier_resolution_mode).lower()
        cached_mode = getattr(cached_engine, "modifier_resolution_mode", None)
        cached_mode_value = getattr(cached_mode, "value", cached_mode)
        if (
            refresh
            or cached_engine is None
            or (
                modifier_resolution_mode is not None
                and str(cached_mode_value or "").lower() != normalized_mode
            )
        ):
            from ..engine import CharacterEngine

            self.__dict__[cache_key] = CharacterEngine(
                self,
                modifier_resolution_mode=modifier_resolution_mode,
            )
        return self.__dict__[cache_key]

    def get_magic_engine(self, *, refresh: bool = False):
        """Return a reusable magic engine instance for spell, aspect, and casting rules."""
        cache_key = "_character_magic_engine"
        cached_engine = self.__dict__.get(cache_key)
        if refresh or cached_engine is None:
            from ..engine.magic_engine import MagicEngine

            self.__dict__[cache_key] = MagicEngine(self)
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
            models.UniqueConstraint(
                fields=["character", "skill", "specification"],
                name="uniq_character_skill_specification",
            )
        ]

    def __str__(self):
        return f"{self.character} learned {self.skill}: {self.level}"


class CharacterItem(models.Model):
    """Ownership state of one item for one character."""

    item = models.ForeignKey("Item", on_delete=models.CASCADE)
    owner = models.ForeignKey(Character, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    equip_locked = models.BooleanField(default=False)
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default=QUALITY_COMMON)
    runes = models.ManyToManyField("Rune", blank=True, related_name="character_items")
    description = models.TextField(blank=True, default="")
    is_magic = models.BooleanField(default=False)
    magic_effect_summary = models.CharField(max_length=255, blank=True, default="")
    name_override = models.CharField(max_length=200, blank=True, default="")
    price_override = models.IntegerField(null=True, blank=True)
    weight_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    size_class_override = models.CharField(max_length=5, choices=GK_CHOICES, blank=True, default="")
    weapon_type_override = models.ForeignKey(
        "charsheet.WeaponType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_item_overrides",
    )
    weapon_min_st_override = models.PositiveIntegerField(null=True, blank=True)
    weapon_damage_source_override = models.ForeignKey(
        DamageSource,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_item_weapon_overrides",
    )
    weapon_damage_dice_amount_override = models.PositiveIntegerField(null=True, blank=True)
    weapon_damage_dice_faces_override = models.PositiveIntegerField(null=True, blank=True)
    weapon_damage_flat_bonus_override = models.IntegerField(null=True, blank=True)
    weapon_damage_flat_operator_override = models.CharField(max_length=1, blank=True, default="")
    weapon_damage_type_override = models.CharField(max_length=1, choices=DAMAGE_TYPE_CHOICES, blank=True, default="")
    weapon_wield_mode_override = models.CharField(max_length=2, choices=WIELD_MODES, blank=True, default="")
    weapon_h2_dice_amount_override = models.PositiveIntegerField(null=True, blank=True)
    weapon_h2_dice_faces_override = models.PositiveIntegerField(null=True, blank=True)
    weapon_h2_flat_bonus_override = models.IntegerField(null=True, blank=True)
    weapon_h2_flat_operator_override = models.CharField(max_length=1, blank=True, default="")
    armor_rs_head_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_torso_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_arm_left_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_arm_right_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_leg_left_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_leg_right_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_total_override = models.PositiveIntegerField(null=True, blank=True)
    armor_encumbrance_override = models.PositiveIntegerField(null=True, blank=True)
    armor_min_st_override = models.PositiveIntegerField(null=True, blank=True)
    shield_rs_override = models.PositiveIntegerField(null=True, blank=True)
    shield_encumbrance_override = models.PositiveIntegerField(null=True, blank=True)
    shield_min_st_override = models.PositiveIntegerField(null=True, blank=True)

    def clean(self):
        """Enforce stackability and equipment consistency."""
        super().clean()
        if not self.item.stackable and self.amount != 1:
            raise ValidationError({"amount": "Item is flagged non stackable. amount must be 1"})
        if self.item.stackable and self.equipped:
            raise ValidationError({"equipped": "Stackable Items can't be equipped"})
        if self.equip_locked and not self.equipped:
            raise ValidationError({"equip_locked": "Locked equipment must remain equipped."})

    def __str__(self):
        return f"{self.owner} owns {self.item}"

    @property
    def is_magic_effective(self) -> bool:
        """Return whether this owned entry behaves as a magic item."""
        return bool(self.is_magic or self.item.is_magic_effective)

    @property
    def effective_name(self) -> str:
        return (self.name_override or "").strip() or self.item.name

    def override_or_item_value(self, override_field: str, item_field: str):
        override_value = getattr(self, override_field)
        if override_value not in (None, ""):
            return override_value
        return getattr(self.item, item_field)


class ItemRune(models.Model):
    """Concrete rune assignment on one owned item, used as modifier source."""

    item = models.ForeignKey(
        CharacterItem,
        on_delete=models.CASCADE,
        related_name="item_runes",
    )
    rune = models.ForeignKey(
        Rune,
        on_delete=models.PROTECT,
        related_name="item_assignments",
    )
    crafter_level = models.PositiveSmallIntegerField(
        default=0,
        help_text="Waffenmeister-Stufe beim Anbringen oder Verbessern dieser Rune.",
    )
    allows_duplicate = models.BooleanField(
        default=False,
        editable=False,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item", "rune__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "rune"],
                condition=models.Q(allows_duplicate=False),
                name="unique_non_duplicate_rune_per_item",
            )
        ]

    def save(self, *args, **kwargs):
        self.allows_duplicate = self.rune.allow_multiple
        super().save(*args, **kwargs)

    def __str__(self):
        level = f" L{self.crafter_level}" if self.crafter_level else ""
        return f"{self.item} - {self.rune}{level}"


class CharacterItemRuneSpec(models.Model):
    """Stores a character's chosen specialization text for one rune slot on one owned item."""

    character_item = models.ForeignKey(CharacterItem, on_delete=models.CASCADE, related_name="rune_specs")
    rune = models.ForeignKey(Rune, on_delete=models.CASCADE, related_name="character_item_specs")
    specification = models.CharField(max_length=100, blank=True, default="")
    slot = models.PositiveSmallIntegerField(
        default=1,
        help_text="Slot-Nummer für mehrfach angewandte Runen (allow_multiple). Beginnt bei 1.",
    )

    class Meta:
        unique_together = [("character_item", "rune", "slot")]
        ordering = ["rune__name", "slot"]

    def __str__(self):
        if self.specification:
            return f"{self.rune.name} (Slot {self.slot}): {self.specification}"
        return f"{self.rune.name} (Slot {self.slot})"


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


class TraitChoiceDefinition(models.Model):
    """A persistent decision that belongs directly to one trait."""

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

    trait = models.ForeignKey(
        Trait,
        on_delete=models.CASCADE,
        related_name="choice_definitions",
    )
    name = models.CharField(
        max_length=120,
        help_text="Readable label that identifies this trait choice in rulebook terms.",
    )
    target_kind = models.CharField(
        max_length=20,
        choices=TargetKind.choices,
        help_text="What kind of thing must be selected for this trait decision.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Short rulebook prompt that explains what exactly must be chosen.",
    )
    min_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Minimum number of stored selections required for this trait decision.",
    )
    max_choices = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of stored selections allowed for this trait decision.",
    )
    is_required = models.BooleanField(
        default=True,
        help_text="If enabled, the trait stays incomplete until this decision reaches min_choices.",
    )
    allowed_attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trait_choice_definitions",
    )
    allowed_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trait_choice_definitions",
    )
    allowed_skill_family = models.SlugField(
        max_length=50,
        blank=True,
        default="",
    )
    allowed_derived_stat = models.CharField(max_length=50, blank=True, default="", choices=STAT_SLUG_CHOICES)
    allowed_resource = models.CharField(max_length=50, blank=True, default="", choices=RESOURCE_KEY_CHOICES)
    allowed_proficiency_group = models.CharField(max_length=50, blank=True, default="", choices=PROFICIENCY_GROUP_CHOICES)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["trait__trait_type", "trait__name", "sort_order", "name", "id"]

    def clean(self):
        """Prevent contradictory trait choice filters."""
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


class CharacterTraitChoice(models.Model):
    """A persistent character-bound choice made for one owned trait."""

    character_trait = models.ForeignKey(
        CharacterTrait,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    definition = models.ForeignKey(
        TraitChoiceDefinition,
        on_delete=models.CASCADE,
        related_name="character_choices",
    )
    selected_attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_trait_choices",
    )
    selected_skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_trait_choices",
    )
    selected_skill_category = models.ForeignKey(
        SkillCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_trait_choices",
    )
    selected_derived_stat = models.CharField(max_length=50, blank=True, default="", choices=STAT_SLUG_CHOICES)
    selected_resource = models.CharField(max_length=50, blank=True, default="", choices=RESOURCE_KEY_CHOICES)
    selected_proficiency_group = models.CharField(max_length=50, blank=True, default="", choices=PROFICIENCY_GROUP_CHOICES)
    selected_item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_trait_choices",
    )
    selected_item_category = models.CharField(max_length=30, blank=True, default="")
    selected_specialization = models.ForeignKey(
        Specialization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="character_trait_choices",
    )
    selected_text = models.CharField(max_length=255, blank=True, default="")
    selected_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="character_trait_choice_targets",
    )
    selected_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    selected_entity = GenericForeignKey("selected_content_type", "selected_object_id")

    class Meta:
        ordering = ["character_trait__owner__name", "character_trait__trait__name", "definition__sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_attribute"],
                condition=models.Q(selected_attribute__isnull=False),
                name="uniq_character_trait_choice_selected_attribute",
            ),
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_skill"],
                condition=models.Q(selected_skill__isnull=False),
                name="uniq_character_trait_choice_selected_skill",
            ),
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_skill_category"],
                condition=models.Q(selected_skill_category__isnull=False),
                name="uniq_character_trait_choice_selected_category",
            ),
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_item"],
                condition=models.Q(selected_item__isnull=False),
                name="uniq_character_trait_choice_selected_item",
            ),
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_specialization"],
                condition=models.Q(selected_specialization__isnull=False),
                name="uniq_character_trait_choice_selected_specialization",
            ),
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_item_category"],
                condition=~models.Q(selected_item_category=""),
                name="uniq_character_trait_choice_selected_item_category",
            ),
            models.UniqueConstraint(
                fields=["character_trait", "definition", "selected_content_type", "selected_object_id"],
                condition=models.Q(selected_object_id__isnull=False),
                name="uniq_character_trait_choice_selected_entity",
            ),
        ]

    def clean(self):
        """Validate stored trait choice targets against their definition."""
        super().clean()
        if self.selected_content_type_id and self.selected_object_id is None:
            raise ValidationError({"selected_object_id": "Set an object id when selecting another entity."})
        if self.selected_object_id is not None and not self.selected_content_type_id:
            raise ValidationError({"selected_content_type": "Select a content type when using another entity."})
        populated_targets = [
            self.selected_attribute_id is not None,
            self.selected_skill_id is not None,
            self.selected_skill_category_id is not None,
            bool(self.selected_derived_stat),
            bool(self.selected_proficiency_group),
            self.selected_item_id is not None,
            bool(self.selected_item_category),
            self.selected_specialization_id is not None,
            bool(self.selected_text),
            self.selected_object_id is not None,
        ]
        if sum(populated_targets) != 1:
            raise ValidationError("A trait choice must select exactly one persistent target.")
        if (
            self.character_trait_id
            and self.definition_id
            and self.character_trait.trait_id != self.definition.trait_id
        ):
            raise ValidationError({"definition": "The selected trait choice definition must belong to the same trait."})
        self._validate_target_kind(self.definition.target_kind if self.definition_id else "")
        if (
            self.definition_id
            and self.definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE
            and self.selected_attribute_id
            and self.definition.allowed_attribute_id
            and self.selected_attribute_id != self.definition.allowed_attribute_id
        ):
            raise ValidationError({"selected_attribute": "The selected attribute does not match the allowed attribute."})
        if (
            self.definition_id
            and self.definition.target_kind == TraitChoiceDefinition.TargetKind.SKILL
            and self.selected_skill_id
        ):
            if (
                self.definition.allowed_skill_category_id
                and self.selected_skill.category_id != self.definition.allowed_skill_category_id
            ):
                raise ValidationError({"selected_skill": "The selected skill does not belong to the allowed skill category."})
            if (
                self.definition.allowed_skill_family
                and self.selected_skill.family != self.definition.allowed_skill_family
            ):
                raise ValidationError({"selected_skill": "The selected skill does not belong to the allowed skill family."})
        if (
            self.definition_id
            and self.definition.target_kind == TraitChoiceDefinition.TargetKind.DERIVED_STAT
            and self.definition.allowed_derived_stat
            and self.selected_derived_stat != self.definition.allowed_derived_stat
        ):
            raise ValidationError({"selected_derived_stat": "The selected derived stat does not match the allowed derived stat."})
        if (
            self.definition_id
            and self.definition.target_kind == TraitChoiceDefinition.TargetKind.RESOURCE
            and self.definition.allowed_resource
            and self.selected_resource != self.definition.allowed_resource
        ):
            raise ValidationError({"selected_resource": "The selected resource does not match the allowed resource."})
        if (
            self.definition_id
            and self.definition.target_kind == TraitChoiceDefinition.TargetKind.PROFICIENCY_GROUP
            and self.definition.allowed_proficiency_group
            and self.selected_proficiency_group != self.definition.allowed_proficiency_group
        ):
            raise ValidationError({"selected_proficiency_group": "The selected proficiency group does not match the allowed group."})
        if self.definition_id and self.character_trait_id:
            existing = CharacterTraitChoice.objects.filter(
                character_trait=self.character_trait,
                definition=self.definition,
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if self.definition.max_choices and existing.count() >= self.definition.max_choices:
                raise ValidationError({"definition": "Maximum number of choices for this trait definition exceeded."})

    def _validate_target_kind(self, expected_kind: str):
        """Ensure the selected target fields match the configured trait choice kind."""
        errors = {}
        allowed_item_categories = {choice for choice, _label in Item.ItemType.choices}
        target_field_by_kind = {
            TraitChoiceDefinition.TargetKind.ATTRIBUTE: "selected_attribute",
            TraitChoiceDefinition.TargetKind.SKILL: "selected_skill",
            TraitChoiceDefinition.TargetKind.SKILL_CATEGORY: "selected_skill_category",
            TraitChoiceDefinition.TargetKind.DERIVED_STAT: "selected_derived_stat",
            TraitChoiceDefinition.TargetKind.RESOURCE: "selected_resource",
            TraitChoiceDefinition.TargetKind.PROFICIENCY_GROUP: "selected_proficiency_group",
            TraitChoiceDefinition.TargetKind.ITEM: "selected_item",
            TraitChoiceDefinition.TargetKind.ITEM_CATEGORY: "selected_item_category",
            TraitChoiceDefinition.TargetKind.SPECIALIZATION: "selected_specialization",
            TraitChoiceDefinition.TargetKind.TEXT: "selected_text",
            TraitChoiceDefinition.TargetKind.ENTITY: "selected_content_type",
        }
        required_field = target_field_by_kind.get(expected_kind)
        if required_field is None:
            raise ValidationError({"definition": "Unsupported trait choice target kind."})
        if expected_kind == TraitChoiceDefinition.TargetKind.ITEM_CATEGORY and (
            not self.selected_item_category or self.selected_item_category not in allowed_item_categories
        ):
            errors["selected_item_category"] = "Select a valid item category."
        elif expected_kind == TraitChoiceDefinition.TargetKind.ENTITY:
            if not self.selected_content_type_id or self.selected_object_id is None:
                errors["selected_content_type"] = "This trait choice requires another entity target."
        elif expected_kind == TraitChoiceDefinition.TargetKind.TEXT:
            if not self.selected_text:
                errors["selected_text"] = "This trait choice requires a free-text choice."
        elif getattr(self, f"{required_field}_id", None) is None and not getattr(self, required_field):
            errors[required_field] = f"This trait choice requires a {expected_kind.replace('_', ' ')} selection."

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
        if expected_kind == TraitChoiceDefinition.TargetKind.ENTITY:
            disallowed_fields -= {"selected_object_id"}
        for field_name in disallowed_fields:
            value = getattr(self, field_name)
            if value not in (None, "", 0):
                errors[field_name] = "This field does not match the configured choice kind."
        if errors:
            raise ValidationError(errors)

    @property
    def owner(self):
        """Return the owning character for admin display convenience."""
        return self.character_trait.owner

    @property
    def trait(self):
        """Return the owning trait for admin display convenience."""
        return self.character_trait.trait

    def selected_target_display(self) -> str:
        """Return a readable label for the chosen trait target."""
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
        """Return the concrete modifier target tuple derived from this stored choice."""
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

    def __str__(self) -> str:
        return f"{self.character_trait.owner.name} -> {self.definition.name}: {self.selected_target_display()}"


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
