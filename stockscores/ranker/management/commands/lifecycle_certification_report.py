import json

from django.core.management.base import BaseCommand

from ranker.lifecycle_audit import certification_payload
from ranker.models import TradeLifecycleCertification


class Command(BaseCommand):
    help = "Return the latest read-only Quantelle lifecycle certification report."

    def add_arguments(self, parser):
        parser.add_argument("--signal-id", type=int)
        parser.add_argument("--limit", type=int, default=25)

    def handle(self, *args, **options):
        reports = TradeLifecycleCertification.objects.select_related("signal").order_by("-checked_at", "-id")
        if options["signal_id"]:
            reports = reports.filter(signal_id=options["signal_id"])
        limit = min(max(options["limit"], 1), 100)
        payload = [certification_payload(record) for record in reports[:limit]]
        self.stdout.write(json.dumps({"count": reports.count(), "results": payload}, default=str, indent=2))
