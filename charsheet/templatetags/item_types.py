"""Expose database item capabilities to catalog form scripts."""

from django import template

from charsheet.models import ItemType
from charsheet.substances import SubstanceStatsForm

register = template.Library()


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
