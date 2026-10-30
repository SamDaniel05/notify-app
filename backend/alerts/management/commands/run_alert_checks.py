from django.core.management.base import BaseCommand

from alerts.checker import run_checks


class Command(BaseCommand):
    help = "Evaluate active alert rules and send notifications"

    def handle(self, *args, **options):
        result = run_checks()
        self.stdout.write(self.style.SUCCESS(str(result)))
