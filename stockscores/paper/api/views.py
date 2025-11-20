from decimal import Decimal

from django.utils import timezone
from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction

from paper.models import (
    PaperPortfolio,
    PaperOrder,
    PaperTrade,
    Strategy,
    LeaderboardSeason,
    LeaderboardEntry,
    PaperPosition,
    PortfolioResetLog,
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
)


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
            raise permissions.PermissionDenied("Cannot place orders on this portfolio")
        # Enforce max positions cap if configured
        if portfolio.max_positions:
            existing = portfolio.positions.count()
            symbol = serializer.validated_data.get("symbol")
            has_symbol = portfolio.positions.filter(symbol=symbol).exists()
            if not has_symbol and existing >= portfolio.max_positions:
                raise permissions.PermissionDenied("Portfolio position cap reached.")
        serializer.save()


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
from paper.engine.runner import StrategyRunner
