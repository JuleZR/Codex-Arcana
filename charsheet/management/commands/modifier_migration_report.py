"""Generate inventory and migration reports for legacy modifiers."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from charsheet.constants import ARCANE_POWER, DEFENSE_GW, DEFENSE_RS, DEFENSE_SR, DEFENSE_VW, INITIATIVE
from charsheet.modifiers import LegacyModifierMigrationService, ModifierResolutionMode
from charsheet.models import Character


class Command(BaseCommand):
    """Emit a structured migration report for legacy modifiers."""

    help = "Inventory legacy modifiers, map them into the new system, and optionally compare new-engine results against legacy debug arithmetic."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
        parser.add_argument("--output", default="")
        parser.add_argument(
            "--character-id",
            action="append",
            dest="character_ids",
            default=[],
            help="Optional character id to compare against the internal legacy debug baseline. Can be supplied multiple times.",
        )

    def handle(self, *args, **options):
        report = self._build_report(character_ids=options["character_ids"])
        if options["format"] == "json":
            rendered = json.dumps(report, ensure_ascii=False, indent=2)
        else:
            rendered = self._render_markdown(report)

        output_path = str(options["output"] or "").strip()
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Modifier migration report written to {target}"))
            return

        self.stdout.write(rendered)

    def _build_report(self, *, character_ids: list[str]) -> dict:
        service = LegacyModifierMigrationService()
        inventory_rows = service.inventory_rows()
        migration_rows = service.migration_records()

        report = {
            "inventory": {
                "count": len(inventory_rows),
                "by_target_kind": self._count_rows(inventory_rows, key="target_kind"),
                "by_source_model": self._count_rows(inventory_rows, key="source_model"),
                "used_target_combinations": service.summarize_combinations(),
            },
            "relationships": [
                {
                    "direction": row.direction,
                    "model_name": row.model_name,
                    "field_name": row.field_name,
                    "relation_kind": row.relation_kind,
                    "related_model_name": row.related_model_name,
                }
                for row in service.relationship_inventory()
            ],
            "code_readers": [
                {"path": path, "meaning": meaning}
                for path, meaning in service.code_reader_inventory()
            ],
            "mapping_table": [
                {
                    "legacy_modifier_id": row.legacy_modifier_id,
                    "legacy_model_name": row.legacy_model_name,
                    "previous_meaning": row.previous_meaning,
                    "new_modifier_type": row.new_modifier_type,
                    "new_target_domain": row.new_target_domain,
                    "migration_strategy": row.migration_strategy,
                    "migration_confidence": row.migration_confidence,
                    "requires_manual_review": row.requires_manual_review,
                    "migration_note": row.migration_note,
                    "risk": row.risk,
                }
                for row in migration_rows
            ],
            "character_comparisons": [],
        }

        for raw_character_id in character_ids:
            try:
                character_id = int(raw_character_id)
            except (TypeError, ValueError) as exc:
                raise CommandError(f"Invalid character id: {raw_character_id}") from exc
            report["character_comparisons"].append(self._build_character_comparison(character_id))
        return report

    def _build_character_comparison(self, character_id: int) -> dict:
        try:
            character = Character.objects.get(pk=character_id)
        except Character.DoesNotExist as exc:
            raise CommandError(f"Character {character_id} does not exist.") from exc

        new_engine = character.get_engine(refresh=True, modifier_resolution_mode=ModifierResolutionMode.NEW_ONLY)
        compare_engine = character.get_engine(refresh=True, modifier_resolution_mode=ModifierResolutionMode.COMPARE)
        compare_engine.modifier_engine.reset_comparison_log()

        stat_keys = [INITIATIVE, ARCANE_POWER, DEFENSE_VW, DEFENSE_GW, DEFENSE_SR, DEFENSE_RS]
        damage_stat_keys = sorted(
            {
                row["target_identifier"]
                for row in LegacyModifierMigrationService().summarize_combinations()
                if str(row["target_identifier"]).startswith("dmg_")
            }
        )
        direct_stat_keys = stat_keys + damage_stat_keys

        stat_compare_rows = []
        for stat_key in direct_stat_keys:
            legacy_value = compare_engine.debug_legacy_modifier_total_for_stat(stat_key)
            new_value = new_engine.modifier_total_for_stat(stat_key)
            compare_engine.modifier_total_for_stat(stat_key)
            stat_compare_rows.append(
                {
                    "stat_key": stat_key,
                    "legacy_value": legacy_value,
                    "new_value": new_value,
                    "matches": legacy_value == new_value,
                }
            )

        skill_compare_rows = []
        for skill_slug in sorted(compare_engine.skills().keys()):
            legacy_value = compare_engine.debug_legacy_skill_total(skill_slug)
            new_value = new_engine.skill_total(skill_slug)
            compare_engine.skill_total(skill_slug)
            skill_compare_rows.append(
                {
                    "skill_slug": skill_slug,
                    "legacy_value": legacy_value,
                    "new_value": new_value,
                    "matches": legacy_value == new_value,
                }
            )

        derived_compare_rows = [
            {
                "key": "initiative",
                "legacy_value": compare_engine.debug_legacy_calculate_initiative(),
                "new_value": new_engine.calculate_initiative(),
                "matches": compare_engine.debug_legacy_calculate_initiative() == new_engine.calculate_initiative(),
            },
            {
                "key": "arcane_power",
                "legacy_value": compare_engine.debug_legacy_calculate_arcane_power(),
                "new_value": new_engine.calculate_arcane_power(),
                "matches": compare_engine.debug_legacy_calculate_arcane_power() == new_engine.calculate_arcane_power(),
            },
            {
                "key": "vw",
                "legacy_value": compare_engine.debug_legacy_vw(),
                "new_value": new_engine.vw(),
                "matches": compare_engine.debug_legacy_vw() == new_engine.vw(),
            },
            {
                "key": "gw",
                "legacy_value": compare_engine.debug_legacy_gw(),
                "new_value": new_engine.gw(),
                "matches": compare_engine.debug_legacy_gw() == new_engine.gw(),
            },
            {
                "key": "sr",
                "legacy_value": compare_engine.debug_legacy_sr(),
                "new_value": new_engine.sr(),
                "matches": compare_engine.debug_legacy_sr() == new_engine.sr(),
            },
            {
                "key": "rs",
                "legacy_value": compare_engine.debug_legacy_get_grs(),
                "new_value": new_engine.get_grs(),
                "matches": compare_engine.debug_legacy_get_grs() == new_engine.get_grs(),
            },
        ]

        return {
            "character_id": character.id,
            "character_name": character.name,
            "modifier_mode_default": ModifierResolutionMode.NEW_ONLY,
            "direct_stat_compare": stat_compare_rows,
            "skill_compare": skill_compare_rows,
            "derived_output_compare": derived_compare_rows,
            "compare_mode_log": [
                {
                    "target_domain": row.target_domain,
                    "target_key": row.target_key,
                    "legacy_value": row.legacy_value,
                    "new_value": row.new_value,
                    "matches": row.matches,
                    "classification": row.classification,
                    "notes": list(row.notes),
                }
                for row in compare_engine.modifier_resolution_comparisons()
            ],
            "review_required_records": [
                {
                    "legacy_modifier_id": row.legacy_modifier_id,
                    "new_target_domain": row.new_target_domain,
                    "migration_note": row.migration_note,
                }
                for row in compare_engine.modifier_engine.review_required_records()
            ],
        }

    def _count_rows(self, rows, *, key: str) -> list[dict]:
        grouped: dict[str, int] = {}
        for row in rows:
            value = getattr(row, key)
            grouped[str(value)] = grouped.get(str(value), 0) + 1
        return [{"key": group_key, "count": count} for group_key, count in sorted(grouped.items())]

    def _render_markdown(self, report: dict) -> str:
        lines: list[str] = []
        inventory = report["inventory"]
        lines.append("# Legacy Modifier Migration Report")
        lines.append("")
        lines.append("## Inventory")
        lines.append("")
        lines.append(f"- Legacy modifier rows: {inventory['count']}")
        lines.append("- Target kinds:")
        for row in inventory["by_target_kind"]:
            lines.append(f"  - `{row['key']}`: {row['count']}")
        lines.append("- Source models:")
        for row in inventory["by_source_model"]:
            lines.append(f"  - `{row['key']}`: {row['count']}")
        lines.append("")
        lines.append("## Relationships")
        lines.append("")
        for row in report["relationships"]:
            lines.append(
                f"- `{row['direction']}` `{row['model_name']}.{row['field_name']}`"
                f" -> `{row['related_model_name']}` ({row['relation_kind']})"
            )
        lines.append("")
        lines.append("## Code Readers")
        lines.append("")
        for row in report["code_readers"]:
            lines.append(f"- `{row['path']}`: {row['meaning']}")
        lines.append("")
        lines.append("## Used Target Combinations")
        lines.append("")
        lines.append("| target_kind | target_identifier | mode | scale_source | count |")
        lines.append("| --- | --- | --- | --- | ---: |")
        for row in inventory["used_target_combinations"]:
            lines.append(
                f"| `{row['target_kind']}` | `{row['target_identifier']}` | `{row['mode']}` | "
                f"`{row['scale_source']}` | {row['count']} |"
            )
        lines.append("")
        lines.append("## Mapping Table")
        lines.append("")
        lines.append(
            "| legacy_id | previous meaning | new type | target domain | strategy | confidence | review | risk | note |"
        )
        lines.append("| ---: | --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in report["mapping_table"]:
            lines.append(
                f"| {row['legacy_modifier_id']} | {row['previous_meaning']} | `{row['new_modifier_type']}` | "
                f"`{row['new_target_domain']}` | `{row['migration_strategy']}` | `{row['migration_confidence']}` | "
                f"`{row['requires_manual_review']}` | `{row['risk']}` | {row['migration_note']} |"
            )

        for character_report in report["character_comparisons"]:
            lines.append("")
            lines.append(f"## Character Compare: {character_report['character_name']} ({character_report['character_id']})")
            lines.append("")
            lines.append("### Derived Outputs")
            lines.append("")
            lines.append("| key | legacy | new | matches |")
            lines.append("| --- | ---: | ---: | --- |")
            for row in character_report["derived_output_compare"]:
                lines.append(f"| `{row['key']}` | {row['legacy_value']} | {row['new_value']} | `{row['matches']}` |")
            lines.append("")
            lines.append("### Debug Compare Log")
            lines.append("")
            lines.append("| domain | key | legacy | new | classification | matches |")
            lines.append("| --- | --- | ---: | ---: | --- | --- |")
            for row in character_report["compare_mode_log"]:
                lines.append(
                    f"| `{row['target_domain']}` | `{row['target_key']}` | {row['legacy_value']} | "
                    f"{row['new_value']} | `{row['classification']}` | `{row['matches']}` |"
                )
            if character_report["review_required_records"]:
                lines.append("")
                lines.append("### Review Required")
                lines.append("")
                for row in character_report["review_required_records"]:
                    lines.append(
                        f"- Legacy modifier `{row['legacy_modifier_id']}` on `{row['new_target_domain']}`: {row['migration_note']}"
                    )
        lines.append("")
        return "\n".join(lines)
