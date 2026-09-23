"""Restricted research-task heartbeat; no broker or trade-record side effects."""

from datetime import datetime, time, timedelta, timezone as utc_timezone
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import OperationalTelegramAlert, ResearchRun


PHOENIX = ZoneInfo("America/Phoenix")
RUN_HOURS = (5, 7, 10, 12, 14)
GRACE = timedelta(minutes=20)


def scheduled_slots(start, end):
    day = start.astimezone(PHOENIX).date()
    final_day = end.astimezone(PHOENIX).date()
    while day <= final_day:
        if day.weekday() < 5:
            for hour in RUN_HOURS:
                slot = datetime.combine(day, time(hour, tzinfo=PHOENIX)).astimezone(utc_timezone.utc)
                if start <= slot <= end:
                    yield slot
        day += timedelta(days=1)


def is_scheduled_slot(value):
    local = value.astimezone(PHOENIX)
    return local.weekday() < 5 and local.hour in RUN_HOURS and local.minute == local.second == local.microsecond == 0


def next_slot(after):
    return next(scheduled_slots(after + timedelta(microseconds=1), after + timedelta(days=8)))


def run_state(run, now=None):
    now = now or timezone.now()
    if run.outcome == "failure":
        return "failed"
    if run.completed_at:
        return "fresh"
    return "overdue" if now > run.expected_run_at + GRACE else "fresh"


def run_payload(run, now=None):
    return {
        "expected_run_at": run.expected_run_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "session_type": run.session_type,
        "outcome": run.outcome,
        "market_regime": run.market_regime,
        "candidates_reviewed": run.candidates_reviewed,
        "operator_action": run.operator_action,
        "verified_result": run.verified_result,
        "error_summary": run.error_summary,
        "next_expected_run_at": run.next_expected_run_at or next_slot(run.expected_run_at),
        "status": run_state(run, now),
    }


def research_health(now=None):
    """Compute freshness even if the watchdog itself has missed a tick."""
    now = now or timezone.now()
    latest = ResearchRun.objects.exclude(request_id__isnull=True).order_by("-expected_run_at").first()
    if latest is None:
        return {"status": "awaiting_first_report", "next_expected_run_at": next_slot(now), "last_reported_at": None}
    expected = next_slot(latest.expected_run_at)
    status = ("overdue" if now > expected + GRACE else
              "failed" if latest.outcome == "failure" else "fresh")
    return {"status": status, "next_expected_run_at": expected, "last_reported_at": latest.completed_at}


def _alert(run, kind):
    OperationalTelegramAlert.objects.get_or_create(
        idempotency_key=f"research-run:{kind}:{run.expected_run_at:%Y%m%dT%H%MZ}",
        defaults={"signal": None, "message": (
            f"Quantelle research run {kind}: expected {run.expected_run_at:%Y-%m-%d %H:%M UTC}. "
            "Review the restricted research-run record and task availability."
        )},
    )


def report_run(data):
    """Only the authenticated operator view calls this after strict validation."""
    expected = data["expected_run_at"]
    with transaction.atomic():
        run, _ = ResearchRun.objects.select_for_update().get_or_create(expected_run_at=expected)
        fields = ("request_id", "started_at", "completed_at", "session_type", "outcome",
                  "market_regime", "candidates_reviewed", "operator_action", "verified_result", "error_summary")
        submitted = {key: data[key] for key in fields}
        if run.request_id:
            if all(getattr(run, key) == value for key, value in submitted.items()):
                return run, True
            raise ValueError("This scheduled run already has a different report")
        if ResearchRun.objects.filter(request_id=data["request_id"]).exclude(pk=run.pk).exists():
            raise ValueError("Request ID is already used by another run")
        for key, value in submitted.items():
            setattr(run, key, value)
        run.next_expected_run_at = next_slot(expected)
        run.save()
        if run.outcome == "failure":
            _alert(run, "failed")
        return run, False


def monitor_research_runs(now=None):
    """Detect a missing task run after the first authenticated heartbeat."""
    now = now or timezone.now()
    first = ResearchRun.objects.order_by("expected_run_at").first()
    if first is None:
        return {"status": "awaiting_first_report", "overdue": 0}
    start = max(first.expected_run_at, now - timedelta(days=30))
    overdue = 0
    for slot in scheduled_slots(start, now - GRACE):
        with transaction.atomic():
            run, _ = ResearchRun.objects.get_or_create(expected_run_at=slot,
                                                        defaults={"next_expected_run_at": next_slot(slot)})
            if run_state(run, now) == "overdue":
                overdue += 1
                _alert(run, "overdue")
    return {"status": "checked", "overdue": overdue, "next_expected_run_at": next_slot(now)}
