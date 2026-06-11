"""Helpers for item prices, quality effects, and equipment stat lookups."""

from decimal import Decimal

from charsheet.constants import (
    ATTR_GE,
    ATTR_ST,
    ONE_HANDED,
    QUALITY_BEL_MODS,
    QUALITY_CHOICES,
    QUALITY_COLOR_MAP,
    QUALITY_COMMON,
    QUALITY_EXCELLENT,
    QUALITY_LEGENDARY,
    QUALITY_POOR,
    QUALITY_PRICE_MODS,
    QUALITY_VERY_POOR,
    QUALITY_WRETCHED,
    TWO_HANDED,
    VERSATILE,
    WEAPON_MANEUVER_ATTRIBUTE_BOTH,
    WEAPON_MANEUVER_ATTRIBUTE_GE,
    WEAPON_MANEUVER_ATTRIBUTE_ST,
    WEAPON_SYMBOL_DESCRIPTIONS,
)
from charsheet.models import ArmorStats, CharacterItem, Item, ShieldStats, WeaponStats


WEAPON_DAMAGE_QUALITY_BONUSES = {
    QUALITY_POOR: -1,
    QUALITY_VERY_POOR: -2,
    QUALITY_WRETCHED: -3,
    QUALITY_EXCELLENT: 1,
    QUALITY_LEGENDARY: 1,
}

WEAPON_MANEUVER_QUALITY_BONUSES = {
    QUALITY_POOR: -1,
    QUALITY_VERY_POOR: -2,
    QUALITY_WRETCHED: -3,
    QUALITY_LEGENDARY: 1,
}


class ItemEngine:
    """Resolve derived item values for base items and owned inventory rows."""

    def __init__(self, obj: Item | CharacterItem):
        self.obj = obj

    @staticmethod
    def normalize_quality(quality: str | None) -> str:
        """Return a valid quality key, falling back to common quality."""
        valid_quality_values = {value for value, _label in QUALITY_CHOICES}
        if quality in valid_quality_values:
            return str(quality)
        return QUALITY_COMMON

    @classmethod
    def quality_color(cls, quality: str | None) -> str:
        """Return the configured UI color for one quality tier."""
        return QUALITY_COLOR_MAP.get(cls.normalize_quality(quality), QUALITY_COLOR_MAP[QUALITY_COMMON])

    @classmethod
    def price_for_item_and_quality(cls, item: Item, quality: str | None) -> int:
        """Return one item price adjusted relative to the item's default quality."""
        resolved_quality = cls.normalize_quality(quality)
        return int(item.price * cls._quality_price_multiplier(item.default_quality, resolved_quality))

    @classmethod
    def _quality_price_multiplier(cls, base_quality: str | None, effective_quality: str | None) -> float:
        """Return the price factor from the stored base quality to another quality."""
        base_mod = QUALITY_PRICE_MODS.get(cls.normalize_quality(base_quality), 1)
        effective_mod = QUALITY_PRICE_MODS.get(cls.normalize_quality(effective_quality), 1)
        if not base_mod:
            return float(effective_mod)
        return float(effective_mod) / float(base_mod)

    def _get_item(self) -> Item:
        """Return the underlying base item regardless of wrapper type."""
        if isinstance(self.obj, Item):
            return self.obj
        if isinstance(self.obj, CharacterItem):
            return self.obj.item
        raise TypeError("ItemEngine expects Item or CharacterItem")

    def _get_character_item(self) -> CharacterItem | None:
        if isinstance(self.obj, CharacterItem):
            return self.obj
        return None

    def _get_override_value(self, override_field: str, fallback):
        character_item = self._get_character_item()
        if character_item is None:
            return fallback
        override_value = getattr(character_item, override_field)
        if override_value in (None, ""):
            return fallback
        return override_value

    def _get_weapon_stats(self) -> WeaponStats | None:
        return getattr(self._get_item(), "weaponstats", None)

    def _get_armor_stats(self) -> ArmorStats | None:
        return getattr(self._get_item(), "armorstats", None)

    def _get_shield_stats(self) -> ShieldStats | None:
        return getattr(self._get_item(), "shieldstats", None)

    def get_effective_quality(self) -> str:
        """Return the quality used for calculations and display."""
        if isinstance(self.obj, CharacterItem):
            return self.normalize_quality(self.obj.quality)
        return self.normalize_quality(self._get_item().default_quality)

    def get_base_quality(self) -> str:
        """Return the quality already baked into the stored item stats."""
        return self.normalize_quality(self._get_item().default_quality)

    def get_quality_color(self) -> str:
        """Return the UI color for the effective quality."""
        return self.quality_color(self.get_effective_quality())

    def get_weight(self) -> Decimal:
        """Return base or stacked item weight."""
        item = self._get_item()
        weight = self._get_override_value("weight_override", item.weight)
        if isinstance(self.obj, CharacterItem):
            return weight * self.obj.amount
        return weight

    def get_base_price(self) -> int:
        """Return the item's unmodified base price."""
        return int(self._get_override_value("price_override", self._get_item().price))

    def get_price(self) -> int:
        """Return the price for the effective quality."""
        return self.get_price_for_quality(self.get_effective_quality())

    def get_price_for_quality(self, quality: str) -> int:
        """Return price for an arbitrary quality without mutating object state."""
        resolved_quality = self.normalize_quality(quality)
        return int(self.get_base_price() * self._quality_price_multiplier(self.get_base_quality(), resolved_quality))

    def get_name(self) -> str:
        """Return the effective display name."""
        return str(self._get_override_value("name_override", self._get_item().name))

    def get_size_class(self) -> str:
        """Return the stored item size class."""
        return str(self._get_override_value("size_class_override", self._get_item().size_class))

    def get_weapon_min_st(self, wield_mode: str | None = None) -> int | None:
        """Return the minimum strength needed for this weapon profile."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        override = self._get_override_value("weapon_min_st_override", None)
        if override is not None:
            return int(override)
        return stats.effective_min_st(wield_mode)

    def get_weapon_min_ge(self, wield_mode: str | None = None) -> int | None:
        """Return the optional minimum agility needed for this weapon profile."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.effective_min_ge(wield_mode)

    def get_weapon_min_attribute_label(self, wield_mode: str | None = None) -> str:
        """Return compact minimum attribute requirements for table display."""
        min_st = self.get_weapon_min_st(wield_mode)
        min_ge = self.get_weapon_min_ge(wield_mode)
        if min_ge is None:
            return str(min_st) if min_st is not None else "-"
        if min_st is None:
            return f"Ge {min_ge}"
        return f"{min_st} (Ge {min_ge})"

    def get_weapon_range_label(self) -> str:
        """Return the compact short/medium/long weapon range label."""
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        return stats.range_label

    def get_weapon_reload_time(self) -> int | None:
        """Return the weapon reload time if configured."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.reload_time

    def get_weapon_shot_count(self) -> int | None:
        """Return the weapon shot count if configured."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.shot_count

    def get_weapon_type(self) -> str:
        """Return the effective weapon type used for matching and UI."""
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        weapon_type = self._get_override_value("weapon_type_override", stats.weapon_type)
        return str(getattr(weapon_type, "slug", "") or "")

    def get_weapon_maneuver_attribute_mode(self) -> str:
        """Return the active attribute mode for this weapon's maneuvers."""
        stats = self._get_weapon_stats()
        if not stats:
            return WEAPON_MANEUVER_ATTRIBUTE_ST
        return str(
            self._get_override_value(
                "weapon_maneuver_attribute_override",
                getattr(stats, "maneuver_attribute_mode", WEAPON_MANEUVER_ATTRIBUTE_ST),
            )
            or WEAPON_MANEUVER_ATTRIBUTE_ST
        )

    def get_weapon_maneuver_attribute_codes(self) -> tuple[str, ...]:
        """Return the attribute codes that add to this weapon's maneuvers."""
        mode = self.get_weapon_maneuver_attribute_mode()
        if mode == WEAPON_MANEUVER_ATTRIBUTE_GE:
            return (ATTR_GE,)
        if mode == WEAPON_MANEUVER_ATTRIBUTE_BOTH:
            return (ATTR_ST, ATTR_GE)
        return (ATTR_ST,)

    def get_weapon_maneuver_attribute_label(self) -> str:
        """Return the short label for the active maneuver attribute mode."""
        labels = {
            WEAPON_MANEUVER_ATTRIBUTE_ST: "ST",
            WEAPON_MANEUVER_ATTRIBUTE_GE: "GE",
            WEAPON_MANEUVER_ATTRIBUTE_BOTH: "ST oder GE",
        }
        return labels.get(self.get_weapon_maneuver_attribute_mode(), "ST")

    def get_weapon_wield_mode(self) -> str | None:
        """Return the configured wield mode code."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return str(self._get_override_value("weapon_wield_mode_override", stats.wield_mode))

    def get_weapon_damage_quality_bonus(self) -> int:
        """Return the flat quality bonus applied to weapon damage."""
        return self._quality_bonus_delta(WEAPON_DAMAGE_QUALITY_BONUSES)

    def get_weapon_maneuver_quality_bonus(self) -> int:
        """Return the quality bonus or penalty applied to maneuver values."""
        return self._quality_bonus_delta(WEAPON_MANEUVER_QUALITY_BONUSES)

    def _quality_bonus_delta(self, bonus_map: dict[str, int]) -> int:
        """Return only the quality bonus not already included in base item stats."""
        effective_bonus = int(bonus_map.get(self.get_effective_quality(), 0) or 0)
        base_bonus = int(bonus_map.get(self.get_base_quality(), 0) or 0)
        return effective_bonus - base_bonus

    @staticmethod
    def _apply_quality_to_damage_bonus(base_bonus: int, operator: str, quality_bonus: int) -> tuple[int, str]:
        """Resolve a signed flat damage modifier back into magnitude plus operator."""
        if operator == WeaponStats.DamageOperator.DIVIDE:
            return base_bonus, operator

        signed_bonus = int(base_bonus or 0)
        if operator == WeaponStats.DamageOperator.SUBTRACT:
            signed_bonus *= -1
        signed_bonus += int(quality_bonus or 0)

        if signed_bonus < 0:
            return abs(signed_bonus), WeaponStats.DamageOperator.SUBTRACT
        if signed_bonus > 0:
            return signed_bonus, WeaponStats.DamageOperator.ADD
        return 0, operator

    def get_weapon_damage(self, wield_mode: str = ONE_HANDED, *, dice_amount_bonus: int = 0):
        """Return weapon damage tuple(s): (dice_amount, dice_faces, flat_bonus, operator)."""
        stats = self._get_weapon_stats()
        if not stats:
            return None

        quality_bonus = self.get_weapon_damage_quality_bonus()
        base_bonus = int(self._get_override_value("weapon_damage_flat_bonus_override", stats.damage_flat_bonus or 0))
        h2_bonus = int(self._get_override_value("weapon_h2_flat_bonus_override", stats.h2_flat_bonus or 0))
        base_adjusted_bonus, base_adjusted_operator = self._apply_quality_to_damage_bonus(
            base_bonus,
            str(self._get_override_value("weapon_damage_flat_operator_override", stats.damage_flat_operator)),
            quality_bonus,
        )
        h2_adjusted_bonus, h2_adjusted_operator = self._apply_quality_to_damage_bonus(
            h2_bonus,
            str(self._get_override_value("weapon_h2_flat_operator_override", stats.h2_flat_operator)),
            quality_bonus,
        )
        base = (
            max(1, int(self._get_override_value("weapon_damage_dice_amount_override", stats.damage_dice_amount)) + int(dice_amount_bonus or 0)),
            int(self._get_override_value("weapon_damage_dice_faces_override", stats.damage_dice_faces)),
            base_adjusted_bonus,
            base_adjusted_operator,
        )
        two_handed = (
            (
                max(1, int(self._get_override_value("weapon_h2_dice_amount_override", stats.h2_dice_amount)) + int(dice_amount_bonus or 0))
                if self._get_override_value("weapon_h2_dice_amount_override", stats.h2_dice_amount) is not None
                else None
            ),
            self._get_override_value("weapon_h2_dice_faces_override", stats.h2_dice_faces),
            h2_adjusted_bonus,
            h2_adjusted_operator,
        )

        if wield_mode == ONE_HANDED:
            return base
        if wield_mode == TWO_HANDED:
            if stats.h2_dice_amount is None or stats.h2_dice_faces is None:
                return None
            return two_handed
        if wield_mode == VERSATILE:
            if stats.h2_dice_amount is None or stats.h2_dice_faces is None:
                return base
            return base, two_handed
        raise ValueError("Invalid wield_mode")

    @staticmethod
    def format_damage(damage_data) -> str:
        """Format one damage tuple into dice notation for UI display."""
        if not damage_data:
            return "-"
        dice_amount, dice_faces, flat_bonus, operator = damage_data
        return WeaponStats.format_damage_label(dice_amount, dice_faces, flat_bonus, operator)

    def get_one_handed_damage_label(self, *, dice_amount_bonus: int = 0) -> str:
        """Return one-handed or base damage label including quality modifier."""
        return self.format_damage(self.get_weapon_damage(ONE_HANDED, dice_amount_bonus=dice_amount_bonus))

    def get_two_handed_damage_label(self, *, dice_amount_bonus: int = 0) -> str | None:
        """Return two-handed damage label including quality modifier."""
        two_handed = self.get_weapon_damage(TWO_HANDED, dice_amount_bonus=dice_amount_bonus)
        if not two_handed:
            return None
        return self.format_damage(two_handed)

    def weapon_profiles(self, *, dice_amount_bonus: int = 0) -> list[dict[str, str]]:
        """Return prepared weapon display profiles for table rendering."""
        profiles = [
            {
                "mode": ONE_HANDED,
                "mode_label": "1 H",
                "damage": self.get_one_handed_damage_label(dice_amount_bonus=dice_amount_bonus),
            }
        ]
        two_handed_damage = self.get_two_handed_damage_label(dice_amount_bonus=dice_amount_bonus)
        if two_handed_damage:
            profiles.append(
                {
                    "mode": TWO_HANDED,
                    "mode_label": "2 H",
                    "damage": two_handed_damage,
                }
            )
        return profiles

    def get_armor_rs_raw(self) -> int | None:
        """Return total armor rating before character-wide modifiers."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        rs_total = self._get_override_value("armor_rs_total_override", stats.rs_total)
        if rs_total:
            return int(rs_total)
        zone_values = [
            int(self._get_override_value("armor_rs_head_override", stats.rs_head)),
            int(self._get_override_value("armor_rs_torso_override", stats.rs_torso)),
            int(self._get_override_value("armor_rs_arm_left_override", stats.rs_arm_left)),
            int(self._get_override_value("armor_rs_arm_right_override", stats.rs_arm_right)),
            int(self._get_override_value("armor_rs_leg_left_override", stats.rs_leg_left)),
            int(self._get_override_value("armor_rs_leg_right_override", stats.rs_leg_right)),
        ]
        return sum(zone_values) // 6

    def get_armor_min_st(self) -> int | None:
        """Return minimum strength for this armor."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        return int(self._get_override_value("armor_min_st_override", stats.min_st))

    def get_armor_bel_raw(self) -> int | None:
        """Return armor encumbrance without quality adjustments."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        return int(self._get_override_value("armor_encumbrance_override", stats.encumbrance))

    def get_armor_encumbrance(self) -> int:
        """Return armor encumbrance with quality adjustments."""
        stats = self._get_armor_stats()
        if not stats:
            return 0
        encumbrance = int(self._get_override_value("armor_encumbrance_override", stats.encumbrance))
        return max(0, encumbrance + self._quality_bonus_delta(QUALITY_BEL_MODS))

    def get_shield_min_st(self) -> int | None:
        """Return minimum strength for this shield."""
        stats = self._get_shield_stats()
        if not stats:
            return None
        return int(self._get_override_value("shield_min_st_override", stats.min_st))

    def get_shield_bel_raw(self) -> int | None:
        """Return shield encumbrance without extra modifiers."""
        stats = self._get_shield_stats()
        if not stats:
            return None
        return int(self._get_override_value("shield_encumbrance_override", stats.encumbrance))

    def get_effective_shield_rs(self) -> int | None:
        """Return shield protection value."""
        stats = self._get_shield_stats()
        if not stats:
            return None
        return int(self._get_override_value("shield_rs_override", stats.rs))

    def get_shield_encumbrance(self) -> int:
        """Return shield encumbrance for display and totals."""
        stats = self._get_shield_stats()
        if not stats:
            return 0
        return max(0, int(self._get_override_value("shield_encumbrance_override", stats.encumbrance)))

    def get_weapon_damage_source_slug(self) -> str:
        """Return the effective weapon damage source slug."""
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        damage_source = self._get_override_value("weapon_damage_source_override", getattr(stats, "damage_source", None))
        return str(getattr(damage_source, "slug", "") or "")

    def get_weapon_damage_type(self) -> str:
        """Return the effective weapon damage type."""
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        return str(self._get_override_value("weapon_damage_type_override", stats.damage_type) or "")

    def get_weapon_flags(self) -> set[str]:
        stats = self._get_weapon_stats()
        if not stats:
            return set()
        return {flag.key for flag in stats.flags.all()}

    def get_weapon_effect_descriptions(self) -> list[str]:
        """Return German effect texts for the weapon's symbols."""
        stats = self._get_weapon_stats()
        if not stats:
            return []
        effects = []
        for flag in stats.flags.all():
            description = WEAPON_SYMBOL_DESCRIPTIONS.get(flag.key, "")
            if description:
                effects.append(description)
        return effects

    @classmethod
    def total_weight_for_character(
        cls,
        character,
        *,
        include_stored: bool = True,
        include_equipped: bool = True,
    ) -> Decimal:
        """Return the summed weight of the character's owned items."""
        total_weight = Decimal("0")
        character_items = CharacterItem.objects.filter(owner=character).select_related("item")
        for character_item in character_items:
            if not include_stored and character_item.stored:
                continue
            if not include_equipped and character_item.equipped:
                continue
            total_weight += cls(character_item).get_weight()
        return total_weight

    @classmethod
    def active_inventory_weight_for_character(cls, character) -> Decimal:
        """Return the weight of all non-stored items, including equipped ones."""
        return cls.total_weight_for_character(
            character,
            include_stored=False,
            include_equipped=True,
        )

    @classmethod
    def carry_penalty_for_character(cls, character) -> int:
        """Return the signed carrying penalty derived from active inventory weight."""
        strength = int(character.get_engine().attributes().get(ATTR_ST, 0) or 0)
        carried_weight = cls.active_inventory_weight_for_character(character)
        if strength <= 0:
            return -8 if carried_weight > 0 else 0

        threshold_light = Decimal(strength * 2)
        threshold_medium = Decimal(strength * 3)
        threshold_heavy = Decimal(strength * 6)
        threshold_overloaded = Decimal(strength * 8)

        if carried_weight >= threshold_overloaded:
            return -8
        if carried_weight >= threshold_heavy:
            return -4
        if carried_weight >= threshold_medium:
            return -2
        if carried_weight >= threshold_light:
            return -1
        return 0

    @classmethod
    def carry_state_for_character(cls, character) -> dict[str, object]:
        """Return carrying state data for all non-stored inventory weight."""
        strength = int(character.get_engine().attributes().get(ATTR_ST, 0) or 0)
        carried_weight = cls.active_inventory_weight_for_character(character)
        penalty = cls.carry_penalty_for_character(character)
        threshold_light = Decimal(strength * 2)
        threshold_medium = Decimal(strength * 3)
        threshold_heavy = Decimal(strength * 6)
        threshold_overloaded = Decimal(strength * 8)

        if penalty <= -8:
            state_label = "Überladen"
        elif penalty <= -4:
            state_label = "Schwer bepackt"
        elif penalty <= -2:
            state_label = "Bepackt"
        elif penalty <= -1:
            state_label = "Leicht belastet"
        else:
            state_label = "Unbelastet"

        return {
            "strength": strength,
            "weight": carried_weight,
            "penalty": penalty,
            "state_label": state_label,
            "threshold_light": threshold_light,
            "threshold_medium": threshold_medium,
            "threshold_heavy": threshold_heavy,
            "threshold_overloaded": threshold_overloaded,
        }
