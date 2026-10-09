"""Versioned, bounded date layouts shared by both calendar editors."""

import copy
import re

from django.core.exceptions import ValidationError


FIELDS = {
    "day": "Tageszahl",
    "month_primary": "Primärer Monatsname",
    "month_alternative": "Alternativer Monatsname",
    "year": "Jahreszahl",
    "system_primary": "Primäre Zeitrechnungsbezeichnung",
    "system_alternative": "Alternative Zeitrechnungsbezeichnung",
    "season": "Jahreszeit",
    "text": "Freitext / Trennzeichen",
}
STYLE_CHOICES = {
    "size_mode": ("fixed", "dynamic"),
    "weight": ("normal", "bold"),
    "italic": (False, True),
    "visible": (False, True),
    "align": ("start", "center", "end"),
    "color": ("inherit", "primary", "muted", "accent"),
    "width": ("auto", "fill"),
    "wrap": (False, True),
}


def element(field, **style):
    return {"type": "element", "field": field, "style": style}


def fallback_layout():
    return {
        "version": 1,
        "root": {
            "type": "group", "direction": "column",
            "style": {"align": "center", "gap": 2},
            "children": [
                {
                    "type": "group", "direction": "row",
                    "style": {"gap": 4, "align": "center", "wrap": True},
                    "children": [
                        {
                            "type": "group", "direction": "row",
                            "style": {"gap": 0, "wrap": False},
                            "children": [
                                element("day", size=28),
                                {**element("text", size=28), "text": "."},
                            ],
                        },
                        element("month_primary", size=28),
                        element("year", size=28),
                        element("system_primary", size=28),
                    ],
                },
                element(
                    "month_alternative", size=15, italic=True, color="muted"
                ),
                element("season", size=11, color="accent"),
            ],
        },
    }


def validate_layout(layout):
    """Reject arbitrary code, unknown properties and unbounded trees."""
    def fail():
        raise ValidationError("Ungültige Datums-Layoutdefinition.")

    if not isinstance(layout, dict) or set(layout) != {"version", "root"}:
        fail()
    if type(layout["version"]) is not int or layout["version"] not in (1, 2):
        fail()
    count = 0

    def visit(node, depth=0):
        nonlocal count
        count += 1
        limit = 132 if layout["version"] == 2 else 128
        if count > limit or depth > 12 or not isinstance(node, dict):
            fail()
        group = node.get("type") == "group"
        allowed = (
            {"type", "direction", "style", "children"}
            if group else {"type", "field", "style", "text"}
        )
        if set(node) - allowed:
            fail()
        style = node.get("style", {})
        if not isinstance(style, dict):
            fail()
        for key, value in style.items():
            if key in STYLE_CHOICES:
                if (
                    value not in STYLE_CHOICES[key]
                    or (key in ("italic", "visible", "wrap")
                        and type(value) is not bool)
                ):
                    fail()
            elif key in ("size", "gap", "padding"):
                low, high = (8, 40) if key == "size" else (0, 24)
                if type(value) is not int or not low <= value <= high:
                    fail()
            else:
                fail()
        if group:
            if node.get("direction") not in ("row", "column"):
                fail()
            if not isinstance(node.get("children"), list):
                fail()
            for child in node["children"]:
                visit(child, depth + 1)
        else:
            if (
                node.get("type") != "element"
                or node.get("field") not in FIELDS
            ):
                fail()
            if "text" in node and (
                node["field"] != "text"
                or not isinstance(node["text"], str)
                or len(node["text"]) > 200
            ):
                fail()

    if (
        not isinstance(layout["root"], dict)
        or layout["root"].get("type") != "group"
    ):
        fail()
    visit(layout["root"])
    if layout["version"] == 2:
        root = layout["root"]
        if root["direction"] != "column" or len(root["children"]) > 3:
            fail()
        for row in root["children"]:
            if row["type"] != "group" or row["direction"] != "row":
                fail()
            if any(child["type"] != "element" for child in row["children"]):
                fail()
    return layout


def split_name(value):
    match = re.fullmatch(r"\s*(.*?)\s*\[([^\[\]]*)\]\s*", value)
    return (match[1].strip(), match[2].strip()) if match else (value, "")


def layout_values(payload):
    month, alternative = split_name(payload["month_name"])
    primary, abbreviation = split_name(payload["abbreviation"])
    return {
        "day": str(payload["day"]).zfill(2), "year": str(payload["year"]),
        "month_primary": month, "month_alternative": alternative,
        "system_primary": primary,
        "system_alternative": abbreviation,
        "season": (payload.get("season") or {}).get("name", ""),
    }


def effective_layout(user, system):
    from charsheet.models.calendar import UserCalendarLayout

    personal = UserCalendarLayout.objects.filter(
        user=user, system=system
    ).first()
    standard = system.date_layout or fallback_layout()
    return {
        "layout": copy.deepcopy(personal.layout if personal else standard),
        "standard_layout": copy.deepcopy(standard),
        "personal_layout": personal is not None,
    }
