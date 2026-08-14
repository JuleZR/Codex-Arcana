"""Engine migration switches kept for compatibility with callers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModifierResolutionMode(str, Enum):
    """Internal switch for modifier resolution."""

    NEW_ONLY = "new_only"
    COMPARE = "compare"

    @classmethod
    def normalize(cls, value: str | None):
        """Return a valid mode string with new-only as the default."""
        if isinstance(value, cls):
            return value
        raw_value = getattr(value, "value", value)
        normalized = str(raw_value or cls.NEW_ONLY.value).strip().lower()
        for member in cls:
            if normalized == str(member.value):
                return member
        return cls.NEW_ONLY


@dataclass(slots=True)
class NumericResolutionComparison:
    """Comparison row retained for debug API compatibility."""

    target_domain: str
    target_key: str
    legacy_value: int
    new_value: int
    matches: bool
    classification: str
    notes: tuple[str, ...] = ()
