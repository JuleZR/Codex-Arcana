"""Print the automatically calculated Codex Arcana version."""

from django.core.management.base import BaseCommand

from codex_arcana.versioning import (
    get_application_version,
    write_deployed_version,
)


class Command(BaseCommand):
    """Make the version available to deployment scripts."""

    help = "Print the current Codex Arcana application version."

    def add_arguments(self, parser):
        parser.add_argument(
            "--write-deployment-file",
            action="store_true",
            help="Store the Git version for the deployed web process.",
        )

    def handle(self, *args, **options):
        if options["write_deployment_file"]:
            version = write_deployed_version()
        else:
            version = get_application_version()

        self.stdout.write(version)
