import json
from django.core.management.base import BaseCommand
from ranker.option_strategies import capability, ACTIVE
from ranker.option_strategy_views import payload
from ranker.alpaca_paper import AlpacaPaperClient
from ranker.models import OptionStrategy


class Command(BaseCommand):
    help = "Read-only complex paper options capability and lifecycle report. Never submits orders."
    requires_system_checks = []

    def handle(self, *args, **options):
        result = {"capability": capability(AlpacaPaperClient()),
                  "strategies": [payload(s, True) for s in OptionStrategy.objects.filter(state__in=ACTIVE)]}
        self.stdout.write(json.dumps(result, default=str))
