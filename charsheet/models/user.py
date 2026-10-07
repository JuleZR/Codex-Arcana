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

    theme_mode = models.CharField(
        max_length=24,
        choices=ThemeMode.choices,
        default=ThemeMode.DEFAULT,
    )
    print_include_inventory = models.BooleanField(default=True)
    print_include_notes = models.BooleanField(default=True)
    print_compact = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    verified_email = models.EmailField(blank=True, default="")
    email_verification_address = models.EmailField(blank=True, default="")
    email_verification_token = models.UUIDField(
        blank=True,
        null=True,
        editable=False,
    )
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.TextField(
        blank=True,
        default="",
        editable=False,
    )
    two_factor_enabled_at = models.DateTimeField(blank=True, null=True)
    dice_enabled = models.BooleanField(default=False)
    dddice_enabled = models.BooleanField(default=False)
    critical_success_text = models.CharField(
        max_length=64, blank=True, default="KRITISCHER ERFOLG",
        verbose_name="Text bei kritischem Erfolg",
    )
    critical_failure_text = models.CharField(
        max_length=64, blank=True, default="KRITISCHER FEHLSCHLAG",
        verbose_name="Text bei kritischem Fehlschlag",
    )
    dddice_api_key = models.CharField(max_length=255, blank=True, default="")
    dddice_room_id = models.CharField(max_length=255, blank=True, default="")
    dddice_room_password = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    dddice_dice_box = models.CharField(max_length=255, blank=True, default="")
    dddice_theme_id = models.CharField(max_length=255, blank=True, default="")


class TwoFactorRecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_recovery_codes",
    )
    code_hash = models.CharField(max_length=128, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(
                fields=("user", "used_at"),
                name="two_factor_user_used_idx",
            )
        ]


class PasskeyCredential(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="passkeys",
    )
    name = models.CharField(max_length=80)
    credential_id = models.BinaryField(unique=True, editable=False)
    public_key = models.BinaryField(editable=False)
    sign_count = models.PositiveBigIntegerField(default=0, editable=False)
    transports = models.JSONField(default=list, blank=True)
    device_type = models.CharField(max_length=32, blank=True, default="")
    backed_up = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.user}: {self.name}"
