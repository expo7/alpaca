try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(*dargs, **dkwargs):
        def decorator(func):
            return func
        return decorator

from paper.engine.runner import StrategyRunner
from paper.services.execution import ExecutionEngine
from paper.models import PaperPortfolio


@shared_task
def run_strategy_engine():
    runner = StrategyRunner()
    runner.run()


@shared_task
def run_execution_engine():
    engine = ExecutionEngine()
    engine.run()


@shared_task
def snapshot_portfolios():
    from paper.models import PerformanceSnapshot
    from django.utils import timezone

    now = timezone.now()
    for portfolio in PaperPortfolio.objects.all():
        PerformanceSnapshot.objects.update_or_create(
            portfolio=portfolio,
            timestamp=now,
            defaults={
                "equity": portfolio.equity,
                "cash": portfolio.cash_balance,
                "realized_pnl": portfolio.realized_pnl,
                "unrealized_pnl": portfolio.unrealized_pnl,
                "leverage": 0,
                "metadata": {},
            },
        )


@shared_task
def recompute_leaderboards():
    from django.utils import timezone
    from paper.models import LeaderboardEntry

    now = timezone.now()
    LeaderboardEntry.objects.update(calculated_at=now)
