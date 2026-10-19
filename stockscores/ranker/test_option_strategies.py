from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, Mock

from django.test import TestCase, SimpleTestCase
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient

from .alpaca_paper import AlpacaPaperClient, PAPER_API_URL
from .models import OptionStrategy, TradeExecutorHealth, TradeSignal
from .option_strategy_rules import validate_structure, signed_fill
from .option_strategies import publish, process, submit, run_option_strategy_executor, primary_entry_order


def occ(strike, kind="C", days=30):
    day = timezone.now().date() + timedelta(days=days)
    return f"TST{day:%y%m%d}{kind}{int(strike * 1000):08d}"


def leg(strike, side="buy", kind="C", days=30):
    return {"symbol": occ(strike, kind, days), "side": side}


class RulesTests(SimpleTestCase):
    def test_debit_and_credit_vertical_risk(self):
        _, debit = validate_structure("vertical", [leg(100), leg(105, "sell")], "2.00")
        self.assertEqual(Decimal(debit["max_loss_dollars"]), 200)
        self.assertEqual(Decimal(debit["max_profit_dollars"]), 300)
        _, credit = validate_structure("vertical", [leg(100, "sell"), leg(105)], "-2.00")
        self.assertEqual(Decimal(credit["max_loss_dollars"]), 300)
        self.assertEqual(Decimal(credit["max_profit_dollars"]), 200)

    def test_put_spread_and_condor(self):
        _, p = validate_structure("vertical", [leg(105, kind="P"), leg(100, "sell", "P")], 2)
        self.assertEqual(Decimal(p["max_profit_dollars"]), 300)
        _, p = validate_structure("iron_condor", [leg(90, kind="P"), leg(95, "sell", "P"), leg(105, "sell"), leg(110)], -2)
        self.assertEqual(Decimal(p["max_loss_dollars"]), 300)

    def test_time_spreads_do_not_claim_fixed_maximum_profit(self):
        for kind, legs in [("calendar", [leg(100, days=60), leg(100, "sell")]),
            ("diagonal", [leg(95, days=60), leg(100, "sell")]),
            ("double_diagonal", [leg(90, kind="P", days=60), leg(95, "sell", "P"), leg(105, "sell"), leg(110, days=60)])]:
            with self.subTest(kind=kind):
                _, risk = validate_structure(kind, legs, 2)
                self.assertIsNone(risk["max_profit_dollars"])
                self.assertGreaterEqual(Decimal(risk["max_loss_dollars"]), 200)

    def test_long_volatility_strategies_have_bounded_debit_risk(self):
        for kind, legs in [("straddle", [leg(100), leg(100, kind="P")]), ("strangle", [leg(105), leg(95, kind="P")])]:
            _, risk = validate_structure(kind, legs, 3)
            self.assertEqual(Decimal(risk["max_loss_dollars"]), 300)
            self.assertIsNone(risk["max_profit_dollars"])

    def test_malformed_uncovered_or_mismatched_structures_rejected(self):
        cases = [("vertical", [leg(100), leg(105)], 2),
                 ("vertical", [leg(100), leg(105, "sell")], 6),
                 ("vertical", [leg(100), leg(105, "sell", days=60)], 2),
                 ("calendar", [leg(100), leg(100, "sell", days=60)], 2),
                 ("strangle", [leg(95), leg(105, kind="P")], 2),
                 ("straddle", [leg(100, "sell"), leg(100, "sell", "P")], -2),
                 ("vertical", [leg(100), leg(105, "sell")], "NaN")]
        for kind, legs, price in cases:
            with self.subTest(kind=kind, legs=legs, price=price), self.assertRaises(ValueError):
                validate_structure(kind, legs, price)

    def test_parent_average_never_substitutes_for_leg_fills(self):
        legs = [leg(100), leg(105, "sell")]
        with self.assertRaises(ValueError):
            signed_fill({"status": "filled", "filled_avg_price": "2.00", "legs": []}, legs)
        order = {"status": "filled", "legs": [{"symbol": legs[0]["symbol"], "filled_qty": "1", "filled_avg_price": "4"},
                                                {"symbol": legs[1]["symbol"], "filled_qty": "1", "filled_avg_price": "2"}]}
        self.assertEqual(signed_fill(order, legs), 2)
        order["legs"][1]["filled_qty"] = "0"
        with self.assertRaises(ValueError): signed_fill(order, legs)


class FakeClient:
    base_url = PAPER_API_URL
    data_url = "https://data.alpaca.markets"

    def __init__(self):
        self.config = SimpleNamespace(enabled=True, option_feed="indicative", max_quote_age_seconds=30, max_open_positions=2)
        self.calls, self.positions, self.orders = [], [], {}
        self.level = 3
        self.prices = {}

    def clock(self):
        return {"is_open": True}

    def _require_fresh_quote(self, value):
        return AlpacaPaperClient._require_fresh_quote(self, value)

    def _request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/v2/account"):
            return {"options_trading_level": self.level, "trading_blocked": False}
        if "/options/contracts/" in url:
            return {"symbol": url.rsplit("/", 1)[-1], "tradable": True, "size": "100"}
        if url.endswith("/options/quotes/latest"):
            rows = {}
            for symbol in kwargs["params"]["symbols"].split(","):
                bid, ask = self.prices.get(symbol, (2, 3))
                rows[symbol] = {"bp": bid, "ap": ask, "t": timezone.now().isoformat()}
            return {"quotes": rows}
        if url.endswith("/v2/positions"): return self.positions
        if url.endswith("orders:by_client_order_id"):
            result = self.orders.get(kwargs["params"]["client_order_id"])
            if result is None: raise ValueError("Alpaca returned 404")
            return result
        if method == "POST" and url.endswith("/v2/orders"):
            p = kwargs["json"]
            order = {"id": p["client_order_id"], "status": "accepted", "legs": p["legs"]}
            self.orders[order["id"]] = order
            return order
        if method == "GET" and "/v2/orders/" in url:
            return self.orders[url.rsplit("/", 1)[-1]]
        if method == "DELETE": return {}
        raise AssertionError((method, url))


class LifecycleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = FakeClient()
        TradeExecutorHealth.objects.create(singleton_id=1, status="healthy", entries_paused=False, last_completed_at=timezone.now())
        self.data = {"request_id": "test-1", "kind": "vertical", "legs": [leg(100), leg(105, "sell")],
            "entry_limit": "2.00", "stop_loss_dollars": "100", "take_profit_dollars": "150",
            "entry_deadline": (timezone.now() + timedelta(hours=2)).isoformat(),
            "close_by": (timezone.now() + timedelta(days=20)).isoformat(),
            "thesis": "A current supported bullish paper spread thesis.", "invalidation": "A clear loss of the underlying breakout invalidates this paper idea."}
        self.client.prices = {self.data["legs"][0]["symbol"]:(4, 4.1), self.data["legs"][1]["symbol"]:(2.2, 2.3)}

    def row(self): return publish(self.data, self.client)[0]

    def test_publication_does_not_submit_order_and_replay_is_idempotent(self):
        row = self.row()
        self.assertEqual(row.state, "pending")
        self.assertFalse(any(m == "POST" for m, u, k in self.client.calls))
        same, replay = publish(self.data, self.client)
        self.assertTrue(replay)
        self.assertEqual(same.pk, row.pk)
        self.assertEqual(row.events.filter(kind="published").count(), 1)

    def test_preview_validates_but_never_creates_a_record_or_order(self):
        result, _ = publish(self.data, self.client, preview=True)
        self.assertEqual(result['orders_submitted'],0)
        self.assertEqual(result['state'],'preview_only')
        self.assertFalse(OptionStrategy.objects.exists())
        self.assertFalse(any(m=='POST' for m,u,k in self.client.calls))

    def test_live_endpoint_and_stale_quotes_are_rejected(self):
        self.client.base_url='https://api.alpaca.markets'
        with self.assertRaisesRegex(ValueError,'paper endpoint'): self.row()
        self.client.base_url=PAPER_API_URL
        with patch.object(self.client,'_require_fresh_quote',side_effect=ValueError('stale quote')):
            with self.assertRaisesRegex(ValueError,'stale quote'): self.row()

    def test_capability_and_duplicate_contract_blocks_are_specific(self):
        self.client.level = 2
        with self.assertRaisesRegex(ValueError, "level 3"): self.row()
        self.client.level = 3
        self.row()
        with self.assertRaisesRegex(ValueError, "overlaps strategy"):
            publish(dict(self.data, request_id="another"), self.client)

    def test_expiry_day_close_or_naive_deadline_rejected(self):
        bad = dict(self.data, close_by=(timezone.now() + timedelta(days=35)).isoformat())
        with self.assertRaisesRegex(ValueError, "earliest expiration"): publish(bad, self.client)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            publish(dict(self.data, entry_deadline="2026-10-19T14:00:00"), self.client)

    def test_submission_is_one_atomic_order_with_explicit_open_intents(self):
        row = self.row()
        process(row, self.client, self.client.clock(), timezone.now())
        row.save()
        p = [k["json"] for m,u,k in self.client.calls if m=="POST"][0]
        self.assertEqual(p["order_class"], "mleg")
        self.assertEqual(p["qty"], "1")
        self.assertEqual([l["position_intent"] for l in p["legs"]], ["buy_to_open", "sell_to_open"])
        process(row, self.client, self.client.clock(), timezone.now())
        self.assertEqual(sum(m=="POST" for m,u,k in self.client.calls), 1)

    def test_recover_accepted_submission_after_database_id_was_not_saved(self):
        row = self.row()
        accepted = submit(self.client, row)
        self.assertEqual(row.entry_order_id, "")
        process(row, self.client, self.client.clock(), timezone.now())
        self.assertEqual(row.entry_order_id, accepted["id"])
        self.assertEqual(sum(m=="POST" for m,u,k in self.client.calls), 1)

    def test_ambiguous_submission_never_blindly_retries(self):
        row = self.row()
        row.entry_attempted = True
        with self.assertRaisesRegex(ValueError, "uncertain"):
            submit(self.client, row)
        self.assertFalse(any(m=="POST" for m,u,k in self.client.calls))

    def filled(self, row, closing=False, long_price="4.00", short_price="2.00"):
        oid = row.exit_order_id if closing else row.entry_order_id
        self.client.orders[oid] = {"id": oid, "status": "filled", "legs": [
            {"symbol": row.legs[0]["symbol"], "filled_qty":"1", "filled_avg_price":long_price},
            {"symbol": row.legs[1]["symbol"], "filled_qty":"1", "filled_avg_price":short_price}]}

    def open_row(self):
        row = self.row()
        process(row, self.client, self.client.clock(), timezone.now())
        self.filled(row)
        self.client.positions = [{"symbol": l["symbol"], "qty": "1" if l["side"]=="buy" else "-1"} for l in row.legs]
        process(row, self.client, self.client.clock(), timezone.now())
        return row

    def test_actual_leg_fills_and_whole_strategy_exit_pnl(self):
        row = self.open_row()
        self.assertEqual(row.entry_fill, 2)
        self.assertEqual(row.state, "open")
        row.close_requested = True
        process(row, self.client, self.client.clock(), timezone.now())
        p = [k["json"] for m,u,k in self.client.calls if m=="POST"][-1]
        self.assertEqual(p["type"], "market")
        self.assertEqual([l["position_intent"] for l in p["legs"]], ["sell_to_close", "buy_to_close"])
        self.filled(row, closing=True, long_price="5.00", short_price="2.00")
        self.client.positions=[]
        process(row, self.client, self.client.clock(), timezone.now())
        self.assertEqual(row.state,"closed")
        self.assertEqual(row.realized_pl, 100)

    def test_inventory_mismatch_does_not_submit_dangerous_leg_orders(self):
        row = self.open_row()
        self.client.positions=[]
        before = len(self.client.calls)
        with self.assertRaisesRegex(ValueError, "assignment"):
            process(row, self.client, self.client.clock(), timezone.now())
        self.assertFalse(any(m=="POST" for m,u,k in self.client.calls[before:]))

    def test_time_exit_does_not_depend_on_quote_feed(self):
        row = self.open_row()
        row.close_by = timezone.now() - timedelta(seconds=1)
        with patch("ranker.option_strategies.quotes", side_effect=ValueError("feed outage")):
            process(row, self.client, self.client.clock(), timezone.now())
        self.assertEqual(row.state,"closing")

    def test_exit_before_market_closes_when_next_open_would_miss_deadline(self):
        row=self.open_row()
        now=timezone.now()
        row.close_by=now+timedelta(hours=2)
        clock={'is_open':True,'next_close':(now+timedelta(minutes=30)).isoformat(),
               'next_open':(now+timedelta(days=3)).isoformat()}
        process(row,self.client,clock,now)
        self.assertEqual(row.state,'closing')

    def test_unfilled_rejected_close_advances_generation_only_after_terminal_state(self):
        row=self.open_row()
        row.close_requested=True
        process(row,self.client,self.client.clock(),timezone.now())
        old=row.exit_order_id
        self.client.orders[old]['status']='rejected'
        process(row,self.client,self.client.clock(),timezone.now())
        self.assertEqual(row.exit_generation,1)
        self.assertEqual(row.exit_order_id,'')
        process(row,self.client,self.client.clock(),timezone.now())
        self.assertNotEqual(row.exit_order_id,old)
        self.assertTrue(row.exit_order_id)
        self.assertEqual(row.state,'closing')

    def test_entry_terminal_with_remaining_leg_exposure_is_not_certified_cancelled(self):
        row=self.row()
        process(row,self.client,self.client.clock(),timezone.now())
        self.client.orders[row.entry_order_id]['status']='canceled'
        self.client.positions=[{'symbol':row.legs[0]['symbol'],'qty':'1'}]
        with self.assertRaisesRegex(ValueError,'broker exposure'):
            process(row,self.client,self.client.clock(),timezone.now())
        self.assertNotEqual(row.state,'cancelled')

    def test_shared_capacity_counts_one_strategy_not_each_leg(self):
        row=self.row()
        row.state='open';row.save()
        self.client.config.max_open_positions=1
        dummy=SimpleNamespace(contract_symbol=occ(120),pk=999,paper_quantity=1)
        self.assertIsNone(primary_entry_order(dummy,self.client,Decimal('1'),self.client.config))

    def test_pending_deadline_cancels_once_without_order(self):
        row = self.row()
        row.entry_deadline = timezone.now()-timedelta(seconds=1)
        process(row,self.client,self.client.clock(),timezone.now())
        self.assertEqual(row.state,"expired")
        self.assertFalse(any(m=="POST" for m,u,k in self.client.calls))

    def test_close_partial_fill_blocks_automatic_resubmission(self):
        row=self.open_row()
        row.close_requested=True
        process(row,self.client,self.client.clock(),timezone.now())
        self.client.orders[row.exit_order_id]["status"]="canceled"
        self.client.orders[row.exit_order_id]["legs"][0]["filled_qty"]="1"
        with self.assertRaisesRegex(ValueError,"partial fills"):
            process(row,self.client,self.client.clock(),timezone.now())

    def test_public_record_redacts_operational_details_and_operator_requires_auth(self):
        row=self.row()
        row.last_error="internal broker details"
        row.save()
        api=APIClient()
        response=api.get('/api/option-strategies/')
        record=response.json()['strategies'][0]
        self.assertTrue(record['management_attention'])
        self.assertNotIn('last_error',record)
        self.assertNotIn('entry_order_id',record)
        self.assertIn(api.post('/api/operator/option-strategies/', {}, format='json').status_code, (401,403))

    def test_expired_primary_guardian_does_not_block_open_strategy_time_exit(self):
        row=self.open_row()
        row.close_by=timezone.now()-timedelta(seconds=1)
        row.save()
        TradeExecutorHealth.objects.update(entries_paused=True, status="degraded")
        with patch('ranker.option_strategies.AlpacaPaperClient',return_value=self.client):
            result=run_option_strategy_executor()
        self.assertEqual(result['state'],'closing')

    def test_degraded_guardian_stops_strategy_entries(self):
        row=self.row()
        TradeExecutorHealth.objects.update(entries_paused=True,status='degraded')
        process(row,self.client,self.client.clock(),timezone.now())
        self.assertIn('guardian',row.last_error)
        self.assertFalse(any(m=='POST' for m,u,k in self.client.calls))

    def test_credit_cashflows_are_not_reported_as_debit_losses(self):
        self.data.update(legs=[leg(100,'sell'),leg(105)],entry_limit='-2.00',stop_loss_dollars='100',take_profit_dollars='100')
        self.client.prices={occ(100):(4.2,4.3),occ(105):(2,2.1)}
        row=self.row()
        process(row,self.client,self.client.clock(),timezone.now())
        self.filled(row,long_price='4',short_price='2')
        self.client.positions=[{'symbol':occ(100),'qty':'-1'},{'symbol':occ(105),'qty':'1'}]
        process(row,self.client,self.client.clock(),timezone.now())
        self.assertEqual(row.entry_fill,-2)
        row.close_requested=True
        process(row,self.client,self.client.clock(),timezone.now())
        self.filled(row,closing=True,long_price='3',short_price='2')
        self.client.positions=[]
        process(row,self.client,self.client.clock(),timezone.now())
        self.assertEqual(row.exit_value,-1)
        self.assertEqual(row.realized_pl,100)
