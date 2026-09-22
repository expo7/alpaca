from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import TradeSignal, TradeSignalUpdate
from .alpaca_paper import PAPER_API_URL, load_paper_config
from .trade_quotes import apply_publication_snapshot


class TradeLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class LifecycleResult:
    signal: TradeSignal
    update: TradeSignalUpdate
    already_applied: bool = False


def publish_trade_signal(*, validated_data):
    """Publish one idempotent, paper-only setup for automated lifecycle management."""
    request_id = validated_data["request_id"]
    existing = TradeSignal.objects.filter(operator_request_id=request_id).first()
    if existing:
        update = existing.updates.filter(event_type="published").order_by("id").first()
        if not update:
            raise TradeLifecycleError("Existing operator publication has no publication event")
        return LifecycleResult(signal=existing, update=update, already_applied=True)

    config = load_paper_config()
    if not config.enabled:
        raise TradeLifecycleError("Publication blocked: Alpaca paper execution is disabled")
    if config.base_url != PAPER_API_URL:
        raise TradeLifecycleError("Publication blocked: executor is not configured for Alpaca paper trading")
    if not config.api_key or not config.secret_key:
        raise TradeLifecycleError("Publication blocked: Alpaca paper credentials are unavailable")

    values = dict(validated_data)
    values.pop("request_id")
    values.pop("paper_quantity", None)
    signal = TradeSignal(
        **values,
        operator_request_id=request_id,
        status=TradeSignal.STATUS_PUBLISHED,
        current_stop=values["initial_stop"],
        paper_execution_enabled=True,
        paper_quantity=1,
    )
    if not apply_publication_snapshot(signal):
        raise TradeLifecycleError("Publication blocked: a current quote snapshot is unavailable")
    quote_ask = signal.publication_option_ask
    if quote_ask is None or quote_ask > signal.do_not_chase_price:
        raise TradeLifecycleError("Publication blocked: option ask exceeds the do-not-chase price")
    max_spread = config.max_spread_pct
    spread = signal.publication_option_spread_pct
    if spread is None or spread > max_spread:
        raise TradeLifecycleError(f"Publication blocked: option spread exceeds {max_spread}%")
    signal.full_clean()

    with transaction.atomic():
        existing = TradeSignal.objects.select_for_update().filter(operator_request_id=request_id).first()
        if existing:
            update = existing.updates.filter(event_type="published").order_by("id").first()
            if not update:
                raise TradeLifecycleError("Existing operator publication has no publication event")
            return LifecycleResult(signal=existing, update=update, already_applied=True)
        signal.save()
        update = signal.updates.get(event_type="published")
        return LifecycleResult(signal=signal, update=update)


def cancel_pending_signal(*, signal_id, note, expected_status=TradeSignal.STATUS_PUBLISHED):
    """Atomically cancel an unfilled setup and create its customer-facing event."""
    clean_note = (note or "").strip()
    if len(clean_note) < 20:
        raise TradeLifecycleError("A customer-facing cancellation explanation is required")

    with transaction.atomic():
        try:
            signal = TradeSignal.objects.select_for_update().get(pk=signal_id)
        except TradeSignal.DoesNotExist as exc:
            raise TradeLifecycleError("Trade signal not found") from exc

        if signal.status == TradeSignal.STATUS_CANCELLED:
            existing = signal.updates.filter(event_type="cancelled").order_by("-occurred_at", "-id").first()
            if existing:
                return LifecycleResult(signal=signal, update=existing, already_applied=True)
            raise TradeLifecycleError("Signal is cancelled but has no cancellation event")
        if signal.status != expected_status:
            raise TradeLifecycleError(
                f"Refusing cancellation: expected status {expected_status}, found {signal.status}"
            )
        if signal.actual_entry is not None or signal.paper_entry_order_id:
            raise TradeLifecycleError("Refusing cancellation: the setup has an entry or broker order")

        signal.status = TradeSignal.STATUS_CANCELLED
        signal.paper_execution_enabled = False
        signal.trigger_first_seen_at = None
        signal.paper_last_error = ""
        signal.closed_at = timezone.now()
        signal.save(update_fields=[
            "status", "paper_execution_enabled", "trigger_first_seen_at",
            "paper_last_error", "closed_at", "updated_at",
        ])
        update = TradeSignalUpdate.objects.create(
            signal=signal,
            event_type="cancelled",
            note=clean_note,
        )
        return LifecycleResult(signal=signal, update=update)
