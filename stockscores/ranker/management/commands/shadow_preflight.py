"""Read-only identity check that works while every execution switch is off."""

from django.core.management.base import BaseCommand, CommandError

from ranker.shadow_broker import ShadowIdentityError, verify_account_identity


class Command(BaseCommand):
    help = "Verify two distinct Alpaca paper IDs without enabling shadow execution."

    def handle(self, *args, **options):
        try:
            # Do not print credentials or full account IDs to console/history.
            verify_account_identity(require_enabled=False)
        except ShadowIdentityError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write("Shadow preflight passed: both paper accounts identified and distinct.")
