# [NOTE-WATCHLIST-URLS]
from django.urls import path, include
from rest_framework_nested import routers
from .views import BacktestConfigViewSet
from .views import (
    RankView,
    RefreshView,
    ScoresListView,
    ExplainView,
    WatchlistViewSet,
    WatchlistItemViewSet,
    SparklineView,
    AlertViewSet,
    AlertEventViewSet,
    UserSettingsMeView,
    BacktestView,
    BacktestRunListView,
    BacktestRunViewSet,
    UserPreferenceView,  # <-- add this import
)

router = routers.SimpleRouter()
router.register(r"watchlists", WatchlistViewSet, basename="watchlist")
router.register(r"alerts", AlertViewSet, basename="alert")
router.register(r"alert-events", AlertEventViewSet, basename="alert-event")  # <-- NEW
router.register(r"backtests", BacktestConfigViewSet, basename="backtest-config")
# nested router for items under a watchlist
nested = routers.NestedSimpleRouter(router, r"watchlists", lookup="watchlist")
nested.register(r"items", WatchlistItemViewSet, basename="watchlist-items")
router.register(r"backtest-runs", BacktestRunViewSet, basename="backtest-run")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(nested.urls)),
    # existing endpoints
    path("sparkline", SparklineView.as_view(), name="sparkline"),
    path("rank", RankView.as_view(), name="rank"),
    path("refresh", RefreshView.as_view(), name="refresh"),
    path("scores", ScoresListView.as_view(), name="scores"),
    path("explain", ExplainView.as_view(), name="explain"),
    path("settings/me", UserSettingsMeView.as_view(), name="user-settings-me"),
    path("backtest/", BacktestView.as_view(), name="backtest"),
    path("backtests/", BacktestRunListView.as_view(), name="backtest-runs"),
]
