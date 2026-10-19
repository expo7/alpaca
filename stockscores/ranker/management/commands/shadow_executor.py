"""Standalone operator-started shadow loop; intentionally absent from Compose/Beat."""

import time

from django.core.management.base import BaseCommand

from ranker.shadow_executor import run_shadow_cycle


class Command(BaseCommand):
    help = "Run the separate paper shadow executor (disabled unless all safety flags pass)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--interval", type=int, default=15)

    def handle(self, *args, **options):
        if not options["once"] and not 10 <= options["interval"] <= 60:
            raise ValueError("Interval must be 10–60 seconds")
        while True:
            result = run_shadow_cycle()
            self.stdout.write(f"Shadow status: {result['status']}")
            if options["once"] or result["status"] in ("disabled", "paused"):
                return
            time.sleep(options["interval"])
