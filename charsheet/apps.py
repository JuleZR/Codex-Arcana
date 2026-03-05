"""Application configuration for the character sheet Django app."""

from django.apps import AppConfig


class CharsheetConfig(AppConfig):
    """Register app-level metadata for Django startup."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "charsheet"
