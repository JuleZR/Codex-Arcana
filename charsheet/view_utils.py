"""Small formatting helpers shared by view-related modules."""

from __future__ import annotations

from decimal import Decimal

from charsheet.constants import QUALITY_CHOICES, QUALITY_COLOR_MAP
from charsheet.engine import ItemEngine


QUALITY_LABELS = dict(QUALITY_CHOICES)


def format_modifier(value: int) -> str:
    """Format signed modifier values for UI display."""
    if value > 0:
        return f"+{value}"
    return str(value)


def format_thousands(value: int) -> str:
    """Format integers with dot-separated thousands."""
    return f"{value:,}".replace(",", ".")


def format_compact_number(value) -> str:
    """Format whole-looking numbers without trailing decimal zeros."""
    if value is None:
        return "-"
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return format(normalized, "f").rstrip("0").rstrip(".") if normalized.as_tuple().exponent < 0 else format(normalized, "f")
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def quality_payload(quality: str | None) -> dict[str, str]:
    """Return normalized quality metadata for templates and JSON responses."""
    resolved_quality = ItemEngine.normalize_quality(quality)
    return {
        "value": resolved_quality,
        "label": QUALITY_LABELS.get(resolved_quality, QUALITY_LABELS[ItemEngine.normalize_quality(None)]),
        "color": QUALITY_COLOR_MAP.get(resolved_quality, QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)]),
    }
