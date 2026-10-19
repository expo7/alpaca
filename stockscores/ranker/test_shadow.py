from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import ResearchRun, ShadowEvent, ShadowSetup
from .shadow import ShadowProposalSerializer, propose
from .shadow_broker import ShadowIdentityError, verify_account_identity
from .shadow_views import _performance


class ShadowTests(APITestCase):
    def test_report_uses_realized_returns_and_chronological_drawdown(self):
        result = _performance([(1, "10"), (2, "-20"), (3, "5")])
        self.assertEqual(result["sample_size"], 3)
        self.assertEqual(Decimal(result["max_drawdown_pct"]), Decimal("20"))
        self.assertTrue(result["small_sample"])

    @override_settings(QUANTELLE_RESEARCH_OPERATOR_TOKEN="test-research-operator-token-more-than-32-characters")
    def test_prospective_proposal_is_private_immutable_and_idempotent(self):
        now = timezone.now()
        run = ResearchRun.objects.create(expected_run_at=now - timedelta(minutes=5), started_at=now - timedelta(minutes=4),
                                         completed_at=now, session_type="regular")
        expiry = (now + timedelta(days=30)).date()
        data = {
            "request_id": "github-issue-123-shadow-1", "research_run_id": run.id,
            "category": "index", "benchmark_rationale": "Regime trend comparison", "decided_at": now.isoformat(),
            "symbol": "SPY", "direction": "bullish", "expiration": expiry.isoformat(),
            "option_symbol": f"SPY{expiry:%y%m%d}C00500000", "strike": "500", "option_type": "call",
            "contract_multiplier": 100, "quantity": 1, "underlying_price": "500", "bid": "4.90", "ask": "5.10",
            "midpoint": "5.00", "quote_at": now.isoformat(), "spread_dollars": "0.20", "spread_pct": "4.00",
            "volume": 120, "open_interest": 900, "entry_trigger": "Underlying clears VWAP", "required_confirmation": "Five-minute hold above VWAP",
            "trigger_direction": "above", "underlying_trigger_price": "500", "confirmation_seconds": 300,
            "entry_low": "5.00", "entry_high": "5.10", "do_not_chase": "5.30", "entry_deadline": (now + timedelta(hours=1)).isoformat(),
            "stop": "4.00", "target_1": "7.30", "underlying_invalidation": "495", "expected_reward_risk": "2.00",
            "market_regime": "Broad risk on", "thesis": "Index breadth and trend align for a swing setup.",
            "evidence": ["VWAP reclaim at decision"], "data_provenance": "Alpaca indicative quote at decision",
            "ruleset_version": "shadow-v1", "broker_execution_intended": False,
        }
        url = "/api/operator/shadow-research/"
        self.assertIn(self.client.post(url, data, format="json").status_code, (401, 403))
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-research-operator-token-more-than-32-characters")
        first = self.client.post(url, data, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.client.post(url, data, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {**data, "request_id": "github-issue-124-shadow-1"}, format="json").status_code, 409)
        self.assertEqual(ShadowSetup.objects.count(), 1)
        setup = ShadowSetup.objects.get()
        self.assertEqual(setup.execution_mode, "observation")
        setup.decision = {"corrupt": True}
        with self.assertRaises(ValueError):
            setup.save()
        event = ShadowEvent.objects.get()
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            event.delete()
        with transaction.atomic(), self.assertRaises(DatabaseError):
            ShadowSetup.objects.filter(pk=setup.pk).update(decision={"corrupt": True})
        with transaction.atomic(), self.assertRaises(DatabaseError):
            ShadowEvent.objects.filter(pk=event.pk).update(kind="rewritten")
        correction = {"correction_id": "correction-0001", "reason": "An evidence label was mistaken",
                      "corrected_statement": "The data source was indicative at decision time",
                      "evidence_source": "Contemporaneous quote provenance log"}
        corrections = f"/api/operator/shadow-research/{setup.pk}/corrections/"
        self.assertEqual(self.client.post(corrections, correction, format="json").status_code, 201)
        self.assertTrue(self.client.post(corrections, correction, format="json").data["already_applied"])
        setup.refresh_from_db()
        self.assertEqual(setup.decision["symbol"], "SPY")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.credentials()
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.assertNotIn("shadow", str(self.client.get("/api/trade-signals/").data).lower())

    def test_near_miss_requires_structured_reason_and_no_future_decision(self):
        now = timezone.now()
        run = ResearchRun.objects.create(expected_run_at=now, started_at=now - timedelta(minutes=1),
                                         completed_at=now, session_type="regular")
        expiry = (now + timedelta(days=30)).date()
        payload = {"request_id": "github-issue-200-shadow-1", "research_run_id": run.pk,
                   "category": "near_miss", "decided_at": now.isoformat(), "symbol": "SPY",
                   "direction": "bullish", "option_symbol": f"SPY{expiry:%y%m%d}C00500000",
                   "expiration": expiry.isoformat(), "strike": "500", "option_type": "call",
                   "contract_multiplier": 100, "quantity": 1, "underlying_price": "500", "bid": "4.90",
                   "ask": "5.10", "midpoint": "5", "quote_at": now.isoformat(), "spread_dollars": "0.20",
                   "spread_pct": "4", "volume": 50, "open_interest": 100,
                   "entry_trigger": "Crosses the defined level", "required_confirmation": "Holds above the level for 60 seconds",
                   "trigger_direction": "above", "underlying_trigger_price": "500", "confirmation_seconds": 60,
                   "entry_low": "5", "entry_high": "5.10", "do_not_chase": "5.30",
                   "entry_deadline": (now + timedelta(hours=1)).isoformat(), "stop": "4", "target_1": "7.30",
                   "underlying_invalidation": "495", "expected_reward_risk": "2",
                   "market_regime": "mixed market", "thesis": "A plausible setup with a single missing catalyst.",
                   "evidence": ["Consolidation"], "data_provenance": "Contemporaneous indicative quote",
                   "ruleset_version": "shadow-v1", "broker_execution_intended": False}
        serializer = ShadowProposalSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("rejection_reason", serializer.errors)
        payload["rejection_reason"] = "no_fresh_catalyst"
        self.assertTrue(ShadowProposalSerializer(data=payload).is_valid())
        payload["decided_at"] = (now + timedelta(minutes=1)).isoformat()
        self.assertFalse(ShadowProposalSerializer(data=payload).is_valid())

    @override_settings(QUANTELLE_RESEARCH_OPERATOR_TOKEN="test-research-operator-token-more-than-32-characters")
    def test_observation_requires_ask_and_exits_at_gapped_bid(self):
        now = timezone.now() - timedelta(seconds=8)
        run = ResearchRun.objects.create(expected_run_at=now, started_at=now - timedelta(minutes=1), completed_at=now,
                                         session_type="regular")
        expiry = (now + timedelta(days=30)).date()
        decision = {"symbol": "QQQ", "direction": "bullish", "option_symbol": f"QQQ{expiry:%y%m%d}C00500000",
                    "expiration": expiry.isoformat(), "contract_multiplier": 100, "entry_low": "5.00", "entry_high": "5.15",
                    "do_not_chase": "5.30", "entry_deadline": (now + timedelta(hours=1)).isoformat(),
                    "volume": 10, "open_interest": 100,
                    "underlying_invalidation": "490", "stop": "4.00", "target_1": "7.30", "market_regime": "risk on"}
        setup = ShadowSetup.objects.create(research_run=run, request_id="shadow-test-1", decision=decision,
                                           contract_symbol=decision["option_symbol"],
                                           category="index", ruleset_version="v1", decided_at=now)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-research-operator-token-more-than-32-characters")
        url = f"/api/operator/shadow-research/{setup.pk}/observe/"

        def sample(identifier, at, bid, ask, confirmation=True):
            return {"observation_id": identifier, "observed_at": at.isoformat(), "quote_at": at.isoformat(),
                    "underlying_price": "500", "bid": bid, "ask": ask,
                    "confirmation_met": confirmation, "thesis_valid": True, "source": "sampled current option quote"}

        a = sample("sample-0001", now + timedelta(seconds=1), "4.90", "5.20")
        self.assertEqual(self.client.post(url, a, format="json").data["status"], "waiting")
        b = sample("sample-0002", now + timedelta(seconds=2), "4.90", "5.10")
        self.assertEqual(self.client.post(url, b, format="json").data["status"], "active")
        self.assertEqual(self.client.post(url, b, format="json").data["already_applied"], True)
        setup.refresh_from_db()
        self.assertEqual(setup.result["modeled_entry"], "5.11")
        self.assertNotIn("realized_return_pct", setup.result)
        c = sample("sample-0003", now + timedelta(seconds=3), "3.50", "3.70")
        self.assertEqual(self.client.post(url, c, format="json").data["status"], "completed")
        setup.refresh_from_db()
        self.assertEqual(setup.result["modeled_exit"], "3.49")
        self.assertEqual(Decimal(setup.result["realized_return_dollars"]), Decimal("-162.00"))
        self.assertEqual(setup.events.filter(kind="stopped").count(), 1)

    def test_identity_fail_closed(self):
        base = {"SHADOW_TRADING_ENABLED": "true", "SHADOW_EXECUTION_CONFIRMED": "true", "SHADOW_EMERGENCY_PAUSE": "false",
                "SHADOW_ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets", "ALPACA_PAPER_BASE_URL": "https://paper-api.alpaca.markets",
                "SHADOW_ALPACA_PAPER_API_KEY": "shadow", "SHADOW_ALPACA_PAPER_SECRET_KEY": "shadow-secret",
                "ALPACA_PAPER_API_KEY": "primary", "ALPACA_PAPER_SECRET_KEY": "primary-secret"}
        with patch.dict("os.environ", base):
            response = Mock(status_code=200)
            response.json.return_value = {"id": "same"}
            with self.assertRaises(ShadowIdentityError):
                verify_account_identity(get=Mock(return_value=response))
            with patch.dict("os.environ", {"SHADOW_ALPACA_PAPER_BASE_URL": "https://api.alpaca.markets"}):
                with self.assertRaises(ShadowIdentityError):
                    verify_account_identity(get=Mock())
            with patch.dict("os.environ", {"SHADOW_ALPACA_PAPER_API_KEY": ""}):
                with self.assertRaises(ShadowIdentityError):
                    verify_account_identity(get=Mock())
            different = Mock(side_effect=[Mock(status_code=200, json=Mock(return_value={"id": "shadow-id"})),
                                          Mock(status_code=200, json=Mock(return_value={"id": "primary-id"}))])
            self.assertEqual(verify_account_identity(get=different), "shadow-id")
        with patch.dict("os.environ", {**base, "SHADOW_TRADING_ENABLED": "false"}):
            with self.assertRaises(ShadowIdentityError):
                verify_account_identity(get=Mock())
            distinct = Mock(side_effect=[Mock(status_code=200, json=Mock(return_value={"id": "shadow-id"})),
                                         Mock(status_code=200, json=Mock(return_value={"id": "primary-id"}))])
            self.assertEqual(verify_account_identity(get=distinct, require_enabled=False), "shadow-id")
