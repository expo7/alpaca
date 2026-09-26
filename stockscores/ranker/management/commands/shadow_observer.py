"""Standalone read-only sampler; never scheduled or enabled by primary processes."""

import time

from django.core.management.base import BaseCommand

from ranker.shadow_observer import run_observation_cycle


class Command(BaseCommand):
    help = "Observe private shadow setups using the second paper account's market data only."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--interval", type=int, default=15)

    def handle(self, *args, **options):
        if not options["once"] and not 10 <= options["interval"] <= 60:
            raise ValueError("Interval must be 10–60 seconds")
        while True:
            result = run_observation_cycle()
            self.stdout.write(f"Shadow observation status: {result['status']}")
            if options["once"]:
                return
            time.sleep(options["interval"])
