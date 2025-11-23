from unittest import result
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from django.utils.dateparse import parse_datetime
from .serializers import (
    StockScoreSerializer,
    StrategySpecSerializer,
    BotConfigSerializer,
    BotSerializer,
)
from .models import StockScore, StrategySpec, BotConfig, Bot
from .services import rank_symbols, compute_and_store
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from .strategy_templates import get_template, list_templates

# [NOTE-WATCHLIST-VIEWS]
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from .models import Watchlist, WatchlistItem
from .serializers import WatchlistSerializer, WatchlistItemSerializer

# --- Sparkline endpoint (add near other imports) ---
import yfinance as yf
from yfinance import cache as yf_cache
import tempfile
from pathlib import Path
from .models import Alert
from .models import AlertEvent
from .serializers import AlertSerializer
from .serializers import AlertEventSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from ranker.scoring import technical_score, fundamental_score
from ranker.models import WatchlistItem
from rest_framework import generics, permissions
from .models import UserSettings
from .serializers import UserSettingsSerializer
from .metrics import get_yf_counter, increment_yf_counter
from .tasks import compute_next_run_at, run_bot_once

# ranker/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .backtest import run_basket_backtest

# ranker/views.py
from datetime import date

from rest_framework import generics, permissions

from .models import BacktestRun
from .serializers import BacktestRunSerializer

# ranker/views.py
from rest_framework import viewsets, permissions
from .models import BacktestConfig
from .serializers import BacktestConfigSerializer
from rest_framework import viewsets, permissions
from .models import BacktestRun
from .serializers import BacktestRunSerializer

# ranker/views.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import UserPreference
from .serializers import UserPreferenceSerializer, UserSignupSerializer
from rest_framework_simplejwt.tokens import RefreshToken

SCREEN_CHOICES = [
    "aggressive_small_caps",
    "conservative_foreign_funds",
    "day_gainers",
    "day_losers",
    "growth_technology_stocks",
    "high_yield_bond",
    "most_actives",
    "most_shorted_stocks",
    "portfolio_anchors",
    "small_cap_gainers",
    "top_mutual_funds",
    "undervalued_growth_stocks",
    "undervalued_large_caps",
]


class RegisterView(APIView):
    """
    POST /api/register/
    Create a user and return tokens so the UI can immediately sign in.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "id": user.id,
                "username": user.get_username(),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class AggressiveSmallCapsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        screen = request.query_params.get("screen", "aggressive_small_caps")
        if screen not in SCREEN_CHOICES:
            return Response(
                {"error": f"screen must be one of {SCREEN_CHOICES}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cache_dir = Path(tempfile.gettempdir()) / "yfinance-cache"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        yf_cache.set_cache_location(str(cache_dir))
        try:
            increment_yf_counter()
            data = yf.screen(screen)
            quotes = data.get("quotes") or []
            symbols = [
                quote.get("symbol")
                for quote in quotes
                if quote.get("symbol")
            ]
            return Response({"screen": screen, "symbols": symbols})
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserPreferenceView(APIView):
    """
    GET  /api/user-prefs/   -> current user's email/scan prefs
    PATCH /api/user-prefs/  -> update fields
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        prefs, _ = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(prefs)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        prefs, _ = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(prefs, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class BacktestRunViewSet(viewsets.ModelViewSet):
    """
    /api/backtest-runs/  (list, create)
    /api/backtest-runs/{id}/ (retrieve, update, delete)
    """

    serializer_class = BacktestRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BacktestRun.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BacktestConfigViewSet(viewsets.ModelViewSet):
    """
    CRUD for saved / named backtest templates.
    """

    serializer_class = BacktestConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BacktestConfig.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BacktestRunListView(generics.ListAPIView):
    """
    GET /api/backtests/history/  -> list of this user's previous runs
    (most recent first)
    """

    serializer_class = BacktestRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BacktestRun.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )


def _structured_errors(errors, prefix=""):
    """Flatten DRF serializer error structures into [{field, message}] entries."""

    def _field_name(current_prefix):
        return current_prefix or "non_field_errors"

    flattened = []

    if isinstance(errors, dict):
        for key, value in errors.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.extend(_structured_errors(value, next_prefix))
    elif isinstance(errors, list):
        for idx, value in enumerate(errors):
            if isinstance(value, (dict, list)):
                next_prefix = f"{prefix}[{idx}]" if prefix else str(idx)
                flattened.extend(_structured_errors(value, next_prefix))
            else:
                flattened.append({"field": _field_name(prefix), "message": str(value)})
    else:
        flattened.append({"field": _field_name(prefix), "message": str(errors)})

    return flattened

class StrategyValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = StrategySpecSerializer(data=request.data)
        if serializer.is_valid():
            StrategySpec.objects.create(
                user=request.user,
                name=serializer.validated_data.get("name", ""),
                spec=serializer.validated_data,
            )
            return Response({"valid": True, "errors": []}, status=status.HTTP_200_OK)

        errors = _structured_errors(serializer.errors)

        return Response({"valid": False, "errors": errors}, status=status.HTTP_200_OK)


class StrategyTemplateListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(list_templates(), status=status.HTTP_200_OK)


class StrategyTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, template_id, *args, **kwargs):
        template = get_template(template_id)
        if not template:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(template, status=status.HTTP_200_OK)


def _build_backtest_stats(summary):
    return {
        "start_equity": summary.get("initial_capital"),
        "end_equity": summary.get("final_value"),
        "return_pct": (summary.get("total_return") or 0.0) * 100.0,
        "max_drawdown_pct": (summary.get("max_drawdown") or 0.0) * 100.0,
        "num_trades": summary.get("num_trades", 0),
        "win_rate_pct": summary.get("win_rate_pct", 0.0),
        "volatility_annualized": summary.get("volatility_annualized"),
        "sharpe_ratio": summary.get("sharpe_ratio"),
        "max_drawdown_duration_bars": summary.get("max_drawdown_duration_bars"),
    }


class StrategyBacktestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        payload = request.data or {}
        strategy_data = payload.get("strategy")
        bot_data = payload.get("bot")
        start_date = payload.get("start_date") or payload.get("start")
        end_date = payload.get("end_date") or payload.get("end")

        strategy_serializer = StrategySpecSerializer(data=strategy_data)
        bot_serializer = BotConfigSerializer(data=bot_data)

        errors = []
        if not strategy_serializer.is_valid():
            errors.extend(_structured_errors(strategy_serializer.errors, prefix="strategy"))
        if not bot_serializer.is_valid():
            errors.extend(_structured_errors(bot_serializer.errors, prefix="bot"))
        if not start_date or not end_date:
            errors.append(
                {"field": "dates", "message": "start_date and end_date are required"}
            )

        if errors:
            return Response({"valid": False, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        strategy_obj = StrategySpec.objects.create(
            user=request.user,
            name=strategy_serializer.validated_data.get("name", ""),
            spec=strategy_serializer.validated_data,
        )
        bot_obj = BotConfig.objects.create(
            user=request.user,
            name=bot_serializer.validated_data.get("name", ""),
            config=bot_serializer.validated_data,
        )

        bot_cfg = bot_serializer.validated_data
        try:
            result = run_basket_backtest(
                tickers=bot_cfg["symbols"],
                start=str(start_date),
                end=str(end_date),
                benchmark=bot_cfg.get("benchmark", "SPY"),
                initial_capital=float(bot_cfg.get("capital", 10000.0)),
                rebalance_days=int(bot_cfg.get("rebalance_days", 5)),
                top_n=bot_cfg.get("top_n"),
                commission_per_trade=float(bot_cfg.get("commission_per_trade", 0.0)),
                commission_pct=float(bot_cfg.get("commission_pct", 0.0)),
                slippage_model=bot_cfg.get("slippage_model", "none"),
                slippage_bps=float(bot_cfg.get("slippage_bps", 0.0)),
                max_open_positions=bot_cfg.get("max_open_positions"),
                max_per_position_pct=float(bot_cfg.get("max_per_position_pct", 1.0)),
                strategy_spec=strategy_serializer.validated_data,
            )
        except Exception as exc:
            return Response(
                {
                    "valid": False,
                    "errors": [
                        {
                            "field": "backtest",
                            "message": f"backtest failed: {exc}",
                        }
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        summary = result.summary or {}
        return Response(
            {
                "strategy_id": strategy_obj.id,
                "bot_config_id": bot_obj.id,
                "trades": summary.get("trades", []),
                "equity_curve": result.equity_curve,
                "stats": _build_backtest_stats(summary),
                "per_ticker": result.per_ticker or [],
            },
            status=status.HTTP_200_OK,
        )


class BacktestView(APIView):
    """
    POST /api/backtest/

    {
      "tickers": ["AAPL","MSFT","NVDA"],
      "start": "2024-08-01",
      "end": "2024-11-13",
      "initial_capital": 10000,
      "rebalance_days": 5,
      "top_n": 3
    }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data or {}

        tickers = data.get("tickers") or data.get("symbols") or []
        start = data.get("start")
        end = data.get("end")
        benchmark = data.get("benchmark", "SPY")

        initial_capital = data.get("initial_capital", 10_000.0)
        rebalance_days = data.get("rebalance_days", 5)
        top_n = data.get("top_n", None)
        commission_per_trade = data.get("commission_per_trade", 0.0)
        commission_pct = data.get("commission_pct", 0.0)
        slippage_model = data.get("slippage_model", "none")
        slippage_bps = data.get("slippage_bps", 0.0)
        max_open_positions = data.get("max_open_positions")
        max_per_position_pct = data.get("max_per_position_pct", 1.0)

        # allow tickers as comma-separated string too
        if isinstance(tickers, str):
            tickers = [s.strip() for s in tickers.split(",") if s.strip()]

        if not tickers:
            return Response(
                {"error": "tickers list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not start or not end:
            return Response(
                {"error": "start and end are required (YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = run_basket_backtest(
                tickers=tickers,
                start=start,
                end=end,
                benchmark=benchmark,
                initial_capital=float(initial_capital),
                rebalance_days=int(rebalance_days),
                top_n=int(top_n) if top_n is not None else None,
                commission_per_trade=float(commission_per_trade),
                commission_pct=float(commission_pct),
                slippage_model=slippage_model,
                slippage_bps=float(slippage_bps),
                max_open_positions=int(max_open_positions)
                if max_open_positions is not None
                else None,
                max_per_position_pct=float(max_per_position_pct),
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # This is what was producing the big HTML error page before.
            # We wrap it so the frontend always gets JSON instead.
            return Response(
                {"error": f"backtest failed: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "tickers": result.tickers,
                "start": result.start,
                "end": result.end,
                "equity_curve": result.equity_curve,
                "benchmark": {
                    "symbol": result.benchmark_symbol,
                    "curve": result.benchmark_curve,
                },
                "summary": result.summary,
                "per_ticker": result.per_ticker,
            }
        )


class UserSettingsMeView(generics.RetrieveUpdateAPIView):
    """
    Get or update settings for the current user.
    """

    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        settings_obj, _ = UserSettings.objects.get_or_create(user=user)
        return settings_obj


# ... existing viewsets ...


class AlertEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only history of alert firings for the current user.
    """

    serializer_class = AlertEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = AlertEvent.objects.select_related("alert", "alert__user")
        user = self.request.user
        qs = qs.filter(alert__user=user)

        # Optional filters: ?symbol=TNXP or ?alert=4
        sym = self.request.query_params.get("symbol")
        if sym:
            qs = qs.filter(symbol__iexact=sym)

        alert_id = self.request.query_params.get("alert")
        if alert_id:
            qs = qs.filter(alert_id=alert_id)

        return qs


class AlertViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AlertSerializer

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        alert = self.get_object()
        now = timezone.now()

        # Determine symbols to test
        if alert.alert_type == alert.TYPE_SYMBOL:
            symbols = [alert.symbol.upper()]
        else:
            symbols = list(
                WatchlistItem.objects.filter(watchlist=alert.watchlist).values_list(
                    "symbol", flat=True
                )
            )

        results = []

        for sym in symbols:
            try:
                tech, _ = technical_score(sym)
                fund, _ = fundamental_score(sym)
                final = 0.6 * tech + 0.4 * fund

                triggered = (
                    final >= alert.min_final_score
                    and (alert.min_tech_score is None or tech >= alert.min_tech_score)
                    and (alert.min_fund_score is None or fund >= alert.min_fund_score)
                )

                results.append(
                    {
                        "symbol": sym,
                        "tech_score": tech,
                        "fund_score": fund,
                        "final_score": final,
                        "triggered": triggered,
                    }
                )

            except Exception as e:
                results.append({"symbol": sym, "error": str(e)})

        return Response(
            {"alert_id": alert.id, "timestamp": now.isoformat(), "results": results}
        )

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SparklineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/sparkline?symbols=AAPL,NVDA&period=1mo&interval=1d
        Returns { results: [{symbol, closes:[...]}] }
        """
        symbols = request.GET.get("symbols", "")
        period = request.GET.get("period", "1mo")
        interval = request.GET.get("interval", "1d")
        if not symbols:
            return Response({"results": []})
        out = []
        for sym in [s.strip().upper() for s in symbols.split(",") if s.strip()]:
            cache_key = f"ranker:sparkline:{sym}:{period}:{interval}"
            cached = cache.get(cache_key)
            if cached is not None:
                out.append(cached)
                continue
            try:
                increment_yf_counter()
                df = yf.Ticker(sym).history(period=period, interval=interval)
                closes = [
                    float(x) for x in df["Close"].dropna().tail(90).tolist()
                ]  # cap length
                entry = {"symbol": sym, "closes": closes}
                out.append(entry)
                cache.set(cache_key, entry, 60 * 10)
            except Exception:
                out.append({"symbol": sym, "closes": []})
        return Response({"results": out})


class BotViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BotSerializer

    def get_queryset(self):
        return Bot.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, state=Bot.STATE_STOPPED, next_run_at=None)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        bot = self.get_object()
        run_now = bool(request.data.get("run_now"))
        if bot.state != Bot.STATE_RUNNING:
            bot.state = Bot.STATE_RUNNING
            bot.next_run_at = compute_next_run_at(bot)
            bot.save(update_fields=["state", "next_run_at"])
        elif bot.next_run_at is None:
            bot.next_run_at = compute_next_run_at(bot)
            bot.save(update_fields=["next_run_at"])

        if run_now and bot.state == Bot.STATE_RUNNING:
            run_bot_once.delay(bot.id)

        serializer = self.get_serializer(bot)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        bot = self.get_object()
        if bot.state != Bot.STATE_PAUSED:
            bot.state = Bot.STATE_PAUSED
            bot.next_run_at = None
            bot.save(update_fields=["state", "next_run_at"])
        serializer = self.get_serializer(bot)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        bot = self.get_object()
        updates = []
        if bot.state != Bot.STATE_STOPPED:
            bot.state = Bot.STATE_STOPPED
            updates.append("state")
        if bot.next_run_at is not None:
            bot.next_run_at = None
            updates.append("next_run_at")
        if updates:
            bot.save(update_fields=updates)
        serializer = self.get_serializer(bot)
        return Response(serializer.data)


class YFinanceUsageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({"count": get_yf_counter()})


class WatchlistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WatchlistItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WatchlistItemSerializer

    def get_queryset(self):
        # nested: /api/watchlists/<watchlist_id>/items/
        wid = self.kwargs.get("watchlist_pk")
        return WatchlistItem.objects.filter(
            watchlist__id=wid, watchlist__user=self.request.user
        )

    def perform_create(self, serializer):
        wid = self.kwargs.get("watchlist_pk")
        wl = Watchlist.objects.get(id=wid, user=self.request.user)
        serializer.save(watchlist=wl)


DEFAULT_TA_WEIGHTS = {
    "trend": 0.35,
    "momentum": 0.25,
    "volume": 0.20,
    "volatility": 0.10,
    "meanreversion": 0.10,
}


class RankView(APIView):
    """
    POST /api/rank
    {
      "tickers": ["AAPL","MSFT","NVDA"],
      "tech_weight": 0.6,
      "fund_weight": 0.4,
      "ta_weights": {"trend":0.45,"momentum":0.25,"volume":0.15,"volatility":0.10,"meanreversion":0.05}  # optional
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tickers = request.data.get("tickers", [])
        if not tickers or not isinstance(tickers, list):
            return Response({"detail": "tickers must be a non-empty list"}, status=400)

        tech_weight = float(request.data.get("tech_weight", 0.5))
        fund_weight = float(request.data.get("fund_weight", 0.5))

        # Optional TA sub-weights
        ta_weights = request.data.get("ta_weights")
        if ta_weights:
            # sanitize & merge with defaults
            ta_weights = {
                **DEFAULT_TA_WEIGHTS,
                **{
                    k: float(v)
                    for k, v in ta_weights.items()
                    if k in DEFAULT_TA_WEIGHTS
                },
            }

        ranked, errors = rank_symbols(
            tickers, tech_weight, fund_weight, extra={"ta_weights": ta_weights}
        )
        data = StockScoreSerializer(ranked, many=True).data
        return Response({"count": len(data), "results": data, "errors": errors})


class RefreshView(APIView):
    """
    POST /api/refresh
    { "tickers": ["AAPL","MSFT"] }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tickers = request.data.get("tickers", [])
        if not tickers:
            return Response({"detail": "tickers required"}, status=400)
        out = []
        for t in tickers:
            out.append(compute_and_store(t))
        return Response(StockScoreSerializer(out, many=True).data, status=200)


class ScoresListView(ListAPIView):
    """
    GET /api/scores?since=2025-01-01T00:00:00&symbols=AAPL,MSFT
    """

    permission_classes = [IsAuthenticated]
    serializer_class = StockScoreSerializer

    def get_queryset(self):
        qs = StockScore.objects.all().order_by("-final_score")
        since = self.request.query_params.get("since")
        if since:
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(asof__gte=dt)
        symbols = self.request.query_params.get("symbols")
        if symbols:
            flt = [s.strip().upper() for s in symbols.split(",")]
            qs = qs.filter(symbol__in=flt)
        return qs


class ExplainView(APIView):
    permission_classes = [IsAuthenticated]
