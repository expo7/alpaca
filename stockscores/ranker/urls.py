# [NOTE-WATCHLIST-URLS]
from django.urls import path
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
    BacktestConfigViewSet,
    StrategyValidateView,
    StrategyBacktestView,
    BacktestBatchCreateView,
    BacktestBatchDetailView,
    BacktestBatchListView,
    StrategyTemplateDetailView,
    StrategyTemplateListView,
    UserPreferenceView,
    RegisterView,
    AggressiveSmallCapsView,
    BotViewSet,
    YFinanceUsageView,
)

watchlist_list = WatchlistViewSet.as_view({"get": "list", "post": "create"})
watchlist_detail = WatchlistViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

watchlist_items = WatchlistItemViewSet.as_view({"get": "list", "post": "create"})
watchlist_item_detail = WatchlistItemViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

alert_list = AlertViewSet.as_view({"get": "list", "post": "create"})
alert_detail = AlertViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)
alert_test = AlertViewSet.as_view({"post": "test"})

alert_event_list = AlertEventViewSet.as_view({"get": "list"})
alert_event_detail = AlertEventViewSet.as_view({"get": "retrieve"})

backtest_config_list = BacktestConfigViewSet.as_view({"get": "list", "post": "create"})
backtest_config_detail = BacktestConfigViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

backtest_run_list = BacktestRunViewSet.as_view({"get": "list", "post": "create"})
backtest_run_detail = BacktestRunViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

bot_list = BotViewSet.as_view({"get": "list", "post": "create"})
bot_detail = BotViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)
bot_start = BotViewSet.as_view({"post": "start"})
bot_pause = BotViewSet.as_view({"post": "pause"})
bot_stop = BotViewSet.as_view({"post": "stop"})

urlpatterns = [
    # Watchlists + nested items
    path("watchlists/", watchlist_list, name="watchlist-list"),
    path("watchlists/<int:pk>/", watchlist_detail, name="watchlist-detail"),
    path(
        "watchlists/<int:watchlist_pk>/items/",
        watchlist_items,
        name="watchlist-item-list",
    ),
    path(
        "watchlists/<int:watchlist_pk>/items/<int:pk>/",
        watchlist_item_detail,
        name="watchlist-item-detail",
    ),
    # Alerts + events
    path("alerts/", alert_list, name="alert-list"),
    path("alerts/<int:pk>/", alert_detail, name="alert-detail"),
    path("alerts/<int:pk>/test/", alert_test, name="alert-test"),
    path("alert-events/", alert_event_list, name="alert-event-list"),
    path("alert-events/<int:pk>/", alert_event_detail, name="alert-event-detail"),
    # Bots
    path("bots/", bot_list, name="bot-list"),
    path("bots/<int:pk>/", bot_detail, name="bot-detail"),
    path("bots/<int:pk>/start/", bot_start, name="bot-start"),
    path("bots/<int:pk>/pause/", bot_pause, name="bot-pause"),
    path("bots/<int:pk>/stop/", bot_stop, name="bot-stop"),
    # Backtests + configs
    path("backtests/", backtest_config_list, name="backtest-config-list"),
    path("backtests/<int:pk>/", backtest_config_detail, name="backtest-config-detail"),
    path("backtest-runs/", backtest_run_list, name="backtest-run-list"),
    path("backtest-runs/<int:pk>/", backtest_run_detail, name="backtest-run-detail"),
    # existing endpoints
    path("sparkline", SparklineView.as_view(), name="sparkline"),
    path("rank", RankView.as_view(), name="rank"),
    path("refresh", RefreshView.as_view(), name="refresh"),
    path("scores", ScoresListView.as_view(), name="scores"),
    path("explain", ExplainView.as_view(), name="explain"),
    path("settings/me", UserSettingsMeView.as_view(), name="user-settings-me"),
    path("user-prefs/", UserPreferenceView.as_view(), name="user-preferences"),
    path("register/", RegisterView.as_view(), name="register"),
    path("backtest/", BacktestView.as_view(), name="backtest"),
    path(
        "strategies/validate/",
        StrategyValidateView.as_view(),
        name="strategy-validate",
    ),
    path(
        "strategies/templates/",
        StrategyTemplateListView.as_view(),
        name="strategy-template-list",
    ),
    path(
        "strategies/templates/<str:template_id>/",
        StrategyTemplateDetailView.as_view(),
        name="strategy-template-detail",
    ),
    path(
        "backtests/run/",
        StrategyBacktestView.as_view(),
        name="strategy-backtest-run",
    ),
    path(
        "backtests/batch/",
        BacktestBatchCreateView.as_view(),
        name="strategy-backtest-batch",
    ),
    path(
        "backtests/batch/list/",
        BacktestBatchListView.as_view(),
        name="strategy-backtest-batch-list",
    ),
    path(
        "backtests/batch/<int:batch_id>/",
        BacktestBatchDetailView.as_view(),
        name="strategy-backtest-batch-detail",
    ),
    path("backtests/history/", BacktestRunListView.as_view(), name="backtest-runs"),
    path(
        "default-tickers/aggressive-small-caps/",
        AggressiveSmallCapsView.as_view(),
        name="aggressive-small-caps",
    ),
    path("metrics/yfinance/", YFinanceUsageView.as_view(), name="yfinance-usage"),
]
