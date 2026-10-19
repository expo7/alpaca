from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import ResearchRun, ShadowSetup, ShadowEvent


class StaffShadowDashboardTests(APITestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.staff = User.objects.create_user(username="staff", is_staff=True)
        self.reader = User.objects.create_user(username="reader")
        self.url = "/api/staff/shadow-research/"
        self.account = self.url + "account/"

    def test_reports_require_staff_and_never_offer_write_actions(self):
        with patch("ranker.shadow_broker.verify_account_identity") as identity:
            for url in (self.url, self.account):
                self.assertIn(self.client.get(url).status_code, (401, 403))
                self.client.force_authenticate(self.reader)
                self.assertEqual(self.client.get(url).status_code, 403)
            identity.assert_not_called()
        self.client.force_authenticate(self.staff)
        for url in (self.url, self.account):
            self.assertEqual(self.client.post(url, {}).status_code, 405)

    def test_records_preserve_decisions_events_filters_and_unknown_results(self):
        now = timezone.now()
        run = ResearchRun.objects.create(expected_run_at=now, started_at=now, completed_at=now, session_type="regular")
        s = ShadowSetup.objects.create(research_run=run, request_id="dashboard-fixture", category="index",
                                      ruleset_version="v1", decided_at=now, contract_symbol="SPY-fixture",
                                      decision={"symbol": "SPY", "thesis": "Original decision"})
        ShadowEvent.objects.create(setup=s, kind="observation", occurred_at=now, details={"bid": "5.00"})
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response.data["summary"]["last_observation_at"], now)
        self.assertEqual(response.data["results"][0]["decision"]["thesis"], "Original decision")
        self.assertNotIn("realized_return_pct", response.data["results"][0]["result"])
        self.assertEqual(response.data["results"][0]["event_count"], 1)
        self.assertEqual(self.client.get(self.url + "?mode=broker_intended").data["count"], 0)
        self.assertEqual(self.client.get(self.url + "?page=-1").status_code, 400)
        self.assertEqual(self.client.get(self.url + "?mode=invalid").status_code, 400)
        self.assertEqual(ShadowSetup.objects.get().decision, s.decision)

    def test_account_is_read_only_redacted_cached_and_unknown_on_failure(self):
        self.client.force_authenticate(self.staff)
        client = Mock()
        client.base_url = "https://paper-api.alpaca.markets"
        client._request.side_effect = [[], []]
        with patch("ranker.shadow_broker.verify_account_identity", return_value="private-account-0944"), patch(
                "ranker.shadow_broker.ShadowMarketDataClient", return_value=client):
            r = self.client.get(self.account)
            self.assertTrue(r.data["flat"])
            self.assertEqual(r.data["account_suffix"], "0944")
            self.assertNotIn("private-account", str(r.data))
            self.client.get(self.account)
            self.assertEqual(client._request.call_count, 2)
            self.assertTrue(all(c.args[0] == "GET" for c in client._request.call_args_list))
        cache.clear()
        with patch("ranker.shadow_broker.verify_account_identity", side_effect=RuntimeError("SECRET")):
            r = self.client.get(self.account)
            self.assertEqual(r.data["status"], "unavailable")
            self.assertNotIn("flat", r.data)
            self.assertNotIn("SECRET", str(r.data))
