"""Remove account-security events beyond the configured retention period."""

from django.core.management.base import BaseCommand

from charsheet.auth_security import purge_expired_security_events


class Command(BaseCommand):
    help = "Delete expired account security activity entries."

    def handle(self, *args, **options):
        deleted_count = purge_expired_security_events()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} expired security activity entries."
            )
        )
