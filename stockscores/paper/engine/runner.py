from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Dict, Any

from django.utils import timezone
from django.db import transaction

from paper.models import PaperPortfolio, Strategy, StrategyRunLog, PaperOrder
from paper.services.market_data import get_market_data_provider
from paper.services.execution import ExecutionEngine, ConditionEvaluator


@dataclass
class StrategyContext:
    strategy: Strategy
    portfolio: PaperPortfolio


class StrategyRunner:
    def __init__(self):
        self.market_data = get_market_data_provider()
        self.execution_engine = ExecutionEngine(data_provider=self.market_data)
        self.condition_evaluator = ConditionEvaluator(self.market_data)

    def run(self, strategies: Iterable[Strategy] | None = None):
        qs = strategies or Strategy.objects.filter(is_active=True).select_related("user")
        now = timezone.now()
        for strategy in qs:
            if not self._should_run(strategy, now):
                continue
            for portfolio in strategy.user.paper_portfolios.all():
                self.evaluate(strategy, portfolio, now)
            strategy.last_run_at = now
            strategy.save(update_fields=["last_run_at"])

    def dry_run(self, strategy: Strategy):
        matches = []
        cfg = strategy.config or {}
        symbols = cfg.get("symbols", [])
        rules = cfg.get("entry", {}).get("rules")
        now = timezone.now()
        for symbol in symbols:
            try:
                quote = self.market_data.get_quote(symbol)
            except Exception:
                continue
            if self._evaluate_node(rules, symbol, quote, now):
                matches.append(symbol)
        return matches

    def _should_run(self, strategy: Strategy, now):
        freq = (strategy.config or {}).get("frequency")
        if not freq or not strategy.last_run_at:
            return True
        delta = (now - strategy.last_run_at).total_seconds()
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "1d": 86400,
        }
        seconds = mapping.get(freq, 0)
        return delta >= seconds if seconds else True

    @transaction.atomic
    def evaluate(self, strategy: Strategy, portfolio: PaperPortfolio, now):
        cfg = strategy.config or {}
        symbols = cfg.get("symbols", [])
        entry_block = cfg.get("entry", {})
        exit_block = cfg.get("exit", {})
        generated_orders = []
        for symbol in symbols:
            try:
                quote = self.market_data.get_quote(symbol)
            except Exception:
                continue
            if self._evaluate_node(entry_block.get("rules"), symbol, quote, now):
                entry_template = entry_block.get("template")
                order_cfg = self._resolve_template(strategy, entry_template, entry_block.get("order", {}))
                if order_cfg:
                    order = self._create_order(order_cfg, strategy, portfolio, symbol)
                    if order:
                        generated_orders.append(order.id)
            if self._evaluate_node(exit_block.get("rules"), symbol, quote, now):
                exit_template = exit_block.get("template")
                exit_order_cfg = self._resolve_template(strategy, exit_template, exit_block.get("order", {}))
                if exit_order_cfg:
                    order = self._create_order(exit_order_cfg, strategy, portfolio, symbol)
                    if order:
                        generated_orders.append(order.id)
        StrategyRunLog.objects.create(
            strategy=strategy,
            portfolio=portfolio,
            run_at=now,
            context={"entry": entry_block, "exit": exit_block},
            generated_orders=generated_orders,
            status="success" if generated_orders else "skipped",
        )

    def _resolve_template(self, strategy, template_name, overrides):
        cfg = strategy.config or {}
        templates = cfg.get("order_templates", {})
        base = templates.get(template_name, {}) if template_name else {}
        merged = {**base, **(overrides or {})}
        return merged if merged else None

    def _create_order(self, order_cfg, strategy, portfolio, symbol):
        if not order_cfg:
            return None
        data = order_cfg.copy()
        quantity = data.pop("quantity_pct", None)
        if quantity:
            equity = portfolio.equity or portfolio.starting_balance
            data["quantity"] = (Decimal(str(quantity)) / Decimal("100")) * Decimal(str(equity))
        data.update(
            {
                "portfolio": portfolio,
                "strategy": strategy,
                "symbol": symbol,
                "status": "new",
            }
        )
        return PaperOrder.objects.create(**data)

    def _evaluate_node(self, node, symbol, quote, now):
        if not node:
            return False
        node_type = node.get("type", "rule")
        if node_type == "and":
            return all(
                self._evaluate_node(child, symbol, quote, now)
                for child in node.get("conditions", [])
            )
        if node_type == "or":
            return any(
                self._evaluate_node(child, symbol, quote, now)
                for child in node.get("conditions", [])
            )
        condition_type = node.get("condition", "indicator")
        payload = node.get("payload", {})
        temp_order = PaperOrder(
            condition_type=condition_type, condition_payload=payload, symbol=symbol
        )
        return self.condition_evaluator.satisfied(temp_order, quote, now)
