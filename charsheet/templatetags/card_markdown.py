from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt


register = template.Library()

_markdown = MarkdownIt(
    "default",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
)


@register.filter(name="card_markdown")
def card_markdown(value):
    if not value:
        return ""
    return mark_safe(_markdown.render(str(value)))
