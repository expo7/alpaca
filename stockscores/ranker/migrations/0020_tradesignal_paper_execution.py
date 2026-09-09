from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ranker", "0019_tradesignal_execution_and_quotes")]

    operations = [
        migrations.AddField(model_name="tradesignal", name="paper_execution_enabled", field=models.BooleanField(default=False, help_text="Allow the globally enabled Alpaca paper executor to manage this signal.")),
        migrations.AddField(model_name="tradesignal", name="paper_quantity", field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name="tradesignal", name="paper_entry_order_id", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="tradesignal", name="paper_exit_order_id", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="tradesignal", name="paper_order_status", field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="tradesignal", name="paper_submitted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="paper_filled_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="paper_last_checked_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="paper_last_error", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="tradesignal", name="paper_exit_reason", field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="tradesignal", name="trigger_first_seen_at", field=models.DateTimeField(blank=True, null=True)),
    ]
