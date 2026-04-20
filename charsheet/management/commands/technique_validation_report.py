"""Report invalid technique rows that violate current model validation rules."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.management.base import BaseCommand

from charsheet.models import Technique


class Command(BaseCommand):
    """Inspect persisted techniques and emit a readable validation report."""

    help = (
        "Validate all persisted techniques against the current model rules and "
        "report rows that fail validation."
    )

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        report = self._build_report()
        rendered = (
            json.dumps(report, ensure_ascii=False, indent=2)
            if options["format"] == "json"
            else self._render_text(report)
        )

        output_path = str(options["output"] or "").strip()
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Technique validation report written to {target}"))
            return

        self.stdout.write(rendered)

    def _build_report(self) -> dict:
        invalid_rows = []
        queryset = Technique.objects.select_related("school", "path").order_by("school__name", "level", "name", "id")
        for technique in queryset:
            try:
                technique.full_clean()
            except ValidationError as exc:
                invalid_rows.append(
                    {
                        "id": technique.id,
                        "name": technique.name,
                        "school": technique.school.name if technique.school_id else "",
                        "level": technique.level,
                        "technique_type": technique.technique_type,
                        "support_level": technique.support_level,
                        "action_type": technique.action_type,
                        "usage_type": technique.usage_type,
                        "activation_cost": technique.activation_cost,
                        "activation_cost_resource": technique.activation_cost_resource,
                        "errors": self._normalize_errors(exc),
                    }
                )

        return {
            "checked_count": queryset.count(),
            "invalid_count": len(invalid_rows),
            "invalid_techniques": invalid_rows,
        }

    def _normalize_errors(self, exc: ValidationError) -> dict[str, list[str]]:
        """Convert ValidationError payloads into a stable JSON/text-friendly mapping."""
        if hasattr(exc, "message_dict"):
            normalized = {}
            for key, messages in exc.message_dict.items():
                field_key = "__all__" if key == NON_FIELD_ERRORS else str(key)
                normalized[field_key] = [str(message) for message in messages]
            return normalized
        return {"__all__": [str(message) for message in exc.messages]}

    def _render_text(self, report: dict) -> str:
        """Render a compact terminal-friendly summary."""
        lines = [
            f"Checked techniques: {report['checked_count']}",
            f"Invalid techniques: {report['invalid_count']}",
        ]
        for row in report["invalid_techniques"]:
            school_label = row["school"] or "No School"
            level_label = f"L{row['level']}" if row["level"] is not None else "L?"
            lines.append(f"- #{row['id']} {school_label} {level_label}: {row['name']}")
            for field_name, messages in row["errors"].items():
                for message in messages:
                    lines.append(f"  [{field_name}] {message}")
        return "\n".join(lines)
