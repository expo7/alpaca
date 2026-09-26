"""Isolated, opt-in Alpaca paper shadow cycle. Never scheduled by primary Celery."""

from decimal import Decimal
import os

from django.db import connection
from django.utils import timezone

from .models import ShadowEvent, ShadowExecutorHealth, ShadowSetup
from .protection_policy import desired_exit
from .shadow_broker import ShadowPaperClient, verify_account_identity, execution_configured, ShadowIdentityError


ACTIVE_ORDERS = {"new", "accepted", "pending_new", "partially_filled", "pending_cancel", "accepted_for_bidding"}
TERMINAL_ORDERS = {"canceled", "expired", "rejected", "done_for_day", "replaced"}
LOCK_NUMBER = 762340019 # never shared with primary executor


def _event(setup, kind, now, **details):
    return ShadowEvent.objects.create(setup=setup, kind=kind, occurred_at=now, details=details,
                                      broker_order_id=str(details.get("broker_order_id") or ""))


def _health(status, now, account_id="", error=""):
    ShadowExecutorHealth.objects.update_or_create(singleton_id=1, defaults={
        "status": status, "last_error": error[:300], "checked_at": now, "verified_account_id": account_id,
    })


def _limit(name, default, *, ceiling):
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= ceiling:
        raise ShadowIdentityError(f"{name} must be between 1 and {ceiling}")
    return value


def _broker_order(client, order_id, client_id):
    if order_id:
        return client.order(order_id)
    # An intent without an order ID is ambiguous. Never submit another order.
    return client.by_client_id(client_id)


def _broker_position(client, setup):
    matches = [p for p in client.positions() if p.get("symbol") == setup.decision["option_symbol"]]
    if len(matches) > 1 or (matches and Decimal(str(matches[0].get("qty", 0))) != 1):
        raise ShadowIdentityError("Unexpected shadow contract inventory")
    return matches[0] if matches else None


def _submit_entry(setup, client, account_id, now, ask):
    if setup.broker_entry_client_id:
        raise ShadowIdentityError("Unresolved shadow entry intent")
    if _broker_position(client, setup):
        raise ShadowIdentityError("Contract already held in shadow account")
    client_id = f"quantelle-shadow-{setup.pk}-entry"
    setup.broker_entry_client_id = client_id
    setup.broker_account_id = account_id
    setup.activated_at = now
    setup.save(update_fields=["broker_entry_client_id", "broker_account_id", "activated_at"])
    _event(setup, "entry_intent", now, client_order_id=client_id, limit=str(ask))
    # Intent is durable before the network request; ambiguous responses require reconciliation.
    order = client.submit_limit_order(symbol=setup.decision["option_symbol"], quantity=1, side="buy",
                                      limit_price=ask, client_order_id=client_id)
    setup.broker_entry_order_id = order["id"]
    setup.status = "waiting"
    setup.save(update_fields=["broker_entry_order_id", "status"])
    _event(setup, "entry_submitted", now, broker_order_id=order["id"], status=order.get("status", "submitted"))
    return "entry_submitted"


def _entry(setup, client, account_id, now, daily_limit, concurrent_limit):
    d = setup.decision
    deadline = timezone.datetime.fromisoformat(d["entry_deadline"])
    if setup.broker_entry_client_id:
        order = _broker_order(client, setup.broker_entry_order_id, setup.broker_entry_client_id)
        if order.get("id") and not setup.broker_entry_order_id:
            setup.broker_entry_order_id = order["id"]
            setup.save(update_fields=["broker_entry_order_id"])
        state = order.get("status")
        if state == "filled":
            if not _broker_position(client, setup):
                raise ShadowIdentityError("Entry filled but exact position is not yet verified")
            price = Decimal(str(order["filled_avg_price"]))
            setup.entered_at = timezone.datetime.fromisoformat(order["filled_at"].replace("Z", "+00:00")) if order.get("filled_at") else now
            setup.status = "active"
            setup.result = {"result_type": "broker", "broker_entry": str(price), "quantity": 1,
                            "unrealized_return_pct": "0", "mfe_pct": "0", "mae_pct": "0",
                            "thesis_valid": None, "confidence": "broker_fill_verified",
                            "time_to_entry_seconds": (setup.entered_at - setup.decided_at).total_seconds()}
            setup.save(update_fields=["entered_at", "status", "result"])
            _event(setup, "entry_filled", now, broker_order_id=order["id"], price=str(price))
            return _open(setup, client, now)
        if state in ACTIVE_ORDERS:
            if now > deadline and state != "pending_cancel":
                if not setup.events.filter(kind="entry_cancel_requested", broker_order_id=order["id"]).exists():
                    client.cancel_order(order["id"])
                    _event(setup, "entry_cancel_requested", now, broker_order_id=order["id"])
                return "entry_cancel_pending"
            return "entry_pending"
        if state in TERMINAL_ORDERS:
            setup.status = "rejected" if state == "rejected" else "expired_unfilled" if now > deadline or state == "expired" else "cancelled"
            setup.save(update_fields=["status"])
            _event(setup, state, now, broker_order_id=order["id"])
            return setup.status
        raise ShadowIdentityError("Unrecognized entry order status")
    if now > deadline:
        setup.status = "expired_unfilled"
        setup.save(update_fields=["status"])
        _event(setup, "expired_unfilled", now)
        return "expired_unfilled"
    if os.getenv("SHADOW_AUTONOMOUS_ENTRIES_ENABLED", "false").lower() != "true" and \
            os.getenv("SHADOW_ALLOWED_SETUP_ID", "") != str(setup.pk):
        return "entry_not_approved"
    if ShadowSetup.objects.filter(execution_mode="broker_intended", status="active").count() >= concurrent_limit:
        return "concurrent_limit"
    if ShadowSetup.objects.filter(execution_mode="broker_intended", status__in=("proposed", "waiting"))\
            .exclude(pk=setup.pk).exclude(broker_entry_client_id="").count() >= concurrent_limit:
        return "pending_entry_limit"
    if ShadowEvent.objects.filter(kind="entry_intent", occurred_at__date=now.date()).count() >= daily_limit:
        return "daily_limit"
    stock = client.stock_quote(d["symbol"])
    underlying = stock["midpoint"]
    trigger = Decimal(d["underlying_trigger_price"])
    invalidation = Decimal(d["underlying_invalidation"])
    if (underlying <= invalidation if d["direction"] == "bullish" else underlying >= invalidation):
        setup.trigger_first_seen_at = None
        setup.save(update_fields=["trigger_first_seen_at"])
        return "underlying_invalidated"
    crossed = underlying >= trigger if d["trigger_direction"] == "above" else underlying <= trigger
    if not crossed:
        setup.trigger_first_seen_at = None
        setup.save(update_fields=["trigger_first_seen_at"])
        return "waiting_for_trigger"
    if not setup.trigger_first_seen_at:
        setup.trigger_first_seen_at = now
        setup.save(update_fields=["trigger_first_seen_at"])
        return "confirming_trigger"
    if (now - setup.trigger_first_seen_at).total_seconds() < int(d["confirmation_seconds"]):
        return "confirming_trigger"
    quote = client.option_quote(d["option_symbol"])
    ask = quote["ask"]
    max_spread = _limit("SHADOW_MAX_SPREAD_PCT", 12, ceiling=20)
    if quote["spread_pct"] > max_spread:
        return "spread_too_wide"
    if not Decimal(d["entry_low"]) <= ask <= Decimal(d["entry_high"]) or ask > Decimal(d["do_not_chase"]):
        return "outside_entry_range"
    # Preserve the explicit near-miss rationale: no publication gate is silently lowered.
    if _broker_position(client, setup):
        raise ShadowIdentityError("Existing exact shadow position blocks entry")
    if len(client.positions()) >= concurrent_limit:
        return "broker_position_limit"
    return _submit_entry(setup, client, account_id, now, ask)


def _submit_exit(setup, client, now, kind):
    if setup.broker_exit_client_id:
        raise ShadowIdentityError("Unresolved shadow exit intent")
    generation = setup.events.filter(kind="exit_intent").count() + 1
    client_id = f"quantelle-shadow-{setup.pk}-{kind}-{generation}"
    setup.broker_exit_client_id = client_id
    setup.broker_protection_kind = kind
    setup.save(update_fields=["broker_exit_client_id", "broker_protection_kind"])
    _event(setup, "exit_intent", now, protection_kind=kind, client_order_id=client_id)
    if kind == "stop":
        order = client.submit_stop_order(symbol=setup.decision["option_symbol"], quantity=1,
                                         stop_price=Decimal(setup.decision["stop"]), client_order_id=client_id)
    elif kind == "target":
        order = client.submit_limit_order(symbol=setup.decision["option_symbol"], quantity=1, side="sell",
                                          limit_price=Decimal(setup.decision["target_1"]),
                                          client_order_id=client_id, time_in_force="gtc")
    else:
        order = client.submit_market_order(symbol=setup.decision["option_symbol"], quantity=1,
                                           side="sell", client_order_id=client_id)
    setup.broker_exit_order_id = order["id"]
    setup.save(update_fields=["broker_exit_order_id"])
    _event(setup, "exit_submitted", now, broker_order_id=order["id"], protection_kind=kind)
    return "exit_submitted"


def _open(setup, client, now):
    if not _broker_position(client, setup):
        # First reconcile an existing exit; a filled exit can explain absence of position.
        if not setup.broker_exit_client_id:
            fills = [o for o in client.orders() if o.get("symbol") == setup.decision["option_symbol"]
                     and o.get("side") == "sell" and o.get("status") == "filled"
                     and Decimal(str(o.get("filled_qty") or o.get("qty") or 0)) == 1
                     and o.get("filled_at")
                     and timezone.datetime.fromisoformat(o["filled_at"].replace("Z", "+00:00")) >= setup.entered_at]
            if len(fills) != 1 or not fills[0].get("filled_avg_price"):
                raise ShadowIdentityError("Open shadow trade has no verified position or unambiguous exit")
            fill = fills[0]
            price = Decimal(str(fill["filled_avg_price"]))
            entry = Decimal(setup.result["broker_entry"])
            result = setup.result.copy()
            result.update({"broker_exit": str(price), "exit_reason": "manually_closed",
                           "realized_return_dollars": str((price - entry) * 100),
                           "realized_return_pct": str((price - entry) / entry * 100)})
            result.pop("unrealized_return_pct", None)
            setup.result = result
            setup.exited_at = timezone.datetime.fromisoformat(fill["filled_at"].replace("Z", "+00:00"))
            setup.status = "completed"
            setup.save(update_fields=["result", "exited_at", "status"])
            _event(setup, "manually_closed", now, broker_order_id=fill["id"], price=str(price))
            return "completed"
    if setup.broker_exit_client_id:
        order = _broker_order(client, setup.broker_exit_order_id, setup.broker_exit_client_id)
        if order.get("id") and not setup.broker_exit_order_id:
            setup.broker_exit_order_id = order["id"]
            setup.save(update_fields=["broker_exit_order_id"])
        state = order.get("status")
        if state == "filled":
            if _broker_position(client, setup):
                raise ShadowIdentityError("Exit filled but position remains at broker")
            price = Decimal(str(order["filled_avg_price"]))
            entry = Decimal(setup.result["broker_entry"])
            result = setup.result.copy()
            result.update({"broker_exit": str(price), "exit_reason": setup.broker_protection_kind,
                           "realized_return_dollars": str((price - entry) * 100),
                           "realized_return_pct": str((price - entry) / entry * 100)})
            result.pop("unrealized_return_pct", None)
            setup.result = result
            setup.exited_at = timezone.datetime.fromisoformat(order["filled_at"].replace("Z", "+00:00")) if order.get("filled_at") else now
            setup.status = "completed"
            setup.save(update_fields=["result", "exited_at", "status"])
            _event(setup, "exit_filled", now, broker_order_id=order["id"], price=str(price))
            return "completed"
        if state in ACTIVE_ORDERS:
            quote = client.option_quote(setup.decision["option_symbol"])
            bid = quote["bid"]
            _excursion(setup, bid)
            if state == "pending_cancel":
                return "cancel_pending"
            wanted = desired_exit(bid=bid, stop=Decimal(setup.decision["stop"]),
                                  target=Decimal(setup.decision["target_1"]),
                                  currently_target=setup.broker_protection_kind == "target")
            if wanted != setup.broker_protection_kind:
                if not setup.events.filter(kind="exit_cancel_requested", broker_order_id=order["id"]).exists():
                    client.cancel_order(order["id"])
                    _event(setup, "exit_cancel_requested", now, broker_order_id=order["id"])
                return "cancel_pending"
            return "protected"
        if state not in TERMINAL_ORDERS:
            raise ShadowIdentityError("Unrecognized exit order status")
        _event(setup, "exit_order_terminal", now, broker_order_id=order["id"], status=state)
        setup.broker_exit_order_id = ""
        setup.broker_exit_client_id = ""
        setup.save(update_fields=["broker_exit_order_id", "broker_exit_client_id"])
    if not _broker_position(client, setup):
        raise ShadowIdentityError("No verified position after exit cancellation")
    quote = client.option_quote(setup.decision["option_symbol"])
    bid = quote["bid"]
    _excursion(setup, bid)
    if bid <= Decimal(setup.decision["stop"]):
        return _submit_exit(setup, client, now, "stop_fallback")
    kind = desired_exit(bid=bid, stop=Decimal(setup.decision["stop"]),
                        target=Decimal(setup.decision["target_1"]), currently_target=False)
    return _submit_exit(setup, client, now, kind)


def _excursion(setup, bid):
    entry = Decimal(setup.result["broker_entry"])
    value = (bid - entry) / entry * 100
    result = setup.result.copy()
    result["unrealized_return_pct"] = str(value)
    result["mfe_pct"] = str(max(value, Decimal(result["mfe_pct"])))
    result["mae_pct"] = str(min(value, Decimal(result["mae_pct"])))
    setup.result = result
    setup.save(update_fields=["result"])


def run_shadow_cycle(*, client_factory=ShadowPaperClient, identity=verify_account_identity, now=None):
    now = now or timezone.now()
    if not execution_configured():
        _health("disabled", now)
        return {"status": "disabled"}
    if connection.vendor != "postgresql":
        _health("paused", now, error="Dedicated executor requires PostgreSQL advisory locking")
        return {"status": "paused"}
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_NUMBER])
        locked = cursor.fetchone()[0]
    if not locked:
        return {"status": "locked"}
    try:
        account_id = identity()
        concurrent = _limit("SHADOW_MAX_CONCURRENT_POSITIONS", 1, ceiling=3)
        daily = _limit("SHADOW_MAX_DAILY_ENTRIES", 2, ceiling=5)
        client = client_factory()
        if not client.clock().get("is_open"):
            _health("market_closed", now, account_id)
            return {"status": "market_closed"}
        results = {}
        # Open positions go first: a protection error pauses all new shadow entries.
        open_setups = list(ShadowSetup.objects.filter(execution_mode="broker_intended", status="active").order_by("entered_at", "id"))
        entries = list(ShadowSetup.objects.filter(execution_mode="broker_intended", status__in=("proposed", "waiting")).order_by("decided_at", "id"))
        open_error = False
        for setup in open_setups + entries:
            try:
                if open_error and setup.status != "active":
                    results[str(setup.pk)] = "open_protection_degraded"
                    continue
                if setup.broker_account_id and setup.broker_account_id != account_id:
                    raise ShadowIdentityError("Stored shadow account ID changed")
                results[str(setup.pk)] = _open(setup, client, now) if setup.status == "active" else _entry(
                    setup, client, account_id, now, daily, concurrent)
                setup.reconciled_at = now
                setup.last_error = ""
                setup.save(update_fields=["reconciled_at", "last_error"])
            except Exception as exc:
                # Independent health, no primary Guardian, Telegram, or TradeSignal writes.
                error = f"{type(exc).__name__}: shadow evaluation failed" if not isinstance(exc, ShadowIdentityError) else str(exc)[:300]
                if setup.last_error != error:
                    _event(setup, "execution_error", now, message=error)
                setup.last_error = error
                setup.save(update_fields=["last_error"])
                results[str(setup.pk)] = "error"
                if setup.status == "active":
                    open_error = True
        state = "degraded" if "error" in results.values() else "healthy"
        _health(state, now, account_id, error="Shadow setup reconciliation failed" if state == "degraded" else "")
        return {"status": state, "setups": results}
    except Exception as exc:
        _health("degraded", now, error=f"{type(exc).__name__}: shadow preflight failed")
        return {"status": "degraded"}
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_NUMBER])
