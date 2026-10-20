from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from zoneinfo import ZoneInfo
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .operator_auth import ResearchOperatorAuthentication
from .alpaca_paper import AlpacaPaperClient
from .models import OptionStrategy
from .option_strategies import publish, event, capability, ACTIVE, order_lookup


def management_session():
    """Use the same broker session as the manager, including holidays/early closes."""
    key = "quantelle-complex-display-session-v1"
    session = cache.get(key)
    if session is None:
        try:
            session = "open" if AlpacaPaperClient().clock()["is_open"] else "closed"
        except Exception:
            # An unavailable clock must never hide an overdue management check.
            return "unknown"
        cache.set(key, session, timeout=15)
    return session


def payload(row, internal=False):
    keys = ("id", "symbol", "kind", "legs", "thesis", "invalidation", "entry_limit", "entry_deadline",
            "close_by", "state", "stop_loss_dollars", "take_profit_dollars", "risk", "entry_fill",
            "exit_value", "realized_pl", "quote", "checked_at", "created_at")
    result = {k:getattr(row,k) for k in keys}
    result["protection"] = "Defined-risk legs and monitored whole-position exits; no broker-held complex stop"
    active = row.state in {"entering", "open", "closing"}
    session = management_session() if active else "inactive"
    now = timezone.now()
    # Allow one normal rotation after the opening bell before flagging overnight age.
    local = now.astimezone(ZoneInfo("America/New_York"))
    opening = local.replace(hour=9, minute=30, second=0, microsecond=0)
    opening_grace = session == "open" and timedelta(0) <= local - opening <= timedelta(seconds=120)
    stale = active and session != "closed" and not opening_grace and (not row.checked_at or now - row.checked_at > timedelta(seconds=120))
    result["management_session"] = session
    result["management_attention"] = bool(row.last_error) or stale
    result["management_stale"] = stale
    events = row.events.all().order_by("-id")[:15]
    result["events"] = [{"kind": e.kind, "at": e.created_at, "details": e.details,
                         "notification_status": e.notification_status} for e in events if internal or e.kind in {"published", "filled", "closed", "cancelled"}]
    if internal:
        result.update({k:getattr(row,k) for k in ("entry_order_id", "exit_order_id", "last_error", "order_status", "entry_attempted", "exit_attempted")})
    return result


class OptionStrategyList(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        rows = OptionStrategy.objects.order_by("-id")[:50]
        return Response({"strategies": [payload(row) for row in rows]})


class OptionStrategyOperator(APIView):
    authentication_classes = [ResearchOperatorAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            cap = capability(AlpacaPaperClient())
        except Exception as exc:
            cap = {"supported": False, "error": str(exc)[:255]}
        return Response({"capability": cap, "strategies": [payload(row, True) for row in OptionStrategy.objects.order_by("-id")[:50]]})

    def post(self, request):
        data = dict(request.data)
        action = data.pop("action", None)
        try:
            if action in {"strategy_publish", "strategy_preview"}:
                row, replay = publish(data, preview=action == "strategy_preview")
                if action == "strategy_preview":
                    return Response(dict(row, already_applied=False))
            elif action in {"strategy_close", "strategy_cancel", "strategy_retry"}:
                if set(data) != {"strategy_id", "note"} or not isinstance(data["strategy_id"], int) or not isinstance(data["note"], str) or len(data["note"].strip()) < 20:
                    raise ValueError("Lifecycle actions require strategy_id and a note of at least 20 characters")
                if not cache.add("quantelle-complex-executor", "operator", timeout=120):
                    raise ValueError("Strategy management is busy; retry after the current cycle")
                try:
                    with transaction.atomic():
                        row = OptionStrategy.objects.select_for_update().get(pk=data["strategy_id"])
                        if row.state not in ACTIVE:
                            return Response(dict(payload(row, True), already_applied=True))
                        if action == "strategy_cancel" and row.entry_fill is not None:
                            raise ValueError("Filled strategies require strategy_close")
                        if action == "strategy_retry":
                            if row.entry_fill is None:
                                if row.entry_order_id and row.state == "blocked":
                                    raise ValueError("Cancel the rejected setup and publish a newly reviewed strategy; do not reuse a terminal entry order")
                                row.entry_attempted = False
                                row.state = "entering" if row.entry_order_id else "pending"
                            else:
                                row.exit_attempted = False
                                row.close_requested = True
                                row.state = "open"
                        else:
                            row.close_requested = True
                            if row.state == "blocked":
                                row.state = "entering" if row.entry_order_id else "pending"
                        event(row, "operator", action=action, note=data["note"])
                        row.save()
                finally:
                    cache.delete("quantelle-complex-executor")
                replay = False
            else:
                raise ValueError("Unsupported strategy action")
            return Response(dict(payload(row, True), already_applied=replay))
        except OptionStrategy.DoesNotExist:
            return Response({"error": "Strategy not found"}, status=404)
        except Exception as exc:
            return Response({"error": str(exc)[:500]}, status=400)
