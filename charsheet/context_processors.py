"""Template context shared by all Codex Arcana pages."""

from django.conf import settings

from codex_arcana.versioning import get_application_version


def application_metadata(_request):
    """Expose application metadata without coupling it to individual views."""
    local_mail_backends = {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    }
    return {
        "app_version": get_application_version(),
        "auth_turnstile_enabled": settings.AUTH_TURNSTILE_ENABLED,
        "auth_turnstile_site_key": settings.AUTH_TURNSTILE_SITE_KEY,
        "auth_turnstile_categories": settings.AUTH_TURNSTILE_CATEGORIES,
        "privacy": {
            "security_retention_days": (
                settings.ACCOUNT_SECURITY_ACTIVITY_RETENTION_DAYS
            ),
            "password_reset_timeout": settings.PASSWORD_RESET_TIMEOUT,
            "verification_timeout": settings.EMAIL_VERIFICATION_TIMEOUT,
            "email_verification_required": (
                settings.EMAIL_VERIFICATION_REQUIRED_FOR_LOGIN
            ),
            "local_mail_backend": (
                settings.EMAIL_BACKEND in local_mail_backends
            ),
            "session_cookie_name": settings.SESSION_COOKIE_NAME,
            "session_age_seconds": settings.SESSION_COOKIE_AGE,
            "session_browser_close": settings.SESSION_EXPIRE_AT_BROWSER_CLOSE,
            "csrf_cookie_name": settings.CSRF_COOKIE_NAME,
            "csrf_age_seconds": settings.CSRF_COOKIE_AGE,
            "csrf_use_sessions": settings.CSRF_USE_SESSIONS,
        },
    }
