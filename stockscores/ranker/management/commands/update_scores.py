from django.core.management.base import BaseCommand
from ranker.services import rank_symbols

DEFAULT_TICKERS = ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","AVGO","NFLX"]

class Command(BaseCommand):
    help = "Compute & store scores for a default (or provided) ticker universe"

    def add_arguments(self, parser):
        parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
        parser.add_argument("--tech_weight", type=float, default=0.5)
        parser.add_argument("--fund_weight", type=float, default=0.5)

    def handle(self, *args, **opts):
        tickers = opts["tickers"]
        tw = opts["tech_weight"]
        fw = opts["fund_weight"]
        objs, errors = rank_symbols(tickers, tech_weight=tw, fund_weight=fw)
        if errors:
            self.stdout.write(self.style.WARNING(f"Errors: {errors}"))
        self.stdout.write(self.style.SUCCESS(f"Updated {len(objs)} scores"))
