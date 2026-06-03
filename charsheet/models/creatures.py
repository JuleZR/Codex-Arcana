"""Creature definition and per-character creature instance models."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from ..constants import (
    ATTR_CHA,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DAMAGE_TYPE_CHOICES,
    GK_AVERAGE,
    GK_CHOICES,
    QUALITY_CHOICES,
    QUALITY_COMMON,
)


ATTRIBUTE_FIELD_MAP = {
    ATTR_ST: "strength_mod",
    ATTR_KON: "constitution_mod",
    ATTR_GE: "dexterity_mod",
    ATTR_INT: "intelligence_mod",
    ATTR_WA: "perception_mod",
    ATTR_WILL: "willpower_mod",
    ATTR_CHA: "charisma_mod",
}


class Creature(models.Model):
    """Canonical creature stat block template."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    card_name = models.CharField(max_length=100, blank=True, default="")
    image = models.ImageField(upload_to="creatures/", blank=True, null=True)
    description = models.TextField(blank=True, default="")

    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)
    size_modifier = models.IntegerField(default=0)

    strength_mod = models.IntegerField(default=0)
    constitution_mod = models.IntegerField(default=0)
    dexterity_mod = models.IntegerField(default=0)
    intelligence_mod = models.IntegerField(default=0)
    perception_mod = models.IntegerField(default=0)
    willpower_mod = models.IntegerField(default=0)
    charisma_mod = models.IntegerField(null=True, blank=True)

    initiative_override = models.IntegerField(null=True, blank=True)
    vw_override = models.IntegerField(null=True, blank=True)
    sr_override = models.IntegerField(null=True, blank=True)
    gw_override = models.IntegerField(null=True, blank=True)
    fear_resistance_bonus = models.IntegerField(default=0)

    natural_rs = models.PositiveIntegerField(default=0)
    wound_step_override = models.PositiveIntegerField(null=True, blank=True)

    combat_speed = models.PositiveIntegerField(default=0)
    march_speed = models.PositiveIntegerField(default=0)
    sprint_speed = models.PositiveIntegerField(default=0)
    swimming_speed = models.FloatField(default=0, validators=[MinValueValidator(0)])
    combat_fly_speed = models.PositiveIntegerField(null=True, blank=True)
    march_fly_speed = models.PositiveIntegerField(null=True, blank=True)
    sprint_fly_speed = models.PositiveIntegerField(null=True, blank=True)

    climate_and_occurrence = models.TextField(blank=True, default="")
    organization = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["name"]

    @property
    def display_name(self) -> str:
        return self.card_name or self.name

    def __str__(self):
        return self.name


class CreatureAttack(models.Model):
    """One natural or stat-block attack of a creature template."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="attacks")
    name = models.CharField(max_length=100)
    attack_value = models.IntegerField(default=0)
    damage_dice_amount = models.PositiveIntegerField(default=0)
    damage_dice_faces = models.PositiveIntegerField(default=0)
    damage_flat_bonus = models.IntegerField(default=0)
    damage_type = models.CharField(max_length=1, choices=DAMAGE_TYPE_CHOICES, blank=True, default="")
    notes = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.creature}: {self.name}"


class CreatureSkill(models.Model):
    """Canonical normal Skill total printed in a creature stat block."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey("Skill", on_delete=models.PROTECT)
    value = models.IntegerField(default=0)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "skill"], name="uniq_creature_skill")
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.value}"


class CreatureSpecialSkill(models.Model):
    """Creature-only skill definition independent from normal character skills."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    picture = models.ImageField(upload_to="creature_skills/", blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CreatureSpecialSkillValue(models.Model):
    """Canonical creature-only skill total printed in a creature stat block."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="special_skills")
    skill = models.ForeignKey(CreatureSpecialSkill, on_delete=models.PROTECT)
    value = models.IntegerField(default=0)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "skill"], name="uniq_creature_special_skill")
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.value}"


class CreatureTrait(models.Model):
    """Canonical special ability or trait printed in a creature stat block."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="traits")
    trait = models.ForeignKey("Trait", on_delete=models.PROTECT, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True, default="")
    level = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name", "trait__name"]

    @property
    def display_name(self) -> str:
        return self.name or (self.trait.name if self.trait_id else "")

    def clean(self):
        super().clean()
        if not self.trait_id and not self.name:
            raise ValidationError({"name": "Creature trait needs either a trait or a name."})

    def __str__(self):
        return f"{self.creature}: {self.display_name}"


class CharacterCreature(models.Model):
    """Character-owned editable creature instance."""

    owner = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="creatures")
    creature = models.ForeignKey(Creature, on_delete=models.PROTECT, related_name="character_instances")
    name_override = models.CharField(max_length=100, blank=True, default="")
    image_override = models.ImageField(upload_to="character_creatures/", blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    current_damage = models.PositiveIntegerField(default=0)

    size_class_override = models.CharField(max_length=5, choices=GK_CHOICES, blank=True, default="")
    size_modifier_override = models.IntegerField(null=True, blank=True)

    strength_mod_override = models.IntegerField(null=True, blank=True)
    constitution_mod_override = models.IntegerField(null=True, blank=True)
    dexterity_mod_override = models.IntegerField(null=True, blank=True)
    intelligence_mod_override = models.IntegerField(null=True, blank=True)
    perception_mod_override = models.IntegerField(null=True, blank=True)
    willpower_mod_override = models.IntegerField(null=True, blank=True)
    charisma_mod_override = models.IntegerField(null=True, blank=True)

    initiative_override = models.IntegerField(null=True, blank=True)
    vw_override = models.IntegerField(null=True, blank=True)
    sr_override = models.IntegerField(null=True, blank=True)
    gw_override = models.IntegerField(null=True, blank=True)
    fear_resistance_bonus_override = models.IntegerField(null=True, blank=True)

    natural_rs_override = models.PositiveIntegerField(null=True, blank=True)
    wound_step_override = models.PositiveIntegerField(null=True, blank=True)

    combat_speed_override = models.PositiveIntegerField(null=True, blank=True)
    march_speed_override = models.PositiveIntegerField(null=True, blank=True)
    sprint_speed_override = models.PositiveIntegerField(null=True, blank=True)
    swimming_speed_override = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])
    combat_fly_speed_override = models.PositiveIntegerField(null=True, blank=True)
    march_fly_speed_override = models.PositiveIntegerField(null=True, blank=True)
    sprint_fly_speed_override = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["owner", "creature", "id"]

    @property
    def display_name(self) -> str:
        return self.name_override or self.creature.display_name

    @property
    def image(self):
        return self.image_override or self.creature.image

    def __str__(self):
        return f"{self.owner}: {self.display_name}"


class CharacterCreatureItem(models.Model):
    """Equipment state of one item on one character-owned creature."""

    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("Item", on_delete=models.PROTECT)
    amount = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default=QUALITY_COMMON)
    notes = models.TextField(blank=True, default="")

    armor_rs_head_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_torso_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_arm_left_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_arm_right_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_leg_left_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_leg_right_override = models.PositiveIntegerField(null=True, blank=True)
    armor_rs_total_override = models.PositiveIntegerField(null=True, blank=True)
    armor_encumbrance_override = models.PositiveIntegerField(null=True, blank=True)
    armor_min_st_override = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["creature", "item__name"]

    def clean(self):
        super().clean()
        if self.amount != 1 and not self.item.stackable:
            raise ValidationError({"amount": "Non stackable creature items must have amount 1."})
        if self.equipped and self.item.stackable:
            raise ValidationError({"equipped": "Stackable creature items cannot be equipped."})

    def __str__(self):
        return f"{self.creature}: {self.item}"


class CharacterCreatureSkill(models.Model):
    """Per-character override for one normal creature skill total."""

    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="skill_overrides")
    skill = models.ForeignKey("Skill", on_delete=models.PROTECT)
    value_override = models.IntegerField()
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "skill"], name="uniq_character_creature_skill")
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.value_override}"


class CharacterCreatureSpecialSkill(models.Model):
    """Per-character override for one creature-only skill total."""

    creature = models.ForeignKey(
        CharacterCreature,
        on_delete=models.CASCADE,
        related_name="special_skill_overrides",
    )
    skill = models.ForeignKey(CreatureSpecialSkill, on_delete=models.PROTECT)
    value_override = models.IntegerField()
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["skill__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["creature", "skill"],
                name="uniq_character_creature_special_skill",
            )
        ]

    def __str__(self):
        return f"{self.creature}: {self.skill} {self.value_override}"


class CharacterCreatureTrait(models.Model):
    """Per-character creature trait override or addition."""

    creature = models.ForeignKey(CharacterCreature, on_delete=models.CASCADE, related_name="trait_overrides")
    base_trait = models.ForeignKey(CreatureTrait, on_delete=models.PROTECT, null=True, blank=True)
    trait = models.ForeignKey("Trait", on_delete=models.PROTECT, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True, default="")
    level_override = models.IntegerField(null=True, blank=True)
    description_override = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name", "trait__name"]

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.trait_id:
            return self.trait.name
        if self.base_trait_id:
            return self.base_trait.display_name
        return ""

    def clean(self):
        super().clean()
        if not self.base_trait_id and not self.trait_id and not self.name:
            raise ValidationError({"name": "Creature trait override needs a base trait, trait, or name."})

    def __str__(self):
        return f"{self.creature}: {self.display_name}"
