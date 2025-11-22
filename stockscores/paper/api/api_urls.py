from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    PortfolioViewSet,
    PositionViewSet,
    QuoteView,
    SymbolIntervalView,
    InstrumentViewSet,
    OrderViewSet,
    TradeViewSet,
    StrategyViewSet,
    LeaderboardSeasonViewSet,
    LeaderboardEntryViewSet,
)

router = DefaultRouter()
router.register("paper/portfolios", PortfolioViewSet, basename="paper-portfolio")
router.register("paper/positions", PositionViewSet, basename="paper-position")
router.register("paper/orders", OrderViewSet, basename="paper-order")
router.register("paper/trades", TradeViewSet, basename="paper-trade")
router.register("paper/strategies", StrategyViewSet, basename="paper-strategy")
router.register(
    "paper/leaderboards/seasons",
    LeaderboardSeasonViewSet,
    basename="leaderboard-season",
)
router.register(
    "paper/leaderboards/entries",
    LeaderboardEntryViewSet,
    basename="leaderboard-entry",
)
router.register("paper/instruments", InstrumentViewSet, basename="instrument")
quote_list = QuoteView.as_view()

urlpatterns = router.urls + [
    path("paper/quotes/", quote_list, name="paper-quote-list"),
    path(
        "paper/symbols/<str:symbol>/interval/",
        SymbolIntervalView.as_view(),
        name="paper-symbol-interval",
    ),
]
