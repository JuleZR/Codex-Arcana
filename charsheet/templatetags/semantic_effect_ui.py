"""Use the shared semantic-effect presentation contract in every template."""

from types import SimpleNamespace
import json

from django import template

from charsheet.constants import SCHOOL_COMBAT, WOUND_STAGE_POSITION_CHOICES
from charsheet.semantic_effect_ui import (
    school_level_target_choices, semantic_effect_area_optgroups,
    semantic_stat_choices,
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


@register.simple_tag
def semantic_trait_targets():
    from charsheet.models import Trait

    return Trait.objects.order_by("name").values_list("slug", "name")


@register.simple_tag
def semantic_school_level_targets(include_unlearned=False):
    return school_level_target_choices(include_unlearned=include_unlearned)


@register.simple_tag
def semantic_focus_targets():
    from charsheet.models import Aspect, School

    schools = [
        SimpleNamespace(pk=school.pk, name=school.name, group="Magieschulen")
        for school in School.objects.exclude(
            type__slug__in=(SCHOOL_COMBAT, "school_combat"),
        )
    ]
    aspects = [
        SimpleNamespace(
            pk=f"aspect:{aspect.pk}", name=aspect.name, group="Aspekte",
        )
        for aspect in Aspect.objects.all()
    ]
    return [
        *sorted(schools, key=lambda target: target.name.casefold()),
        *sorted(aspects, key=lambda target: target.name.casefold()),
    ]


@register.simple_tag
def semantic_focus_binding_options():
    from charsheet.focus import focus_target_catalog

    return json.dumps(focus_target_catalog(), ensure_ascii=False)
