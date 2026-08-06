"""Item and equipment definition models."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from django.utils.text import slugify

from ..constants import (
    ATTR_GE,
    ATTR_ST,
    DAMAGE_TYPE_CHOICES,
    DEADLY,
    GK_AVERAGE,
    GK_CHOICES,
    ONE_HANDED,
    QUALITY_COMMON,
    TWO_HANDED,
    VERSATILE,
    WEAPON_SYMBOL_CHOICES,
    WEAPON_MANEUVER_ATTRIBUTE_BOTH,
    WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
    WEAPON_MANEUVER_ATTRIBUTE_GE,
    WEAPON_MANEUVER_ATTRIBUTE_ST,
    WIELD_MODES,
)
from .core import DamageSource


class Quality(models.Model):
    """Shared quality tier for items, creatures, and display coloring."""

    code = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    hex_color = models.CharField(
        max_length=7,
        default="#33CC33",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Enter a hex color like #33CC33.")],
    )
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "qualities"

    def __str__(self):
        return self.name


class Rune(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=255, blank=True, default="")
    image = models.ImageField(upload_to="runes/", blank=True, null=True)
    has_specialization = models.BooleanField(default=False)
    specialization_label = models.CharField(max_length=100, blank=True, default="")
    allowed_item_types = models.JSONField(
        blank=True,
        default=list,
        help_text="Leere Liste bedeutet: alle Item-Typen erlaubt.",
    )
    is_level_scaled = models.BooleanField(
        default=False,
        help_text="Wenn aktiv, skaliert der Effekt mit dem gespeicherten Waffenmeister-Level der ItemRune.",
    )
    allow_multiple = models.BooleanField(
        default=False,
        help_text="Wenn aktiv, darf diese Rune mehrfach auf demselben Gegenstand angebracht werden.",
    )
    modifier_templates = GenericRelation(
        "Modifier",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
        related_query_name="rune_template",
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = (slugify(self.name) or "rune")[:110]
            slug = base_slug
            suffix = 2
            existing = Rune.objects.all()
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            while existing.filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Item(models.Model):
    """Inventory item that may be owned, stacked, or equipped."""

    MAGIC_EQUIPMENT_TYPES = frozenset({"ring", "amulet", "magical_weapon", "magical_armor"})
    WEAPON_ITEM_TYPES = frozenset({"weapon", "magical_weapon"})
    ARMOR_ITEM_TYPES = frozenset({"armor", "magical_armor"})

    class ItemType(models.TextChoices):
        ARMOR = "armor", "Rüstung"
        WEAPON = "weapon", "Waffe"
        SHIELD = "shield", "Schild"
        CLOTHING = "clothing", "Kleidung"
        RING = "ring", "Ring"
        AMULET = "amulet", "Amulett"
        MAGICAL_WEAPON = "magical_weapon", "Magische Waffe"
        MAGICAL_ARMOR = "magical_armor", "Magisches Rüstzeug"
        CONSUM = "consumable", "Verbrauchsgegenstand"
        AMMO = "ammo", "Monition"
        CREATURE = "creature", "Tiere & Kreaturen"
        MISC = "misc", "Sonstiges"

    name = models.CharField(max_length=200)
    price = models.IntegerField(default=1)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="items/", blank=True, null=True)

    stackable = models.BooleanField(default=True)
    is_consumable = models.BooleanField(default=False)
    is_magic = models.BooleanField(default=False)
    not_buyable = models.BooleanField(default=False)
    not_sellable = models.BooleanField(default=False)

    default_quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="default_quality",
        on_delete=models.PROTECT,
        related_name="default_items",
        default=QUALITY_COMMON,
    )
    weight = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    size_class = models.CharField(max_length=5, choices=GK_CHOICES, default=GK_AVERAGE)

    runes = models.ManyToManyField("Rune", blank=True, related_name="items")
    catalog_group = models.ForeignKey(
        "charsheet.GameGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="catalog_items",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(catalog_group__isnull=True),
                name="uniq_global_item_name",
            ),
            models.UniqueConstraint(
                fields=["catalog_group", "name"],
                condition=models.Q(catalog_group__isnull=False),
                name="uniq_group_item_name",
            ),
        ]

    def clean(self):
        """Prevent invalid stackable armor definitions."""
        super().clean()
        if self.item_type in {
            self.ItemType.SHIELD,
            self.ItemType.CLOTHING,
            *self.weapon_item_type_values(),
            *self.armor_item_type_values(),
        } and self.stackable:
            raise ValidationError({"stackable": f"Type: {self.item_type.upper()} can't be stackable."})
        if (self.is_magic or self.item_type in self.magic_item_type_values()) and self.stackable:
            raise ValidationError({"stackable": f"Type: {self.item_type.upper()} can't be stackable."})

    def __str__(self):
        return f"{self.item_type.upper()}: {self.name}"

    @property
    def is_magic_effective(self) -> bool:
        return bool(self.is_magic or self.item_type in self.magic_item_type_values())

    @classmethod
    def magic_item_type_values(cls) -> frozenset[str]:
        return cls.MAGIC_EQUIPMENT_TYPES

    @classmethod
    def weapon_item_type_values(cls) -> frozenset[str]:
        return cls.WEAPON_ITEM_TYPES

    @classmethod
    def armor_item_type_values(cls) -> frozenset[str]:
        return cls.ARMOR_ITEM_TYPES


class ArmorStats(models.Model):
    """Armor protection, physical component metadata, and covered hit zones."""

    class ComponentType(models.TextChoices):
        HELMET = "helmet", "Helm"
        TORSO = "torso", "Torso"
        ARM_LEFT = "arm_left", "Arm links"
        ARM_RIGHT = "arm_right", "Arm rechts"
        LEG_LEFT = "leg_left", "Bein links"
        LEG_RIGHT = "leg_right", "Bein rechts"

    item = models.OneToOneField(Item, on_delete=models.CASCADE)

    rs_total = models.PositiveIntegerField(default=0)
    zone_rs_overrides = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Optionale RS-Abweichungen einzelner abgedeckter Zonen.<br>"
            "<strong>Verfügbare Schlüssel:</strong><br>"
            "head – Kopf<br>"
            "face – Gesicht<br>"
            "eyes – Augen<br>"
            "neck – Hals<br>"
            "torso – Torso<br>"
            "organs – Organe<br>"
            "soft_tissue – Weichteile<br>"
            "arm_left – Arm links<br>"
            "leg_left – Bein links<br>"
            "arm_right – Arm rechts<br>"
            "leg_right – Bein rechts"
        ),
    )
    component_price_helmet_override = models.PositiveIntegerField("Helm", null=True, blank=True)
    component_price_arms_override = models.PositiveIntegerField("Arme gesamt", null=True, blank=True)
    component_price_legs_override = models.PositiveIntegerField("Beine gesamt", null=True, blank=True)
    component_price_hands_override = models.PositiveIntegerField("Hände gesamt", null=True, blank=True)
    component_price_feet_override = models.PositiveIntegerField("Schuhe gesamt", null=True, blank=True)
    component_price_torso_override = models.PositiveIntegerField("Torso", null=True, blank=True)
    encumbrance = models.PositiveIntegerField(default=0)
    min_st = models.PositiveIntegerField(default=1)

    suppress_component_generation = models.BooleanField(
        default=False,
        help_text="Wenn aktiv, werden aus dieser Rüstung keine physischen Einzelteile erzeugt.",
    )
    parent_set = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="components",
    )
    component_type = models.CharField(
        max_length=20,
        choices=ComponentType.choices,
        blank=True,
        default="",
    )

    covers_head = models.BooleanField(default=False)
    covers_face = models.BooleanField(default=False)
    covers_eyes = models.BooleanField(default=False)
    covers_neck = models.BooleanField(default=False)
    covers_torso = models.BooleanField(default=False)
    covers_organs = models.BooleanField(default=False)
    covers_soft_tissue = models.BooleanField(default=False)
    covers_arm_left = models.BooleanField(default=False)
    covers_hand_left = models.BooleanField(default=False)
    covers_leg_left = models.BooleanField(default=False)
    covers_foot_left = models.BooleanField(default=False)
    covers_arm_right = models.BooleanField(default=False)
    covers_hand_right = models.BooleanField(default=False)
    covers_leg_right = models.BooleanField(default=False)
    covers_foot_right = models.BooleanField(default=False)

    ZONE_FIELDS = (
        "head",
        "face",
        "eyes",
        "neck",
        "torso",
        "organs",
        "soft_tissue",
        "arm_left",
        "hand_left",
        "leg_left",
        "foot_left",
        "arm_right",
        "hand_right",
        "leg_right",
        "foot_right",
    )
    MAIN_ZONE_FIELDS = (
        "head",
        "torso",
        "arm_left",
        "arm_right",
        "leg_left",
        "leg_right",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("parent_set", "component_type"),
                condition=models.Q(parent_set__isnull=False),
                name="uniq_armor_component_per_set",
            ),
        ]

    @property
    def rs(self) -> int:
        """Return the local RS used by every covered zone."""
        return int(self.rs_total)

    def covered_zones(self) -> tuple[str, ...]:
        """Return all detailed hit zones covered by this physical item."""
        return tuple(zone for zone in self.ZONE_FIELDS if getattr(self, f"covers_{zone}", False))

    def rs_sum(self):
        """Return this item's contribution across the six GRS body zones."""
        return self.rs * sum(
            1
            for zone in self.MAIN_ZONE_FIELDS
            if getattr(self, f"covers_{zone}", False)
        )

    def clean(self):
        """Validate armor ownership, component metadata, and coverage."""
        super().clean()
        if self.item.item_type not in Item.armor_item_type_values():
            raise ValidationError({"item_type": "Non armor items can't have ArmorStats"})
        if not self.rs_total:
            raise ValidationError({"rs_total": "Armor must have RS greater than zero."})
        if self.parent_set_id and not self.component_type:
            raise ValidationError({"component_type": "Generated armor components require a component type."})
        if self.component_type and not self.parent_set_id:
            raise ValidationError({"parent_set": "Armor components require a parent armor."})
        if self.parent_set_id and not self.suppress_component_generation:
            raise ValidationError(
                {"suppress_component_generation": "Generated components must not generate further components."}
            )
        if not self.covered_zones():
            raise ValidationError("Armor must cover at least one hit zone.")
        invalid_zone_overrides = {
            str(zone)
            for zone, value in (self.zone_rs_overrides or {}).items()
            if zone not in self.ZONE_FIELDS or not isinstance(value, int) or value < 0
        }
        if invalid_zone_overrides:
            raise ValidationError({"zone_rs_overrides": "Invalid armor zone RS overrides."})

    def save(self, *args, **kwargs):
        """Persist stats and synchronize generated physical armor components."""
        sync_components = kwargs.pop("sync_components", True)
        with transaction.atomic():
            super().save(*args, **kwargs)
            if (
                sync_components
                and not self.parent_set_id
                and self.item.item_type in Item.armor_item_type_values()
            ):
                from charsheet.armor_generation import sync_armor_set_components

                sync_armor_set_components(self)

    def __str__(self):
        return f"{self.item}: RS {self.rs}"


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
    effect_summary = models.TextField(blank=True, default="")

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


class WeaponType(models.Model):
    """Rule-level weapon type used by Waffenmeister and related effects."""

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class WeaponStats(models.Model):
    """Weapon-specific combat data attached to an item."""

    class DamageOperator(models.TextChoices):
        NONE = "", "Kein Operator"
        ADD = "+", "+"
        SUBTRACT = "-", "-"
        DIVIDE = "/", "/"

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    min_st = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    min_st_1h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    min_st_2h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    min_ge_1h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    min_ge_2h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_short = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_medium = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_long = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    reload_time = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    shot_count = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    damage_source = models.ForeignKey(DamageSource, on_delete=models.PROTECT)
    damage_dice_amount = models.PositiveIntegerField(default=1)
    damage_dice_faces = models.PositiveIntegerField(default=10)
    damage_flat_bonus = models.IntegerField(default=0)
    damage_flat_operator = models.CharField(max_length=1, choices=DamageOperator.choices, default=DamageOperator.NONE, blank=True)
    maneuver_attribute_mode = models.CharField(
        max_length=10,
        choices=WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
        default=WEAPON_MANEUVER_ATTRIBUTE_ST,
        help_text="Welcher Attributsmodifikator für Waffenmanöver und Waffenwürfe gilt.",
    )
    damage_bonus_attribute = models.CharField(max_length=20, blank=True, default="")
    damage_bonus_mode = models.CharField(max_length=20, blank=True, default="flat")
    damage_type = models.CharField(max_length=1, default=DEADLY, choices=DAMAGE_TYPE_CHOICES)
    weapon_type = models.ForeignKey(
        "charsheet.WeaponType",
        on_delete=models.PROTECT,
        related_name="weapon_stats",
        null=True,
        blank=True,
        help_text="Regeltechnischer Waffentyp fuer Waffenmeister und aehnliche Effekte.",
    )

    wield_mode = models.CharField(max_length=2, choices=WIELD_MODES, default=ONE_HANDED)

    h2_dice_amount = models.PositiveIntegerField(null=True, blank=True)
    h2_dice_faces = models.PositiveIntegerField(null=True, blank=True)
    h2_flat_bonus = models.IntegerField(null=True, blank=True)
    h2_flat_operator = models.CharField(max_length=1, choices=DamageOperator.choices, default=DamageOperator.NONE, blank=True)
    h2_damage_type = models.CharField(max_length=1, default=DEADLY, choices=DAMAGE_TYPE_CHOICES)

    flags = models.ManyToManyField(WeaponFlag, blank=True)
    skills = models.ManyToManyField(
        "Skill",
        blank=True,
        related_name="weapon_stats",
        help_text="Alle Fertigkeiten, mit denen diese Waffe regeltechnisch gefuehrt werden kann.",
    )

    @property
    def two_handed(self) -> bool:
        """Return whether this weapon has a dedicated two-handed profile."""
        return self.wield_mode in {TWO_HANDED, VERSATILE}

    @property
    def requires_two_handed_damage_profile(self) -> bool:
        """Return whether two-handed damage values are required for this weapon."""
        return self.wield_mode in {TWO_HANDED, VERSATILE}

    @property
    def has_alternate_two_handed_profile(self) -> bool:
        """Return whether the weapon has a second, optional two-handed profile."""
        return self.wield_mode == VERSATILE

    def effective_min_st(self, wield_mode: str | None = None) -> int:
        """Return minimum strength with 1H/2H fallback semantics."""
        base = int(self.min_st or 1)
        one_handed = self.min_st_1h
        two_handed = self.min_st_2h
        if wield_mode == TWO_HANDED:
            return int(two_handed or one_handed or base)
        if wield_mode == ONE_HANDED:
            return int(one_handed or two_handed or base)
        return int(one_handed or two_handed or base)

    def effective_min_ge(self, wield_mode: str | None = None) -> int | None:
        """Return optional minimum agility with 1H/2H fallback semantics."""
        one_handed = self.min_ge_1h
        two_handed = self.min_ge_2h
        if wield_mode == TWO_HANDED:
            return int(two_handed or one_handed) if two_handed or one_handed else None
        if wield_mode == ONE_HANDED:
            return int(one_handed or two_handed) if one_handed or two_handed else None
        return int(one_handed or two_handed) if one_handed or two_handed else None

    @property
    def range_label(self) -> str:
        """Return a compact short/medium/long range label."""
        values = [self.range_short, self.range_medium, self.range_long]
        if not any(value is not None for value in values):
            return ""
        return "/".join(str(value) if value is not None else "-" for value in values)

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
    def maneuver_attribute_codes(self) -> tuple[str, ...]:
        """Return the attribute codes that contribute to this weapon's maneuvers."""
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_GE:
            return (ATTR_GE,)
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_BOTH:
            return (ATTR_ST, ATTR_GE)
        return (ATTR_ST,)

    @property
    def two_handed_damage(self) -> str | None:
        """Return two-handed damage in dice notation if available."""
        if not self.requires_two_handed_damage_profile or self.h2_dice_amount is None or self.h2_dice_faces is None:
            return None
        label = self.format_damage_label(
            self.h2_dice_amount,
            self.h2_dice_faces,
            self.h2_flat_bonus,
            self.h2_flat_operator,
        )
        return f"{label} {self.h2_damage_type}".strip()

    @classmethod
    def format_damage_label(cls, dice_amount: int, dice_faces: int, bonus: int | None, operator: str | None) -> str:
        """Return classic damage notation with a configurable operator."""
        resolved_dice_amount = int(dice_amount or 0)
        resolved_dice_faces = int(dice_faces or 0)
        damage = str(resolved_dice_amount) if resolved_dice_faces <= 0 else f"{resolved_dice_amount}w{resolved_dice_faces}"
        resolved_bonus = int(bonus or 0)
        resolved_operator = str(operator or "")
        if not resolved_bonus:
            return damage
        if resolved_dice_faces <= 0:
            if resolved_operator == cls.DamageOperator.SUBTRACT:
                return str(resolved_dice_amount - resolved_bonus)
            if resolved_operator in ("", cls.DamageOperator.ADD):
                return str(resolved_dice_amount + resolved_bonus)
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
        if self.item.item_type not in Item.weapon_item_type_values():
            raise ValidationError({"item": "Non-weapon items can't have WeaponStats"})

        has_h2_values = (
            self.h2_dice_amount is not None
            or self.h2_dice_faces is not None
            or self.h2_flat_bonus is not None
            or bool(self.h2_flat_operator)
        )
        if self.requires_two_handed_damage_profile:
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
            return f"{self.item}: DMG {base} ({self.get_damage_type_display()}) / 2H {alt} ({self.get_h2_damage_type_display()})"

        return f"{self.item}: DMG {base} ({self.get_damage_type_display()})"


class RaceStartingItem(models.Model):
    race = models.ForeignKey("charsheet.Race", on_delete=models.CASCADE, related_name="starting_items")
    item = models.ForeignKey("charsheet.Item", on_delete=models.CASCADE, related_name="race_starting_items")
    amount = models.PositiveIntegerField(default=1)
    quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="quality",
        on_delete=models.PROTECT,
        related_name="race_starting_items",
        blank=True,
        null=True,
    )
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
            Item.ItemType.SHIELD,
            Item.ItemType.CLOTHING,
            *Item.weapon_item_type_values(),
            *Item.armor_item_type_values(),
            *Item.magic_item_type_values(),
        }:
            raise ValidationError({"item": "Race items must be equippable items because they are always equipped."})

    def __str__(self):
        return f"{self.race} -> {self.item} x{self.amount}"
