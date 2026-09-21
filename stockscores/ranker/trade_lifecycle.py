from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import TradeSignal, TradeSignalUpdate


class TradeLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class LifecycleResult:
    signal: TradeSignal
    update: TradeSignalUpdate
    already_applied: bool = False


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

