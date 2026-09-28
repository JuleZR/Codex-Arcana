"""Persistent data for authentication throttling and account auditing."""

from django.conf import settings
from django.db import models


class AuthenticationThrottle(models.Model):
    """Store a privacy-preserving rate-limit bucket."""

    category = models.CharField(max_length=40)
    key_digest = models.CharField(max_length=64)
    attempts = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("category", "key_digest"),
                name="unique_authentication_throttle_bucket",
            )
        ]
        indexes = [
            models.Index(
                fields=("category", "updated_at"),
                name="auth_thr_category_updated_idx",
            )
        ]


class AccountSecurityEvent(models.Model):
    """A minimal, secret-free audit trail for account security actions."""

    class EventType(models.TextChoices):
        LOGIN_SUCCEEDED = "login_succeeded", "Successful login"
        LOGIN_FAILED = "login_failed", "Failed login attempt"
        PASSWORD_CHANGED = "password_changed", "Password changed"
        PASSWORD_RESET = "password_reset", "Password reset completed"
        EMAIL_CHANGED = "email_changed", "Email address changed"
        EMAIL_VERIFIED = "email_verified", "Email verification completed"
        TWO_FACTOR_ENABLED = "two_factor_enabled", "2FA enabled"
        TWO_FACTOR_DISABLED = "two_factor_disabled", "2FA disabled"
        RECOVERY_CODES_REGENERATED = (
            "recovery_codes_regenerated",
            "Recovery codes regenerated",
        )
        PASSKEY_ADDED = "passkey_added", "Passkey added"
        PASSKEY_REMOVED = "passkey_removed", "Passkey removed"
        OTHER_SESSIONS_LOGGED_OUT = (
            "other_sessions_logged_out",
            "Other sessions logged out",
        )
        SESSION_TERMINATED = "session_terminated", "Session terminated"
        ACCOUNT_DEACTIVATED = "account_deactivated", "Account deactivated"
        ACCOUNT_REACTIVATED = "account_reactivated", "Account reactivated"
        DELETION_REQUESTED = (
            "deletion_requested",
            "Permanent deletion requested",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_events",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=160, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("user", "-created_at"),
                name="acct_sec_user_created_idx",
            )
        ]
        permissions = [
            (
                "inspect_accountsecurityevent",
                "Can inspect account security activity",
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.get_event_type_display()}"

    @property
    def description(self):
        label = str(self.metadata.get("label", "")).strip()
        if label and self.event_type in {
            self.EventType.PASSKEY_ADDED,
            self.EventType.PASSKEY_REMOVED,
        }:
            return f"{self.get_event_type_display()}: {label}"
        return self.get_event_type_display()
