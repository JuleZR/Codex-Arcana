"""Forms for user-facing character actions."""

from django import forms

from .models import Character


class CharacterCreateForm(forms.ModelForm):
    """Minimal character creation form for dashboard usage."""

    class Meta:
        model = Character
        fields = ["name", "race", "gender"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "dashboard_input",
                    "maxlength": 100,
                    "autocomplete": "off",
                }
            ),
            "race": forms.Select(attrs={"class": "dashboard_input"}),
            "gender": forms.Select(attrs={"class": "dashboard_input"}),
        }


class CharacterUpdateForm(CharacterCreateForm):
    """Character update form with same fields/widgets as create form."""


class CharacterInfoInlineForm(forms.ModelForm):
    """Inline form for editing character info fields on the character sheet."""

    class Meta:
        model = Character
        fields = [
            "name",
            "gender",
            "age",
            "height",
            "skin_color",
            "hair_color",
            "eye_color",
            "country_of_origin",
            "weight",
            "religion",
            "appearance",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "dashboard_input", "maxlength": 100, "autocomplete": "off"}),
            "gender": forms.Select(attrs={"class": "dashboard_input"}),
            "age": forms.NumberInput(attrs={"class": "dashboard_input", "min": 0, "step": 1}),
            "height": forms.NumberInput(attrs={"class": "dashboard_input", "min": 0, "step": 1}),
            "skin_color": forms.TextInput(attrs={"class": "dashboard_input", "maxlength": 25}),
            "hair_color": forms.TextInput(attrs={"class": "dashboard_input", "maxlength": 25}),
            "eye_color": forms.TextInput(attrs={"class": "dashboard_input", "maxlength": 25}),
            "country_of_origin": forms.TextInput(attrs={"class": "dashboard_input", "maxlength": 25}),
            "weight": forms.NumberInput(attrs={"class": "dashboard_input", "min": 0, "step": 1}),
            "religion": forms.TextInput(attrs={"class": "dashboard_input", "maxlength": 25}),
            "appearance": forms.Textarea(attrs={"class": "dashboard_input", "maxlength": 85, "rows": 3}),
        }
