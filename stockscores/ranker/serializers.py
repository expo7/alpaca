from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from .models import StockScore
from .models import StrategySpec, BotConfig, Bot

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

User = get_user_model()


def _collect_param_refs(node):
    refs = set()
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "param" and isinstance(val, str):
                refs.add(val)
            else:
                refs.update(_collect_param_refs(val))
    elif isinstance(node, list):
        for val in node:
            refs.update(_collect_param_refs(val))
    return refs


class ParameterDefinitionSerializer(serializers.Serializer):
    type = serializers.CharField()
    default = serializers.FloatField(required=False, allow_null=True)
    min = serializers.FloatField(required=False, allow_null=True)
    max = serializers.FloatField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


class StrategySpecSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, default="")
    entry_tree = serializers.DictField()
    exit_tree = serializers.DictField(required=False, default=dict)
    parameters = serializers.DictField(
        child=ParameterDefinitionSerializer(), default=dict
    )
    metadata = serializers.DictField(required=False, default=dict)

    def validate(self, data):
        entry = data.get("entry_tree") or {}
        if not entry:
            raise serializers.ValidationError({"entry_tree": "entry_tree is required"})

        params = data.get("parameters") or {}
        defined_params = set(params.keys())
        referenced_params = _collect_param_refs(entry) | _collect_param_refs(
            data.get("exit_tree") or {}
        )

        missing = referenced_params - defined_params
        if missing:
            names = ", ".join(sorted(missing))
            raise serializers.ValidationError(
                {"parameters": f"Missing parameter definitions for: {names}"}
            )
        return data


class BotConfigSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, default="")
    symbols = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )
    mode = serializers.CharField(required=False, allow_blank=True, default="paper")
    overrides = serializers.DictField(required=False, default=dict)
    capital = serializers.FloatField(default=10000.0, min_value=0.0)
    rebalance_days = serializers.IntegerField(default=5, min_value=1)
    top_n = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    benchmark = serializers.CharField(required=False, default="SPY")
    commission_per_trade = serializers.FloatField(
        required=False, default=0.0, min_value=0.0
    )
    commission_pct = serializers.FloatField(required=False, default=0.0, min_value=0.0)
    slippage_model = serializers.CharField(required=False, default="none")
    slippage_bps = serializers.FloatField(required=False, default=0.0, min_value=0.0)
    max_open_positions = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )
    max_per_position_pct = serializers.FloatField(
        required=False, default=1.0, min_value=0.0, max_value=1.0
    )


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = [
            "id",
            "name",
            "strategy_spec",
            "bot_config",
            "state",
            "mode",
            "schedule",
            "last_run_at",
            "next_run_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state",
            "last_run_at",
            "next_run_at",
            "created_at",
            "updated_at",
        ]


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            "daily_scan_enabled",
            "daily_scan_min_score",
            "daily_scan_max_ideas",
        ]


class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]
        extra_kwargs = {
            "email": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        pw = attrs.get("password")
        pw2 = attrs.pop("password_confirm", None)
        if pw != pw2:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        try:
            validate_password(pw)
        except django_exceptions.ValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


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
    technical_deltas = serializers.SerializerMethodField()
    tech_score_delta = serializers.SerializerMethodField()

    class Meta:
        model = StockScore
        fields = [
            "symbol",
            "asof",
            "tech_score",
            "fundamental_score",
            "final_score",
            "components",
            "technical_deltas",
            "tech_score_delta",
        ]

    def get_technical_deltas(self, obj):
        tech = (obj.components or {}).get("technical") or {}
        deltas = tech.get("deltas")
        if isinstance(deltas, dict):
            return deltas
        return {
            "trend_raw": None,
            "momentum_raw": None,
            "volume_raw": None,
            "volatility_raw": None,
            "meanreversion_raw": None,
        }

    def get_tech_score_delta(self, obj):
        tech = (obj.components or {}).get("technical") or {}
        delta = tech.get("score_delta")
        if isinstance(delta, (int, float)):
            return round(float(delta), 2)
        return None
