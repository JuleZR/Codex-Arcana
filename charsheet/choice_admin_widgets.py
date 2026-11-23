"""Structured inputs for per-target choice limits."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join


class TargetLevelWidget(forms.Widget):
    def __init__(self, choices=(), attrs=None):
        super().__init__(attrs)
        self.choices = choices

    def render(self, name, value, attrs=None, renderer=None):
        rows = list((value or {}).items()) if isinstance(value, dict) else []
        if isinstance(value, list):
            rows = value
        choices = list(
            self.choices() if callable(self.choices) else self.choices,
        )
        known = {key for key, label in choices}
        choices.extend((key, key) for key, level in rows if key not in known)
        rows.append(("", ""))
        rendered = []
        for index, (target, level) in enumerate(rows):
            input_attrs = dict(attrs or {})
            input_attrs["id"] = f'{input_attrs.get("id", name)}_{index}'
            rendered.append(format_html(
                '<div data-limit-row>{} {} '
                '<button type="button" data-remove-limit>Entfernen</button>'
                '</div>',
                forms.Select(choices=[("", "Ziel auswählen"), *choices])
                .render(name + "_target", target, input_attrs),
                forms.NumberInput(attrs={
                    "min": 0, "aria-label": "Maximale Stufe",
                    "placeholder": "Maximale Stufe",
                }).render(name + "_level", level),
            ))
        return format_html(
            '<div data-target-limits>{}'
            '<button type="button" data-add-limit>Begrenzung hinzufügen'
            '</button></div>',
            format_html_join("", "{}", ((row,) for row in rendered)),
        )

    def value_from_datadict(self, data, files, name):
        if name in data and isinstance(data.get(name), dict):
            return data.get(name)

        def values(key):
            if hasattr(data, "getlist"):
                return data.getlist(key)
            value = data.get(key, [])
            return value if isinstance(value, (list, tuple)) else [value]

        targets = values(name + "_target")
        levels = values(name + "_level")
        return list(zip(targets, levels))

    def value_omitted_from_data(self, data, files, name):
        return name + "_target" not in data


class TargetLevelField(forms.Field):
    widget = TargetLevelWidget

    def to_python(self, value):
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        result = {}
        for target, level in value:
            if not target and level == "":
                continue
            if not target or level == "":
                raise ValidationError("Ziel und maximale Stufe angeben.")
            try:
                number = int(level)
            except (TypeError, ValueError):
                raise ValidationError("Eine ganze Stufe angeben.")
            if number < 0 or target in result:
                raise ValidationError(
                    "Jedes Ziel einmal mit einer gültigen Stufe angeben.",
                )
            result[target] = number
        return result
