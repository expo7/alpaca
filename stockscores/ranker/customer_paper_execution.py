"""Independent one-contract paper mirror with durable, non-replayed order intent."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.db.models import Q
from django.core.cache import cache
import hashlib
from django.utils import timezone

from .alpaca_paper import PaperTradingError
from .customer_paper_broker import (
    CustomerBrokerError, CustomerPaperClient, account_lock, execution_enabled,
    flag, shared_option_quote,
)
from .models import CustomerPaperConnection, CustomerPaperExecution, CustomerPaperEvent, TradeSignal, OperationalTelegramAlert
from .protection_policy import desired_exit

TERMINAL = {"canceled", "expired", "rejected", "replaced", "done_for_day"}
ACTIVE = ("entry_intent", "entry_pending", "entry_cancel_pending", "open", "exit_intent", "exit_pending", "exit_cancel_pending")


def event(connection, kind, execution=None, **details):
    CustomerPaperEvent.objects.create(connection=connection, execution=execution, kind=kind, details=details)


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CustomerBrokerError("Alpaca returned an invalid numeric value.") from exc


def money(value):
    return number(value).quantize(Decimal("0.01"))


def worker_ready():
    return bool(cache.get("customer-paper-worker-heartbeat"))


def warn(row):
    if not row.last_error:
        return
    digest = hashlib.sha256(row.last_error.encode()).hexdigest()[:16]
    key = f"customer-paper:{row.pk}:{row.state}:{digest}"
    _, created = OperationalTelegramAlert.objects.get_or_create(idempotency_key=key,
        defaults={"message": f"Customer PAPER execution {row.pk} (connection {row.connection_id}) needs review: {row.last_error}. Inspect the admin paper ledger. House executions are separate."})
    if created:
        event(row.connection, "execution_warning", row, detail=row.last_error)


def entry_allowed(connection):
    return execution_enabled() and worker_ready() and connection.is_connected and connection.user.is_active and connection.trading_authorized and (
        connection.user.is_superuser or flag("CUSTOMER_PAPER_CUSTOMERS_ENABLED"))


def verified_account(connection, client):
    account = client.account()
    if account.get("id") != connection.alpaca_account_id:
        raise CustomerBrokerError("Paper account identity changed. Reconnect before trading.")
    return account


def preview(connection, signal, client=None):
    if not entry_allowed(connection):
        raise CustomerBrokerError("Customer paper entries are disabled, the customer worker is unavailable, or trading authorization is missing.")
    if signal.instrument_type not in ("call", "put") or not signal.strike or not signal.expiration:
        raise CustomerBrokerError("This workflow supports one long call or put contract.")
    if signal.status not in (TradeSignal.STATUS_PUBLISHED, TradeSignal.STATUS_OPEN) or not signal.paper_entry_order_id:
        raise CustomerBrokerError("The house workflow has not entered this signal.")
    if signal.status == TradeSignal.STATUS_PUBLISHED and signal.paper_order_status in TERMINAL:
        raise CustomerBrokerError("The house entry order is no longer active.")
    if connection.executions.filter(state__in=ACTIVE + ("attention",), last_error__gt="").exists():
        raise CustomerBrokerError("Resolve the existing customer execution warning before placing another entry.")
    today = timezone.localdate()
    if signal.expiration <= today or (signal.entry_deadline and signal.entry_deadline < today):
        raise CustomerBrokerError("This setup has passed its customer entry deadline.")
    if CustomerPaperExecution.objects.filter(connection=connection, signal=signal).exists():
        raise CustomerBrokerError("This signal already has a customer execution record.", code=409)
    if connection.executions.filter(state__in=ACTIVE + ("attention",)).count() >= connection.max_open_positions:
        raise CustomerBrokerError("Your customer position limit has been reached.")
    client = client or CustomerPaperClient(connection)
    account = verified_account(connection, client)
    if account.get("status") != "ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        raise CustomerBrokerError("Alpaca has blocked trading on this paper account.")
    if int(account.get("options_trading_level") or 0) < 2:
        raise CustomerBrokerError("This paper account needs options trading level 2 for long calls and puts.")
    if not client.clock().get("is_open"):
        raise CustomerBrokerError("The market is closed. Try during the regular trading session.")
    positions = client.positions()
    orders = client._request("GET", f"{client.base_url}/v2/orders", params={"status": "open", "limit": 500})
    if len(positions) >= connection.max_open_positions:
        raise CustomerBrokerError("The account already has its maximum number of positions.")
    if any(p.get("symbol") == signal.contract_symbol for p in positions) or any(o.get("symbol") == signal.contract_symbol for o in orders):
        raise CustomerBrokerError("This contract already has a position or open order in your paper account.")
    quote = shared_option_quote(signal.contract_symbol)
    price = money(quote["ask"])
    upper = signal.do_not_chase_price or signal.entry_high or signal.entry_low
    if price < signal.entry_low or price > upper or number(quote["spread_pct"]) > client.config.max_spread_pct:
        raise CustomerBrokerError("The current premium or spread is outside the published entry limits.")
    cost = price * 100
    if cost > connection.max_trade_notional or cost > number(account.get("options_buying_power", account.get("buying_power", "0"))):
        raise CustomerBrokerError("One contract exceeds your trade budget or options buying power.")
    stop = money(signal.current_stop or signal.initial_stop)
    target = money(signal.target_1)
    if not Decimal("0") < stop < price < target:
        raise CustomerBrokerError("The current entry does not fit the published stop and target.")
    return {"signal_id": signal.pk, "symbol": signal.contract_symbol, "quantity": 1,
            "limit_price": str(price), "estimated_cost": str(cost), "stop": str(stop),
            "target": str(target), "environment": "paper"}


def entry_client_id(row):
    return f"qc-{row.connection_id}-{row.signal_id}-entry"


def exit_client_id(row):
    return f"qc-{row.connection_id}-{row.signal_id}-exit-{row.exit_generation}"


def submit_intent(row, client, *, exiting=False):
    attempted = row.exit_attempted if exiting else row.entry_attempted
    client_id = exit_client_id(row) if exiting else entry_client_id(row)
    if attempted:
        order = client.find_order(client_id)
        if order is None:
            row.last_error = "Order outcome is unconfirmed; automatic resubmission is blocked."
            row.save(update_fields=["last_error", "updated_at"])
            return "unconfirmed"
    else:
        # Persist BEFORE HTTP, outside a transaction that could roll back on timeout.
        field = "exit_attempted" if exiting else "entry_attempted"
        setattr(row, field, True)
        row.save(update_fields=[field, "updated_at"])
        event(row.connection, "exit_attempt" if exiting else "entry_attempt", row, client_order_id=client_id)
        try:
            if not exiting:
                order = client.submit_limit_order(symbol=row.symbol, quantity=1, side="buy",
                    limit_price=row.entry_limit, client_order_id=client_id)
            elif row.exit_kind == "stop":
                order = client.submit_stop_order(symbol=row.symbol, quantity=row.filled_quantity,
                    stop_price=row.stop, client_order_id=client_id)
            elif row.exit_kind == "target":
                order = client.submit_limit_order(symbol=row.symbol, quantity=row.filled_quantity,
                    side="sell", limit_price=row.target, client_order_id=client_id, time_in_force="gtc")
            else:
                order = client.submit_market_order(symbol=row.symbol, quantity=row.filled_quantity,
                    side="sell", client_order_id=client_id)
        except CustomerBrokerError as exc:
            # Explicit throttling means no order accepted; do not treat a timeout that way.
            if exc.code == 429:
                setattr(row, field, False)
                row.save(update_fields=[field, "updated_at"])
            elif exc.code in (400, 401, 403, 404, 422):
                # Duplicate client-ID errors also use 422: reconcile before classifying.
                if exc.code == 422:
                    found = client.find_order(client_id)
                    if found:
                        return remember_order(row, found, exiting)
                row.state = "attention" if exiting else "rejected"
                row.last_error = str(exc)
                row.save(update_fields=["state", "last_error", "updated_at"])
            raise
    return remember_order(row, order, exiting)


def remember_order(row, order, exiting):
    if not isinstance(order.get("id"), str) or not order["id"]:
        raise CustomerBrokerError("Order acknowledgement is missing. Refresh to reconcile.")
    if exiting:
        row.exit_order_id = order["id"]
        row.state = "exit_pending"
    else:
        row.entry_order_id = order["id"]
        row.state = "entry_pending"
    row.order_status = str(order.get("status", "submitted"))[:32]
    row.last_error = ""
    row.save()
    event(row.connection, "order_acknowledged", row, phase="exit" if exiting else "entry", status=row.order_status)
    return row.state


def create_execution(connection, signal, *, source="manual", client=None):
    client = client or CustomerPaperClient(connection)
    plan = preview(connection, signal, client)
    row = CustomerPaperExecution.objects.create(connection=connection, signal=signal, source=source,
        symbol=plan["symbol"], entry_limit=plan["limit_price"], stop=plan["stop"], target=plan["target"])
    event(connection, "execution_created", row, source=source, quantity=1, limit_price=plan["limit_price"])
    try:
        submit_intent(row, client)
    except CustomerBrokerError as exc:
        row.refresh_from_db()
        row.last_error = str(exc)[:255]
        row.save(update_fields=["last_error", "updated_at"])
        warn(row)
        raise
    return row


def process_execution(row, client, *, entries_paused=False):
    row.checked_at = timezone.now()
    row.save(update_fields=["checked_at", "updated_at"])
    if row.state == "attention":
        positions = client.positions()
        if any(p.get("symbol") == row.symbol for p in positions):
            return "attention"
        if row.missing_position_since is None:
            row.missing_position_since = timezone.now()
            row.save()
            return "confirming_external_close"
        if row.missing_position_since > timezone.now() - timedelta(seconds=30):
            return "confirming_external_close"
        row.state = "closed_external"
        row.save()
        event(row.connection, "external_close", row)
        return row.state
    if row.state == "entry_intent":
        # An already-attempted POST must always be reconciled, even after opt-out.
        if entries_paused and not row.entry_attempted:
            row.state = "canceled"
            row.save()
            return "canceled"
        return submit_intent(row, client)
    if row.state in ("entry_pending", "entry_cancel_pending"):
        order = client.order(row.entry_order_id)
        status = order.get("status")
        row.order_status = str(status)[:32]
        filled = number(order.get("filled_qty", 0))
        if filled > 1 or filled < 0 or filled != filled.to_integral_value():
            raise CustomerBrokerError("Unexpected entry fill quantity. Manual reconciliation required.")
        expired = row.created_at < timezone.now() - timedelta(minutes=2)
        stop_entry = entries_paused or expired or row.signal.status not in ("published", "open")
        if status == "filled" and filled != 1:
            raise CustomerBrokerError("Unexpected filled order quantity. Manual reconciliation required.")
        if status == "filled" or (status in TERMINAL and filled > 0):
            row.filled_quantity = filled
            row.entry_fill = number(order.get("filled_avg_price"))
            row.state = "open"
            row.last_error = ""
            row.save()
            event(row.connection, "entry_filled", row, quantity=str(filled), price=str(row.entry_fill))
        elif status in TERMINAL:
            row.state = "canceled" if status != "rejected" else "rejected"
            row.save()
            return row.state
        elif stop_entry or filled:
            client.cancel_order(row.entry_order_id)
            row.state = "entry_cancel_pending"
            row.save()
            return row.state
        else:
            row.save()
            return "entry_pending"
    if row.state == "exit_intent":
        return submit_intent(row, client, exiting=True)
    if row.state in ("exit_pending", "exit_cancel_pending"):
        order = client.order(row.exit_order_id)
        row.order_status = str(order.get("status", ""))[:32]
        sold = number(order.get("filled_qty", 0))
        if sold == row.filled_quantity and sold > 0:
            row.exit_fill = number(order.get("filled_avg_price"))
            row.state = "closed"
            row.last_error = ""
            row.save()
            event(row.connection, "exit_filled", row, price=str(row.exit_fill), reason=row.exit_kind)
            return "closed"
        if sold:
            raise CustomerBrokerError("Unexpected partial customer exit. Inspect the account before continuing.")
        if row.order_status in TERMINAL:
            if row.order_status == "rejected":
                # Avoid repeatedly replacing rejected protection with new order IDs.
                row.state = "attention"
                row.last_error = "Alpaca rejected exit protection. Inspect the paper account."
                row.save()
                return "attention"
            row.exit_order_id = ""
            row.state = "open"
            row.save()
        elif row.state == "exit_cancel_pending":
            row.save()
            return row.state
    if row.state not in ("open", "exit_pending"):
        return row.state
    positions = client.positions()
    position = next((p for p in positions if p.get("symbol") == row.symbol), None)
    if position is None:
        if row.exit_order_id:
            # A fill may race order/position reads: confirm the order next pass.
            return "reconciling_exit"
        if row.missing_position_since is None:
            row.missing_position_since = timezone.now()
            row.save()
            return "confirming_position_inventory"
        if row.missing_position_since > timezone.now() - timedelta(seconds=30):
            return "confirming_position_inventory"
        row.state = "closed_external"
        row.last_error = "Position was closed outside Quantelle; no exit price is assumed."
        row.save()
        event(row.connection, "external_close", row)
        return row.state
    row.missing_position_since = None
    if number(position.get("qty")) != row.filled_quantity:
        raise CustomerBrokerError("Position quantity changed outside Quantelle. Exit submission is paused.")
    quote = shared_option_quote(row.symbol)
    bid = number(quote["bid"])
    stop = money(row.signal.current_stop or row.stop)
    row.stop = max(row.stop, stop)  # Follow tightened stops; never loosen protection.
    choice = desired_exit(bid=bid, stop=row.stop, target=row.target, currently_target=row.exit_kind == "target")
    if row.signal.status in ("closed", "cancelled", "expired"):
        choice = "market"
    if row.exit_order_id:
        changed_stop = row.exit_kind == "stop" and money(order.get("stop_price", row.stop)) != row.stop
        if choice == row.exit_kind and not changed_stop:
            row.last_error = ""
            row.save()
            return "protected"
        client.cancel_order(row.exit_order_id)
        row.state = "exit_cancel_pending"
        row.save()
        return row.state
    row.exit_kind = "market" if bid <= row.stop or choice == "market" else choice
    row.exit_generation += 1
    row.exit_attempted = False
    row.state = "exit_intent"
    row.save()
    return submit_intent(row, client, exiting=True)


@shared_task(name="ranker.customer_paper_execution.dispatch_customer_paper")
def dispatch_customer_paper():
    cache.set("customer-paper-worker-heartbeat", True, 45)
    # Reconciliation/exits survive the entry kill switch and customer opt-out.
    connections = CustomerPaperConnection.objects.filter(
        Q(mirror_enabled=True) | Q(executions__state__in=ACTIVE + ("attention",))).distinct()
    count = 0
    for pk in connections.values_list("pk", flat=True).iterator():
        run_customer_paper.delay(pk)
        count += 1
    return {"queued_accounts": count}


@shared_task(name="ranker.customer_paper_execution.run_customer_paper", queue="customer-paper", soft_time_limit=90, time_limit=110)
def run_customer_paper(connection_id):
    try:
        user_id = CustomerPaperConnection.objects.get(pk=connection_id).user_id
        with account_lock(user_id):
            connection = CustomerPaperConnection.objects.select_related("user").get(pk=connection_id)
            client = CustomerPaperClient(connection)
            verified_account(connection, client)
            connection.last_error = ""
            paused = not (entry_allowed(connection) and connection.mirror_enabled)
            # Existing positions first; one failed account/row cannot stop another.
            for row in connection.executions.select_related("signal").filter(state__in=ACTIVE + ("attention",)).order_by("created_at"):
                try:
                    process_execution(row, client, entries_paused=(not entry_allowed(connection) or (row.source == "mirror" and not connection.mirror_enabled)))
                except (PaperTradingError, KeyError, ValueError) as exc:
                    row.last_error = str(exc)[:255] if isinstance(exc, CustomerBrokerError) else "Customer execution needs another broker check."
                    row.save(update_fields=["last_error", "updated_at"])
                warn(row)
            if not paused and connection.consent_at and not connection.executions.filter(last_error__gt="", state__in=ACTIVE + ("attention",)).exists():
                now = timezone.now()
                # Mirror only fresh house entry submissions AFTER consent. No historical backfill.
                signals = TradeSignal.objects.filter(paper_execution_enabled=True,
                    status__in=("published", "open"), paper_submitted_at__gte=max(connection.consent_at, now-timedelta(seconds=120)),
                    paper_submitted_at__lte=now).exclude(paper_entry_order_id="")
                if not (connection.user.is_staff or connection.user.is_superuser):
                    signals = signals.filter(is_test=False)
                for signal in signals.order_by("paper_submitted_at", "pk"):
                    if not connection.executions.filter(signal=signal).exists():
                        try:
                            create_execution(connection, signal, source="mirror", client=client)
                        except (PaperTradingError, KeyError, ValueError) as exc:
                            connection.last_error = str(exc)[:255] if isinstance(exc, CustomerBrokerError) else "Mirror entry could not be evaluated."
                            connection.save(update_fields=["last_error", "updated_at"])
            connection.last_checked_at = timezone.now()
            connection.save(update_fields=["last_checked_at", "last_error", "updated_at"])
            return {"status": "checked", "connection_id": connection_id}
    except CustomerPaperConnection.DoesNotExist:
        return {"status": "disconnected"}
    except (PaperTradingError, KeyError, ValueError):
        CustomerPaperConnection.objects.filter(pk=connection_id).update(last_error="Paper account check failed or is temporarily busy.")
        return {"status": "unavailable", "connection_id": connection_id}
