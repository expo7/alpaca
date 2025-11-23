from datetime import timedelta
from typing import Any, Dict

from celery import shared_task
from django.utils import timezone

from .backtest import run_basket_backtest
from .models import Bot

SCHEDULE_OFFSETS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def compute_next_run_at(bot: Bot, from_time=None):
    base = from_time or timezone.now()
    delta = SCHEDULE_OFFSETS.get(bot.schedule, timedelta(minutes=5))
    return base + delta


def run_bot_engine(bot: Bot) -> Dict[str, Any]:
    """Execute a single bot iteration using the existing backtester."""

    config = bot.bot_config.config if bot.bot_config else {}
    symbols = config.get("symbols") or []
    if not symbols:
        return {"status": "no_symbols"}

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)

    result = run_basket_backtest(
        tickers=symbols,
        start=str(config.get("start") or config.get("start_date") or start_date),
        end=str(config.get("end") or config.get("end_date") or end_date),
        benchmark=config.get("benchmark", "SPY"),
        initial_capital=float(config.get("capital", 10000.0)),
        rebalance_days=int(config.get("rebalance_days", 5)),
        top_n=config.get("top_n"),
        commission_per_trade=float(config.get("commission_per_trade", 0.0)),
        commission_pct=float(config.get("commission_pct", 0.0)),
        slippage_model=config.get("slippage_model", "none"),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        max_open_positions=config.get("max_open_positions"),
        max_per_position_pct=float(config.get("max_per_position_pct", 1.0)),
    )

    return {"status": "completed", "summary": result.summary}


@shared_task
def run_bot_once(bot_id: int):
    try:
        bot = Bot.objects.select_related("bot_config", "strategy_spec", "user").get(
            id=bot_id
        )
    except Bot.DoesNotExist:
        return {"status": "missing"}

    if bot.state != Bot.STATE_RUNNING:
        return {"status": "skipped"}

    now = timezone.now()
    status = "completed"
    try:
        run_bot_engine(bot)
    except Exception as exc:  # pragma: no cover - defensive guard
        status = f"error: {exc}"
    finally:
        bot.last_run_at = now
        bot.next_run_at = compute_next_run_at(bot, from_time=now)
        bot.save(update_fields=["last_run_at", "next_run_at"])

    return {"status": status, "bot_id": bot_id}


@shared_task
def schedule_due_bots():
    now = timezone.now()
    due = Bot.objects.filter(state=Bot.STATE_RUNNING, next_run_at__lte=now)
    for bot in due:
        run_bot_once.delay(bot.id)
    return {"enqueued": due.count()}
