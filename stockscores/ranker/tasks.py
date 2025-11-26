from datetime import timedelta, datetime
from typing import Any, Dict

from celery import shared_task
from django.db import models, transaction
from django.utils import timezone

from .backtest import BacktestResult, run_basket_backtest
from .models import Bot, BacktestBatch, BacktestBatchRun, BotForwardRun
from .serializers import StrategySpecSerializer, BotConfigSerializer

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

    if bot.mode == Bot.MODE_PAPER:
        return run_forward_bot(bot)

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
        max_open_positions=int(config.get("max_open_positions"))
        if config.get("max_open_positions") is not None
        else None,
        max_per_position_pct=float(config.get("max_per_position_pct", 1.0)),
        strategy_spec=bot.strategy_spec.spec if bot.strategy_spec else None,
    )

    return {"status": "completed", "summary": result.summary}


def _forward_start(bot, today):
    cfg = bot.bot_config.config if bot.bot_config else {}
    if bot.forward_start_date:
        return bot.forward_start_date
    start_cfg = cfg.get("start_date") or cfg.get("start")
    if start_cfg:
        try:
            return datetime.fromisoformat(str(start_cfg)).date()
        except Exception:
            pass
    return today - timedelta(days=365)


def run_forward_bot(bot: Bot) -> Dict[str, Any]:
    cfg = bot.bot_config.config if bot.bot_config else {}
    symbols = cfg.get("symbols") or []
    if not symbols:
        return {"status": "no_symbols"}
    today = timezone.now().date()
    if bot.last_forward_run_at and bot.last_forward_run_at >= today:
        return {"status": "up_to_date"}
    start_date = _forward_start(bot, today)

    result = run_basket_backtest(
        tickers=symbols,
        start=str(start_date),
        end=str(today),
        benchmark=cfg.get("benchmark", "SPY"),
        initial_capital=float(cfg.get("capital", 10000.0)),
        rebalance_days=int(cfg.get("rebalance_days", 5)),
        top_n=cfg.get("top_n"),
        commission_per_trade=float(cfg.get("commission_per_trade", 0.0)),
        commission_pct=float(cfg.get("commission_pct", 0.0)),
        slippage_model=cfg.get("slippage_model", "none"),
        slippage_bps=float(cfg.get("slippage_bps", 0.0)),
        max_open_positions=int(cfg.get("max_open_positions"))
        if cfg.get("max_open_positions") is not None
        else None,
        max_per_position_pct=float(cfg.get("max_per_position_pct", 1.0)),
        strategy_spec=bot.strategy_spec.spec if bot.strategy_spec else None,
    )
    summary = result.summary or {}
    equity = summary.get("final_value") or summary.get("final_equity") or 0.0
    cash = summary.get("final_cash", 0.0)
    positions_value = summary.get("final_positions_value") or (equity - cash)
    pnl = summary.get("total_return", 0.0)
    num_trades = summary.get("num_trades", len(summary.get("trades", []) or []))
    with transaction.atomic():
        BotForwardRun.objects.update_or_create(
            bot=bot,
            as_of=today,
            defaults={
                "equity": equity,
                "cash": cash,
                "positions_value": positions_value,
                "pnl": pnl,
                "num_trades": num_trades,
                "stats": summary,
            },
        )
        bot.last_forward_run_at = today
        if not bot.forward_start_date:
            bot.forward_start_date = start_date
        bot.save(update_fields=["last_forward_run_at", "forward_start_date"])
    return {"status": "completed", "equity": equity, "num_trades": num_trades}


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
    due = Bot.objects.filter(state=Bot.STATE_RUNNING).filter(
        (models.Q(next_run_at__lte=now)) | models.Q(next_run_at__isnull=True)
    )
    today = now.date()
    for bot in due:
        if bot.mode == Bot.MODE_PAPER and bot.last_forward_run_at and bot.last_forward_run_at >= today:
            continue
        run_bot_once.delay(bot.id)
    return {"enqueued": due.count()}


def _apply_param_overrides(strategy_data: dict, bot_data: dict, params: dict) -> tuple[dict, dict]:
    strat_copy = {**strategy_data}
    strat_copy["parameters"] = {**(strategy_data.get("parameters") or {})}
    for key, val in params.items():
        if key in strat_copy["parameters"]:
            strat_copy["parameters"][key] = {**strat_copy["parameters"][key], "default": val}
        elif key in bot_data:
            bot_data[key] = val
        else:
            overrides = bot_data.get("overrides") or {}
            overrides[key] = val
            bot_data["overrides"] = overrides
    return strat_copy, bot_data


@shared_task
def run_backtest_batch(batch_id: int) -> Dict[str, Any]:
    try:
        batch = BacktestBatch.objects.prefetch_related("runs").get(id=batch_id)
    except BacktestBatch.DoesNotExist:
        return {"status": "missing"}

    if batch.status == BacktestBatch.STATUS_PENDING:
        batch.status = BacktestBatch.STATUS_RUNNING
        batch.save(update_fields=["status"])

    config = batch.config or {}
    strategy_data = config.get("strategy") or {}
    bot_data_base = config.get("bot") or {}
    start_date = config.get("start_date") or config.get("start")
    end_date = config.get("end_date") or config.get("end")

    any_failed = False
    completed = 0

    for run in batch.runs.filter(status__in=[BacktestBatchRun.STATUS_PENDING, BacktestBatchRun.STATUS_RUNNING]).order_by("index"):
        run.status = BacktestBatchRun.STATUS_RUNNING
        run.save(update_fields=["status"])
        try:
            strat_payload, bot_payload = _apply_param_overrides(
                strategy_data, bot_data_base.copy(), run.params or {}
            )
            strat_serializer = StrategySpecSerializer(data=strat_payload)
            bot_serializer = BotConfigSerializer(data=bot_payload)
            strat_serializer.is_valid(raise_exception=True)
            bot_serializer.is_valid(raise_exception=True)
            bot_cfg = bot_serializer.validated_data

            result: BacktestResult = run_basket_backtest(
                tickers=bot_cfg["symbols"],
                start=str(start_date),
                end=str(end_date),
                benchmark=bot_cfg.get("benchmark", "SPY"),
                initial_capital=float(bot_cfg.get("capital", 10000.0)),
                rebalance_days=int(bot_cfg.get("rebalance_days", 5)),
                top_n=bot_cfg.get("top_n"),
                commission_per_trade=float(bot_cfg.get("commission_per_trade", 0.0)),
                commission_pct=float(bot_cfg.get("commission_pct", 0.0)),
                slippage_model=bot_cfg.get("slippage_model", "none"),
                slippage_bps=float(bot_cfg.get("slippage_bps", 0.0)),
                max_open_positions=bot_cfg.get("max_open_positions"),
                max_per_position_pct=float(bot_cfg.get("max_per_position_pct", 1.0)),
                strategy_spec=strat_serializer.validated_data,
            )
            run.stats = result.summary
            run.status = BacktestBatchRun.STATUS_COMPLETED
            completed += 1
        except Exception as exc:  # pragma: no cover
            run.error = str(exc)
            run.status = BacktestBatchRun.STATUS_FAILED
            any_failed = True
        run.save(update_fields=["status", "stats", "error"])

    if any_failed:
        batch.status = BacktestBatch.STATUS_FAILED
    elif completed == batch.runs.count():
        batch.status = BacktestBatch.STATUS_COMPLETED
    batch.save(update_fields=["status"])

    return {"status": batch.status, "completed": completed, "total": batch.runs.count()}
