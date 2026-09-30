import time

from django.core.management.base import BaseCommand

from ranker.tasks import run_execution_guardian, run_paper_trade_executor, _record_guardian_transition


def available_memory_mb():
    with open('/proc/meminfo') as source:
        for line in source:
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) // 1024
    return None


class Command(BaseCommand):
    help = "Run the independent Quantelle execution guardian and monitored-exit fallback."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        interval = max(15, options["interval"])
        memory_warning = False
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

            # Observe resources after exit recovery; notice failures cannot interrupt it.
            try:
                available = available_memory_mb()
                if available is not None and available < 128 and not memory_warning:
                    memory_warning = True
                    _record_guardian_transition(True, "Server memory pressure: under 128 MB available. Admin experiments should remain paused; main execution remains active.")
                elif available is not None and available >= 192 and memory_warning:
                    memory_warning = False
                    _record_guardian_transition(False, "Server memory headroom recovered above 192 MB.")
            except Exception:
                pass

            if options["once"]:
                return
            time.sleep(interval)
