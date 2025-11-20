from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import prod, sqrt
from typing import Iterable, Optional

from django.utils import timezone

from paper.models import LeaderboardEntry, LeaderboardSeason, PaperPortfolio, PaperTrade


@dataclass
class PortfolioMetrics:
    return_pct: Optional[Decimal]
    sharpe: Optional[Decimal]
    sortino: Optional[Decimal]
    volatility: Optional[Decimal]
    consistency: Optional[Decimal]
    max_drawdown_pct: Optional[Decimal]
    win_rate: Optional[Decimal]
    profit_factor: Optional[Decimal]
    time_weighted_return: Optional[Decimal]
    sample_count: int
    trade_count: int

    def as_extra(self) -> dict:
        def _safe(v):
            if v is None:
                return None
            try:
                return float(v)
            except (InvalidOperation, TypeError):
                return None

        return {
            "return_pct": _safe(self.return_pct),
            "sharpe": _safe(self.sharpe),
            "sortino": _safe(self.sortino),
            "volatility": _safe(self.volatility),
            "consistency": _safe(self.consistency),
            "max_drawdown_pct": _safe(self.max_drawdown_pct),
            "win_rate": _safe(self.win_rate),
            "profit_factor": _safe(self.profit_factor),
            "time_weighted_return": _safe(self.time_weighted_return),
            "samples": self.sample_count,
            "trade_count": self.trade_count,
        }


def _quantize(value: Decimal, places: str = "0.000001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _to_decimal_or_none(value: Optional[float]) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def calculate_metrics(
    portfolio: PaperPortfolio,
    start_dt: datetime,
    end_dt: datetime,
    baseline_override: Optional[Decimal] = None,
) -> Optional[PortfolioMetrics]:
    snaps = list(
        portfolio.snapshots.filter(timestamp__gte=start_dt, timestamp__lte=end_dt).order_by(
            "timestamp"
        )
    )
    if not snaps:
        return None
    equities = [Decimal(s.equity) for s in snaps if s.equity is not None]
    if not equities:
        return None
    if len(equities) < 1:
        return None
    baseline = baseline_override or equities[0]
    if baseline <= 0:
        baseline = Decimal("1")
    end_equity = equities[-1]
    return_raw = ((end_equity - baseline) / baseline) * Decimal("100")
    return_pct = _quantize(return_raw)

    daily_returns = []
    for prev, curr in zip(equities, equities[1:]):
        if prev > 0:
            daily_returns.append(float((curr - prev) / prev))
    sharpe = sortino = volatility = time_weighted = None
    if len(daily_returns) > 1:
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        stdev = sqrt(variance) if variance > 0 else 0
        if stdev > 0:
            volatility = _quantize(Decimal(str(stdev * sqrt(252))))
            sharpe = _quantize(Decimal(str(mean / stdev * sqrt(252))))
        downside = [r for r in daily_returns if r < 0]
        if downside:
            downside_mean = sum(downside) / len(downside)
            downside_var = (
                sum((r - downside_mean) ** 2 for r in downside) / len(downside)
                if len(downside) > 0
                else 0
            )
            downside_stdev = sqrt(downside_var) if downside_var > 0 else abs(downside_mean)
            if downside_stdev > 0:
                sortino = _quantize(Decimal(str(mean / downside_stdev * sqrt(252))))
        try:
            time_weighted = _quantize(Decimal(str(prod((1 + r) for r in daily_returns) - 1)))
        except Exception:
            time_weighted = None
    # Max drawdown (fraction)
    peak = equities[0]
    max_dd = Decimal("0")
    for eq in equities:
        if eq > peak:
            peak = eq
        drawdown = (eq - peak) / peak if peak > 0 else Decimal("0")
        if drawdown < max_dd:
            max_dd = drawdown
    max_drawdown_pct = _quantize(max_dd * Decimal("100"))
    consistency = None
    if max_drawdown_pct and max_drawdown_pct < 0:
        consistency = _quantize(return_pct / abs(max_drawdown_pct))
    elif return_pct is not None:
        consistency = return_pct

    # Trade-based metrics for the same window
    trades = PaperTrade.objects.filter(
        portfolio=portfolio, created_at__gte=start_dt, created_at__lte=end_dt
    )
    trade_count = trades.count()
    win_rate = profit_factor = None
    if trade_count > 0:
        pnl_values = [Decimal(t.realized_pnl) for t in trades]
        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]
        win_rate = _quantize(Decimal(len(wins)) / Decimal(trade_count)) if trade_count else None
        total_wins = sum(wins) if wins else Decimal("0")
        total_losses = abs(sum(losses)) if losses else Decimal("0")
        if total_losses > 0:
            profit_factor = _quantize(total_wins / total_losses)
        elif total_wins > 0:
            profit_factor = _quantize(Decimal(total_wins))

    return PortfolioMetrics(
        return_pct=return_pct,
        sharpe=sharpe,
        sortino=sortino,
        volatility=volatility,
        consistency=consistency,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate,
        profit_factor=profit_factor,
        time_weighted_return=time_weighted,
        sample_count=len(equities),
        trade_count=trade_count,
    )


def _update_entries_for_metric(
    results: list[tuple[PaperPortfolio, PortfolioMetrics]],
    metric: str,
    period: str,
    season: LeaderboardSeason | None,
    calculated_at: datetime,
):
    # Sort descending by metric value (None treated as lowest)
    sorted_results = sorted(
        results,
        key=lambda item: (item[1].__getattribute__(metric) is not None, item[1].__getattribute__(metric)),
        reverse=True,
    )
    seen_ids = []
    for idx, (portfolio, metrics) in enumerate(sorted_results, start=1):
        value = getattr(metrics, metric)
        if value is None:
            continue
        seen_ids.append(portfolio.id)
        LeaderboardEntry.objects.update_or_create(
            season=season,
            portfolio=portfolio,
            metric=metric,
            period=period,
            defaults={
                "value": _quantize(Decimal(value)),
                "rank": idx,
                "calculated_at": calculated_at,
                "extra": metrics.as_extra(),
            },
        )
    qs = LeaderboardEntry.objects.filter(metric=metric, period=period, season=season)
    if seen_ids:
        qs.exclude(portfolio_id__in=seen_ids).delete()
    else:
        qs.delete()


def recompute_all_leaderboards(now: Optional[datetime] = None):
    """
    Recompute leaderboards for:
    - Global 7d and 30d windows (normalized by join date)
    - Seasons (active; window bounded by season dates and portfolio join)
    - Since join (return pct)
    """
    now = now or timezone.now()
    end_dt = now
    portfolios = list(PaperPortfolio.objects.all())
    periods = {
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
    }
    metrics = [
        "return_pct",
        "time_weighted_return",
        "sharpe",
        "sortino",
        "volatility",
        "consistency",
        "max_drawdown_pct",
        "win_rate",
        "profit_factor",
    ]

    # Global rolling periods
    for period_id, start_dt in periods.items():
        results: list[tuple[PaperPortfolio, PortfolioMetrics]] = []
        for p in portfolios:
            start = max(start_dt, p.created_at)
            stats = calculate_metrics(p, start, end_dt)
            if stats:
                results.append((p, stats))
        for metric in metrics:
            _update_entries_for_metric(results, metric, period_id, None, now)

    # Since-join
    sj_results: list[tuple[PaperPortfolio, PortfolioMetrics]] = []
    for p in portfolios:
        stats = calculate_metrics(p, p.created_at, end_dt)
        if stats:
            sj_results.append((p, stats))
    for metric in metrics:
        _update_entries_for_metric(sj_results, metric, "since_join", None, now)

    # Seasonal leaderboards
    seasons = LeaderboardSeason.objects.filter(is_active=True)
    for season in seasons:
        start_dt = timezone.make_aware(
            datetime.combine(season.start_date, datetime.min.time()), timezone.get_current_timezone()
        )
        end_date = season.end_date
        end_bound = datetime.combine(end_date, datetime.max.time())
        end_bound = timezone.make_aware(end_bound, timezone.get_current_timezone())
        season_end = min(end_bound, end_dt)
        season_results: list[tuple[PaperPortfolio, PortfolioMetrics]] = []
        for p in portfolios:
            if p.created_at > season_end:
                continue
            season_start = max(start_dt, p.created_at)
            stats = calculate_metrics(
                p, season_start, season_end, baseline_override=Decimal(season.starting_balance)
            )
            if stats:
                season_results.append((p, stats))
        for metric in metrics:
            _update_entries_for_metric(season_results, metric, "season", season, now)
