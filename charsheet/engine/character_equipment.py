"""Equipment- and inventory-related CharacterEngine methods."""

from __future__ import annotations

from django.db.models import QuerySet

from charsheet.constants import ARMOR_PENALTY_IGNORE, ATTR_ST, DEFENSE_RS
from charsheet.models import CharacterItem, Item

from .item_engine import ItemEngine


def equipped_weapon_items(engine) -> QuerySet:
    """Return all currently equipped weapons with required relations loaded."""
    return (
        CharacterItem.objects.filter(
            owner=engine.character,
            equipped=True,
            item__item_type=Item.ItemType.WEAPON,
        )
        .select_related("item", "item__weaponstats", "item__weaponstats__damage_source")
        .prefetch_related("item__runes", "runes")
    )


def equipped_armor_items(engine) -> QuerySet:
    """Return all currently equipped armor items of the character."""
    return (
        CharacterItem.objects.filter(
            owner=engine.character,
            equipped=True,
            item__item_type=Item.ItemType.ARMOR,
        )
        .select_related("item", "item__armorstats")
        .prefetch_related("item__runes", "runes")
    )


def equipped_shield_items(engine) -> QuerySet:
    """Return all currently equipped shields of the character."""
    return (
        CharacterItem.objects.filter(
            owner=engine.character,
            equipped=True,
            item__item_type=Item.ItemType.SHIELD,
        )
        .select_related("item", "item__shieldstats")
        .prefetch_related("item__runes", "runes")
    )


def weapon_quality_skill_modifier(engine) -> int:
    """Return the maneuver quality modifier of the first equipped weapon."""
    weapon = engine.equipped_weapon_items().first()
    quality_bonus = ItemEngine(weapon).get_weapon_maneuver_quality_bonus() if weapon else 0
    return quality_bonus + engine.resolve_combat_value("melee_maneuvers")


def equipped_weapon_rows(engine) -> list[dict]:
    """Return character-sheet-ready weapon rows with one prepared row per display profile."""
    rows: list[dict] = []
    bel_malus = engine.load_penalty()
    maneuver_modifier = engine.resolve_combat_value("melee_maneuvers")
    for character_item in engine.equipped_weapon_items():
        item_engine = ItemEngine(character_item)
        weapon_stats = getattr(character_item.item, "weaponstats", None)
        damage_source_slug = getattr(getattr(weapon_stats, "damage_source", None), "slug", "")
        damage_stat_slug = damage_source_slug or getattr(weapon_stats, "damage_type", "")
        dmg_mod = engine.get_dmg_modifier_sum(damage_stat_slug) if damage_stat_slug else engine.attribute_modifier(ATTR_ST)
        for profile_index, profile in enumerate(item_engine.weapon_profiles()):
            rows.append(
                {
                    "character_item": character_item,
                    "item": character_item.item,
                    "quality": item_engine.get_effective_quality(),
                    "quality_color": item_engine.get_quality_color(),
                    "dmg_mod": dmg_mod,
                    "dmg_mod_display": f"{dmg_mod:+d}" if dmg_mod else "0",
                    "bel_malus": bel_malus,
                    "bel_malus_display": f"{bel_malus:+d}" if bel_malus else "0",
                    "with_bel": dmg_mod + bel_malus,
                    "with_bel_display": f"{(dmg_mod + bel_malus):+d}" if (dmg_mod + bel_malus) else "0",
                    "wield_mode": item_engine.get_weapon_wield_mode(),
                    "size_class": item_engine.get_size_class(),
                    "min_st": item_engine.get_weapon_min_st(),
                    "damage": profile["damage"],
                    "mode_label": profile["mode_label"],
                    "is_primary_profile": profile_index == 0,
                    "quality_damage_bonus": item_engine.get_weapon_damage_quality_bonus(),
                    "quality_maneuver_bonus": item_engine.get_weapon_maneuver_quality_bonus(),
                    "trait_maneuver_modifier": maneuver_modifier,
                    "total_maneuver_modifier": item_engine.get_weapon_maneuver_quality_bonus() + maneuver_modifier,
                }
            )
    return rows


def equipped_armor_rows(engine) -> list[dict]:
    """Return equipped armor rows resolved through ItemEngine."""
    rows: list[dict] = []
    for character_item in engine.equipped_armor_items():
        item_engine = ItemEngine(character_item)
        rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "quality": item_engine.get_effective_quality(),
                "quality_color": item_engine.get_quality_color(),
                "rs": item_engine.get_armor_rs_raw() or 0,
                "bel_raw": item_engine.get_armor_bel_raw() or 0,
                "bel_effective": item_engine.get_armor_encumbrance(),
                "min_st": item_engine.get_armor_min_st(),
            }
        )
    return rows


def equipped_shield_rows(engine) -> list[dict]:
    """Return equipped shield rows resolved through ItemEngine."""
    rows: list[dict] = []
    for character_item in engine.equipped_shield_items():
        item_engine = ItemEngine(character_item)
        rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "quality": item_engine.get_effective_quality(),
                "quality_color": item_engine.get_quality_color(),
                "rs": item_engine.get_effective_shield_rs() or 0,
                "bel_raw": item_engine.get_shield_bel_raw() or 0,
                "bel_effective": item_engine.get_shield_encumbrance(),
                "min_st": item_engine.get_shield_min_st(),
            }
        )
    return rows


def get_grs(engine) -> int:
    """Calculate the total armor rating from equipped armor."""
    total = 0
    for armor in engine.equipped_armor_items():
        total += ItemEngine(armor).get_armor_rs_raw() or 0
    return total + engine._resolve_stat_modifiers(DEFENSE_RS)


def get_bel(engine) -> int:
    """Calculate the armor encumbrance value."""
    if engine.resolve_flags().get(ARMOR_PENALTY_IGNORE, False):
        return 0
    armor_bel = 0
    for armor in engine.equipped_armor_items():
        armor_bel += ItemEngine(armor).get_armor_encumbrance() or 0

    shield_bel = 0
    for shield in engine.equipped_shield_items():
        shield_bel += ItemEngine(shield).get_shield_encumbrance() or 0

    return armor_bel + shield_bel


def load_penalty(engine) -> int:
    """Return encumbrance as a signed penalty that can be added to derived values."""
    bel_value = int(engine.get_bel())
    return bel_value if bel_value <= 0 else -bel_value


def get_ms(engine) -> int:
    """Calculate the movement penalty derived from armor."""
    return engine.get_grs() // 2


def get_dmg_modifier_sum(engine, slug: str) -> int:
    """Return the total damage modifier for one damage-related stat slug."""
    return engine._resolve_stat_modifiers(slug) + engine.attribute_modifier(ATTR_ST)


def km_to_coins(engine) -> tuple[int, int, int]:
    """Split stored copper-equivalent money into coin denominations."""
    player_km = engine.character.money
    gm = player_km // 100
    sm = (player_km % 100) // 10
    km = player_km % 10
    return gm, sm, km
