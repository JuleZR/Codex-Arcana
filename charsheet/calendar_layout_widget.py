"""Shared visual date-layout editor embedded in Django model forms."""

import json

from django import forms
from django.templatetags.static import static
from django.utils.html import format_html

from charsheet.calendar_layout import fallback_layout


class CalendarLayoutWidget(forms.HiddenInput):
    is_hidden = False

    @property
    def media(self):
        return forms.Media(
            js=(static("charsheet/js/calendar-layout.js")
                + "?v=20261009-layout-5",),
            css={"all": (
                "https://fonts.googleapis.com/css2?family=Noto+Serif:"
                "wght@400;500&family=Noto+Serif+JP:wght@400;500&display=swap",
                "charsheet/css/character-date.css",
                static("charsheet/css/calendar-layout.css")
                + "?v=20261009-layout-5",
            )},
        )

    def format_value(self, value):
        return json.dumps(value) if isinstance(value, dict) else value

    def render(self, name, value, attrs=None, renderer=None):
        encoded = self.format_value(value)
        # Keep invalid submitted JSON available for form validation.
        try:
            initial = json.loads(encoded) if encoded else None
            from charsheet.calendar_layout import validate_layout

            if initial is not None:
                validate_layout(initial)
        except (ValueError, forms.ValidationError):
            initial = None
        return format_html(
            '<div data-calendar-layout-widget>{}'
            '<span hidden data-layout-initial>{}</span>'
            '<span hidden data-layout-fallback>{}</span>'
            '<div data-layout-host></div></div>',
            super().render(name, encoded, attrs, renderer),
            json.dumps(initial), json.dumps(fallback_layout()),
        )
