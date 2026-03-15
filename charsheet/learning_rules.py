"""Shared learning and progression calculations for views."""

from __future__ import annotations

from django.db.models import Max

from charsheet.models import Technique


DEFAULT_SCHOOL_MAX_LEVEL = 10


def calc_skill_total_cost(level: int) -> int:
    """Return cumulative skill cost for one target level."""
    if level <= 5:
        return max(0, level)
    return 5 + ((max(0, level) - 5) * 2)


def calc_language_total_cost(level: int, can_write: bool, is_mother_tongue: bool) -> int:
    """Return cumulative language cost for one language state."""
    base = 0 if is_mother_tongue else max(0, level)
    return base + (1 if can_write else 0)


def calc_attribute_total_cost(target_level: int, max_value: int) -> int:
    """Return cumulative attribute cost for one target level."""
    level = max(0, target_level)
    threshold = max_value - 2
    if level <= threshold:
        return level * 10
    cost = threshold * 10
    for _value in range(threshold + 1, level + 1):
        cost += 20
    return cost


def school_max_levels() -> dict[int, int]:
    """Return dynamic school level caps based on highest technique level per school."""
    caps: dict[int, int] = {}
    rows = Technique.objects.values("school_id").annotate(max_level=Max("level"))
    for row in rows:
        school_id = int(row.get("school_id") or 0)
        if school_id <= 0:
            continue
        max_level = int(row.get("max_level") or DEFAULT_SCHOOL_MAX_LEVEL)
        caps[school_id] = max(1, max_level)
    return caps
