from django.core.management.base import BaseCommand, CommandError

from ranker.models import TradeSignal
from ranker.trade_lifecycle import TradeLifecycleError, cancel_pending_signal


class Command(BaseCommand):
    help = "Cancel an unfilled published trade and queue its customer notification"

    def add_arguments(self, parser):
        parser.add_argument("signal_id", type=int)
        parser.add_argument("--note", required=True)
        parser.add_argument("--expected-status", default=TradeSignal.STATUS_PUBLISHED)

    def handle(self, *args, **options):
        try:
            result = cancel_pending_signal(
                signal_id=options["signal_id"],
                note=options["note"],
                expected_status=options["expected_status"],
            )
        except TradeLifecycleError as exc:
            raise CommandError(str(exc)) from exc
        state = "already applied" if result.already_applied else "cancelled"
        self.stdout.write(self.style.SUCCESS(
            f"Signal {result.signal.pk} {state}; update {result.update.pk}; "
            f"notification {result.update.telegram_notification.pk}"
        ))

