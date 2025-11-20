from decimal import Decimal
from datetime import datetime, timedelta

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from paper.models import PaperPortfolio, PaperOrder
from paper.services.execution import ExecutionEngine
from paper.services.market_data import Quote


User = get_user_model()


class DummyProvider:
    def __init__(self, price_map):
        self.price_map = price_map

    def get_quote(self, symbol: str) -> Quote:
        return self.price_map[symbol]

    def get_history_period(self, symbol: str, period="3mo", interval="1d"):
        dates = pd.date_range(end=datetime.utcnow(), periods=50, freq="D")
        volume = getattr(self.price_map[symbol], "volume", None) or 1_000_000
        data = {
            "Open": [self.price_map[symbol].price] * len(dates),
            "High": [self.price_map[symbol].price] * len(dates),
            "Low": [self.price_map[symbol].price] * len(dates),
            "Close": [self.price_map[symbol].price] * len(dates),
            "Volume": [volume] * len(dates),
        }
        return pd.DataFrame(data, index=dates)


class ExecutionEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="exec-user")
        self.portfolio = PaperPortfolio.objects.create(
            user=self.user,
            name="Exec",
            base_currency="USD",
            status="active",
        )

    def test_iceberg_partial_fills(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="limit",
            tif="day",
            quantity=Decimal("100"),
            reserve_quantity=Decimal("20"),
            limit_price=Decimal("150"),
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {
                "AAPL": Quote("AAPL", price=140, timestamp=datetime.utcnow()),
            }
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        order.refresh_from_db()
        self.assertEqual(order.status, "part_filled")
        self.assertEqual(order.filled_quantity, Decimal("20"))
        prev_qty = order.filled_quantity
        iteration = 0
        while order.status != "filled" and iteration < 10:
            engine.run()
            order.refresh_from_db()
            iteration += 1
            self.assertGreater(order.filled_quantity, prev_qty)
            prev_qty = order.filled_quantity
        self.assertEqual(order.filled_quantity, Decimal("100"))
        self.assertEqual(order.status, "filled")

    def test_cross_symbol_condition(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="TSLA",
            side="buy",
            order_type="market",
            tif="day",
            quantity=Decimal("10"),
            condition_type="cross_symbol",
            condition_payload={"symbol": "QQQ", "operator": "gt"},
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {
                "TSLA": Quote("TSLA", price=200, timestamp=datetime.utcnow()),
                "QQQ": Quote("QQQ", price=350, timestamp=datetime.utcnow()),
            }
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        order.refresh_from_db()
        self.assertEqual(order.status, "filled")

    def test_bracket_exits_cancel(self):
        parent = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="market",
            tif="day",
            quantity=Decimal("10"),
            extended_hours=True,
            status="new",
        )
        tp = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="sell",
            order_type="limit",
            limit_price=Decimal("150"),
            tif="day",
            extended_hours=True,
            quantity=Decimal("10"),
            parent=parent,
            chain_id="chain1",
            child_role="tp",
            status="new",
        )
        sl = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="sell",
            order_type="stop",
            stop_price=Decimal("130"),
            tif="day",
            extended_hours=True,
            quantity=Decimal("10"),
            parent=parent,
            chain_id="chain1",
            child_role="sl",
            status="new",
        )
        provider1 = DummyProvider(
            {"AAPL": Quote("AAPL", price=140, timestamp=datetime.utcnow())}
        )
        engine = ExecutionEngine(data_provider=provider1)
        engine.run()
        provider2 = DummyProvider(
            {"AAPL": Quote("AAPL", price=155, timestamp=datetime.utcnow())}
        )
        engine2 = ExecutionEngine(data_provider=provider2)
        engine2.run()
        tp.refresh_from_db()
        sl.refresh_from_db()
        self.assertEqual(tp.status, "filled")
        parent.refresh_from_db()
        self.assertEqual(sl.status, "canceled", parent.notes)

    def test_oco_cancel(self):
        parent = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="oco",
            tif="day",
            quantity=Decimal("10"),
            extended_hours=True,
            status="filled",
        )
        l1 = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="sell",
            order_type="limit",
            limit_price=Decimal("160"),
            extended_hours=True,
            quantity=Decimal("10"),
            parent=parent,
            status="working",
        )
        l2 = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="sell",
            order_type="limit",
            limit_price=Decimal("170"),
            extended_hours=True,
            quantity=Decimal("10"),
            parent=parent,
            status="working",
        )
        provider = DummyProvider(
            {
                "AAPL": Quote("AAPL", price=165, timestamp=datetime.utcnow()),
            }
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        parent.refresh_from_db()
        l1.refresh_from_db()
        l2.refresh_from_db()
        self.assertEqual(l1.status, "filled")
        self.assertEqual(l2.status, "canceled", parent.notes)
        self.assertEqual(parent.notes["events"][-1]["event"], "chain_action")

    def test_oto_activates_child(self):
        parent = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="market",
            tif="day",
            quantity=Decimal("10"),
            extended_hours=True,
            status="new",
        )
        child = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="sell",
            order_type="trailing_amount",
            trail_amount=Decimal("5"),
            tif="day",
            parent=parent,
            child_role="sl",
            status="new",
        )
        provider = DummyProvider(
            {"AAPL": Quote("AAPL", price=150, timestamp=datetime.utcnow())}
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        child.refresh_from_db()
        self.assertEqual(child.status, "working")

    def test_parent_fill_activates_children_and_sets_chain(self):
        parent = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="buy",
            order_type="market",
            tif="day",
            quantity=Decimal("5"),
            extended_hours=True,
            status="new",
            chain_id="",
        )
        tp = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="sell",
            order_type="limit",
            limit_price=Decimal("350"),
            quantity=Decimal("5"),
            tif="day",
            status="new",
            parent=parent,
            child_role="tp",
            extended_hours=True,
        )
        sl = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="sell",
            order_type="stop",
            stop_price=Decimal("280"),
            quantity=Decimal("5"),
            tif="day",
            status="new",
            parent=parent,
            child_role="sl",
            extended_hours=True,
        )
        provider = DummyProvider(
            {"MSFT": Quote("MSFT", price=310, timestamp=datetime.utcnow())}
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        parent.refresh_from_db()
        tp.refresh_from_db()
        sl.refresh_from_db()
        self.assertEqual(parent.status, "filled")
        self.assertNotEqual(parent.chain_id, "")
        self.assertEqual(tp.status, "working")
        self.assertEqual(sl.status, "working")
        self.assertEqual(tp.chain_id, parent.chain_id)
        self.assertEqual(sl.chain_id, parent.chain_id)
        self.assertIn("activate_children", [evt.get("event") for evt in parent.notes.get("events", [])])

    def test_otoco_child_fill_cancels_sibling(self):
        parent = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="NVDA",
            side="buy",
            order_type="otoco",
            tif="day",
            quantity=Decimal("3"),
            extended_hours=True,
            status="filled",
            chain_id="chain-x",
        )
        tp = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="NVDA",
            side="sell",
            order_type="limit",
            limit_price=Decimal("600"),
            quantity=Decimal("3"),
            tif="day",
            status="working",
            parent=parent,
            child_role="tp",
            chain_id="chain-x",
            extended_hours=True,
        )
        sl = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="NVDA",
            side="sell",
            order_type="stop",
            stop_price=Decimal("450"),
            quantity=Decimal("3"),
            tif="day",
            status="working",
            parent=parent,
            child_role="sl",
            chain_id="chain-x",
            extended_hours=True,
        )
        provider = DummyProvider(
            {"NVDA": Quote("NVDA", price=605, timestamp=datetime.utcnow())}
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        tp.refresh_from_db()
        sl.refresh_from_db()
        parent.refresh_from_db()
        self.assertEqual(tp.status, "filled")
        self.assertEqual(sl.status, "canceled")
        self.assertEqual(
            parent.notes["events"][-1]["event"],
            "chain_action",
        )

    def test_algo_twap_reserve_and_schedule(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="algo_twap",
            tif="day",
            quantity=Decimal("50"),
            reserve_quantity=Decimal("7"),
            algo_params={"slices": 5, "interval_minutes": 1},
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {
                "AAPL": Quote(
                    "AAPL",
                    price=120,
                    timestamp=datetime.utcnow(),
                    volume=1_000_000,
                )
            }
        )
        engine = ExecutionEngine(data_provider=provider)
        now = timezone.now()
        engine.run(simulation_time=now)
        order.refresh_from_db()
        self.assertEqual(order.filled_quantity, Decimal("7"))
        self.assertEqual(order.algo_slice_index, 1)
        self.assertIsNotNone(order.algo_next_run_at)
        first_next = order.algo_next_run_at
        self.assertIn("algo_events", order.notes)
        engine.run(simulation_time=now + timedelta(seconds=30))
        order.refresh_from_db()
        self.assertEqual(order.filled_quantity, Decimal("7"))
        self.assertEqual(order.algo_slice_index, 1)
        engine.run(simulation_time=now + timedelta(minutes=1, seconds=5))
        order.refresh_from_db()
        self.assertEqual(order.filled_quantity, Decimal("14"))
        self.assertGreaterEqual(order.algo_slice_index, 2)
        self.assertGreater(order.algo_next_run_at, first_next)
        sim_time = now + timedelta(minutes=2)
        iterations = 0
        while order.status != "filled" and iterations < 10:
            engine.run(simulation_time=sim_time)
            order.refresh_from_db()
            sim_time += timedelta(minutes=1)
            iterations += 1
        self.assertEqual(order.status, "filled")
        self.assertEqual(order.filled_quantity, Decimal("50"))

    def test_algo_vwap_respects_participation_and_reserve(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="QQQ",
            side="buy",
            order_type="algo_vwap",
            tif="day",
            quantity=Decimal("100"),
            reserve_quantity=Decimal("30"),
            algo_params={"participation": 0.5},
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {"QQQ": Quote("QQQ", price=400, timestamp=datetime.utcnow(), volume=500_000)}
        )
        engine = ExecutionEngine(data_provider=provider)
        now = timezone.now()
        engine.run(simulation_time=now)
        order.refresh_from_db()
        self.assertEqual(order.filled_quantity, Decimal("30"))
        self.assertEqual(order.status, "part_filled")
        self.assertIsNotNone(order.algo_next_run_at)
        self.assertEqual(order.algo_slice_index, 1)
        # Next run should fill 35 (remaining 70 * 0.5 but reserve caps at 30 again)
        engine.run(simulation_time=now + timedelta(seconds=90))
        order.refresh_from_db()
        self.assertEqual(order.filled_quantity, Decimal("60"))
        self.assertEqual(order.algo_slice_index, 2)

    def test_algo_pov_uses_volume_and_reaches_completion(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="SPY",
            side="buy",
            order_type="algo_pov",
            tif="day",
            quantity=Decimal("40"),
            reserve_quantity=Decimal("25"),
            algo_params={"participation": 0.25},
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {"SPY": Quote("SPY", price=420, timestamp=datetime.utcnow(), volume=80)}
        )
        engine = ExecutionEngine(data_provider=provider)
        now = timezone.now()
        engine.run(simulation_time=now)
        order.refresh_from_db()
        # 80 volume * 0.25 => 20 shares
        self.assertEqual(order.filled_quantity, Decimal("20"))
        self.assertEqual(order.status, "part_filled")
        engine.run(simulation_time=now + timedelta(seconds=60))
        order.refresh_from_db()
        self.assertEqual(order.filled_quantity, Decimal("40"))
        self.assertEqual(order.status, "filled")

    def test_fok_cancels_when_reserve_blocks_full_fill(self):
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="AAPL",
            side="buy",
            order_type="limit",
            tif="fok",
            quantity=Decimal("50"),
            reserve_quantity=Decimal("10"),
            limit_price=Decimal("150"),
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {"AAPL": Quote("AAPL", price=140, timestamp=datetime.utcnow())}
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        order.refresh_from_db()
        self.assertEqual(order.status, "canceled")
        self.assertEqual(order.filled_quantity, Decimal("10"))

    def test_algo_order_expires_gtd(self):
        past = timezone.now() - timedelta(minutes=5)
        order = PaperOrder.objects.create(
            portfolio=self.portfolio,
            symbol="MSFT",
            side="buy",
            order_type="algo_twap",
            tif="gtd",
            tif_date=past,
            quantity=Decimal("20"),
            algo_params={"slices": 2, "interval_minutes": 1},
            extended_hours=True,
            status="new",
        )
        provider = DummyProvider(
            {"MSFT": Quote("MSFT", price=300, timestamp=datetime.utcnow(), volume=1_000)}
        )
        engine = ExecutionEngine(data_provider=provider)
        engine.run()
        order.refresh_from_db()
        self.assertEqual(order.status, "expired")
        self.assertEqual(order.filled_quantity, Decimal("0"))
