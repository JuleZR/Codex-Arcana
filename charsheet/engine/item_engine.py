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


class ItemEngine:
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
        if isinstance(self.obj, Item):
            return self.obj
        if isinstance(self.obj, CharacterItem):
            return self.obj.item
        raise TypeError("ItemEngine expects Item or CharacterItem")

    def get_weight(self) -> Decimal:
        item = self._get_item()
        if isinstance(self.obj, CharacterItem):
            return item.weight * self.obj.amount
        return item.weight

    def get_effective_quality(self) -> str:
        if isinstance(self.obj, CharacterItem):
            return self.normalize_quality(self.obj.quality)
        return self.normalize_quality(self._get_item().default_quality)

    def get_quality_color(self) -> str:
        """Return the UI color for the effective quality."""
        return self.quality_color(self.get_effective_quality())

    def get_base_price(self) -> int:
        return self._get_item().price

    def get_price(self) -> int:
        return self.price_for_item_and_quality(self._get_item(), self.get_effective_quality())

    def get_price_for_quality(self, quality: str) -> int:
        """Return price for an arbitrary quality without mutating object state."""
        return self.price_for_item_and_quality(self._get_item(), quality)

    def get_size_class(self) -> str:
        return self._get_item().size_class

    def _get_weapon_stats(self) -> WeaponStats | None:
        item = self._get_item()
        return getattr(item, "weaponstats", None)

    def get_weapon_min_st(self) -> int | None:
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.min_st

    def get_weapon_wield_mode(self) -> str | None:
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.wield_mode

    def get_weapon_damage_quality_bonus(self) -> int:
        quality = self.get_effective_quality()
        if quality == QUALITY_POOR:
            return -1
        if quality == QUALITY_VERY_POOR:
            return -2
        if quality == QUALITY_WRETCHED:
            return -3
        if quality in {QUALITY_EXCELLENT, QUALITY_LEGENDARY}:
            return 1
        return 0

    def get_weapon_maneuver_quality_bonus(self) -> int:
        quality = self.get_effective_quality()
        if quality == QUALITY_POOR:
            return -1
        if quality == QUALITY_VERY_POOR:
            return -2
        if quality == QUALITY_WRETCHED:
            return -3
        if quality == QUALITY_LEGENDARY:
            return 1
        return 0

    def get_weapon_damage(self, wield_mode: str = ONE_HANDED):
        """Return weapon damage tuple(s): (dice_amount, dice_faces, flat_bonus)."""
        stats = self._get_weapon_stats()
        if not stats:
            return None

        base = (
            stats.damage_dice_amount,
            stats.damage_dice_faces,
            (stats.damage_flat_bonus or 0) + self.get_weapon_damage_quality_bonus(),
        )
        two_handed = (
            stats.h2_dice_amount,
            stats.h2_dice_faces,
            (stats.h2_flat_bonus or 0) + self.get_weapon_damage_quality_bonus(),
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
        dice_amount, dice_faces, flat_bonus = damage_data
        label = f"{dice_amount}w{dice_faces}"
        if flat_bonus:
            label += f"{flat_bonus:+d}"
        return label

    def get_one_handed_damage_label(self) -> str:
        """Return one-handed/base damage label including quality modifier."""
        return self.format_damage(self.get_weapon_damage(ONE_HANDED))

    def get_two_handed_damage_label(self) -> str | None:
        """Return two-handed damage label including quality modifier."""
        two_handed = self.get_weapon_damage(TWO_HANDED)
        if not two_handed:
            return None
        return self.format_damage(two_handed)

    def _get_armor_stats(self) -> ArmorStats | None:
        item = self._get_item()
        return getattr(item, "armorstats", None)

    def _get_shield_stats(self) -> ShieldStats | None:
        item = self._get_item()
        return getattr(item, "shieldstats", None)

    def get_armor_rs_raw(self) -> int | None:
        stats = self._get_armor_stats()
        if not stats:
            return None
        if stats.rs_total:
            return stats.rs_total
        return stats.rs_sum() // 6

    def get_armor_min_st(self) -> int | None:
        stats = self._get_armor_stats()
        if not stats:
            return None
        return stats.min_st

    def get_armor_bel_raw(self) -> int | None:
        stats = self._get_armor_stats()
        if not stats:
            return None
        return stats.encumbrance

    def get_shield_min_st(self) -> int | None:
        stats = self._get_shield_stats()
        if not stats:
            return None
        return stats.min_st

    def get_shield_bel_raw(self) -> int | None:
        stats = self._get_shield_stats()
        if not stats:
            return None
        return stats.encumbrance

    def get_effective_shield_rs(self) -> int | None:
        stats = self._get_shield_stats()
        if not stats:
            return None
        return stats.rs

    def get_shield_encumbrance(self) -> int:
        stats = self._get_shield_stats()
        if not stats:
            return 0
        return stats.encumbrance

    def get_armor_encumbrance(self) -> int:
        stats = self._get_armor_stats()
        if not stats:
            return 0
        bel = stats.encumbrance
        quality = self.get_effective_quality()
        return bel + QUALITY_BEL_MODS.get(quality, 0)
    
    def get_size_class(self) -> str:
        return self._get_item().size_class
