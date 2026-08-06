from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    class ThemeMode(models.TextChoices):
        DEFAULT = "default", "Standard"
        COMPACT = "compact", "Kompakt"
        LARGE = "large", "Groß"
        HIGH_CONTRAST = "high_contrast", "Hoher Kontrast"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    radial_menu_enabled = models.BooleanField(default=False)
    theme_mode = models.CharField(max_length=24, choices=ThemeMode.choices, default=ThemeMode.DEFAULT)
    print_include_inventory = models.BooleanField(default=True)
    print_include_notes = models.BooleanField(default=True)
    print_compact = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(blank=True, null=True)
    dddice_enabled = models.BooleanField(default=False)
    dddice_api_key = models.CharField(max_length=255, blank=True, default="")
    dddice_room_id = models.CharField(max_length=255, blank=True, default="")
    dddice_room_password = models.CharField(max_length=255, blank=True, default="")
    dddice_dice_box = models.CharField(max_length=255, blank=True, default="")
    dddice_theme_id = models.CharField(max_length=255, blank=True, default="")
