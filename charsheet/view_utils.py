"""Small formatting helpers shared by view-related modules."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from charsheet.constants import QUALITY_CHOICES, QUALITY_COLOR_MAP
from charsheet.engine import ItemEngine
from charsheet.models import Quality


QUALITY_LABELS = dict(QUALITY_CHOICES)


@lru_cache(maxsize=64)
def _quality_model_payload(code: str) -> tuple[str, str] | None:
    try:
        quality = Quality.objects.only("name", "hex_color").filter(pk=code).first()
    except Exception:
        return None
    if quality is None:
        return None
    return quality.name, quality.hex_color


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
    model_payload = None if hasattr(quality, "name") else _quality_model_payload(resolved_quality)
    model_label = None if model_payload is None else model_payload[0]
    model_color = None if model_payload is None else model_payload[1]
    return {
        "value": resolved_quality,
        "label": getattr(quality, "name", None)
        or model_label
        or QUALITY_LABELS.get(resolved_quality, QUALITY_LABELS[ItemEngine.normalize_quality(None)]),
        "color": getattr(quality, "hex_color", None)
        or model_color
        or QUALITY_COLOR_MAP.get(resolved_quality, QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)]),
    }
