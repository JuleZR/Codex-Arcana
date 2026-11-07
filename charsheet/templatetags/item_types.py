"""Expose database item capabilities to catalog form scripts."""

import re

from django import template

from charsheet.constants import GK_CHOICES
from charsheet.models import ItemType
from charsheet.substances import SubstanceStatsForm

register = template.Library()


@register.filter
def quality_text_color(value):
    """Choose the higher-contrast black or white text for a hex colour."""
    color = str(value or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{3}|[0-9a-fA-F]{6}", color):
        return "#000000"
    if len(color) == 3:
        color = "".join(channel * 2 for channel in color)
    channels = [int(color[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    luminance = sum(
        channel * weight
        for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722))
    )
    return "#000000" if luminance > 0.179 else "#FFFFFF"


@register.simple_tag
def inventory_size_class_choices():
    return GK_CHOICES


@register.simple_tag
def workshop_item_types():
    return ItemType.objects.all()


@register.simple_tag
def substance_stats_form(item=None):
    return SubstanceStatsForm(
        instance=getattr(item, "substancestats", None), prefix="substance",
    )


@register.simple_tag
def item_type_capabilities():
    fields = [
        field.name
        for field in ItemType._meta.fields
        if field.get_internal_type() == "BooleanField"
    ]
    return {
        row.pop("slug"): row
        for row in ItemType.objects.values("slug", *fields)
    }
