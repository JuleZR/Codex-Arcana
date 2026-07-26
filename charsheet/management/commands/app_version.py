"""Print the automatically calculated Codex Arcana version."""

from django.core.management.base import BaseCommand

from codex_arcana.versioning import get_application_version


class Command(BaseCommand):
    """Make the version available to deployment scripts."""

    help = "Print the current Codex Arcana application version."

    def handle(self, *args, **options):
        self.stdout.write(get_application_version())
