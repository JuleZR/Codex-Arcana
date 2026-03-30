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
)
from .core import DamageSource


class Item(models.Model):
    """Inventory item that may be owned, stacked, or equipped."""

    class ItemType(models.TextChoices):
        ARMOR = "armor", "Rüstung"
        WEAPON = "weapon", "Waffe"
        SHIELD = "shield", "Schild"
        CONSUM = "consumable", "verbrauchbar"
        AMMO = "ammo", "Monition"
        MISC = "misc", "Misc"

    name = models.CharField(max_length=200, unique=True)
    price = models.IntegerField(default=1)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.TextField(null=True, blank=True)

    stackable = models.BooleanField(default=True)
    is_consumable = models.BooleanField(default=False)

    default_quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default=QUALITY_COMMON)
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)

    def clean(self):
        """Prevent invalid stackable armor definitions."""
        super().clean()
        if self.item_type in {
            self.ItemType.ARMOR,
            self.ItemType.SHIELD,
            self.ItemType.WEAPON,
        } and self.stackable:
            raise ValidationError({"stackable": f"Type: {self.item_type.upper()} can't be stackable."})

    def __str__(self):
        return f"{self.item_type.upper()}: {self.name}"


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


class WeaponStats(models.Model):
    """Weapon-specific combat data attached to an item."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    damage_source = models.ForeignKey(DamageSource, on_delete=models.PROTECT)
    min_st = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    damage_dice_amount = models.PositiveIntegerField(default=1)
    damage_dice_faces = models.PositiveIntegerField(default=10)
    damage_flat_bonus = models.PositiveIntegerField(default=0)

    wield_mode = models.CharField(max_length=2, choices=WIELD_MODES, default=ONE_HANDED)

    h2_dice_amount = models.PositiveIntegerField(null=True, blank=True)
    h2_dice_faces = models.PositiveIntegerField(null=True, blank=True)
    h2_flat_bonus = models.PositiveIntegerField(null=True, blank=True)

    @property
    def two_handed(self) -> bool:
        """Return whether this weapon has a dedicated two-handed profile."""
        return self.wield_mode in {TWO_HANDED, VERSATILE}

    @property
    def damage(self) -> str:
        """Return one-handed/base damage in classic dice notation."""
        damage = f"{self.damage_dice_amount}w{self.damage_dice_faces}"
        if self.damage_flat_bonus:
            damage += f"{self.damage_flat_bonus:+d}"
        return damage

    @property
    def two_handed_damage(self) -> str | None:
        """Return two-handed damage in dice notation if available."""
        if not self.two_handed or self.h2_dice_amount is None or self.h2_dice_faces is None:
            return None
        damage = f"{self.h2_dice_amount}w{self.h2_dice_faces}"
        if self.h2_flat_bonus:
            damage += f"{self.h2_flat_bonus:+d}"
        return damage

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
        )
        if self.two_handed:
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
            return f"{self.item}: DMG {base} / 2H {alt} ({self.damage_source})"

        return f"{self.item}: DMG {base} ({self.damage_source})"


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
        if self.item.item_type not in {Item.ItemType.WEAPON, Item.ItemType.ARMOR, Item.ItemType.SHIELD}:
            raise ValidationError({"item": "Race items must be weapons, armor, or shields because they are always equipped."})

    def __str__(self):
        return f"{self.race} -> {self.item} x{self.amount}"
