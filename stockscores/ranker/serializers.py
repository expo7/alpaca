from rest_framework import serializers
from .models import StockScore

# [NOTE-WATCHLIST-SERIALIZERS]
from .models import Watchlist, WatchlistItem
from rest_framework import serializers
from .models import Alert, AlertEvent
from .models import UserSettings

# ranker/serializers.py
from .models import BacktestRun

# ranker/serializers.py
from .models import BacktestConfig
from .models import BacktestRun

# ranker/serializers.py
from rest_framework import serializers
from .models import UserPreference


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            "daily_scan_enabled",
            "daily_scan_min_score",
            "daily_scan_max_ideas",
        ]


class BacktestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestRun
        fields = [
            "id",
            "name",
            "tickers",
            "start",
            "end",
            "benchmark",
            "initial_capital",
            "rebalance_days",
            "top_n",
            "summary",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class BacktestConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestConfig
        fields = [
            "id",
            "name",
            "tickers",
            "start",
            "end",
            "initial_capital",
            "rebalance_days",
            "top_n",
            "benchmark",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BacktestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestRun
        fields = [
            "id",
            "name",
            "tickers",
            "start",
            "end",
            "benchmark",
            "initial_capital",
            "rebalance_days",
            "top_n",
            "summary",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            "default_tickers",
            "default_tech_weight",
            "default_fund_weight",
            "default_min_final_score",
        ]


class AlertEventSerializer(serializers.ModelSerializer):
    alert_id = serializers.IntegerField(source="alert.id", read_only=True)
    user = serializers.CharField(source="alert.user.username", read_only=True)

    class Meta:
        model = AlertEvent
        fields = [
            "id",
            "alert_id",
            "user",
            "symbol",
            "final_score",
            "tech_score",
            "fund_score",
            "triggered_at",
        ]


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            "id",
            "alert_type",
            "symbol",
            "watchlist",
            "min_final_score",
            "min_tech_score",
            "min_fund_score",
            "active",
            "trigger_once",
            "last_triggered_at",
            "created_at",
        ]

    def validate(self, attrs):
        alert_type = attrs.get("alert_type") or getattr(
            self.instance, "alert_type", None
        )
        symbol = attrs.get("symbol", getattr(self.instance, "symbol", None))
        watchlist = attrs.get("watchlist", getattr(self.instance, "watchlist", None))

        if alert_type == Alert.TYPE_SYMBOL and not symbol:
            raise serializers.ValidationError("Symbol is required for symbol alerts.")
        if alert_type == Alert.TYPE_WATCHLIST and not watchlist:
            raise serializers.ValidationError(
                "Watchlist is required for watchlist alerts."
            )
        return attrs


class WatchlistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WatchlistItem
        fields = ["id", "symbol", "created_at"]


class WatchlistSerializer(serializers.ModelSerializer):
    items = WatchlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Watchlist
        fields = ["id", "name", "created_at", "items"]


class StockScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockScore
        fields = [
            "symbol",
            "asof",
            "tech_score",
            "fundamental_score",
            "final_score",
            "components",
        ]
