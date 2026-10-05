"""Expose database item capabilities to catalog form scripts."""

from django import template

from charsheet.models import ItemType

register = template.Library()


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
