"""Forms for user-facing character actions."""

import base64
import binascii
from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from .models import Character, CharacterDivineEntity, CharacterItemRuneSpec, CharacterSkill, CharacterTechnique, DivineEntity
from .models.user import UserSettings
from .religion_rules import active_clerical_school_entries, locked_religion_entity, unique_divine_entity_for_school


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            "sidebar_enabled",
            "dddice_enabled",
            "dddice_api_key",
            "dddice_room_id",
            "dddice_room_password",
            "dddice_dice_box",
            "dddice_theme_id",
        ]
        widgets = {
            "dddice_room_password": forms.PasswordInput(render_value=True),
        }

    def clean(self):
        cleaned_data = super().clean()

        dddice_enabled = cleaned_data.get("dddice_enabled")
        dddice_api_key = (cleaned_data.get("dddice_api_key") or "").strip()
        dddice_room_id = (cleaned_data.get("dddice_room_id") or "").strip()

        if dddice_enabled:
            if not dddice_api_key:
                self.add_error("dddice_api_key", "Bitte einen API Key hinterlegen.")
            if not dddice_room_id:
                self.add_error("dddice_room_id", "Bitte eine Room ID hinterlegen.")

        return cleaned_data


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

    religion_entity = forms.ModelChoiceField(
        queryset=DivineEntity.objects.none(),
        required=False,
        empty_label="",
        widget=forms.Select(attrs={"class": "dashboard_input"}),
    )
    char_picture_upload = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": "dashboard_input",
                "accept": "image/*",
                "id": "charPictureInput",
            }
        ),
    )
    char_picture_cropped_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "charPictureCroppedData"}),
    )
    remove_char_picture = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "charPictureRemoveFlag"}),
    )

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
            "religion_entity",
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
            "appearance": forms.Textarea(attrs={"class": "dashboard_input", "maxlength": 300, "rows": 3, "style": "resize: none;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cropped_picture_content = None
        self._uploaded_picture_content = None
        self._locked_religion_entity = None
        self.fields["religion_entity"].queryset = DivineEntity.objects.order_by("name")

        if self.instance and self.instance.pk:
            self._locked_religion_entity = locked_religion_entity(self.instance, repair=True)
            binding = getattr(self.instance, "divine_entity_binding", None)
            if self._locked_religion_entity is not None:
                self.fields["religion_entity"].initial = self._locked_religion_entity.pk
                self.fields["religion_entity"].disabled = True
                self.fields["religion_entity"].help_text = "Durch die gelernte klerikale Schule festgelegt."
            elif binding is not None:
                self.fields["religion_entity"].initial = binding.entity_id
            elif self.instance.religion:
                self.fields["religion_entity"].initial = (
                    DivineEntity.objects.filter(name=self.instance.religion).values_list("pk", flat=True).first()
                )

    @staticmethod
    def _normalize_picture_bytes(raw_bytes):
        try:
            with Image.open(BytesIO(raw_bytes)) as image:
                image = ImageOps.exif_transpose(image)
                if image.mode not in ("RGB", "L"):
                    background = Image.new("RGB", image.size, "#f3ead8")
                    alpha_image = image.convert("RGBA")
                    background.paste(alpha_image, mask=alpha_image.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")

                width, height = image.size
                if width <= 0 or height <= 0:
                    raise forms.ValidationError("Das hochgeladene Bild ist leer.")

                target_ratio = 4 / 5
                current_ratio = width / height

                if current_ratio > target_ratio:
                    crop_height = height
                    crop_width = round(height * target_ratio)
                else:
                    crop_width = width
                    crop_height = round(width / target_ratio)

                crop_width = max(4, min(crop_width, width))
                crop_height = max(5, min(crop_height, height))

                left = max(0, (width - crop_width) // 2)
                top = max(0, (height - crop_height) // 2)
                image = image.crop((left, top, left + crop_width, top + crop_height))

                if image.size != (800, 1000):
                    image = image.resize((800, 1000), Image.Resampling.LANCZOS)

                output = BytesIO()
                image.save(output, format="JPEG", quality=92, optimize=True)
        except OSError as error:
            raise forms.ValidationError("Das Bild konnte nicht verarbeitet werden.") from error

        return output.getvalue(), "jpg"

    def clean_char_picture_cropped_data(self):
        raw_value = (self.cleaned_data.get("char_picture_cropped_data") or "").strip()
        if not raw_value:
            return ""

        if "," not in raw_value:
            raise forms.ValidationError("Das zugeschnittene Bild konnte nicht gelesen werden.")

        header, encoded = raw_value.split(",", 1)
        if ";base64" not in header:
            raise forms.ValidationError("Das zugeschnittene Bild ist ungültig.")

        mime_type = header.split(":", 1)[-1].split(";", 1)[0].lower()
        extension_by_mime = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        extension = extension_by_mime.get(mime_type)
        if extension is None:
            raise forms.ValidationError("Bitte ein Bild als JPG, PNG oder WEBP verwenden.")

        try:
            decoded = base64.b64decode(encoded)
        except (ValueError, binascii.Error) as error:
            raise forms.ValidationError("Das zugeschnittene Bild ist beschädigt.") from error

        if not decoded:
            raise forms.ValidationError("Das zugeschnittene Bild ist leer.")

        try:
            normalized_bytes, normalized_extension = self._normalize_picture_bytes(decoded)
        except forms.ValidationError as error:
            raise forms.ValidationError(error.message) from error

        self._cropped_picture_content = (normalized_bytes, normalized_extension or extension)
        return raw_value

    def clean_char_picture_upload(self):
        uploaded = self.cleaned_data.get("char_picture_upload")
        if not uploaded:
            return uploaded

        try:
            uploaded_bytes = uploaded.read()
        finally:
            uploaded.seek(0)

        if not uploaded_bytes:
            raise forms.ValidationError("Bitte ein gültiges Bild auswählen.")

        normalized_bytes, normalized_extension = self._normalize_picture_bytes(uploaded_bytes)
        self._uploaded_picture_content = (normalized_bytes, normalized_extension)
        return uploaded

    def clean_religion_entity(self):
        selected_religion = self.cleaned_data.get("religion_entity")
        if not self.instance or not self.instance.pk:
            return selected_religion

        clerical_entries = active_clerical_school_entries(self.instance)
        if not clerical_entries:
            return selected_religion
        if len(clerical_entries) > 1:
            raise forms.ValidationError("Religion kann bei mehreren klerikalen Schulen nicht eindeutig gesetzt werden.")

        school = clerical_entries[0].school
        if selected_religion is None:
            selected_religion = unique_divine_entity_for_school(school.id)
            if selected_religion is None:
                raise forms.ValidationError("Bitte eine Religion passend zur klerikalen Schule waehlen.")
        if int(selected_religion.school_id) != int(school.id):
            raise forms.ValidationError("Diese Religion passt nicht zur gelernten klerikalen Schule.")
        return selected_religion

    def save(self, commit=True):
        character = super().save(commit=False)
        locked_entity = locked_religion_entity(character, repair=True) if character.pk else None
        selected_religion = locked_entity or self.cleaned_data.get("religion_entity")
        character.religion = selected_religion.name if selected_religion else ""
        remove_picture = bool(self.cleaned_data.get("remove_char_picture"))
        safe_name = "".join(ch.lower() if ch.isalnum() else "-" for ch in (character.name or "character")).strip("-")
        safe_name = safe_name or f"character-{character.pk or 'portrait'}"

        if self._cropped_picture_content:
            decoded, extension = self._cropped_picture_content
            remove_picture = False
            if character.char_picture:
                character.char_picture.delete(save=False)
            character.char_picture.save(
                f"{safe_name}-portrait-{uuid4().hex[:10]}.{extension}",
                ContentFile(decoded),
                save=False,
            )
        elif self._uploaded_picture_content:
            decoded, extension = self._uploaded_picture_content
            remove_picture = False
            if character.char_picture:
                character.char_picture.delete(save=False)
            character.char_picture.save(
                f"{safe_name}-portrait-{uuid4().hex[:10]}.{extension}",
                ContentFile(decoded),
                save=False,
            )
        elif remove_picture and character.char_picture:
            character.char_picture.delete(save=False)
            character.char_picture = None

        if commit:
            character.save()
            if selected_religion:
                CharacterDivineEntity.objects.update_or_create(
                    character=character,
                    defaults={"entity": selected_religion},
                )
            else:
                CharacterDivineEntity.objects.filter(character=character).delete()
            self.save_m2m()
        return character


class CharacterSkillSpecificationForm(forms.ModelForm):
    """Edit the specification text for learned skills such as Beruf."""

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
        return " ".join(specification.split())


class CharacterItemRuneSpecForm(forms.ModelForm):
    """Edit the specialization text for one rune on an owned item."""

    class Meta:
        model = CharacterItemRuneSpec
        fields = ["specification"]
        widgets = {
            "specification": forms.TextInput(
                attrs={
                    "class": "dashboard_input",
                    "maxlength": 100,
                    "autocomplete": "off",
                    "placeholder": "z. B. Feuer",
                }
            ),
        }


class CharacterTechniqueSpecificationForm(forms.ModelForm):
    """Edit the specification text for learned techniques on the character sheet."""

    class Meta:
        model = CharacterTechnique
        fields = ["specification_value"]
        widgets = {
            "specification_value": forms.TextInput(
                attrs={
                    "class": "dashboard_input",
                    "maxlength": 100,
                    "autocomplete": "off",
                    "placeholder": "z. B. Feuerschwert",
                }
            ),
        }

    def clean_specification_value(self):
        specification_value = (self.cleaned_data.get("specification_value") or "").strip()
        if not specification_value:
            return ""
        return " ".join(specification_value.split())


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

        User = get_user_model()

        duplicate_qs = User.objects.filter(username__iexact=username).exclude(pk=self.user.pk)
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
