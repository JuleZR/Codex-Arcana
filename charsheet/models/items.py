"""Item and equipment definition models."""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
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
    TWO_HANDED,
    VERSATILE,
    WEAPON_SYMBOL_CHOICES,
    WEAPON_MANEUVER_ATTRIBUTE_BOTH,
    WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
    WEAPON_MANEUVER_ATTRIBUTE_GE,
    WEAPON_MANEUVER_ATTRIBUTE_NONE,
    WEAPON_MANEUVER_ATTRIBUTE_ST,
    WIELD_MODES,
)
from .core import DamageSource, Race
from .core import (
    MODIFIER_OPERATOR_CHOICES,
    MODIFIER_VISIBILITY_CHOICES,
    STACK_BEHAVIOR_CHOICES,
    TARGET_DOMAIN_CHOICES,
)
from .semantic_effects import SemanticEffectFields
from decimal import Decimal


class Quality(models.Model):
    """Shared quality tier and its rule-relevant configuration."""

    code = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    hex_color = models.CharField(
        max_length=7,
        default="#33CC33",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Enter a hex color like #33CC33.",
            )
        ],
    )
    sort_order = models.SmallIntegerField(default=0)

    is_default = models.BooleanField(
        default=False,
        editable=False,
    )

    # Preis
    price_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    # Waffen
    weapon_damage_modifier = models.SmallIntegerField(default=0)
    weapon_maneuver_modifier = models.SmallIntegerField(default=0)

    # Rüstungen
    armor_rs_modifier = models.SmallIntegerField(default=0)
    armor_min_st_modifier = models.SmallIntegerField(default=0)
    armor_encumbrance_modifier = models.SmallIntegerField(default=0)

    # Werkzeuge / Instrumente / Utensilien
    skill_modifier = models.SmallIntegerField(default=0)

    # Haltbarkeit
    structure_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    hardness_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    lifespan_multiplier = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )

    # Kreaturendarstellung / Kreaturentraining
    creature_kind_label = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    creature_training_advantage_points = models.PositiveSmallIntegerField(
        default=0,
    )
    creature_training_disadvantage_points = models.PositiveSmallIntegerField(
        default=0,
    )

    class HolographicStyle(models.TextChoices):
        NONE = "", "Kein Holo"
        GOLD = "gold", "Gold"
        RAINBOW = "rainbow", "Rainbow"

    holographic_style = models.CharField(
        max_length=20,
        choices=HolographicStyle.choices,
        blank=True,
        default="",
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "qualities"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_quality",
            ),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        return cls.objects.get(is_default=True)

    @classmethod
    def resolve(cls, value, *, use_default=False):
        if isinstance(value, cls):
            return value

        code = str(value or "").strip()
        if code:
            quality = cls.objects.filter(pk=code).first()
            if quality is not None:
                return quality

        if use_default:
            return cls.get_default()

        raise cls.DoesNotExist(f"Unknown quality: {value!r}")


class Metal(models.Model):
    """Special metal with rule-relevant item modifiers."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    descirption = models.TextField(blank=True)

    price_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )
    ms_modifier = models.IntegerField(default=0)
    weight_multiplier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )

    quality_overwrite = models.ForeignKey(
        "charsheet.Quality",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="metal_overwrites",
    )

    apply_quality_effects = models.BooleanField(
        default=True,
        help_text=(
            "Wenn deaktiviert, überschreibt das Metall die angezeigte Qualität, "
            "ohne deren regeltechnische Qualitätsboni anzuwenden."
        ),
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def default_quality_pk():
    return Quality.get_default().pk


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


class RuneSemanticEffect(SemanticEffectFields):
    """Persisted semantic effect attached directly to one reusable rune."""

    rune = models.ForeignKey(Rune, on_delete=models.CASCADE, related_name="semantic_effects")

    class Meta:
        ordering = ["rune", "sort_order", "id"]

    def __str__(self):
        return f"{self.rune.name}: {self.target_domain}/{self.target_key} ({self.operator})"

    def semantic_source_type(self) -> str:
        return "rune"

    def semantic_source_id(self) -> str:
        return str(self.rune_id)

    def semantic_source_label(self) -> str:
        return str(self.rune)

    def semantic_effect_key_prefix(self) -> str:
        return "rune_effect"


class Item(models.Model):
    """Inventory item that may be owned, stacked, or equipped."""

    MAGIC_EQUIPMENT_TYPES = frozenset({"ring", "amulet", "magical_weapon", "magical_armor"})
    WEAPON_ITEM_TYPES = frozenset({"weapon", "magical_weapon"})
    ARMOR_ITEM_TYPES = frozenset({"armor", "magical_armor"})
    ARMOR_STATS_ITEM_TYPES = frozenset({"armor", "magical_armor", "ring", "amulet"})
    SHIELD_STATS_ITEM_TYPES = frozenset({"shield", "magical_armor"})

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
    invested_cp = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional investierte CP fuer skalierende magische Items, z.B. 2/4/6/8/10.",
    )
    invested_cp_steps = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optionale Beschreibung der CP-Schritte, z.B. 2/4/6/8/10.",
    )

    default_quality = models.ForeignKey(
        "charsheet.Quality",
        db_column="default_quality",
        on_delete=models.PROTECT,
        related_name="default_items",
        default=default_quality_pk,
    )

    metal = models.ForeignKey(
        "charsheet.Metal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="items",
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

    @classmethod
    def armor_stats_item_type_values(cls) -> frozenset[str]:
        return cls.ARMOR_STATS_ITEM_TYPES

    @classmethod
    def shield_stats_item_type_values(cls) -> frozenset[str]:
        return cls.SHIELD_STATS_ITEM_TYPES


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
        if self.item.item_type not in Item.armor_stats_item_type_values():
            raise ValidationError({"item": "Only armor-capable items can have ArmorStats"})
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

    class DamageOperator(models.TextChoices):
        NONE = "", "Kein Operator"
        ADD = "+", "+"
        SUBTRACT = "-", "-"
        DIVIDE = "/", "/"

    item = models.OneToOneField(Item, on_delete=models.CASCADE)

    rs = models.PositiveIntegerField(default=0)
    encumbrance = models.PositiveIntegerField(default=0)
    min_st = models.PositiveIntegerField(default=1)
    parade_bonus = models.IntegerField(
        default=0,
        help_text="Bonus auf die Fertigkeit Schilde, wenn mit diesem Schild verteidigt wird.",
    )
    damage_source = models.ForeignKey(DamageSource, on_delete=models.PROTECT, null=True, blank=True)
    damage_dice_amount = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    damage_dice_faces = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    damage_flat_bonus = models.IntegerField(default=0)
    damage_flat_operator = models.CharField(max_length=1, choices=DamageOperator.choices, default=DamageOperator.NONE, blank=True)
    maneuver_attribute_mode = models.CharField(
        max_length=10,
        choices=WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
        default=WEAPON_MANEUVER_ATTRIBUTE_ST,
        help_text="Welcher Attributsmodifikator fuer offensive Schildaktionen gilt.",
    )
    damage_type = models.CharField(max_length=1, default=DEADLY, choices=DAMAGE_TYPE_CHOICES)
    weapon_type = models.ForeignKey(
        "charsheet.WeaponType",
        on_delete=models.PROTECT,
        related_name="shield_stats",
        null=True,
        blank=True,
        help_text="Regeltechnischer Waffentyp, falls dieser Schild offensiv gefuehrt werden kann.",
    )
    skills = models.ManyToManyField(
        "Skill",
        blank=True,
        related_name="shield_stats",
        help_text="Alle Fertigkeiten, mit denen dieser Schild offensiv gefuehrt werden kann.",
    )

    @property
    def has_damage_profile(self) -> bool:
        """Return whether this shield also carries offensive combat data."""
        dice_amount = int(self.damage_dice_amount or 0)
        dice_faces = int(self.damage_dice_faces or 0)
        flat_bonus = int(self.damage_flat_bonus or 0)
        if dice_faces == 0:
            return bool(dice_amount or flat_bonus)
        return self.damage_dice_amount is not None and self.damage_dice_faces is not None

    @property
    def can_be_wielded_as_weapon(self) -> bool:
        """Return whether this shield should be accepted by weapon-slot handling."""
        return self.has_damage_profile or self.weapon_type_id is not None or self.skills.exists()

    @property
    def damage(self) -> str:
        """Return optional shield damage in classic or shield-range notation."""
        if self.damage_dice_amount is None or self.damage_dice_faces is None:
            return ""
        if int(self.damage_dice_faces or 0) == 0:
            lower = int(self.damage_dice_amount or 0)
            upper = int(self.damage_flat_bonus or 0)
            if not lower and not upper:
                return ""
            if lower and upper:
                label = f"{lower}-{upper}"
            elif lower:
                label = str(lower)
            elif upper:
                label = str(upper)
            return f"{label} {self.damage_type}".strip()
        return WeaponStats.format_damage_label(
            self.damage_dice_amount,
            self.damage_dice_faces,
            self.damage_flat_bonus,
            self.damage_flat_operator,
        )

    @property
    def maneuver_attribute_codes(self) -> tuple[str, ...]:
        """Return the attribute codes that contribute to this shield's offensive use."""
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_NONE:
            return ()
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_GE:
            return (ATTR_GE,)
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_BOTH:
            return (ATTR_ST, ATTR_GE)
        return (ATTR_ST,)

    def clean(self):
        super().clean()
        if self.item.item_type not in Item.shield_stats_item_type_values():
            raise ValidationError(
                {"item": "Only shields and magical armor can have ShieldStats."}
            )
        if self.has_damage_profile:
            errors = {}
            if self.damage_source_id is None:
                errors["damage_source"] = "Shield damage needs a damage source."
            if self.damage_dice_amount is None:
                self.damage_dice_amount = 0
            if self.damage_dice_faces is None:
                self.damage_dice_faces = 0
            if int(self.damage_dice_faces or 0) > 0 and int(self.damage_dice_amount or 0) <= 0:
                errors["damage_dice_amount"] = "Shield dice damage needs dice amount greater than zero."
            if errors:
                raise ValidationError(errors)

    def __str__(self):
        damage = f", DMG {self.damage}" if self.damage else ""
        return f"{self.item}: RS {self.rs}{damage}"


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


class ItemSemanticEffectFields(models.Model):
    """Shared persisted item semantic effect fields."""

    class ScaleSource(models.TextChoices):
        NONE = "", "-"
        ITEM_INVESTED_CP = "item_invested_cp", "Investierte CP des Items"

    sort_order = models.PositiveIntegerField(default=0)
    target_domain = models.CharField(max_length=40, choices=TARGET_DOMAIN_CHOICES, default="rule_flag")
    target_key = models.CharField(max_length=120, blank=True, default="")
    operator = models.CharField(max_length=40, choices=MODIFIER_OPERATOR_CHOICES, default="flat_add")
    mode = models.CharField(max_length=20, default="flat")
    value = models.CharField(max_length=200, blank=True, default="")
    scale_source = models.CharField(max_length=40, choices=ScaleSource.choices, blank=True, default="")
    scale_divisor = models.PositiveSmallIntegerField(null=True, blank=True)
    value_min = models.IntegerField(null=True, blank=True)
    value_max = models.IntegerField(null=True, blank=True)
    formula = models.CharField(max_length=200, blank=True, default="")
    scaling = models.JSONField(default=dict, blank=True)
    stack_behavior = models.CharField(max_length=40, choices=STACK_BEHAVIOR_CHOICES, default="stack")
    condition_set = models.JSONField(default=dict, blank=True)
    condition_races = models.ManyToManyField(
        Race,
        blank=True,
        related_name="%(class)s_conditions",
        help_text="Optional race condition. Leave empty to apply to every race.",
    )
    condition_schools = models.ManyToManyField(
       "charsheet.School",
       blank=True,
       related_name="%(class)s_school_conditions",
       help_text="Optional school condition. Leave empty to apply to every school.",
    )
    active_flag = models.BooleanField(default=True)
    toggleable = models.BooleanField(default=False)
    toggle_state_inverted = models.BooleanField(default=False)
    display_group = models.PositiveSmallIntegerField(null=True, blank=True)
    display_group_append = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    rules_text = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=20, choices=MODIFIER_VISIBILITY_CHOICES, default="public")
    hidden = models.BooleanField(default=False)
    sheet_relevant = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    @staticmethod
    def _coerce_scalar(raw_value):
        import json

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
        for field_name in ("scaling", "condition_set", "metadata"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, dict):
                raise ValidationError({field_name: "Value must be a JSON object."})

    def semantic_source_type(self) -> str:
        raise NotImplementedError

    def semantic_source_id(self) -> str:
        raise NotImplementedError

    def semantic_source_label(self) -> str:
        raise NotImplementedError

    def item_invested_cp(self) -> int | None:
        return None

    def to_modifier(self, *, invested_cp: int | None = None):
        """Materialize this persisted effect as one typed modifier instance."""
        from ..modifiers.definitions import (
            AttributeCapModifier,
            AttributeModifier,
            BaseModifier,
            CombatModifier,
            ConditionSet,
            DerivedStatModifier,
            EconomyModifier,
            ItemModifier,
            LanguageModifier,
            MovementModifier,
            PerceptionModifier,
            ProficiencyGroupModifier,
            ResourceModifier,
            ResistanceModifier,
            RuleFlagModifier,
            SkillModifier,
            SocialModifier,
            SpecializationModifier,
            TraitModifier,
        )
        from ..modifiers.targets import TargetResolver

        modifier_map = {
            "skill": SkillModifier,
            "skill_category": SkillModifier,
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
            "item": ItemModifier,
            "item_category": ItemModifier,
            "specialization": SpecializationModifier,
        }
        metadata = dict(self.metadata or {})
        core_stat_targets = {"initiative", "vw", "sr", "gw", "arcane_power", "potential"}
        note_implies_condition = (
            (self.target_domain == "derived_stat" and self.target_key in core_stat_targets)
            or self.target_domain in {"skill", "skill_category"}
        )
        if (
            note_implies_condition
            and not str(metadata.get("condition_text") or "").strip()
            and str(self.notes or "").strip()
        ):
            metadata["condition_text"] = " ".join(str(self.notes or "").split())
        if self.pk:
            metadata["semantic_effect_key"] = f"item_effect:{self.pk}"
            metadata["semantic_effect_label"] = self.semantic_source_label()
            condition_race_ids = list(self.condition_races.order_by("id").values_list("id", flat=True))
            if condition_race_ids:
                metadata["condition_race_ids"] = condition_race_ids
            condition_school_ids = list(
                self.condition_schools.order_by("id").values_list("id", flat=True)
            )
            if condition_school_ids:
                metadata["condition_school_ids"] = condition_school_ids
        resolved_invested_cp = self.item_invested_cp() if invested_cp is None else invested_cp
        if resolved_invested_cp is not None:
            metadata["item_invested_cp"] = resolved_invested_cp
        mode = self.mode
        scaling = dict(self.scaling or {})
        if self.scale_source:
            mode = "scaled"
            scaling.update(
                {
                    "scale_source": self.scale_source,
                    "mul": 1,
                    "div": self.scale_divisor or 1,
                    "round_mode": "floor",
                }
            )
        resolved_target = TargetResolver.resolve(self.target_domain, self.target_key, metadata)
        for key, values in resolved_target.context_requirements.items():
            if key == "weapon_types":
                metadata.setdefault("target_weapon_type", list(values))
            elif key == "weapon_skill_slugs":
                metadata.setdefault("target_weapon_skill", list(values))
            elif key == "weapon_categories":
                metadata.setdefault("target_weapon_category", list(values))
            elif key == "weapon_ids":
                metadata.setdefault("target_weapon_id", list(values))
        modifier_cls = modifier_map.get(resolved_target.domain, BaseModifier)
        return modifier_cls(
            source_type=self.semantic_source_type(),
            source_id=self.semantic_source_id(),
            target_domain=resolved_target.domain,
            target_key=resolved_target.key,
            mode=mode,
            value=self._coerce_scalar(self.value),
            value_min=self.value_min,
            value_max=self.value_max,
            formula=self.formula,
            scaling=scaling,
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


class ItemSemanticEffect(ItemSemanticEffectFields):
    """Persisted semantic effect attached directly to one base item definition."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="semantic_effects")

    class Meta:
        ordering = ["item", "sort_order", "id"]

    def __str__(self):
        return f"{self.item}: {self.target_domain}/{self.target_key} ({self.operator})"

    def semantic_source_type(self) -> str:
        return "item"

    def semantic_source_id(self) -> str:
        return str(self.item_id)

    def semantic_source_label(self) -> str:
        return str(self.item)

    def item_invested_cp(self) -> int | None:
        return self.item.invested_cp


class CharacterItemSemanticEffect(ItemSemanticEffectFields):
    """Persisted semantic effect attached directly to one concrete item instance."""

    character_item = models.ForeignKey("CharacterItem", on_delete=models.CASCADE, related_name="semantic_effects")

    class Meta:
        ordering = ["character_item", "sort_order", "id"]

    def __str__(self):
        return f"{self.character_item}: {self.target_domain}/{self.target_key} ({self.operator})"

    def semantic_source_type(self) -> str:
        return "characteritem"

    def semantic_source_id(self) -> str:
        return str(self.character_item_id)

    def semantic_source_label(self) -> str:
        return str(self.character_item)

    def item_invested_cp(self) -> int | None:
        return self.character_item.invested_cp if self.character_item.invested_cp is not None else self.character_item.item.invested_cp


class CharacterItemDisclosure(models.Model):
    """Player-facing disclosure state for one concrete item field."""

    character_item = models.ForeignKey(
        "CharacterItem",
        on_delete=models.CASCADE,
        related_name="disclosures",
    )
    field_key = models.CharField(max_length=80)
    revealed = models.BooleanField(default=True)
    alternative_text = models.TextField(blank=True, default="")
    alternative_image = models.ImageField(
        upload_to="character_item_disclosures/",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["character_item", "field_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["character_item", "field_key"],
                name="uniq_character_item_disclosure_field",
            ),
        ]

    def __str__(self):
        state = "visible" if self.revealed else "hidden"
        return f"{self.character_item}: {self.field_key} ({state})"


class CharacterItemIdentificationState(models.Model):
    """Marks that a concrete item uses explicit effect identification rules."""

    character_item = models.OneToOneField(
        "CharacterItem",
        on_delete=models.CASCADE,
        related_name="identification_state",
    )
    initialized = models.BooleanField(default=True)

    class Meta:
        ordering = ["character_item"]

    def __str__(self):
        state = "initialized" if self.initialized else "legacy"
        return f"{self.character_item}: {state}"


class CharacterItemEffectIdentification(models.Model):
    """Identification state for one concrete item effect source."""

    character_item = models.ForeignKey(
        "CharacterItem",
        on_delete=models.CASCADE,
        related_name="effect_identifications",
    )
    item_effect = models.ForeignKey(
        "ItemSemanticEffect",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="character_item_identifications",
    )
    character_item_effect = models.ForeignKey(
        "CharacterItemSemanticEffect",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="identifications",
    )
    identified = models.BooleanField(default=False)
    alternative_text = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["character_item", "item_effect", "character_item_effect"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(item_effect__isnull=False)
                        & models.Q(character_item_effect__isnull=True)
                    )
                    | (
                        models.Q(item_effect__isnull=True)
                        & models.Q(character_item_effect__isnull=False)
                    )
                ),
                name="character_item_identification_exactly_one_effect",
            ),
            models.UniqueConstraint(
                fields=["character_item", "item_effect"],
                condition=models.Q(item_effect__isnull=False),
                name="uniq_character_item_item_effect_identification",
            ),
            models.UniqueConstraint(
                fields=["character_item", "character_item_effect"],
                condition=models.Q(character_item_effect__isnull=False),
                name="uniq_character_item_instance_effect_identification",
            ),
        ]

    def clean(self):
        super().clean()
        if bool(self.item_effect_id) == bool(self.character_item_effect_id):
            raise ValidationError("Exactly one effect source is required.")
        if self.character_item_effect_id and self.character_item_id:
            if self.character_item_effect.character_item_id != self.character_item_id:
                raise ValidationError(
                    {"character_item_effect": "Effect must belong to this character item."}
                )
        if self.item_effect_id and self.character_item_id:
            if self.item_effect.item_id != self.character_item.item_id:
                raise ValidationError(
                    {"item_effect": "Effect must belong to this character item's base item."}
                )

    def __str__(self):
        effect = self.character_item_effect or self.item_effect
        state = "identified" if self.identified else "unknown"
        return f"{self.character_item}: {effect} ({state})"


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

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="weapon_stats"
    )
    profile_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Optionaler Name dieses Waffenprofils, z. B. Rapier oder Main-Gauche."
    )
    min_st = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    min_st_1h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    min_st_2h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    min_ge_1h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    min_ge_2h = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_short = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_medium = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_long = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    range_strength_multiplier = models.BooleanField(default=False)
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

        label = " / ".join(
            str(value) if value is not None else "-"
            for value in values
        )

        return f"St x {label}" if self.range_strength_multiplier else label

    def effective_range_label(self, strength: int | None = None) -> str:
        """Return range values after applying the optional strength multiplier."""
        if not self.range_strength_multiplier:
            return self.range_label

        if strength is None:
            return self.range_label

        values = [self.range_short, self.range_medium, self.range_long]
        if not any(value is not None for value in values):
            return ""

        multiplier = max(0, int(strength or 0))

        return " / ".join(
            str(int(value) * multiplier) if value is not None else "-"
            for value in values
        )

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
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_NONE:
            return ()
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


class RangedWeaponStats(models.Model):
    """Ranged-weapon combat data attached to an item."""

    item = models.OneToOneField(Item, on_delete=models.CASCADE)
    damage_label = models.CharField(max_length=50, blank=True, default="")
    damage_dice_amount = models.PositiveIntegerField(default=1)
    damage_dice_faces = models.PositiveIntegerField(default=10)
    damage_flat_bonus = models.IntegerField(default=0)
    damage_flat_operator = models.CharField(
        max_length=1,
        choices=WeaponStats.DamageOperator.choices,
        default=WeaponStats.DamageOperator.NONE,
        blank=True,
    )
    damage_type = models.CharField(max_length=1, default=DEADLY, choices=DAMAGE_TYPE_CHOICES)
    weapon_type = models.ForeignKey(
        "charsheet.WeaponType",
        on_delete=models.PROTECT,
        related_name="ranged_weapon_stats",
        null=True,
        blank=True,
        help_text="Regeltechnischer Waffentyp fuer Waffenmeister und aehnliche Effekte.",
    )
    maneuver_attribute_mode = models.CharField(
        max_length=10,
        choices=WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
        default=WEAPON_MANEUVER_ATTRIBUTE_NONE,
        help_text="Welcher Attributsmodifikator fuer Fernkampf-Manoever und Waffenwuerfe gilt.",
    )
    range_short = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    range_medium = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    range_long = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    range_strength_multiplier = models.BooleanField(default=False)
    reload_time = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    shots = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    minimum_strength = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    skills = models.ManyToManyField(
        "Skill",
        blank=True,
        related_name="ranged_weapon_stats",
        help_text="Alle Fertigkeiten, mit denen diese Fernkampfwaffe regeltechnisch gefuehrt werden kann.",
    )
    flags = models.ManyToManyField(WeaponFlag, blank=True)

    @property
    def damage(self) -> str:
        """Return ranged damage in classic dice notation."""
        label = WeaponStats.format_damage_label(
            self.damage_dice_amount,
            self.damage_dice_faces,
            self.damage_flat_bonus,
            self.damage_flat_operator,
        )
        prefix = str(self.damage_label or "").strip()
        return f"{prefix} {label}".strip()

    @property
    def range_label(self) -> str:
        """Return stored short/medium/long range values."""
        label = " / ".join(str(value) for value in (self.range_short, self.range_medium, self.range_long))
        return f"St x {label}" if self.range_strength_multiplier else label

    def effective_range_label(self, strength: int | None = None) -> str:
        """Return range values after applying the optional strength multiplier."""
        if not self.range_strength_multiplier:
            return self.range_label
        if strength is None:
            return self.range_label
        multiplier = max(0, int(strength or 0))
        return " / ".join(str(int(value or 0) * multiplier) for value in (self.range_short, self.range_medium, self.range_long))

    @property
    def has_damage_profile(self) -> bool:
        """Expose the same capability shape used by shield offensive profiles."""
        return True

    @property
    def maneuver_attribute_codes(self) -> tuple[str, ...]:
        """Return the attribute codes that contribute to this ranged weapon's maneuvers."""
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_NONE:
            return ()
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_GE:
            return (ATTR_GE,)
        if self.maneuver_attribute_mode == WEAPON_MANEUVER_ATTRIBUTE_BOTH:
            return (ATTR_ST, ATTR_GE)
        return (ATTR_ST,)

    def clean(self):
        super().clean()
        if self.item.item_type not in Item.weapon_item_type_values():
            raise ValidationError({"item": "Non-weapon items can't have RangedWeaponStats"})

    def __str__(self):
        return f"{self.item}: Ranged DMG {self.damage} ({self.get_damage_type_display()})"


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
