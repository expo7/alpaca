from django.db import models
from django.conf import settings
from django.utils import timezone


# ranker/models.py
from django.db import models
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
