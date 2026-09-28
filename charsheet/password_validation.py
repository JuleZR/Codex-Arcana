from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class MaximumLengthValidator:
    def __init__(self, max_length=24):
        self.max_length = max_length

    def validate(self, password, user=None):
        if len(password) > self.max_length:
            raise ValidationError(
                _(
                    "This password is too long. It must contain at most "
                    "%(max_length)d characters."
                ),
                code="password_too_long",
                params={"max_length": self.max_length},
            )

    def get_help_text(self):
        return _(
            "Your password must contain at most %(max_length)d characters."
        ) % {"max_length": self.max_length}


class UppercaseValidator:
    def validate(self, password, user=None):
        if not any(character.isupper() for character in password):
            raise ValidationError(
                _("This password must contain at least one uppercase letter."),
                code="password_no_uppercase",
            )

    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter.")


class SpecialCharacterValidator:
    def validate(self, password, user=None):
        has_special_character = any(
            not character.isalnum() and not character.isspace()
            for character in password
        )
        if not has_special_character:
            raise ValidationError(
                _(
                    "This password must contain at least one special "
                    "character."
                ),
                code="password_no_special_character",
            )

    def get_help_text(self):
        return _("Your password must contain at least one special character.")
