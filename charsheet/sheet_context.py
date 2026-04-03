"""Prepared context data for the character sheet template."""

from __future__ import annotations

from collections import OrderedDict

from charsheet.constants import ATTRIBUTE_ORDER, DAMAGE_TYPE_CHOICES, GK_MODS, QUALITY_CHOICES, QUALITY_COLOR_MAP
from charsheet.engine import ItemEngine
from charsheet.forms import (
    CharacterInfoInlineForm,
    CharacterSkillSpecificationForm,
    CharacterTechniqueSpecificationForm,
)
from charsheet.learning_progression import build_learning_progression_context
from charsheet.learning_rules import DEFAULT_SCHOOL_MAX_LEVEL, school_max_levels
from charsheet.models import (
    Character,
    CharacterItem,
    CharacterLanguage,
    CharacterTechnique,
    CharacterTrait,
    DamageSource,
    Item,
    Language,
    RaceTechnique,
    Rune,
    School,
    Skill,
    Technique,
    Trait,
)
from charsheet.view_utils import format_compact_number, format_modifier, format_thousands, quality_payload


SHOP_GROUP_LABELS = {
    Item.ItemType.WEAPON: "Waffen",
    Item.ItemType.ARMOR: "Rüstungen",
    Item.ItemType.SHIELD: "Schilde",
    Item.ItemType.AMMO: "Munition",
    Item.ItemType.CONSUM: "Verbrauchbar",
    Item.ItemType.MISC: "Sonstiges",
}
SHOP_GROUP_ORDER = [
    Item.ItemType.WEAPON,
    Item.ItemType.ARMOR,
    Item.ItemType.SHIELD,
    Item.ItemType.AMMO,
    Item.ItemType.CONSUM,
    Item.ItemType.MISC,
]
SHOP_FORM_ORDER = [
    Item.ItemType.MISC,
    Item.ItemType.CONSUM,
    Item.ItemType.AMMO,
    Item.ItemType.WEAPON,
    Item.ItemType.ARMOR,
    Item.ItemType.SHIELD,
]
QUALITY_TOOLTIP_TYPES = {Item.ItemType.ARMOR, Item.ItemType.WEAPON, Item.ItemType.SHIELD}
EQUIPPABLE_ITEM_TYPES = {Item.ItemType.ARMOR, Item.ItemType.WEAPON, Item.ItemType.SHIELD}
RUNE_RETROFIT_ITEM_TYPES = {Item.ItemType.ARMOR, Item.ItemType.WEAPON, Item.ItemType.MISC}


def _single_line(value: str) -> str:
    """Collapse multiline text into one tooltip-friendly line."""
    return " ".join(str(value or "").replace("\r", "\n").split())


def _to_roman(value: int | None) -> str:
    """Convert positive integers into Roman numerals for school level labels."""
    number = int(value or 0)
    if number <= 0:
        return ""
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    parts: list[str] = []
    for arabic, roman in numerals:
        while number >= arabic:
            parts.append(roman)
            number -= arabic
    return "".join(parts)


def _rune_image_url(rune: Rune) -> str:
    """Return a tooltip-safe rune image URL when an image is present."""
    image = getattr(rune, "image", None)
    if not image:
        return ""
    try:
        return _single_line(image.url)
    except (ValueError, OSError):
        return ""


def _collect_rune_rows(*, item: Item, character_item: CharacterItem | None = None) -> list[dict[str, str]]:
    """Return combined visible rune rows for tooltips without duplicate entries."""
    rows: list[dict[str, str]] = []
    seen_ids: set[int] = set()
    for runes in (
        item.runes.all(),
        character_item.runes.all() if character_item is not None else [],
    ):
        for rune in runes:
            if rune.id in seen_ids:
                continue
            seen_ids.add(rune.id)
            rows.append(
                {
                    "name": rune.name,
                    "description": "",
                    "image": _rune_image_url(rune),
                }
            )
    return rows


def _format_rune_tooltip_block(*, item: Item, character_item: CharacterItem | None = None) -> str:
    """Return compact rune markup for the tooltip renderer."""
    rune_rows = _collect_rune_rows(item=item, character_item=character_item)
    if not rune_rows:
        return ""
    lines: list[str] = []
    for row in rune_rows:
        lines.append(f"[[RUNE:{row['name']}|{row['description']}|{row['image']}]]")
    return "\n".join(lines)

def _format_item_tooltip(
    *,
    description: str,
    quality_label: str | None = None,
    quality_color: str | None = None,
    status_label: str | None = None,
    status_color: str | None = None,
    rune_block: str = "",
) -> str:
    """Return the tooltip text used by item-related template rows."""
    body_parts = [part for part in (description, rune_block) if part]
    body = "\n\n".join(body_parts)
    status_line = ""
    if status_label and status_color:
        status_line = f"[[STATUS:{status_label}|{status_color}]]"
    if quality_label and quality_color:
        prefix = "\n".join(part for part in (status_line, f"[[QUALITY:{quality_label}|{quality_color}]]") if part)
        if body:
            return f"{prefix}\n\n{body}"
        return prefix
    if status_line:
        if body:
            return f"{status_line}\n\n{body}"
        return status_line
    return body


def _build_skill_rows(character: Character, engine, *, load_penalty: int) -> tuple[list[dict], object]:
    """Build prepared skill rows and return the queryset for reuse elsewhere."""
    skill_rows: list[dict] = []
    character_skills = (
        character.characterskill_set
        .select_related("skill", "skill__attribute", "skill__category")
        .order_by("skill__name")
    )
    for character_skill in character_skills:
        breakdown = engine.skill_breakdown(character_skill.skill.slug)
        if "error" in breakdown:
            continue
        specification = (character_skill.specification or "").strip()
        has_specification = (
            character_skill.skill.requires_specification
            and specification
            and specification != "*"
        )
        display_name = character_skill.skill.name.rstrip(": ").strip()
        if character_skill.skill.requires_specification:
            display_name = f"{display_name}: {specification if has_specification else '*'}"
        elif has_specification:
            display_name = f"{display_name} {specification}"
        skill_rows.append(
            {
                "character_skill_id": character_skill.id,
                "name": character_skill.skill.name,
                "display_name": display_name,
                "description": character_skill.skill.description,
                "attribute": character_skill.skill.attribute.short_name,
                "attribute_mod": format_modifier(breakdown["attribute_modifier"]),
                "rank": character_skill.level,
                "misc_mod": format_modifier(breakdown["modifiers"] - load_penalty),
                "total": breakdown["total"] - load_penalty,
                "with_load_total": breakdown["total"],
                "can_edit_specification": character_skill.skill.requires_specification,
                "specification": specification if specification != "*" else "",
            }
        )
    return skill_rows, character_skills


def _build_trait_rows(character: Character) -> tuple[list[dict], list[dict]]:
    """Build prepared rows for advantages and disadvantages."""
    traits_qs = (
        CharacterTrait.objects
        .filter(owner=character)
        .select_related("trait")
        .order_by("trait__trait_type", "trait__name")
    )
    advantage_rows: list[dict] = []
    disadvantage_rows: list[dict] = []
    for entry in traits_qs:
        row = {
            "name": entry.trait.name,
            "description": entry.trait.description,
            "points": entry.trait_level * entry.trait.points_per_level,
        }
        if entry.trait.trait_type == Trait.TraitType.ADV:
            advantage_rows.append(row)
        else:
            disadvantage_rows.append(row)
    return advantage_rows, disadvantage_rows


def _build_inventory_rows(character: Character) -> list[dict]:
    """Build prepared inventory rows for the unequipped inventory list."""
    inventory_rows: list[dict] = []
    inventory_items = (
        CharacterItem.objects
        .filter(owner=character, equipped=False)
        .select_related("item")
        .prefetch_related("item__runes", "runes")
        .order_by("item__name")
    )
    for character_item in inventory_items:
        item = character_item.item
        item_engine = ItemEngine(character_item)
        quality = quality_payload(item_engine.get_effective_quality())
        tooltip_text = ""
        if item.item_type in QUALITY_TOOLTIP_TYPES:
            tooltip_text = _format_item_tooltip(
                description=item.description or "",
                quality_label=quality["label"],
                quality_color=quality["color"],
                rune_block=_format_rune_tooltip_block(item=item, character_item=character_item),
            )
        elif item.description:
            tooltip_text = _format_item_tooltip(
                description=item.description,
                rune_block=_format_rune_tooltip_block(item=item, character_item=character_item),
            )
        elif item.runes.exists() or character_item.runes.exists():
            tooltip_text = _format_rune_tooltip_block(item=item, character_item=character_item)

        inventory_rows.append(
            {
                "character_item": character_item,
                "item": item,
                "has_runes": bool(item.runes.exists() or character_item.runes.exists()),
                "display_name": (
                    f"{character_item.amount}x {item.name}"
                    if item.stackable
                    else item.name
                ),
                "quality": quality["value"],
                "quality_label": quality["label"],
                "quality_color": quality["color"],
                "tooltip_text": tooltip_text,
                "can_consume": item.stackable and item.item_type == Item.ItemType.CONSUM,
                "can_equip": item.item_type in EQUIPPABLE_ITEM_TYPES,
                "can_socket_runes": item.item_type in RUNE_RETROFIT_ITEM_TYPES,
                "equip_label": "Anlegen",
                "base_rune_ids": [rune.id for rune in item.runes.all()],
                "base_rune_names": [rune.name for rune in item.runes.all()],
                "extra_rune_ids": [rune.id for rune in character_item.runes.all()],
            }
        )
    return inventory_rows


def _build_weapon_rows(engine) -> list[dict]:
    """Build prepared weapon rows with flattened display profiles."""
    weapon_rows: list[dict] = []
    for row in engine.equipped_weapon_rows():
        quality = quality_payload(str(row["quality"]))
        weapon_rows.append(
            {
                **row,
                "quality_label": quality["label"],
                "quality_color": quality["color"],
                "tooltip_text": _format_item_tooltip(
                    description=row["item"].description or "",
                    quality_label=quality["label"],
                    quality_color=quality["color"],
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    return weapon_rows


def _build_armor_rows(engine) -> list[dict]:
    """Build prepared armor and shield rows for the equipment panel."""
    armor_rows: list[dict] = []
    for row in engine.equipped_armor_rows():
        quality = quality_payload(str(row["quality"]))
        armor_rows.append(
            {
                **row,
                "kind": "armor",
                "quality_label": quality["label"],
                "quality_color": quality["color"],
                "summary": f"{row['item'].name} (RS {row['rs']} | Bel {row['bel_effective']} | Min-St {row['min_st'] or '-'})",
                "tooltip_text": _format_item_tooltip(
                    description=row["item"].description or "",
                    quality_label=quality["label"],
                    quality_color=quality["color"],
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in engine.equipped_shield_rows():
        quality = quality_payload(str(row["quality"]))
        armor_rows.append(
            {
                **row,
                "kind": "shield",
                "quality_label": quality["label"],
                "quality_color": quality["color"],
                "summary": f"{row['item'].name} (Schild-RS {row['rs']} | Bel {row['bel_effective']} | Min-St {row['min_st'] or '-'})",
                "tooltip_text": _format_item_tooltip(
                    description=row["item"].description or "",
                    quality_label=quality["label"],
                    quality_color=quality["color"],
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    return armor_rows


def _build_school_technique_rows(character: Character, engine) -> tuple[list[dict], dict[int, int]]:
    """Build visible learned technique rows for the school panel."""
    schools = list(
        character.schools
        .select_related("school", "school__type")
        .order_by("school__type__name", "school__name")
    )
    school_levels = {entry.school_id: entry.level for entry in schools}
    school_technique_rows: list[dict] = []
    learned_techniques_by_technique_id = {
        entry.technique_id: entry
        for entry in (
            CharacterTechnique.objects
            .filter(character=character)
            .select_related("technique")
        )
    }
    race_techniques = (
        RaceTechnique.objects
        .filter(race=character.race)
        .select_related("technique")
        .order_by("technique__name")
    )
    for race_link in race_techniques:
        technique = race_link.technique
        learned_technique = learned_techniques_by_technique_id.get(technique.id)
        specification_value = ((learned_technique.specification_value if learned_technique else "") or "").strip()
        entry_name = technique.name
        if technique.has_specification:
            entry_name = f"{technique.name}: {specification_value or '*'}"
        school_technique_rows.append(
            {
                "kind": "race_technique",
                "level": "",
                "school_name": character.race.name,
                "entry_name": entry_name,
                "description": technique.description,
                "can_edit_specification": bool(technique.has_specification),
                "specification_value": specification_value,
                "technique_id": technique.id,
            }
        )
    race_row_count = len(school_technique_rows)
    if school_levels:
        techniques = (
            Technique.objects
            .filter(school_id__in=school_levels.keys())
            .select_related("school")
            .order_by("school__name", "level", "name")
        )
        for technique in techniques:
            if technique.level <= school_levels.get(technique.school_id, 0):
                learned_technique = learned_techniques_by_technique_id.get(technique.id)
                specification_value = ((learned_technique.specification_value if learned_technique else "") or "").strip()
                entry_name = technique.name
                if technique.has_specification:
                    entry_name = f"{technique.name}: {specification_value or '*'}"
                school_technique_rows.append(
                    {
                        "kind": "technique",
                        "level": technique.level,
                        "level_label": _to_roman(technique.level),
                        "school_name": technique.school.name,
                        "entry_name": entry_name,
                        "description": technique.description,
                        "can_edit_specification": bool(technique.has_specification),
                        "specification_value": specification_value,
                        "technique_id": technique.id,
                    }
                )
    if race_row_count and len(school_technique_rows) > race_row_count:
        school_technique_rows[race_row_count - 1]["show_group_separator"] = True
    for school_entry in schools:
        for specialization_entry in engine.character_specializations(school_entry.school_id):
            specialization = specialization_entry.specialization
            school_technique_rows.append(
                {
                    "kind": "specialization",
                    "level": "Spez.",
                    "level_label": "Spez.",
                    "school_name": school_entry.school.name,
                    "entry_name": specialization.name,
                    "description": specialization.description,
                }
            )
    if school_levels:
        for technique in techniques:
            for choice in engine.technique_choices(technique):
                if choice.selected_specialization_id is None:
                    continue
                school_technique_rows.append(
                    {
                        "kind": "technique_specialization",
                        "level": "Spez.",
                        "level_label": "Spez.",
                        "school_name": technique.school.name,
                        "entry_name": f"{choice.selected_specialization.name} ({technique.name})",
                        "display_name": f"{choice.selected_specialization.name} ({technique.name})",
                        "description": choice.selected_specialization.description,
                    }
                )
    return school_technique_rows, school_levels


def _build_language_rows(character: Character) -> tuple[list[dict], object]:
    """Build the compact language display rows and keep the queryset for learning data."""
    language_entries = (
        CharacterLanguage.objects
        .filter(owner=character)
        .select_related("language")
        .order_by("-is_mother_tongue", "language__name")
    )
    language_rows: list[dict] = []
    for entry in language_entries:
        level_count = max(0, min(3, entry.levels))
        language_rows.append(
            {
                "name": entry.language.name,
                "level_1": level_count >= 1,
                "level_2": level_count >= 2,
                "level_3": level_count >= 3,
                "can_write": bool(entry.can_write),
            }
        )
    return language_rows, language_entries


def _build_shop_item_groups() -> list[dict]:
    """Build grouped shop rows from all buyable items."""
    grouped_items: dict[str, list[dict]] = {}
    buyable_items = (
        Item.objects
        .select_related("weaponstats", "armorstats", "shieldstats")
        .prefetch_related("runes")
        .order_by("item_type", "name")
    )
    for item in buyable_items:
        item_engine = ItemEngine(item)
        quality = quality_payload(item_engine.get_effective_quality())
        stats_payload: dict[str, object] = {
            "item_type": item.item_type,
            "size_class": item.size_class,
            "weight": str(item.weight),
            "min_st": None,
        }
        weapon_stats = getattr(item, "weaponstats", None)
        if weapon_stats is not None:
            stats_payload.update(
                {
                    "damage_dice_amount": weapon_stats.damage_dice_amount,
                    "damage_dice_faces": weapon_stats.damage_dice_faces,
                    "damage_flat_bonus": weapon_stats.damage_flat_bonus,
                    "h2_dice_amount": weapon_stats.h2_dice_amount,
                    "h2_dice_faces": weapon_stats.h2_dice_faces,
                    "h2_flat_bonus": weapon_stats.h2_flat_bonus,
                    "wield_mode": weapon_stats.wield_mode,
                    "min_st": weapon_stats.min_st,
                    "damage_type": weapon_stats.damage_type,
                }
            )
        armor_stats = getattr(item, "armorstats", None)
        if armor_stats is not None:
            stats_payload.update(
                {
                    "armor_rs": item_engine.get_armor_rs_raw() or 0,
                    "armor_bel": armor_stats.encumbrance,
                    "armor_min_st": armor_stats.min_st,
                    "min_st": armor_stats.min_st,
                }
            )
        shield_stats = getattr(item, "shieldstats", None)
        if shield_stats is not None:
            stats_payload.update(
                {
                    "shield_rs": shield_stats.rs,
                    "shield_bel": shield_stats.encumbrance,
                    "shield_min_st": shield_stats.min_st,
                    "min_st": shield_stats.min_st,
                }
            )
        grouped_items.setdefault(item.item_type, []).append(
            {
                "id": item.id,
                "name": item.name,
                "description": item.description or "",
                "item_type": item.item_type,
                "stackable": bool(item.stackable),
                "base_price": int(item.price),
                "default_price": item_engine.get_price(),
                "default_quality": quality["value"],
                "default_quality_label": quality["label"],
                "default_quality_color": quality["color"],
                "stats": stats_payload,
                "rune_ids": [rune.id for rune in item.runes.all()],
            }
        )

    return [
        {
            "key": item_type,
            "label": SHOP_GROUP_LABELS[item_type],
            "items": grouped_items[item_type],
        }
        for item_type in SHOP_GROUP_ORDER
        if grouped_items.get(item_type)
    ]


def _build_learning_rows(
    character: Character,
    attributes: dict[str, int],
    character_skills,
    language_entries,
    school_levels: dict[int, int],
        ) -> dict[str, object]:
    """Build prepared learning rows grouped for the learning window."""
    attribute_limits = {
        limit.attribute.short_name: {
            "min": int(limit.min_value),
            "max": int(limit.max_value),
        }
        for limit in character.race.raceattributelimit_set.select_related("attribute")
    }
    skill_levels = {entry.skill_id: entry.level for entry in character_skills}
    language_lookup = {
        entry.language_id: {
            "level": int(entry.levels),
            "write": bool(entry.can_write),
            "mother": bool(entry.is_mother_tongue),
        }
        for entry in language_entries
    }
    trait_levels = {
        entry.trait_id: int(entry.trait_level)
        for entry in CharacterTrait.objects.filter(owner=character).select_related("trait")
    }

    learn_attr_rows: list[dict] = []
    for short_name, label in ATTRIBUTE_ORDER:
        base_value = int(attributes.get(short_name, 0))
        learn_attr_rows.append(
            {
                "short_name": short_name,
                "label": label,
                "base_value": base_value,
                "min_value": int(attribute_limits.get(short_name, {}).get("min", 0)),
                "max_value": int(attribute_limits.get(short_name, {}).get("max", base_value)),
            }
        )

    skill_groups: OrderedDict[str, list[dict]] = OrderedDict()
    for skill in Skill.objects.select_related("category", "attribute").order_by("category__name", "name"):
        skill_groups.setdefault(skill.category.name, []).append(
            {
                "slug": skill.slug,
                "name": skill.name,
                "description": (skill.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "base_level": int(skill_levels.get(skill.id, 0)),
            }
        )

    learn_language_rows: list[dict] = []
    for language in Language.objects.order_by("name"):
        base_state = language_lookup.get(language.id, {"level": 0, "write": False, "mother": False})
        learn_language_rows.append(
            {
                "slug": language.slug,
                "name": language.name,
                "base_level": int(base_state["level"]),
                "max_level": int(language.max_level),
                "base_write": bool(base_state["write"]),
                "base_mother": bool(base_state["mother"]),
            }
        )

    school_level_caps = school_max_levels()
    school_groups: OrderedDict[str, list[dict]] = OrderedDict()
    for school in School.objects.select_related("type").order_by("type__name", "name"):
        base_level = int(school_levels.get(school.id, 0))
        max_level = max(base_level, int(school_level_caps.get(school.id, DEFAULT_SCHOOL_MAX_LEVEL)))
        school_groups.setdefault(school.type.name, []).append(
            {
                "id": school.id,
                "name": school.name,
                "description": (school.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "type_name": school.type.name,
                "base_level": base_level,
                "max_level": max_level,
            }
        )

    trait_groups: OrderedDict[str, list[dict]] = OrderedDict()
    for trait in Trait.objects.order_by("trait_type", "name"):
        group_name = "Vorteile" if trait.trait_type == Trait.TraitType.ADV else "Nachteile"
        trait_groups.setdefault(group_name, []).append(
            {
                "slug": trait.slug,
                "name": trait.name,
                "description": (trait.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "base_level": int(trait_levels.get(trait.id, 0)),
                "min_level": int(trait.min_level),
                "max_level": int(trait.max_level),
                "points_per_level": int(trait.points_per_level),
            }
        )

    return {
        "learn_attr_rows": learn_attr_rows,
        "learn_trait_groups": [
            {"name": group_name, "rows": rows}
            for group_name, rows in trait_groups.items()
        ],
        "learn_skill_groups": [
            {"name": category_name, "rows": rows}
            for category_name, rows in skill_groups.items()
        ],
        "learn_language_rows": learn_language_rows,
        "learn_school_groups": [
            {"name": type_name, "rows": rows}
            for type_name, rows in school_groups.items()
        ],
    }


def build_character_sheet_context(character: Character, *, close_learn_window_once: bool = False) -> dict[str, object]:
    """Build the full character-sheet context without direct template calculations."""
    engine = character.engine
    attributes = engine.attributes()
    attr_mods = {
        short_name: format_modifier(engine.attribute_modifier(short_name))
        for short_name, _label in ATTRIBUTE_ORDER
    }
    attribute_rows = [
        {
            "short_name": short_name,
            "label": label,
            "value": attributes.get(short_name, 0),
            "modifier": attr_mods[short_name],
        }
        for short_name, label in ATTRIBUTE_ORDER
    ]
    load_penalty = engine.load_penalty()
    skill_rows, character_skills = _build_skill_rows(character, engine, load_penalty=load_penalty)
    advantage_rows, disadvantage_rows = _build_trait_rows(character)
    inventory_rows = _build_inventory_rows(character)
    weapon_rows = _build_weapon_rows(engine)
    armor_rows = _build_armor_rows(engine)
    school_technique_rows, school_levels = _build_school_technique_rows(character, engine)
    language_rows, language_entries = _build_language_rows(character)

    initiative_value = engine.calculate_initiative()
    current_wound_stage, _current_wound_penalty_stage = engine.current_wound_stage()
    current_wound_penalty = engine.current_wound_penalty_raw()
    current_wound_penalty_display = (
        "-"
        if current_wound_stage == "-"
        else format_modifier(current_wound_penalty)
    )

    wound_threshold_data = engine.wound_thresholds()
    wound_threshold_rows = [
        {"threshold": threshold, "stage": stage, "penalty": penalty}
        for threshold, (stage, penalty) in sorted(wound_threshold_data.items())
    ]
    wallet_gold, wallet_silver, wallet_copper = engine.km_to_coins()

    race = character.race
    size_class = getattr(race, "size_class", None) or getattr(race, "height_class", "-") or "-"
    size_class_mod = (
        format_modifier(int(GK_MODS[size_class]))
        if size_class in GK_MODS
        else "-"
    )
    movement_profile = engine.resolve_movement()
    ground_combat = int(race.combat_speed or 0) + int(movement_profile.values.get("ground_combat", 0))
    ground_march = int(race.march_speed or 0) + int(movement_profile.values.get("ground_march", 0))
    ground_sprint = int(race.sprint_speed or 0) + int(movement_profile.values.get("ground_sprint", 0))
    swim_speed = int(race.swimming_speed or 0) + int(movement_profile.values.get("swim", 0))
    fly_value = "-"
    has_flight = race.can_fly or any(
        key in movement_profile.values
        for key in ("fly_combat", "fly_march", "fly_sprint")
    )
    if has_flight and "fly" not in movement_profile.blocked_modes:
        combat_fly = int(race.combat_fly_speed or 0) + int(movement_profile.values.get("fly_combat", 0))
        march_fly = int(race.march_fly_speed or 0) + int(movement_profile.values.get("fly_march", 0))
        sprint_fly = int(race.sprint_fly_speed or 0) + int(movement_profile.values.get("fly_sprint", 0))
        fly_value = " | ".join(
            (
                format_compact_number(combat_fly),
                format_compact_number(march_fly),
                format_compact_number(sprint_fly),
            )
        )
    movement_ground = {
        "combat": format_compact_number(ground_combat),
        "march": format_compact_number(ground_march),
        "sprint": format_compact_number(ground_sprint),
        "swim": format_compact_number(swim_speed),
        "fly": fly_value,
    }

    learning_context = _build_learning_rows(
        character,
        attributes,
        character_skills,
        language_entries,
        school_levels,
    )
    learning_progression_context = build_learning_progression_context(character, engine=engine)
    shop_quality_choices = [
        {
            "value": value,
            "label": label,
            "color": QUALITY_COLOR_MAP.get(value, QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)]),
        }
        for value, label in QUALITY_CHOICES
    ]

    return {
        "character": character,
        "char_info_form": CharacterInfoInlineForm(instance=character),
        "skill_specification_form": CharacterSkillSpecificationForm(),
        "technique_specification_form": CharacterTechniqueSpecificationForm(),
        "fame_total_rank": int(character.personal_fame_rank) + int(character.sacrifice_rank) + int(character.artefact_rank),
        "attributes": attributes,
        "attr_mods": attr_mods,
        "attribute_rows": attribute_rows,
        "skill_rows": skill_rows,
        "advantage_rows": advantage_rows,
        "disadvantage_rows": disadvantage_rows,
        "inventory_rows": inventory_rows,
        "weapon_rows": weapon_rows,
        "armor_rows": armor_rows,
        "school_technique_rows": school_technique_rows,
        "core_stats": {
            "load_value": load_penalty,
            "initiative_display": format_modifier(initiative_value),
            "initiative_with_load_display": format_modifier(initiative_value + load_penalty),
            "vw": engine.vw(),
            "sr": engine.sr(),
            "gw": engine.gw(),
            "arcane_power": engine.calculate_arcane_power(),
        },
        "armor_summary": {
            "total_rs": engine.get_grs(),
            "load_value": load_penalty,
            "minimum_strength": engine.get_ms(),
        },
        "current_wound_stage": current_wound_stage,
        "current_wound_penalty": current_wound_penalty_display,
        "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
        "current_damage_max": max(wound_threshold_data.keys()) if wound_threshold_data else 0,
        "wound_threshold_rows": wound_threshold_rows,
        "wallet_gold": wallet_gold,
        "wallet_silver": wallet_silver,
        "wallet_copper": wallet_copper,
        "wallet_total_ks": format_thousands(character.money),
        "size_class": size_class,
        "size_class_mod": size_class_mod,
        "movement_ground": movement_ground,
        "language_rows": language_rows,
        "shop_item_groups": _build_shop_item_groups(),
        "shop_quality_choices": shop_quality_choices,
        "shop_item_form_type_choices": [
            (item_type, dict(Item.ItemType.choices)[item_type])
            for item_type in SHOP_FORM_ORDER
        ],
        "shop_damage_type_choices": DAMAGE_TYPE_CHOICES,
        "shop_damage_source_choices": DamageSource.objects.order_by("name"),
        "shop_runes": Rune.objects.order_by("name"),
        "rune_retrofit_choices": [
            {
                "id": rune.id,
                "name": rune.name,
                "description": _single_line(rune.description),
            }
            for rune in Rune.objects.order_by("name")
        ],
        "close_learn_window_once": close_learn_window_once,
        "learn_skill_count": sum(len(group["rows"]) for group in learning_context["learn_skill_groups"]),
        "learn_trait_count": sum(len(group["rows"]) for group in learning_context["learn_trait_groups"]),
        "learn_school_count": sum(len(group["rows"]) for group in learning_context["learn_school_groups"]),
        **learning_context,
        **learning_progression_context,
    }
