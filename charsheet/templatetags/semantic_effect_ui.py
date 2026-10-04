"""Use the shared semantic-effect presentation contract in every template."""

from django import template

from charsheet.constants import WOUND_STAGE_POSITION_CHOICES
from charsheet.semantic_effect_ui import (
    semantic_effect_area_optgroups, semantic_stat_choices,
)


register = template.Library()


@register.filter
def semantic_effect_groups(choices):
    return semantic_effect_area_optgroups(choices)


@register.filter
def semantic_stat_targets(choices, area):
    return semantic_stat_choices(choices or (), combat=area == "combat")


@register.simple_tag
def semantic_wound_positions():
    return WOUND_STAGE_POSITION_CHOICES
