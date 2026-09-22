from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ranker/models.py
from django.contrib.auth import get_user_model

User = get_user_model()


class UserPreference(models.Model):
    """
    Per-user feature toggles / thresholds for things like daily scan emails.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="ranker_prefs",
    )
    # [NOTE-AUTOSCAN-FIELDS]
    daily_scan_enabled = models.BooleanField(default=False)
    daily_scan_min_score = models.FloatField(default=15.0)
    daily_scan_max_ideas = models.PositiveIntegerField(default=10)

    def __str__(self):
        return f"Prefs for {self.user!s}"


class StrategySpec(models.Model):
    """Persisted representation of a validated strategy JSON payload."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="strategy_specs",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    spec = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"StrategySpec {self.id}"


class BotConfig(models.Model):
    """Persisted representation of a validated bot configuration payload."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bot_configs",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    config = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"BotConfig {self.id}"


class Bot(models.Model):
    STATE_STOPPED = "stopped"
    STATE_RUNNING = "running"
    STATE_PAUSED = "paused"
    STATE_CHOICES = [
        (STATE_STOPPED, "Stopped"),
        (STATE_RUNNING, "Running"),
        (STATE_PAUSED, "Paused"),
    ]

    MODE_BACKTEST = "backtest"
    MODE_PAPER = "paper"
    MODE_LIVE = "live"
    MODE_CHOICES = [
        (MODE_BACKTEST, "Backtest"),
        (MODE_PAPER, "Paper"),
        (MODE_LIVE, "Live"),
    ]

    SCHEDULE_CHOICES = [
        ("1m", "Every minute"),
        ("5m", "Every 5 minutes"),
        ("15m", "Every 15 minutes"),
        ("1h", "Hourly"),
        ("1d", "Daily"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bots",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    strategy_spec = models.ForeignKey(
        StrategySpec,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bots",
    )
    bot_config = models.ForeignKey(
        BotConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bots",
    )
    state = models.CharField(
        max_length=16, choices=STATE_CHOICES, default=STATE_STOPPED
    )
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default=MODE_BACKTEST)
    schedule = models.CharField(max_length=16, choices=SCHEDULE_CHOICES, default="5m")
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    forward_start_date = models.DateField(null=True, blank=True)
    last_forward_run_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"Bot {self.id}"


class BotForwardRun(models.Model):
    bot = models.ForeignKey(Bot, related_name="forward_runs", on_delete=models.CASCADE)
    as_of = models.DateField()
    equity = models.DecimalField(max_digits=20, decimal_places=2)
    cash = models.DecimalField(max_digits=20, decimal_places=2)
    positions_value = models.DecimalField(max_digits=20, decimal_places=2)
    pnl = models.DecimalField(max_digits=20, decimal_places=2)
    num_trades = models.IntegerField(default=0)
    stats = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("bot", "as_of")
        ordering = ["bot", "as_of"]

    def __str__(self):
        return f"Forward run {self.bot_id} @ {self.as_of}"


class BacktestRun(models.Model):
    """
    A saved / named backtest configuration + summary snapshot.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="backtest_runs",
    )
    name = models.CharField(max_length=100)

    tickers = models.JSONField()  # e.g. ["AAPL","MSFT","NVDA"]
    start = models.DateField()
    end = models.DateField()
    benchmark = models.CharField(max_length=16, default="SPY")

    initial_capital = models.FloatField(default=10_000.0)
    rebalance_days = models.PositiveIntegerField(default=5)
    top_n = models.PositiveIntegerField(null=True, blank=True)

    # snapshot of result.summary from the backtest
    summary = models.JSONField(default=dict)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"


class BacktestBatch(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="backtest_batches",
    )
    label = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    config = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch {self.id} ({self.status})"


class BacktestBatchRun(models.Model):
    STATUS_PENDING = BacktestBatch.STATUS_PENDING
    STATUS_RUNNING = BacktestBatch.STATUS_RUNNING
    STATUS_COMPLETED = BacktestBatch.STATUS_COMPLETED
    STATUS_FAILED = BacktestBatch.STATUS_FAILED
    STATUS_CHOICES = BacktestBatch.STATUS_CHOICES

    batch = models.ForeignKey(
        BacktestBatch,
        related_name="runs",
        on_delete=models.CASCADE,
    )
    index = models.IntegerField()
    params = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    stats = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["index"]

    def __str__(self):
        return f"BatchRun {self.batch_id}#{self.index} ({self.status})"


class BacktestConfig(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="backtest_configs",
    )
    name = models.CharField(max_length=100)

    tickers = models.TextField(help_text="Comma-separated tickers")
    start = models.DateField()
    end = models.DateField()
    initial_capital = models.FloatField(default=10_000.0)
    rebalance_days = models.PositiveIntegerField(default=5)
    top_n = models.PositiveIntegerField(null=True, blank=True)
    benchmark = models.CharField(max_length=20, default="SPY")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} – {self.name}"


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stockranker_settings",
    )
    default_tickers = models.CharField(
        max_length=512,
        blank=True,
        help_text="Comma-separated symbols, e.g. AAPL,MSFT,NVDA",
    )
    default_tech_weight = models.FloatField(default=0.6)
    default_fund_weight = models.FloatField(default=0.4)
    default_min_final_score = models.FloatField(
        default=15.0, help_text="Default alert threshold for final score"
    )

    def __str__(self):
        return f"Settings for {self.user}"


# ... existing models (Watchlist, Alert, etc.) ...


class AlertEvent(models.Model):
    """
    A single firing of an alert.
    Stores scores and symbol at the moment it triggered.
    """

    alert = models.ForeignKey(
        "Alert",
        related_name="events",
        on_delete=models.CASCADE,
    )
    symbol = models.CharField(max_length=16)

    final_score = models.DecimalField(max_digits=6, decimal_places=2)
    tech_score = models.DecimalField(max_digits=6, decimal_places=2)
    fund_score = models.DecimalField(max_digits=6, decimal_places=2)

    triggered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"AlertEvent(alert={self.alert_id}, {self.symbol}, {self.final_score})"


class Alert(models.Model):
    TYPE_SYMBOL = "symbol"
    TYPE_WATCHLIST = "watchlist"
    TYPE_CHOICES = [
        (TYPE_SYMBOL, "Single symbol"),
        (TYPE_WATCHLIST, "Watchlist"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    alert_type = models.CharField(
        max_length=16,
        choices=TYPE_CHOICES,
        default=TYPE_SYMBOL,
    )

    # Symbol-based alert
    symbol = models.CharField(max_length=16, blank=True, null=True)

    # Watchlist-based alert
    watchlist = models.ForeignKey(
        "Watchlist",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="alerts",
    )

    min_final_score = models.FloatField()
    min_tech_score = models.FloatField(blank=True, null=True)
    min_fund_score = models.FloatField(blank=True, null=True)

    active = models.BooleanField(default=True)
    trigger_once = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target = self.symbol or (self.watchlist.name if self.watchlist else "?")
        return f"{self.user} · {target} · ≥ {self.min_final_score}"


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlists"
    )
    name = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.user} · {self.name}"


class WatchlistItem(models.Model):
    watchlist = models.ForeignKey(
        Watchlist, on_delete=models.CASCADE, related_name="items"
    )
    symbol = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("watchlist", "symbol")
        ordering = ["symbol"]


class StockScore(models.Model):
    symbol = models.CharField(max_length=12, db_index=True)
    asof = models.DateTimeField(auto_now=True)

    tech_score = models.FloatField(default=0.0)
    fundamental_score = models.FloatField(default=0.0)
    final_score = models.FloatField(default=0.0)

    components = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.symbol} {self.final_score:.2f} @ {self.asof}"


class Article(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class AnalyticsEvent(models.Model):
    """Privacy-conscious first-party product analytics event."""

    EVENT_PAGE_VIEW = "page_view"

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event_name = models.CharField(max_length=64, db_index=True)
    path = models.CharField(max_length=512, blank=True, default="", db_index=True)
    referrer_host = models.CharField(max_length=255, blank=True, default="")
    visitor_hash = models.CharField(max_length=64, db_index=True)
    device_type = models.CharField(max_length=16, blank=True, default="unknown")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_events",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["event_name", "occurred_at"]),
            models.Index(fields=["path", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.event_name} · {self.path or '-'}"


class TradeSignal(models.Model):
    """A staff-published, timestamped trade plan and its final outcome."""

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published — waiting for entry"),
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]
    INSTRUMENT_CHOICES = [
        ("stock", "Stock"),
        ("call", "Call option"),
        ("put", "Put option"),
    ]
    RISK_CHOICES = [("low", "Low"), ("moderate", "Moderate"), ("high", "High")]
    TRIGGER_CHOICES = [("above", "Trades above"), ("below", "Trades below")]
    FILL_CHOICES = [("ask", "Ask at activation (conservative)"), ("midpoint", "Bid/ask midpoint at activation")]

    symbol = models.CharField(max_length=16, db_index=True)
    company_name = models.CharField(max_length=160, blank=True, default="")
    instrument_type = models.CharField(max_length=8, choices=INSTRUMENT_CHOICES, default="stock")
    strike = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expiration = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    risk_level = models.CharField(max_length=12, choices=RISK_CHOICES, default="moderate")
    trigger_direction = models.CharField(max_length=8, choices=TRIGGER_CHOICES, default="above")
    underlying_trigger_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    trigger_confirmation = models.CharField(max_length=255, blank=True, default="")
    do_not_chase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    entry_deadline = models.DateField(null=True, blank=True)
    official_fill_method = models.CharField(max_length=12, choices=FILL_CHOICES, default="ask")
    entry_low = models.DecimalField(max_digits=12, decimal_places=2)
    entry_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    initial_stop = models.DecimalField(max_digits=12, decimal_places=2)
    current_stop = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_1 = models.DecimalField(max_digits=12, decimal_places=2)
    target_2 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_3 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_entry = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    final_exit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    realized_return_pct = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    max_return_pct = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    thesis = models.TextField(help_text="Why this setup qualified when it was published.")
    invalidation = models.TextField(blank=True, default="", help_text="What would prove the thesis wrong.")
    evidence_tags = models.JSONField(default=list, blank=True, help_text='Examples: ["Price action", "News", "Sentiment"]')
    publication_underlying_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    publication_option_bid = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    publication_option_ask = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    publication_option_midpoint = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    publication_option_spread_pct = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    publication_option_volume = models.PositiveBigIntegerField(null=True, blank=True)
    publication_option_open_interest = models.PositiveBigIntegerField(null=True, blank=True)
    publication_quote_at = models.DateTimeField(null=True, blank=True)
    publication_quote_source = models.CharField(max_length=80, blank=True, default="")
    paper_execution_enabled = models.BooleanField(
        default=False,
        help_text="Allow the globally enabled Alpaca paper executor to manage this signal.",
    )
    is_test = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Operator test trade: execute and notify, but never expose in public records.",
    )
    paper_quantity = models.PositiveIntegerField(default=1)
    paper_entry_order_id = models.CharField(max_length=64, blank=True, default="")
    paper_exit_order_id = models.CharField(max_length=64, blank=True, default="")
    paper_order_status = models.CharField(max_length=32, blank=True, default="")
    paper_submitted_at = models.DateTimeField(null=True, blank=True)
    paper_filled_at = models.DateTimeField(null=True, blank=True)
    paper_last_checked_at = models.DateTimeField(null=True, blank=True)
    paper_last_error = models.CharField(max_length=255, blank=True, default="")
    paper_exit_reason = models.CharField(max_length=32, blank=True, default="")
    trigger_first_seen_at = models.DateTimeField(null=True, blank=True)
    operator_request_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    LOCKED_AFTER_PUBLICATION = (
        "symbol", "company_name", "instrument_type", "strike", "expiration", "risk_level",
        "trigger_direction", "underlying_trigger_price", "trigger_confirmation", "do_not_chase_price",
        "entry_deadline", "official_fill_method",
        "entry_low", "entry_high", "initial_stop", "target_1", "target_2", "target_3",
        "thesis", "invalidation", "evidence_tags", "published_at",
        "publication_underlying_price", "publication_option_bid", "publication_option_ask",
        "publication_option_midpoint", "publication_option_spread_pct", "publication_option_volume", "publication_option_open_interest",
        "publication_quote_at", "publication_quote_source", "operator_request_id", "is_test",
    )

    @property
    def display_instrument(self):
        if self.instrument_type == "stock":
            return self.symbol
        expiration = self.expiration.strftime("%-m/%-d/%y") if self.expiration else ""
        strike = f"{self.strike:g}" if self.strike is not None else ""
        side = "C" if self.instrument_type == "call" else "P"
        return " ".join(part for part in [self.symbol, f"{strike}{side}", expiration] if part)

    @property
    def contract_symbol(self):
        if self.instrument_type == "stock" or not self.expiration or self.strike is None:
            return self.symbol
        side = "C" if self.instrument_type == "call" else "P"
        strike_code = f"{int(self.strike * 1000):08d}"
        return f"{self.symbol}{self.expiration:%y%m%d}{side}{strike_code}"

    def save(self, *args, **kwargs):
        self.symbol = (self.symbol or "").strip().upper()
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.published_at:
                changed = [
                    field for field in self.LOCKED_AFTER_PUBLICATION
                    if getattr(original, field) not in (None, "", [])
                    and getattr(original, field) != getattr(self, field)
                ]
                if changed:
                    raise ValidationError(
                        "Published trade plans cannot be rewritten. Add a timestamped update instead. "
                        f"Locked fields changed: {', '.join(changed)}"
                    )
            if original and original.paper_entry_order_id and original.paper_quantity != self.paper_quantity:
                raise ValidationError("Paper quantity cannot change after an entry order has been submitted.")
        if self.status != self.STATUS_DRAFT and not self.published_at:
            self.published_at = timezone.now()
        if self.status in {self.STATUS_CLOSED, self.STATUS_CANCELLED, self.STATUS_EXPIRED} and not self.closed_at:
            self.closed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_instrument} · {self.status}"


class TradeExecutorHealth(models.Model):
    """Persistent health state for the published-trade paper executor.

    The guardian may pause *new entries*, but it never disables processing of
    open positions.  That keeps the original monitored-exit path available
    during guardian failures or recovery.
    """

    STATUS_WARMING = "warming"
    STATUS_HEALTHY = "healthy"
    STATUS_DEGRADED = "degraded"
    STATUS_MARKET_CLOSED = "market_closed"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = [
        (STATUS_WARMING, "Warming up"),
        (STATUS_HEALTHY, "Healthy"),
        (STATUS_DEGRADED, "Degraded"),
        (STATUS_MARKET_CLOSED, "Market closed"),
        (STATUS_DISABLED, "Disabled"),
    ]

    singleton_id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WARMING)
    entries_paused = models.BooleanField(default=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_completed_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    degraded_at = models.DateTimeField(null=True, blank=True)
    recovered_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trade executor health"
        verbose_name_plural = "Trade executor health"

    def save(self, *args, **kwargs):
        self.singleton_id = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Trade executor · {self.get_status_display()}"


class TradeSignalUpdate(models.Model):
    EVENT_CHOICES = [
        ("published", "Setup published"),
        ("entry_submitted", "Entry order submitted"),
        ("triggered", "Entry filled"),
        ("protection_active", "Exit protection active"),
        ("target", "Target reached"),
        ("stop", "Stop changed"),
        ("partial_exit", "Partial exit"),
        ("exit_submitted", "Exit order submitted"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
        ("execution_warning", "Execution warning"),
        ("note", "Status note"),
    ]

    signal = models.ForeignKey(TradeSignal, on_delete=models.CASCADE, related_name="updates")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, default="note")
    note = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    return_pct = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]

    def __str__(self):
        return f"{self.signal.symbol} · {self.get_event_type_display()}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Published trade updates are append-only. Add a correction as a new update.")
        super().save(*args, **kwargs)


class TelegramNotification(models.Model):
    """Idempotent outbox entry for one immutable trade lifecycle update."""

    STATUS_PENDING = "pending"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENDING, "Sending"),
        (STATUS_SENT, "Sent"),
    ]

    update = models.OneToOneField(
        TradeSignalUpdate,
        on_delete=models.CASCADE,
        related_name="telegram_notification",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True, default="")
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Telegram · {self.update} · {self.status}"


class TradeLifecycleCertification(models.Model):
    """Latest read-only cross-system certification for one trade lifecycle."""

    STATUS_PENDING = "pending"
    STATUS_CERTIFIED = "certified"
    STATUS_DISCREPANCY = "discrepancy"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CERTIFIED, "Certified"),
        (STATUS_DISCREPANCY, "Discrepancy"),
        (STATUS_ERROR, "Audit error"),
    ]

    signal = models.OneToOneField(
        TradeSignal,
        on_delete=models.CASCADE,
        related_name="lifecycle_certification",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    lifecycle_certified = models.BooleanField(default=False, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    certified_at = models.DateTimeField(null=True, blank=True)
    checkpoints = models.JSONField(default=dict, blank=True)
    discrepancy_codes = models.JSONField(default=list, blank=True)
    discrepancy_details = models.JSONField(default=list, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-checked_at", "-id"]

    def __str__(self):
        return f"Certification · {self.signal} · {self.status}"


class OperationalTelegramAlert(models.Model):
    """Idempotent operational Telegram warning, separate from public trade history."""

    STATUS_PENDING = "pending"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENDING, "Sending"),
        (STATUS_SENT, "Sent"),
    ]

    idempotency_key = models.CharField(max_length=160, unique=True)
    signal = models.ForeignKey(TradeSignal, on_delete=models.CASCADE, related_name="operational_alerts")
    message = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True, default="")
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Operational alert · {self.signal} · {self.status}"


class BillingProfile(models.Model):
    """Stripe identifiers and the webhook-derived subscription state for one user."""

    ACCESS_STATUSES = {"active", "trialing"}

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_profile",
    )
    stripe_customer_id = models.CharField(max_length=64, blank=True, default=None, unique=True, null=True)
    stripe_subscription_id = models.CharField(max_length=64, blank=True, default=None, unique=True, null=True)
    stripe_price_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=32, blank=True, default="inactive", db_index=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_pro_access(self):
        return bool(self.user.is_staff or self.user.is_superuser or self.status in self.ACCESS_STATUSES)

    def __str__(self):
        return f"{self.user} · {self.status}"
