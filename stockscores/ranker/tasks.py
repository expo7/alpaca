from datetime import timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from celery import shared_task
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .backtest import BacktestResult, run_basket_backtest
from .alpaca_paper import AlpacaPaperClient, PaperTradingError, load_paper_config
from .models import Bot, BacktestBatch, BacktestBatchRun, BotForwardRun, TradeSignal, TradeSignalUpdate
from .serializers import StrategySpecSerializer, BotConfigSerializer

SCHEDULE_OFFSETS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _filled_at(order):
    value = parse_datetime(order.get("filled_at") or "")
    return value or timezone.now()


def _record_update(signal, event_type, note, *, price=None, return_pct=None):
    TradeSignalUpdate.objects.create(
        signal=signal,
        event_type=event_type,
        note=note,
        price=price,
        return_pct=return_pct,
    )


def _reconcile_entry(signal, client):
    order = client.order(signal.paper_entry_order_id)
    status_value = order.get("status", "")[:32]
    signal.paper_order_status = status_value
    signal.paper_last_checked_at = timezone.now()
    if status_value == "filled":
        fill = _money(order["filled_avg_price"])
        signal.actual_entry = fill
        signal.status = TradeSignal.STATUS_OPEN
        signal.paper_filled_at = _filled_at(order)
        signal.paper_last_error = ""
        signal.save(update_fields=[
            "actual_entry", "status", "paper_order_status", "paper_filled_at",
            "paper_last_checked_at", "paper_last_error", "updated_at",
        ])
        _record_update(
            signal,
            "triggered",
            f"Alpaca paper order filled {signal.paper_quantity} contract(s) at ${fill}.",
            price=fill,
        )
        return "entry_filled"
    if status_value in {"canceled", "expired", "rejected", "replaced"}:
        signal.paper_last_error = f"Entry order ended with status: {status_value}"
    signal.save(update_fields=["paper_order_status", "paper_last_checked_at", "paper_last_error", "updated_at"])
    return status_value or "entry_pending"


def _reconcile_exit(signal, client):
    order = client.order(signal.paper_exit_order_id)
    status_value = order.get("status", "")[:32]
    signal.paper_order_status = status_value
    signal.paper_last_checked_at = timezone.now()
    if status_value == "filled":
        fill = _money(order["filled_avg_price"])
        entry = signal.actual_entry or Decimal("0")
        return_pct = _money(((fill - entry) / entry) * 100) if entry else None
        signal.final_exit = fill
        signal.realized_return_pct = return_pct
        signal.status = TradeSignal.STATUS_CLOSED
        signal.closed_at = _filled_at(order)
        signal.paper_last_error = ""
        signal.save(update_fields=[
            "final_exit", "realized_return_pct", "status", "closed_at", "paper_order_status",
            "paper_last_checked_at", "paper_last_error", "updated_at",
        ])
        _record_update(
            signal,
            "closed",
            f"Alpaca paper position closed at ${fill} ({signal.paper_exit_reason}).",
            price=fill,
            return_pct=return_pct,
        )
        return "exit_filled"
    if status_value in {"canceled", "expired", "rejected", "replaced"}:
        signal.paper_last_error = f"Exit order ended with status: {status_value}"
    signal.save(update_fields=["paper_order_status", "paper_last_checked_at", "paper_last_error", "updated_at"])
    return status_value or "exit_pending"


def _process_published_signal(signal, client, now, config):
    if signal.paper_entry_order_id:
        return _reconcile_entry(signal, client)
    if signal.entry_deadline and now.date() > signal.entry_deadline:
        signal.status = TradeSignal.STATUS_EXPIRED
        signal.paper_last_error = "Entry deadline passed before activation"
        signal.save(update_fields=["status", "paper_last_error", "updated_at"])
        _record_update(signal, "cancelled", "Alpaca paper setup expired before an entry was triggered.")
        return "expired"
    if signal.instrument_type not in {"call", "put"}:
        raise PaperTradingError("Initial executor supports long call and put signals only")
    stock = client.stock_quote(signal.symbol)
    trigger = signal.underlying_trigger_price
    if trigger is None:
        raise PaperTradingError("Signal has no underlying trigger price")
    crossed = stock["midpoint"] >= trigger if signal.trigger_direction == "above" else stock["midpoint"] <= trigger
    if not crossed:
        if signal.trigger_first_seen_at:
            signal.trigger_first_seen_at = None
            signal.save(update_fields=["trigger_first_seen_at", "updated_at"])
        return "waiting_for_trigger"
    if not signal.trigger_first_seen_at:
        signal.trigger_first_seen_at = now
        signal.save(update_fields=["trigger_first_seen_at", "updated_at"])
        return "confirming_trigger"
    if (now - signal.trigger_first_seen_at).total_seconds() < config.confirm_seconds:
        return "confirming_trigger"

    quote = client.option_quote(signal.contract_symbol)
    ask = quote["ask"]
    upper = signal.do_not_chase_price or signal.entry_high or signal.entry_low
    if ask < signal.entry_low or ask > upper:
        return "premium_outside_entry_range"
    if quote["spread_pct"] > config.max_spread_pct:
        return "spread_too_wide"
    open_count = TradeSignal.objects.filter(
        paper_execution_enabled=True,
        status=TradeSignal.STATUS_OPEN,
    ).count()
    if open_count >= config.max_open_positions:
        return "position_limit"

    order = client.submit_limit_order(
        symbol=signal.contract_symbol,
        quantity=signal.paper_quantity,
        side="buy",
        limit_price=_money(ask),
        client_order_id=f"quantelle-{signal.pk}-entry",
    )
    signal.paper_entry_order_id = order["id"]
    signal.paper_order_status = order.get("status", "submitted")[:32]
    signal.paper_submitted_at = now
    signal.paper_last_checked_at = now
    signal.paper_last_error = ""
    signal.save(update_fields=[
        "paper_entry_order_id", "paper_order_status", "paper_submitted_at",
        "paper_last_checked_at", "paper_last_error", "updated_at",
    ])
    _record_update(signal, "note", f"Submitted Alpaca paper buy limit for {signal.paper_quantity} contract(s) at ${_money(ask)}.", price=_money(ask))
    return "entry_submitted"


def _process_open_signal(signal, client, now):
    if signal.paper_exit_order_id:
        return _reconcile_exit(signal, client)
    quote = client.option_quote(signal.contract_symbol)
    bid = quote["bid"]
    stop = signal.current_stop or signal.initial_stop
    if bid <= stop:
        reason = "stop"
    elif bid >= signal.target_1:
        reason = "target_1"
    else:
        signal.paper_last_checked_at = now
        signal.save(update_fields=["paper_last_checked_at", "updated_at"])
        return "position_open"

    order = client.submit_limit_order(
        symbol=signal.contract_symbol,
        quantity=signal.paper_quantity,
        side="sell",
        limit_price=_money(bid),
        client_order_id=f"quantelle-{signal.pk}-exit",
    )
    signal.paper_exit_order_id = order["id"]
    signal.paper_exit_reason = reason
    signal.paper_order_status = order.get("status", "submitted")[:32]
    signal.paper_last_checked_at = now
    signal.paper_last_error = ""
    signal.save(update_fields=[
        "paper_exit_order_id", "paper_exit_reason", "paper_order_status",
        "paper_last_checked_at", "paper_last_error", "updated_at",
    ])
    _record_update(signal, "note", f"Submitted Alpaca paper sell limit at ${_money(bid)} ({reason}).", price=_money(bid))
    return "exit_submitted"


@shared_task
def run_paper_trade_executor():
    config = load_paper_config()
    if not config.enabled:
        return {"status": "disabled"}
    if not cache.add("ranker-paper-trade-executor-lock", "1", timeout=14):
        return {"status": "locked"}
    results = {}
    try:
        client = AlpacaPaperClient()
        if not client.clock().get("is_open"):
            return {"status": "market_closed"}
        now = timezone.now()
        signals = TradeSignal.objects.filter(
            paper_execution_enabled=True,
            status__in=[TradeSignal.STATUS_PUBLISHED, TradeSignal.STATUS_OPEN],
        ).order_by("published_at", "id")
        for signal in signals:
            try:
                if signal.status == TradeSignal.STATUS_PUBLISHED:
                    results[str(signal.pk)] = _process_published_signal(signal, client, now, config)
                else:
                    results[str(signal.pk)] = _process_open_signal(signal, client, now)
            except (PaperTradingError, KeyError, ValueError) as exc:
                signal.paper_last_error = str(exc)[:255]
                signal.paper_last_checked_at = now
                signal.save(update_fields=["paper_last_error", "paper_last_checked_at", "updated_at"])
                results[str(signal.pk)] = "error"
        return {"status": "ok", "signals": results}
    finally:
        cache.delete("ranker-paper-trade-executor-lock")


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
