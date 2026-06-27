"""Creature definition and per-character creature instance models."""
from django.db import models

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils.text import slugify

from ..constants import (
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
    QUALITY_COMMON,
)
from .core import Attribute, Skill


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
    fear_resistance_bonus = models.IntegerField(default=0)
    natural_rs = models.PositiveIntegerField(default=0)
    wound_step_override = models.PositiveIntegerField(blank=True, null=True)
    combat_speed = models.PositiveIntegerField(default=0)
    march_speed = models.PositiveIntegerField(default=0)
    sprint_speed = models.PositiveIntegerField(default=0)
    swimming_speed = models.FloatField(default=0, validators=[MinValueValidator(0)])
    combat_fly_speed = models.PositiveIntegerField(blank=True, null=True)
    march_fly_speed = models.PositiveIntegerField(blank=True, null=True)
    sprint_fly_speed = models.PositiveIntegerField(blank=True, null=True)
    climate_and_occurrence = models.TextField(blank=True, default="")
    organization = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.max_level < self.min_level:
            raise ValidationError("Max level < min level is prohibited.")

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


class CharacterCreature(models.Model):
    owner = models.ForeignKey("charsheet.Character", on_delete=models.CASCADE, related_name="creatures")
    creature = models.ForeignKey(Creature, on_delete=models.PROTECT, related_name="character_instances")
    name_override = models.CharField(max_length=100, blank=True, default="")
    image_override = models.ImageField(upload_to="character_creatures/", blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    current_damage = models.PositiveIntegerField(default=0)
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
    fear_resistance_bonus_override = models.IntegerField(blank=True, null=True)
    natural_rs_override = models.PositiveIntegerField(blank=True, null=True)
    wound_step_override = models.PositiveIntegerField(blank=True, null=True)
    combat_speed_override = models.PositiveIntegerField(blank=True, null=True)
    march_speed_override = models.PositiveIntegerField(blank=True, null=True)
    sprint_speed_override = models.PositiveIntegerField(blank=True, null=True)
    swimming_speed_override = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    combat_fly_speed_override = models.PositiveIntegerField(blank=True, null=True)
    march_fly_speed_override = models.PositiveIntegerField(blank=True, null=True)
    sprint_fly_speed_override = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["owner", "creature", "id"]

    def __str__(self):
        return f"{self.display_name} ({self.owner})"

    @property
    def display_name(self):
        return self.name_override or self.creature.display_name

    @property
    def image(self):
        return self.image_override or self.creature.image


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
    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="trait_overrides")
    base_trait = models.ForeignKey(CreatureTrait, on_delete=models.PROTECT, blank=True, null=True)
    trait = models.ForeignKey(CreatureTraitDefinition, on_delete=models.CASCADE)
    trait_level = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["creature", "trait"]
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
    def description_override(self):
        return self.trait.description

    @property
    def order(self):
        return 0


class CreatureCardBinding(models.Model):
    class TriggerType(models.TextChoices):
        ITEM = "item", "Item"
        TECHNIQUE = "technique", "Technique"

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="card_bindings", null=True)
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    item_trigger = models.ForeignKey(
        "charsheet.Item",
        on_delete=models.CASCADE,
        related_name="creature_card_bindings",
        blank=True,
        null=True,
    )
    technique_trigger = models.ForeignKey(
        "charsheet.Technique",
        on_delete=models.CASCADE,
        related_name="creature_card_bindings",
        blank=True,
        null=True,
    )
    active = models.BooleanField(default=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["creature__name", "trigger_type", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["creature", "item_trigger"],
                condition=models.Q(item_trigger__isnull=False),
                name="uniq_creature_card_item_binding",
            ),
            models.UniqueConstraint(
                fields=["creature", "technique_trigger"],
                condition=models.Q(technique_trigger__isnull=False),
                name="uniq_creature_card_technique_binding",
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


class CharacterCreatureCard(models.Model):
    character = models.ForeignKey("charsheet.Character", on_delete=models.CASCADE, related_name="creature_cards")
    binding = models.ForeignKey(CreatureCardBinding, on_delete=models.PROTECT, related_name="character_cards")
    creature = models.ForeignKey(Creature, on_delete=models.PROTECT, related_name="character_cards", null=True)
    active = models.BooleanField(default=True)
    current_damage = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    name = models.CharField(max_length=100)
    creature_type = models.CharField(max_length=100, blank=True, default="")
    image = models.ImageField(upload_to="character_creature_cards/", blank=True, null=True)
    description = models.TextField(blank=True, default="")
    source_reference = models.CharField(max_length=200, blank=True, default="")
    quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="quality",
        on_delete=models.PROTECT,
        related_name="creature_cards",
        default=QUALITY_COMMON,
    )
    initiative = models.IntegerField(default=0)
    vw = models.IntegerField(default=0)
    sr = models.IntegerField(default=0)
    gw = models.IntegerField(default=0)
    fear_resistance_bonus = models.IntegerField(default=0)
    rs = models.PositiveIntegerField(default=0)
    wound_step = models.PositiveIntegerField(default=1)
    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)
    size_modifier = models.IntegerField(default=0)
    combat_speed = models.PositiveIntegerField(default=0)
    march_speed = models.PositiveIntegerField(default=0)
    sprint_speed = models.PositiveIntegerField(default=0)
    swimming_speed = models.FloatField(default=0, validators=[MinValueValidator(0)])
    combat_fly_speed = models.PositiveIntegerField(blank=True, null=True)
    march_fly_speed = models.PositiveIntegerField(blank=True, null=True)
    sprint_fly_speed = models.PositiveIntegerField(blank=True, null=True)
    strength_mod = models.IntegerField(default=0)
    constitution_mod = models.IntegerField(default=0)
    dexterity_mod = models.IntegerField(default=0)
    intelligence_mod = models.IntegerField(default=0)
    perception_mod = models.IntegerField(default=0)
    willpower_mod = models.IntegerField(default=0)
    charisma_mod = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ["character", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["character", "binding"], name="uniq_character_creature_card_binding"),
        ]

    def __str__(self):
        return f"{self.name} ({self.character})"

    @property
    def trigger_label(self):
        return self.binding.trigger_label

    @classmethod
    def snapshot_defaults(cls, creature, binding, values):
        defaults = dict(values)
        defaults.update({"binding": binding, "creature": creature, "active": True})
        return defaults

    @property
    def has_source_deviations(self):
        if not self.creature_id:
            return True
        from ..engine.creature_engine import _creature_card_snapshot_values

        source_values = _creature_card_snapshot_values(self.creature)
        compared_fields = (
            "initiative",
            "vw",
            "sr",
            "gw",
            "fear_resistance_bonus",
            "quality",
            "rs",
            "wound_step",
            "size_class",
            "size_modifier",
            "combat_speed",
            "march_speed",
            "sprint_speed",
            "swimming_speed",
            "combat_fly_speed",
            "march_fly_speed",
            "sprint_fly_speed",
            "strength_mod",
            "constitution_mod",
            "dexterity_mod",
            "intelligence_mod",
            "perception_mod",
            "willpower_mod",
            "charisma_mod",
        )
        return any(getattr(self, field) != source_values.get(field) for field in compared_fields)


class CharacterCreatureCardAttack(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="attacks")
    name = models.CharField(max_length=100)
    attack_value = models.IntegerField(default=0)
    damage = models.CharField(max_length=100, blank=True, default="")
    notes = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.card}: {self.name}"


class CharacterCreatureCardSkill(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=100)
    value = models.IntegerField(default=0)
    notes = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.card}: {self.name} {self.value:+d}"


class CharacterCreatureCardTrait(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="traits")
    name = models.CharField(max_length=100)
    level = models.IntegerField(blank=True, null=True)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.card}: {self.name}"


class CharacterCreatureCardCommand(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="commands")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True, default="")
    ep_cost = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    difficulty = models.PositiveIntegerField(blank=True, null=True)
    prerequisites = models.ManyToManyField(
        "self",
        through="CharacterCreatureCardCommandPrerequisite",
        symmetrical=False,
        related_name="unlocks",
        blank=True,
    )
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.card}: {self.name}"

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


class CharacterCreatureCardCommandPrerequisite(models.Model):
    command = models.ForeignKey(
        CharacterCreatureCardCommand,
        on_delete=models.CASCADE,
        related_name="prerequisite_links",
    )
    prerequisite = models.ForeignKey(
        CharacterCreatureCardCommand,
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
                name="uniq_card_command_prerequisite_group",
            ),
        ]

    def __str__(self):
        return f"{self.command}: {self.prerequisite}"

    def clean(self):
        super().clean()
        if self.command_id and self.prerequisite_id and self.command.card_id != self.prerequisite.card_id:
            raise ValidationError({"prerequisite": "Prerequisite must belong to the same creature card."})
