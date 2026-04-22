"""Prepared context data for the character sheet template."""

from __future__ import annotations

from collections import OrderedDict
import json
import math

from django.contrib.contenttypes.models import ContentType

from charsheet.constants import (
    ARMOR_PENALTY_IGNORE,
    ARCANE_POWER,
    ATTRIBUTE_ORDER,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DAMAGE_TYPE_CHOICES,
    DEFENSE_GW,
    DEFENSE_RS,
    DEFENSE_SR,
    DEFENSE_VW,
    GK_MODS,
    INITIATIVE,
    QUALITY_CHOICES,
    QUALITY_COLOR_MAP,
    STAT_SLUG_CHOICES,
)
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
    CharacterSpell,
    RaceStartingItem,
    CharacterTechnique,
    CharacterTrait,
    DamageSource,
    Item,
    Language,
    Modifier,
    RaceTechnique,
    Rune,
    School,
    Skill,
    SkillCategory,
    Spell,
    Specialization,
    Technique,
    Trait,
)
from charsheet.view_utils import format_compact_number, format_modifier, format_thousands, quality_payload


_DAMAGE_GAUGE_START = -180
_DAMAGE_GAUGE_SWEEP = 180
_DAMAGE_GAUGE_NEEDLE_MIN = 6.0
_DAMAGE_GAUGE_NEEDLE_MAX = 174.0
_DAMAGE_GAUGE_NEEDLE_SWEEP = _DAMAGE_GAUGE_NEEDLE_MAX - _DAMAGE_GAUGE_NEEDLE_MIN
_DAMAGE_GAUGE_CX = 120
_DAMAGE_GAUGE_CY = 122
_DAMAGE_GAUGE_RADIUS = 84
_DAMAGE_GAUGE_TICK_OUTER = 90
_DAMAGE_GAUGE_TICK_INNER_MAJOR = 70
_DAMAGE_GAUGE_TICK_INNER_MINOR = 76


def _damage_gauge_stage_label(stage: str) -> str:
    labels = {
        "-": "Stabil",
        "Angeschlagen": "Angeschlagen",
        "Verletzt": "Verletzt",
        "Verwundet": "Verwundet",
        "Schwer verwundet": "Schwer",
        "Ausser Gefecht": "Gefecht",
        "Außer Gefecht": "Gefecht",
        "Koma": "Koma",
        "Tod": "Tod",
    }
    return labels.get(stage, stage)


def _damage_gauge_point(angle_degrees: float, radius: float) -> tuple[float, float]:
    radians = math.radians(angle_degrees)
    return (
        _DAMAGE_GAUGE_CX + math.cos(radians) * radius,
        _DAMAGE_GAUGE_CY + math.sin(radians) * radius,
    )


def _damage_gauge_arc_path(start_angle: float, end_angle: float, radius: float = _DAMAGE_GAUGE_RADIUS) -> str:
    start_x, start_y = _damage_gauge_point(start_angle, radius)
    end_x, end_y = _damage_gauge_point(end_angle, radius)
    large_arc_flag = 1 if abs(end_angle - start_angle) > 180 else 0
    return (
        f"M {start_x:.2f} {start_y:.2f} "
        f"A {radius:.2f} {radius:.2f} 0 {large_arc_flag} 1 {end_x:.2f} {end_y:.2f}"
    )


def _mix_hex_color(start_hex: str, end_hex: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, float(ratio)))
    start = start_hex.lstrip("#")
    end = end_hex.lstrip("#")
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (0, 2, 4))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (0, 2, 4))
    mixed = tuple(round(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * ratio) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _build_damage_gauge_data(current_damage: int, threshold_rows: list[dict[str, int | str]], damage_max: int) -> dict[str, object]:
    if damage_max <= 0:
        damage_max = 1

    sorted_threshold_values = sorted(
        int(row["threshold"])
        for row in threshold_rows
        if row.get("threshold") is not None
    )

    def value_to_rotation(value: float) -> float:
        clamped = max(0.0, min(float(damage_max), float(value)))
        adjusted = clamped
        if clamped in sorted_threshold_values and clamped < float(damage_max):
            adjusted = clamped + 1.0
        elif 0.0 < clamped < float(damage_max):
            adjusted = clamped + 0.5
        adjusted = max(0.0, min(float(damage_max), adjusted))
        return _DAMAGE_GAUGE_NEEDLE_MIN + (adjusted / float(damage_max)) * _DAMAGE_GAUGE_NEEDLE_SWEEP

    sorted_rows = sorted(
        (
            {
                "threshold": int(row["threshold"]),
                "stage": str(row["stage"]),
                "penalty": int(row["penalty"] or 0),
            }
            for row in threshold_rows
            if row.get("threshold") is not None
        ),
        key=lambda row: row["threshold"],
    )

    interval_segments: list[dict[str, object]] = []
    current_stage = "-"
    current_penalty = 0
    segment_start = 0

    for row in sorted_rows:
        threshold = max(0, min(int(row["threshold"]), int(damage_max)))
        if row["stage"] == current_stage and row["penalty"] == current_penalty:
            continue
        if threshold > segment_start:
            interval_segments.append(
                {
                    "start_value": segment_start,
                    "end_value": threshold,
                    "stage": current_stage,
                    "penalty": current_penalty,
                }
            )
        current_stage = row["stage"]
        current_penalty = row["penalty"]
        segment_start = threshold

    if segment_start < damage_max:
        interval_segments.append(
            {
                "start_value": segment_start,
                "end_value": damage_max,
                "stage": current_stage,
                "penalty": current_penalty,
            }
        )

    if not interval_segments:
        interval_segments = [{"start_value": 0, "end_value": damage_max, "stage": "-", "penalty": 0}]

    if sorted_rows and sorted_rows[-1]["threshold"] >= damage_max:
        terminal_stage = sorted_rows[-1]["stage"]
        terminal_penalty = sorted_rows[-1]["penalty"]
        previous_threshold = sorted_rows[-2]["threshold"] if len(sorted_rows) > 1 else 0
        terminal_visual_width = max(1.0, (damage_max - previous_threshold) * 0.28)
        terminal_start = max(float(previous_threshold), float(damage_max) - terminal_visual_width)
        if interval_segments:
            interval_segments[-1]["end_value"] = terminal_start
        interval_segments.append(
            {
                "start_value": terminal_start,
                "end_value": float(damage_max),
                "stage": terminal_stage,
                "penalty": terminal_penalty,
            }
        )

    first_danger_index = next(
        (index for index, segment in enumerate(interval_segments) if int(segment["penalty"]) < 0),
        len(interval_segments),
    )

    def _segment_label_position(start_percent: float, end_percent: float) -> tuple[str, str]:
        mid_ratio = ((start_percent + end_percent) / 2.0) / 100.0
        angle = math.radians(180.0 - (mid_ratio * 180.0))
        radius_x = 38.0
        radius_y = 81.0
        x = 50.0 + math.cos(angle) * radius_x
        y = 100.0 - math.sin(angle) * radius_y
        return (f"{x:.2f}%", f"{y:.2f}%")

    segments: list[dict[str, object]] = []
    safe_count = max(1, first_danger_index)
    danger_count = max(1, len(interval_segments) - first_danger_index)
    for index, state_segment in enumerate(interval_segments):
        start_percent = (float(state_segment["start_value"]) / float(damage_max)) * 100.0
        end_percent = (float(state_segment["end_value"]) / float(damage_max)) * 100.0
        label_left, label_top = _segment_label_position(start_percent, end_percent)
        penalty = int(state_segment["penalty"])
        if index < first_danger_index:
            safe_ratio = 0.0 if safe_count <= 1 else index / float(safe_count - 1)
            color = _mix_hex_color("#18995a", "#7bd883", safe_ratio)
            class_name = "is-safe"
        else:
            danger_index = index - first_danger_index
            danger_ratio = 0.0 if danger_count <= 1 else danger_index / float(danger_count - 1)
            color = _mix_hex_color("#f08a56", "#b31325", danger_ratio)
            class_name = "is-danger"
        if str(state_segment["stage"]).strip() == "Koma":
            color = "#8d1623"

        segments.append(
            {
                "stage": state_segment["stage"],
                "class_name": class_name,
                "start_percent": f"{start_percent:.4f}",
                "end_percent": f"{end_percent:.4f}",
                "color": color,
                "penalty_display": format_modifier(penalty) if penalty else "",
                "label_left": label_left,
                "label_top": label_top,
            }
        )

    gradient_stops = ", ".join(
        f"{segment['color']} {_DAMAGE_GAUGE_NEEDLE_MIN + (float(segment['start_percent']) / 100.0) * _DAMAGE_GAUGE_NEEDLE_SWEEP:.2f}deg "
        f"{_DAMAGE_GAUGE_NEEDLE_MIN + (float(segment['end_percent']) / 100.0) * _DAMAGE_GAUGE_NEEDLE_SWEEP:.2f}deg"
        for segment in segments
    )
    needle_angle = value_to_rotation(current_damage)
    return {
        "needle_angle": f"{needle_angle:.2f}",
        "segments": segments,
        "gradient_stops": gradient_stops,
    }


SHOP_GROUP_LABELS = {
    Item.ItemType.WEAPON: "Waffen",
    Item.ItemType.ARMOR: "Rüstungen",
    Item.ItemType.SHIELD: "Schilde",
    Item.ItemType.CLOTHING: "Kleidung",
    Item.ItemType.MAGIC_ITEM: "Magische Gegenstände",
    Item.ItemType.AMMO: "Munition",
    Item.ItemType.CONSUM: "Verbrauchbar",
    Item.ItemType.MISC: "Sonstiges",
}
SHOP_GROUP_ORDER = [
    Item.ItemType.WEAPON,
    Item.ItemType.ARMOR,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    Item.ItemType.MAGIC_ITEM,
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
    Item.ItemType.CLOTHING,
    Item.ItemType.MAGIC_ITEM,
]
QUALITY_TOOLTIP_TYPES = {
    Item.ItemType.ARMOR,
    Item.ItemType.WEAPON,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    Item.ItemType.MAGIC_ITEM,
}
EQUIPPABLE_ITEM_TYPES = {
    Item.ItemType.ARMOR,
    Item.ItemType.WEAPON,
    Item.ItemType.SHIELD,
    Item.ItemType.CLOTHING,
    Item.ItemType.MAGIC_ITEM,
}
RUNE_RETROFIT_ITEM_TYPES = {Item.ItemType.ARMOR, Item.ItemType.WEAPON, Item.ItemType.MISC}
MODIFIER_SOURCE_LABELS = {
    "race": "Rasse",
    "trait": "Merkmal",
    "school": "Schule",
    "technique": "Technik",
    "item": "Magischer Gegenstand",
}


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
    """Return combined visible rune rows for tooltips, including specification text."""
    rows: list[dict[str, str]] = []
    seen_base_ids: set[int] = set()
    for rune in item.runes.all():
        if rune.id not in seen_base_ids:
            seen_base_ids.add(rune.id)
            rows.append(
                {
                    "name": rune.name,
                    "description": rune.description or "",
                    "image": _rune_image_url(rune),
                }
            )
    if character_item is not None:
        specs = list(character_item.rune_specs.all())
        if specs:
            for spec in specs:
                if spec.rune_id in seen_base_ids:
                    continue
                display_name = spec.rune.name
                if spec.specification:
                    display_name = f"{spec.rune.name}: {spec.specification}"
                rows.append(
                    {
                        "name": display_name,
                        "description": spec.rune.description or "",
                        "image": _rune_image_url(spec.rune),
                    }
                )
        else:
            # Legacy fallback: use M2M when no spec records exist yet
            for rune in character_item.runes.all():
                if rune.id in seen_base_ids:
                    continue
                seen_base_ids.add(rune.id)
                rows.append(
                    {
                        "name": rune.name,
                        "description": rune.description or "",
                        "image": _rune_image_url(rune),
                    }
                )
    return rows


def _serialize_modifier_payload(modifier: Modifier) -> dict[str, object]:
    """Return one frontend-friendly magic modifier payload."""
    target_display = ""
    if modifier.target_kind == Modifier.TargetKind.STAT:
        target_display = dict(STAT_SLUG_CHOICES).get(str(modifier.target_slug or ""), str(modifier.target_slug or ""))
    elif modifier.target_kind == Modifier.TargetKind.SKILL and modifier.target_skill_id:
        target_display = modifier.target_skill.name
    elif modifier.target_kind == Modifier.TargetKind.CATEGORY and modifier.target_skill_category_id:
        target_display = modifier.target_skill_category.name
    elif modifier.target_kind == Modifier.TargetKind.ITEM_CATEGORY:
        target_display = dict(Item.ItemType.choices).get(str(modifier.target_slug or ""), str(modifier.target_slug or ""))
    elif modifier.target_kind == Modifier.TargetKind.SPECIALIZATION and modifier.target_specialization_id:
        target_display = modifier.target_specialization.name
    payload: dict[str, object] = {
        "target_kind": str(modifier.target_kind),
        "value": int(modifier.value),
        "effect_description": str(modifier.effect_description or ""),
        "target_display": target_display,
    }
    if modifier.target_kind == Modifier.TargetKind.STAT:
        payload["target_stat"] = str(modifier.target_slug or "")
    elif modifier.target_kind == Modifier.TargetKind.SKILL and modifier.target_skill_id:
        payload["target_skill"] = str(modifier.target_skill_id)
    elif modifier.target_kind == Modifier.TargetKind.CATEGORY and modifier.target_skill_category_id:
        payload["target_skill_category"] = str(modifier.target_skill_category_id)
    elif modifier.target_kind == Modifier.TargetKind.ITEM_CATEGORY:
        payload["target_item_category"] = str(modifier.target_slug or "")
    elif modifier.target_kind == Modifier.TargetKind.SPECIALIZATION and modifier.target_specialization_id:
        payload["target_specialization"] = str(modifier.target_specialization_id)
    return payload


def _build_character_item_magic_tooltip_rows(*, effect_summary: str, modifier_payloads: list[dict[str, object]]) -> list[tuple[str, object]]:
    """Return tooltip rows for magic effects stored on one owned item."""
    rows: list[tuple[str, object]] = []
    summary_line = _single_line(effect_summary)
    if summary_line:
        rows.append(("Effekt", summary_line))
    for payload in modifier_payloads:
        target_display = _single_line(str(payload.get("target_display") or "")) or "Ziel"
        effect_description = _single_line(str(payload.get("effect_description") or ""))
        try:
            value = int(payload.get("value") or 0)
        except (TypeError, ValueError):
            value = 0
        value_display = f"{value:+d} {target_display}"
        if effect_description:
            rows.append(("Magie", f"{effect_description} · {value_display}"))
        else:
            rows.append(("Magie", value_display))
    return rows


def _load_character_item_modifier_payloads(
    character_items: list[CharacterItem],
) -> dict[int, list[dict[str, object]]]:
    """Return serialized magic-modifier payloads keyed by owned item id."""
    if not character_items:
        return {}
    character_item_content_type = ContentType.objects.get_for_model(CharacterItem, for_concrete_model=False)
    modifiers_by_character_item_id: dict[int, list[dict[str, object]]] = {}
    for modifier in (
        Modifier.objects
        .filter(
            source_content_type=character_item_content_type,
            source_object_id__in=[entry.id for entry in character_items],
        )
        .select_related("target_skill", "target_skill_category", "target_specialization")
        .order_by("id")
    ):
        modifiers_by_character_item_id.setdefault(int(modifier.source_object_id), []).append(_serialize_modifier_payload(modifier))
    return modifiers_by_character_item_id


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
    detail_rows: list[tuple[str, object]] | None = None,
    rune_block: str = "",
) -> str:
    """Return the tooltip text used by item-related template rows."""
    table_rows: list[tuple[str, object]] = list(detail_rows or [])
    if quality_label and quality_color:
        table_rows.insert(0, ("Qualitaet", f"[[QUALITY:{quality_label}|{quality_color}]]"))
    if status_label and status_color:
        insert_at = 1 if quality_label else 0
        table_rows.insert(insert_at, ("Status", f"[[STATUS:{status_label}|{status_color}]]"))

    parts: list[str] = []
    table = _build_tooltip_table(table_rows)
    if table:
        parts.append(table)

    description_line = _single_line(description)
    if description_line:
        parts.append(description_line)
    if rune_block:
        parts.append(rune_block)
    return "\n\n".join(parts)


def _escape_tooltip_table_cell(value: object) -> str:
    """Escape tooltip table separators in markdown-style cells."""
    return str(value if value not in (None, "") else "-").replace("|", "\\|")


def _build_tooltip_table(rows: list[tuple[str, object]]) -> str:
    """Return a compact markdown table for the tooltip renderer."""
    if not rows:
        return ""
    lines = [
        "| Wert | Details |",
        "| --- | --- |",
    ]
    for label, value in rows:
        lines.append(
            f"| {_escape_tooltip_table_cell(label)} | {_escape_tooltip_table_cell(value)} |"
        )
    return "\n".join(lines)


def _build_core_stat_tooltip(rows: list[dict[str, object]]) -> str:
    """Return one compact bookkeeping-style table for a derived combat stat."""
    lines = [
        "| Posten | Wert | Herkunft |",
        "| --- | ---: | --- |",
    ]
    for row in rows:
        label = str(row.get("label", "") or "-")
        value = str(row.get("value", "") or "0")
        source = str(row.get("source", "") or "")
        if row.get("tone") == "modifier":
            label = f"**{label}**"
        if row.get("tone") == "total":
            label = f"**{label}**"
            value = f"**{value}**"
        lines.append(
            f"| {_escape_tooltip_table_cell(label)} | {_escape_tooltip_table_cell(f'`{value}`')} | {_escape_tooltip_table_cell(source or ' ')} |"
        )
    return "\n".join(lines)


def _build_item_tooltip_rows(item_engine: ItemEngine, item: Item) -> list[tuple[str, object]]:
    """Return structured item values for inventory-like tooltips."""
    rows: list[tuple[str, object]] = [("Kaufpreis", f"{format_thousands(item_engine.get_price())} KM")]

    weight = item_engine.get_weight()
    if weight not in (None, ""):
        rows.append(("Gewicht", weight))

    size_class = item_engine.get_size_class()
    if size_class:
        rows.append(("GK", size_class))

    if item.item_type == Item.ItemType.WEAPON:
        rows.append(("Schaden", item_engine.get_one_handed_damage_label()))
        two_handed_damage = item_engine.get_two_handed_damage_label()
        if two_handed_damage:
            rows.append(("2H Schaden", two_handed_damage))
        min_st = item_engine.get_weapon_min_st()
        if min_st is not None:
            rows.append(("Min-St", min_st))
    elif item.item_type == Item.ItemType.ARMOR:
        rs = item_engine.get_armor_rs_raw()
        if rs is not None:
            rows.append(("RS", rs))
        rows.append(("Bel", item_engine.get_armor_encumbrance()))
        min_st = item_engine.get_armor_min_st()
        if min_st is not None:
            rows.append(("Min-St", min_st))
    elif item.item_type == Item.ItemType.SHIELD:
        rs = item_engine.get_effective_shield_rs()
        if rs is not None:
            rows.append(("RS", rs))
        rows.append(("Bel", item_engine.get_shield_encumbrance()))
        min_st = item_engine.get_shield_min_st()
        if min_st is not None:
            rows.append(("Min-St", min_st))
    elif item.item_type == Item.ItemType.MAGIC_ITEM:
        effect_summary = getattr(getattr(item, "magicitemstats", None), "effect_summary", "")
        if effect_summary:
            rows.append(("Effekt", effect_summary))
    elif getattr(item, "magicitemstats", None) is not None:
        effect_summary = getattr(item.magicitemstats, "effect_summary", "")
        if effect_summary:
            rows.append(("Effekt", effect_summary))

    return rows


def _build_weapon_calculation_tooltip(engine, row: dict[str, object]) -> str:
    """Return a detailed damage-modifier ledger for one equipped weapon row."""
    weapon_stats = getattr(row["item"], "weaponstats", None)
    damage_source = getattr(weapon_stats, "damage_source", None)
    damage_source_name = getattr(damage_source, "name", "") or "Schadensquelle"
    damage_source_slug = getattr(damage_source, "slug", "") or getattr(weapon_stats, "damage_type", "")
    strength_mod = engine.attribute_modifier(ATTR_ST)
    source_mod = engine._resolve_stat_modifiers(damage_source_slug) if damage_source_slug else 0
    mastery_bonus = int(row.get("weapon_mastery_damage_bonus", 0) or 0)
    mastery_source = "Schule: Waffenmeister"
    weapon_master_school_entry = getattr(engine, "_weapon_master_school_entry", None)
    if weapon_master_school_entry is not None and getattr(weapon_master_school_entry, "school", None) is not None:
        mastery_source = f"Schule: {weapon_master_school_entry.school.name}"
    damage_modifier_rows = _build_modifier_breakdown_rows(engine, damage_source_slug) if damage_source_slug else []
    if not damage_modifier_rows:
        damage_modifier_rows = [
            {
                "label": f"{damage_source_name}-Mod.",
                "value": format_modifier(source_mod),
                "source": damage_source_name,
                "tone": "modifier" if source_mod else "",
            }
        ]

    return _build_core_stat_tooltip(
        [
            {"label": "ST-Bonus/Malus", "value": format_modifier(strength_mod), "source": "ST"},
            *damage_modifier_rows,
            {
                "label": "Waffenmeister",
                "value": format_modifier(mastery_bonus),
                "source": mastery_source,
                "tone": "modifier" if mastery_bonus else "",
            },
            {"label": "Belastung", "value": row["bel_malus_display"]},
            {"label": "= Gesamt", "value": row["with_bel_display"], "tone": "total"},
        ]
    )


def _build_total_armor_tooltip(engine) -> str:
    """Return a breakdown tooltip for the total armor protection value."""
    raw_armor_total = sum(ItemEngine(armor).get_armor_rs_raw() or 0 for armor in engine.equipped_armor_items())
    return _build_core_stat_tooltip(
        [
            {"label": "Ruestungen", "value": raw_armor_total},
            *_build_modifier_breakdown_rows(engine, DEFENSE_RS),
            {"label": "= Gesamt", "value": engine.get_grs(), "tone": "total"},
        ]
    )


def _build_load_tooltip(engine) -> str:
    """Return a breakdown tooltip for the effective encumbrance penalty."""
    armor_load = sum(ItemEngine(armor).get_armor_encumbrance() or 0 for armor in engine.equipped_armor_items())
    shield_load = sum(ItemEngine(shield).get_shield_encumbrance() or 0 for shield in engine.equipped_shield_items())
    total_raw_load = armor_load + shield_load
    rows: list[dict[str, object]] = [
        {"label": "Ruestungen", "value": armor_load},
        {"label": "Schilde", "value": shield_load},
    ]
    if engine.resolve_flags().get(ARMOR_PENALTY_IGNORE, False) and total_raw_load:
        rows.append({"label": "Belastung ignorieren", "value": format_modifier(-total_raw_load), "source": "Effekt"})
    rows.append({"label": "= Gesamt", "value": format_modifier(engine.load_penalty()), "tone": "total"})
    return _build_core_stat_tooltip(rows)


def _prettify_source_id(value: object) -> str:
    """Convert internal slugs into a compact human-readable fallback label."""
    text = str(value or "").strip()
    if not text:
        return "Unbekannt"
    if text.isdigit():
        return text
    return text.replace("_", " ").replace("-", " ").strip().title()


def _resolve_modifier_source_name(engine, source_type: object, source_id: object) -> str:
    """Return a readable source label for one modifier explanation row."""
    source_type_text = str(source_type or "").strip().lower()
    source_id_text = str(source_id or "").strip()
    if source_type_text == "race":
        race = getattr(engine.character, "race", None)
        if race is not None and (not source_id_text or source_id_text == str(race.id)):
            return race.name
        if source_id_text.isdigit():
            race = Race.objects.filter(pk=int(source_id_text)).only("name").first()
            if race is not None:
                return race.name
    if source_type_text == "trait":
        if source_id_text.isdigit():
            trait = Trait.objects.filter(pk=int(source_id_text)).only("name").first()
            if trait is not None:
                return trait.name
        trait = Trait.objects.filter(slug=source_id_text).only("name").first()
        if trait is not None:
            return trait.name
    if source_type_text == "school":
        if source_id_text.isdigit():
            school_entry = engine._school_entries.get(int(source_id_text))
            if school_entry is not None:
                return school_entry.school.name
            school = School.objects.filter(pk=int(source_id_text)).only("name").first()
            if school is not None:
                return school.name
    if source_type_text == "technique":
        if source_id_text.isdigit():
            technique = engine._techniques_by_id.get(int(source_id_text))
            if technique is not None:
                return technique.name
            technique = Technique.objects.filter(pk=int(source_id_text)).only("name").first()
            if technique is not None:
                return technique.name
    if source_type_text == "item" and source_id_text.isdigit():
        item = Item.objects.filter(pk=int(source_id_text)).only("name").first()
        if item is not None:
            return item.name
    return _prettify_source_id(source_id_text or source_type_text)


def _format_modifier_source_display(source_label: str, source_name: str) -> str:
    """Combine source family and concrete source into one compact display label."""
    source_label_text = str(source_label or "").strip()
    source_name_text = str(source_name or "").strip()
    if source_name_text and source_name_text.lower() != source_label_text.lower():
        return f"{source_label_text}: {source_name_text}" if source_label_text else source_name_text
    return source_label_text or source_name_text or "Unbekannt"


def _clean_modifier_note_text(note_text: object) -> str:
    """Hide generic migration notes that do not help the player-facing tooltip."""
    text = str(note_text or "").strip()
    if text.lower() == "mapped automatically from legacy modifier semantics.":
        return ""
    return text


def _build_modifier_breakdown_rows(engine, stat_key: str) -> list[dict[str, object]]:
    """Return ledger rows for each contributing modifier source."""
    grouped_rows: OrderedDict[tuple[str, str], dict[str, object]] = OrderedDict()
    explanation = engine.explain_modifier_resolution("derived_stat", stat_key)
    for entry in explanation:
        resolved_value = entry.get("resolved_value")
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        source_type = str(entry.get("source_type") or "").strip().lower()
        source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
        source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
        source_display = _format_modifier_source_display(source_label, source_name)
        note_text = _clean_modifier_note_text(entry.get("notes"))
        row_label = note_text or source_name or source_label
        group_key = (source_type, row_label)
        existing = grouped_rows.get(group_key)
        if existing is None:
            grouped_rows[group_key] = {
                "label": row_label,
                "value": int(resolved_value),
                "source": source_display,
                "tone": "modifier",
                "count": 1,
            }
            continue
        existing["value"] = int(existing["value"]) + int(resolved_value)
        existing["count"] = int(existing.get("count", 1)) + 1

    rows: list[dict[str, object]] = []
    for row in grouped_rows.values():
        label = str(row["label"])
        count = int(row.get("count", 1))
        if count > 1:
            label = f"{label} {_to_roman(count)}".strip()
        rows.append(
            {
                "label": label,
                "value": format_modifier(int(row["value"])),
                "source": row["source"],
                "tone": row["tone"],
            }
        )
    return rows


def _build_skill_modifier_rows(
    engine, skill_slug: str,
    *,
    skill_name: str,
    category_slug: str | None,
    skill_id: int | None) -> list[dict[str, object]]:
    """Return modifier rows for one skill calculation tooltip."""
    rows: list[dict[str, object]] = []
    for entry in engine.explain_modifier_resolution("skill", skill_slug):
        resolved_value = entry.get("resolved_value")
        if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
            continue
        source_type = str(entry.get("source_type") or "").strip().lower()
        source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
        source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
        source_display = _format_modifier_source_display(source_label, source_name)
        note_text = _clean_modifier_note_text(entry.get("notes"))
        rows.append(
            {
                "label": note_text or source_name or skill_name,
                "value": format_modifier(int(resolved_value)),
                "source": source_display,
                "tone": "modifier",
            }
        )
    if category_slug:
        for entry in engine.explain_modifier_resolution("skill_category", category_slug):
            resolved_value = entry.get("resolved_value")
            if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                continue
            source_type = str(entry.get("source_type") or "").strip().lower()
            source_label = MODIFIER_SOURCE_LABELS.get(source_type, _prettify_source_id(source_type))
            source_name = _resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
            source_display = _format_modifier_source_display(source_label, source_name)
            note_text = _clean_modifier_note_text(entry.get("notes"))
            rows.append(
                {
                    "label": note_text or source_name or "Kategorie-Bonus",
                    "value": format_modifier(int(resolved_value)),
                    "source": source_display,
                    "tone": "modifier",
                }
            )
    if skill_id is not None:
        choice_bonus = int(engine._resolve_choice_skill_bonus(skill_id))
        if choice_bonus:
            rows.append(
                {
                    "label": "Auswahlbonus",
                    "value": format_modifier(choice_bonus),
                    "source": "Auswahl",
                    "tone": "modifier",
                }
            )
        choice_modifiers = int(engine._resolve_choice_skill_modifiers(skill_id))
        if choice_modifiers:
            rows.append(
                {
                    "label": "Auswahl-Mod.",
                    "value": format_modifier(choice_modifiers),
                    "source": "Auswahl",
                    "tone": "modifier",
                }
            )
    return rows


def _build_skill_rows(character: Character, engine, *, load_penalty: int) -> tuple[list[dict], object]:
    """Build prepared skill rows and return the queryset for reuse elsewhere."""
    skill_rows: list[dict] = []
    character_skills = (
        character.characterskill_set
        .select_related("skill", "skill__attribute", "skill__category")
        .order_by("skill__name")
    )
    skills_map = engine.skills()
    for character_skill in character_skills:
        breakdown = engine.skill_breakdown(character_skill.skill.slug)
        if "error" in breakdown:
            continue
        skill_info = skills_map.get(character_skill.skill.slug, {})
        category_slug = skill_info.get("category")
        skill_id = skill_info.get("skill_id")
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
                "calculation_tooltip": _build_core_stat_tooltip(
                    [
                        {"label": "Eigenschaft", "value": format_modifier(breakdown["attribute_modifier"]), "source": character_skill.skill.attribute.short_name},
                        {"label": "Rang", "value": character_skill.level},
                        {
                            "label": "Wundmalus",
                            "value": format_modifier(engine.current_wound_penalty()),
                        },
                        *_build_skill_modifier_rows(
                            engine,
                            character_skill.skill.slug,
                            skill_name=character_skill.skill.name,
                            category_slug=category_slug,
                            skill_id=skill_id,
                        ),
                        {"label": "Belastung", "value": format_modifier(load_penalty)},
                        {"label": "= Gesamt", "value": breakdown["total"], "tone": "total"},
                    ]
                ),
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
            "points": entry.trait.cost_for_level(entry.trait_level),
        }
        if entry.trait.trait_type == Trait.TraitType.ADV:
            advantage_rows.append(row)
        else:
            disadvantage_rows.append(row)
    return advantage_rows, disadvantage_rows


def _race_item_ids() -> set[int]:
    """Return item ids that are reserved as race-starting equipment definitions."""
    return set(RaceStartingItem.objects.values_list("item_id", flat=True))


def _build_inventory_rows(character: Character) -> list[dict]:
    """Build prepared inventory rows for the unequipped inventory list."""
    inventory_rows: list[dict] = []
    race_item_ids = _race_item_ids()
    inventory_items = (
        CharacterItem.objects
        .filter(owner=character, equipped=False)
        .select_related("item")
        .prefetch_related("item__runes", "runes", "rune_specs__rune")
        .order_by("item__name")
    )
    inventory_items = list(inventory_items)
    modifiers_by_character_item_id = _load_character_item_modifier_payloads(inventory_items)
    for character_item in inventory_items:
        item = character_item.item
        is_race_item = item.id in race_item_ids
        item_engine = ItemEngine(character_item)
        quality = quality_payload(item_engine.get_effective_quality())
        magic_modifier_payloads = modifiers_by_character_item_id.get(character_item.id, [])
        tooltip_text = ""
        item_description = character_item.description or item.description or ""
        if not is_race_item and item.item_type in QUALITY_TOOLTIP_TYPES:
            tooltip_text = _format_item_tooltip(
                description=item_description,
                quality_label=quality["label"],
                quality_color=quality["color"],
                detail_rows=(
                    _build_item_tooltip_rows(item_engine, item)
                    + _build_character_item_magic_tooltip_rows(
                        effect_summary=character_item.magic_effect_summary or "",
                        modifier_payloads=magic_modifier_payloads,
                    )
                ),
            )
        elif item_description:
            tooltip_text = _format_item_tooltip(
                description=item_description,
                detail_rows=(
                    _build_item_tooltip_rows(item_engine, item)
                    + _build_character_item_magic_tooltip_rows(
                        effect_summary=character_item.magic_effect_summary or "",
                        modifier_payloads=magic_modifier_payloads,
                    )
                ),
            )

        inventory_rows.append(
            {
                "character_item": character_item,
                "item": item,
                "has_runes": bool(item.runes.exists() or character_item.runes.exists()),
                "rune_rows": _collect_rune_rows(item=item, character_item=character_item),
                "display_name": (
                    f"{character_item.amount}x {item.name}"
                    if item.stackable
                    else item.name
                ),
                "quality": "" if is_race_item else quality["value"],
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_text": tooltip_text,
                "can_consume": item.stackable and item.item_type == Item.ItemType.CONSUM,
                "can_equip": item.item_type in EQUIPPABLE_ITEM_TYPES or character_item.is_magic_effective,
                "can_socket_runes": item.item_type in RUNE_RETROFIT_ITEM_TYPES,
                "equip_label": "Anlegen",
                "base_rune_ids": [rune.id for rune in item.runes.all()],
                "base_rune_names": [rune.name for rune in item.runes.all()],
                "extra_rune_ids": [rune.id for rune in character_item.runes.all()],
                "rune_specs_json": json.dumps([
                    {
                        "rune_id": spec.rune_id,
                        "specification": spec.specification,
                        "slot": spec.slot,
                    }
                    for spec in character_item.rune_specs.all()
                ]),
                "description": character_item.description or item.description or "",
                "is_character_item_magic": bool(character_item.is_magic),
                "magic_effect_summary": character_item.magic_effect_summary or "",
                "magic_modifier_payloads": magic_modifier_payloads,
                "magic_modifier_payloads_json": json.dumps(magic_modifier_payloads),
            }
        )
    return inventory_rows


def _build_weapon_rows(engine) -> list[dict]:
    """Build prepared weapon rows with flattened display profiles."""
    weapon_rows: list[dict] = []
    race_item_ids = _race_item_ids()
    raw_rows = engine.equipped_weapon_rows()
    character_items = [row["character_item"] for row in raw_rows]
    modifiers_by_character_item_id = _load_character_item_modifier_payloads(character_items)
    profile_rows_by_item: OrderedDict[int, list[dict]] = OrderedDict()
    for row in raw_rows:
        character_item = row["character_item"]
        profile_rows_by_item.setdefault(character_item.pk, []).append(row)

    rendered_profiles_by_item: dict[int, int] = {}
    for row in raw_rows:
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(str(row["quality"]))
        profile_rows = profile_rows_by_item.get(row["character_item"].pk, [row])
        profile_index = rendered_profiles_by_item.get(row["character_item"].pk, 0)
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        weapon_rows.append(
            {
                **row,
                "is_last_profile": profile_index == (len(profile_rows) - 1),
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "tooltip_text": _format_item_tooltip(
                    description=row["character_item"].description or row["item"].description or "",
                    quality_label="" if is_race_item else quality["label"],
                    quality_color="" if is_race_item else quality["color"],
                    detail_rows=(
                        _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"])
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=row["character_item"].magic_effect_summary or "",
                            modifier_payloads=magic_modifier_payloads,
                        )
                    ),
                ),
                "has_runes": bool(row["item"].runes.exists() or row["character_item"].runes.exists()),
                "rune_rows": _collect_rune_rows(item=row["item"], character_item=row["character_item"]),
                "calculation_tooltip": _build_weapon_calculation_tooltip(engine, row),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
        rendered_profiles_by_item[row["character_item"].pk] = profile_index + 1
    return weapon_rows


def _build_armor_rows(engine) -> list[dict]:
    """Build prepared armor, clothing, and shield rows for the equipment panel."""
    armor_rows: list[dict] = []
    race_item_ids = _race_item_ids()
    armor_equipped_rows = engine.equipped_armor_rows()
    clothing_equipped_rows = engine.equipped_clothing_rows()
    magic_equipped_rows = engine.equipped_magic_item_rows()
    shield_equipped_rows = engine.equipped_shield_rows()
    all_character_items = [
        row["character_item"]
        for row in (*armor_equipped_rows, *clothing_equipped_rows, *magic_equipped_rows, *shield_equipped_rows)
    ]
    modifiers_by_character_item_id = _load_character_item_modifier_payloads(all_character_items)
    for row in armor_equipped_rows:
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(str(row["quality"]))
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        armor_rows.append(
            {
                **row,
                "kind": "armor",
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "summary": f"{row['item'].name} (RS {row['rs']} | Bel {row['bel_effective']} | Min-St {row['min_st'] or '-'})",
                "tooltip_text": _format_item_tooltip(
                    description=row["character_item"].description or row["item"].description or "",
                    quality_label="" if is_race_item else quality["label"],
                    quality_color="" if is_race_item else quality["color"],
                    detail_rows=(
                        _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"])
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=row["character_item"].magic_effect_summary or "",
                            modifier_payloads=magic_modifier_payloads,
                        )
                    ),
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in clothing_equipped_rows:
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(str(row["quality"]))
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        armor_rows.append(
            {
                **row,
                "kind": "clothing",
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "summary": f"{row['item'].name} (Kleidung)",
                "tooltip_text": _format_item_tooltip(
                    description=row["character_item"].description or row["item"].description or "",
                    quality_label="" if is_race_item else quality["label"],
                    quality_color="" if is_race_item else quality["color"],
                    detail_rows=(
                        _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"])
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=row["character_item"].magic_effect_summary or "",
                            modifier_payloads=magic_modifier_payloads,
                        )
                    ),
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in magic_equipped_rows:
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(str(row["quality"]))
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        armor_rows.append(
            {
                **row,
                "kind": "magic_item",
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "summary": f"{row['item'].name} (Magischer Gegenstand)",
                "tooltip_text": _format_item_tooltip(
                    description=row["character_item"].description or row["item"].description or "",
                    quality_label="" if is_race_item else quality["label"],
                    quality_color="" if is_race_item else quality["color"],
                    detail_rows=(
                        _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"])
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=row["character_item"].magic_effect_summary or "",
                            modifier_payloads=magic_modifier_payloads,
                        )
                    ),
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    for row in shield_equipped_rows:
        is_race_item = row["item"].id in race_item_ids
        quality = quality_payload(str(row["quality"]))
        magic_modifier_payloads = modifiers_by_character_item_id.get(row["character_item"].id, [])
        armor_rows.append(
            {
                **row,
                "kind": "shield",
                "quality_label": "" if is_race_item else quality["label"],
                "quality_color": "" if is_race_item else quality["color"],
                "summary": f"{row['item'].name} (Schild-RS {row['rs']} | Bel {row['bel_effective']} | Min-St {row['min_st'] or '-'})",
                "tooltip_text": _format_item_tooltip(
                    description=row["character_item"].description or row["item"].description or "",
                    quality_label="" if is_race_item else quality["label"],
                    quality_color="" if is_race_item else quality["color"],
                    detail_rows=(
                        _build_item_tooltip_rows(ItemEngine(row["character_item"]), row["item"])
                        + _build_character_item_magic_tooltip_rows(
                            effect_summary=row["character_item"].magic_effect_summary or "",
                            modifier_payloads=magic_modifier_payloads,
                        )
                    ),
                    rune_block=_format_rune_tooltip_block(item=row["item"], character_item=row["character_item"]),
                ),
                "can_unequip": not row["character_item"].equip_locked,
            }
        )
    return armor_rows


_SUPPORT_ICON_COMPUTED = "\u16C9"   # ᛉ — calculated by engine
_SUPPORT_ICON_DESCRIPTIVE = "\u16A8"  # ᚨ — rule text only
_SUPPORT_TOOLTIP_COMPUTED = (
    "Automatisch berechnet\u2009\u2013\u2009"
    "dieser Effekt wird vom System ermittelt und auf die relevanten Werte angewendet."
)
_SUPPORT_TOOLTIP_DESCRIPTIVE = (
    "Regeltext\u2009\u2013\u2009"
    "dieser Effekt wird nicht automatisch berechnet "
    "und muss eigenst\u00e4ndig nachgehalten werden."
)


def _support_icon(support_level: str) -> tuple[str, str]:
    """Return (icon, tooltip) for a technique's support_level value."""
    from charsheet.models.techniques import Technique
    if support_level == Technique.SupportLevel.DESCRIPTIVE:
        return _SUPPORT_ICON_DESCRIPTIVE, _SUPPORT_TOOLTIP_DESCRIPTIVE
    return _SUPPORT_ICON_COMPUTED, _SUPPORT_TOOLTIP_COMPUTED


def _build_school_technique_rows(character: Character, engine) -> tuple[list[dict], dict[int, int]]:
    """Build visible learned technique rows for the school panel."""
    schools = list(
        character.schools
        .select_related("school", "school__type")
        .order_by("school__type__name", "school__name")
    )
    school_levels = {entry.school_id: entry.level for entry in schools}
    school_technique_rows: list[dict] = []
    technique_specialization_names: dict[int, list[str]] = {}
    technique_specialization_descriptions: dict[int, list[str]] = {}
    learned_techniques_by_technique_id = {
        entry.technique_id: entry
        for entry in (
            CharacterTechnique.objects
            .filter(character=character)
            .select_related("technique")
        )
    }
    for choice in (
        character.technique_choices
        .filter(selected_specialization__isnull=False)
        .select_related("technique", "selected_specialization")
    ):
        technique_specialization_names.setdefault(choice.technique_id, []).append(choice.selected_specialization.name)
        description_text = (choice.selected_specialization.description or "").strip()
        if description_text:
            technique_specialization_descriptions.setdefault(choice.technique_id, []).append(description_text)
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
        icon, icon_tooltip = _support_icon(technique.support_level)
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
                "support_level_icon": icon,
                "support_level_tooltip": icon_tooltip,
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
                if (
                    technique.school.name == "Bardenschule"
                    and technique.level == 10
                    and technique.name == "Erwachte Begabung"
                ):
                    continue
                learned_technique = learned_techniques_by_technique_id.get(technique.id)
                if technique.acquisition_type == Technique.AcquisitionType.CHOICE and learned_technique is None:
                    continue
                specification_value = ((learned_technique.specification_value if learned_technique else "") or "").strip()
                entry_name = technique.name
                if technique.has_specification:
                    entry_name = f"{technique.name}: {specification_value or '*'}"
                selected_specializations = technique_specialization_names.get(technique.id, [])
                selected_specialization_descriptions = technique_specialization_descriptions.get(technique.id, [])
                description_text = technique.description
                if selected_specializations:
                    rendered_specializations = ", ".join(selected_specializations)
                    entry_name = f"{rendered_specializations} ({technique.name})"
                    if selected_specialization_descriptions:
                        description_text = "\n\n".join(selected_specialization_descriptions)
                icon, icon_tooltip = _support_icon(technique.support_level)
                school_technique_rows.append(
                    {
                        "kind": "technique",
                        "level": technique.level,
                        "level_label": _to_roman(technique.level),
                        "school_name": technique.school.name,
                        "school_id": technique.school_id,
                        "entry_name": entry_name,
                        "description": description_text,
                        "can_edit_specification": bool(technique.has_specification),
                        "specification_value": specification_value,
                        "technique_id": technique.id,
                        "support_level_icon": icon,
                        "support_level_tooltip": icon_tooltip,
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
                    "school_id": school_entry.school_id,
                    "entry_name": specialization.name,
                    "description": specialization.description,
                    "support_level_icon": _SUPPORT_ICON_DESCRIPTIVE,
                    "support_level_tooltip": _SUPPORT_TOOLTIP_DESCRIPTIVE,
                }
            )
    weapon_master_school = engine._weapon_master_school
    if weapon_master_school is not None and weapon_master_school.id in school_levels:
        school_level = school_levels.get(weapon_master_school.id, 0)
        mastered_entries = sorted(
            engine._weapon_mastery_entries_by_item_id.values(),
            key=lambda entry: (entry.pick_order, entry.weapon_item.name),
        )
        for mastery in mastered_entries:
            maneuver_bonus, damage_bonus = mastery.maneuver_damage_bonus(school_level)
            school_technique_rows.append(
                {
                    "kind": "weapon_mastery",
                    "level": mastery.pick_order,
                    "level_label": _to_roman(mastery.pick_order),
                    "school_name": weapon_master_school.name,
                    "school_id": weapon_master_school.id,
                    "entry_name": f"{mastery.weapon_item.name} ({maneuver_bonus} / {damage_bonus})",
                    "description": "",
                    "support_level_icon": _SUPPORT_ICON_COMPUTED,
                    "support_level_tooltip": _SUPPORT_TOOLTIP_COMPUTED,
                }
            )
    return school_technique_rows, school_levels


def _group_school_technique_rows(
    school_technique_rows: list[dict],
    school_levels: dict[int, int],
) -> tuple[list[dict], list[dict]]:
    """Split rows into race rows (flat) and school groups (collapsible).

    Returns (race_rows, school_groups) where each group is:
    {school_name, max_level, max_level_label, rows: [...]}.
    """
    race_rows: list[dict] = []
    groups: OrderedDict[str, dict] = OrderedDict()

    for row in school_technique_rows:
        if row["kind"] == "race_technique":
            race_rows.append(row)
            continue
        school_name = row["school_name"]
        if school_name not in groups:
            # Determine the character's current max level in this school.
            school_id = row.get("school_id")
            current_level = school_levels.get(school_id, 0) if school_id else 0
            groups[school_name] = {
                "school_name": school_name,
                "max_level": current_level,
                "max_level_label": _to_roman(current_level) if current_level else "",
                "rows": [],
            }
        groups[school_name]["rows"].append(row)

    return race_rows, list(groups.values())


def _build_language_rows(character: Character) -> tuple[list[dict], object]:
    """Build the compact language display rows and keep the queryset for learning data."""
    engine = character.engine
    language_entries = (
        CharacterLanguage.objects
        .filter(owner=character)
        .select_related("language")
        .order_by("-is_mother_tongue", "language__name")
    )
    language_rows: list[dict] = []
    for entry in language_entries:
        level_count = max(0, min(3, engine.resolve_language_level(entry.language.slug)))
        language_rows.append(
            {
                "name": entry.language.name,
                "level_1": level_count >= 1,
                "level_2": level_count >= 2,
                "level_3": level_count >= 3,
                "can_write": bool(engine.effective_language_write(entry.language.slug)),
            }
        )
    return language_rows, language_entries


def _build_shop_item_groups() -> list[dict]:
    """Build grouped shop rows from all buyable items."""
    grouped_items: dict[str, list[dict]] = {}
    race_item_ids = _race_item_ids()
    buyable_items = (
        Item.objects
        .select_related("weaponstats", "armorstats", "shieldstats", "magicitemstats")
        .prefetch_related("runes")
        .order_by("item_type", "name")
    )
    for item in buyable_items:
        if item.id in race_item_ids:
            continue
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
                    "damage_flat_operator": weapon_stats.damage_flat_operator,
                    "h2_dice_amount": weapon_stats.h2_dice_amount,
                    "h2_dice_faces": weapon_stats.h2_dice_faces,
                    "h2_flat_bonus": weapon_stats.h2_flat_bonus,
                    "h2_flat_operator": weapon_stats.h2_flat_operator,
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
        magic_item_stats = getattr(item, "magicitemstats", None)
        if magic_item_stats is not None:
            stats_payload.update(
                {
                    "effect_summary": magic_item_stats.effect_summary,
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
            "max": int(limit.max_value) + int(character.engine.resolve_attribute_cap_bonus(limit.attribute.short_name)),
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
    magic_engine = character.get_magic_engine()

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
                "points_display": trait.cost_display(),
                "points_by_level": list(trait.cost_curve()),
            }
        )

    magic_groups: OrderedDict[str, list[dict]] = OrderedDict()
    known_spell_ids = set(CharacterSpell.objects.filter(character=character).values_list("spell_id", flat=True))

    for school_entry in magic_engine._arcane_school_entries():
        choice_state = magic_engine.get_available_arcane_spell_choices(school_entry.school)
        free_choice_ids = {spell.id for spell in choice_state["options"]} if int(choice_state["remaining"]) > 0 else set()
        for spell in Spell.objects.filter(school_id=school_entry.school_id, grade__lte=school_entry.level).exclude(id__in=known_spell_ids).order_by(
            "grade",
            "name",
        ):
            if spell.id in free_choice_ids:
                continue
            magic_groups.setdefault("Zusatzzauber", []).append(
                {
                    "kind": "magic_spell",
                    "spell_id": spell.id,
                    "name": spell.name,
                    "owner_name": school_entry.school.name,
                    "base_level": int(spell.grade),
                    "cost": 2,
                    "description": (spell.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                    "search_tokens": f"{spell.name.lower()} {school_entry.school.name.lower()} zauber arkane magie",
                }
            )

    character_aspects = magic_engine.get_character_aspects()
    aspect_levels = {entry.aspect_id: int(entry.level) for entry in character_aspects}
    bonus_aspect_ids = {entry.aspect_id for entry in character_aspects if entry.is_bonus_aspect}
    for spell in Spell.objects.filter(aspect_id__in=aspect_levels.keys()).exclude(id__in=known_spell_ids).select_related("aspect").order_by(
        "aspect__name",
        "grade",
        "name",
    ):
        if int(spell.grade) > int(aspect_levels.get(spell.aspect_id, 0)):
            continue
        if spell.is_base_spell and spell.aspect_id in bonus_aspect_ids:
            continue
        magic_groups.setdefault("Zusatzzauber", []).append(
            {
                "kind": "magic_spell",
                "spell_id": spell.id,
                "name": spell.name,
                "owner_name": spell.aspect.name,
                "base_level": int(spell.grade),
                "cost": 2,
                "description": (spell.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "search_tokens": f"{spell.name.lower()} {spell.aspect.name.lower()} zauber aspekt klerikal",
            }
        )

    bonus_aspects = magic_engine.get_available_bonus_aspects()
    for aspect in bonus_aspects["options"]:
        magic_groups.setdefault("Aspekte", []).append(
            {
                "kind": "magic_aspect",
                "aspect_id": aspect.id,
                "name": aspect.name,
                "base_level": 0,
                "max_level": int(bonus_aspects["school_level"]),
                "cost_per_level": 4,
                "description": (aspect.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                "search_tokens": f"{aspect.name.lower()} aspekt klerikal magie",
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
        "learn_magic_groups": [
            {"name": group_name, "rows": rows}
            for group_name, rows in magic_groups.items()
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
    school_race_rows, school_technique_groups = _group_school_technique_rows(school_technique_rows, school_levels)
    language_rows, language_entries = _build_language_rows(character)

    initiative_value = engine.calculate_initiative()
    initiative_stat_mod = engine._resolve_stat_modifiers(INITIATIVE)
    initiative_ge_mod = engine.attribute_modifier(ATTR_GE)
    initiative_wound_penalty = engine.current_wound_penalty()
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
    current_damage_max = max(wound_threshold_data.keys()) if wound_threshold_data else 0
    damage_gauge = _build_damage_gauge_data(
        current_damage=character.current_damage,
        threshold_rows=wound_threshold_rows,
        damage_max=current_damage_max,
    )
    wallet_gold, wallet_silver, wallet_copper = engine.km_to_coins()
    vw_ge_mod = engine.attribute_modifier(ATTR_GE)
    vw_wa_mod = engine.attribute_modifier(ATTR_WA)
    if engine.resolve_flags().get("suppress_positive_vw_attribute_bonuses", False):
        vw_ge_mod = min(0, vw_ge_mod)
        vw_wa_mod = min(0, vw_wa_mod)
    vw_stat_mod = engine._resolve_stat_modifiers(DEFENSE_VW)
    sr_st_mod = engine.attribute_modifier(ATTR_ST)
    sr_kon_mod = engine.attribute_modifier(ATTR_KON)
    sr_stat_mod = engine._resolve_stat_modifiers(DEFENSE_SR)
    sr_value = engine.sr()
    gw_int_mod = engine.attribute_modifier(ATTR_INT)
    gw_will_mod = engine.attribute_modifier(ATTR_WILL)
    gw_stat_mod = engine._resolve_stat_modifiers(DEFENSE_GW)
    gw_value = engine.gw()
    willpower = attributes.get(ATTR_WILL, 0)
    school_level_total = sum(school_levels.values())
    arcane_power_value = engine.calculate_arcane_power()
    current_arcane_power = character.current_arcane_power
    if current_arcane_power is None:
        current_arcane_power = arcane_power_value
    current_arcane_power = max(0, int(current_arcane_power))
    arcane_power_display_max = max(int(arcane_power_value), int(current_arcane_power))
    arcane_meter_percent = 0 if arcane_power_display_max <= 0 else (current_arcane_power / arcane_power_display_max) * 100.0
    vw_value = engine.vw()

    race = character.race
    size_class = getattr(race, "size_class", None) or getattr(race, "height_class", "-") or "-"
    size_class_mod = (
        format_modifier(int(GK_MODS[size_class]))
        if size_class in GK_MODS
        else "-"
    )
    movement_profile = engine.resolve_movement()

    def _resolve_movement_value(base_value, target_key):
        base = int(base_value or 0)
        multiplier = float(movement_profile.multipliers.get(target_key, 1.0))
        additive = int(movement_profile.values.get(target_key, 0))
        return max(0, int(base * multiplier) + additive)

    ground_combat = _resolve_movement_value(race.combat_speed, "ground_combat")
    ground_march = _resolve_movement_value(race.march_speed, "ground_march")
    ground_sprint = _resolve_movement_value(race.sprint_speed, "ground_sprint")
    swim_speed = _resolve_movement_value(race.swimming_speed, "swim")
    fly_value = "-"
    has_flight = race.can_fly or any(
        key in movement_profile.values
        for key in ("fly_combat", "fly_march", "fly_sprint")
    )
    if has_flight and "fly" not in movement_profile.blocked_modes:
        combat_fly = _resolve_movement_value(race.combat_fly_speed, "fly_combat")
        march_fly = _resolve_movement_value(race.march_fly_speed, "fly_march")
        sprint_fly = _resolve_movement_value(race.sprint_fly_speed, "fly_sprint")
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
    magic_engine = character.get_magic_engine()
    spell_panel_data = magic_engine.get_spell_panel_data()
    load_tooltip = _build_load_tooltip(engine)
    total_armor_tooltip = _build_total_armor_tooltip(engine)
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
        "effective_personal_fame_point": max(0, int(character.personal_fame_point) + int(engine.resolve_resource("personal_fame_point"))),
        "effective_personal_fame_rank": max(0, int(character.personal_fame_rank) + int(engine.resolve_resource("personal_fame_rank"))),
        "effective_artefact_rank": max(0, int(character.artefact_rank) + int(engine.resolve_resource("artefact_rank"))),
        "char_info_form": CharacterInfoInlineForm(instance=character),
        "skill_specification_form": CharacterSkillSpecificationForm(),
        "technique_specification_form": CharacterTechniqueSpecificationForm(),
        "fame_total_rank": engine.fame_total() - max(0, int(character.personal_fame_point) + int(engine.resolve_resource("personal_fame_point"))),
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
        "school_race_rows": school_race_rows,
        "school_technique_groups": school_technique_groups,
        "core_stats": {
            "load_value": load_penalty,
            "load_tooltip": load_tooltip,
            "initiative_display": format_modifier(initiative_value),
            "initiative_with_load_display": format_modifier(initiative_value + load_penalty),
            "initiative_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "GE-Bonus/Malus", "value": format_modifier(initiative_ge_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "= Gesamt", "value": format_modifier(initiative_value), "tone": "total"},
                ]
            ),
            "initiative_with_load_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "GE-Bonus/Malus", "value": format_modifier(initiative_ge_mod)},
                    {"label": "Wundmalus", "value": format_modifier(initiative_wound_penalty)},
                    *_build_modifier_breakdown_rows(engine, INITIATIVE),
                    {"label": "Belastung", "value": format_modifier(load_penalty)},
                    {"label": "= Gesamt", "value": format_modifier(initiative_value + load_penalty), "tone": "total"},
                ]
            ),
            "vw": vw_value,
            "vw_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "GE-Bonus/Malus", "value": format_modifier(vw_ge_mod)},
                    {"label": "WA-Bonus/Malus", "value": format_modifier(vw_wa_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_VW),
                    {"label": "= Gesamt", "value": vw_value, "tone": "total"},
                ]
            ),
            "sr": sr_value,
            "sr_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "ST-Bonus/Malus", "value": format_modifier(sr_st_mod)},
                    {"label": "KON-Bonus/Malus", "value": format_modifier(sr_kon_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_SR),
                    {"label": "= Gesamt", "value": sr_value, "tone": "total"},
                ]
            ),
            "gw": gw_value,
            "gw_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Basis", "value": 14},
                    {"label": "INT-Bonus/Malus", "value": format_modifier(gw_int_mod)},
                    {"label": "WILL-Bonus/Malus", "value": format_modifier(gw_will_mod)},
                    *_build_modifier_breakdown_rows(engine, DEFENSE_GW),
                    {"label": "= Gesamt", "value": gw_value, "tone": "total"},
                ]
            ),
            "arcane_power": arcane_power_value,
            "arcane_power_tooltip": _build_core_stat_tooltip(
                [
                    {"label": "Will", "value": willpower},
                    {"label": "Stufen in Schulen", "value": school_level_total},
                    *_build_modifier_breakdown_rows(engine, ARCANE_POWER),
                    {"label": "= Gesamt", "value": arcane_power_value, "tone": "total"},
                ]
            ),
        },
        "armor_summary": {
            "total_rs": engine.get_grs(),
            "total_rs_tooltip": total_armor_tooltip,
            "load_value": load_penalty,
            "load_tooltip": load_tooltip,
            "minimum_strength": engine.get_ms(),
        },
        "current_wound_stage": current_wound_stage,
        "current_wound_penalty": current_wound_penalty_display,
        "is_wound_penalty_ignored": engine.is_wound_penalty_ignored(),
        "current_damage_max": current_damage_max,
        "damage_gauge_needle_angle": damage_gauge["needle_angle"],
        "damage_gauge_segments": damage_gauge["segments"],
        "damage_gauge_gradient_stops": damage_gauge["gradient_stops"],
        "wound_threshold_rows": wound_threshold_rows,
        "current_arcane_power": current_arcane_power,
        "current_arcane_power_max": arcane_power_display_max,
        "arcane_meter_percent": f"{arcane_meter_percent:.2f}",
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
            if item_type != Item.ItemType.MAGIC_ITEM
        ],
        "shop_damage_type_choices": DAMAGE_TYPE_CHOICES,
        "shop_damage_source_choices": DamageSource.objects.order_by("name"),
        "shop_modifier_target_kind_choices": [
            ("", "Kein Effekt"),
            ("stat", "Wert auf dem Bogen"),
            ("skill", "Einzelne Fertigkeit"),
            ("category", "Fertigkeitskategorie"),
            ("item_category", "Alle Gegenstände eines Typs"),
            ("specialization", "Spezialisierung"),
        ],
        "shop_modifier_stat_choices": STAT_SLUG_CHOICES,
        "shop_modifier_skill_choices": Skill.objects.order_by("name"),
        "shop_modifier_skill_category_choices": SkillCategory.objects.order_by("name"),
        "shop_modifier_item_category_choices": [
            (value, label) for value, label in Item.ItemType.choices if value != Item.ItemType.MAGIC_ITEM
        ],
        "shop_modifier_specialization_choices": Specialization.objects.order_by("name"),
        "shop_runes": Rune.objects.order_by("name"),
        "spell_panel_enabled": bool(spell_panel_data["spell_panel_enabled"]),
        "spell_and_lessons_panel_enabled": bool(spell_panel_data["spell_and_lessons_panel_enabled"]),
        "has_castable_entries": bool(spell_panel_data["has_castable_entries"]),
        "spell_panel_groups": spell_panel_data["groups"],
        "spell_panel_arcane_schools": spell_panel_data["arcane_schools"],
        "spell_panel_divine_summary": spell_panel_data["divine_summary"],
        "rune_retrofit_choices": [
            {
                "id": rune.id,
                "name": rune.name,
                "description": _single_line(rune.description),
                "has_specialization": rune.has_specialization,
                "specialization_label": rune.specialization_label or "Bezeichnung",
                "allow_multiple": rune.allow_multiple,
            }
            for rune in Rune.objects.order_by("name")
        ],
        "close_learn_window_once": close_learn_window_once,
        "learn_skill_count": sum(len(group["rows"]) for group in learning_context["learn_skill_groups"]),
        "learn_trait_count": sum(len(group["rows"]) for group in learning_context["learn_trait_groups"]),
        "learn_school_count": sum(len(group["rows"]) for group in learning_context["learn_school_groups"]),
        "learn_magic_count": sum(len(group["rows"]) for group in learning_context["learn_magic_groups"]),
        **learning_context,
        **learning_progression_context,
    }
