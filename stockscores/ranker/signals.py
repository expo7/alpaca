from django.db.models.signals import post_save, pre_save
from django.db import transaction
from django.dispatch import receiver

from .models import TelegramNotification, TradeSignal, TradeSignalUpdate


TERMINAL_TRADE_STATUSES = {
    TradeSignal.STATUS_CLOSED,
    TradeSignal.STATUS_CANCELLED,
    TradeSignal.STATUS_EXPIRED,
}


@receiver(pre_save, sender=TradeSignal)
def remember_trade_publication_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._was_published = False
        return
    instance._was_published = sender.objects.filter(
        pk=instance.pk,
        published_at__isnull=False,
    ).exists()
    instance._previous_lifecycle_status = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()


@receiver(post_save, sender=TradeSignal)
def record_trade_publication(sender, instance, created, **kwargs):
    was_published = getattr(instance, "_was_published", False)
    is_published = instance.status != TradeSignal.STATUS_DRAFT and instance.published_at is not None
    if not is_published or was_published:
        return
    TradeSignalUpdate.objects.get_or_create(
        signal=instance,
        event_type="published",
        defaults={
            "note": "Quantelle published this trade setup. It is waiting for the entry trigger.",
            "occurred_at": instance.published_at,
        },
    )


@receiver(post_save, sender=TradeSignal)
def schedule_lifecycle_certification(sender, instance, created, **kwargs):
    if instance.status == TradeSignal.STATUS_DRAFT:
        return
    previous = getattr(instance, "_previous_lifecycle_status", None)
    if not created and previous == instance.status:
        return
    from .tasks import audit_trade_lifecycle
    transaction.on_commit(lambda: audit_trade_lifecycle.apply_async(args=[instance.pk], countdown=2))
    if instance.status in TERMINAL_TRADE_STATUSES:
        transaction.on_commit(lambda: audit_trade_lifecycle.apply_async(args=[instance.pk], countdown=120))


@receiver(post_save, sender=TradeSignalUpdate)
def create_telegram_outbox_entry(sender, instance, created, **kwargs):
    if created:
        TelegramNotification.objects.get_or_create(update=instance)
        from .tasks import audit_trade_lifecycle
        transaction.on_commit(lambda: audit_trade_lifecycle.apply_async(args=[instance.signal_id], countdown=3))
