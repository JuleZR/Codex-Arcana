"""Validated deployment facts for the shared public legal layout."""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from charsheet.legal import legal_page_context


register = template.Library()


@register.filter
def legal_duration(value, largest_unit="days"):
    """Render configured seconds exactly, using readable German units."""
    try:
        remaining = int(value)
    except (TypeError, ValueError):
        return ""
    if remaining < 0:
        return ""
    units = [(86400, "Tag", "Tage"), (3600, "Stunde", "Stunden"),
             (60, "Minute", "Minuten"), (1, "Sekunde", "Sekunden")]
    if largest_unit == "hours":
        units = units[1:]
    parts = []
    for size, singular, plural in units:
        amount, remaining = divmod(remaining, size)
        if amount:
            parts.append(f"{amount} {singular if amount == 1 else plural}")
    return ", ".join(parts) or "0 Sekunden"


@register.simple_tag
def public_legal_info():
    return legal_page_context()["legal"]


@register.filter
def legal_email(value):
    """Display contact addresses as plain text with an (at) separator."""
    return str(value or "").replace("@", "(at)")


@register.filter
def legal_bold(value):
    """Allow inline **bold** text while escaping all supplied HTML."""
    escaped = str(escape(value or ""))
    return mark_safe(re.sub(
        r"\*\*([^\n]+?)\*\*", r"<strong>\1</strong>", escaped,
    ))
