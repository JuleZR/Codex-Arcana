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
