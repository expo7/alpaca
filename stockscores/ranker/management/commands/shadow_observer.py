"""Standalone read-only sampler; never scheduled or enabled by primary processes."""

import time
import fcntl
import signal
from contextlib import contextmanager


@contextmanager
def observation_guard():
    # Lock lives with the Python work, not the disposable host Docker client.
    with open('/tmp/quantelle-shadow-observer-process.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        def expired(signum, frame):
            raise SystemExit('Shadow observation exceeded 45 seconds')
        previous = signal.signal(signal.SIGALRM, expired)
        signal.alarm(45)
        try:
            yield True
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)


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
            with observation_guard() as acquired:
                if not acquired:
                    self.stdout.write('Shadow observation skipped: already running')
                    return
                result = run_observation_cycle()
            self.stdout.write(f"Shadow observation status: {result['status']}")
            if options["once"]:
                return
            time.sleep(options["interval"])
