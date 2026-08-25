"""Helpers for item prices, quality effects, and equipment stat lookups."""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist

from charsheet.constants import (
    ATTR_GE,
    ATTR_ST,
    ONE_HANDED,
    TWO_HANDED,
    VERSATILE,
    WEAPON_MANEUVER_ATTRIBUTE_BOTH,
    WEAPON_MANEUVER_ATTRIBUTE_GE,
    WEAPON_MANEUVER_ATTRIBUTE_NONE,
    WEAPON_MANEUVER_ATTRIBUTE_ST,
    WEAPON_SYMBOL_DESCRIPTIONS,
)
from charsheet.models import ArmorStats, CharacterItem, Item, Quality, RangedWeaponStats, ShieldStats, WeaponStats


class ItemEngine:
    """Resolve derived item values for base items and owned inventory rows."""

    def __init__(
        self,
        obj: Item | CharacterItem,
        weapon_stats: WeaponStats | None = None,
    ):
        self.obj = obj
        self.weapon_stats = weapon_stats

    @staticmethod
    def normalize_quality(quality) -> str:
        """Return the persisted quality code, falling back to the DB default."""
        return Quality.resolve(
            quality,
            use_default=True,
        ).code

    @staticmethod
    def quality_color(quality) -> str:
        """Return the persisted UI color for one quality tier."""
        return Quality.resolve(
            quality,
            use_default=True,
        ).hex_color

    @classmethod
    def price_for_item_and_quality(
        cls,
        item: Item,
        quality,
    ) -> int:
        """Return the effective price for an item at one quality."""
        return cls(item).get_price_for_quality(quality)

    @staticmethod
    def _quality_price_multiplier(
        base_quality,
        effective_quality,
    ) -> Decimal:
        """Return the DB-defined price ratio between two qualities."""
        base_quality_obj = Quality.resolve(base_quality)
        effective_quality_obj = Quality.resolve(effective_quality)

        base_multiplier = Decimal(
            base_quality_obj.price_multiplier
        )
        effective_multiplier = Decimal(
            effective_quality_obj.price_multiplier
        )

        return effective_multiplier / base_multiplier

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

    def _get_metal(self):
        """Return the item's configured metal, if any."""
        return getattr(
            self._get_item(),
            "metal",
            None,
        )

    def _apply_metal_ms_modifier(
        self,
        minimum_strength: int | None,
    ) -> int | None:
        """Apply the configured metal modifier to minimum strength."""
        if minimum_strength is None:
            return None
        metal = self._get_metal()
        modifier = (
            int(metal.ms_modifier or 0)
            if metal is not None
            else 0
        )
        return max(
            1,
            int(minimum_strength) + modifier,
        )

    def _get_override_value(self, override_field: str, fallback):
        character_item = self._get_character_item()
        if character_item is None:
            return fallback
        override_value = getattr(character_item, override_field)
        if override_value in (None, ""):
            return fallback
        return override_value

    def _get_weapon_stats(self) -> WeaponStats | None:
        if self.weapon_stats is not None:
            return self.weapon_stats
        return (
            self._get_item()
            .weapon_stats
            .order_by("id")
            .first()
        )

    def get_weapon_stats_profiles(self) -> list[WeaponStats]:
        return list(
            self._get_item()
            .weapon_stats
            .order_by("id")
        )

    def _get_ranged_weapon_stats(self) -> RangedWeaponStats | None:
        try:
            return getattr(self._get_item(), "rangedweaponstats", None)
        except ObjectDoesNotExist:
            return None

    def _get_armor_stats(self) -> ArmorStats | None:
        try:
            return getattr(self._get_item(), "armorstats", None)
        except ObjectDoesNotExist:
            return None

    def _get_offensive_stats(self) -> WeaponStats | RangedWeaponStats | ShieldStats | None:
        ranged_stats = self._get_ranged_weapon_stats()
        if ranged_stats is not None:
            return ranged_stats
        weapon_stats = self._get_weapon_stats()
        if weapon_stats is not None:
            return weapon_stats
        shield_stats = self._get_shield_stats()
        if shield_stats is not None:
            return shield_stats
        return None

    def _get_shield_stats(self) -> ShieldStats | None:
        try:
            return getattr(self._get_item(), "shieldstats", None)
        except ObjectDoesNotExist:
            return None

    def get_base_quality_obj(self) -> Quality:
        """Return the quality already represented by the stored base item."""
        return self._get_item().default_quality

    def get_effective_quality_obj(self) -> Quality:
        """Return the quality governing the effective item."""
        metal = self._get_metal()

        if metal is not None and metal.quality_overwrite_id:
            return metal.quality_overwrite

        character_item = self._get_character_item()
        if character_item is not None:
            return character_item.quality

        return self._get_item().default_quality

    def get_base_quality(self) -> str:
        """Return the persisted base-quality code."""
        return self.get_base_quality_obj().code

    def get_effective_quality(self) -> str:
        """Return the persisted effective-quality code."""
        return self.get_effective_quality_obj().code

    def get_quality_color(self) -> str:
        """Return the UI color of the effective quality."""
        return self.get_effective_quality_obj().hex_color

    def get_weight(self) -> Decimal:
        """Return effective item weight including metal and stack amount."""
        item = self._get_item()
        weight = Decimal(
            self._get_override_value(
                "weight_override",
                item.weight,
            )
        )
        metal = self._get_metal()
        if metal is not None:
            weight *= Decimal(
                metal.weight_multiplier or 1
            )
        if isinstance(self.obj, CharacterItem):
            weight *= self.obj.amount
        return weight

    def get_base_price(self) -> int:
        """Return the item's unmodified base price."""
        return int(self._get_override_value("price_override", self._get_item().price))

    def get_price(self) -> int:
        """Return the effective item price."""
        return self.get_price_for_quality(
            self.get_effective_quality_obj()
        )

    def get_price_for_quality(self, quality) -> int:
        """Return the effective price for an arbitrary quality."""
        effective_quality = Quality.resolve(quality)
        metal = self._get_metal()
        price = Decimal(self.get_base_price())
        # A metal quality overwrite replaces the item's regular quality.
        # Its price multiplier already represents that material's price rule.
        if metal is None or not metal.quality_overwrite_id:
            price *= self._quality_price_multiplier(
                self.get_base_quality_obj(),
                effective_quality,
            )
        if metal is not None:
            price *= Decimal(
                metal.price_multiplier or 1
            )
        return int(
            price.quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

    def get_name(self) -> str:
        """Return the effective display name."""
        item = self._get_item()
        original_name = str(item.name)
        custom_name = str(self._get_override_value("name_override", original_name)).strip()
        if (
            isinstance(self.obj, CharacterItem)
            and item.item_type == Item.ItemType.CREATURE
            and custom_name
            and custom_name != original_name
        ):
            return f"{custom_name} ({original_name})"
        return custom_name or original_name

    def get_size_class(self) -> str:
        """Return the stored item size class."""
        return str(self._get_override_value("size_class_override", self._get_item().size_class))

    def get_weapon_min_st(
        self,
        wield_mode: str | None = None,
    ) -> int | None:
        """Return minimum strength including metal modifiers."""
        ranged_stats = self._get_ranged_weapon_stats()

        if ranged_stats is not None:
            return self._apply_metal_ms_modifier(
                ranged_stats.minimum_strength
            )

        stats = self._get_weapon_stats()

        if not stats:
            shield_stats = self._get_shield_stats()

            if (
                shield_stats is not None
                and shield_stats.has_damage_profile
            ):
                minimum_strength = self._get_override_value(
                    "shield_min_st_override",
                    shield_stats.min_st,
                )
                return self._apply_metal_ms_modifier(
                    minimum_strength
                )

            return None

        override = self._get_override_value(
            "weapon_min_st_override",
            None,
        )

        if (
            override is not None
            and int(override) != int(stats.min_st or 1)
        ):
            minimum_strength = int(override)
        else:
            minimum_strength = stats.effective_min_st(
                wield_mode
            )

        return self._apply_metal_ms_modifier(
            minimum_strength
        )

    def get_weapon_min_ge(self, wield_mode: str | None = None) -> int | None:
        """Return the optional minimum agility needed for this weapon profile."""
        if self._get_ranged_weapon_stats() is not None:
            return None
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

    def get_weapon_range_label(self, *, strength: int | None = None) -> str:
        """Return the compact short/medium/long weapon range label."""
        ranged_stats = self._get_ranged_weapon_stats()
        if ranged_stats is not None:
            return ranged_stats.effective_range_label(strength)
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        return stats.effective_range_label(strength)

    def get_weapon_reload_time(self) -> int | None:
        """Return the weapon reload time if configured."""
        ranged_stats = self._get_ranged_weapon_stats()
        if ranged_stats is not None:
            return ranged_stats.reload_time
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.reload_time

    def get_weapon_shot_count(self) -> int | None:
        """Return the weapon shot count if configured."""
        ranged_stats = self._get_ranged_weapon_stats()
        if ranged_stats is not None:
            return ranged_stats.shots
        stats = self._get_weapon_stats()
        if not stats:
            return None
        return stats.shot_count

    def get_weapon_type(self) -> str:
        """Return the effective weapon type used for matching and UI."""
        stats = self._get_offensive_stats()
        if not stats:
            return ""
        weapon_type = self._get_override_value("weapon_type_override", getattr(stats, "weapon_type", None))
        return str(getattr(weapon_type, "slug", "") or "")

    def get_weapon_maneuver_attribute_mode(self) -> str:
        """Return the active attribute mode for this weapon's maneuvers."""

        # Bei einem konkret ausgewählten WeaponStats-Profil gilt dessen
        # Attributseinstellung und nicht der globale CharacterItem-Override.
        if self.weapon_stats is not None:
            return str(
                self.weapon_stats.maneuver_attribute_mode
                or WEAPON_MANEUVER_ATTRIBUTE_ST
            )

        stats = self._get_offensive_stats()
        if not stats:
            return WEAPON_MANEUVER_ATTRIBUTE_ST

        return str(
            self._get_override_value(
                "weapon_maneuver_attribute_override",
                getattr(
                    stats,
                    "maneuver_attribute_mode",
                    WEAPON_MANEUVER_ATTRIBUTE_ST,
                ),
            )
            or WEAPON_MANEUVER_ATTRIBUTE_ST
        )

    def get_weapon_maneuver_attribute_codes(self) -> tuple[str, ...]:
        """Return the attribute codes that add to this weapon's maneuvers."""
        mode = self.get_weapon_maneuver_attribute_mode()
        if mode == WEAPON_MANEUVER_ATTRIBUTE_NONE:
            return ()
        if mode == WEAPON_MANEUVER_ATTRIBUTE_GE:
            return (ATTR_GE,)
        if mode == WEAPON_MANEUVER_ATTRIBUTE_BOTH:
            return (ATTR_ST, ATTR_GE)
        return (ATTR_ST,)

    def get_weapon_maneuver_attribute_label(self) -> str:
        """Return the short label for the active maneuver attribute mode."""
        labels = {
            WEAPON_MANEUVER_ATTRIBUTE_NONE: "-",
            WEAPON_MANEUVER_ATTRIBUTE_ST: "ST",
            WEAPON_MANEUVER_ATTRIBUTE_GE: "GE",
            WEAPON_MANEUVER_ATTRIBUTE_BOTH: "ST oder GE",
        }
        return labels.get(self.get_weapon_maneuver_attribute_mode(), "ST")

    def get_weapon_wield_mode(self) -> str | None:
        """Return the configured wield mode code."""
        if self._get_ranged_weapon_stats() is not None:
            return ONE_HANDED
        stats = self._get_weapon_stats()
        if not stats:
            shield_stats = self._get_shield_stats()
            if shield_stats is not None and shield_stats.has_damage_profile:
                return ONE_HANDED
            return None
        return str(self._get_override_value("weapon_wield_mode_override", stats.wield_mode))

    def get_weapon_damage_quality_bonus(self) -> int:
        """Return the effective quality modifier to weapon damage."""
        return self._quality_modifier_delta(
            "weapon_damage_modifier"
        )

    def get_weapon_maneuver_quality_bonus(self) -> int:
        """Return the effective quality modifier to weapon maneuvers."""
        return self._quality_modifier_delta(
            "weapon_maneuver_modifier"
        )

    def _quality_modifier_delta(self, field_name: str) -> int:
        """Return the quality modifier not already represented by base stats."""
        metal = self._get_metal()

        if (
            metal is not None
            and metal.quality_overwrite_id
            and not metal.apply_quality_effects
        ):
            return 0
        effective_quality = self.get_effective_quality_obj()
        base_quality = self.get_base_quality_obj()
        effective_modifier = int(
            getattr(effective_quality, field_name, 0) or 0
        )
        base_modifier = int(
            getattr(base_quality, field_name, 0) or 0
        )
        return effective_modifier - base_modifier

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
        """Return weapon damage tuple(s): (dice_amount, dice_faces, flat_bonus, operator, damage_type)."""
        stats = self._get_offensive_stats()
        if not stats:
            return None

        if not isinstance(stats, WeaponStats) and not stats.has_damage_profile:
            if wield_mode in {ONE_HANDED, TWO_HANDED, VERSATILE}:
                return None
            raise ValueError("Invalid wield_mode")

        quality_bonus = self.get_weapon_damage_quality_bonus()
        base_bonus = int(self._get_override_value("weapon_damage_flat_bonus_override", stats.damage_flat_bonus or 0))
        base_adjusted_bonus, base_adjusted_operator = self._apply_quality_to_damage_bonus(
            base_bonus,
            str(self._get_override_value("weapon_damage_flat_operator_override", stats.damage_flat_operator)),
            quality_bonus,
        )
        base = (
            max(1, int(self._get_override_value(
                "weapon_damage_dice_amount_override",
                stats.damage_dice_amount)) + int(dice_amount_bonus or 0)),
            int(self._get_override_value("weapon_damage_dice_faces_override", stats.damage_dice_faces)),
            base_adjusted_bonus,
            base_adjusted_operator,
            self.get_weapon_damage_type(),
            getattr(stats, "damage_label", ""),
        )
        if not isinstance(stats, WeaponStats):
            if wield_mode == ONE_HANDED:
                return base
            if wield_mode in {TWO_HANDED, VERSATILE}:
                return None
            raise ValueError("Invalid wield_mode")

        h2_bonus = int(self._get_override_value("weapon_h2_flat_bonus_override", stats.h2_flat_bonus or 0))
        h2_adjusted_bonus, h2_adjusted_operator = self._apply_quality_to_damage_bonus(
            h2_bonus,
            str(self._get_override_value("weapon_h2_flat_operator_override", stats.h2_flat_operator)),
            quality_bonus,
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
            self.get_weapon_h2_damage_type(),
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
        dice_amount, dice_faces, flat_bonus, operator, *rest = damage_data
        damage_type = str(rest[0] if rest else "")
        damage_label = str(rest[1] if len(rest) > 1 else "").strip()
        if int(dice_faces or 0) == 0:
            lower = int(dice_amount or 0)
            upper = int(flat_bonus or 0)
            if not lower and not upper:
                return "-"
            if lower and upper:
                label = f"{lower}-{upper}"
            elif lower:
                label = str(lower)
            elif upper:
                label = str(upper)
        else:
            label = WeaponStats.format_damage_label(dice_amount, dice_faces, flat_bonus, operator)
        if damage_label:
            label = f"{damage_label} {label}"
        return f"{label} {damage_type}".strip()

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
        wield_mode = self.get_weapon_wield_mode()
        profiles = []

        if wield_mode != TWO_HANDED:
            profiles.append(
                {
                    "mode": ONE_HANDED,
                    "mode_label": "1 H",
                    "damage": self.get_one_handed_damage_label(
                        dice_amount_bonus=dice_amount_bonus
                    ),
                }
            )

        if wield_mode in {TWO_HANDED, VERSATILE}:
            two_handed_damage = self.get_two_handed_damage_label(
                dice_amount_bonus=dice_amount_bonus
            )
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
        """Return this physical armor item's quality-adjusted local RS."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        rs_value = int(self._get_override_value("armor_rs_total_override", stats.rs))
        return max(0, rs_value + self.get_armor_rs_quality_bonus())

    def get_armor_rs_quality_bonus(self) -> int:
        """Return the effective quality modifier to armor RS."""
        return self._quality_modifier_delta(
            "armor_rs_modifier"
        )

    def get_armor_zone_rs(self) -> dict[str, int] | None:
        """Return this physical armor item's RS for every covered hit zone."""
        stats = self._get_armor_stats()
        if not stats:
            return None

        rs_value = int(self._get_override_value("armor_rs_total_override", stats.rs))
        quality_bonus = self.get_armor_rs_quality_bonus()
        base_zone_overrides = dict(stats.zone_rs_overrides or {})
        character_item = self._get_character_item()
        instance_zone_overrides = dict(
            getattr(character_item, "armor_zone_rs_overrides", {}) or {}
        )
        covered_main_zone_count = sum(
            1
            for zone in stats.MAIN_ZONE_FIELDS
            if getattr(stats, f"covers_{zone}", False)
        )
        split_basis_rs = rs_value
        if 1 < covered_main_zone_count < len(stats.MAIN_ZONE_FIELDS):
            split_basis_rs = int(
                (
                    Decimal(rs_value)
                    * Decimal(len(stats.MAIN_ZONE_FIELDS))
                    / Decimal(covered_main_zone_count)
                ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        return {
            zone: max(
                0,
                int(
                    instance_zone_overrides.get(
                        zone,
                        base_zone_overrides.get(
                            zone,
                            split_basis_rs if zone in stats.MAIN_ZONE_FIELDS else rs_value,
                        ),
                    )
                )
                + quality_bonus,
            )
            for zone in stats.ZONE_FIELDS
            if getattr(stats, f"covers_{zone}", False)
        }

    def get_armor_grs_zone_rs(self) -> dict[str, int] | None:
        """Return the main-zone RS values used as this item's GRS calculation basis."""
        zone_values = self.get_armor_zone_rs()
        stats = self._get_armor_stats()
        if not zone_values or not stats:
            return zone_values

        main_zones = [
            zone
            for zone in stats.MAIN_ZONE_FIELDS
            if getattr(stats, f"covers_{zone}", False)
        ]
        if len(main_zones) <= 1:
            return zone_values

        target_sum = int(self._get_override_value("armor_rs_total_override", stats.rs)) * len(stats.MAIN_ZONE_FIELDS)
        current_sum = sum(int(zone_values.get(zone, 0) or 0) for zone in main_zones)
        if current_sum >= target_sum:
            return zone_values

        adjusted = dict(zone_values)
        adjusted[main_zones[-1]] = int(adjusted.get(main_zones[-1], 0) or 0) + (target_sum - current_sum)
        return adjusted

    def get_armor_min_st(self) -> int | None:
        """Return minimum strength including quality and metal modifiers."""
        stats = self._get_armor_stats()

        if not stats:
            return None

        minimum_strength = int(
            self._get_override_value(
                "armor_min_st_override",
                stats.min_st,
            )
        )

        minimum_strength += self._quality_modifier_delta(
            "armor_min_st_modifier"
        )

        return self._apply_metal_ms_modifier(
            minimum_strength
        )

    def get_armor_bel_raw(self) -> int | None:
        """Return armor encumbrance without quality adjustments."""
        stats = self._get_armor_stats()
        if not stats:
            return None
        return int(self._get_override_value("armor_encumbrance_override", stats.encumbrance))

    def get_armor_encumbrance(self) -> int:
        """Return armor encumbrance including quality modifiers."""
        stats = self._get_armor_stats()
        if not stats:
            return 0
        encumbrance = int(
            self._get_override_value(
                "armor_encumbrance_override",
                stats.encumbrance,
            )
        )
        encumbrance += self._quality_modifier_delta(
            "armor_encumbrance_modifier"
        )
        return max(0, encumbrance)

    def get_shield_min_st(self) -> int | None:
        """Return shield minimum strength including metal modifiers."""
        stats = self._get_shield_stats()
        if not stats:
            return None

        minimum_strength = self._get_override_value(
            "shield_min_st_override",
            stats.min_st,
        )

        return self._apply_metal_ms_modifier(
            minimum_strength
        )

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
        stats = self._get_offensive_stats()
        if not stats:
            return ""
        if isinstance(stats, RangedWeaponStats):
            return ""
        damage_source = self._get_override_value("weapon_damage_source_override", getattr(stats, "damage_source", None))
        return str(getattr(damage_source, "slug", "") or "")

    def get_weapon_damage_type(self) -> str:
        """Return the effective weapon damage type."""
        stats = self._get_offensive_stats()
        if not stats:
            return ""
        return str(self._get_override_value("weapon_damage_type_override", stats.damage_type) or "")

    def get_weapon_h2_damage_type(self) -> str:
        """Return the effective two-handed weapon damage type."""
        stats = self._get_weapon_stats()
        if not stats:
            return ""
        return str(self._get_override_value("weapon_h2_damage_type_override", stats.h2_damage_type) or "")

    def get_weapon_flags(self) -> set[str]:
        stats = self._get_offensive_stats()
        if not stats or not hasattr(stats, "flags"):
            return set()
        return {flag.key for flag in stats.flags.all()}

    def get_weapon_effect_descriptions(self) -> list[str]:
        """Return German effect texts for the weapon's symbols."""
        stats = self._get_offensive_stats()
        if not stats or not hasattr(stats, "flags"):
            return []
        effects = []
        for flag in stats.flags.all():
            description = WEAPON_SYMBOL_DESCRIPTIONS.get(flag.key, "")
            if description:
                effects.append(f"{flag.get_key_display()} {description}")
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
        character_items = CharacterItem.objects.filter(owner=character).exclude(
            transfers__status="pending"
        ).select_related("item").distinct()
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
        threshold_light = Decimal(strength * 2)
        threshold_medium = Decimal(strength * 3)
        threshold_heavy = Decimal(strength * 6)
        threshold_overloaded = Decimal(strength * 8)

        if strength <= 0:
            penalty = -8 if carried_weight > 0 else 0
        elif carried_weight >= threshold_overloaded:
            penalty = -8
        elif carried_weight >= threshold_heavy:
            penalty = -4
        elif carried_weight >= threshold_medium:
            penalty = -2
        elif carried_weight >= threshold_light:
            penalty = -1
        else:
            penalty = 0

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
