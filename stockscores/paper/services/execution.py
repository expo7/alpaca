from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from typing import Dict, Optional

import pandas as pd
from ta.momentum import RSIIndicator

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from paper.models import PaperOrder, PaperPortfolio, PaperPosition, PaperTrade
from ranker.models import StockScore
from .market_data import (
    MarketDataProvider,
    Quote,
    get_market_data_provider,
)


@dataclass
class FillResult:
    filled: bool
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    notes: dict = field(default_factory=dict)


MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
WINDOW_MINUTES = 5


def _within_window(now, target: time) -> bool:
    local_now = timezone.localtime(now)
    target_dt = local_now.replace(
        hour=target.hour, minute=target.minute, second=0, microsecond=0
    )
    delta_minutes = abs((local_now - target_dt).total_seconds()) / 60
    return delta_minutes <= WINDOW_MINUTES


class IndicatorService:
    TIMEFRAME_MAP = {
        "1d": ("6mo", "1d"),
        "1h": ("60d", "60m"),
        "30m": ("30d", "30m"),
        "15m": ("30d", "15m"),
        "5m": ("30d", "5m"),
        "1m": ("7d", "1m"),
    }

    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider
        self.cache: Dict[tuple, pd.DataFrame] = {}
        self.score_cache: Dict[str, dict] = {}

    def get_value(self, symbol: str, payload: dict) -> Optional[Decimal]:
        indicator = payload.get("indicator")
        source = payload.get("source", "indicator")
        if source == "scorer":
            return self._value_from_scorer(symbol, payload)
        if not indicator:
            return None
        period, interval = self._resolve_timeframe(payload)
        window = payload.get("window", 14)
        key = (symbol, period, interval)
        df = self.cache.get(key)
        if df is None:
            df = self.data_provider.get_history_period(
                symbol, period=period, interval=interval
            )
            self.cache[key] = df
        if df.empty:
            return None
        closes = df["Close"]
        if indicator.lower() == "sma":
            return Decimal(str(closes.tail(window).mean()))
        if indicator.lower() == "ema":
            return Decimal(str(closes.ewm(span=window).mean().iloc[-1]))
        if indicator.lower() == "rsi":
            rsi = RSIIndicator(closes, window)
            return Decimal(str(rsi.rsi().iloc[-1]))
        if indicator.lower() == "volume":
            vols = df["Volume"]
            return Decimal(str(vols.tail(window).mean()))
        return None

    def _resolve_timeframe(self, payload: dict):
        timeframe = payload.get("timeframe")
        if timeframe and timeframe in self.TIMEFRAME_MAP:
            return self.TIMEFRAME_MAP[timeframe]
        period = payload.get("period", "3mo")
        interval = payload.get("interval", "1d")
        return period, interval

    def _value_from_scorer(self, symbol: str, payload: dict) -> Optional[Decimal]:
        symbol = symbol.upper()
        score = self.score_cache.get(symbol)
        if score is None:
            latest = (
                StockScore.objects.filter(symbol=symbol)
                .order_by("-asof")
                .values("final_score", "tech_score", "fundamental_score", "components")
                .first()
            )
            if not latest:
                return None
            self.score_cache[symbol] = latest
            score = latest
        field = payload.get("field", "final_score")
        parts = field.split(".")
        value = score
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)
        return Decimal(str(value)) if value is not None else None


class ConditionEvaluator:
    OPERATORS = {
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
    }

    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider
        self.indicator_service = IndicatorService(data_provider)

    def satisfied(self, order: PaperOrder, quote: Quote, now) -> bool:
        condition_type = order.condition_type or "none"
        payload = order.condition_payload or {}
        if condition_type == "none":
            return True
        if condition_type == "price":
            operator = payload.get("operator", "gte")
            value = payload.get("value")
            if value is None:
                return True
            comparator = self.OPERATORS.get(operator, self.OPERATORS["gte"])
            return comparator(Decimal(str(quote.price)), Decimal(str(value)))
        if condition_type == "time":
            ts = payload.get("timestamp")
            if not ts:
                return True
            try:
                target = timezone.datetime.fromisoformat(ts)
                if timezone.is_naive(target):
                    target = timezone.make_aware(target, timezone.utc)
            except Exception:
                return True
            return now >= target
        if condition_type == "indicator":
            value = self.indicator_service.get_value(order.symbol, payload)
            threshold = payload.get("value")
            if value is None or threshold is None:
                return True
            comparator = self.OPERATORS.get(
                payload.get("operator", "gte"), self.OPERATORS["gte"]
            )
            return comparator(value, Decimal(str(threshold)))
        if condition_type == "cross_symbol":
            target_symbol = payload.get("symbol", order.symbol)
            operator = payload.get("operator", "gte")
            try:
                base_quote = (
                    quote
                    if target_symbol == order.symbol
                    else self.data_provider.get_quote(target_symbol)
                )
            except Exception:
                return True
            comparator = self.OPERATORS.get(operator, self.OPERATORS["gte"])
            compare_value = payload.get("value")
            if payload.get("compare_symbol"):
                try:
                    compare_quote = self.data_provider.get_quote(
                        payload["compare_symbol"]
                    )
                    compare_value = compare_quote.price
                except Exception:
                    return True
            if compare_value is None:
                compare_value = quote.price
            return comparator(
                Decimal(str(base_quote.price)), Decimal(str(compare_value))
            )
        if condition_type in {"and_group", "or_group"}:
            conditions = payload.get("conditions", [])
            results = []
            original_type = order.condition_type
            original_payload = order.condition_payload
            for cond in conditions:
                order.condition_type = cond.get("type", "none")
                order.condition_payload = cond.get("payload", {})
                results.append(self.satisfied(order, quote, now))
            order.condition_type = original_type
            order.condition_payload = original_payload
            return all(results) if condition_type == "and_group" else any(results)
        if condition_type == "volume":
            operator = payload.get("operator", "gte")
            target = payload.get("value")
            comparator = self.OPERATORS.get(operator, self.OPERATORS["gte"])
            if payload.get("basis") == "average":
                avg = self.indicator_service.get_value(
                    order.symbol,
                    {
                        "indicator": "volume",
                        "window": payload.get("window", 20),
                        "period": payload.get("period", "3mo"),
                        "interval": payload.get("interval", "1d"),
                    },
                )
                if avg is None or target is None:
                    return True
                return comparator(avg, Decimal(str(target)))
            if quote.volume is None or target is None:
                return True
            return comparator(Decimal(str(quote.volume)), Decimal(str(target)))
        return True


class OrderHandler:
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        raise NotImplementedError


class MarketOrderHandler(OrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if order.status not in {"new", "working", "part_filled"}:
            return None
        price = Decimal(str(quote.price))
        qty, remaining_after = self._resolve_quantity(order, price)
        if qty <= 0:
            return None
        return FillResult(
            filled=True,
            quantity=qty,
            price=price,
            remaining=remaining_after,
        )

    @staticmethod
    def _resolve_quantity(order: PaperOrder, price: Decimal) -> tuple[Decimal, Decimal]:
        total_qty = order.quantity
        if total_qty is None and order.notional:
            total_qty = Decimal(str(order.notional)) / price
            order.quantity = total_qty
            order.save(update_fields=["quantity"])
        if total_qty is None:
            return Decimal("0"), Decimal("0")
        remaining = total_qty - order.filled_quantity
        if remaining <= 0:
            return Decimal("0"), Decimal("0")
        if order.reserve_quantity:
            visible = min(order.reserve_quantity, remaining)
            return visible, remaining - visible
        return remaining, Decimal("0")


class LimitOrderHandler(MarketOrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if order.status not in {"new", "working", "part_filled"} or order.limit_price is None:
            return None
        price = Decimal(str(quote.price))
        limit_price = Decimal(str(order.limit_price))
        should_fill = (
            price <= limit_price if order.side == "buy" else price >= limit_price
        )
        if not should_fill:
            order.status = "working"
            order.save(update_fields=["status"])
            return None
        qty, remaining_after = self._resolve_quantity(order, price)
        return FillResult(
            filled=True, quantity=qty, price=limit_price, remaining=remaining_after
        )


class StopOrderHandler(MarketOrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if order.status not in {"new", "working", "part_filled"} or order.stop_price is None:
            return None
        price = Decimal(str(quote.price))
        stop_price = Decimal(str(order.stop_price))
        triggered = (
            price >= stop_price if order.side == "buy" else price <= stop_price
        )
        if not triggered:
            order.status = "working"
            order.save(update_fields=["status"])
            return None
        qty, remaining_after = self._resolve_quantity(order, price)
        return FillResult(
            filled=True, quantity=qty, price=price, remaining=remaining_after
        )


class StopLimitOrderHandler(MarketOrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if (
            order.status not in {"new", "working", "part_filled"}
            or order.stop_price is None
            or order.limit_price is None
        ):
            return None
        price = Decimal(str(quote.price))
        stop_price = Decimal(str(order.stop_price))
        limit_price = Decimal(str(order.limit_price))
        triggered = (
            price >= stop_price if order.side == "buy" else price <= stop_price
        )
        if not triggered:
            order.status = "working"
            order.save(update_fields=["status"])
            return None
        should_fill = (
            price <= limit_price if order.side == "buy" else price >= limit_price
        )
        if not should_fill:
            return None
        qty, remaining_after = self._resolve_quantity(order, price)
        return FillResult(
            filled=True, quantity=qty, price=limit_price, remaining=remaining_after
        )


class TrailingStopHandler(MarketOrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if order.status not in {"new", "working", "part_filled"}:
            return None
        price = Decimal(str(quote.price))
        if order.order_type == "trailing_amount" and order.trail_amount:
            trail = Decimal(str(order.trail_amount))
        elif order.order_type == "trailing_percent" and order.trail_percent:
            trail = price * Decimal(str(order.trail_percent)) / Decimal("100")
        else:
            return None

        ref_price = Decimal(str(order.stop_price or price))
        if order.side == "sell":
            trigger_price = ref_price - trail
            if price <= trigger_price:
                qty, remaining_after = self._resolve_quantity(order, price)
                return FillResult(
                    filled=True, quantity=qty, price=price, remaining=remaining_after
                )
        else:
            trigger_price = ref_price + trail
            if price >= trigger_price:
                qty, remaining_after = self._resolve_quantity(order, price)
                return FillResult(
                    filled=True, quantity=qty, price=price, remaining=remaining_after
                )
        order.notes["trail_ref"] = str(ref_price)
        order.save(update_fields=["notes"])
        return None


class TrailingStopLimitHandler(TrailingStopHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        result = super().maybe_fill(order, portfolio, quote, now)
        if result and result.filled and order.limit_price:
            result.price = Decimal(str(order.limit_price))
        return result


class SessionOrderHandler(MarketOrderHandler):
    target = MARKET_CLOSE

    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if not _within_window(now, self.target):
            order.status = "working"
            order.save(update_fields=["status"])
            return None
        return super().maybe_fill(order, portfolio, quote, now)


class MarketOpenHandler(SessionOrderHandler):
    target = MARKET_OPEN


class MarketCloseHandler(SessionOrderHandler):
    target = MARKET_CLOSE


class LimitSessionHandler(LimitOrderHandler):
    target = MARKET_CLOSE

    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        if not _within_window(now, self.target):
            order.status = "working"
            order.save(update_fields=["status"])
            return None
        return super().maybe_fill(order, portfolio, quote, now)


class LimitOpenHandler(LimitSessionHandler):
    target = MARKET_OPEN


class LimitCloseHandler(LimitSessionHandler):
    target = MARKET_CLOSE


class PeggedOrderHandler(LimitOrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        price = Decimal(str(quote.price))
        if order.order_type == "pegged_mid" and quote.bid and quote.ask:
            price = (Decimal(str(quote.bid)) + Decimal(str(quote.ask))) / Decimal("2")
        elif order.order_type == "pegged_primary" and quote.bid:
            price = Decimal(str(quote.bid))
        offset = Decimal(str(order.pegged_offset or Decimal("0")))
        if order.side == "buy":
            order.limit_price = price + offset
        else:
            order.limit_price = price - offset
        order.save(update_fields=["limit_price"])
        return super().maybe_fill(order, portfolio, quote, now)


class NoopHandler(OrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        return None


class BracketOrderHandler(NoopHandler):
    pass


class OCOOrderHandler(NoopHandler):
    pass


class AlgoOrderHandler(OrderHandler):
    def maybe_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, quote: Quote, now
    ) -> Optional[FillResult]:
        params = order.algo_params or {}
        if order.order_type == "algo_twap":
            return self._handle_twap(order, params, quote, now)
        if order.order_type == "algo_vwap":
            return self._handle_vwap(order, params, quote, now)
        if order.order_type == "algo_pov":
            return self._handle_pov(order, params, quote, now)
        return None

    def _handle_twap(self, order, params, quote, now):
        slices = params.get("slices", 10)
        interval_minutes = params.get("interval_minutes", 5)
        last_fill = order.notes.get("algo_last_fill")
        if last_fill:
            last_dt = datetime.fromisoformat(last_fill)
            if (now - last_dt).total_seconds() < interval_minutes * 60:
                return None
        total = order.quantity or Decimal("0")
        if total <= 0:
            return None
        slice_qty = total / Decimal(slices)
        order.notes["algo_last_fill"] = now.isoformat()
        order.save(update_fields=["notes"])
        remaining = max(total - order.filled_quantity - slice_qty, Decimal("0"))
        return FillResult(
            filled=True,
            quantity=min(slice_qty, total - order.filled_quantity),
            price=Decimal(str(quote.price)),
            remaining=remaining,
        )

    def _handle_vwap(self, order, params, quote, now):
        participation = Decimal(str(params.get("participation", 0.1)))
        total = order.quantity or Decimal("0")
        if total <= 0:
            return None
        slice_qty = total * participation
        remaining = max(total - order.filled_quantity - slice_qty, Decimal("0"))
        return FillResult(
            filled=True,
            quantity=min(slice_qty, total - order.filled_quantity),
            price=Decimal(str(quote.price)),
            remaining=remaining,
        )

    def _handle_pov(self, order, params, quote, now):
        rate = Decimal(str(params.get("participation", 0.1)))
        volume = Decimal(str(quote.volume or 0))
        total = order.quantity or Decimal("0")
        if volume <= 0 or total <= 0:
            return None
        target = volume * rate
        remaining = max(total - order.filled_quantity - target, Decimal("0"))
        return FillResult(
            filled=True,
            quantity=min(target, total - order.filled_quantity),
            price=Decimal(str(quote.price)),
            remaining=remaining,
        )


class ExecutionEngine:
    def __init__(self, data_provider: MarketDataProvider | None = None):
        self.data_provider = data_provider or get_market_data_provider()
        self.handlers: Dict[str, OrderHandler] = {
            "market": MarketOrderHandler(),
            "limit": LimitOrderHandler(),
            "stop": StopOrderHandler(),
            "stop_limit": StopLimitOrderHandler(),
            "trailing_amount": TrailingStopHandler(),
            "trailing_percent": TrailingStopHandler(),
            "trailing_limit": TrailingStopLimitHandler(),
            "market_open": MarketOpenHandler(),
            "market_close": MarketCloseHandler(),
            "limit_open": LimitOpenHandler(),
            "limit_close": LimitCloseHandler(),
            "pegged_mid": PeggedOrderHandler(),
            "pegged_primary": PeggedOrderHandler(),
            "hidden_limit": LimitOrderHandler(),
            "iceberg": LimitOrderHandler(),
            "bracket": BracketOrderHandler(),
            "oco": OCOOrderHandler(),
            "oto": NoopHandler(),
            "otoco": NoopHandler(),
            "algo_vwap": AlgoOrderHandler(),
            "algo_twap": AlgoOrderHandler(),
            "algo_pov": AlgoOrderHandler(),
        }
        self.condition_evaluator = ConditionEvaluator(self.data_provider)
        self.backtest_mode = getattr(settings, "PAPER_BACKTEST_FILL_MODE", "live")
        self.slippage_bps = getattr(settings, "PAPER_SLIPPAGE_BPS", Decimal("0"))
        self.fees_per_share = getattr(
            settings, "PAPER_FEES_PER_SHARE", Decimal("0")
        )
        self.flat_commission = getattr(
            settings, "PAPER_FLAT_COMMISSION", Decimal("0")
        )
        self.simulation_clock = getattr(settings, "PAPER_SIMULATION_CLOCK", "")
        self._override_now: Optional[datetime] = None

    def run(self, simulation_time: Optional[datetime] = None):
        self._override_now = simulation_time or self._parse_simulation_clock()
        for portfolio in PaperPortfolio.objects.all():
            self.process_portfolio(portfolio)
        self._override_now = None

    def _parse_simulation_clock(self) -> Optional[datetime]:
        if not self.simulation_clock:
            return None
        try:
            parsed = datetime.fromisoformat(self.simulation_clock)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.utc)
            return parsed
        except Exception:
            return None

    def _current_time(self):
        return self._override_now or timezone.now()

    def _get_quote(self, symbol: str) -> Quote:
        if self.backtest_mode == "next_open":
            history = self.data_provider.get_history_period(symbol, period="5d", interval="1d")
            if not history.empty:
                row = history.iloc[-1]
                return Quote(
                    symbol=symbol,
                    price=float(row["Open"]),
                    timestamp=self._current_time(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
        return self.data_provider.get_quote(symbol)

    def process_portfolio(self, portfolio: PaperPortfolio):
        orders = (
            portfolio.orders.filter(status__in=["new", "working", "part_filled"])
            .select_related("portfolio")
            .order_by("created_at")
        )
        now = self._current_time()
        for order in orders:
            if not self._tif_allows_processing(order, now):
                continue
            if not order.extended_hours and not self._in_regular_hours(now):
                continue
            handler = self.handlers.get(order.order_type, NoopHandler())
            try:
                quote = self._get_quote(order.symbol)
            except Exception:
                continue
            if not self.condition_evaluator.satisfied(order, quote, now):
                continue
            result = handler.maybe_fill(order, portfolio, quote, now)
            if result and result.filled:
                self._apply_fill(order, portfolio, result)
                if order.tif == "fok" and result.remaining > 0:
                    order.status = "canceled"
                    order.save(update_fields=["status"])
            elif order.tif in {"ioc", "fok"}:
                order.status = "canceled"
                order.save(update_fields=["status"])

    @transaction.atomic
    def _apply_fill(
        self, order: PaperOrder, portfolio: PaperPortfolio, result: FillResult
    ):
        fill_price = result.price
        slippage_multiplier = (
            Decimal("1") + (self.slippage_bps / Decimal("10000"))
            if order.side == "buy"
            else Decimal("1") - (self.slippage_bps / Decimal("10000"))
        )
        fill_price = fill_price * slippage_multiplier
        qty = result.quantity
        cost = qty * fill_price
        entry_avg_price = None
        if order.side == "buy":
            fees = (qty * self.fees_per_share) + self.flat_commission + result.fees
            portfolio.cash_balance -= cost + fees
            position, _ = PaperPosition.objects.get_or_create(
                portfolio=portfolio,
                symbol=order.symbol.upper(),
                defaults={
                    "quantity": Decimal("0"),
                    "avg_price": fill_price,
                    "market_value": Decimal("0"),
                    "unrealized_pnl": Decimal("0"),
                },
            )
            entry_avg_price = position.avg_price
            total_qty = position.quantity + qty
            if total_qty > 0:
                position.avg_price = (
                    (position.quantity * position.avg_price) + cost
                ) / total_qty
            position.quantity = total_qty
            position.market_value = total_qty * fill_price
            position.unrealized_pnl = position.market_value - (total_qty * position.avg_price)
            position.save()
        else:
            fees = (qty * self.fees_per_share) + self.flat_commission + result.fees
            portfolio.cash_balance += cost - fees
            try:
                position = PaperPosition.objects.get(
                    portfolio=portfolio, symbol=order.symbol.upper()
                )
            except PaperPosition.DoesNotExist:
                position = None
            if position:
                entry_avg_price = position.avg_price
                position.quantity -= qty
                position.market_value = position.quantity * fill_price
                position.unrealized_pnl = position.market_value - (
                    position.quantity * position.avg_price
                )
                position.save()

        trade = PaperTrade.objects.create(
            order=order,
            portfolio=portfolio,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=qty,
            price=fill_price,
            fees=result.fees,
            slippage=result.slippage,
            strategy=order.strategy,
            realized_pnl=Decimal("0"),
        )
        prev_filled = order.filled_quantity
        new_total_filled = prev_filled + qty
        if prev_filled > 0 and order.average_fill_price:
            order.average_fill_price = (
                (order.average_fill_price * prev_filled) + (fill_price * qty)
            ) / new_total_filled
        else:
            order.average_fill_price = fill_price
        order.filled_quantity = new_total_filled
        total_qty = order.quantity or new_total_filled
        remaining_after_fill = total_qty - new_total_filled
        order.status = "part_filled" if remaining_after_fill > 0 else "filled"
        order.save(
            update_fields=["status", "filled_quantity", "average_fill_price"]
        )
        total_market = (
            portfolio.positions.aggregate(total=Sum("market_value"))["total"]
            or Decimal("0")
        )
        portfolio.equity = portfolio.cash_balance + total_market
        portfolio.unrealized_pnl = (
            portfolio.positions.aggregate(total=Sum("unrealized_pnl"))["total"]
            or Decimal("0")
        )
        if order.side == "sell" and entry_avg_price is not None:
            trade.realized_pnl = (fill_price - entry_avg_price) * qty
            portfolio.realized_pnl += trade.realized_pnl
            trade.save(update_fields=["realized_pnl"])
        self._handle_parent_child(order)
        portfolio.save(
            update_fields=[
                "cash_balance",
                "equity",
                "unrealized_pnl",
                "realized_pnl",
            ]
        )

    def _handle_parent_child(self, order: PaperOrder):
        if order.children.exists():
            order.children.filter(status="new").update(status="working")
        parent = order.parent
        if not parent:
            return
        if parent.order_type == "bracket":
            parent.children.exclude(id=order.id).update(status="canceled")
        if parent.order_type == "oco":
            parent.children.exclude(id=order.id).update(status="canceled")
        if parent.order_type == "otoco":
            parent.children.exclude(id=order.id).update(status="canceled")
        if parent.order_type == "oto":
            parent.children.filter(status="new").update(status="working")

    def _tif_allows_processing(self, order: PaperOrder, now) -> bool:
        if order.tif == "day":
            if timezone.localdate(now) > timezone.localdate(order.created_at):
                order.status = "expired"
                order.save(update_fields=["status"])
                return False
        if order.tif == "gtd" and order.tif_date and now > order.tif_date:
            order.status = "expired"
            order.save(update_fields=["status"])
            return False
        return True

    def _in_regular_hours(self, now) -> bool:
        local = timezone.localtime(now).time()
        return MARKET_OPEN <= local <= MARKET_CLOSE
