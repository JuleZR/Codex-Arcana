"""Forms for user-facing character actions."""

from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Character, CharacterSkill


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


class CharacterSkillSpecificationForm(forms.ModelForm):
    """Edit the one-word specification for learned skills such as Beruf."""

    class Meta:
        model = CharacterSkill
        fields = ["specification"]
        widgets = {
            "specification": forms.TextInput(
                attrs={
                    "class": "dashboard_input",
                    "maxlength": 25,
                    "autocomplete": "off",
                    "placeholder": "z. B. Schmied",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.specification == "*":
            self.initial["specification"] = ""

    def clean_specification(self):
        specification = (self.cleaned_data.get("specification") or "").strip()
        if not specification:
            return "*"
        if len(specification.split()) != 1:
            raise forms.ValidationError("Bitte nur ein einzelnes Wort eintragen.")
        return specification


class AccountSettingsForm(forms.Form):
    """Update the authenticated user's basic account settings."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "dashboard_input", "autocomplete": "username"}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "dashboard_input", "autocomplete": "email"}),
    )
    current_password = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "dashboard_input", "autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "dashboard_input", "autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "dashboard_input", "autocomplete": "new-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["username"].initial = user.get_username()
            self.fields["email"].initial = user.email or ""

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Benutzername darf nicht leer sein.")
        duplicate_qs = type(self.user).objects.filter(username__iexact=username).exclude(pk=self.user.pk)
        if duplicate_qs.exists():
            raise forms.ValidationError("Dieser Benutzername ist bereits vergeben.")
        return username

    def clean(self):
        cleaned = super().clean()
        current_password = cleaned.get("current_password") or ""
        new_password1 = cleaned.get("new_password1") or ""
        new_password2 = cleaned.get("new_password2") or ""
        wants_password_change = bool(current_password or new_password1 or new_password2)
        if not wants_password_change:
            return cleaned

        if not current_password:
            self.add_error("current_password", "Bitte aktuelles Passwort angeben.")
            return cleaned
        if not self.user.check_password(current_password):
            self.add_error("current_password", "Aktuelles Passwort ist falsch.")
            return cleaned
        if not new_password1:
            self.add_error("new_password1", "Bitte neues Passwort eingeben.")
            return cleaned
        if new_password1 != new_password2:
            self.add_error("new_password2", "Die neuen Passwörter stimmen nicht überein.")
            return cleaned
        validate_password(new_password1, self.user)
        return cleaned

    def save(self):
        """Persist updates and return whether password changed."""
        username = self.cleaned_data["username"]
        email = self.cleaned_data.get("email") or ""
        password_changed = bool(self.cleaned_data.get("new_password1"))

        changed = False
        if self.user.username != username:
            self.user.username = username
            changed = True
        if (self.user.email or "") != email:
            self.user.email = email
            changed = True
        if password_changed:
            self.user.set_password(self.cleaned_data["new_password1"])
            changed = True
        if changed:
            self.user.save()
        return changed, password_changed
