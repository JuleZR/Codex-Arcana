"""Helpers for packing visible summaries plus text-only magic effects."""

from __future__ import annotations

import base64
import json


TEXT_TARGET_KIND = "text"
_TEXT_EFFECT_MARKER = "[[CAFX1:"
_TEXT_EFFECT_SUFFIX = "]]"


def _decode_base64_payload(raw_value: str) -> str:
    padding = "=" * (-len(raw_value) % 4)
    return base64.urlsafe_b64decode(f"{raw_value}{padding}".encode("ascii")).decode("utf-8")


def unpack_magic_effect_summary(raw_summary: str | None) -> tuple[str, list[dict[str, object]]]:
    """Return the visible summary plus reconstructed text-only effect payloads."""
    summary = str(raw_summary or "").strip()
    if not summary or not summary.endswith(_TEXT_EFFECT_SUFFIX):
        return summary, []

    marker_index = summary.rfind(_TEXT_EFFECT_MARKER)
    if marker_index < 0:
        return summary, []

    encoded_payload = summary[marker_index + len(_TEXT_EFFECT_MARKER) : -len(_TEXT_EFFECT_SUFFIX)]
    try:
        decoded_payload = json.loads(_decode_base64_payload(encoded_payload))
    except (ValueError, json.JSONDecodeError):
        return summary, []

    if not isinstance(decoded_payload, list):
        return summary, []

    text_payloads: list[dict[str, object]] = []
    for entry in decoded_payload:
        if isinstance(entry, dict):
            description = str(entry.get("effect_description") or "").strip()
            display_order = int(entry.get("display_order") or 0)
        else:
            description = str(entry or "").strip()
            display_order = 0
        if not description:
            continue
        text_payloads.append(
            {
                "target_kind": TEXT_TARGET_KIND,
                "value": 0,
                "effect_description": description,
                "target_display": "Text",
                "display_order": display_order,
            }
        )

    return summary[:marker_index].rstrip(), text_payloads


def pack_magic_effect_summary(visible_summary: str | None, text_effect_descriptions: list[object]) -> str:
    """Store text-only effects inside the summary field without changing the visible text."""
    summary = str(visible_summary or "").strip()
    cleaned_payloads: list[dict[str, object]] = []
    for entry in text_effect_descriptions:
        if isinstance(entry, dict):
            description = str(entry.get("effect_description") or "").strip()
            display_order = int(entry.get("display_order") or 0)
        else:
            description = str(entry).strip()
            display_order = 0
        if not description:
            continue
        cleaned_payloads.append(
            {
                "effect_description": description,
                "display_order": display_order,
            }
        )
    if not cleaned_payloads:
        return summary

    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(cleaned_payloads, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    if summary:
        return f"{summary} {_TEXT_EFFECT_MARKER}{encoded_payload}{_TEXT_EFFECT_SUFFIX}"
    return f"{_TEXT_EFFECT_MARKER}{encoded_payload}{_TEXT_EFFECT_SUFFIX}"
