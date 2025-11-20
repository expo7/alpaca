from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import sqrt
from typing import Iterable, Optional

from django.utils import timezone

from paper.models import LeaderboardEntry, LeaderboardSeason, PaperPortfolio


@dataclass
class PortfolioMetrics:
    return_pct: Optional[Decimal]
    sharpe: Optional[Decimal]
    consistency: Optional[Decimal]
    max_drawdown_pct: Optional[Decimal]
    sample_count: int

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
            "consistency": _safe(self.consistency),
            "max_drawdown_pct": _safe(self.max_drawdown_pct),
            "samples": self.sample_count,
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
    sharpe = None
    if len(daily_returns) > 1:
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        stdev = sqrt(variance) if variance > 0 else 0
        if stdev > 0:
            sharpe = _quantize(Decimal(str(mean / stdev * sqrt(252))))
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

    return PortfolioMetrics(
        return_pct=return_pct,
        sharpe=sharpe,
        consistency=consistency,
        max_drawdown_pct=max_drawdown_pct,
        sample_count=len(equities),
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
    for idx, (portfolio, metrics) in enumerate(sorted_results, start=1):
        value = getattr(metrics, metric)
        if value is None:
            continue
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
        "7d": now - timezone.timedelta(days=7),
        "30d": now - timezone.timedelta(days=30),
    }
    metrics = ["return_pct", "sharpe", "consistency"]

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
