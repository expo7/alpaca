from decimal import Decimal

from django.utils import timezone
from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from rest_framework.views import APIView

from paper.models import (
    PaperPortfolio,
    PaperOrder,
    PaperTrade,
    Strategy,
    LeaderboardSeason,
    LeaderboardEntry,
    PaperPosition,
    PortfolioResetLog,
    PortfolioCashMovement,
    Instrument,
)
from .serializers import (
    PaperPortfolioSerializer,
    PaperOrderSerializer,
    PaperTradeSerializer,
    StrategySerializer,
    LeaderboardSeasonSerializer,
    LeaderboardEntrySerializer,
    PerformanceSnapshotSerializer,
    PaperPositionSerializer,
    PortfolioResetLogSerializer,
    PortfolioCashMovementSerializer,
    InstrumentSerializer,
)
from paper.services.market_data import get_market_data_provider


class OwnedQuerySetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        return qs.filter(user=user) if hasattr(qs.model, "user") else qs


class PortfolioViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = PaperPortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaperPortfolio.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """
        Reset a portfolio to its starting balance, wipe positions, and log the action.
        """
        portfolio = self.get_object()
        reason = request.data.get("reason", "")
        with transaction.atomic():
            previous_cash = portfolio.cash_balance
            previous_equity = portfolio.equity
            portfolio.positions.all().delete()
            portfolio.cash_balance = portfolio.starting_balance
            portfolio.equity = portfolio.starting_balance
            portfolio.realized_pnl = Decimal("0")
            portfolio.unrealized_pnl = Decimal("0")
            portfolio.save(update_fields=["cash_balance", "equity", "realized_pnl", "unrealized_pnl"])
            log = PortfolioResetLog.objects.create(
                portfolio=portfolio,
                performed_by=request.user if request.user.is_authenticated else None,
                reset_to=portfolio.starting_balance,
                previous_cash=previous_cash,
                previous_equity=previous_equity,
                reason=reason,
            )
        return Response(PortfolioResetLogSerializer(log).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deposit(self, request, pk=None):
        portfolio = self.get_object()
        amount = Decimal(str(request.data.get("amount", "0")))
        if amount <= 0:
            return Response({"detail": "amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "")
        with transaction.atomic():
            portfolio.cash_balance = (portfolio.cash_balance or Decimal("0")) + amount
            portfolio.equity = (portfolio.equity or Decimal("0")) + amount
            portfolio.save(update_fields=["cash_balance", "equity"])
            movement = PortfolioCashMovement.objects.create(
                portfolio=portfolio,
                performed_by=request.user if request.user.is_authenticated else None,
                movement_type="deposit",
                amount=amount,
                reason=reason,
            )
        return Response(PortfolioCashMovementSerializer(movement).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        portfolio = self.get_object()
        amount = Decimal(str(request.data.get("amount", "0")))
        if amount <= 0:
            return Response({"detail": "amount must be positive"}, status=status.HTTP_400_BAD_REQUEST)
        if portfolio.cash_balance < amount:
            return Response({"detail": "insufficient cash balance"}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get("reason", "")
        with transaction.atomic():
            portfolio.cash_balance = portfolio.cash_balance - amount
            portfolio.equity = portfolio.equity - amount
            portfolio.save(update_fields=["cash_balance", "equity"])
            movement = PortfolioCashMovement.objects.create(
                portfolio=portfolio,
                performed_by=request.user if request.user.is_authenticated else None,
                movement_type="withdrawal",
                amount=amount,
                reason=reason,
            )
        return Response(PortfolioCashMovementSerializer(movement).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def performance(self, request, pk=None):
        portfolio = self.get_object()
        latest_snapshot = portfolio.snapshots.order_by("-timestamp").first()
        start_equity = portfolio.starting_balance or Decimal("0")
        if start_equity <= 0:
            start_equity = Decimal("1")
        equity = latest_snapshot.equity if latest_snapshot else portfolio.equity
        cash = latest_snapshot.cash if latest_snapshot else portfolio.cash_balance
        realized = (
            latest_snapshot.realized_pnl if latest_snapshot else portfolio.realized_pnl
        )
        unrealized = (
            latest_snapshot.unrealized_pnl
            if latest_snapshot
            else portfolio.unrealized_pnl
        )
        total_return_pct = float(
            ((equity - start_equity) / start_equity) * Decimal("100")
        )
        first_snapshot = portfolio.snapshots.order_by("timestamp").first()
        started_at = (
            first_snapshot.timestamp if first_snapshot else portfolio.created_at
        )
        days_active = max(
            1, (timezone.now().date() - started_at.date()).days + 1
        )
        payload = {
            "portfolio_id": portfolio.id,
            "equity": str(equity),
            "cash": str(cash),
            "total_return_pct": total_return_pct,
            "realized_pnl": str(realized),
            "unrealized_pnl": str(unrealized),
            "days_active": days_active,
        }
        if latest_snapshot:
            payload["latest_snapshot"] = PerformanceSnapshotSerializer(
                latest_snapshot
            ).data
        return Response(payload)

    @action(detail=True, methods=["get"], url_path="performance/snapshots")
    def performance_snapshots(self, request, pk=None):
        portfolio = self.get_object()
        limit = min(
            365,
            max(5, int(request.query_params.get("limit", 90))),
        )
        qs = list(portfolio.snapshots.order_by("-timestamp")[:limit])
        qs.reverse()
        serializer = PerformanceSnapshotSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="cash-movements")
    def cash_movements(self, request, pk=None):
        portfolio = self.get_object()
        limit = min(200, max(10, int(request.query_params.get("limit", 50))))
        movements = portfolio.cash_movements.order_by("-created_at")[:limit]
        return Response(PortfolioCashMovementSerializer(movements, many=True).data)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = PaperOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaperOrder.objects.filter(
            portfolio__user=self.request.user
        ).select_related("portfolio")

    def perform_create(self, serializer):
        portfolio = serializer.validated_data["portfolio"]
        if portfolio.user != self.request.user:
            raise PermissionDenied("Cannot place orders on this portfolio")
        # Enforce max positions cap if configured
        if portfolio.max_positions:
            existing = portfolio.positions.count()
            symbol = serializer.validated_data.get("symbol")
            has_symbol = portfolio.positions.filter(symbol=symbol).exists()
            if not has_symbol and existing >= portfolio.max_positions:
                raise PermissionDenied("Portfolio position cap reached.")
        self._enforce_exposure_caps(portfolio, serializer.validated_data)
        serializer.save()

    def _estimate_notional(self, data):
        notional = data.get("notional")
        if notional:
            try:
                return abs(Decimal(notional))
            except Exception:
                return None
        qty = data.get("quantity")
        if not qty:
            return None
        price = data.get("limit_price") or data.get("stop_price")
        if not price:
            try:
                quote = get_market_data_provider().get_quote(data.get("symbol"))
                price = Decimal(str(quote.price))
            except Exception:
                price = None
        try:
            return abs(Decimal(qty) * Decimal(price)) if price is not None else None
        except Exception:
            return None

    def _enforce_exposure_caps(self, portfolio, data):
        notional = self._estimate_notional(data)
        if notional is None or notional <= 0:
            return
        equity = portfolio.equity or portfolio.cash_balance or Decimal("0")
        if equity <= 0:
            return
        symbol = data.get("symbol")
        # Single position cap
        if portfolio.max_single_position_pct:
            limit_value = equity * (portfolio.max_single_position_pct / Decimal("100"))
            current_pos = portfolio.positions.filter(symbol=symbol).first()
            current_val = abs(current_pos.market_value) if current_pos and current_pos.market_value else Decimal("0")
            if current_val + notional > limit_value:
                raise PermissionDenied("Single-position exposure cap exceeded.")
        # Gross exposure cap
        if portfolio.max_gross_exposure_pct:
            gross_limit = equity * (portfolio.max_gross_exposure_pct / Decimal("100"))
            current_gross = Decimal("0")
            for p in portfolio.positions.all():
                if p.market_value:
                    current_gross += abs(p.market_value)
            if current_gross + notional > gross_limit:
                raise PermissionDenied("Gross exposure cap exceeded.")


class TradeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaperTradeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaperTrade.objects.filter(portfolio__user=self.request.user).select_related(
            "portfolio", "order"
        )


class StrategyViewSet(viewsets.ModelViewSet):
    serializer_class = StrategySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Strategy.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"])
    def validate_config(self, request):
        serializer = StrategySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"status": "ok"})

    @action(detail=False, methods=["post"])
    def dry_run(self, request):
        strategy = Strategy(user=request.user, config=request.data.get("config", {}), name="dry-run")
        runner = StrategyRunner()
        matches = runner.dry_run(strategy)
        return Response({"matches": matches})


class LeaderboardSeasonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaderboardSeasonSerializer
    permission_classes = [permissions.AllowAny]
    queryset = LeaderboardSeason.objects.all().order_by("-start_date")


class LeaderboardEntryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaderboardEntrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = LeaderboardEntry.objects.select_related("portfolio", "season").order_by(
            "rank"
        )
        season_id = self.request.query_params.get("season")
        metric = self.request.query_params.get("metric")
        if season_id:
            qs = qs.filter(season_id=season_id)
        if metric:
            qs = qs.filter(metric=metric)
        return qs


class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaperPositionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            PaperPosition.objects.filter(portfolio__user=self.request.user)
            .select_related("portfolio", "instrument")
            .order_by("symbol")
        )

    def _get_quote_decimal(self, symbol: str) -> Decimal:
        quote = get_market_data_provider().get_quote(symbol)
        return Decimal(str(quote.price))

    def _recalc_portfolio(self, portfolio: PaperPortfolio):
        totals = portfolio.positions.aggregate(
            total_mv=Sum("market_value"), total_unreal=Sum("unrealized_pnl")
        )
        portfolio.unrealized_pnl = totals.get("total_unreal") or Decimal("0")
        total_mv = totals.get("total_mv") or Decimal("0")
        portfolio.equity = (portfolio.cash_balance or Decimal("0")) + total_mv
        portfolio.save(update_fields=["equity", "unrealized_pnl"])

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        position = self.get_object()
        portfolio = position.portfolio
        if portfolio.user != request.user:
            raise PermissionDenied("Not your position.")
        limit_price = request.data.get("limit_price")
        price = self._get_quote_decimal(position.symbol)
        if limit_price is not None:
            try:
                limit_price = Decimal(str(limit_price))
                if position.quantity > 0 and price < limit_price:
                    return Response(
                        {"detail": "Live price below limit_price"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if position.quantity < 0 and price > limit_price:
                    return Response(
                        {"detail": "Live price above limit_price"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception:
                pass
        if position.quantity == 0:
            return Response({"detail": "Already closed"}, status=status.HTTP_200_OK)
        qty = position.quantity
        proceeds = qty * price
        portfolio.cash_balance += proceeds
        realized = Decimal("0")
        if qty > 0:
            realized = (price - position.avg_price) * qty
        elif qty < 0:
            realized = (position.avg_price - price) * abs(qty)
        portfolio.realized_pnl += realized
        portfolio.save(update_fields=["cash_balance", "realized_pnl"])
        position.quantity = Decimal("0")
        position.market_value = Decimal("0")
        position.unrealized_pnl = Decimal("0")
        position.save(update_fields=["quantity", "market_value", "unrealized_pnl"])
        self._recalc_portfolio(portfolio)
        return Response(
            {
                "detail": "Closed position",
                "realized_pnl": str(realized),
                "cash_balance": str(portfolio.cash_balance),
            }
        )

    @action(detail=True, methods=["post"])
    def rebalance(self, request, pk=None):
        position = self.get_object()
        portfolio = position.portfolio
        if portfolio.user != request.user:
            raise PermissionDenied("Not your position.")
        target_pct = Decimal(str(request.data.get("target_pct", "0")))
        if target_pct <= 0 or target_pct > 100:
            return Response(
                {"detail": "target_pct must be between 0 and 100"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        price = self._get_quote_decimal(position.symbol)
        limit_price = request.data.get("limit_price")
        if limit_price is not None:
            try:
                limit_price = Decimal(str(limit_price))
                # For buys, ensure live price does not exceed limit; for sells ensure not below limit
                if price > limit_price and target_pct > 0:
                    return Response(
                        {"detail": "Live price above limit_price"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception:
                pass
        equity = portfolio.equity or portfolio.cash_balance or Decimal("0")
        if equity <= 0:
            return Response(
                {"detail": "Cannot rebalance with zero equity"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        desired_value = equity * (target_pct / Decimal("100"))
        delta_value = desired_value - (position.market_value or Decimal("0"))
        if abs(delta_value) < Decimal("0.01"):
            return Response({"detail": "Already at target"}, status=status.HTTP_200_OK)
        delta_qty = delta_value / price
        realized = Decimal("0")
        if delta_qty > 0:
            # buy more
            new_qty = position.quantity + delta_qty
            if new_qty > 0:
                position.avg_price = (
                    (position.quantity * position.avg_price) + delta_value
                ) / new_qty
            position.quantity = new_qty
            portfolio.cash_balance -= delta_value
        else:
            # sell some
            sell_qty = abs(delta_qty)
            position.quantity = max(Decimal("0"), position.quantity - sell_qty)
            realized = (price - position.avg_price) * sell_qty
            portfolio.cash_balance += abs(delta_value)
            portfolio.realized_pnl += realized
        position.market_value = position.quantity * price
        position.unrealized_pnl = position.market_value - (position.quantity * position.avg_price)
        position.save(
            update_fields=["quantity", "avg_price", "market_value", "unrealized_pnl"]
        )
        self._recalc_portfolio(portfolio)
        return Response(
            {
                "detail": "Rebalanced",
                "quantity": str(position.quantity),
                "avg_price": str(position.avg_price),
                "market_value": str(position.market_value),
                "realized_pnl": str(realized),
                "cash_balance": str(portfolio.cash_balance),
            }
        )


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InstrumentSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Instrument.objects.all().order_by("symbol")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(symbol__icontains=q.upper())
        limit = min(200, max(10, int(self.request.query_params.get("limit", 100))))
        return qs[:limit]


class QuoteView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        symbols = request.query_params.get("symbols", "")
        if not symbols:
            return Response([], status=status.HTTP_200_OK)
        data = []
        provider = get_market_data_provider()
        for sym in filter(None, [s.strip() for s in symbols.split(",")]):
            try:
                q = provider.get_quote(sym)
                data.append(
                    {
                        "symbol": q.symbol,
                        "price": q.price,
                        "timestamp": q.timestamp,
                        "bid": q.bid,
                        "ask": q.ask,
                    }
                )
            except Exception:
                continue
        return Response(data)
from paper.engine.runner import StrategyRunner
