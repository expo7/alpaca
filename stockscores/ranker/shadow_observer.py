"""Read-only option sampling for observation-only shadow setups."""

from django.utils import timezone
from decimal import Decimal
import hashlib

from .models import ShadowSetup
from .shadow import ShadowObservationSerializer, observe
from .shadow_broker import ShadowMarketDataClient, verify_account_identity


def run_observation_cycle(*, client_factory=ShadowMarketDataClient, identity=verify_account_identity):
    # This path works with the execution kill switch off. It has no order methods.
    identity(require_enabled=False)
    client = client_factory()
    if not client.clock().get("is_open"):
        return {"status": "market_closed"}
    results = {}
    for setup in ShadowSetup.objects.filter(execution_mode="observation", status__in=("proposed", "waiting", "active")):
        try:
            d = setup.decision
            stock = client.stock_quote(d["symbol"])
            option = client.option_quote(d["option_symbol"])
            now = timezone.now()
            underlying = stock["midpoint"]
            trigger_price = Decimal(d["underlying_trigger_price"])
            trigger = underlying >= trigger_price if d["trigger_direction"] == "above" else underlying <= trigger_price
            if trigger and not setup.trigger_first_seen_at:
                setup.trigger_first_seen_at = now
                setup.save(update_fields=["trigger_first_seen_at"])
            if not trigger and setup.trigger_first_seen_at:
                setup.trigger_first_seen_at = None
                setup.save(update_fields=["trigger_first_seen_at"])
            confirmed = bool(trigger and setup.trigger_first_seen_at and
                             (now - setup.trigger_first_seen_at).total_seconds() >= int(d["confirmation_seconds"]))
            quote_at = option["timestamp"]
            quote_key = hashlib.sha256(f"{setup.pk}:{quote_at}".encode()).hexdigest()[:24]
            observation_id = f"quote-{setup.pk}-{quote_key}"
            if setup.events.filter(kind="observation", details__observation_id=observation_id).exists():
                results[str(setup.pk)] = setup.status
                continue
            invalidation = Decimal(d["underlying_invalidation"])
            level_valid = underlying > invalidation if d["direction"] == "bullish" else underlying < invalidation
            payload = {"observation_id": observation_id, "observed_at": now.isoformat(),
                       "quote_at": quote_at, "underlying_price": str(underlying),
                       "bid": str(option["bid"]), "ask": str(option["ask"]),
                       "confirmation_met": confirmed, "thesis_valid": level_valid,
                       "source": "Shadow Alpaca price-level observation"}
            serializer = ShadowObservationSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            updated, _ = observe(setup.pk, serializer.validated_data)
            results[str(setup.pk)] = updated.status
        except Exception:
            # No synthetic quote/fill when market data or state verification fails.
            results[str(setup.pk)] = "error"
    return {"status": "degraded" if "error" in results.values() else "ok", "setups": results}
