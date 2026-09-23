from django.db import migrations


def restore_expiry_timestamp(apps, schema_editor):
    Signal = apps.get_model("ranker", "TradeSignal")
    Update = apps.get_model("ranker", "TradeSignalUpdate")
    for signal in Signal.objects.filter(status="expired", closed_at__isnull=True).iterator():
        event = Update.objects.filter(signal_id=signal.pk, event_type="cancelled").order_by("occurred_at", "id").first()
        if event:
            # Preserve the recorded expiry event time; never fabricate an exit or return.
            Signal.objects.filter(pk=signal.pk, closed_at__isnull=True).update(closed_at=event.occurred_at)


class Migration(migrations.Migration):
    dependencies = [("ranker", "0027_tradesignalupdate_audience")]

    operations = [migrations.RunPython(restore_expiry_timestamp, migrations.RunPython.noop)]
