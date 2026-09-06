from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("ranker", "0017_analyticsevent")]

    operations = [
        migrations.CreateModel(
            name="TradeSignal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(db_index=True, max_length=16)),
                ("company_name", models.CharField(blank=True, default="", max_length=160)),
                ("instrument_type", models.CharField(choices=[("stock", "Stock"), ("call", "Call option"), ("put", "Put option")], default="stock", max_length=8)),
                ("strike", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("expiration", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published — waiting for entry"), ("open", "Open"), ("closed", "Closed"), ("cancelled", "Cancelled"), ("expired", "Expired")], db_index=True, default="draft", max_length=16)),
                ("risk_level", models.CharField(choices=[("low", "Low"), ("moderate", "Moderate"), ("high", "High")], default="moderate", max_length=12)),
                ("entry_low", models.DecimalField(decimal_places=2, max_digits=12)),
                ("entry_high", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("initial_stop", models.DecimalField(decimal_places=2, max_digits=12)),
                ("current_stop", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("target_1", models.DecimalField(decimal_places=2, max_digits=12)),
                ("target_2", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("target_3", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("actual_entry", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("final_exit", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("realized_return_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True)),
                ("max_return_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True)),
                ("thesis", models.TextField(help_text="Why this setup qualified when it was published.")),
                ("invalidation", models.TextField(blank=True, default="", help_text="What would prove the thesis wrong.")),
                ("evidence_tags", models.JSONField(blank=True, default=list, help_text='Examples: ["Price action", "News", "Sentiment"]')),
                ("published_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-published_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="TradeSignalUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("note", "Status note"), ("triggered", "Entry triggered"), ("target", "Target reached"), ("stop", "Stop changed"), ("partial_exit", "Partial exit"), ("closed", "Closed"), ("cancelled", "Cancelled")], default="note", max_length=20)),
                ("note", models.TextField()),
                ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("return_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True)),
                ("occurred_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("signal", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="updates", to="ranker.tradesignal")),
            ],
            options={"ordering": ["occurred_at", "id"]},
        ),
    ]
