from django.conf import settings
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
