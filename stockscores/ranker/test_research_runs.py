from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import OperationalTelegramAlert, ResearchRun
from .research_runs import GRACE, monitor_research_runs, next_slot, research_health, run_state, scheduled_slots


@override_settings(QUANTELLE_RESEARCH_OPERATOR_TOKEN="test-research-operator-token-more-than-32-characters")
class ResearchRunTests(APITestCase):
    def setUp(self):
        now = timezone.now()
        self.slot = list(scheduled_slots(now - timedelta(days=4), now - timedelta(hours=2)))[-1]
        self.url = reverse("research-run-report")
        self.data = {
            "action": "report_run", "request_id": "github-issue-123", "expected_run_at": self.slot.isoformat(),
            "started_at": (self.slot + timedelta(minutes=1)).isoformat(),
            "completed_at": (self.slot + timedelta(minutes=12)).isoformat(),
            "session_type": "regular", "outcome": "watchlist_no_trade", "market_regime": "mixed/narrow",
            "candidates_reviewed": 18, "operator_action": "none", "verified_result": "",
            "error_summary": "",
        }

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-research-operator-token-more-than-32-characters")

    def test_only_restricted_operator_can_report_or_read(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.assertIn(self.client.post(self.url, self.data, format="json").status_code, (401, 403))
        self.authenticate()
        response = self.client.post(self.url, self.data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "fresh")
        self.assertEqual(self.client.get(self.url).data["results"][0]["candidates_reviewed"], 18)
        self.assertEqual(ResearchRun.objects.count(), 1)

    def test_idempotent_report_rejects_conflicting_replay(self):
        self.authenticate()
        self.assertEqual(self.client.post(self.url, self.data, format="json").status_code, 201)
        self.assertTrue(self.client.post(self.url, self.data, format="json").data["already_applied"])
        changed = {**self.data, "candidates_reviewed": 19}
        self.assertEqual(self.client.post(self.url, changed, format="json").status_code, 409)
        self.assertEqual(ResearchRun.objects.get().candidates_reviewed, 18)

    def test_regime_contract_accepts_boundary_and_preserves_narrative(self):
        self.authenticate()
        analysis = "QQQ led premarket while opening confirmation and intraday VWAP were unavailable."
        payload = {**self.data, "market_regime": "R" * 80, "verified_result": analysis}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        run = ResearchRun.objects.get(expected_run_at=self.slot)
        self.assertEqual(run.market_regime, "R" * 80)
        self.assertEqual(run.verified_result, analysis)

    def test_regime_over_limit_is_rejected_without_record(self):
        self.authenticate()
        response = self.client.post(self.url, {**self.data, "market_regime": "R" * 81}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("market_regime", response.data)
        self.assertFalse(ResearchRun.objects.exists())

    def test_completion_order_timezone_and_future_boundary(self):
        self.authenticate()
        fixed = self.slot + timedelta(minutes=20)
        phoenix = ZoneInfo("America/Phoenix")
        payload = {**self.data, "started_at": fixed.astimezone(phoenix).isoformat(),
                   "completed_at": fixed.astimezone(phoenix).isoformat()}
        with patch("django.utils.timezone.now", return_value=fixed):
            self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 201)
        self.assertEqual(ResearchRun.objects.get().completed_at, fixed)
        ResearchRun.objects.all().delete()
        with patch("django.utils.timezone.now", return_value=fixed):
            for bad in (
                {**payload, "completed_at": (fixed - timedelta(microseconds=1)).isoformat()},
                {**payload, "completed_at": (fixed + timedelta(microseconds=1)).isoformat()},
                {**payload, "completed_at": fixed.replace(tzinfo=None).isoformat()},
            ):
                self.assertEqual(self.client.post(self.url, bad, format="json").status_code, 400)
        self.assertFalse(ResearchRun.objects.exists())

    def test_rejects_unscheduled_slot_and_unverified_action(self):
        self.authenticate()
        invalid = {**self.data, "expected_run_at": (self.slot + timedelta(minutes=1)).isoformat()}
        self.assertEqual(self.client.post(self.url, invalid, format="json").status_code, 400)
        invalid = {**self.data, "operator_action": "publish"}
        self.assertEqual(self.client.post(self.url, invalid, format="json").status_code, 400)

    def test_monitor_detects_missing_next_slot_and_alerts_staff_once(self):
        ResearchRun.objects.create(expected_run_at=self.slot, request_id="github-issue-123",
                                   started_at=self.slot, completed_at=self.slot + timedelta(minutes=1),
                                   outcome="watchlist_no_trade", next_expected_run_at=next_slot(self.slot))
        next_expected = next_slot(self.slot)
        at = next_expected + GRACE + timedelta(minutes=1)
        first = monitor_research_runs(now=at)
        second = monitor_research_runs(now=at)
        self.assertEqual(first["overdue"], 1)
        self.assertEqual(second["overdue"], 1)
        self.assertEqual(run_state(ResearchRun.objects.get(expected_run_at=next_expected), at), "overdue")
        self.assertEqual(OperationalTelegramAlert.objects.count(), 1)
        self.assertIsNone(OperationalTelegramAlert.objects.get().signal_id)
        self.assertEqual(research_health(at)["status"], "overdue")

    def test_monitor_waits_for_first_authenticated_report(self):
        self.assertEqual(monitor_research_runs()["status"], "awaiting_first_report")
        self.assertFalse(OperationalTelegramAlert.objects.exists())
