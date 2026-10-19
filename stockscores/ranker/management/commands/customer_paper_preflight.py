"""Read-only deployment proof of private access, queue wiring and live heartbeat."""
import time

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from ranker.customer_paper_broker import credentials_ready, flag
from ranker.customer_paper_execution import worker_ready
from ranker.customer_paper_views import CustomerPaperConnectionView


class Command(BaseCommand):
    help = "Verify customer paper infrastructure without broker requests or customer credentials."

    def add_arguments(self, parser):
        parser.add_argument("--wait", type=int, default=0)
        parser.add_argument("--check-http", action="store_true")

    def handle(self, *args, **options):
        if not credentials_ready():
            raise CommandError("Customer paper encrypted storage is unavailable.")
        job = settings.CELERY_BEAT_SCHEDULE.get("customer-paper-dispatch", {})
        if job.get("options", {}).get("queue") != "customer-paper":
            raise CommandError("Customer paper dispatcher is not isolated to its dedicated queue.")
        deadline = time.monotonic() + min(45, max(0, options["wait"]))
        while not worker_ready() and time.monotonic() < deadline:
            time.sleep(1)
        if not worker_ready():
            raise CommandError("Dedicated customer worker heartbeat is missing; entries remain blocked.")
        factory = APIRequestFactory()
        view = CustomerPaperConnectionView.as_view()
        User = get_user_model()
        admin = User(pk=-1, is_superuser=True, is_staff=True)
        reader = User(pk=-2, is_staff=False, is_superuser=False)
        staff = User(pk=-3, is_staff=True, is_superuser=False)
        for user, expected in ((admin, 200), (reader, 200 if flag("CUSTOMER_PAPER_CUSTOMERS_ENABLED") else 403),
                               (staff, 200 if flag("CUSTOMER_PAPER_CUSTOMERS_ENABLED") else 403)):
            request = factory.get("/api/alpaca-paper/connection/")
            force_authenticate(request, user=user)
            result = view(request)
            if result.status_code != expected:
                raise CommandError("Customer paper role boundary check failed.")
        if options["check_http"]:
            result = requests.get("http://127.0.0.1:8000/api/alpaca-paper/connection/", timeout=8)
            if result.status_code not in (401, 403):
                raise CommandError("Anonymous customer connection endpoint is not protected.")
        self.stdout.write("Customer paper preflight PASS: encrypted storage, isolated queue, live worker, role boundary, no broker requests.")
