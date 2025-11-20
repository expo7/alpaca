from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from paper.models import LeaderboardEntry, LeaderboardSeason, PaperPortfolio, PerformanceSnapshot
from paper.services.leaderboards import calculate_metrics, recompute_all_leaderboards


User = get_user_model()


class LeaderboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="leader-user")
        self.now = timezone.now()
        self.p1 = PaperPortfolio.objects.create(
            user=self.user,
            name="Alpha",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("100000"),
            equity=Decimal("100000"),
            status="active",
        )
        self.p2 = PaperPortfolio.objects.create(
            user=self.user,
            name="Beta",
            base_currency="USD",
            starting_balance=Decimal("100000"),
            cash_balance=Decimal("100000"),
            equity=Decimal("100000"),
            status="active",
        )
        # Backdate creation to ensure snapshot windows include join date
        PaperPortfolio.objects.filter(id=self.p1.id).update(
            created_at=self.now - timedelta(days=10)
        )
        PaperPortfolio.objects.filter(id=self.p2.id).update(
            created_at=self.now - timedelta(days=10)
        )
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        # Equity curves: p1 grows faster
        # Place snapshots within last 3-4 days so rolling windows always include them
        for i, eq in enumerate([100000, 102000, 105000, 110000]):
            ts = self.now - timedelta(days=3 - i)
            PerformanceSnapshot.objects.create(
                portfolio=self.p1,
                timestamp=ts,
                equity=Decimal(eq),
                cash=Decimal(eq),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
            )
        for i, eq in enumerate([100000, 101000, 103000, 105000]):
            ts = self.now - timedelta(days=3 - i)
            PerformanceSnapshot.objects.create(
                portfolio=self.p2,
                timestamp=ts,
                equity=Decimal(eq),
                cash=Decimal(eq),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
            )

    def test_calculate_metrics_basic(self):
        start = self.now - timedelta(days=7)
        metrics = calculate_metrics(self.p1, start, self.now)
        self.assertIsNotNone(metrics)
        self.assertGreater(metrics.return_pct, Decimal("9"))
        self.assertLess(metrics.max_drawdown_pct, Decimal("0.000001"))  # no drawdown, should be near 0

    def test_recompute_leaderboards_ranks_by_return(self):
        # Active season spanning snapshots
        season = LeaderboardSeason.objects.create(
            name="Q1",
            start_date=timezone.now().date() - timedelta(days=15),
            end_date=timezone.now().date() + timedelta(days=15),
            starting_balance=Decimal("100000"),
            is_active=True,
        )
        recompute_all_leaderboards(now=self.now)
        entries = LeaderboardEntry.objects.filter(period="7d", metric="return_pct", season__isnull=True)
        self.assertEqual(entries.count(), 2)
        top = entries.order_by("rank").first()
        self.assertEqual(top.portfolio, self.p1)
        # Season entries exist
        season_entries = LeaderboardEntry.objects.filter(period="season", season=season, metric="return_pct")
        self.assertEqual(season_entries.count(), 2)
        top_season = season_entries.order_by("rank").first()
        self.assertEqual(top_season.portfolio, self.p1)
