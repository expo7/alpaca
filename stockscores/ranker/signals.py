from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import TelegramNotification, TradeSignal, TradeSignalUpdate


@receiver(pre_save, sender=TradeSignal)
def remember_trade_publication_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._was_published = False
        return
    instance._was_published = sender.objects.filter(
        pk=instance.pk,
        published_at__isnull=False,
    ).exists()


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


@receiver(post_save, sender=TradeSignalUpdate)
def create_telegram_outbox_entry(sender, instance, created, **kwargs):
    if created:
        TelegramNotification.objects.get_or_create(update=instance)
