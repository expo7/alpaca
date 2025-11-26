from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from .models import StockScore
from .models import StrategySpec, BotConfig, Bot, BacktestBatch, BacktestBatchRun, BotForwardRun

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
from itertools import product
from datetime import datetime

User = get_user_model()


ALLOWED_NODE_TYPES = {
    "group",
    "and",
    "or",
    "condition",
    "indicator_condition",
    "position_condition",
    "action",
    "event_condition",
}


def _collect_param_refs(node):
    refs = set()
    if isinstance(node, dict):
        for key, val in node.items():
            if (
                isinstance(val, str)
                and (key == "param" or key == "value_param" or key.endswith("_param"))
            ):
                refs.add(val)
            else:
                refs.update(_collect_param_refs(val))
    elif isinstance(node, list):
        for val in node:
            refs.update(_collect_param_refs(val))
    return refs


def _validate_tree_node(node, path, errors):
    if not isinstance(node, dict):
        errors.setdefault(path, []).append("must be an object")
        return

    node_type = node.get("type") or node.get("node_type")
    if not node_type:
        errors.setdefault(f"{path}.type", []).append("type is required")
        return

    node_type = str(node_type)
    node_type = node_type.lower()
    if node_type not in ALLOWED_NODE_TYPES:
        errors.setdefault(f"{path}.type", []).append(f"unsupported node type: {node_type}")
        return

    if node_type in {"group", "and", "or"}:
        op = node.get("op") or node.get("operator") or ("AND" if node_type == "and" else "OR" if node_type == "or" else None)
        if not op:
            errors.setdefault(f"{path}.op", []).append("group op is required")
        elif str(op).lower() not in {"and", "or"}:
            errors.setdefault(f"{path}.op", []).append("op must be AND or OR")

        children = node.get("children")
        if not isinstance(children, list) or not children:
            errors.setdefault(f"{path}.children", []).append("children must be a non-empty list")
        else:
            for idx, child in enumerate(children):
                _validate_tree_node(child, f"{path}.children[{idx}]", errors)
    elif node_type in {"condition", "indicator_condition", "position_condition"}:
        op = node.get("operator")
        if not op:
            errors.setdefault(f"{path}.operator", []).append("operator is required")
        has_left = any(k in node for k in ("indicator", "left", "metric"))
        has_right = any(k in node for k in ("value", "value_param", "param", "right"))
        if not (has_left and has_right):
            errors.setdefault(f"{path}.operands", []).append(
                "condition must define indicator/left and value/right"
            )
    elif node_type == "action":
        if not node.get("action"):
            errors.setdefault(f"{path}.action", []).append("action is required")
    elif node_type == "event_condition":
        if not (node.get("event_type") or node.get("event")):
            errors.setdefault(f"{path}.event_type", []).append("event_type is required")
        if not node.get("field"):
            errors.setdefault(f"{path}.field", []).append("field is required")
        if not node.get("operator"):
            errors.setdefault(f"{path}.operator", []).append("operator is required")
        if "value" not in node and "value_param" not in node:
            errors.setdefault(f"{path}.value", []).append("value or value_param is required")


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

        errors = {}
        _validate_tree_node(entry, "entry_tree", errors)
        if data.get("exit_tree"):
            _validate_tree_node(data["exit_tree"], "exit_tree", errors)
        if errors:
            raise serializers.ValidationError(errors)
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

    def validate_slippage_model(self, value):
        val = (value or "none").lower()
        allowed = {"none", "bps"}
        if val not in allowed:
            raise serializers.ValidationError(f"slippage_model must be one of {sorted(allowed)}")
        return val


class BacktestBatchRequestSerializer(serializers.Serializer):
    strategy = StrategySpecSerializer()
    bot = BotConfigSerializer()
    param_grid = serializers.DictField(required=False, default=dict)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_param_grid(self, grid):
        if grid is None:
            return {}
        if not isinstance(grid, dict):
            raise serializers.ValidationError("param_grid must be a dict of lists")
        cleaned = {}
        for key, val in grid.items():
            if not isinstance(val, list) or not val:
                raise serializers.ValidationError(f"param_grid[{key}] must be a non-empty list")
            for v in val:
                if not isinstance(v, (int, float)):
                    raise serializers.ValidationError(f"param_grid[{key}] values must be numbers")
            cleaned[key] = val
        return cleaned

    def validate(self, data):
        # validate nested serializers explicitly to reuse their errors
        strat = StrategySpecSerializer(data=data.get("strategy") or {})
        bot = BotConfigSerializer(data=data.get("bot") or {})
        errors = {}
        if not strat.is_valid():
            errors["strategy"] = strat.errors
        if not bot.is_valid():
            errors["bot"] = bot.errors
        if errors:
            raise serializers.ValidationError(errors)

        param_grid = data.get("param_grid") or {}
        strategy_params = set((strat.validated_data.get("parameters") or {}).keys())

        for key in param_grid.keys():
            if key not in strategy_params and key not in bot.validated_data:
                raise serializers.ValidationError(
                    {"param_grid": f"param_grid key '{key}' not found in strategy parameters or bot config"}
                )

        try:
            combos = expand_param_grid(param_grid)
        except ValueError as exc:
            raise serializers.ValidationError({"param_grid": str(exc)})
        if not combos:
            raise serializers.ValidationError({"param_grid": "param_grid produced zero combinations"})

        return {
            **data,
            "strategy": strat.validated_data,
            "bot": bot.validated_data,
            "param_grid": param_grid,
            "combinations": combos,
        }


def expand_param_grid(grid: dict) -> list[dict]:
    if not grid:
        return [dict()]
    keys = list(grid.keys())
    values = []
    for key in keys:
        vals = grid[key]
        if not isinstance(vals, list) or not vals:
            raise ValueError(f"param_grid[{key}] must be a non-empty list")
        values.append(vals)
    combos = []
    for prod in product(*values):
        combos.append({k: v for k, v in zip(keys, prod)})
    return combos


class BotSerializer(serializers.ModelSerializer):
    symbols = serializers.SerializerMethodField()
    last_forward_equity = serializers.SerializerMethodField()
    strategy_spec_data = serializers.SerializerMethodField()
    bot_config_data = serializers.SerializerMethodField()

    def get_symbols(self, obj):
        cfg = obj.bot_config.config if obj.bot_config else {}
        syms = cfg.get("symbols") or []
        return syms

    def get_last_forward_equity(self, obj):
        latest = obj.forward_runs.order_by("-as_of").first()
        if not latest:
            return None
        return latest.equity

    def get_strategy_spec_data(self, obj):
        return obj.strategy_spec.spec if obj.strategy_spec else None

    def get_bot_config_data(self, obj):
        return obj.bot_config.config if obj.bot_config else None

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
            "forward_start_date",
            "last_forward_run_at",
            "last_forward_equity",
            "strategy_spec_data",
            "bot_config_data",
            "symbols",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state",
            "last_run_at",
            "next_run_at",
            "last_forward_run_at",
            "created_at",
            "updated_at",
        ]


class BotForwardRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotForwardRun
        fields = [
            "id",
            "bot",
            "as_of",
            "equity",
            "cash",
            "positions_value",
            "pnl",
            "num_trades",
            "stats",
            "created_at",
        ]
        read_only_fields = fields


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
