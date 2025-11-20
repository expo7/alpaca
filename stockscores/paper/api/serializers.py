from decimal import Decimal

from rest_framework import serializers

from paper.models import (
    PaperPortfolio,
    PaperPosition,
    PaperOrder,
    PaperTrade,
    PerformanceSnapshot,
    Strategy,
    StrategyRule,
    LeaderboardSeason,
    LeaderboardEntry,
    Instrument,
    PortfolioResetLog,
    PortfolioCashMovement,
)


class PaperPortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperPortfolio
        fields = [
            "id",
            "name",
            "base_currency",
            "starting_balance",
            "cash_balance",
            "equity",
            "realized_pnl",
            "unrealized_pnl",
            "max_positions",
            "max_single_position_pct",
            "max_gross_exposure_pct",
            "status",
            "created_at",
        ]
        read_only_fields = ["cash_balance", "equity", "realized_pnl", "unrealized_pnl", "created_at"]


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = ["id", "symbol", "name", "exchange", "asset_class", "currency", "created_at"]
        read_only_fields = ["created_at"]


class PaperPositionSerializer(serializers.ModelSerializer):
    instrument = InstrumentSerializer(read_only=True)
    portfolio = serializers.PrimaryKeyRelatedField(read_only=True)
    portfolio_name = serializers.CharField(source="portfolio.name", read_only=True)
    live_price = serializers.SerializerMethodField()
    cap_single_breach = serializers.SerializerMethodField()
    cap_gross_breach = serializers.SerializerMethodField()

    class Meta:
        model = PaperPosition
        fields = [
            "id",
            "portfolio",
            "portfolio_name",
            "instrument",
            "symbol",
            "live_price",
            "quantity",
            "avg_price",
            "market_value",
            "unrealized_pnl",
            "last_updated",
            "cap_single_breach",
            "cap_gross_breach",
        ]

    def get_live_price(self, obj):
        quotes = self.context.get("quotes") or {}
        return quotes.get(obj.symbol.upper())

    def _equity(self, obj):
        port = obj.portfolio
        return port.equity or port.cash_balance or None

    def get_cap_single_breach(self, obj):
        equity = self._equity(obj)
        if not equity:
            return False
        cap = obj.portfolio.max_single_position_pct
        if not cap:
            return False
        price = self.get_live_price(obj) or obj.avg_price or 0
        live_val = obj.quantity * Decimal(str(price))
        return live_val > equity * (cap / Decimal("100"))

    def get_cap_gross_breach(self, obj):
        equity = self._equity(obj)
        if not equity:
            return False
        cap = obj.portfolio.max_gross_exposure_pct
        if not cap:
            return False
        # Expect view to pass "total_gross_by_portfolio" for efficiency
        gross_map = self.context.get("total_gross_by_portfolio") or {}
        gross = gross_map.get(obj.portfolio_id)
        if gross is None:
            price = self.get_live_price(obj) or obj.avg_price or 0
            gross = obj.quantity * Decimal(str(price))
        return gross > equity * (cap / Decimal("100"))


class PaperOrderSerializer(serializers.ModelSerializer):
    slippage_mode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    slippage_bps = serializers.DecimalField(
        max_digits=8, decimal_places=4, required=False, allow_null=True
    )
    slippage_fixed = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    fee_mode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fee_bps = serializers.DecimalField(
        max_digits=8, decimal_places=4, required=False, allow_null=True
    )
    fee_per_share = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    max_fill_participation = serializers.DecimalField(
        max_digits=6, decimal_places=4, required=False, allow_null=True
    )
    min_fill_size = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True
    )
    backtest_fill_mode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    audit_events = serializers.SerializerMethodField(read_only=True)

    ADVANCED_FIELDS = [
        "slippage_mode",
        "slippage_bps",
        "slippage_fixed",
        "fee_mode",
        "fee_bps",
        "fee_per_share",
        "max_fill_participation",
        "min_fill_size",
        "backtest_fill_mode",
    ]

    class Meta:
        model = PaperOrder
        fields = [
            "id",
            "portfolio",
            "strategy",
            "symbol",
            "side",
            "order_type",
            "tif",
            "quantity",
            "notional",
            "limit_price",
            "stop_price",
            "trail_amount",
            "trail_percent",
            "hidden",
            "reserve_quantity",
            "pegged_offset",
            "extended_hours",
            "tif_date",
            "condition_type",
            "condition_payload",
            "algo_params",
            "chain_id",
            "child_role",
            "parent",
            "status",
            "filled_quantity",
            "average_fill_price",
            "algo_next_run_at",
            "algo_slice_index",
            "created_at",
            "expires_at",
            "notes",
            "slippage_mode",
            "slippage_bps",
            "slippage_fixed",
            "fee_mode",
            "fee_bps",
            "fee_per_share",
            "max_fill_participation",
            "min_fill_size",
            "backtest_fill_mode",
            "audit_events",
        ]
        read_only_fields = [
            "status",
            "filled_quantity",
            "average_fill_price",
            "algo_next_run_at",
            "algo_slice_index",
            "audit_events",
        ]

    def validate(self, attrs):
        data = super().validate(attrs)
        order_type = data.get("order_type") or getattr(self.instance, "order_type", None)
        tif = data.get("tif") or getattr(self.instance, "tif", None)
        quantity = data.get("quantity") or getattr(self.instance, "quantity", None)
        notional = data.get("notional") or getattr(self.instance, "notional", None)
        limit_price = data.get("limit_price") or getattr(self.instance, "limit_price", None)
        stop_price = data.get("stop_price") or getattr(self.instance, "stop_price", None)
        trail_amount = data.get("trail_amount") or getattr(self.instance, "trail_amount", None)
        trail_percent = data.get("trail_percent") or getattr(self.instance, "trail_percent", None)
        reserve_qty = data.get("reserve_quantity") or getattr(self.instance, "reserve_quantity", None)
        condition_type = data.get("condition_type") or getattr(self.instance, "condition_type", "none")
        condition_payload = data.get("condition_payload") or getattr(self.instance, "condition_payload", {})

        if not quantity and not notional:
            raise serializers.ValidationError("Specify either quantity or notional.")

        limit_required_types = {
            "limit",
            "limit_close",
            "limit_open",
            "stop_limit",
            "trailing_limit",
            "pegged_mid",
            "pegged_primary",
            "hidden_limit",
            "iceberg",
        }
        if order_type in limit_required_types and not limit_price:
            raise serializers.ValidationError("limit_price is required for this order type.")

        stop_required_types = {"stop", "stop_limit", "trailing_amount", "trailing_percent", "trailing_limit"}
        if order_type in stop_required_types and not stop_price and order_type not in {"trailing_amount", "trailing_percent", "trailing_limit"}:
            raise serializers.ValidationError("stop_price is required for this order type.")

        if order_type in {"trailing_amount", "trailing_percent", "trailing_limit"}:
            if not trail_amount and not trail_percent:
                raise serializers.ValidationError("Provide trail_amount or trail_percent for trailing orders.")

        if order_type == "iceberg" and reserve_qty and quantity and reserve_qty >= quantity:
            raise serializers.ValidationError("reserve_quantity must be less than total quantity for iceberg orders.")

        if order_type in {"pegged_mid", "pegged_primary"} and not data.get("pegged_offset"):
            raise serializers.ValidationError("pegged_offset is required for pegged orders.")

        if tif == "gtd" and not data.get("tif_date"):
            raise serializers.ValidationError("tif_date is required when tif is GTD.")

        if condition_type and condition_type != "none" and not condition_payload:
            raise serializers.ValidationError("condition_payload is required for conditional orders.")

        return data

    def get_audit_events(self, instance):
        events = (instance.notes or {}).get("events", [])
        return sorted(
            events, key=lambda evt: evt.get("timestamp") or "", reverse=False
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        notes = instance.notes or {}
        for field in self.ADVANCED_FIELDS:
            value = notes.get(field)
            if isinstance(value, Decimal):
                value = str(value)
            data[field] = value
        return data

    def _attach_overrides(self, validated_data):
        overrides = {}
        for key in list(self.ADVANCED_FIELDS):
            if key in validated_data:
                value = validated_data.pop(key)
                if isinstance(value, Decimal):
                    value = str(value)
                overrides[key] = value
        if overrides:
            notes = validated_data.get("notes") or {}
            merged = {**notes}
            merged.update(overrides)
            validated_data["notes"] = merged
        return validated_data

    def create(self, validated_data):
        validated_data = self._attach_overrides(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._attach_overrides(validated_data)
        return super().update(instance, validated_data)


class PaperTradeSerializer(serializers.ModelSerializer):
    instrument = InstrumentSerializer(read_only=True)

    class Meta:
        model = PaperTrade
        fields = [
            "id",
            "order",
            "portfolio",
            "instrument",
            "symbol",
            "side",
            "quantity",
            "price",
            "fees",
            "slippage",
            "realized_pnl",
            "strategy",
            "created_at",
        ]


class StrategyRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyRule
        fields = ["id", "rule_type", "order", "logic", "created_at", "updated_at"]


class StrategySerializer(serializers.ModelSerializer):
    rules = StrategyRuleSerializer(many=True, read_only=True)

    class Meta:
        model = Strategy
        fields = [
            "id",
            "name",
            "description",
            "config",
            "is_public_template",
            "is_active",
            "created_at",
            "updated_at",
            "rules",
        ]

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("config must be a JSON object.")
        templates = value.get("order_templates", {})
        if templates and not isinstance(templates, dict):
            raise serializers.ValidationError("order_templates must be a mapping.")
        for name, tpl in templates.items():
            if not isinstance(tpl, dict):
                raise serializers.ValidationError(f"Template {name} must be a JSON object.")
        return value


class LeaderboardSeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardSeason
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "starting_balance",
            "is_active",
            "created_at",
        ]


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    portfolio = PaperPortfolioSerializer(read_only=True)

    class Meta:
        model = LeaderboardEntry
        fields = [
            "id",
            "season",
            "portfolio",
            "metric",
            "period",
            "value",
            "rank",
            "calculated_at",
            "extra",
        ]


class PerformanceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceSnapshot
        fields = [
            "id",
            "timestamp",
            "equity",
            "cash",
            "realized_pnl",
            "unrealized_pnl",
            "leverage",
            "metadata",
        ]


class PortfolioResetLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioResetLog
        fields = [
            "id",
            "portfolio",
            "performed_by",
            "reset_to",
            "previous_cash",
            "previous_equity",
            "reason",
            "created_at",
        ]
        read_only_fields = ["performed_by", "created_at"]


class PortfolioCashMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioCashMovement
        fields = [
            "id",
            "portfolio",
            "performed_by",
            "movement_type",
            "amount",
            "reason",
            "created_at",
        ]
        read_only_fields = ["performed_by", "created_at"]
