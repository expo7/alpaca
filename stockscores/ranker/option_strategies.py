"""Paper-only complex-order lifecycle. Never submit individual short legs."""
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .alpaca_paper import AlpacaPaperClient, PAPER_API_URL
from .models import OptionStrategy, OptionStrategyEvent, TradeSignal, TradeExecutorHealth, OperationalTelegramAlert
from .option_strategy_rules import validate_structure, number, signed_fill

ACTIVE = ("pending", "entering", "open", "closing", "blocked")
TERMINAL = {"canceled", "expired", "rejected", "done_for_day"}
ET = ZoneInfo("America/New_York")


def event(row, kind, **details):
    customer = kind in {"published", "filled", "closed", "cancelled"}
    return OptionStrategyEvent.objects.create(strategy=row, kind=kind, details=details,
        notification_status="pending" if customer else "none")


def request(client, method, path, **kwargs):
    if client.base_url != PAPER_API_URL:
        raise ValueError("Complex strategies require the exact paper endpoint")
    return client._request(method, client.base_url + path, timeout=3, **kwargs)


def capability(client):
    account = request(client, "GET", "/v2/account")
    level = int(account.get("options_trading_level") or 0)
    result = {"paper": True, "options_trading_level": level,
              "trading_blocked": bool(account.get("trading_blocked")),
              "supported": level >= 3 and not account.get("trading_blocked")}
    return result


def quotes(client, legs):
    payload = client._request("GET", client.data_url + "/v1beta1/options/quotes/latest",
        params={"symbols": ",".join(l["symbol"] for l in legs), "feed": client.config.option_feed}, timeout=3)
    snapshot, cost, value = {}, Decimal(0), Decimal(0)
    for leg in legs:
        q = (payload.get("quotes") or {}).get(leg["symbol"], {})
        client._require_fresh_quote(q.get("t"))
        bid, ask = number(q.get("bp")), number(q.get("ap"))
        if bid <= 0 or ask < bid:
            raise ValueError("Missing or crossed quote for " + leg["symbol"])
        snapshot[leg["symbol"]] = {"bid": str(bid), "ask": str(ask), "at": q["t"]}
        cost += ask if leg["side"] == "buy" else -bid
        value += bid if leg["side"] == "buy" else -ask
    return {"legs": snapshot, "entry_cost": str(cost), "liquidation_value": str(value),
            "source": "Alpaca " + client.config.option_feed,
            "fetched_at": timezone.now().isoformat()}


def contract_conflict(legs, exclude=None):
    symbols = {l["symbol"] for l in legs}
    for s in TradeSignal.objects.filter(status__in=["published", "open"], paper_execution_enabled=True):
        if s.contract_symbol in symbols:
            return "Contract overlaps primary signal " + str(s.pk)
    for s in OptionStrategy.objects.filter(state__in=ACTIVE).exclude(pk=exclude):
        if symbols.intersection(l["symbol"] for l in s.legs):
            return "Contract overlaps strategy " + str(s.pk)
    return ""


def exposure_count():
    return (TradeSignal.objects.filter(paper_execution_enabled=True).filter(
        models_Q_primary()).count() + OptionStrategy.objects.filter(
        state__in=["entering", "open", "closing"]).count())


def models_Q_primary():
    from django.db.models import Q
    return Q(status="open") | (Q(status="published") & ~Q(paper_entry_order_id=""))


def primary_entry_order(signal, client, limit_price, config):
    """Share the existing account position budget with complex strategy units."""
    with transaction.atomic():
        TradeExecutorHealth.objects.select_for_update().get_or_create(singleton_id=1)
        if exposure_count() >= config.max_open_positions:
            return None
        for row in OptionStrategy.objects.filter(state__in=ACTIVE):
            if signal.contract_symbol in {l["symbol"] for l in row.legs}:
                raise ValueError("Primary contract reserved by complex strategy " + str(row.pk))
        order = client.submit_limit_order(symbol=signal.contract_symbol, quantity=signal.paper_quantity,
            side="buy", limit_price=limit_price, client_order_id=f"quantelle-{signal.pk}-entry")
        signal.paper_entry_order_id = order["id"]
        signal.save(update_fields=["paper_entry_order_id", "updated_at"])
        return order


def publish(data, client=None, preview=False):
    allowed = {"request_id", "kind", "legs", "entry_limit", "stop_loss_dollars", "take_profit_dollars",
               "entry_deadline", "close_by", "thesis", "invalidation"}
    if set(data) != allowed or not isinstance(data["request_id"], str) or not 1 <= len(data["request_id"]) <= 100:
        raise ValueError("Strategy publication requires exactly the documented fields and request_id")
    existing = OptionStrategy.objects.filter(request_id=data["request_id"]).first() if not preview else None
    if existing:
        return existing, True
    parsed, risk = validate_structure(data["kind"], data["legs"], data["entry_limit"])
    for key in ("thesis", "invalidation"):
        if not isinstance(data[key], str) or not 20 <= len(data[key].strip()) <= 5000:
            raise ValueError(key + " must explain the idea in 20–5000 characters")
    now = timezone.now()
    times = {}
    for key in ("entry_deadline", "close_by"):
        value = parse_datetime(data[key]) if isinstance(data[key], str) else None
        if value is None or timezone.is_naive(value):
            raise ValueError(key + " must be a timezone-aware timestamp")
        times[key] = value
    if not now < times["entry_deadline"] < times["close_by"]:
        raise ValueError("Entry deadline must be future and precede close_by")
    if times["close_by"].astimezone(ET).date() >= min(l["expiration"] for l in parsed):
        raise ValueError("Close all legs before the earliest expiration date")
    stop, target = number(data["stop_loss_dollars"]), number(data["take_profit_dollars"])
    if not 0 < stop <= number(risk["max_loss_dollars"]) or target <= 0:
        raise ValueError("Dollar stop must be positive and within the risk bound; target must be positive")
    if risk["max_profit_dollars"] is not None and target > number(risk["max_profit_dollars"]):
        raise ValueError("Profit target exceeds the theoretical maximum")
    client = client or AlpacaPaperClient()
    if not client.config.enabled or not capability(client)["supported"]:
        raise ValueError("Paper account needs enabled execution and effective options level 3")
    if not client.clock().get("is_open"):
        raise ValueError("Publish executable strategies during the regular market session")
    for leg in parsed:
        c = request(client, "GET", "/v2/options/contracts/" + leg["symbol"])
        if c.get("symbol") != leg["symbol"] or not c.get("tradable") or str(c.get("size", "100")) != "100":
            raise ValueError("Contract is not a tradable standard 100-share option: " + leg["symbol"])
    snapshot = quotes(client, data["legs"])
    if number(snapshot["entry_cost"]) > number(data["entry_limit"]):
        raise ValueError("Current conservative net price exceeds the signed entry limit")
    if preview:
        try:
            underlying = client.stock_quote(parsed[0]["underlying"], allow_delayed=True, request_timeout=3)
            underlying = {k: str(v) if isinstance(v, Decimal) else v for k,v in underlying.items()}
        except Exception:
            underlying = None
        return {"kind": data["kind"], "symbol": parsed[0]["underlying"], "legs": data["legs"], "underlying": underlying,
                "quote": snapshot, "risk": risk, "state": "preview_only", "orders_submitted": 0,
                "protection": "Defined-risk legs; monitored whole-position exits, no broker-held complex stop"}, False
    # Serialize reservations with the primary executor's entry submission.
    with transaction.atomic():
        TradeExecutorHealth.objects.select_for_update().get_or_create(singleton_id=1)
        existing = OptionStrategy.objects.filter(request_id=data["request_id"]).first()
        if existing:
            return existing, True
        collision = contract_conflict(data["legs"])
        if collision:
            raise ValueError(collision)
        owned = {l["symbol"] for l in data["legs"]}
        if owned.intersection(p["symbol"] for p in request(client, "GET", "/v2/positions")):
            raise ValueError("A strategy leg already exists in the broker account")
        values = {k:v for k,v in data.items() if k not in times}
        for key in ("entry_limit", "stop_loss_dollars", "take_profit_dollars"):
            values[key] = number(values[key])
        row = OptionStrategy.objects.create(**values,
            **times, symbol=parsed[0]["underlying"], risk=risk, quote=snapshot)
        event(row, "published", risk=risk, protection="Defined-risk structure; monitored whole-position exits, no broker-held stop")
        return row, False


def order_lookup(client, client_id):
    try:
        return request(client, "GET", "/v2/orders:by_client_order_id", params={"client_order_id": client_id})
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


def submit(client, row, closing=False):
    generation = row.exit_generation if closing else 0
    cid = f"quantelle-complex-{row.pk}-{'close' if closing else 'open'}-{generation}"
    existing = order_lookup(client, cid)
    if existing:
        return existing
    attempted = row.exit_attempted if closing else row.entry_attempted
    if attempted:
        raise ValueError("Submission outcome uncertain; broker lookup found no order. Retry requires explicit operator recovery")
    if closing:
        row.exit_attempted = True
    else:
        row.entry_attempted = True
        row.state = "entering"
    row.save()
    legs = []
    for leg in row.legs:
        side = ("sell" if leg["side"] == "buy" else "buy") if closing else leg["side"]
        legs.append({"symbol": leg["symbol"], "side": side, "ratio_qty": "1",
                     "position_intent": side + ("_to_close" if closing else "_to_open")})
    payload = {"order_class": "mleg", "qty": "1", "type": "market" if closing else "limit",
               "time_in_force": "day", "client_order_id": cid, "legs": legs}
    if not closing:
        payload["limit_price"] = str(row.entry_limit)
    return request(client, "POST", "/v2/orders", json=payload)


def _terminal_exposure(client, row):
    symbols = {l["symbol"] for l in row.legs}
    return [p for p in request(client, "GET", "/v2/positions") if p["symbol"] in symbols and number(p["qty"]) != 0]


def process(row, client, clock, now):
    if row.entry_order_id or (row.entry_attempted and row.state != "open" and row.entry_fill is None):
        order = request(client, "GET", "/v2/orders/" + row.entry_order_id, params={"nested": "true"}) if row.entry_order_id else order_lookup(client, f"quantelle-complex-{row.pk}-open-0")
        if not order:
            raise ValueError("Entry submission uncertain: no matching broker order; operator recovery required")
        row.entry_order_id = order["id"]
        row.order_status = order["status"]
        if order["status"] == "filled" and row.entry_fill is None:
            row.entry_fill = signed_fill(order, row.legs)
            if row.entry_fill > row.entry_limit:
                row.close_requested = True
            row.state = "open"
            event(row, "filled", entry_fill=str(row.entry_fill), broker_order_id=order["id"])
        elif order["status"] in TERMINAL and row.entry_fill is None:
            if _terminal_exposure(client, row):
                raise ValueError("Terminal entry left broker exposure: inspect every leg before recovery")
            row.state = "cancelled" if row.close_requested else "expired" if now >= row.entry_deadline else "blocked"
            event(row, "cancelled", reason="Entry order ended: " + order["status"])
            return
        elif row.entry_fill is None:
            if now >= row.entry_deadline or row.close_requested:
                request(client, "DELETE", "/v2/orders/" + row.entry_order_id)
            row.state = "entering"
            return
    if row.exit_order_id or row.exit_attempted:
        order = request(client, "GET", "/v2/orders/" + row.exit_order_id, params={"nested": "true"}) if row.exit_order_id else order_lookup(client, f"quantelle-complex-{row.pk}-close-{row.exit_generation}")
        if not order:
            raise ValueError("Close submission uncertain: no matching broker order; operator recovery required")
        row.exit_order_id, row.order_status = order["id"], order["status"]
        if order["status"] == "filled":
            row.exit_value = signed_fill(order, row.legs)
            if _terminal_exposure(client, row):
                raise ValueError("Close reported filled but broker legs remain; reconcile before certifying closed")
            row.realized_pl = (row.exit_value - row.entry_fill) * 100
            row.state = "closed"
            event(row, "closed", realized_pl=str(row.realized_pl), exit_value=str(row.exit_value), broker_order_id=order["id"])
        elif order["status"] in TERMINAL:
            if any(number(l.get("filled_qty", 0)) for l in order.get("legs", [])):
                raise ValueError("Close ended with partial fills: reconcile remaining legs; no automatic reissue")
            row.exit_order_id, row.exit_attempted = "", False
            row.exit_generation += 1
            row.close_requested = True
            row.state = "open"
            event(row, "warning", reason="Close rejected/cancelled; retry whole remaining strategy next cycle")
        else:
            row.state = "closing"
        return
    if row.state == "open":
        positions = {p["symbol"]: number(p["qty"]) for p in request(client, "GET", "/v2/positions")}
        if any(positions.get(l["symbol"]) != (1 if l["side"] == "buy" else -1) for l in row.legs):
            raise ValueError("Leg inventory mismatch / possible assignment. Automatic orders paused for this strategy; reconcile broker shares and options")
        # Time exits must work even if the quote provider is unavailable.
        next_open = parse_datetime(clock.get("next_open", ""))
        next_close = parse_datetime(clock.get("next_close", ""))
        due = now >= row.close_by or bool(next_open and next_close and next_open >= row.close_by and now >= next_close - timedelta(hours=1))
        if not row.close_requested and not due:
            row.quote = quotes(client, row.legs)
            pnl = (number(row.quote["liquidation_value"]) - row.entry_fill) * 100
            row.quote["unrealized_pl"] = str(pnl)
            row.close_requested = pnl <= -row.stop_loss_dollars or pnl >= row.take_profit_dollars
        if row.close_requested or due:
            row.close_requested = True
            order = submit(client, row, closing=True)
            row.exit_order_id, row.order_status, row.state = order["id"], order["status"], "closing"
            event(row, "exit_submitted", broker_order_id=order["id"], reason="deadline" if due else "stop/target/operator")
        return
    if row.state == "pending":
        if now >= row.entry_deadline or row.close_requested:
            row.state = "cancelled" if row.close_requested else "expired"
            event(row, "cancelled", reason="Unfilled entry cancelled or deadline passed")
            return
        health = TradeExecutorHealth.objects.first()
        if not health or health.entries_paused or health.status != "healthy" or not health.last_completed_at or now - health.last_completed_at > timedelta(seconds=60):
            row.last_error = "Primary guardian not ready for new entries"
            return
        if not capability(client)["supported"]:
            raise ValueError("Effective paper options level 3 unavailable")
        row.quote = quotes(client, row.legs)
        if number(row.quote["entry_cost"]) > row.entry_limit:
            row.last_error = "Waiting: conservative net price exceeds signed limit"
            return
        with transaction.atomic():
            TradeExecutorHealth.objects.select_for_update().get_or_create(singleton_id=1)
            if exposure_count() >= client.config.max_open_positions:
                row.last_error = "Waiting: shared primary/strategy position limit"
                return
            collision = contract_conflict(row.legs, exclude=row.pk)
            if collision or _terminal_exposure(client, row):
                raise ValueError(collision or "Broker already holds a reserved leg")
            order = submit(client, row)
            row.entry_order_id, row.order_status, row.state = order["id"], order["status"], "entering"
            event(row, "entry_submitted", broker_order_id=order["id"])


def run_option_strategy_executor():
    """One bounded strategy per existing guardian cycle; primary work runs first."""
    if not OptionStrategy.objects.filter(state__in=ACTIVE).exists():
        return {"status": "idle"}
    if not cache.add("quantelle-complex-executor", "1", timeout=120):
        return {"status": "locked"}
    try:
        client = AlpacaPaperClient()
        if not client.config.enabled:
            return {"status": "disabled"}
        clock = client.clock()
        if not clock.get("is_open"):
            return {"status": "market_closed"}
        # In-flight orders and open risks precede fresh entries.
        qs = OptionStrategy.objects.filter(state__in=ACTIVE).exclude(state="blocked")
        row = qs.order_by("checked_at", "id").first()
        if not row:
            return {"status": "blocked"}
        previous_error = row.last_error
        row.last_error = ""
        try:
            process(row, client, clock, timezone.now())
        except Exception as exc:
            row.last_error = str(exc)[:500]
            if row.last_error != previous_error:
                event(row, "warning", error=row.last_error)
            bucket = int(timezone.now().timestamp()) // 300
            OperationalTelegramAlert.objects.get_or_create(idempotency_key=f"complex:{row.pk}:{bucket}",
                defaults={"message": f"Paper strategy {row.pk}: {row.last_error}"})
        row.checked_at = timezone.now()
        row.save()
        return {"status": "error" if row.last_error else "ok", "strategy_id": row.pk,
                "state": row.state, "error": row.last_error}
    finally:
        cache.delete("quantelle-complex-executor")


def deliver_strategy_events():
    if not (settings.TELEGRAM_NOTIFICATIONS_ENABLED and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return
    now = timezone.now()
    ids = OptionStrategyEvent.objects.filter(notification_status="pending").filter(
        Q(notification_after__isnull=True) | Q(notification_after__lte=now)).values_list("pk", flat=True)[:2]
    for pk in ids:
        with transaction.atomic():
            e = OptionStrategyEvent.objects.select_for_update().select_related("strategy").get(pk=pk)
            if e.notification_status != "pending":
                continue
            e.notification_attempts += 1
            e.notification_after = now + timedelta(minutes=5)
            e.save()
        try:
            row = e.strategy
            text = f"Quantelle PAPER {row.kind.replace('_', ' ')} · {row.symbol}\n{e.kind.upper()} · one strategy unit\n"
            text += "\n".join(f"{l['side'].upper()} 1 {l['symbol']}" for l in row.legs)
            text += f"\nNet entry limit {row.entry_limit} (debit + / credit −).\nMonitored whole-position exits; no broker-held complex stop.\nhttps://quantelle.io/signals#strategy-{row.pk}"
            if e.kind == "filled":
                text += f"\nActual signed entry: {e.details.get('entry_fill')}"
            elif e.kind == "closed":
                text += f"\nRealized paper P/L: ${e.details.get('realized_pl')} (before fees)"
            response = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=3)
            response.raise_for_status()
            if not response.json().get("ok"):
                raise ValueError("Telegram did not accept strategy event")
            e.notification_status = "sent"
            e.notification_error = ""
        except Exception as exc:
            e.notification_error = type(exc).__name__
        e.save()
