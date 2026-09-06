"""Delete expired anonymous onboarding sessions and their temporary data.

Run periodically (cron) in addition to the opportunistic purge that happens
when new sessions are created. Only temporary per-session data is deleted —
global catalog data is never touched.
"""

from django.core.management.base import BaseCommand

from Apps.journey.services import purge_expired_sessions


class Command(BaseCommand):
    help = "Delete expired anonymous onboarding sessions (and their assessment data)."

    def handle(self, *args, **options):
        deleted, per_model = purge_expired_sessions()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} rows: {per_model}"))
