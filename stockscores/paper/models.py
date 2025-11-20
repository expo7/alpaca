from django.db import models
from django.conf import settings
from decimal import Decimal

ORDER_TYPE_CHOICES = [
    ("market", "Market"),
    ("limit", "Limit"),
    ("stop", "Stop"),
    ("stop_limit", "Stop Limit"),
    ("trailing_amount", "Trailing Stop (Amount)"),
    ("trailing_percent", "Trailing Stop (Percent)"),
    ("trailing_limit", "Trailing Stop Limit"),
    ("market_close", "Market on Close"),
    ("market_open", "Market on Open"),
    ("limit_close", "Limit on Close"),
    ("limit_open", "Limit on Open"),
    ("pegged_mid", "Pegged to Midpoint"),
    ("pegged_primary", "Primary Peg"),
    ("hidden_limit", "Hidden Limit"),
    ("iceberg", "Iceberg / Reserve"),
    ("bracket", "Bracket Entry"),
    ("oco", "One Cancels Other"),
    ("oto", "One Triggers Other"),
    ("otoco", "One Triggers OCO"),
    ("algo_vwap", "Algo VWAP"),
    ("algo_twap", "Algo TWAP"),
    ("algo_pov", "Algo Participation"),
]

ORDER_STATUS_CHOICES = [
    ("new", "NEW"),
    ("working", "WORKING"),
    ("part_filled", "PARTIALLY FILLED"),
    ("filled", "FILLED"),
    ("canceled", "CANCELED"),
    ("expired", "EXPIRED"),
    ("rejected", "REJECTED"),
]


class PaperPortfolio(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="paper_portfolios",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=64)
    base_currency = models.CharField(max_length=8, default="USD")
    starting_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("100000")
    )
    cash_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("100000")
    )
    equity = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("100000")
    )
    realized_pnl = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0")
    )
    unrealized_pnl = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0")
    )
    status = models.CharField(
        max_length=16, choices=[("active", "Active"), ("archived", "Archived")]
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PaperPosition(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, related_name="positions", on_delete=models.CASCADE
    )
    symbol = models.CharField(max_length=16)
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    avg_price = models.DecimalField(max_digits=18, decimal_places=4)
    market_value = models.DecimalField(max_digits=18, decimal_places=2)
    unrealized_pnl = models.DecimalField(max_digits=18, decimal_places=2)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("portfolio", "symbol")


class Strategy(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="paper_strategies",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_public_template = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PaperOrder(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, related_name="orders", on_delete=models.CASCADE
    )
    strategy = models.ForeignKey(
        "Strategy", blank=True, null=True, on_delete=models.SET_NULL
    )
    symbol = models.CharField(max_length=16)
    side = models.CharField(max_length=4, choices=[("buy", "Buy"), ("sell", "Sell")])
    order_type = models.CharField(
        max_length=16, choices=ORDER_TYPE_CHOICES
    )  # market, limit, stop, etc.
    tif = models.CharField(
        max_length=8,
        choices=[
            ("day", "DAY"),
            ("gtc", "GTC"),
            ("gtd", "GTD"),
            ("ioc", "IOC"),
            ("fok", "FOK"),
            ("aon", "All or None"),
            ("opg", "On Open"),
            ("cls", "At Close"),
            ("ext", "Extended Hours"),
        ],
        default="day",
    )
    tif_date = models.DateTimeField(null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    notional = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )  # amount-based
    limit_price = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    stop_price = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    trail_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    trail_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    hidden = models.BooleanField(default=False)
    reserve_quantity = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    pegged_offset = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    extended_hours = models.BooleanField(default=False)
    condition_type = models.CharField(
        max_length=32,
        blank=True,
        choices=[
            ("none", "None"),
            ("price", "Price Trigger"),
            ("time", "Time Trigger"),
            ("indicator", "Indicator Trigger"),
            ("cross_symbol", "Cross Symbol"),
            ("volume", "Volume Trigger"),
            ("and_group", "AND Group"),
            ("or_group", "OR Group"),
        ],
        default="none",
    )
    condition_payload = models.JSONField(default=dict, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )  # bracket/OCO
    chain_id = models.CharField(max_length=32, blank=True)
    child_role = models.CharField(max_length=32, blank=True)  # e.g. entry, tp, sl
    algo_params = models.JSONField(default=dict, blank=True)
    algo_next_run_at = models.DateTimeField(null=True, blank=True)
    algo_slice_index = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=24,
        choices=ORDER_STATUS_CHOICES,
        default="new",
    )
    filled_quantity = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("0")
    )
    average_fill_price = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.JSONField(default=dict, blank=True)


class PaperTrade(models.Model):
    order = models.ForeignKey(
        PaperOrder, related_name="trades", on_delete=models.CASCADE
    )
    portfolio = models.ForeignKey(
        PaperPortfolio, related_name="trades", on_delete=models.CASCADE
    )
    symbol = models.CharField(max_length=16)
    side = models.CharField(max_length=4, choices=[("buy", "Buy"), ("sell", "Sell")])
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    price = models.DecimalField(max_digits=18, decimal_places=4)
    fees = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0")
    )
    slippage = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0")
    )
    realized_pnl = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0")
    )
    strategy = models.ForeignKey(
        "Strategy", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)


class StrategyRule(models.Model):
    strategy = models.ForeignKey(
        Strategy, related_name="rules", on_delete=models.CASCADE
    )
    rule_type = models.CharField(
        max_length=16, choices=[("entry", "Entry"), ("exit", "Exit")]
    )
    order = models.PositiveIntegerField(default=0)
    logic = models.JSONField(
        default=dict
    )  # stores the AND/OR tree, indicator references, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StrategyRunLog(models.Model):
    strategy = models.ForeignKey(
        Strategy, related_name="run_logs", on_delete=models.CASCADE
    )
    portfolio = models.ForeignKey(
        PaperPortfolio, related_name="strategy_logs", on_delete=models.CASCADE
    )
    run_at = models.DateTimeField(auto_now_add=True)
    context = models.JSONField(default=dict)
    generated_orders = models.JSONField(default=list)
    status = models.CharField(
        max_length=16,
        choices=[("success", "Success"), ("error", "Error"), ("skipped", "Skipped")],
        default="success",
    )
    error_message = models.TextField(blank=True)


class PerformanceSnapshot(models.Model):
    portfolio = models.ForeignKey(
        PaperPortfolio, related_name="snapshots", on_delete=models.CASCADE
    )
    timestamp = models.DateTimeField()
    equity = models.DecimalField(max_digits=18, decimal_places=2)
    cash = models.DecimalField(max_digits=18, decimal_places=2)
    realized_pnl = models.DecimalField(max_digits=18, decimal_places=2)
    unrealized_pnl = models.DecimalField(max_digits=18, decimal_places=2)
    leverage = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("0")
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("portfolio", "timestamp")


class LeaderboardSeason(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    starting_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("100000")
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LeaderboardEntry(models.Model):
    season = models.ForeignKey(
        LeaderboardSeason,
        related_name="entries",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    portfolio = models.ForeignKey(
        PaperPortfolio, related_name="leaderboard_entries", on_delete=models.CASCADE
    )
    metric = models.CharField(max_length=32)  # e.g. return_pct, sharpe
    period = models.CharField(
        max_length=16, default="since_join"
    )  # e.g. 7d, 30d, season
    value = models.DecimalField(max_digits=18, decimal_places=6)
    rank = models.PositiveIntegerField(default=0)
    calculated_at = models.DateTimeField(auto_now=True)
    extra = models.JSONField(default=dict, blank=True)
