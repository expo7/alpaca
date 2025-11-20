from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from paper.models import (
    PaperPortfolio,
    PaperOrder,
    PaperTrade,
    Strategy,
    LeaderboardSeason,
    LeaderboardEntry,
)
from .serializers import (
    PaperPortfolioSerializer,
    PaperOrderSerializer,
    PaperTradeSerializer,
    StrategySerializer,
    LeaderboardSeasonSerializer,
    LeaderboardEntrySerializer,
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
