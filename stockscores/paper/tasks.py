try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(*dargs, **dkwargs):
        def decorator(func):
            return func
        return decorator

from paper.engine.runner import StrategyRunner
from paper.services.execution import ExecutionEngine
from paper.models import PaperPortfolio, Strategy
from django.utils import timezone


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
    from paper.services.leaderboards import recompute_all_leaderboards

    recompute_all_leaderboards()


@shared_task
def run_algo_slices():
    from django.utils import timezone
    from django.db.models import Q
    from paper.models import PaperOrder
    now = timezone.now()
    engine = ExecutionEngine()
    algo_orders = (
        PaperOrder.objects.filter(
            order_type__in=["algo_twap", "algo_vwap", "algo_pov"],
            status__in=["new", "working", "waiting", "part_filled"],
        )
        .filter(Q(algo_next_run_at__lte=now) | Q(algo_next_run_at__isnull=True))
        .select_related("portfolio")
        .order_by("algo_next_run_at", "created_at")
    )
    for order in algo_orders:
        engine.process_order(order)


@shared_task
def execute_strategy_task(strategy_id: int, portfolio_ids: list[int] | None = None, overrides=None):
    """
    Executes a single strategy immediately for the provided portfolio ids.
    This is the hook the API uses; Celery will run it asynchronously when available.
    """
    portfolio_ids = portfolio_ids or []
    overrides = overrides or {}
    runner = StrategyRunner()
    try:
        strategy = Strategy.objects.get(id=strategy_id)
    except Strategy.DoesNotExist:  # pragma: no cover - guarded by API
        return {"status": "missing"}
    now = timezone.now()
    portfolios = PaperPortfolio.objects.filter(id__in=portfolio_ids, user=strategy.user)
    for portfolio in portfolios:
        runner.evaluate(strategy, portfolio, now)
    return {"status": "completed", "strategy_id": strategy_id, "portfolios": list(portfolios.values_list("id", flat=True))}
