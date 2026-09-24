from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .alpaca_paper import AlpacaPaperClient, PaperTradingError, load_paper_config
from .models import (
    OperationalTelegramAlert,
    TelegramNotification,
    TradeExecutorHealth,
    TradeLifecycleCertification,
    TradeSignal,
    TradeSignalUpdate,
)


RECENT_TERMINAL_WINDOW = timedelta(hours=24)
GUARDIAN_FRESHNESS = timedelta(minutes=3)
TERMINAL_STATUSES = {
    TradeSignal.STATUS_CLOSED,
    TradeSignal.STATUS_CANCELLED,
    TradeSignal.STATUS_EXPIRED,
}
UNRESOLVED_STATUSES = {TradeSignal.STATUS_PUBLISHED, TradeSignal.STATUS_OPEN}
REQUIRED_TELEGRAM_EVENTS = {
    TradeSignal.STATUS_PUBLISHED: {"published"},
    TradeSignal.STATUS_OPEN: {"published", "triggered"},
    TradeSignal.STATUS_CLOSED: {"published", "triggered", "closed"},
    TradeSignal.STATUS_CANCELLED: {"published", "cancelled"},
    TradeSignal.STATUS_EXPIRED: {"published", "cancelled"},
}


def certification_candidates(now=None):
    now = now or timezone.now()
    recent = now - RECENT_TERMINAL_WINDOW
    return TradeSignal.objects.filter(
        Q(status__in=UNRESOLVED_STATUSES)
        | Q(status__in=TERMINAL_STATUSES, closed_at__gte=recent)
        | Q(paper_last_error__gt="", updated_at__gte=recent)
    ).distinct().order_by("id")


def _checkpoint(checkpoints, codes, details, name, passed, code, detail, *, pending=False):
    result = "pass" if passed else ("pending" if pending else "fail")
    checkpoints[name] = {"result": result, "detail": detail}
    if not passed and not pending:
        codes.append(code)
        details.append(detail)


def _not_applicable(checkpoints, name, detail):
    checkpoints[name] = {"result": "not_applicable", "detail": detail}


def _queue_warning(signal, codes, details):
    if not codes:
        return
    signature = ",".join(sorted(set(codes)))
    key = f"lifecycle-audit:{signal.pk}:{signature}"[:160]
    message = (
        f"⚠️ Quantelle lifecycle certification discrepancy · {signal.display_instrument}\n"
        f"Signal {signal.pk}: {signature}\n" + "\n".join(details[:6])
    )
    OperationalTelegramAlert.objects.get_or_create(
        idempotency_key=key,
        defaults={"signal": signal, "message": message},
    )


def _broker_snapshot(signal, client, orders, positions):
    by_id = {str(order.get("id")): order for order in orders if order.get("id")}
    relevant = [
        order for order in orders
        if str(order.get("client_order_id") or "").startswith(f"quantelle-{signal.pk}-")
    ]
    position = next((p for p in positions if p.get("symbol") == signal.contract_symbol), None)
    return by_id, relevant, position


def _active_order(order):
    return order.get("status") in {"accepted", "new", "pending_new", "partially_filled", "held"}


def _matches_protection(signal, order):
    if not order or not _active_order(order):
        return False
    expected_type = {"broker_stop": "stop", "broker_target": "limit"}.get(signal.paper_exit_reason)
    if not expected_type:
        return False
    price_key = "stop_price" if expected_type == "stop" else "limit_price"
    expected_price = signal.current_stop or signal.initial_stop if expected_type == "stop" else signal.target_1
    try:
        return (
            order.get("type") == expected_type
            and order.get("time_in_force") == "gtc"
            and order.get("side") == "sell"
            and order.get("symbol") == signal.contract_symbol
            and Decimal(str(order.get("qty"))) == Decimal(str(signal.paper_quantity))
            and Decimal(str(order.get(price_key))) == expected_price
        )
    except (TypeError, ValueError, InvalidOperation):
        return False


def audit_trade_signal(signal, *, client=None, orders=None, positions=None, now=None):
    """Certify one lifecycle without mutating trading or lifecycle state."""
    now = now or timezone.now()
    checkpoints, codes, details = {}, [], []
    pending = signal.status in UNRESOLVED_STATUSES
    updates = list(signal.updates.filter(audience=TradeSignalUpdate.AUDIENCE_CUSTOMER).select_related("telegram_notification"))
    event_types = [update.event_type for update in updates]

    publication_ok = bool(signal.published_at and "published" in event_types)
    _checkpoint(checkpoints, codes, details, "operator_publication_completed", publication_ok,
                "PUBLICATION_INCOMPLETE", "Published timestamp and immutable publication event are present." if publication_ok else "Publication timestamp or event is missing.")

    broker_error = None
    relevant_orders, position = [], None
    try:
        if client is None:
            client = AlpacaPaperClient()
        if orders is None:
            orders = client.orders()
        if positions is None:
            positions = client.positions()
        by_id, relevant_orders, position = _broker_snapshot(signal, client, orders, positions)
        entry_order = by_id.get(signal.paper_entry_order_id) if signal.paper_entry_order_id else None
        exit_order = by_id.get(signal.paper_exit_order_id) if signal.paper_exit_order_id else None
    except Exception as exc:
        broker_error = str(exc)[:500]
        entry_order = exit_order = None
        codes.append("ALPACA_API_FAILURE")
        details.append(f"Alpaca paper reconciliation failed: {broker_error}")

    if broker_error:
        checkpoints["broker_order_accepted"] = {"result": "error", "detail": broker_error}
        checkpoints["entry_filled"] = {"result": "error", "detail": broker_error}
    elif signal.status in {TradeSignal.STATUS_CANCELLED, TradeSignal.STATUS_EXPIRED} and signal.actual_entry is None:
        if entry_order and entry_order.get("status") == "filled":
            _checkpoint(checkpoints, codes, details, "broker_order_accepted", True,
                        "BROKER_ENTRY_MISMATCH", "Recorded entry order exists at Alpaca.")
            _checkpoint(checkpoints, codes, details, "entry_filled", False,
                        "ENTRY_FILL_MISMATCH", "Broker entry filled, but Quantelle recorded an unfilled terminal setup.")
        else:
            _not_applicable(checkpoints, "broker_order_accepted", "Unfilled setup requires no accepted entry order.")
            _not_applicable(checkpoints, "entry_filled", "Setup ended before an entry filled.")
        if position is not None:
            _checkpoint(checkpoints, codes, details, "unfilled_broker_position_absent", False,
                        "UNEXPECTED_BROKER_POSITION", "Unfilled terminal setup has a broker position.")
    elif signal.paper_entry_order_id:
        accepted = bool(entry_order and entry_order.get("status") not in {"rejected", "canceled", "expired"})
        _checkpoint(checkpoints, codes, details, "broker_order_accepted", accepted,
                    "BROKER_ENTRY_MISMATCH", "Recorded entry order exists at Alpaca." if accepted else "Recorded entry order is missing or not accepted at Alpaca.")
        filled = bool(entry_order and entry_order.get("status") == "filled")
        needs_fill = signal.status in {TradeSignal.STATUS_OPEN, TradeSignal.STATUS_CLOSED}
        _checkpoint(checkpoints, codes, details, "entry_filled", filled, "ENTRY_FILL_MISMATCH",
                    "Entry order is filled at Alpaca." if filled else "Entry order is not filled at Alpaca.", pending=not needs_fill)
    else:
        _checkpoint(checkpoints, codes, details, "broker_order_accepted", False, "ENTRY_ORDER_MISSING",
                    "No broker entry order has been recorded.", pending=signal.status == TradeSignal.STATUS_PUBLISHED)
        _checkpoint(checkpoints, codes, details, "entry_filled", False, "ENTRY_NOT_FILLED",
                    "Entry has not filled.", pending=signal.status == TradeSignal.STATUS_PUBLISHED)

    executor_ok = bool(
        signal.status not in {TradeSignal.STATUS_OPEN, TradeSignal.STATUS_CLOSED}
        or (signal.actual_entry is not None and signal.paper_filled_at and "triggered" in event_types)
    )
    _checkpoint(checkpoints, codes, details, "executor_recognized_position", executor_ok,
                "EXECUTOR_POSITION_MISMATCH", "Executor lifecycle state recognizes the fill." if executor_ok else "Executor has not fully recorded the filled position.")

    health = TradeExecutorHealth.objects.filter(singleton_id=1).first()
    guardian_fresh = bool(
        health and health.last_completed_at and health.last_completed_at >= now - GUARDIAN_FRESHNESS
        and health.status in {TradeExecutorHealth.STATUS_HEALTHY, TradeExecutorHealth.STATUS_MARKET_CLOSED}
    )
    if signal.status == TradeSignal.STATUS_OPEN:
        broker_position_ok = broker_error is None and position is not None
        guardian_ok = guardian_fresh and broker_position_ok
        _checkpoint(checkpoints, codes, details, "guardian_recognized_protected_position", guardian_ok,
                    "GUARDIAN_POSITION_UNPROTECTED", "Guardian heartbeat is fresh and the paper position exists." if guardian_ok else "Guardian heartbeat is stale/degraded or the paper position is missing.")
        monitoring = guardian_ok and signal.paper_last_checked_at is not None
        _checkpoint(checkpoints, codes, details, "stop_target_monitoring_active", monitoring,
                    "MONITORING_INACTIVE", "Stop/target monitoring is active." if monitoring else "Stop/target monitoring cannot be confirmed active.")
        if broker_error:
            checkpoints["broker_held_protection"] = {"result": "error", "detail": "Broker protection could not be verified."}
        else:
            active_exits = [order for order in relevant_orders if order.get("side") == "sell" and _active_order(order)]
            protection_ok = (
                len(active_exits) == 1
                and str(active_exits[0].get("id")) == signal.paper_exit_order_id
                and _matches_protection(signal, active_exits[0])
            )
            _checkpoint(checkpoints, codes, details, "broker_held_protection", protection_ok,
                        "BROKER_PROTECTION_MISMATCH",
                        "Exactly one matching broker-held GTC protection order is active." if protection_ok else
                        "A single matching broker-held GTC stop or target order could not be confirmed.")
    else:
        _not_applicable(checkpoints, "guardian_recognized_protected_position", "Required only while a position is open.")
        _not_applicable(checkpoints, "stop_target_monitoring_active", "Required only while a position is open.")
        _not_applicable(checkpoints, "broker_held_protection", "Required only while a position is open.")

    if signal.status == TradeSignal.STATUS_CLOSED:
        exit_complete = bool(signal.paper_exit_order_id and exit_order and exit_order.get("status") == "filled")
        _checkpoint(checkpoints, codes, details, "exit_order_completed", exit_complete,
                    "EXIT_ORDER_MISMATCH", "Exit order is filled at Alpaca." if exit_complete else "Recorded exit order is missing or not filled at Alpaca.")
    elif signal.status in {TradeSignal.STATUS_CANCELLED, TradeSignal.STATUS_EXPIRED}:
        _not_applicable(checkpoints, "exit_order_completed", "No filled position required an exit order.")
    else:
        _checkpoint(checkpoints, codes, details, "exit_order_completed", False, "EXIT_PENDING",
                    "Trade has not reached final exit.", pending=True)

    if signal.status in TERMINAL_STATUSES:
        db_final = bool(signal.closed_at and (
            signal.status != TradeSignal.STATUS_CLOSED
            or (signal.final_exit is not None and signal.realized_return_pct is not None and "closed" in event_types)
        ))
        _checkpoint(checkpoints, codes, details, "database_finalized", db_final,
                    "DATABASE_NOT_FINALIZED", "Terminal database fields are complete." if db_final else "Terminal database fields or final lifecycle event are incomplete.")
        public_final = signal.is_test or (db_final and signal.status in TERMINAL_STATUSES)
        _checkpoint(checkpoints, codes, details, "public_record_finalized", public_final,
                    "PUBLIC_RECORD_NOT_FINALIZED", "Public record reflects the terminal state." if public_final else "Public record is not ready to represent the terminal state.")
    else:
        _checkpoint(checkpoints, codes, details, "database_finalized", False, "DATABASE_PENDING", "Lifecycle is unresolved.", pending=True)
        _checkpoint(checkpoints, codes, details, "public_record_finalized", False, "PUBLIC_RECORD_PENDING", "Lifecycle is unresolved.", pending=True)

    required_events = REQUIRED_TELEGRAM_EVENTS.get(signal.status, set())
    notifications = {u.event_type: getattr(u, "telegram_notification", None) for u in updates if u.event_type in required_events}
    telegram_ok = all(
        notifications.get(event) and notifications[event].status == TelegramNotification.STATUS_SENT
        for event in required_events
    )
    _checkpoint(checkpoints, codes, details, "required_telegram_events_succeeded", telegram_ok,
                "TELEGRAM_EVENT_MISSING", "All required lifecycle Telegram events were sent." if telegram_ok else "One or more required lifecycle Telegram events are missing or unsent.")

    duplicate_event_types = list(
        TradeSignalUpdate.objects.filter(signal=signal, event_type__in={"published", "triggered", "closed", "cancelled"})
        .values("event_type").annotate(total=Count("id")).filter(total__gt=1).values_list("event_type", flat=True)
    )
    client_ids = [str(o.get("client_order_id") or "") for o in relevant_orders]
    duplicate_orders = sorted({value for value in client_ids if value and client_ids.count(value) > 1})
    no_duplicates = not duplicate_event_types and not duplicate_orders
    _checkpoint(checkpoints, codes, details, "no_duplicate_orders_or_lifecycle_events", no_duplicates,
                "DUPLICATE_LIFECYCLE_ARTIFACT", "No duplicate broker orders or unique lifecycle events found." if no_duplicates else f"Duplicates found: events={duplicate_event_types}, orders={duplicate_orders}.")

    has_error = broker_error is not None
    has_failures = any(value["result"] in {"fail", "error"} for value in checkpoints.values())
    certified = not pending and not has_failures
    status_value = (
        TradeLifecycleCertification.STATUS_CERTIFIED if certified else
        TradeLifecycleCertification.STATUS_ERROR if has_error else
        TradeLifecycleCertification.STATUS_DISCREPANCY if has_failures else
        TradeLifecycleCertification.STATUS_PENDING
    )
    with transaction.atomic():
        record, _ = TradeLifecycleCertification.objects.select_for_update().get_or_create(signal=signal)
        was_certified = record.lifecycle_certified
        record.status = status_value
        record.lifecycle_certified = certified
        record.checked_at = now
        record.certified_at = record.certified_at if certified and was_certified else (now if certified else None)
        record.checkpoints = checkpoints
        record.discrepancy_codes = sorted(set(codes))
        record.discrepancy_details = details
        record.retry_count = record.retry_count + 1 if has_failures or has_error else 0
        record.save()
        _queue_warning(signal, record.discrepancy_codes, details)
    return record


def audit_lifecycles(now=None):
    now = now or timezone.now()
    signals = list(certification_candidates(now))
    if not signals:
        return {"status": "idle", "audited": 0}
    client = None
    orders = positions = None
    if load_paper_config().enabled:
        try:
            client = AlpacaPaperClient()
            orders, positions = client.orders(), client.positions()
        except Exception:
            client = None
    results = {}
    for signal in signals:
        record = audit_trade_signal(signal, client=client, orders=orders, positions=positions, now=now)
        results[str(signal.pk)] = record.status
    return {"status": "ok", "audited": len(signals), "signals": results}


def certification_payload(record):
    return {
        "signal_id": record.signal_id,
        "symbol": record.signal.display_instrument,
        "lifecycle_status": record.signal.status,
        "certification_status": record.status,
        "lifecycle_certified": record.lifecycle_certified,
        "checked_at": record.checked_at,
        "certified_at": record.certified_at,
        "retry_count": record.retry_count,
        "checkpoints": record.checkpoints,
        "discrepancy_codes": record.discrepancy_codes,
        "discrepancy_details": record.discrepancy_details,
    }
