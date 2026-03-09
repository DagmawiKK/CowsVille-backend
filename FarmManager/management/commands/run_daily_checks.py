"""
Management command to run the daily farm monitoring checks.

Usage:
    python manage.py run_daily_checks

Schedule with cron (runs every day at 06:00 server time):
    0 6 * * * /path/to/venv/bin/python /path/to/manage.py run_daily_checks \
        --settings=FarmManagerSystem.productions_settings >> /var/log/cowsville_daily.log 2>&1
"""

from django.core.management.base import BaseCommand

from AlertSystem.updater import run_daily_checks


class Command(BaseCommand):
    help = "Run daily farm monitoring checks (heat-sign alerts and pregnancy calving alerts)"

    def handle(self, *args, **options):
        self.stdout.write("Starting daily farm monitoring checks...")
        result = run_daily_checks()
        self.stdout.write(self.style.SUCCESS(result))
