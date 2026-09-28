"""Template context shared by all Codex Arcana pages."""

from django.conf import settings

from codex_arcana.versioning import get_application_version


def application_metadata(_request):
    """Expose application metadata without coupling it to individual views."""

    return {
        "app_version": get_application_version(),
        "auth_turnstile_enabled": settings.AUTH_TURNSTILE_ENABLED,
        "auth_turnstile_site_key": settings.AUTH_TURNSTILE_SITE_KEY,
        "auth_turnstile_categories": settings.AUTH_TURNSTILE_CATEGORIES,
    }
