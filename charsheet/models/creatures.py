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
    GK_MODS,
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


CREATURE_CARD_STAT_FIELDS = (
    "name",
    "creature_type",
    "initiative",
    "vw",
    "sr",
    "gw",
    "fear_resistance_bonus",
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
    "description",
    "source_reference",
)


class CreatureCardBinding(models.Model):
    """Activation binding between a concrete creature card and a concrete trigger."""

    class TriggerType(models.TextChoices):
        ITEM = "item", "Item"
        TECHNIQUE = "technique", "Technique"

    creature = models.ForeignKey("Creature", on_delete=models.CASCADE, null=True, related_name="card_bindings")
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    item_trigger = models.ForeignKey(
        "Item",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="creature_card_bindings",
    )
    technique_trigger = models.ForeignKey(
        "Technique",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="creature_card_bindings",
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

    def clean(self):
        super().clean()
        if self.trigger_type == self.TriggerType.ITEM:
            if not self.item_trigger_id or self.technique_trigger_id:
                raise ValidationError("Item bindings need exactly one item trigger and no technique trigger.")
        elif self.trigger_type == self.TriggerType.TECHNIQUE:
            if not self.technique_trigger_id or self.item_trigger_id:
                raise ValidationError("Technique bindings need exactly one technique trigger and no item trigger.")
        elif self.item_trigger_id or self.technique_trigger_id:
            raise ValidationError("Creature card bindings need a supported trigger type.")
        if not self.creature_id:
            raise ValidationError("Creature card bindings need a concrete creature.")

    @property
    def trigger_label(self) -> str:
        if self.trigger_type == self.TriggerType.ITEM and self.item_trigger_id:
            return str(self.item_trigger)
        if self.trigger_type == self.TriggerType.TECHNIQUE and self.technique_trigger_id:
            return str(self.technique_trigger)
        return "-"

    def __str__(self):
        return f"{self.creature} <- {self.trigger_label}"


class CharacterCreatureCard(models.Model):
    """Character-bound snapshot of one concrete creature card."""

    character = models.ForeignKey("Character", on_delete=models.CASCADE, related_name="creature_cards")
    creature = models.ForeignKey("Creature", on_delete=models.PROTECT, null=True, related_name="character_cards")
    binding = models.ForeignKey(CreatureCardBinding, on_delete=models.PROTECT, related_name="character_cards")
    active = models.BooleanField(default=True)
    current_damage = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default="")

    name = models.CharField(max_length=100)
    creature_type = models.CharField(max_length=100, blank=True, default="")
    image = models.ImageField(upload_to="character_creature_cards/", blank=True, null=True)
    description = models.TextField(blank=True, default="")
    source_reference = models.CharField(max_length=200, blank=True, default="")

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
    combat_fly_speed = models.PositiveIntegerField(null=True, blank=True)
    march_fly_speed = models.PositiveIntegerField(null=True, blank=True)
    sprint_fly_speed = models.PositiveIntegerField(null=True, blank=True)

    strength_mod = models.IntegerField(default=0)
    constitution_mod = models.IntegerField(default=0)
    dexterity_mod = models.IntegerField(default=0)
    intelligence_mod = models.IntegerField(default=0)
    perception_mod = models.IntegerField(default=0)
    willpower_mod = models.IntegerField(default=0)
    charisma_mod = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["character", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["character", "binding"], name="uniq_character_creature_card_binding")
        ]

    @classmethod
    def snapshot_defaults(cls, creature: "Creature", binding: CreatureCardBinding, values: dict | None = None) -> dict:
        data = dict(values or {})
        data["creature"] = creature
        data["binding"] = binding
        return data

    @property
    def trigger_label(self) -> str:
        return self.binding.trigger_label

    @property
    def has_source_deviations(self) -> bool:
        creature = self.creature
        if creature is None:
            return True
        size_modifier = int(creature.size_modifier or 0) or int(GK_MODS.get(creature.size_class, 0))
        source_values = {
            "name": creature.display_name,
            "description": creature.description,
            "source_reference": creature.climate_and_occurrence,
            "initiative": creature.initiative_override if creature.initiative_override is not None else creature.perception_mod,
            "vw": creature.vw_override if creature.vw_override is not None else 14 + creature.dexterity_mod + creature.perception_mod + size_modifier,
            "sr": creature.sr_override if creature.sr_override is not None else 14 + creature.strength_mod + creature.constitution_mod,
            "gw": creature.gw_override if creature.gw_override is not None else 14 + creature.intelligence_mod + creature.willpower_mod,
            "fear_resistance_bonus": creature.fear_resistance_bonus,
            "rs": creature.natural_rs,
            "wound_step": creature.wound_step_override if creature.wound_step_override is not None else 5 + creature.constitution_mod,
            "size_class": creature.size_class,
            "size_modifier": size_modifier,
            "combat_speed": creature.combat_speed,
            "march_speed": creature.march_speed,
            "sprint_speed": creature.sprint_speed,
            "swimming_speed": creature.swimming_speed,
            "combat_fly_speed": creature.combat_fly_speed,
            "march_fly_speed": creature.march_fly_speed,
            "sprint_fly_speed": creature.sprint_fly_speed,
            "strength_mod": creature.strength_mod,
            "constitution_mod": creature.constitution_mod,
            "dexterity_mod": creature.dexterity_mod,
            "intelligence_mod": creature.intelligence_mod,
            "perception_mod": creature.perception_mod,
            "willpower_mod": creature.willpower_mod,
            "charisma_mod": creature.charisma_mod,
        }
        for field, value in source_values.items():
            if getattr(self, field) != value:
                return True
        if self.image != creature.image:
            return True
        def format_attack_damage(row) -> str:
            if not row.damage_dice_amount or not row.damage_dice_faces:
                return ""
            bonus = ""
            flat_bonus = int(row.damage_flat_bonus or 0)
            flat_operator = str(row.damage_flat_operator or "")
            if flat_bonus:
                if flat_operator == "/":
                    bonus = f"/{abs(flat_bonus)}"
                elif flat_operator == "-":
                    bonus = f"-{abs(flat_bonus)}"
                elif flat_operator == "+":
                    bonus = f"+{abs(flat_bonus)}"
                else:
                    bonus = f"{flat_bonus:+d}"
            damage_type = f" {row.damage_type}" if row.damage_type else ""
            return f"{row.damage_dice_amount}w{row.damage_dice_faces}{bonus}{damage_type}"

        source_attacks = [
            (row.order, row.name, row.attack_value, format_attack_damage(row), row.notes)
            for row in creature.attacks.all()
        ]
        card_attacks = [
            (row.order, row.name, row.attack_value, row.damage, row.notes)
            for row in self.attacks.all()
        ]
        if card_attacks != source_attacks:
            return True
        source_skills = [
            (row.skill.name, row.value, row.notes)
            for row in creature.skills.select_related("skill")
        ]
        card_skills = [
            (row.name, row.value, row.notes)
            for row in self.skills.all()
        ]
        if card_skills != source_skills:
            return True
        source_traits = [
            (row.order, row.display_name, row.level, row.description)
            for row in creature.traits.select_related("trait")
        ]
        card_traits = [
            (row.order, row.name, row.level, row.description)
            for row in self.traits.all()
        ]
        if card_traits != source_traits:
            return True
        source_commands = [
            (row.order, row.command.name, row.command.slug, row.command.description)
            for row in creature.commands.select_related("command")
        ]
        card_commands = [
            (row.order, row.name, row.slug, row.description)
            for row in self.commands.all()
        ]
        if card_commands != source_commands:
            return True
        return False

    def __str__(self):
        return f"{self.character}: {self.name}"


class CharacterCreatureCardAttack(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="attacks")
    name = models.CharField(max_length=100)
    attack_value = models.IntegerField(default=0)
    damage = models.CharField(max_length=100, blank=True, default="")
    notes = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]


class CharacterCreatureCardSkill(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=100)
    value = models.IntegerField(default=0)
    notes = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]


class CharacterCreatureCardTrait(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="traits")
    name = models.CharField(max_length=100)
    level = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]


class CharacterCreatureCardCommand(models.Model):
    card = models.ForeignKey(CharacterCreatureCard, on_delete=models.CASCADE, related_name="commands")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]


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


class CreatureCommand(models.Model):
    """Reusable creature command printed on creature cards."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CreatureCommandReference(models.Model):
    """Command assigned to a creature template."""

    creature = models.ForeignKey(Creature, on_delete=models.CASCADE, related_name="commands")
    command = models.ForeignKey(CreatureCommand, on_delete=models.PROTECT, related_name="creature_references")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "command__name"]
        constraints = [
            models.UniqueConstraint(fields=["creature", "command"], name="uniq_creature_command")
        ]

    def __str__(self):
        return f"{self.creature}: {self.command}"


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
