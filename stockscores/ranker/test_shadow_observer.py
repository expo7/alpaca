from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from .models import ResearchRun, ShadowSetup
from .shadow_observer import run_observation_cycle
from .shadow_broker import ShadowMarketDataClient


class ShadowObserverTests(TestCase):
    def test_read_only_sampling_and_quote_replay(self):
        now = timezone.now()
        decided = now - timedelta(minutes=2)
        run = ResearchRun.objects.create(expected_run_at=decided, started_at=decided,
                                         completed_at=decided, session_type="regular")
        setup = ShadowSetup.objects.create(
            research_run=run, request_id="observer-1", category="index", ruleset_version="v1",
            contract_symbol="SPY261023C00500000", decided_at=decided,
            trigger_first_seen_at=now - timedelta(seconds=61),
            decision={"symbol": "SPY", "direction": "bullish", "option_symbol": "SPY261023C00500000",
                      "underlying_trigger_price": "500", "trigger_direction": "above", "confirmation_seconds": 60,
                      "underlying_invalidation": "495", "entry_low": "5", "entry_high": "5.50",
                      "do_not_chase": "5.60", "entry_deadline": (now + timedelta(hours=1)).isoformat(),
                      "expiration": "2026-10-23", "volume": 100, "open_interest": 1000,
                      "stop": "4.00", "target_1": "8.00", "contract_multiplier": 100})
        client = Mock(spec=ShadowMarketDataClient)
        client.clock.return_value = {"is_open": True}
        client.stock_quote.return_value = {"midpoint": Decimal("501")}
        client.option_quote.return_value = {"bid": Decimal("5.00"), "ask": Decimal("5.20"),
                                            "timestamp": now.isoformat()}
        identity = Mock(return_value="shadow-id")
        result = run_observation_cycle(client_factory=lambda: client, identity=identity)
        self.assertEqual(result["setups"][str(setup.pk)], "active")
        setup.refresh_from_db()
        self.assertEqual(setup.result["result_type"], "modeled")
        self.assertEqual(setup.events.filter(kind="observation").count(), 1)
        run_observation_cycle(client_factory=lambda: client, identity=identity)
        self.assertEqual(setup.events.filter(kind="observation").count(), 1)
        identity.assert_called_with(require_enabled=False)
        self.assertFalse(hasattr(client, "submit_limit_order"))
