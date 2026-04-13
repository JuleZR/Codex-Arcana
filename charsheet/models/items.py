"""Item and equipment definition models."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from ..constants import (
    GK_AVERAGE,
    GK_CHOICES,
    ONE_HANDED,
    QUALITY_CHOICES,
    QUALITY_COMMON,
    TWO_HANDED,
    VERSATILE,
    WIELD_MODES,
    DEADLY,
    DAMAGE_TYPE_CHOICES,
    WEAPON_SYMBOL_CHOICES
)
from .core import DamageSource


class Rune(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="runes/", blank=True, null=True)
    has_specialization = models.BooleanField(default=False)
    specialization_label = models.CharField(max_length=100, blank=True, default="")
    allow_multiple = models.BooleanField(
        default=False,
        help_text="Erlaubt, diese Rune mehrfach auf denselben Gegenstand anzuwenden.",
    )

    def __str__(self):
        return self.name


class Item(models.Model):
    """Inventory item that may be owned, stacked, or equipped."""

    class ItemType(models.TextChoices):
        ARMOR = "armor", "Rüstung"
        WEAPON = "weapon", "Waffe"
        SHIELD = "shield", "Schild"
        CLOTHING = "clothing", "Kleidung"
        MAGIC_ITEM = "magic_item", "Magischer Gegenstand"
        CONSUM = "consumable", "verbrauchbar"
        AMMO = "ammo", "Monition"
        MISC = "misc", "Misc"

    name = models.CharField(max_length=200, unique=True)
    price = models.IntegerField(default=1)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.TextField(null=True, blank=True)

    stackable = models.BooleanField(default=True)
    is_consumable = models.BooleanField(default=False)
    is_magic = models.BooleanField(default=False)

    default_quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default=QUALITY_COMMON)
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)

    runes = models.ManyToManyField("Rune", blank=True, related_name="items")

    def clean(self):
        """Prevent invalid stackable armor definitions."""
        super().clean()
        if self.item_type in {
            self.ItemType.ARMOR,
            self.ItemType.SHIELD,
            self.ItemType.WEAPON,
            self.ItemType.CLOTHING,
        } and self.stackable:
            raise ValidationError({"stackable": f"Type: {self.item_type.upper()} can't be stackable."})
        if (self.is_magic or self.item_type == self.ItemType.MAGIC_ITEM) and self.stackable:
            raise ValidationError({"stackable": f"Type: {self.item_type.upper()} can't be stackable."})

    def __str__(self):
        return f"{self.item_type.upper()}: {self.name}"

    @property
    def is_magic_effective(self) -> bool:
        return bool(self.is_magic or self.item_type == self.ItemType.MAGIC_ITEM)


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
    encumbrance = models.PositiveIntegerField(default=0)
    min_st = models.PositiveIntegerField(default=1)

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
        if self.rs_total:
            return f"{self.item}: RS {self.rs_total}"
        return f"{self.item}: RS {self.rs_sum()}"


class ShieldStats(models.Model):
    """Shield-specific protection values for an item."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)

    rs = models.PositiveIntegerField(default=0)
    encumbrance = models.PositiveIntegerField(default=0)
    min_st = models.PositiveIntegerField(default=1)

    def clean(self):
        super().clean()
        if self.item.item_type != Item.ItemType.SHIELD:
            raise ValidationError("Shield must be type SHIELD")

    def __str__(self):
        return f"{self.item}: RS {self.rs}"


class MagicItemStats(models.Model):
    """Magic-item specific metadata attached to one item."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    effect_summary = models.CharField(max_length=255, blank=True, default="")

    def clean(self):
        super().clean()
        if not self.item.is_magic_effective:
            raise ValidationError({"item": "Only magic items can have MagicItemStats."})

    def __str__(self):
        summary = f" - {self.effect_summary}" if self.effect_summary else ""
        return f"{self.item}{summary}"


class WeaponFlag(models.Model):
    key = models.CharField(max_length=50, choices=WEAPON_SYMBOL_CHOICES, unique=True)

    def __str__(self):
        return self.get_key_display()


class WeaponStats(models.Model):
    """Weapon-specific combat data attached to an item."""

    class DamageOperator(models.TextChoices):
        NONE = "", "Kein Operator"
        ADD = "+", "+"
        SUBTRACT = "-", "-"
        DIVIDE = "/", "/"

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    min_st = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    damage_source = models.ForeignKey(DamageSource, on_delete=models.PROTECT)
    damage_dice_amount = models.PositiveIntegerField(default=1)
    damage_dice_faces = models.PositiveIntegerField(default=10)
    damage_flat_bonus = models.IntegerField(default=0)
    damage_flat_operator = models.CharField(max_length=1, choices=DamageOperator.choices, default=DamageOperator.NONE, blank=True)
    damage_bonus_attribute = models.CharField(max_length=20, blank=True, default="")
    damage_bonus_mode = models.CharField(max_length=20, blank=True, default="flat")
    damage_type = models.CharField(max_length=1, default=DEADLY, choices=DAMAGE_TYPE_CHOICES)

    wield_mode = models.CharField(max_length=2, choices=WIELD_MODES, default=ONE_HANDED)

    h2_dice_amount = models.PositiveIntegerField(null=True, blank=True)
    h2_dice_faces = models.PositiveIntegerField(null=True, blank=True)
    h2_flat_bonus = models.IntegerField(null=True, blank=True)
    h2_flat_operator = models.CharField(max_length=1, choices=DamageOperator.choices, default=DamageOperator.NONE, blank=True)

    flags = models.ManyToManyField(WeaponFlag, blank=True)

    @property
    def two_handed(self) -> bool:
        """Return whether this weapon has a dedicated two-handed profile."""
        return self.wield_mode in {TWO_HANDED, VERSATILE}

    @property
    def has_alternate_two_handed_profile(self) -> bool:
        """Return whether the weapon has a second, optional two-handed profile."""
        return self.wield_mode == VERSATILE

    @property
    def damage(self) -> str:
        """Return one-handed/base damage in classic dice notation."""
        return self.format_damage_label(
            self.damage_dice_amount,
            self.damage_dice_faces,
            self.damage_flat_bonus,
            self.damage_flat_operator,
        )

    @property
    def two_handed_damage(self) -> str | None:
        """Return two-handed damage in dice notation if available."""
        if not self.has_alternate_two_handed_profile or self.h2_dice_amount is None or self.h2_dice_faces is None:
            return None
        return self.format_damage_label(
            self.h2_dice_amount,
            self.h2_dice_faces,
            self.h2_flat_bonus,
            self.h2_flat_operator,
        )

    @classmethod
    def format_damage_label(cls, dice_amount: int, dice_faces: int, bonus: int | None, operator: str | None) -> str:
        """Return classic damage notation with a configurable operator."""
        damage = f"{dice_amount}w{dice_faces}"
        resolved_bonus = int(bonus or 0)
        resolved_operator = str(operator or "")
        if not resolved_bonus:
            return damage
        if resolved_operator == cls.DamageOperator.DIVIDE:
            return f"{damage}/{resolved_bonus}"
        if resolved_operator == cls.DamageOperator.SUBTRACT:
            return f"{damage}-{resolved_bonus}"
        if resolved_operator == cls.DamageOperator.ADD:
            return f"{damage}+{resolved_bonus}"
        return f"{damage}{resolved_bonus:+d}"

    @property
    def size_class(self) -> str:
        """Expose item size class for admin list display convenience."""
        return self.item.size_class

    def clean(self):
        super().clean()
        if self.item.item_type != Item.ItemType.WEAPON:
            raise ValidationError({"item": "Non-weapon items can't have WeaponStats"})

        has_h2_values = (
            self.h2_dice_amount is not None
            or self.h2_dice_faces is not None
            or self.h2_flat_bonus is not None
            or bool(self.h2_flat_operator)
        )
        if self.has_alternate_two_handed_profile:
            if self.h2_dice_amount is None or self.h2_dice_faces is None:
                raise ValidationError("Two-handed weapons need h2_dice_amount and h2_dice_faces.")
        elif has_h2_values:
            raise ValidationError("Non-two-handed weapons must not define two-handed damage values.")

    def __str__(self):
        base = f"{self.damage_dice_amount}w{self.damage_dice_faces}"
        if self.damage_flat_bonus:
            base += f"{self.damage_flat_bonus:+d}"

        if self.two_handed and self.h2_dice_amount and self.h2_dice_faces:
            alt = f"{self.h2_dice_amount}w{self.h2_dice_faces}"
            if self.h2_flat_bonus:
                alt += f"{self.h2_flat_bonus:+d}"
            return f"{self.item}: DMG {base} / 2H {alt} ({self.get_damage_type_display()})"

        return f"{self.item}: DMG {base} ({self.get_damage_type_display()})"


class RaceStartingItem(models.Model):
    race = models.ForeignKey("charsheet.Race", on_delete=models.CASCADE, related_name="starting_items")
    item = models.ForeignKey("charsheet.Item", on_delete=models.CASCADE, related_name="race_starting_items")
    amount = models.PositiveIntegerField(default=1)
    quality = models.CharField(max_length=30, blank=True, default="")
    equipped = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["race", "item"], name="uniq_race_starting_item")
        ]

    def clean(self):
        super().clean()
        if self.item.stackable:
            raise ValidationError({"item": "Race items must not be stackable because they are always equipped."})
        if self.item.item_type not in {
            Item.ItemType.WEAPON,
            Item.ItemType.ARMOR,
            Item.ItemType.SHIELD,
            Item.ItemType.CLOTHING,
            Item.ItemType.MAGIC_ITEM,
        }:
            raise ValidationError({"item": "Race items must be equippable items because they are always equipped."})

    def __str__(self):
        return f"{self.race} -> {self.item} x{self.amount}"
