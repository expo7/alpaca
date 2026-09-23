import html
from datetime import timedelta
from zoneinfo import ZoneInfo

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OperationalTelegramAlert, TelegramNotification

EASTERN = ZoneInfo("America/New_York")

EVENT_HEADINGS = {
    "published": ("📣", "New Trade Setup"),
    "entry_submitted": ("⏳", "Entry Order Submitted"),
    "triggered": ("🟢", "Entry Filled"),
    "protection_active": ("🛡️", "Exit Protection Active"),
    "target": ("🎯", "Target Reached"),
    "stop": ("🔒", "Stop Updated"),
    "partial_exit": ("💵", "Partial Exit"),
    "exit_submitted": ("⏳", "Exit Order Submitted"),
    "closed": ("🏁", "Trade Closed"),
    "cancelled": ("🚫", "Setup Cancelled"),
    "execution_warning": ("⚠️", "Execution Warning"),
    "note": ("ℹ️", "Trade Update"),
}


def _money(value):
    return f"${value:,.2f}" if value is not None else None


def _line(label, value):
    if value in (None, ""):
        return None
    return f"<b>{html.escape(label)}:</b> {html.escape(str(value))}"


def format_trade_update(update):
    signal = update.signal
    emoji, heading = EVENT_HEADINGS.get(update.event_type, EVENT_HEADINGS["note"])
    occurred = timezone.localtime(update.occurred_at, EASTERN).strftime("%b %-d, %Y · %-I:%M:%S %p ET")

    lines = [
        f"<b>{emoji} {html.escape(heading)} · {html.escape(signal.display_instrument)}</b>",
        _line("Status", signal.get_status_display()),
    ]
    if signal.is_test:
        lines.insert(0, "<b>🧪 TEST TRADE — NOT A PUBLIC QUANTELLE SIGNAL</b>")
    if update.price is not None:
        price_label = "Fill" if update.event_type == "triggered" else "Price"
        lines.append(_line(price_label, _money(update.price)))
    if update.return_pct is not None:
        lines.append(_line("Return", f"{update.return_pct:+.2f}%"))

    if update.event_type == "published":
        trigger = _money(signal.underlying_trigger_price)
        if trigger:
            lines.append(_line("Trigger", f"{signal.trigger_direction} {trigger}"))
        entry = _money(signal.entry_low)
        if signal.entry_high is not None:
            entry = f"{entry}–{_money(signal.entry_high)}"
        lines.extend([
            _line("Entry", entry),
            _line("Stop", _money(signal.current_stop or signal.initial_stop)),
            _line("Target", _money(signal.target_1)),
            _line("Risk", signal.get_risk_level_display()),
        ])
    elif update.event_type in {"triggered", "protection_active", "stop", "target", "partial_exit"}:
        lines.extend([
            _line("Stop", _money(signal.current_stop or signal.initial_stop)),
            _line("Target", _money(signal.target_1)),
        ])

    lines.extend([
        _line("Time", occurred),
        html.escape(update.note),
    ])
    if not signal.is_test:
        lines.append(f'<a href="https://quantelle.io/signals#trade-{signal.pk}">View this trade on Quantelle</a>')
    return "\n".join(line for line in lines if line)


def _telegram_configured():
    return bool(
        settings.TELEGRAM_NOTIFICATIONS_ENABLED
        and settings.TELEGRAM_BOT_TOKEN
        and settings.TELEGRAM_CHAT_ID
    )


@shared_task(bind=True, name="ranker.deliver_telegram_notification", max_retries=5)
def deliver_telegram_notification(self, notification_id):
    if not _telegram_configured():
        return {"status": "disabled"}

    with transaction.atomic():
        notification = (
            TelegramNotification.objects.select_for_update()
            .select_related("update__signal")
            .get(pk=notification_id)
        )
        if notification.update.audience != "customer":
            return {"status": "staff_only"}
        if notification.status == TelegramNotification.STATUS_SENT:
            return {"status": "already_sent"}
        if notification.status == TelegramNotification.STATUS_SENDING:
            return {"status": "already_sending"}
        notification.status = TelegramNotification.STATUS_SENDING
        notification.attempt_count += 1
        notification.last_error = ""
        notification.save(update_fields=["status", "attempt_count", "last_error", "updated_at"])

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": format_trade_update(notification.update),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description") or "Telegram rejected the message")
    except Exception as exc:
        TelegramNotification.objects.filter(pk=notification_id).update(
            status=TelegramNotification.STATUS_PENDING,
            last_error=str(exc)[:500],
            updated_at=timezone.now(),
        )
        countdown = min(300, 2 ** min(notification.attempt_count, 8))
        raise self.retry(exc=exc, countdown=countdown)

    TelegramNotification.objects.filter(pk=notification_id).update(
        status=TelegramNotification.STATUS_SENT,
        telegram_message_id=payload.get("result", {}).get("message_id"),
        sent_at=timezone.now(),
        last_error="",
        updated_at=timezone.now(),
    )
    return {"status": "sent", "message_id": payload.get("result", {}).get("message_id")}


@shared_task(name="ranker.deliver_pending_telegram_notifications")
def deliver_pending_telegram_notifications(limit=25):
    if not _telegram_configured():
        return {"status": "disabled", "queued": 0}

    stale_before = timezone.now() - timedelta(minutes=5)
    notification_ids = list(
        TelegramNotification.objects.filter(
            status=TelegramNotification.STATUS_PENDING,
            update__audience="customer",
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
    stale_ids = list(
        TelegramNotification.objects.filter(
            status=TelegramNotification.STATUS_SENDING,
            update__audience="customer",
            updated_at__lt=stale_before,
        )
        .exclude(id__in=notification_ids)
        .order_by("updated_at")
        .values_list("id", flat=True)[: max(0, limit - len(notification_ids))]
    )
    if stale_ids:
        TelegramNotification.objects.filter(id__in=stale_ids).update(
            status=TelegramNotification.STATUS_PENDING,
            updated_at=timezone.now(),
        )
    notification_ids.extend(stale_ids)
    for notification_id in notification_ids:
        deliver_telegram_notification.delay(notification_id)
    operational_ids = list(
        OperationalTelegramAlert.objects.filter(status=OperationalTelegramAlert.STATUS_PENDING)
        .order_by("created_at").values_list("id", flat=True)[:limit]
    )
    for alert_id in operational_ids:
        deliver_operational_telegram_alert.delay(alert_id)
    return {"status": "ok", "queued": len(notification_ids), "operational_queued": len(operational_ids)}


@shared_task(bind=True, name="ranker.deliver_operational_telegram_alert", max_retries=5)
def deliver_operational_telegram_alert(self, alert_id):
    if not _telegram_configured():
        return {"status": "disabled"}
    with transaction.atomic():
        alert = OperationalTelegramAlert.objects.select_for_update().get(pk=alert_id)
        if alert.status == OperationalTelegramAlert.STATUS_SENT:
            return {"status": "already_sent"}
        if alert.status == OperationalTelegramAlert.STATUS_SENDING:
            return {"status": "already_sending"}
        alert.status = OperationalTelegramAlert.STATUS_SENDING
        alert.attempt_count += 1
        alert.last_error = ""
        alert.save(update_fields=["status", "attempt_count", "last_error", "updated_at"])
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": alert.message, "disable_web_page_preview": True},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description") or "Telegram rejected the message")
    except Exception as exc:
        OperationalTelegramAlert.objects.filter(pk=alert_id).update(
            status=OperationalTelegramAlert.STATUS_PENDING,
            last_error=str(exc)[:500],
            updated_at=timezone.now(),
        )
        raise self.retry(exc=exc, countdown=min(300, 2 ** min(alert.attempt_count, 8)))
    OperationalTelegramAlert.objects.filter(pk=alert_id).update(
        status=OperationalTelegramAlert.STATUS_SENT,
        telegram_message_id=payload.get("result", {}).get("message_id"),
        sent_at=timezone.now(),
        last_error="",
        updated_at=timezone.now(),
    )
    return {"status": "sent", "message_id": payload.get("result", {}).get("message_id")}
