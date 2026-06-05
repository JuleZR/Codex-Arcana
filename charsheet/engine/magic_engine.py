"""Central magic rules for spells, aspects, divine entities, and casting."""

from __future__ import annotations

from collections import defaultdict
import re

from django.db import models, transaction

from charsheet.constants import SCHOOL_ARCANE, SCHOOL_DIVINE
from charsheet.models import (
    Aspect,
    Character,
    CharacterAspect,
    CharacterDivineEntity,
    CharacterSchool,
    CharacterSpell,
    CharacterSpellSource,
    DivineEntity,
    School,
    Spell,
    Trait,
)


BONUS_SPELL_TRAIT_SLUGS = (
    "zusatzzauber",
    "adv_zusatzzauber",
    "extra_spell",
    "adv_extra_spell",
)

BONUS_SPELL_TRAIT_NAMES = (
    "Zusatzzauber",
    "Extra Spell",
)

SPELL_LEARNING_SLOTS_PER_MAGIC_LEVEL = 2
SPELL_LEARNING_BONUS_SLOTS_PER_MAGIC_LEVEL = 1


def _aspect_spell_slot_source_key(aspect_id: int, grade: int) -> str:
    return f"aspect:{int(aspect_id)}:grade:{int(grade)}"


def _to_roman(value: int | None) -> str:
    """Return a compact roman numeral label used in grouped panel headers."""
    number = int(value or 0)
    mapping = (
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    if number <= 0:
        return ""
    result: list[str] = []
    for arabic, roman in mapping:
        while number >= arabic:
            result.append(roman)
            number -= arabic
    return "".join(result)


def _escape_tooltip_table_cell(value: object) -> str:
    """Escape markdown-style table separators used by the shared tooltip renderer."""
    return str(value if value not in (None, "") else "-").replace("|", "\\|")


def _effective_spell_level(
    entry: CharacterSpell,
    *,
    school_levels: dict[int, int] | None = None,
    aspect_levels: dict[int, int] | None = None,
) -> int:
    """Resolve the effective magic level used by this spell entry."""
    spell = entry.spell
    if entry.uses_divine_school_level and entry.granted_by_entity_id:
        if school_levels is not None:
            return int(school_levels.get(entry.granted_by_entity.school_id, 0))
        if entry.character_id:
            cs = CharacterSchool.objects.filter(
                character_id=entry.character_id,
                school_id=entry.granted_by_entity.school_id,
            ).first()
            return int(cs.level) if cs else 0
        return 0
    if spell.school_id and school_levels is not None:
        return int(school_levels.get(spell.school_id, 0))
    if spell.aspect_id and aspect_levels is not None:
        return int(aspect_levels.get(spell.aspect_id, 0))
    if entry.character_id:
        if spell.school_id:
            cs = CharacterSchool.objects.filter(character_id=entry.character_id, school_id=spell.school_id).first()
            return int(cs.level) if cs else 0
        if spell.aspect_id:
            ca = CharacterAspect.objects.filter(character_id=entry.character_id, aspect_id=spell.aspect_id).first()
            return int(ca.level) if ca else 0
    return 0


def _build_spell_tooltip(entry: CharacterSpell, *, school_levels: dict[int, int] | None = None, aspect_levels: dict[int, int] | None = None) -> str:
    """Return a structured tooltip with spell facts followed by the description."""
    spell = entry.spell
    attribute_label = "-"
    if spell.spell_attribute_id:
        raw_attribute_label = spell.spell_attribute.short_name or spell.spell_attribute.name
        attribute_label = str(raw_attribute_label).title()

    school_level = _effective_spell_level(entry, school_levels=school_levels, aspect_levels=aspect_levels)

    if spell.mw is None:
        mw_label = "-"
    elif spell.grade_adds_school_level:
        mw_label = str(int(spell.mw) + school_level)
    else:
        mw_label = str(int(spell.mw))
    resistance_label = str(spell.resistance_value or "-").strip() or "-"

    grade_label = str(int(spell.grade) + school_level) if spell.grade_adds_level else str(int(spell.grade))

    extra_cost = ""
    if spell.extra_cost_type == getattr(spell.ExtraCostType, "WOUND_GRADE", "") and spell.extra_cost_value:
        amount = int(spell.extra_cost_value)
        label = "Wundgrad" if amount == 1 else "Wundgrade"
        extra_cost = f"{amount} {label}"
    kp_cost_label = str(spell.kp_cost_label or "").strip()
    ep_cost_label = str(spell.ep_cost_label or "").strip()
    cost_label = f"{int(spell.kp_cost)} KP{kp_cost_label}"
    if spell.ep_cost:
        cost_label += f" [[SUB:oder {int(spell.ep_cost)} EP{ep_cost_label}]]"
    if extra_cost:
        cost_label += f" [[SUB:und {extra_cost}]]"
    rows: list[tuple[str, object]] = [
        ("Eigenschaft", attribute_label),
        ("Grad", grade_label),
        ("MW/Widerstandswert", f"{mw_label}/{resistance_label}"),
        ("Kosten", cost_label),
    ]
    _PLURAL = {
        "Aktion": "Aktionen",
        "Minute": "Minuten",
        "Stunde": "Stunden",
        "Tag": "Tage",
        "Woche": "Wochen",
        "Runde": "Runden",
    }

    def _unit_label(unit_display: str, number: int) -> str:
        if number != 1 and unit_display in _PLURAL:
            return _PLURAL[unit_display]
        return unit_display

    def _cast_time_label(number, unit_key) -> str | None:
        if number is not None and unit_key:
            unit = spell.CastTimeUnit(unit_key).label
            return f"{number} {_unit_label(unit, number)}"
        return None

    cast_time1 = _cast_time_label(spell.cast_time_number, spell.cast_time_unit)
    cast_time2 = _cast_time_label(spell.cast_time2_number, spell.cast_time2_unit)
    if cast_time1 and cast_time2:
        rows.append(("Zeitaufwand", f"{cast_time1} [[SUB:oder {cast_time2}]]"))
    elif cast_time1:
        rows.append(("Zeitaufwand", cast_time1))
    elif cast_time2:
        rows.append(("Zeitaufwand", cast_time2))
    elif spell.cast_time:
        rows.append(("Zeitaufwand", spell.cast_time))

    if spell.range_number is not None and spell.range_unit:
        unit = spell.get_range_unit_display()
        if spell.range_per_grade:
            total = spell.range_number * school_level
            range_unit_label = _unit_label(unit, total)
            note = f"[[SUB:Stufe {school_level} × {spell.range_number} {unit}]]"
            rows.append(("Reichweite", f"{total} {range_unit_label} {note}"))
        else:
            rows.append(("Reichweite", f"{spell.range_number} {_unit_label(unit, spell.range_number)}"))
    elif spell.range_text:
        rows.append(("Reichweite", spell.range_text))

    def _duration_label(number, unit_key, per_grade) -> str | None:
        if unit_key in ("sofort", "permanent", "Szene", "Konzentration"):
            from django.apps import apps
            return apps.get_model("charsheet", "Spell").DurationUnit(unit_key).label
        if number is not None and unit_key:
            from charsheet.models import Spell as _Spell
            unit = _Spell.DurationUnit(unit_key).label
            if per_grade:
                total = number * school_level
                note = f"[[SUB:Stufe {school_level} × {number} {unit}]]"
                return f"{total} {_unit_label(unit, total)} {note}"
            return f"{number} {_unit_label(unit, number)}"
        return None

    def _normalize_duration_text(value: str) -> str:
        return re.sub(r"\b([2-9]\d*)\s+Woche\b", r"\1 Wochen", value)

    dur1 = _duration_label(spell.duration_number, spell.duration_unit, spell.duration_per_grade)
    dur2 = _duration_label(spell.duration2_number, spell.duration2_unit, spell.duration2_per_grade)
    if dur1 and dur2:
        rows.append(("Wirkungsdauer", f"{dur1} [[SUB:oder {dur2}]]"))
    elif dur1:
        rows.append(("Wirkungsdauer", dur1))
    elif dur2:
        rows.append(("Wirkungsdauer", dur2))
    elif spell.duration_text:
        rows.append(("Wirkungsdauer", _normalize_duration_text(spell.duration_text)))

    lines = [
        "| Wert | Details |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| {_escape_tooltip_table_cell(label)} | {_escape_tooltip_table_cell(value)} |"
        for label, value in rows
    )

    description = str(spell.description or "").strip()
    if description:
        lines.append("")
        lines.append(description)
    return "\n".join(lines)


def _spell_group_sort_key(group_kind: str, group_name: str) -> tuple[int, str]:
    """Keep base spells first, then arcane schools, then divine aspects."""
    order = {
        "base": 0,
        "arcane": 1,
        "divine": 2,
    }
    return (order.get(group_kind, 99), group_name)


def _spell_owner_accent(name: str) -> str:
    """Return a stable card accent that roughly matches common magic symbols."""
    normalized = str(name or "").strip().lower()
    accents = (
        (("wasser", "eis", "frost", "kaelte", "kalte"), "#67bde8"),
        (("feuer", "flamme", "brand"), "#d9793b"),
        (("erde", "stein", "fels"), "#8d7a48"),
        (("luft", "wind", "sturm"), "#a7c8d8"),
        (("licht", "sonne"), "#e4c766"),
        (("schatten", "nacht", "dunkel"), "#8d75bd"),
        (("leben", "heil", "natur"), "#79b66a"),
        (("tod", "nekro", "verfall"), "#9b8f78"),
        (("blut", "krieg"), "#b45a4c"),
        (("geist", "seele"), "#8bb7b0"),
    )
    for needles, color in accents:
        if any(needle in normalized for needle in needles):
            return color
    return "#b98f56"


class MagicEngine:
    """Resolve magic progression, known spells, and casting for one character."""

    @staticmethod
    def _spell_group_symbol(group_kind: str, spell: Spell | None = None) -> str:
        if group_kind == "arcane" and spell is not None and spell.school_id:
            return str(getattr(spell.school, "panel_symbol", "") or "").strip() or "▶"
        if group_kind == "divine":
            return "✧"
        if group_kind == "base":
            return "✦"
        return ""

    @staticmethod
    def _spell_group_symbol_image_url(group_kind: str, spell: Spell | None = None) -> str:
        if group_kind != "arcane" or spell is None or not spell.school_id:
            return ""
        image = getattr(spell.school, "symbol_image", None)
        if not image:
            return ""
        try:
            return str(image.url or "")
        except ValueError:
            return ""

    @staticmethod
    def _image_url(image) -> str:
        if not image:
            return ""
        try:
            return str(image.url or "")
        except ValueError:
            return ""

    @classmethod
    def _spell_owner_symbol_data(cls, spell: Spell) -> dict[str, str]:
        if spell.school_id:
            return {
                "owner_symbol": str(getattr(spell.school, "panel_symbol", "") or "").strip() or "*",
                "owner_symbol_image_url": cls._image_url(getattr(spell.school, "symbol_image", None)),
            }
        if spell.aspect_id:
            return {
                "owner_symbol": str(spell.aspect.name or "?").strip()[:1] or "*",
                "owner_symbol_image_url": cls._image_url(getattr(spell.aspect, "aspect_image", None)),
            }
        return {"owner_symbol": "*", "owner_symbol_image_url": ""}

    def __init__(self, character: Character) -> None:
        self.character = character

    @staticmethod
    def _school_matches_magic_type(school_or_entry, expected_slug: str) -> bool:
        """Handle small legacy naming differences in school type data."""
        school = getattr(school_or_entry, "school", school_or_entry)
        school_type = getattr(school, "type", None)
        if school_type is None:
            return False
        slug = str(getattr(school_type, "slug", "") or "").strip().lower()
        name = str(getattr(school_type, "name", "") or "").strip().lower()
        if expected_slug == SCHOOL_ARCANE:
            return slug == SCHOOL_ARCANE or "arkan" in name or "magie" in name or "magic" in name
        if expected_slug == SCHOOL_DIVINE:
            return slug == SCHOOL_DIVINE or "kler" in name or "divin" in name or "priest" in name
        return False

    def _school_entries(self) -> list[CharacterSchool]:
        return list(
            self.character.schools.select_related("school", "school__type").order_by(
                "school__type__name",
                "school__name",
            )
        )

    def _school_level_map(self) -> dict[int, int]:
        return {entry.school_id: int(entry.level) for entry in self._school_entries()}

    def _arcane_school_entries(self) -> list[CharacterSchool]:
        return [entry for entry in self._school_entries() if self._school_matches_magic_type(entry, SCHOOL_ARCANE)]

    def _divine_school_entries(self) -> list[CharacterSchool]:
        return [entry for entry in self._school_entries() if self._school_matches_magic_type(entry, SCHOOL_DIVINE)]

    def _magic_school_entries(self) -> list[CharacterSchool]:
        return [
            entry
            for entry in self._school_entries()
            if self._school_matches_magic_type(entry, SCHOOL_ARCANE)
            or self._school_matches_magic_type(entry, SCHOOL_DIVINE)
        ]

    def _divine_binding(self) -> CharacterDivineEntity | None:
        return (
            CharacterDivineEntity.objects.filter(character=self.character)
            .select_related("entity", "entity__school", "entity__school__type")
            .first()
        )

    def _divine_arcane_grant_entities(self) -> list[DivineEntity]:
        learned_school_ids = {entry.school_id for entry in self._divine_school_entries()}
        if not learned_school_ids:
            return []
        entities_by_id: dict[int, DivineEntity] = {}
        binding = self._divine_binding()
        if (
            binding is not None
            and binding.entity.grants_arcane_spell_choice_per_level
            and binding.entity.school_id in learned_school_ids
        ):
            entities_by_id[binding.entity_id] = binding.entity
        for entity in DivineEntity.objects.filter(
            grants_arcane_spell_choice_per_level=True,
            school_id__in=learned_school_ids,
        ).select_related("school", "school__type"):
            entities_by_id.setdefault(entity.id, entity)
        return sorted(entities_by_id.values(), key=lambda entity: (entity.school.name, entity.name))

    def _aspect_entries(self) -> list[CharacterAspect]:
        return list(
            self.character.aspect_entries.select_related("aspect", "source_entity").order_by(
                "aspect__name",
            )
        )

    def _known_spell_entries(self) -> list[CharacterSpell]:
        return list(
            self.character.known_spells.select_related(
                "spell",
                "spell__school",
                "spell__school__type",
                "spell__aspect",
                "spell__spell_attribute",
                "bonus_source",
                "bonus_source__trait",
                "granted_by_entity",
                "granted_by_entity__school",
            ).order_by("spell__school__name", "spell__aspect__name", "spell__grade", "spell__name")
        )

    def _trait_bonus_spell_rows(self):
        return (
            self.character.charactertrait_set.select_related("trait")
            .filter(
                trait__trait_type=Trait.TraitType.ADV,
                trait_level__gt=0,
            )
            .filter(
                models.Q(trait__slug__in=BONUS_SPELL_TRAIT_SLUGS)
                | models.Q(trait__name__in=BONUS_SPELL_TRAIT_NAMES)
            )
        )

    def _has_bonus_spell_trait(self, *, planned_trait_levels: dict[str, int] | None = None) -> bool:
        if planned_trait_levels is not None:
            for slug, level in planned_trait_levels.items():
                if slug in BONUS_SPELL_TRAIT_SLUGS and int(level or 0) > 0:
                    return True
            return False
        return bool(
            self.character.get_engine(refresh=True).resolve_flags().get("bonus_spell_slots_per_magic_level", False)
        )

    def project_spell_learning_slot_summary(
        self,
        *,
        planned_school_levels: dict[int, int] | None = None,
        planned_trait_levels: dict[str, int] | None = None,
    ) -> dict[str, int | bool]:
        if planned_school_levels is None:
            magic_levels = sum(int(entry.level) for entry in self._magic_school_entries())
        else:
            magic_levels = 0
            for entry in self._magic_school_entries():
                magic_levels += max(0, int(planned_school_levels.get(entry.school_id, entry.level)))

        has_bonus_trait = self._has_bonus_spell_trait(planned_trait_levels=planned_trait_levels)
        slots_per_level = SPELL_LEARNING_SLOTS_PER_MAGIC_LEVEL + (
            SPELL_LEARNING_BONUS_SLOTS_PER_MAGIC_LEVEL if has_bonus_trait else 0
        )
        total = max(0, magic_levels * slots_per_level)
        spent = max(0, int(self.character.spent_spell_learning_slots or 0))
        remaining = max(0, total - spent)
        return {
            "magic_levels": magic_levels,
            "slots_per_level": slots_per_level,
            "has_bonus_trait": has_bonus_trait,
            "total": total,
            "spent": spent,
            "remaining": remaining,
        }

    def get_spell_learning_slot_summary(self) -> dict[str, int | bool]:
        summary = self.project_spell_learning_slot_summary()
        source_summaries = self.get_spell_learning_slot_source_summaries()
        total = sum(int(source["total"]) for source in source_summaries.values())
        spent = sum(int(source["spent"]) for source in source_summaries.values())
        summary.update(
            {
                "magic_levels": sum(int(source["level"]) for source in source_summaries.values()),
                "total": total,
                "spent": spent,
                "remaining": max(0, total - spent),
                "sources": source_summaries,
            }
        )
        return summary

    def get_spell_learning_slot_source_summaries(self) -> dict[str, dict[str, object]]:
        has_bonus_trait = self._has_bonus_spell_trait()
        slots_per_level = SPELL_LEARNING_SLOTS_PER_MAGIC_LEVEL + (
            SPELL_LEARNING_BONUS_SLOTS_PER_MAGIC_LEVEL if has_bonus_trait else 0
        )
        sources: dict[str, dict[str, object]] = {}
        for entry in self._arcane_school_entries():
            key = f"school:{entry.school_id}"
            level = max(0, int(entry.level))
            sources[key] = {
                "key": key,
                "kind": "school",
                "id": entry.school_id,
                "name": entry.school.name,
                "symbol": str(getattr(entry.school, "panel_symbol", "") or "").strip() or "*",
                "symbol_image_url": self._image_url(getattr(entry.school, "symbol_image", None)),
                "level": level,
                "slots_per_level": slots_per_level,
                "total": level * slots_per_level,
                "spent": 0,
                "remaining": level * slots_per_level,
            }
        for entry in self._aspect_entries():
            level = max(0, int(entry.level))
            for grade in range(1, level + 1):
                key = _aspect_spell_slot_source_key(entry.aspect_id, grade)
                sources[key] = {
                    "key": key,
                    "kind": "aspect",
                    "id": entry.aspect_id,
                    "grade": grade,
                    "name": f"{entry.aspect.name} Grad {grade}",
                    "symbol": str(entry.aspect.name or "?").strip()[:1] or "*",
                    "symbol_image_url": self._image_url(getattr(entry.aspect, "aspect_image", None)),
                    "level": 1,
                    "slots_per_level": slots_per_level,
                    "total": slots_per_level,
                    "spent": 0,
                    "remaining": slots_per_level,
                }

        slot_spells = CharacterSpell.objects.filter(
            character=self.character,
            source_kind__in=(
                CharacterSpell.SourceKind.ARCANE_FREE,
                CharacterSpell.SourceKind.ARCANE_EXTRA,
                CharacterSpell.SourceKind.ARCANE_BONUS,
                CharacterSpell.SourceKind.DIVINE_EXTRA,
                CharacterSpell.SourceKind.DIVINE_BONUS,
            ),
        ).select_related("spell")
        for entry in slot_spells:
            spell = entry.spell
            if spell.school_id:
                key = f"school:{spell.school_id}"
            elif spell.aspect_id:
                key = _aspect_spell_slot_source_key(spell.aspect_id, spell.grade)
            else:
                continue
            if key not in sources:
                continue
            sources[key]["spent"] = int(sources[key]["spent"]) + 1

        for source in sources.values():
            source["remaining"] = max(0, int(source["total"]) - int(source["spent"]))
        for choice_row in self.get_divine_arcane_spell_choices():
            key = f"divine-arcane:{choice_row['entity_id']}"
            if key not in sources:
                total = max(0, int(choice_row["divine_level"]))
                spent = CharacterSpell.objects.filter(
                    character=self.character,
                    source_kind=CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
                    granted_by_entity_id=int(choice_row["entity_id"]),
                ).count()
                sources[key] = {
                    "key": key,
                    "kind": "divine_arcane",
                    "id": int(choice_row["entity_id"]),
                    "name": f"{choice_row['school_name']} Arkane Gabe",
                    "symbol": str(getattr(choice_row.get("school"), "panel_symbol", "") or "").strip() or "*",
                    "symbol_image_url": str(choice_row.get("symbol_image_url") or ""),
                    "level": int(choice_row["divine_level"]),
                    "slots_per_level": 1,
                    "total": total,
                    "spent": spent,
                    "remaining": 0,
                }
            sources[key]["remaining"] = int(sources[key]["remaining"]) + 1
        return sources

    def get_spell_learning_options(self) -> list[dict[str, object]]:
        known_spell_ids = set(self.character.known_spells.values_list("spell_id", flat=True))
        groups: dict[str, list[dict[str, object]]] = {}
        slot_sources = self.get_spell_learning_slot_source_summaries()

        for school_entry in self._arcane_school_entries():
            slot_source = slot_sources.get(f"school:{school_entry.school_id}", {})
            if int(slot_source.get("remaining", 0) or 0) <= 0:
                continue
            rows: list[dict[str, object]] = []
            spells = (
                Spell.objects.filter(
                    school_id=school_entry.school_id,
                    grade__lte=school_entry.level,
                )
                .exclude(id__in=known_spell_ids)
                .order_by("grade", "name")
            )
            for spell in spells:
                rows.append(
                    {
                        "kind": "magic_spell",
                        "spell_id": spell.id,
                        "name": spell.name,
                        "owner_name": school_entry.school.name,
                        **self._spell_owner_symbol_data(spell),
                        "filter_source_key": f"school:{spell.school_id}",
                        "filter_source_name": spell.school.name,
                        "slot_source_key": str(slot_source.get("key", "")),
                        "slot_source_name": str(slot_source.get("name", school_entry.school.name)),
                        "slot_source_remaining": int(slot_source.get("remaining", 0) or 0),
                        "grade": int(spell.grade),
                        "grade_label": f"{int(spell.grade)} + Stufe" if spell.grade_adds_level else str(int(spell.grade)),
                        "description": (spell.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                        "search_tokens": f"{spell.name.lower()} {school_entry.school.name.lower()} grad {int(spell.grade)} zauber arkane magie",
                    }
                )
            if rows:
                groups[school_entry.school.name] = rows

        character_aspects = self.get_character_aspects()
        aspect_levels = {entry.aspect_id: int(entry.level) for entry in character_aspects}
        bonus_aspect_ids = {entry.aspect_id for entry in character_aspects if entry.is_bonus_aspect}
        divine_rows_by_aspect: dict[str, list[dict[str, object]]] = {}
        spells = (
            Spell.objects.filter(aspect_id__in=aspect_levels.keys())
            .exclude(id__in=known_spell_ids)
            .select_related("aspect")
            .order_by("aspect__name", "grade", "name")
        )
        for spell in spells:
            if int(spell.grade) > int(aspect_levels.get(spell.aspect_id, 0)):
                continue
            if spell.is_base_spell and spell.aspect_id in bonus_aspect_ids:
                continue
            slot_source = slot_sources.get(_aspect_spell_slot_source_key(spell.aspect_id, spell.grade), {})
            if int(slot_source.get("remaining", 0) or 0) <= 0:
                continue
            divine_rows_by_aspect.setdefault(spell.aspect.name, []).append(
                {
                    "kind": "magic_spell",
                    "spell_id": spell.id,
                    "name": spell.name,
                    "owner_name": spell.aspect.name,
                    **self._spell_owner_symbol_data(spell),
                    "filter_source_key": f"aspect:{spell.aspect_id}",
                    "filter_source_name": spell.aspect.name,
                    "slot_source_key": str(slot_source.get("key", "")),
                    "slot_source_name": str(slot_source.get("name", spell.aspect.name)),
                    "slot_source_remaining": int(slot_source.get("remaining", 0) or 0),
                    "grade": int(spell.grade),
                    "grade_label": f"{int(spell.grade)} + Stufe" if spell.grade_adds_level else str(int(spell.grade)),
                    "description": (spell.description or "").replace("\r\n", "\n").replace("\r", "\n"),
                    "search_tokens": f"{spell.name.lower()} {spell.aspect.name.lower()} grad {int(spell.grade)} zauber aspekt klerikal",
                }
            )
        groups.update(divine_rows_by_aspect)
        return [{"name": group_name, "rows": rows} for group_name, rows in groups.items() if rows]

    def get_divine_arcane_spell_choices(self) -> list[dict[str, object]]:
        known_spell_ids = set(self.character.known_spells.values_list("spell_id", flat=True))
        rows: list[dict[str, object]] = []
        arcane_school_ids = [
            school.id
            for school in School.objects.select_related("type").all()
            if self._school_matches_magic_type(school, SCHOOL_ARCANE)
        ]
        for entity in self._divine_arcane_grant_entities():
            divine_level = int(self._school_level_map().get(entity.school_id, 0))
            if divine_level <= 0:
                continue
            existing_rows = (
                CharacterSpell.objects.filter(
                    character=self.character,
                    source_kind=CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
                    granted_by_entity=entity,
                )
                .select_related("spell")
                .order_by("granted_for_level", "spell__name")
            )
            granted_levels = {int(entry.granted_for_level) for entry in existing_rows if entry.granted_for_level}
            symbol_image_url = self._image_url(getattr(entity, "symbol_image", None)) or self._image_url(
                getattr(entity.school, "symbol_image", None)
            )
            for granted_level in range(1, divine_level + 1):
                if granted_level in granted_levels:
                    continue
                options = list(
                    Spell.objects.filter(
                        school_id__in=arcane_school_ids,
                        grade=granted_level,
                    )
                    .exclude(id__in=known_spell_ids)
                    .select_related("school")
                    .order_by("school__name", "name")
                )
                if not options:
                    continue
                rows.append(
                    {
                        "entity_id": entity.id,
                        "entity_name": entity.name,
                        "school_id": entity.school_id,
                        "school": entity.school,
                        "school_name": entity.school.name,
                        "symbol_image_url": symbol_image_url,
                        "divine_level": divine_level,
                        "granted_level": granted_level,
                        "options": options,
                    }
                )
        return rows

    def _ensure_bonus_spell_sources(self) -> list[CharacterSpellSource]:
        source_ids_to_keep: set[int] = set()
        for trait_row in self._trait_bonus_spell_rows():
            source, _created = CharacterSpellSource.objects.update_or_create(
                character=self.character,
                trait=trait_row.trait,
                source_kind=CharacterSpellSource.SourceKind.TRAIT,
                defaults={
                    "label": trait_row.trait.name,
                    "capacity": int(trait_row.trait_level),
                    "is_active": int(trait_row.trait_level) > 0,
                },
            )
            source_ids_to_keep.add(source.id)

        CharacterSpellSource.objects.filter(character=self.character, source_kind=CharacterSpellSource.SourceKind.TRAIT).exclude(
            id__in=source_ids_to_keep
        ).delete()
        return list(
            CharacterSpellSource.objects.filter(character=self.character, is_active=True).select_related("trait").order_by(
                "source_kind",
                "label",
                "id",
            )
        )

    def bonus_spell_sources(self) -> list[dict[str, object]]:
        sources = self._ensure_bonus_spell_sources()
        used_counts = defaultdict(int)
        for entry in self.character.known_spells.exclude(bonus_source__isnull=True).values_list("bonus_source_id", flat=True):
            used_counts[int(entry)] += 1
        rows: list[dict[str, object]] = []
        for source in sources:
            capacity = int(source.capacity)
            used = int(used_counts.get(source.id, 0))
            rows.append(
                {
                    "id": source.id,
                    "label": source.label or (source.trait.name if source.trait_id else source.get_source_kind_display()),
                    "capacity": capacity,
                    "used": used,
                    "remaining": max(0, capacity - used),
                    "source_kind": source.source_kind,
                }
            )
        return rows

    def sync_character_magic(self) -> dict[str, int]:
        """Synchronize automatic divine aspects, base spells, and granted divine spells."""
        summary = {"aspects_created": 0, "aspects_updated": 0, "spells_created": 0, "spells_deleted": 0}
        self._ensure_bonus_spell_sources()

        school_levels = self._school_level_map()
        binding = self._divine_binding()
        granted_aspect_ids: set[int] = set()
        divine_school_level = 0
        if binding is not None:
            divine_school_level = int(school_levels.get(binding.entity.school_id, 0))
            if divine_school_level > 0:
                for link in binding.entity.aspects.filter(is_starting_aspect=True).select_related("aspect"):
                    granted_aspect_ids.add(link.aspect_id)
                    aspect_entry, created = CharacterAspect.objects.get_or_create(
                        character=self.character,
                        aspect=link.aspect,
                        defaults={
                            "level": divine_school_level,
                            "source_entity": binding.entity,
                            "is_bonus_aspect": False,
                        },
                    )
                    changed_fields: list[str] = []
                    if aspect_entry.level != divine_school_level:
                        aspect_entry.level = divine_school_level
                        changed_fields.append("level")
                    if aspect_entry.source_entity_id != binding.entity_id:
                        aspect_entry.source_entity = binding.entity
                        changed_fields.append("source_entity")
                    if aspect_entry.is_bonus_aspect:
                        aspect_entry.is_bonus_aspect = False
                        changed_fields.append("is_bonus_aspect")
                    if changed_fields:
                        aspect_entry.full_clean()
                        aspect_entry.save(update_fields=changed_fields)
                        summary["aspects_updated"] += 1
                    elif created:
                        summary["aspects_created"] += 1

        if binding is None or divine_school_level <= 0:
            removed_granted_aspects = CharacterAspect.objects.filter(
                character=self.character,
                is_bonus_aspect=False,
            ).exclude(source_entity__isnull=True)
            if removed_granted_aspects.exists():
                removed_granted_aspects.delete()
            CharacterSpell.objects.filter(
                character=self.character,
                source_kind=CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
            ).delete()

        CharacterAspect.objects.filter(
            character=self.character,
            is_bonus_aspect=False,
        ).exclude(source_entity__isnull=True).exclude(
            aspect_id__in=granted_aspect_ids,
        ).delete()

        if binding is not None and divine_school_level > 0:
            for aspect_entry in CharacterAspect.objects.filter(character=self.character, is_bonus_aspect=True).select_related("aspect"):
                capped_level = min(int(aspect_entry.level), divine_school_level)
                if capped_level != int(aspect_entry.level):
                    aspect_entry.level = capped_level
                    aspect_entry.full_clean()
                    aspect_entry.save(update_fields=["level"])

        if binding is not None and divine_school_level > 0:
            CharacterSpell.objects.filter(
                character=self.character,
                source_kind=CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
            ).exclude(granted_by_entity_id=binding.entity_id).delete()
            CharacterSpell.objects.filter(
                character=self.character,
                source_kind=CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
                granted_by_entity_id=binding.entity_id,
                granted_for_level__gt=divine_school_level,
            ).delete()

        desired_auto_spells: dict[int, dict[str, object]] = {}
        for school_entry in self._arcane_school_entries():
            for spell in Spell.objects.filter(
                school_id=school_entry.school_id,
                is_base_spell=True,
                grade__lte=school_entry.level,
            ).select_related("school"):
                desired_auto_spells[spell.id] = {
                    "source_kind": CharacterSpell.SourceKind.BASE,
                    "bonus_source": None,
                }

        for aspect_entry in CharacterAspect.objects.filter(character=self.character).select_related("aspect"):
            # Clerical aspects learn their fixed aspect spell progression, not the
            # full aspect spell list. Special exceptions such as Atherus are handled
            # separately through dedicated divine-arcane grant rules.
            spell_queryset = Spell.objects.filter(
                aspect_id=aspect_entry.aspect_id,
                grade__lte=aspect_entry.level,
                is_base_spell=True,
            )
            if aspect_entry.is_bonus_aspect:
                source_kind = CharacterSpell.SourceKind.BASE
            else:
                source_kind = CharacterSpell.SourceKind.DIVINE_GRANTED
            for spell in spell_queryset.select_related("aspect"):
                desired_auto_spells[spell.id] = {
                    "source_kind": source_kind,
                    "bonus_source": None,
                }

        if self._arcane_school_entries() or CharacterAspect.objects.filter(character=self.character).exists():
            for spell in Spell.objects.filter(is_base_spell=True, school__isnull=True, aspect__isnull=True):
                desired_auto_spells.setdefault(spell.id, {
                    "source_kind": CharacterSpell.SourceKind.BASE,
                    "bonus_source": None,
                })

        existing_auto_entries = list(
            CharacterSpell.objects.filter(
                character=self.character,
                source_kind__in=(
                    CharacterSpell.SourceKind.BASE,
                    CharacterSpell.SourceKind.DIVINE_GRANTED,
                ),
            ).select_related("spell")
        )
        existing_auto_by_spell_id = {entry.spell_id: entry for entry in existing_auto_entries}

        for spell_id, defaults in desired_auto_spells.items():
            if spell_id in existing_auto_by_spell_id:
                entry = existing_auto_by_spell_id[spell_id]
                if entry.source_kind != defaults["source_kind"]:
                    entry.source_kind = defaults["source_kind"]
                    entry.save(update_fields=["source_kind"])
                continue
            CharacterSpell.objects.create(
                character=self.character,
                spell_id=spell_id,
                source_kind=defaults["source_kind"],
                bonus_source=defaults["bonus_source"],
            )
            summary["spells_created"] += 1

        removable_ids = [
            entry.id for entry in existing_auto_entries if entry.spell_id not in desired_auto_spells
        ]
        if removable_ids:
            CharacterSpell.objects.filter(id__in=removable_ids).delete()
            summary["spells_deleted"] += len(removable_ids)
        return summary

    def get_known_spells(self) -> list[CharacterSpell]:
        return self._known_spell_entries()

    def get_character_aspects(self) -> list[CharacterAspect]:
        return self._aspect_entries()

    def get_available_arcane_spell_choices(self, school) -> dict[str, object]:
        school_id = school.id if hasattr(school, "id") else int(school)
        school_entry = next((entry for entry in self._arcane_school_entries() if entry.school_id == school_id), None)
        if school_entry is None:
            return {"school_id": school_id, "remaining": 0, "options": []}
        used_free_count = self.character.known_spells.filter(
            spell__school_id=school_id,
            source_kind=CharacterSpell.SourceKind.ARCANE_FREE,
        ).count()
        capacity = max(0, int(school_entry.level) * 2)
        remaining = max(0, capacity - used_free_count)
        known_spell_ids = set(self.character.known_spells.values_list("spell_id", flat=True))
        options = list(
            Spell.objects.filter(
                school_id=school_id,
                grade__lte=school_entry.level,
            )
            .exclude(id__in=known_spell_ids)
            .order_by("grade", "name")
        )
        return {
            "school_id": school_id,
            "school_name": school_entry.school.name,
            "school_level": int(school_entry.level),
            "capacity": capacity,
            "used": used_free_count,
            "remaining": remaining,
            "options": options,
        }

    def get_available_bonus_spells(self) -> list[dict[str, object]]:
        known_spell_ids = set(self.character.known_spells.values_list("spell_id", flat=True))
        eligible_arcane = Spell.objects.filter(
            school_id__in=[entry.school_id for entry in self._arcane_school_entries()],
        )
        school_levels = self._school_level_map()
        arcane_options = [
            spell
            for spell in eligible_arcane.select_related("school").order_by("school__name", "grade", "name")
            if spell.id not in known_spell_ids and spell.grade <= int(school_levels.get(spell.school_id, 0))
        ]

        aspect_levels = {entry.aspect_id: int(entry.level) for entry in self._aspect_entries()}
        divine_options = [
            spell
            for spell in Spell.objects.filter(aspect_id__in=aspect_levels.keys()).select_related("aspect").order_by(
                "aspect__name",
                "grade",
                "name",
            )
            if spell.id not in known_spell_ids and spell.grade <= int(aspect_levels.get(spell.aspect_id, 0))
        ]

        rows: list[dict[str, object]] = []
        for source in self.bonus_spell_sources():
            if int(source["remaining"]) <= 0:
                continue
            rows.append(
                {
                    "source": source,
                    "options": [*arcane_options, *divine_options],
                }
            )
        return rows

    def get_divine_magic_summary(self) -> dict[str, object]:
        binding = self._divine_binding()
        aspect_rows = []
        for entry in self._aspect_entries():
            aspect_rows.append(
                {
                    "aspect_id": entry.aspect_id,
                    "name": entry.aspect.name,
                    "level": int(entry.level),
                    "is_bonus_aspect": bool(entry.is_bonus_aspect),
                    "source_entity_name": entry.source_entity.name if entry.source_entity_id else "",
                }
            )
        return {
            "has_divine_magic": binding is not None,
            "entity_name": binding.entity.name if binding else "",
            "entity_kind": binding.entity.get_entity_kind_display() if binding else "",
            "school_name": binding.entity.school.name if binding else "",
            "school_level": self.character.engine.school_level(binding.entity.school_id) if binding else 0,
            "school_level_label": _to_roman(self.character.engine.school_level(binding.entity.school_id)) if binding else "",
            "aspects": aspect_rows,
        }

    def get_available_bonus_aspects(self) -> dict[str, object]:
        binding = self._divine_binding()
        if binding is None:
            return {"school_level": 0, "options": []}
        school_level = int(self.character.engine.school_level(binding.entity.school_id))
        if school_level <= 0:
            return {"school_level": 0, "options": []}
        known_aspect_ids = set(self.character.aspect_entries.values_list("aspect_id", flat=True))
        opposed_ids = {
            entry.aspect.opposite_id
            for entry in self.character.aspect_entries.select_related("aspect")
            if entry.aspect.opposite_id
        }
        options = list(
            Aspect.objects.exclude(id__in=known_aspect_ids)
            .exclude(id__in=opposed_ids)
            .order_by("name")
        )
        return {"school_level": school_level, "options": options}

    def normalize_current_arcane_power(
        self,
        *,
        previous_max: int | None = None,
        persist: bool = True,
    ) -> dict[str, int | bool]:
        """Shift current KP alongside max changes and never allow values above max."""
        current_max = max(0, int(self.character.get_engine(refresh=True).calculate_arcane_power()))
        stored_current = self.character.current_arcane_power

        if stored_current is None:
            normalized_current = current_max
        else:
            normalized_current = max(0, int(stored_current))
            if previous_max is not None:
                max_delta = current_max - max(0, int(previous_max))
                normalized_current += max_delta
            normalized_current = min(normalized_current, current_max)

        changed = stored_current is None or int(stored_current) != normalized_current
        self.character.current_arcane_power = normalized_current
        if persist and changed:
            self.character.save(update_fields=["current_arcane_power"])

        return {
            "current_arcane_power": normalized_current,
            "current_arcane_power_max": current_max,
            "changed": changed,
        }

    def can_cast_spell(self, spell) -> dict[str, object]:
        spell_obj = spell if isinstance(spell, Spell) else Spell.objects.select_related("school", "aspect").filter(pk=spell).first()
        if spell_obj is None:
            return {"ok": False, "error": "spell_not_found", "message": "Zauber nicht gefunden."}
        if not CharacterSpell.objects.filter(character=self.character, spell=spell_obj).exists():
            return {"ok": False, "error": "unknown_spell", "message": "Der Charakter kennt diesen Zauber nicht."}
        current_arcane_power = int(self.normalize_current_arcane_power()["current_arcane_power"])
        if current_arcane_power < int(spell_obj.kp_cost):
            return {"ok": False, "error": "not_enough_kp", "message": "Nicht genug KP fuer diesen Zauber."}
        return {"ok": True, "spell": spell_obj, "current_arcane_power": current_arcane_power}

    def cast_spell(self, spell) -> dict[str, object]:
        spell_id = spell.id if isinstance(spell, Spell) else int(spell)
        with transaction.atomic():
            character = Character.objects.select_for_update().get(pk=self.character.pk)
            engine = character.get_magic_engine(refresh=True)
            result = engine.can_cast_spell(spell_id)
            if not result["ok"]:
                return result
            spell_obj = result["spell"]
            normalized_arcane_power = engine.normalize_current_arcane_power(persist=False)
            calculated_arcane_power = int(normalized_arcane_power["current_arcane_power_max"])
            current_arcane_power = int(normalized_arcane_power["current_arcane_power"])
            spent_kp = int(spell_obj.kp_cost)
            projected_arcane_power = current_arcane_power - spent_kp
            if projected_arcane_power < 0:
                return {"ok": False, "error": "not_enough_kp", "message": "Nicht genug KP fuer diesen Zauber."}
            current_arcane_power = projected_arcane_power
            character.current_arcane_power = current_arcane_power
            character.save(update_fields=["current_arcane_power"])
            display_arcane_power_max = max(calculated_arcane_power, current_arcane_power)
            return {
                "ok": True,
                "spell_id": spell_obj.id,
                "spell_name": spell_obj.name,
                "current_arcane_power": current_arcane_power,
                "current_arcane_power_max": display_arcane_power_max,
                "spent_kp": spent_kp,
            }

    def get_spell_panel_data(self) -> dict[str, object]:
        known_entries = self.get_known_spells()
        school_entries = self._school_entries()
        arcane_school_levels = {
            entry.school.name: int(entry.level)
            for entry in school_entries
            if self._school_matches_magic_type(entry, SCHOOL_ARCANE)
        }
        school_level_map: dict[int, int] = {entry.school_id: int(entry.level) for entry in school_entries}
        aspect_level_map: dict[int, int] = {
            entry.aspect_id: int(entry.level) for entry in self._aspect_entries()
        }
        grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for entry in known_entries:
            spell = entry.spell
            owner_symbol_data = self._spell_owner_symbol_data(spell)
            if entry.source_kind == CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED and entry.granted_by_entity_id:
                group_kind = "divine"
                group_name = entry.granted_by_entity.name
                owner_name = spell.school.name
            elif spell.school_id:
                group_kind = "arcane"
                group_name = spell.school.name
                owner_name = spell.school.name
            elif spell.aspect_id:
                group_kind = "divine"
                group_name = spell.aspect.name
                owner_name = spell.aspect.name
            else:
                group_kind = "base"
                group_name = "Basiszauber"
                owner_name = "Basiszauber"
            grouped_rows[(group_kind, group_name)].append(
                {
                    "_spell_obj": spell,
                    "spell_id": spell.id,
                    "name": spell.name,
                    "owner_name": owner_name,
                    "level": int(spell.grade),
                    "effective_level": _effective_spell_level(
                        entry,
                        school_levels=school_level_map,
                        aspect_levels=aspect_level_map,
                    ),
                    "kp_cost": int(spell.kp_cost),
                    "cost_display": (
                        f"{int(spell.kp_cost)} KP{str(spell.kp_cost_label or '').strip()}"
                        + (
                            f" oder {int(spell.ep_cost)} EP{str(spell.ep_cost_label or '').strip()}"
                            if spell.ep_cost
                            else ""
                        )
                        + (
                            f" + {int(spell.extra_cost_value)} "
                            + ("Wundgrad" if int(spell.extra_cost_value) == 1 else "Wundgrade")
                            if spell.extra_cost_type == getattr(spell.ExtraCostType, "WOUND_GRADE", "") and spell.extra_cost_value
                            else ""
                        )
                    ),
                    "source_kind": entry.source_kind,
                    "is_base_spell": bool(spell.is_base_spell),
                    "is_bonus_spell": entry.source_kind in {
                        CharacterSpell.SourceKind.ARCANE_BONUS,
                        CharacterSpell.SourceKind.DIVINE_BONUS,
                        CharacterSpell.SourceKind.ARCANE_EXTRA,
                        CharacterSpell.SourceKind.DIVINE_EXTRA,
                    },
                    "source_label": self._source_label(entry),
                    "badge_label": (spell.panel_badge_label or "").strip(),
                    "owner_symbol": owner_symbol_data["owner_symbol"],
                    "owner_symbol_image_url": owner_symbol_data["owner_symbol_image_url"],
                    "owner_accent": _spell_owner_accent(owner_name),
                    "description": spell.description or "",
                    "tooltip_text": _build_spell_tooltip(entry, school_levels=school_level_map, aspect_levels=aspect_level_map),
                    "castable_kind": "spell",
                }
            )
        for rows in grouped_rows.values():
            for row in rows:
                spell = row["_spell_obj"]
                row["grade_label"] = (
                    str(int(row["level"]) + int(row["effective_level"]))
                    if spell.grade_adds_level
                    else str(int(row["level"]))
                )
        groups = [
            {
                "kind": group_kind,
                "name": group_name,
                "symbol": self._spell_group_symbol(group_kind, rows[0]["_spell_obj"]) if rows else "",
                "symbol_image_url": self._spell_group_symbol_image_url(group_kind, rows[0]["_spell_obj"]) if rows else "",
                "rank_label": (
                    _to_roman(arcane_school_levels.get(group_name, 0))
                    if group_kind == "arcane"
                    else ""
                ),
                "rows": sorted(
                    [{key: value for key, value in row.items() if key != "_spell_obj"} for row in rows],
                    key=lambda row: (row["level"], row["name"]),
                ),
            }
            for (group_kind, group_name), rows in sorted(
                grouped_rows.items(),
                key=lambda item: _spell_group_sort_key(item[0][0], item[0][1]),
            )
        ]
        arcane_filter_groups = [
            {
                "name": group["name"],
                "symbol": group["symbol"],
                "symbol_image_url": group["symbol_image_url"],
            }
            for group in groups
            if group["kind"] == "arcane" and group["rows"]
        ]
        has_entries = any(group["rows"] for group in groups)
        return {
            "spell_panel_enabled": has_entries,
            "spell_and_lessons_panel_enabled": has_entries,
            "has_castable_entries": has_entries,
            "groups": groups,
            "arcane_filter_groups": arcane_filter_groups if len(arcane_filter_groups) > 1 else [],
            "arcane_schools": [
                {
                    "name": entry.school.name,
                    "level": int(entry.level),
                    "level_label": _to_roman(int(entry.level)),
                }
                for entry in self._arcane_school_entries()
            ],
            "divine_summary": self.get_divine_magic_summary(),
        }

    def _source_label(self, entry: CharacterSpell) -> str:
        return self._source_label_static(entry)

    @staticmethod
    def _source_label_static(entry: CharacterSpell) -> str:
        """Static helper so spell tooltips can reuse source labels without an engine instance."""
        if entry.source_kind == CharacterSpell.SourceKind.BASE:
            return "Basis"
        if entry.source_kind == CharacterSpell.SourceKind.ARCANE_FREE:
            return "Zauber"
        if entry.source_kind == CharacterSpell.SourceKind.ARCANE_EXTRA:
            return "Zusatzzauber"
        if entry.source_kind == CharacterSpell.SourceKind.ARCANE_BONUS:
            return entry.bonus_source.label if entry.bonus_source_id else "Bonuszauber"
        if entry.source_kind == CharacterSpell.SourceKind.DIVINE_GRANTED:
            return "Automatisch"
        if entry.source_kind == CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED:
            if entry.granted_by_entity_id:
                return f"{entry.granted_by_entity.name}-Gabe"
            return "Goettliche Arkangabe"
        if entry.source_kind == CharacterSpell.SourceKind.DIVINE_EXTRA:
            return "Zusatzzauber"
        if entry.source_kind == CharacterSpell.SourceKind.DIVINE_BONUS:
            return entry.bonus_source.label if entry.bonus_source_id else "Bonuszauber"
        return "Manuell"
