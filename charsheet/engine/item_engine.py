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
        if isinstance(self.obj, CharacterItem):
            return item.weight * self.obj.amount
        return item.weight

    def get_base_price(self) -> int:
        """Return the item's unmodified base price."""
        return self._get_item().price

    def get_price(self) -> int:
        """Return the price for the effective quality."""
        return self.price_for_item_and_quality(self._get_item(), self.get_effective_quality())

    def get_price_for_quality(self, quality: str) -> int:
        """Return price for an arbitrary quality without mutating object state."""
        return self.price_for_item_and_quality(self._get_item(), quality)

    def get_size_class(self) -> str:
        """Return the stored item size class."""
        return self._get_item().size_class

    def get_weapon_min_st(self) -> int | None:
        """Return the minimum strength needed for this weapon."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.min_st

    def get_weapon_wield_mode(self) -> str | None:
        """Return the configured wield mode code."""
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.wield_mode

    def get_weapon_damage_quality_bonus(self) -> int:
        """Return the flat quality bonus applied to weapon damage."""
        return WEAPON_DAMAGE_QUALITY_BONUSES.get(self.get_effective_quality(), 0)

    def get_weapon_maneuver_quality_bonus(self) -> int:
        """Return the quality bonus or penalty applied to maneuver values."""
        return WEAPON_MANEUVER_QUALITY_BONUSES.get(self.get_effective_quality(), 0)

    def get_weapon_damage(self, wield_mode: str = ONE_HANDED):
        """Return weapon damage tuple(s): (dice_amount, dice_faces, flat_bonus, operator)."""
        stats = self._get_weapon_stats()
        if not stats:
            return None

        quality_bonus = self.get_weapon_damage_quality_bonus()
        base_bonus = stats.damage_flat_bonus or 0
        h2_bonus = stats.h2_flat_bonus or 0
        base = (
            stats.damage_dice_amount,
            stats.damage_dice_faces,
            base_bonus + quality_bonus if stats.damage_flat_operator != stats.DamageOperator.DIVIDE else base_bonus,
            stats.damage_flat_operator,
        )
        two_handed = (
            stats.h2_dice_amount,
            stats.h2_dice_faces,
            h2_bonus + quality_bonus if stats.h2_flat_operator != stats.DamageOperator.DIVIDE else h2_bonus,
            stats.h2_flat_operator,
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
        if stats.rs_total:
            return stats.rs_total
        return stats.rs_sum() // 6

    def get_armor_min_st(self) -> int | None:
        """Return minimum strength for this armor."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        return stats.min_st

    def get_armor_bel_raw(self) -> int | None:
        """Return armor encumbrance without quality adjustments."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        return stats.encumbrance

    def get_armor_encumbrance(self) -> int:
        """Return armor encumbrance with quality adjustments."""
        stats = self._get_armor_stats()
        if not stats:
            return 0
        return stats.encumbrance + QUALITY_BEL_MODS.get(self.get_effective_quality(), 0)

    def get_shield_min_st(self) -> int | None:
        """Return minimum strength for this shield."""
        stats = self._get_shield_stats()
        if not stats:
            return None
        return stats.min_st

    def get_shield_bel_raw(self) -> int | None:
        """Return shield encumbrance without extra modifiers."""
        stats = self._get_shield_stats()
        if not stats:
            return None
        return stats.encumbrance

    def get_effective_shield_rs(self) -> int | None:
        """Return shield protection value."""
        stats = self._get_shield_stats()
        if not stats:
            return None
        return stats.rs

    def get_shield_encumbrance(self) -> int:
        """Return shield encumbrance for display and totals."""
        stats = self._get_shield_stats()
        if not stats:
            return 0
        return stats.encumbrance

    def get_weapon_flags(self) -> set[str]:
        stats = self._get_weapon_stats()
        if not stats:
            return set()
        return {flag.key for flag in stats.flags.all()}
