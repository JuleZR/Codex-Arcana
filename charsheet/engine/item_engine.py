"""Helpers for item prices, quality effects, and equipment stat lookups."""

from decimal import Decimal

from charsheet.constants import (
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
        """Return one quality-adjusted item price."""
        resolved_quality = cls.normalize_quality(quality)
        return int(item.price * QUALITY_PRICE_MODS.get(resolved_quality, 1))

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
        return int(self.get_base_price() * QUALITY_PRICE_MODS.get(resolved_quality, 1))

    def get_name(self) -> str:
        """Return the effective display name."""
        return str(self._get_override_value("name_override", self._get_item().name))

    def get_size_class(self) -> str:
        """Return the stored item size class."""
        return str(self._get_override_value("size_class_override", self._get_item().size_class))

    def get_weapon_min_st(self) -> int | None:
        """Return the minimum strength needed for this weapon."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return int(self._get_override_value("weapon_min_st_override", stats.min_st))

    def get_weapon_type(self) -> str:
        """Return the effective weapon type used for matching and UI."""
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        weapon_type = self._get_override_value("weapon_type_override", stats.weapon_type)
        return str(getattr(weapon_type, "slug", "") or "")

    def get_weapon_wield_mode(self) -> str | None:
        """Return the configured wield mode code."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return str(self._get_override_value("weapon_wield_mode_override", stats.wield_mode))

    def get_weapon_damage_quality_bonus(self) -> int:
        """Return the flat quality bonus applied to weapon damage."""
        return WEAPON_DAMAGE_QUALITY_BONUSES.get(self.get_effective_quality(), 0)

    def get_weapon_maneuver_quality_bonus(self) -> int:
        """Return the quality bonus or penalty applied to maneuver values."""
        return WEAPON_MANEUVER_QUALITY_BONUSES.get(self.get_effective_quality(), 0)

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

    def get_weapon_damage(self, wield_mode: str = ONE_HANDED):
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
            int(self._get_override_value("weapon_damage_dice_amount_override", stats.damage_dice_amount)),
            int(self._get_override_value("weapon_damage_dice_faces_override", stats.damage_dice_faces)),
            base_adjusted_bonus,
            base_adjusted_operator,
        )
        two_handed = (
            self._get_override_value("weapon_h2_dice_amount_override", stats.h2_dice_amount),
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

    def get_one_handed_damage_label(self) -> str:
        """Return one-handed or base damage label including quality modifier."""
        return self.format_damage(self.get_weapon_damage(ONE_HANDED))

    def get_two_handed_damage_label(self) -> str | None:
        """Return two-handed damage label including quality modifier."""
        two_handed = self.get_weapon_damage(TWO_HANDED)
        if not two_handed:
            return None
        return self.format_damage(two_handed)

    def weapon_profiles(self) -> list[dict[str, str]]:
        """Return prepared weapon display profiles for table rendering."""
        profiles = [
            {
                "mode": ONE_HANDED,
                "mode_label": "1 H",
                "damage": self.get_one_handed_damage_label(),
            }
        ]
        two_handed_damage = self.get_two_handed_damage_label()
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
        return max(0, encumbrance + QUALITY_BEL_MODS.get(self.get_effective_quality(), 0))

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
