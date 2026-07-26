"""Template context shared by all Codex Arcana pages."""

from codex_arcana.versioning import get_application_version


def application_metadata(_request):
    """Expose application metadata without coupling it to individual views."""

    return {"app_version": get_application_version()}
