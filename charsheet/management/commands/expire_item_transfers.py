from django.core.management.base import BaseCommand

from charsheet.item_transfers import expire_due_transfers


class Command(BaseCommand):
    help = "Expire pending item transfers whose seven-day deadline has elapsed."

    def handle(self, *args, **options):
        total = 0
        while True:
            count = expire_due_transfers()
            total += count
            if count < 250:
                break
        self.stdout.write(self.style.SUCCESS(f"Expired {total} item transfer(s)."))
