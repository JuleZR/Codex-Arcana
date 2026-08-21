"""Equipment- and inventory-related CharacterEngine methods."""

from __future__ import annotations

from django.db.models import Q

from charsheet.constants import (
    ARMOR_PENALTY_IGNORE,
    ARMOR_ENCUMBRANCE,
    ATTR_ST,
    DEFENSE_RS,
    MELEE_MANEUVERS,
    SHIELD_ENCUMBRANCE,
    SOURCE_ITEM_RUNE,
    WEAPON_DAMAGE,
    WEAPON_DAMAGE_DICE,
    WEAPON_MANEUVER_ATTRIBUTE_NONE,
    WEAPON_MANEUVER_DAMAGE,
)
from charsheet.modifiers.definitions import ModifierOperator, StackBehavior, TargetDomain
from charsheet.modifiers.targets import TargetResolver
from charsheet.models import CharacterItem, Item

from .item_engine import ItemEngine


LOCAL_WEAPON_DAMAGE_SOURCE_TYPES = {"item", "characteritem", SOURCE_ITEM_RUNE}
def _cached_equipment_list(engine, cache_key, queryset_factory):
    """Evaluate one equipment queryset once per CharacterEngine instance."""
    cache = engine.__dict__.setdefault("_equipment_cache", {})
    if cache_key not in cache:
        cache[cache_key] = list(queryset_factory())
    return cache[cache_key]


def _cached_equipment_value(engine, cache_key, factory):
    """Cache derived equipment calculations for the current CharacterEngine."""
    cache = engine.__dict__.setdefault("_equipment_cache", {})
    if cache_key not in cache:
        cache[cache_key] = factory()
    return cache[cache_key]


def equipped_weapon_items(engine) -> list[CharacterItem]:
    """Return all currently equipped weapons with required relations loaded."""
    return _cached_equipment_list(
        engine,
        "weapon_items",
        lambda: (
            CharacterItem.objects.filter(
                owner=engine.character,
                equipped=True,
            )
            .filter(
                Q(item__item_type__in=Item.weapon_item_type_values())
                | Q(item__item_type=Item.ItemType.SHIELD, item__shieldstats__isnull=False)
            )
            .select_related("item", "item__weaponstats", "item__weaponstats__damage_source")
            .select_related("item__weaponstats__weapon_type")
            .select_related("item__rangedweaponstats")
            .select_related("item__rangedweaponstats__weapon_type")
            .select_related("item__shieldstats", "item__shieldstats__damage_source")
            .select_related("item__shieldstats__weapon_type")
            .prefetch_related(
                "item__runes",
                "runes",
                "item_runes__rune",
                "item__weaponstats__skills",
                "item__weaponstats__flags",
                "item__rangedweaponstats__skills",
                "item__rangedweaponstats__flags",
                "item__shieldstats__skills",
            )
        )
    )


def equipped_armor_items(engine) -> list[CharacterItem]:
    """Return all currently equipped armor items of the character."""
    return _cached_equipment_list(
        engine,
        "armor_items",
        lambda: (
            CharacterItem.objects.filter(
                owner=engine.character,
                equipped=True,
            )
            .filter(Q(item__item_type__in=Item.armor_item_type_values()) | Q(item__armorstats__isnull=False))
            .select_related("item", "item__armorstats")
            .prefetch_related("item__runes", "runes", "item_runes__rune")
        )
    )


def equipped_clothing_items(engine) -> list[CharacterItem]:
    """Return all currently equipped clothing items of the character."""
    return _cached_equipment_list(
        engine,
        "clothing_items",
        lambda: (
            CharacterItem.objects.filter(
                owner=engine.character,
                equipped=True,
                item__item_type=Item.ItemType.CLOTHING,
            )
            .select_related("item")
            .prefetch_related("item__runes", "runes", "item_runes__rune")
        )
    )


def equipped_magic_item_items(engine) -> list[CharacterItem]:
    """Return all currently equipped magic items of the character."""
    return _cached_equipment_list(
        engine,
        "magic_items",
        lambda: (
            CharacterItem.objects.filter(
                owner=engine.character,
                equipped=True,
            )
            .filter(
                Q(item__is_magic=True)
                | Q(item__item_type__in=Item.magic_item_type_values())
                | Q(is_magic=True)
                | Q(item__magicitemstats__isnull=False)
            )
            .exclude(
                item__item_type__in=(
                    Item.ItemType.SHIELD,
                    Item.ItemType.CLOTHING,
                    *Item.armor_item_type_values(),
                    *Item.weapon_item_type_values(),
                )
            )
            .exclude(item__armorstats__isnull=False)
            .select_related("item", "item__magicitemstats")
            .prefetch_related("item__runes", "runes", "item_runes__rune")
        )
    )


def equipped_shield_items(engine) -> list[CharacterItem]:
    """Return all currently equipped shields of the character."""
    return _cached_equipment_list(
        engine,
        "shield_items",
        lambda: (
            CharacterItem.objects.filter(
                owner=engine.character,
                equipped=True,
                item__item_type=Item.ItemType.SHIELD,
            )
            .select_related("item", "item__shieldstats", "item__shieldstats__weapon_type")
            .prefetch_related("item__runes", "runes", "item_runes__rune")
        )
    )


def weapon_quality_skill_modifier(engine) -> int:
    """Return the maneuver quality modifier of the first equipped weapon."""
    weapon = next(iter(engine.equipped_weapon_items()), None)
    quality_bonus = ItemEngine(weapon).get_weapon_maneuver_quality_bonus() if weapon else 0
    return quality_bonus + engine.resolve_combat_value("melee_maneuvers")


def _character_item_specific_maneuver_modifier(engine, character_item: CharacterItem) -> int:
    """Return item-bound maneuver modifiers that should only affect this equipped weapon."""
    return _character_item_specific_semantic_modifier(engine, character_item, MELEE_MANEUVERS)


def _character_item_specific_damage_modifier(engine, character_item: CharacterItem) -> int:
    """Return item-bound damage modifiers that should only affect this equipped weapon."""
    return (
        _character_item_specific_semantic_modifier(engine, character_item, WEAPON_DAMAGE)
        + _character_item_specific_rune_modifier(engine, character_item, WEAPON_DAMAGE)
    )


def _character_item_specific_damage_dice_modifier(engine, character_item: CharacterItem) -> int:
    """Return item-bound modifiers that increase this weapon's damage dice count."""
    return (
        _character_item_specific_semantic_modifier(engine, character_item, WEAPON_DAMAGE_DICE)
        + _character_item_specific_rune_modifier(engine, character_item, WEAPON_DAMAGE_DICE)
    )


def _character_item_target_context(engine, character_item: CharacterItem) -> dict[str, tuple[str, ...]]:
    """Return target context for effects bound to this concrete equipped item."""
    cache_key = ("target_context", int(character_item.id))

    def build_context() -> dict[str, tuple[str, ...]]:
        item = character_item.item
        weapon_ids = (str(item.id), str(character_item.id))
        weapon_skill_slugs: set[str] = set()
        weapon_type_slugs: set[str] = set()
        for stats_name in ("weaponstats", "rangedweaponstats", "shieldstats"):
            stats = getattr(item, stats_name, None)
            if not stats:
                continue
            weapon_type = getattr(stats, "weapon_type", None)
            if weapon_type and getattr(weapon_type, "slug", ""):
                weapon_type_slugs.add(str(weapon_type.slug))
            skill_manager = getattr(stats, "skills", None)
            if skill_manager is not None:
                weapon_skill_slugs.update(str(skill.slug) for skill in skill_manager.all())
        return {
            "character_item_id": str(character_item.id),
            "weapon_ids": weapon_ids,
            "weapon_types": tuple(sorted(weapon_type_slugs)),
            "weapon_skill_slugs": tuple(sorted(weapon_skill_slugs)),
        }

    return _cached_equipment_value(engine, cache_key, build_context)

def _character_item_specific_semantic_modifier(engine, character_item: CharacterItem, target_key: str) -> int:
    """Return concrete CharacterItem semantic effects for one item-bound combat target."""
    cache_key = ("semantic_modifier", int(character_item.id), str(target_key))

    def resolve_modifier() -> int:
        total = 0
        target_context = _character_item_target_context(engine, character_item)
        for modifier in engine.modifier_engine._active_item_semantic_modifiers:
            source_type = str(modifier.source_type or "")
            source_id = str(modifier.source_id or "")
            if source_type == "characteritem":
                if source_id != str(character_item.id):
                    continue
            elif source_type == "item":
                if source_id != str(character_item.item_id):
                    continue
                modifier_character_item_id = (modifier.metadata or {}).get("character_item_id")
                if modifier_character_item_id is not None and str(modifier_character_item_id) != str(character_item.id):
                    continue
            else:
                continue
            if not engine.modifier_engine._modifier_matches_race_condition(modifier):
                continue
            if modifier.target_domain != TargetDomain.COMBAT:
                continue
            modifier_target_key = str(modifier.target_key or "")
            if modifier_target_key != target_key and not (
                modifier_target_key == WEAPON_MANEUVER_DAMAGE
                and target_key in {MELEE_MANEUVERS, WEAPON_DAMAGE}
            ):
                continue
            if not TargetResolver.matches_context(modifier, target_context):
                continue
            total += int(engine.modifier_engine._resolve_numeric_modifier(modifier) or 0)
        return total

    return _cached_equipment_value(engine, cache_key, resolve_modifier)

def _character_item_specific_armor_semantic_modifiers(engine, character_item: CharacterItem, target_key: str) -> list:
    """Return item-bound semantic effects that affect this equipped armor or shield item."""
    cache_key = ("armor_semantic_modifiers", int(character_item.id), str(target_key))

    def collect_modifiers() -> list:
        modifiers = []
        for modifier in engine.modifier_engine._active_item_semantic_modifiers:
            source_type = str(modifier.source_type or "")
            source_id = str(modifier.source_id or "")
            if source_type == "characteritem":
                if source_id != str(character_item.id):
                    continue
            elif source_type == "item":
                if source_id != str(character_item.item_id):
                    continue
                modifier_character_item_id = (modifier.metadata or {}).get("character_item_id")
                if modifier_character_item_id is not None and str(modifier_character_item_id) != str(character_item.id):
                    continue
            else:
                continue
            if not engine.modifier_engine._modifier_matches_race_condition(modifier):
                continue
            if modifier.target_domain != TargetDomain.DERIVED_STAT:
                continue
            if str(modifier.target_key or "") != target_key:
                continue
            modifiers.append(modifier)
        return modifiers

    return _cached_equipment_value(engine, cache_key, collect_modifiers)

def _character_item_specific_rune_modifier(engine, character_item: CharacterItem, target_key: str) -> int:
    """Return rune modifiers that affect only the item they are socketed into."""
    cache_key = ("rune_modifier", int(character_item.id), str(target_key))
    return _cached_equipment_value(
        engine,
        cache_key,
        lambda: sum(
            int(engine.modifier_engine._resolve_numeric_modifier(modifier) or 0)
            for modifier in _character_item_specific_rune_modifiers(engine, character_item, target_key)
        ),
    )


def _character_item_specific_rune_modifiers(engine, character_item: CharacterItem, target_key: str) -> list:
    """Return rune modifier rows that affect only the item they are socketed into."""
    cache_key = ("rune_modifiers", int(character_item.id), str(target_key))

    def collect_modifiers() -> list:
        equipped_item_rune_ids = {
            int(item_rune.id)
            for item_rune in engine._equipped_item_runes
            if int(item_rune.item_id) == int(character_item.id)
        }
        if not equipped_item_rune_ids:
            return []

        modifiers = []
        target_context = _character_item_target_context(engine, character_item)
        for modifier in engine.modifier_engine._active_item_rune_modifiers:
            if modifier.source_type != SOURCE_ITEM_RUNE:
                continue
            if not engine.modifier_engine._modifier_matches_race_condition(modifier):
                continue
            modifier_target_key = str(modifier.target_key or "")
            if modifier_target_key != target_key and not (
                modifier_target_key == WEAPON_MANEUVER_DAMAGE
                and target_key in {MELEE_MANEUVERS, WEAPON_DAMAGE}
            ):
                continue
            if not TargetResolver.matches_context(modifier, target_context):
                continue
            try:
                source_id = int(modifier.source_id)
            except (TypeError, ValueError):
                continue
            if source_id not in equipped_item_rune_ids:
                continue
            modifiers.append(modifier)
        return modifiers

    return _cached_equipment_value(engine, cache_key, collect_modifiers)

def _resolve_item_bound_numeric_modifiers(engine, base_value: int, modifiers: list) -> int:
    """Apply local item/rune numeric operators to an item base value."""
    resolved_total = int(base_value or 0)
    seen_unique_sources: set[tuple[str, str, str, str]] = set()
    for modifier in sorted(modifiers, key=lambda entry: (entry.priority, entry.source_type, entry.source_id)):
        if modifier.stack_behavior == StackBehavior.UNIQUE_BY_SOURCE:
            dedupe_key = (modifier.source_type, modifier.source_id, modifier.target_domain, modifier.target_key)
            if dedupe_key in seen_unique_sources:
                continue
            seen_unique_sources.add(dedupe_key)

        resolved_value = engine.modifier_engine._resolve_numeric_modifier(modifier)
        if resolved_value is None:
            continue

        if modifier.operator == ModifierOperator.OVERRIDE:
            resolved_total = int(resolved_value)
        elif modifier.operator == ModifierOperator.MULTIPLY:
            resolved_total = int(resolved_total * resolved_value)
        elif modifier.operator == ModifierOperator.FLOOR_DIVIDE:
            if resolved_value:
                resolved_total = int(resolved_total // resolved_value)
        elif modifier.operator == ModifierOperator.MIN_VALUE:
            resolved_total = max(resolved_total, int(resolved_value))
        elif modifier.operator == ModifierOperator.MAX_VALUE:
            resolved_total = min(resolved_total, int(resolved_value))
        else:
            resolved_total += int(resolved_value)
    return int(resolved_total)


def _global_weapon_context_combat_modifier(engine, target_key: str, context: dict[str, tuple[str, ...]]) -> int:
    """Return non-item-bound combat modifiers for one concrete weapon context."""
    total = 0
    for modifier in engine.modifier_engine.collect_active_modifiers(context=context):
        if str(getattr(modifier, "source_type", "") or "") in LOCAL_WEAPON_DAMAGE_SOURCE_TYPES:
            continue
        if modifier.target_domain != TargetDomain.COMBAT:
            continue
        modifier_target_key = str(modifier.target_key or "")
        if modifier_target_key != target_key and not (
            modifier_target_key == WEAPON_MANEUVER_DAMAGE
            and target_key in {MELEE_MANEUVERS, WEAPON_DAMAGE}
        ):
            continue
        total += int(engine.modifier_engine._resolve_numeric_modifier(modifier) or 0)
    return total


def _effective_armor_encumbrance(engine, character_item: CharacterItem) -> int:
    return max(
        0,
        _resolve_item_bound_numeric_modifiers(
            engine,
            int(ItemEngine(character_item).get_armor_encumbrance() or 0),
            [
                *_character_item_specific_armor_semantic_modifiers(engine, character_item, ARMOR_ENCUMBRANCE),
                *_character_item_specific_rune_modifiers(engine, character_item, ARMOR_ENCUMBRANCE),
            ],
        ),
    )


def _effective_armor_rs(engine, character_item: CharacterItem) -> int:
    """Return local armor RS including quality and item-bound semantic effects."""
    return max(
        0,
        _resolve_item_bound_numeric_modifiers(
            engine,
            int(ItemEngine(character_item).get_armor_rs_raw() or 0),
            [
                *_character_item_specific_armor_semantic_modifiers(engine, character_item, DEFENSE_RS),
                *_character_item_specific_rune_modifiers(engine, character_item, DEFENSE_RS),
            ],
        ),
    )


def _effective_armor_rs_delta(engine, character_item: CharacterItem) -> int:
    """Return the local RS change compared to this armor's physical base value."""
    raw_rs = int(ItemEngine(character_item).get_armor_rs_raw() or 0)
    return _effective_armor_rs(engine, character_item) - raw_rs


def _effective_shield_encumbrance(engine, character_item: CharacterItem) -> int:
    return max(
        0,
        _resolve_item_bound_numeric_modifiers(
            engine,
            int(ItemEngine(character_item).get_shield_encumbrance() or 0),
            [
                *_character_item_specific_armor_semantic_modifiers(engine, character_item, SHIELD_ENCUMBRANCE),
                *_character_item_specific_rune_modifiers(engine, character_item, SHIELD_ENCUMBRANCE),
            ],
        ),
    )


def equipped_weapon_rows(engine) -> list[dict]:
    """Return character-sheet-ready weapon rows with one prepared row per display profile."""
    return _cached_equipment_value(engine, "weapon_rows", lambda: _build_equipped_weapon_rows(engine))


def _build_equipped_weapon_rows(engine) -> list[dict]:
    rows: list[dict] = []
    bel_malus = engine.load_penalty()
    strength = int(engine.attributes().get(ATTR_ST, 0) or 0)
    for character_item in engine.equipped_weapon_items():
        item_engine = ItemEngine(character_item)
        weapon_context = _character_item_target_context(engine, character_item)
        maneuver_modifier = _global_weapon_context_combat_modifier(engine, MELEE_MANEUVERS, weapon_context)
        mastery_maneuver_bonus, mastery_damage_bonus = engine.weapon_mastery_bonus_for_item(character_item)
        item_specific_maneuver_modifier = _character_item_specific_maneuver_modifier(engine, character_item)
        item_specific_damage_modifier = _character_item_specific_damage_modifier(engine, character_item)
        item_specific_damage_dice_modifier = _character_item_specific_damage_dice_modifier(engine, character_item)
        maneuver_attribute_codes = item_engine.get_weapon_maneuver_attribute_codes()
        size_modifier = engine.size_modifier()
        common_maneuver_bonus = (
            item_engine.get_weapon_maneuver_quality_bonus()
            + maneuver_modifier
            + mastery_maneuver_bonus
            + item_specific_maneuver_modifier
            + size_modifier
        )
        maneuver_options = []
        for attribute_code in maneuver_attribute_codes:
            attribute_modifier = engine.attribute_modifier(attribute_code)
            total_maneuver_modifier = attribute_modifier + common_maneuver_bonus
            maneuver_options.append(
                {
                    "attribute_code": attribute_code,
                    "attribute_modifier": attribute_modifier,
                    "attribute_modifier_display": f"{attribute_modifier:+d}" if attribute_modifier else "0",
                    "total_modifier": total_maneuver_modifier,
                    "total_modifier_display": f"{total_maneuver_modifier:+d}" if total_maneuver_modifier else "0",
                    "with_bel": total_maneuver_modifier + bel_malus,
                    "with_bel_display": f"{(total_maneuver_modifier + bel_malus):+d}" if (total_maneuver_modifier + bel_malus) else "0",
                }
            )
        if not maneuver_options:
            total_maneuver_modifier = common_maneuver_bonus
            maneuver_options.append(
                {
                    "attribute_code": "-",
                    "attribute_modifier": 0,
                    "attribute_modifier_display": "0",
                    "total_modifier": total_maneuver_modifier,
                    "total_modifier_display": f"{total_maneuver_modifier:+d}" if total_maneuver_modifier else "0",
                    "with_bel": total_maneuver_modifier + bel_malus,
                    "with_bel_display": f"{(total_maneuver_modifier + bel_malus):+d}" if (total_maneuver_modifier + bel_malus) else "0",
                }
            )
        primary_maneuver_option = maneuver_options[0]
        damage_source_slug = item_engine.get_weapon_damage_source_slug()
        damage_stat_slug = damage_source_slug or item_engine.get_weapon_damage_type()
        damage_attribute_modifier = (
            0
            if item_engine.get_weapon_maneuver_attribute_mode() == WEAPON_MANEUVER_ATTRIBUTE_NONE
            else engine.attribute_modifier(ATTR_ST)
        )
        damage_stat_modifier = (
            engine.modifier_engine.resolve_numeric_total(TargetDomain.COMBAT, damage_stat_slug, context=weapon_context)
            if damage_stat_slug and str(damage_stat_slug).startswith("dmg_")
            else engine._resolve_stat_modifiers(damage_stat_slug)
            if damage_stat_slug
            else 0
        )
        weapon_damage_modifier = _global_weapon_context_combat_modifier(engine, WEAPON_DAMAGE, weapon_context)
        dmg_mod = damage_stat_modifier + damage_attribute_modifier
        total_damage_modifier = dmg_mod + mastery_damage_bonus + weapon_damage_modifier + item_specific_damage_modifier
        for profile_index, profile in enumerate(
            item_engine.weapon_profiles(dice_amount_bonus=item_specific_damage_dice_modifier)
        ):
            min_attribute_label = item_engine.get_weapon_min_attribute_label(profile["mode"])
            rows.append(
                {
                    "character_item": character_item,
                    "item": character_item.item,
                    "item_name": item_engine.get_name(),
                    "quality": item_engine.get_effective_quality(),
                    "quality_color": item_engine.get_quality_color(),
                    "dmg_mod": total_damage_modifier,
                    "dmg_mod_display": f"{total_damage_modifier:+d}" if total_damage_modifier else "0",
                    "maneuver_options": maneuver_options,
                    "maneuver_mod_display": " / ".join(
                        f"{option['attribute_code']} {option['total_modifier_display']}"
                        for option in maneuver_options
                    ),
                    "base_dmg_mod": dmg_mod,
                    "base_dmg_mod_display": f"{dmg_mod:+d}" if dmg_mod else "0",
                    "damage_attribute_modifier": damage_attribute_modifier,
                    "damage_stat_modifier": damage_stat_modifier,
                    "weapon_damage_modifier": weapon_damage_modifier,
                    "bel_malus": bel_malus,
                    "bel_malus_display": f"{bel_malus:+d}" if bel_malus else "0",
                    "with_bel": total_damage_modifier + bel_malus,
                    "with_bel_display": f"{(total_damage_modifier + bel_malus):+d}" if (total_damage_modifier + bel_malus) else "0",
                    "maneuver_with_bel_display": " / ".join(
                        f"{option['attribute_code']} {option['with_bel_display']}"
                        for option in maneuver_options
                    ),
                    "wield_mode": item_engine.get_weapon_wield_mode(),
                    "size_class": item_engine.get_size_class(),
                    "min_st": item_engine.get_weapon_min_st(profile["mode"]),
                    "min_attribute_label": min_attribute_label,
                    "min_attribute_compact": "Ge" in min_attribute_label,
                    "reload_time": item_engine.get_weapon_reload_time(),
                    "range_label": item_engine.get_weapon_range_label(strength=strength),
                    "maneuver_attribute_mode": item_engine.get_weapon_maneuver_attribute_mode(),
                    "maneuver_attribute_label": item_engine.get_weapon_maneuver_attribute_label(),
                    "maneuver_attribute_modifier": primary_maneuver_option["attribute_modifier"],
                    "mode": profile["mode"],
                    "damage": profile["damage"],
                    "mode_label": profile["mode_label"],
                    "is_primary_profile": profile_index == 0,
                    "quality_damage_bonus": item_engine.get_weapon_damage_quality_bonus(),
                    "quality_maneuver_bonus": item_engine.get_weapon_maneuver_quality_bonus(),
                    "weapon_mastery_damage_bonus": mastery_damage_bonus,
                    "weapon_mastery_maneuver_bonus": mastery_maneuver_bonus,
                    "size_modifier": size_modifier,
                    "weapon_mastery_quality_bonus": engine.weapon_mastery_quality_bonus_for_item(character_item.item),
                    "trait_maneuver_modifier": maneuver_modifier,
                    "item_maneuver_modifier": item_specific_maneuver_modifier,
                    "item_damage_modifier": item_specific_damage_modifier,
                    "item_damage_dice_modifier": item_specific_damage_dice_modifier,
                    "total_maneuver_modifier": primary_maneuver_option["total_modifier"],
                }
            )
    return rows


def equipped_armor_rows(engine) -> list[dict]:
    """Return equipped armor rows resolved through ItemEngine."""
    return _cached_equipment_value(engine, "armor_rows", lambda: _build_equipped_armor_rows(engine))


def _build_equipped_armor_rows(engine) -> list[dict]:
    rows: list[dict] = []
    for character_item in engine.equipped_armor_items():
        item_engine = ItemEngine(character_item)
        armor_stats = item_engine._get_armor_stats()
        rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "armor_stats": armor_stats,
                "item_name": item_engine.get_name(),
                "quality": item_engine.get_effective_quality(),
                "quality_color": item_engine.get_quality_color(),
                "rs": _effective_armor_rs(engine, character_item),
                "bel_raw": item_engine.get_armor_bel_raw() or 0,
                "bel_effective": _effective_armor_encumbrance(engine, character_item),
                "min_st": item_engine.get_armor_min_st(),
            }
        )
    return rows


def equipped_shield_rows(engine) -> list[dict]:
    """Return equipped shield rows resolved through ItemEngine."""
    return _cached_equipment_value(engine, "shield_rows", lambda: _build_equipped_shield_rows(engine))


def _build_equipped_shield_rows(engine) -> list[dict]:
    rows: list[dict] = []
    for character_item in engine.equipped_shield_items():
        item_engine = ItemEngine(character_item)
        rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "item_name": item_engine.get_name(),
                "quality": item_engine.get_effective_quality(),
                "quality_color": item_engine.get_quality_color(),
                "rs": item_engine.get_effective_shield_rs() or 0,
                "bel_raw": item_engine.get_shield_bel_raw() or 0,
                "bel_effective": _effective_shield_encumbrance(engine, character_item),
                "min_st": item_engine.get_shield_min_st(),
                "parade_bonus": int(getattr(getattr(character_item.item, "shieldstats", None), "parade_bonus", 0) or 0),
            }
        )
    return rows


def armor_zone_protection(engine) -> dict[str, int]:
    """Return zone protection including armor, shields, quality, and item-rune bonuses."""
    return _cached_equipment_value(engine, "armor_zone_protection", lambda: _armor_zone_protection(engine, for_grs=False))


def _armor_zone_protection(engine, *, for_grs: bool = False) -> dict[str, int]:
    """Return zone protection for display or the normalized GRS basis."""
    totals = {
        "head": 0,
        "face": 0,
        "eyes": 0,
        "neck": 0,
        "torso": 0,
        "organs": 0,
        "soft_tissue": 0,
        "arm_left": 0,
        "hand_left": 0,
        "leg_left": 0,
        "foot_left": 0,
        "arm_right": 0,
        "hand_right": 0,
        "leg_right": 0,
        "foot_right": 0,
    }
    component_groups: dict[int, dict[str, object]] = {}
    for character_item in engine.equipped_armor_items():
        item_engine = ItemEngine(character_item)
        zone_values = item_engine.get_armor_grs_zone_rs() if for_grs else item_engine.get_armor_zone_rs()
        if not zone_values:
            continue
        effective_rs = _effective_armor_rs(engine, character_item)
        rs_delta = _effective_armor_rs_delta(engine, character_item)
        adjusted_zone_values: dict[str, int] = {}
        for field_name in totals:
            if field_name not in zone_values:
                continue
            adjusted_zone_values[field_name] = (
                0
                if effective_rs <= 0
                else max(0, int(zone_values[field_name] or 0) + rs_delta)
            )
            totals[field_name] += adjusted_zone_values[field_name]
        armor_stats = item_engine._get_armor_stats()
        if for_grs and armor_stats is not None and armor_stats.parent_set_id:
            group = component_groups.setdefault(
                armor_stats.parent_set_id,
                {"zones": {}, "target_rs": 0},
            )
            group["target_rs"] = max(
                int(group["target_rs"]),
                _effective_armor_rs(engine, character_item),
            )
            group_zones = group["zones"]
            for zone in armor_stats.MAIN_ZONE_FIELDS:
                if zone in adjusted_zone_values:
                    group_zones[zone] = int(group_zones.get(zone, 0)) + adjusted_zone_values[zone]
    if for_grs:
        for group in component_groups.values():
            group_zones = group["zones"]
            if len(group_zones) <= 1:
                continue
            target_sum = int(group["target_rs"]) * 6
            current_sum = sum(int(value or 0) for value in group_zones.values())
            if current_sum >= target_sum:
                continue
            target_zone = next(
                zone
                for zone in reversed(("head", "torso", "arm_left", "arm_right", "leg_left", "leg_right"))
                if zone in group_zones
            )
            totals[target_zone] += target_sum - current_sum
    shield_rs = shield_protection(engine)
    if shield_rs:
        for field_name in totals:
            totals[field_name] += shield_rs
    return totals


def shield_protection(engine) -> int:
    """Return summed protection from equipped shields."""
    return _cached_equipment_value(
        engine,
        "shield_protection",
        lambda: sum(
            int(ItemEngine(character_item).get_effective_shield_rs() or 0)
            for character_item in engine.equipped_shield_items()
        ),
    )


def equipped_clothing_rows(engine) -> list[dict]:
    """Return equipped clothing rows for the armor panel without combat stats."""
    return _cached_equipment_value(engine, "clothing_rows", lambda: _build_equipped_clothing_rows(engine))


def _build_equipped_clothing_rows(engine) -> list[dict]:
    rows: list[dict] = []
    for character_item in engine.equipped_clothing_items():
        item_engine = ItemEngine(character_item)
        rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "item_name": item_engine.get_name(),
                "quality": item_engine.get_effective_quality(),
                "quality_color": item_engine.get_quality_color(),
            }
        )
    return rows


def equipped_magic_item_rows(engine) -> list[dict]:
    """Return equipped magic item rows for the armor panel without combat stats."""
    return _cached_equipment_value(engine, "magic_item_rows", lambda: _build_equipped_magic_item_rows(engine))


def _build_equipped_magic_item_rows(engine) -> list[dict]:
    rows: list[dict] = []
    for character_item in engine.equipped_magic_item_items():
        item_engine = ItemEngine(character_item)
        rows.append(
            {
                "character_item": character_item,
                "item": character_item.item,
                "item_name": item_engine.get_name(),
                "quality": item_engine.get_effective_quality(),
                "quality_color": item_engine.get_quality_color(),
                "effect_summary": getattr(getattr(character_item.item, "magicitemstats", None), "effect_summary", ""),
            }
        )
    return rows


def get_grs(engine) -> int:
    """Calculate GRS from the six main hit zones, rounding only once."""
    return _cached_equipment_value(engine, "grs", lambda: _calculate_grs(engine))


def _calculate_grs(engine) -> int:
    zone_totals = _cached_equipment_value(
        engine,
        "armor_zone_protection_grs",
        lambda: _armor_zone_protection(engine, for_grs=True),
    )
    main_zone_sum = sum(
        int(zone_totals[zone])
        for zone in ("head", "torso", "arm_left", "arm_right", "leg_left", "leg_right")
    )
    global_modifiers = _non_local_rs_modifier(engine)
    return (main_zone_sum // 6) + global_modifiers


def _non_local_rs_modifier(engine) -> int:
    """Return RS modifiers that are not bound to a concrete armor item."""
    modifiers = [
        modifier
        for modifier in engine.modifier_engine.collect_active_modifiers()
        if modifier.target_domain == TargetDomain.DERIVED_STAT
        and str(modifier.target_key or "") == DEFENSE_RS
        and not _is_local_armor_rs_source(engine, modifier)
    ]
    return _resolve_item_bound_numeric_modifiers(engine, 0, modifiers)


def _is_local_armor_rs_source(engine, modifier) -> bool:
    """Return whether a modifier belongs to an equipped armor item's own RS."""
    armor_character_item_ids = {int(item.id) for item in engine.equipped_armor_items()}
    if not armor_character_item_ids:
        return False

    source_type = str(modifier.source_type or "")
    if source_type == "characteritem":
        try:
            return int(modifier.source_id) in armor_character_item_ids
        except (TypeError, ValueError):
            return False

    if source_type == "item":
        metadata_character_item_id = (modifier.metadata or {}).get("character_item_id")
        if metadata_character_item_id is not None:
            try:
                return int(metadata_character_item_id) in armor_character_item_ids
            except (TypeError, ValueError):
                return False
        armor_item_ids = {int(item.item_id) for item in engine.equipped_armor_items()}
        try:
            return int(modifier.source_id) in armor_item_ids
        except (TypeError, ValueError):
            return False

    if source_type == SOURCE_ITEM_RUNE:
        armor_item_rune_ids = {
            int(item_rune.id)
            for item_rune in engine._equipped_item_runes
            if int(item_rune.item_id) in armor_character_item_ids
        }
        try:
            return int(modifier.source_id) in armor_item_rune_ids
        except (TypeError, ValueError):
            return False

    return False


def get_bel(engine) -> int:
    """Calculate the armor encumbrance value."""
    return _cached_equipment_value(engine, "bel", lambda: _calculate_bel(engine))


def _calculate_bel(engine) -> int:
    if engine.resolve_flags().get(ARMOR_PENALTY_IGNORE, False):
        return 0
    armor_bel = 0
    for armor in engine.equipped_armor_items():
        armor_bel += _effective_armor_encumbrance(engine, armor)

    shield_bel = 0
    for shield in engine.equipped_shield_items():
        shield_bel += _effective_shield_encumbrance(engine, shield)

    return armor_bel + shield_bel


def load_penalty(engine) -> int:
    """Return encumbrance as a signed penalty that can be added to derived values."""
    bel_value = int(engine.get_bel())
    return bel_value if bel_value <= 0 else -bel_value


def _semantic_rs_modifier(engine) -> int:
    """Return RS granted by semantic modifiers rather than physical armor stats."""
    total = 0
    for entry in engine.explain_modifier_resolution(TargetDomain.DERIVED_STAT, DEFENSE_RS):
        resolved_value = entry.get("resolved_value")
        if isinstance(resolved_value, (int, float)):
            total += int(resolved_value)
    return total


def get_ms(engine) -> int:
    """Return armor minimum strength using set MS or the loose-parts formula."""
    return _cached_equipment_value(engine, "ms", lambda: _calculate_ms(engine))


def _calculate_ms(engine) -> int:
    complete_armor_minimums = []
    for character_item in engine.equipped_armor_items():
        item_engine = ItemEngine(character_item)
        armor_stats = item_engine._get_armor_stats()
        if armor_stats is None or armor_stats.parent_set_id is not None:
            continue
        complete_armor_minimums.append(int(item_engine.get_armor_min_st() or 0))
    if complete_armor_minimums:
        return max(complete_armor_minimums)

    grs = max(0, int(engine.get_grs()) - _semantic_rs_modifier(engine))
    return (grs + 1) // 2


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
