"""Central magic rules for spells, aspects, divine entities, and casting."""

from __future__ import annotations

from collections import defaultdict

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


def _get_character_school_level(entry: CharacterSpell) -> int:
    """Return the character's current level in the spell's school or aspect, or 0."""
    if not entry.character_id:
        return 0
    spell = entry.spell
    if spell.school_id:
        cs = CharacterSchool.objects.filter(character_id=entry.character_id, school_id=spell.school_id).first()
        return int(cs.level) if cs else 0
    if spell.aspect_id:
        ca = CharacterAspect.objects.filter(character_id=entry.character_id, aspect_id=spell.aspect_id).first()
        return int(ca.level) if ca else 0
    return 0


def _build_spell_tooltip(entry: CharacterSpell) -> str:
    """Return a structured tooltip with spell facts followed by the description."""
    spell = entry.spell
    attribute_label = "-"
    if spell.spell_attribute_id:
        raw_attribute_label = spell.spell_attribute.short_name or spell.spell_attribute.name
        attribute_label = str(raw_attribute_label).title()

    if spell.mw is None:
        mw_label = "-"
    elif spell.grade_adds_school_level:
        mw_label = f"{int(spell.mw)} + Stufe"
    else:
        mw_label = str(int(spell.mw))
    resistance_label = str(spell.resistance_value or "-").strip() or "-"

    school_level = _get_character_school_level(entry)

    rows: list[tuple[str, object]] = [
        ("Eigenschaft/Grad", f"{attribute_label}/{int(spell.grade)}"),
        ("MW/Widerstandswert", f"{mw_label}/{resistance_label}"),
        ("Kosten", f"{int(spell.kp_cost)} KP"),
    ]
    _PLURAL = {
        "Aktion": "Aktionen",
        "Minute": "Minuten",
        "Stunde": "Stunden",
        "Runde": "Runden",
    }

    def _unit_label(unit_display: str, number: int) -> str:
        if number != 1 and unit_display in _PLURAL:
            return _PLURAL[unit_display]
        return unit_display

    if spell.cast_time_number is not None and spell.cast_time_unit:
        unit = spell.get_cast_time_unit_display()
        label = _unit_label(unit, spell.cast_time_number)
        rows.append(("Zeitaufwand", f"{spell.cast_time_number} {label}"))
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

    if spell.duration_unit in ("sofort", "permanent", "Szene"):
        rows.append(("Wirkungsdauer", spell.get_duration_unit_display()))
    elif spell.duration_number is not None and spell.duration_unit:
        unit = spell.get_duration_unit_display()
        if spell.duration_per_grade:
            total = spell.duration_number * school_level
            dur_label = _unit_label(unit, total)
            note = f"[[SUB:Stufe {school_level} × {spell.duration_number} {unit}]]"
            rows.append(("Wirkungsdauer", f"{total} {dur_label} {note}"))
        else:
            rows.append(("Wirkungsdauer", f"{spell.duration_number} {_unit_label(unit, spell.duration_number)}"))
    elif spell.duration_text:
        rows.append(("Wirkungsdauer", spell.duration_text))

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

    def __init__(self, character: Character) -> None:
        self.character = character

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
        return [entry for entry in self._school_entries() if entry.school.type.slug == SCHOOL_ARCANE]

    def _divine_school_entries(self) -> list[CharacterSchool]:
        return [entry for entry in self._school_entries() if entry.school.type.slug == SCHOOL_DIVINE]

    def _divine_binding(self) -> CharacterDivineEntity | None:
        return (
            CharacterDivineEntity.objects.filter(character=self.character)
            .select_related("entity", "entity__school", "entity__school__type")
            .first()
        )

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
            spell_queryset = Spell.objects.filter(
                aspect_id=aspect_entry.aspect_id,
                grade__lte=aspect_entry.level,
            )
            if aspect_entry.is_bonus_aspect:
                spell_queryset = spell_queryset.filter(is_base_spell=True)
                source_kind = CharacterSpell.SourceKind.BASE
            else:
                source_kind = CharacterSpell.SourceKind.DIVINE_GRANTED
            for spell in spell_queryset.select_related("aspect"):
                desired_auto_spells[spell.id] = {
                    "source_kind": source_kind,
                    "bonus_source": None,
                }

        existing_auto_entries = list(
            CharacterSpell.objects.filter(
                character=self.character,
                source_kind__in=(
                    CharacterSpell.SourceKind.BASE,
                    CharacterSpell.SourceKind.DIVINE_GRANTED,
                ),
            ).exclude(
                # Universal base spells (no school, no aspect) are user-chosen and must not be
                # managed by the automatic sync — only school- and aspect-bound entries are.
                spell__school__isnull=True,
                spell__aspect__isnull=True,
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

    def can_cast_spell(self, spell) -> dict[str, object]:
        spell_obj = spell if isinstance(spell, Spell) else Spell.objects.select_related("school", "aspect").filter(pk=spell).first()
        if spell_obj is None:
            return {"ok": False, "error": "spell_not_found", "message": "Zauber nicht gefunden."}
        if not CharacterSpell.objects.filter(character=self.character, spell=spell_obj).exists():
            return {"ok": False, "error": "unknown_spell", "message": "Der Charakter kennt diesen Zauber nicht."}
        current_arcane_power = self.character.current_arcane_power
        current_arcane_power = int(
            current_arcane_power if current_arcane_power is not None else self.character.engine.calculate_arcane_power()
        )
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
            calculated_arcane_power = max(0, int(character.engine.calculate_arcane_power()))
            current_arcane_power = character.current_arcane_power
            if current_arcane_power is None:
                current_arcane_power = calculated_arcane_power
            current_arcane_power = max(0, int(current_arcane_power))
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
        arcane_school_levels = {
            entry.school.name: int(entry.level)
            for entry in self._arcane_school_entries()
        }
        grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for entry in known_entries:
            spell = entry.spell
            if spell.school_id:
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
                    "kp_cost": int(spell.kp_cost),
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
                    "description": spell.description or "",
                    "tooltip_text": _build_spell_tooltip(entry),
                    "castable_kind": "spell",
                }
            )
        groups = [
            {
                "kind": group_kind,
                "name": group_name,
                "symbol": self._spell_group_symbol(group_kind, rows[0]["_spell_obj"]) if rows else "",
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
        has_entries = any(group["rows"] for group in groups)
        return {
            "spell_panel_enabled": has_entries,
            "spell_and_lessons_panel_enabled": has_entries,
            "has_castable_entries": has_entries,
            "groups": groups,
            "arcane_schools": [
                {
                    "name": entry.school.name,
                    "level": int(entry.level),
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
        if entry.source_kind == CharacterSpell.SourceKind.DIVINE_EXTRA:
            return "Zusatzzauber"
        if entry.source_kind == CharacterSpell.SourceKind.DIVINE_BONUS:
            return entry.bonus_source.label if entry.bonus_source_id else "Bonuszauber"
        return "Manuell"
