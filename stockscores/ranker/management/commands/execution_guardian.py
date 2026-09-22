import time

from django.core.management.base import BaseCommand

from ranker.tasks import run_execution_guardian, run_paper_trade_executor


class Command(BaseCommand):
    help = "Run the independent Quantelle execution guardian and monitored-exit fallback."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        interval = max(15, options["interval"])
        while True:
            guardian_result = run_execution_guardian()
            if (
                guardian_result.get("status") == "degraded"
                and guardian_result.get("reason") == "stale_heartbeat"
            ):
                # Use the original executor unchanged as the recovery path.
                # Its distributed lock prevents simultaneous duplicate work.
                try:
                    fallback_result = run_paper_trade_executor()
                except Exception as exc:
                    fallback_result = {"status": "error", "reason": str(exc)[:500]}
                self.stdout.write(
                    f"guardian={guardian_result} fallback={fallback_result}",
                    ending="\n",
                )
            elif guardian_result.get("status") == "degraded":
                self.stdout.write(f"guardian={guardian_result}", ending="\n")

            if options["once"]:
                return
            time.sleep(interval)
