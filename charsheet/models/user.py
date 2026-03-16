from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    dddice_enabled = models.BooleanField(default=False)
    dddice_api_key = models.CharField(max_length=255, blank=True, default="")
    dddice_room_id = models.CharField(max_length=255, blank=True, default="")
    dddice_room_password = models.CharField(max_length=255, blank=True, default="")
    dddice_dice_box = models.CharField(max_length=255, blank=True, default="")
    dddice_theme_id = models.CharField(max_length=255, blank=True, default="")