from django.db import migrations, models


def classify_guardian_history(apps, schema_editor):
    Update = apps.get_model("ranker", "TradeSignalUpdate")
    # These exact prefixes were emitted by the old Guardian transition writer.
    # Preserve the immutable rows and any already-sent outbox history.
    for prefix in (
        "Execution protection degraded; new entries are paused",
        "Execution protection recovered; monitored exits stayed active",
        "Paper execution error:",
    ):
        Update.objects.filter(note__startswith=prefix).update(audience="staff")


class Migration(migrations.Migration):
    dependencies = [("ranker", "0026_lifecycle_certification")]

    operations = [
        migrations.AddField(
            model_name="tradesignalupdate",
            name="audience",
            field=models.CharField(choices=[("customer", "Customer"), ("staff", "Staff")], db_index=True, default="customer", max_length=8),
        ),
        migrations.RunPython(classify_guardian_history, migrations.RunPython.noop),
    ]
