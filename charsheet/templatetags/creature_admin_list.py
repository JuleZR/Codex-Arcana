"""Template tags for the visually grouped creature admin list."""

from django import template
from django.contrib.admin.templatetags.admin_list import (
    result_headers,
    result_hidden_fields,
    results,
)


register = template.Library()


@register.inclusion_tag("admin/charsheet/creature/grouped_change_list_results.html")
def grouped_creature_result_list(cl):
    """Render standard admin result rows with creature-type group headings."""

    headers = list(result_headers(cl))
    num_sorted_fields = sum(
        1 for header in headers if header["sortable"] and header["sorted"]
    )
    rendered_results = list(results(cl))
    grouped_results = []
    previous_group = object()

    for creature, result in zip(cl.result_list, rendered_results):
        group_key = creature.creature_type_id
        group_label = (
            creature.creature_type.name
            if creature.creature_type_id
            else "Ohne Kreaturentyp"
        )
        starts_group = group_key != previous_group
        grouped_results.append(
            {
                "group_label": group_label,
                "starts_group": starts_group,
                "result": result,
            }
        )
        previous_group = group_key

    return {
        "cl": cl,
        "result_hidden_fields": list(result_hidden_fields(cl)),
        "result_headers": headers,
        "num_sorted_fields": num_sorted_fields,
        "grouped_results": grouped_results,
    }
