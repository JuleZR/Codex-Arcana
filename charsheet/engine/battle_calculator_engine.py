"""Battle calculator helpers for the character sheet UI."""

from __future__ import annotations

from dataclasses import dataclass

from charsheet.constants import (
    ATTR_SPEC,
    ATTR_ST,
    MELEE_MANEUVERS,
    ONE_HANDED,
    SKILL_COMBAT,
    SOURCE_ITEM_RUNE,
    TWO_HANDED,
    WEAPON_DAMAGE,
    WEAPON_DAMAGE_DICE,
)
from charsheet.engine.item_engine import ItemEngine
from charsheet.models import CharacterItem, Item, ItemRune, Modifier, Race, School, Technique, Trait


MODIFIER_SOURCE_LABELS = {
    "race": "Volk",
    "trait": "Vorteil/Nachteil",
    "school": "Schule",
    "technique": "Technik",
    "item": "Gegenstand",
    "characteritem": "Ausrüstung",
    SOURCE_ITEM_RUNE: "Rune",
}
@dataclass(slots=True)
class AttackCalculationInput:
    """Normalized input for one to-hit calculation."""

    maneuver_value: int = 0
    used_ap: int = 0
    accumulated_successes: int = 0
    multiple_action_penalty: int = 0
    die_one: int = 0
    die_two: int = 0


@dataclass(slots=True)
class DamageCalculationInput:
    """Normalized input for one damage calculation."""

    dice_values: tuple[int, ...] = ()
    bonus_successes: int = 0
    flat_bonus: int = 0
    flat_operator: str = "+"
    manual_bonus: int = 0
    multiplier: int = 1


class BattleCalculatorEngine:
    """Prepare battle-calculator payloads and resolve calculator formulas."""

    @staticmethod
    def _safe_int(value, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _format_modifier(value: int) -> str:
        value = int(value)
        if value > 0:
            return f"+{value}"
        if value < 0:
            return f"-{abs(value)}"
        return "0"

    @staticmethod
    def _modifier_entry(label: str, value: str, *, source: str = "", tone: str = "modifier") -> dict[str, str]:
        return {
            "label": BattleCalculatorEngine._clean_display_text(label),
            "value": str(value),
            "source": BattleCalculatorEngine._clean_display_text(source),
            "tone": str(tone),
        }

    @staticmethod
    def _clean_display_text(value: object) -> str:
        text = str(value or "").strip()
        for marker in ("**", "__", "`"):
            text = text.replace(marker, "")
        return " ".join(text.split())

    @staticmethod
    def _prettify_source_id(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return "Unbekannt"
        if text.isdigit():
            return text
        return text.replace("_", " ").replace("-", " ").strip().title()

    @staticmethod
    def _clean_modifier_note_text(note_text: object) -> str:
        text = str(note_text or "").strip()
        if text.lower() == "mapped automatically from legacy modifier semantics.":
            return ""
        return text

    @classmethod
    def _resolve_modifier_source_name(cls, engine, source_type: object, source_id: object) -> str:
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
        if source_type_text == "characteritem" and source_id_text.isdigit():
            character_item = CharacterItem.objects.filter(pk=int(source_id_text)).select_related("item").first()
            if character_item is not None:
                return character_item.effective_name
        if source_type_text == SOURCE_ITEM_RUNE and source_id_text.isdigit():
            item_rune = ItemRune.objects.filter(pk=int(source_id_text)).select_related("rune", "item__item").first()
            if item_rune is not None:
                return item_rune.rune.name
        return cls._prettify_source_id(source_id_text or source_type_text)

    @classmethod
    def _resolve_modifier_source_detail(cls, engine, source_type: object, source_id: object) -> str:
        source_type_text = str(source_type or "").strip().lower()
        source_id_text = str(source_id or "").strip()
        if source_type_text == SOURCE_ITEM_RUNE and source_id_text.isdigit():
            item_rune = ItemRune.objects.filter(pk=int(source_id_text)).select_related("item__item").first()
            if item_rune is not None:
                return f"auf {item_rune.item.effective_name}"
        if source_type_text != "technique":
            return ""
        technique = None
        if source_id_text.isdigit():
            technique = engine._techniques_by_id.get(int(source_id_text))
            if technique is None:
                technique = Technique.objects.filter(pk=int(source_id_text)).select_related("school").only(
                    "name", "level", "school__name"
                ).first()
        if technique is None:
            return ""
        school_name = str(getattr(getattr(technique, "school", None), "name", "") or "").strip()
        technique_level = getattr(technique, "level", None)
        if school_name and technique_level:
            return f"{school_name} {int(technique_level)}"
        return school_name

    @classmethod
    def _build_grouped_explanation_rows(cls, engine, explanation: list[dict[str, object]]) -> list[dict[str, str]]:
        grouped: dict[tuple[str, str, str], int] = {}
        order: list[tuple[str, str, str]] = []
        for entry in explanation:
            resolved_value = entry.get("resolved_value")
            if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                continue
            source_type = str(entry.get("source_type") or "").strip().lower()
            source_label = MODIFIER_SOURCE_LABELS.get(source_type, cls._prettify_source_id(source_type))
            source_name = cls._resolve_modifier_source_name(engine, source_type, entry.get("source_id"))
            source_detail = cls._resolve_modifier_source_detail(engine, source_type, entry.get("source_id"))
            label = cls._clean_modifier_note_text(entry.get("notes")) or source_name or source_label or "Unbekannt"
            source = source_detail or (source_name if source_name and source_name != label else source_label if source_label != label else "")
            label = cls._clean_display_text(label)
            source = cls._clean_display_text(source)
            key = (source_type, label, source)
            if key not in grouped:
                grouped[key] = 0
                order.append(key)
            grouped[key] += int(resolved_value)
        return [
            cls._modifier_entry(label, cls._format_modifier(grouped[(source_type, label, source)]), source=source)
            for source_type, label, source in order
        ]

    @classmethod
    def _build_modifier_breakdown_rows(cls, engine, stat_key: str) -> list[dict[str, str]]:
        explanation = engine.explain_modifier_resolution("derived_stat", stat_key)
        if not explanation:
            explanation = cls._build_legacy_stat_modifier_explanation(engine, stat_key)
        return cls._build_grouped_explanation_rows(engine, explanation or [])

    @classmethod
    def _build_legacy_stat_modifier_explanation(cls, engine, stat_key: str) -> list[dict[str, object]]:
        modifiers = engine._modifiers_by_target.get((Modifier.TargetKind.STAT, stat_key), [])
        if not modifiers:
            return []

        learned_stack: set[int] = set()
        available_stack: set[int] = set()
        rows: list[dict[str, object]] = []
        for modifier in modifiers:
            resolved_value = engine._modifier_value(modifier, learned_stack, available_stack)
            if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                continue
            rows.append(
                {
                    "source_type": getattr(modifier.source_content_type, "model", ""),
                    "source_id": modifier.source_object_id,
                    "resolved_value": resolved_value,
                    "notes": getattr(modifier, "effect_description", ""),
                }
            )
        return rows

    @classmethod
    def _build_character_item_stat_modifier_rows(cls, engine, character_item, stat_key: str) -> list[dict[str, str]]:
        modifiers = [
            modifier
            for modifier in engine._modifiers_by_target.get(("stat", stat_key), [])
            if getattr(getattr(modifier, "source_content_type", None), "model", "") == "characteritem"
            and int(modifier.source_object_id or 0) == int(character_item.id)
        ]
        learned_stack: set[int] = set()
        available_stack: set[int] = set()
        explanation: list[dict[str, object]] = []
        for modifier in modifiers:
            resolved_value = engine._modifier_value(modifier, learned_stack, available_stack)
            if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                continue
            explanation.append(
                {
                    "source_type": getattr(modifier.source_content_type, "model", ""),
                    "source_id": modifier.source_object_id,
                    "resolved_value": resolved_value,
                    "notes": getattr(modifier, "effect_description", ""),
                }
            )
        if stat_key in {WEAPON_DAMAGE, WEAPON_DAMAGE_DICE}:
            equipped_item_rune_ids = {
                int(item_rune.id)
                for item_rune in character_item.item_runes.all()
                if item_rune.is_active
            }
            for modifier in engine.modifier_engine._active_item_rune_modifiers:
                if str(getattr(modifier, "source_type", "") or "") != SOURCE_ITEM_RUNE:
                    continue
                if str(getattr(modifier, "target_key", "") or "") != stat_key:
                    continue
                try:
                    source_id = int(getattr(modifier, "source_id", ""))
                except (TypeError, ValueError):
                    continue
                if source_id not in equipped_item_rune_ids:
                    continue
                resolved_value = engine.modifier_engine._resolve_numeric_modifier(modifier)
                if not isinstance(resolved_value, (int, float)) or int(resolved_value) == 0:
                    continue
                explanation.append(
                    {
                        "source_type": SOURCE_ITEM_RUNE,
                        "source_id": source_id,
                        "resolved_value": resolved_value,
                        "notes": getattr(modifier, "notes", ""),
                    }
                )
        return cls._build_grouped_explanation_rows(engine, explanation)

    @classmethod
    def _build_weapon_attack_modifiers(cls, engine, row: dict[str, object]) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        quality_bonus = cls._safe_int(row.get("quality_maneuver_bonus"))
        if quality_bonus:
            entries.append(cls._modifier_entry("Qualität", cls._format_modifier(quality_bonus), source=str(row["item"].name)))
        entries.extend(cls._build_grouped_explanation_rows(engine, engine.explain_modifier_resolution("combat_value", MELEE_MANEUVERS) or []))
        mastery_bonus = cls._safe_int(row.get("weapon_mastery_maneuver_bonus"))
        if mastery_bonus:
            mastery_source = "Schule: Waffenmeister"
            weapon_master_school_entry = getattr(engine, "_weapon_master_school_entry", None)
            if weapon_master_school_entry is not None and getattr(weapon_master_school_entry, "school", None) is not None:
                mastery_source = weapon_master_school_entry.school.name
            entries.append(cls._modifier_entry("Waffenmeister", cls._format_modifier(mastery_bonus), source=mastery_source))
        size_modifier = cls._safe_int(row.get("size_modifier"))
        if size_modifier:
            entries.append(cls._modifier_entry("GK", cls._format_modifier(size_modifier), source=engine.size_class()))
        entries.extend(cls._build_character_item_stat_modifier_rows(engine, row["character_item"], MELEE_MANEUVERS))
        bel_malus = cls._safe_int(row.get("bel_malus"))
        if bel_malus:
            entries.append(cls._modifier_entry("Belastung", cls._format_modifier(bel_malus), source="Charakterzustand"))
        return entries

    @classmethod
    def _build_weapon_damage_modifiers(cls, engine, row: dict[str, object]) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        strength_mod = cls._safe_int(engine.attribute_modifier(ATTR_ST))
        if strength_mod:
            entries.append(cls._modifier_entry("Stärke", cls._format_modifier(strength_mod), source="ST"))
        weapon_stats = getattr(row["item"], "weaponstats", None)
        damage_source = getattr(weapon_stats, "damage_source", None)
        damage_source_slug = getattr(damage_source, "slug", "") or getattr(weapon_stats, "damage_type", "")
        if damage_source_slug:
            entries.extend(cls._build_modifier_breakdown_rows(engine, damage_source_slug))
        mastery_bonus = cls._safe_int(row.get("weapon_mastery_damage_bonus"))
        if mastery_bonus:
            mastery_source = "Schule: Waffenmeister"
            weapon_master_school_entry = getattr(engine, "_weapon_master_school_entry", None)
            if weapon_master_school_entry is not None and getattr(weapon_master_school_entry, "school", None) is not None:
                mastery_source = weapon_master_school_entry.school.name
            entries.append(cls._modifier_entry("Waffenmeister", cls._format_modifier(mastery_bonus), source=mastery_source))
        entries.extend(cls._build_character_item_stat_modifier_rows(engine, row["character_item"], WEAPON_DAMAGE))
        return entries

    @classmethod
    def _build_weapon_damage_dice_modifiers(cls, engine, row: dict[str, object]) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for entry in cls._build_character_item_stat_modifier_rows(engine, row["character_item"], WEAPON_DAMAGE_DICE):
            value = str(entry.get("value") or "").strip()
            if value and not value.lower().endswith("w10"):
                value = f"{value} W10"
            entries.append(
                cls._modifier_entry(
                    entry.get("label") or "Zusatzwürfel",
                    value,
                    source=entry.get("source") or "Schadenswürfel",
                    tone=entry.get("tone") or "modifier",
                )
            )
        return entries

    @classmethod
    def calculate_attack_result(cls, payload: AttackCalculationInput) -> dict[str, object]:
        """Return resolved to-hit values for one calculator state."""
        die_one = max(0, cls._safe_int(payload.die_one))
        die_two = max(0, cls._safe_int(payload.die_two))
        dice_total = die_one + die_two
        nat20_bonus = 10 if die_one == 10 and die_two == 10 else 0
        modifier_total = (
            cls._safe_int(payload.maneuver_value)
            + cls._safe_int(payload.used_ap)
            - cls._safe_int(payload.accumulated_successes)
            - cls._safe_int(payload.multiple_action_penalty)
        )
        total = modifier_total + dice_total
        return {
            "dice_total": dice_total,
            "nat20_bonus": nat20_bonus,
            "modifier_total": modifier_total,
            "total": total,
        }

    @classmethod
    def calculate_damage_result(cls, payload: DamageCalculationInput) -> dict[str, object]:
        """Return resolved damage values for one calculator state."""
        dice_values = tuple(max(0, cls._safe_int(value)) for value in payload.dice_values)
        dice_total = sum(dice_values)
        bonus_successes = cls._safe_int(payload.bonus_successes)
        manual_bonus = cls._safe_int(payload.manual_bonus)
        flat_bonus = max(0, cls._safe_int(payload.flat_bonus))
        flat_operator = str(payload.flat_operator or "+").strip()
        multiplier = max(1, cls._safe_int(payload.multiplier, 1))

        subtotal = dice_total + bonus_successes + manual_bonus
        if flat_operator == "-":
            subtotal -= flat_bonus
        elif flat_operator == "/":
            subtotal = subtotal if flat_bonus <= 0 else subtotal // flat_bonus
        else:
            subtotal += flat_bonus

        total = subtotal * multiplier
        return {
            "dice_total": dice_total,
            "subtotal": subtotal,
            "total": total,
        }

    @classmethod
    def build_payload(cls, engine, skill_rows: list[dict], weapon_rows: list[dict]) -> dict[str, object]:
        """Return one prepared frontend payload for the battle calculator."""
        attack_options: list[dict[str, object]] = []
        seen_attack_keys: set[str] = set()
        combat_skill_ids: set[int] = set()
        base_attack_options_by_skill_id: dict[int, dict[str, object]] = {}
        for row in skill_rows:
            if str(row.get("row_kind") or "") != "skill":
                continue
            attribute_code = str(row.get("attribute") or "")
            category_slug = str(row.get("category_slug") or "")
            if category_slug != SKILL_COMBAT and attribute_code != ATTR_SPEC:
                continue
            combat_skill_ids.add(cls._safe_int(row.get("skill_id")))
            option_key = (
                f"character-skill-{row.get('character_skill_id')}"
                if row.get("character_skill_id")
                else f"skill-{row.get('skill_id')}-{row.get('display_name')}"
            )
            if option_key in seen_attack_keys:
                continue
            seen_attack_keys.add(option_key)
            base_label = str(row.get("name") or "Unbenannte Fertigkeit").rstrip(": ").strip()
            family = str(row.get("family") or "").replace("_", " ").strip()
            if attribute_code == ATTR_SPEC:
                label = f"{family} - mit {base_label}" if family else f"Spez - {base_label}"
            else:
                label = str(row.get("display_name") or base_label)
            attack_options.append(
                {
                    "id": option_key,
                    "skill_id": cls._safe_int(row.get("skill_id")),
                    "character_skill_id": cls._safe_int(row.get("character_skill_id")) or None,
                    "label": label,
                    "category": str(row.get("category_name") or ""),
                    "maneuver_value": cls._safe_int(row.get("total_value")),
                    "attribute": attribute_code,
                    "family": family,
                }
            )
            if attribute_code != ATTR_SPEC and cls._safe_int(row.get("skill_id")) not in base_attack_options_by_skill_id:
                base_attack_options_by_skill_id[cls._safe_int(row.get("skill_id"))] = attack_options[-1]

        for row in skill_rows:
            if str(row.get("row_kind") or "") != "weapon_context":
                continue
            skill_id = cls._safe_int(row.get("skill_id"))
            if skill_id not in combat_skill_ids:
                continue
            option_key = f"weapon-context-{skill_id}-{row.get('display_name')}"
            if option_key in seen_attack_keys:
                continue
            seen_attack_keys.add(option_key)
            base_label = str(row.get("name") or "Unbenannte Fertigkeit").rstrip(": ").strip()
            context_label = str(row.get("display_name") or "").strip()
            attack_options.append(
                {
                    "id": option_key,
                    "skill_id": skill_id,
                    "character_skill_id": None,
                    "label": f"{base_label} - {context_label}" if context_label else base_label,
                    "category": "Waffenkontext",
                    "maneuver_value": cls._safe_int(row.get("total_value")),
                    "attribute": str(row.get("attribute") or ""),
                    "family": str(row.get("family") or "").replace("_", " ").strip(),
                }
            )

        weapon_options: list[dict[str, object]] = []
        seen_weapon_keys: set[str] = set()
        for row in weapon_rows:
            character_item = row.get("character_item")
            item = row.get("item")
            if character_item is None or item is None:
                continue
            item_engine = ItemEngine(character_item)
            mode = str(row.get("mode") or ONE_HANDED)
            if mode not in {ONE_HANDED, TWO_HANDED}:
                mode = ONE_HANDED
            option_id = f"weapon-{character_item.pk}-{mode}"
            if option_id in seen_weapon_keys:
                continue
            seen_weapon_keys.add(option_id)
            damage_tuple = item_engine.get_weapon_damage(
                mode,
                dice_amount_bonus=cls._safe_int(row.get("item_damage_dice_modifier")),
            )
            if not damage_tuple:
                continue
            weapon_stats = getattr(item, "weaponstats", None)
            skill_ids = []
            if weapon_stats is not None:
                skill_ids = [skill.id for skill in weapon_stats.skills.all()]
            damage_label = str(row.get("damage") or "-")
            dice_amount, dice_faces, flat_bonus, flat_operator, *_damage_meta = damage_tuple
            label = str(row.get("item_name") or getattr(item, "name", "Waffe"))
            mode_label = str(row.get("mode_label") or "").strip()
            if mode_label:
                label = f"{label} ({mode_label})"
            weapon_options.append(
                {
                    "id": option_id,
                    "character_item_id": character_item.pk,
                    "label": label,
                    "base_name": str(row.get("item_name") or getattr(item, "name", "Waffe")),
                    "mode": mode,
                    "mode_label": mode_label,
                    "damage_label": damage_label,
                    "dice_amount": cls._safe_int(dice_amount, 1),
                    "dice_faces": cls._safe_int(dice_faces, 10),
                    "flat_bonus": cls._safe_int(flat_bonus),
                    "flat_operator": str(flat_operator or "+"),
                    "damage_modifier": cls._safe_int(row.get("dmg_mod")),
                    "skill_ids": skill_ids,
                    "attack_modifiers": cls._build_weapon_attack_modifiers(engine, row),
                    "damage_bonus_breakdown": cls._build_weapon_damage_modifiers(engine, row),
                    "damage_modifiers": cls._build_weapon_damage_dice_modifiers(engine, row),
                    "runes": [
                        str(entry.get("name") or "").strip()
                        for entry in (row.get("rune_rows") or [])
                        if str(entry.get("name") or "").strip()
                    ],
                }
            )

        seen_weapon_context_keys = {
            str(entry.get("label") or "").strip().casefold()
            for entry in attack_options
            if str(entry.get("category") or "") == "Waffenkontext"
        }
        seen_base_weapon_pairs: set[tuple[int, str]] = set()
        for weapon in weapon_options:
            weapon_name = str(weapon.get("base_name") or "").strip()
            if not weapon_name:
                continue
            for skill_id in weapon.get("skill_ids") or []:
                normalized_skill_id = cls._safe_int(skill_id)
                base_option = base_attack_options_by_skill_id.get(normalized_skill_id)
                if base_option is None:
                    continue
                pair_key = (normalized_skill_id, weapon_name.casefold())
                if pair_key in seen_base_weapon_pairs:
                    continue
                seen_base_weapon_pairs.add(pair_key)
                label = f"{base_option['label']} - mit {weapon_name}"
                if label.casefold() in seen_weapon_context_keys:
                    continue
                attack_options.append(
                    {
                        "id": f"weapon-fallback-{normalized_skill_id}-{weapon_name.casefold().replace(' ', '-')}",
                        "skill_id": normalized_skill_id,
                        "character_skill_id": base_option.get("character_skill_id"),
                        "label": label,
                        "category": "Waffenkontext",
                        "maneuver_value": cls._safe_int(base_option.get("maneuver_value")),
                        "attribute": str(base_option.get("attribute") or ""),
                        "family": str(base_option.get("family") or ""),
                    }
                )
                seen_weapon_context_keys.add(label.casefold())

        attack_options.sort(key=lambda entry: str(entry["label"]).lower())
        weapon_options.sort(key=lambda entry: str(entry["label"]).lower())
        return {
            "attack_options": attack_options,
            "weapon_options": weapon_options,
            "meta": {
                "title": "Kampfrechner",
                "subtitle": "Arkanes Analysewerkzeug für Treffer und Schaden",
            },
        }
