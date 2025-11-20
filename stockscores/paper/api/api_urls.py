from rest_framework.routers import DefaultRouter

from .views import (
    PortfolioViewSet,
    PositionViewSet,
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
