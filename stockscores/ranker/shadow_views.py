"""Restricted shadow research endpoint, deliberately absent from public URLs."""

from decimal import Decimal

from django.db.models import Count
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ShadowSetup, ShadowEvent, TradeSignal, ShadowExecutorHealth
from .operator_auth import ResearchOperatorAuthentication
from .shadow import ShadowProposalSerializer, ShadowObservationSerializer, propose, observe
from .shadow_broker import execution_configured


def dashboard_record(s):
    events = list(s.events.order_by("-occurred_at", "-id")[:100])
    return {
        "id": s.id, "decision": s.decision, "decided_at": s.decided_at,
        "category": s.category, "rejection_reason": s.rejection_reason,
        "execution_mode": s.execution_mode, "status": s.status, "result": s.result,
        "entered_at": s.entered_at, "exited_at": s.exited_at,
        "reconciled_at": s.reconciled_at, "has_error": bool(s.last_error),
        "protection_kind": s.broker_protection_kind,
        "event_count": s.events.count(),
        "events": [{"kind": e.kind, "occurred_at": e.occurred_at, "details": e.details}
                   for e in reversed(events)],
    }


class StaffShadowDashboardView(APIView):
    """JWT staff report; deliberately has no proposal or order methods."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            if page < 1:
                raise ValueError
        except ValueError:
            return Response({"detail": "Invalid page"}, status=400)
        records = ShadowSetup.objects.order_by("-decided_at", "-id")
        mode = request.query_params.get("mode", "all")
        state = request.query_params.get("status", "all")
        if mode not in ("all", "observation", "broker_intended") or state not in (
                "all", *(code for code, _ in ShadowSetup.STATUS_CHOICES)):
            return Response({"detail": "Invalid filter"}, status=400)
        if mode != "all":
            records = records.filter(execution_mode=mode)
        if state != "all":
            records = records.filter(status=state)
        report = summary()
        rejection_groups = {}
        for s in ShadowSetup.objects.filter(status="completed").order_by("exited_at", "id"):
            if "realized_return_pct" not in s.result:
                continue
            key = (s.execution_mode, s.rejection_reason or "index_benchmark")
            rejection_groups.setdefault(key, []).append((s.exited_at, s.result["realized_return_pct"]))
        report["rejection_results"] = [
            {"mode": key[0], "reason": key[1], **_performance(values)}
            for key, values in rejection_groups.items()]
        latest = ShadowEvent.objects.filter(kind="observation").order_by("-occurred_at").first()
        report["last_observation_at"] = latest.occurred_at if latest else None
        # Raw exception strings may contain provider/configuration information.
        health = report["executor_health"]
        health["has_error"] = bool(health.pop("last_error", ""))
        count = records.count()
        return Response({"generated_at": timezone.now(), "summary": report,
                         "count": count, "page": page,
                         "next_page": page + 1 if page * 25 < count else None,
                         "results": [dashboard_record(s) for s in records[(page-1)*25:page*25]]},
                        headers={"Cache-Control": "private, no-store"})


class StaffShadowAccountView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from django.core.cache import cache
        from .shadow_broker import ShadowMarketDataClient, verify_account_identity
        cached = cache.get("staff-shadow-account-v1")
        if cached is not None:
            return Response(cached, headers={"Cache-Control": "private, no-store"})
        checked_at = timezone.now().isoformat()
        try:
            identity = verify_account_identity(require_enabled=False)
            client = ShadowMarketDataClient()
            positions = client._request("GET", f"{client.base_url}/v2/positions")
            orders = client._request("GET", f"{client.base_url}/v2/orders",
                                     params={"status": "open", "limit": 500})
            data = {"status": "verified", "checked_at": checked_at,
                    "account_suffix": identity[-4:], "flat": not positions and not orders,
                    "position_count": len(positions), "open_order_count": len(orders),
                    "positions": [{k: p.get(k) for k in ("symbol", "qty", "side", "asset_class")}
                                  for p in positions],
                    "orders": [{k: o.get(k) for k in ("symbol", "qty", "side", "status", "type")}
                               for o in orders]}
        except Exception:
            data = {"status": "unavailable", "checked_at": checked_at,
                    "detail": "Paper account verification failed. Inventory is unknown; inspect staff logs."}
        cache.set("staff-shadow-account-v1", data, 30)
        return Response(data, headers={"Cache-Control": "private, no-store"})


def _performance(records):
    """Chronological one-contract gross return; no substitution of peak gain."""
    returns = [Decimal(str(row[1])) for row in records]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value <= 0]
    equity = peak = Decimal("1")
    max_drawdown = Decimal("0")
    for value in returns:
        equity *= 1 + value / 100
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
    return {
        "sample_size": len(returns), "small_sample": len(returns) < 30,
        "win_rate_pct": str(Decimal(len(wins)) / len(returns) * 100) if returns else None,
        "average_win_pct": str(sum(wins) / len(wins)) if wins else None,
        "average_loss_pct": str(sum(losses) / len(losses)) if losses else None,
        "expectancy_pct": str(sum(returns) / len(returns)) if returns else None,
        "max_drawdown_pct": str(max_drawdown) if returns else None,
    }


def summary():
    setups = list(ShadowSetup.objects.order_by("exited_at", "id"))
    completed = [s for s in setups if s.status == "completed" and "realized_return_pct" in s.result]
    groups = {}
    for dimension in ("category", "rejection_reason", "execution_mode", "ruleset_version",
                      "market_regime", "direction", "symbol"):
        grouped = {}
        for setup in completed:
            value = setup.decision.get(dimension) if dimension in ("market_regime", "direction", "symbol") else getattr(setup, dimension)
            grouped.setdefault(value or "unspecified", []).append((setup.exited_at, setup.result["realized_return_pct"]))
        groups[dimension] = {key: _performance(values) for key, values in grouped.items()}
    first_decision = min((s.decided_at for s in setups), default=None)
    last_decision = max((s.decided_at for s in setups), default=None)
    published = []
    if first_decision and last_decision:
        published = [(s.closed_at, s.realized_return_pct) for s in TradeSignal.objects.filter(
            is_test=False, status="closed", published_at__gte=first_decision,
            published_at__lte=last_decision, closed_at__isnull=False,
            realized_return_pct__isnull=False).order_by("closed_at", "id")]
    status_counts = {row["status"]: row["n"] for row in ShadowSetup.objects.values("status").annotate(n=Count("id"))}
    health = ShadowExecutorHealth.objects.filter(singleton_id=1).first()
    return {
        "count": len(setups), "statuses": status_counts,
        "broker_executed": sum(s.result.get("result_type") == "broker" for s in completed),
        "observation_only": sum(s.execution_mode == "observation" for s in setups),
        "near_miss": sum(s.category == "near_miss" for s in setups),
        "index_benchmark": sum(s.category == "index" for s in setups),
        "data_completeness_pct": str(Decimal(sum(
            int(key in s.result and s.result[key] is not None)
            for s in completed for key in ("realized_return_pct", "mfe_pct", "mae_pct", "thesis_valid")
        )) / (len(completed) * 4) * 100) if completed else None,
        "shadow": _performance([(s.exited_at, s.result["realized_return_pct"]) for s in completed]),
        "published_same_decision_window": _performance(published),
        "comparison_limit": "Unmatched selected cohorts; no causal inference or significance claim.",
        "groups": groups,
        "executor_health": {"status": health.status, "checked_at": health.checked_at,
                            "last_error": health.last_error} if health else {"status": "never_started"},
        "execution_switch_enabled": execution_configured(),
    }


class ShadowResearchView(APIView):
    authentication_classes = [ResearchOperatorAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            limit = min(max(int(request.query_params.get("limit", 50)), 1), 100)
        except ValueError:
            return Response({"detail": "Invalid limit"}, status=400)
        records = ShadowSetup.objects.order_by("-decided_at")[:limit]
        return Response({"summary": summary(), "results": [
            {"id": s.id, "request_id": s.request_id, "decision": s.decision,
             "category": s.category, "rejection_reason": s.rejection_reason,
             "execution_mode": s.execution_mode, "status": s.status, "result": s.result,
             "events": list(s.events.order_by("occurred_at").values("kind", "occurred_at", "details", "broker_order_id"))}
            for s in records]})

    def post(self, request):
        serializer = ShadowProposalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            setup, replay = propose(serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"id": setup.id, "status": setup.status, "execution_mode": setup.execution_mode,
                         "already_applied": replay}, status=200 if replay else 201)


class ShadowObservationView(APIView):
    authentication_classes = [ResearchOperatorAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        serializer = ShadowObservationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            setup, replay = observe(pk, serializer.validated_data)
        except ShadowSetup.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response({"id": setup.id, "status": setup.status, "result": setup.result,
                         "already_applied": replay})


class ShadowCorrectionSerializer(serializers.Serializer):
    correction_id = serializers.RegexField(r"^[A-Za-z0-9._:-]{8,80}$")
    reason = serializers.CharField(min_length=10, max_length=1000)
    corrected_statement = serializers.CharField(min_length=10, max_length=2000)
    evidence_source = serializers.CharField(min_length=10, max_length=300)


class ShadowCorrectionView(APIView):
    authentication_classes = [ResearchOperatorAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        serializer = ShadowCorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            setup = ShadowSetup.objects.select_for_update().filter(pk=pk).first()
            if not setup:
                return Response({"detail": "Not found"}, status=404)
            details = serializer.validated_data
            previous = setup.events.filter(kind="correction", details__correction_id=details["correction_id"]).first()
            if previous:
                if previous.details != details:
                    return Response({"detail": "Conflicting correction replay"}, status=409)
                return Response({"id": previous.id, "already_applied": True})
            event = ShadowEvent.objects.create(setup=setup, kind="correction", occurred_at=timezone.now(), details=details)
            return Response({"id": event.id, "already_applied": False}, status=201)
