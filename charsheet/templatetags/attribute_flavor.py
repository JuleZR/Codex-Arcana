"""Pre-render portraits alongside the current attribute panel."""

from django import template

from charsheet.attribute_flavor import (
    build_flavor_catalog,
    resolve_attribute_flavor,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def attribute_flavor_data(context, character, short_name, value):
    key = ("attribute_flavor_catalog", character.pk, character.race_id)
    catalog = context.render_context.get(key)
    if catalog is None:
        catalog = build_flavor_catalog(character)
        context.render_context[key] = catalog
    attribute = catalog["attributes"].get(short_name)
    if attribute is None:
        return {}
    return resolve_attribute_flavor(character, attribute, value, catalog)
