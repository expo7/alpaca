from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("ranker", "0025_tradeexecutorhealth")]

    operations = [
        migrations.CreateModel(
            name="TradeLifecycleCertification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("certified", "Certified"), ("discrepancy", "Discrepancy"), ("error", "Audit error")], db_index=True, default="pending", max_length=16)),
                ("lifecycle_certified", models.BooleanField(db_index=True, default=False)),
                ("checked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("certified_at", models.DateTimeField(blank=True, null=True)),
                ("checkpoints", models.JSONField(blank=True, default=dict)),
                ("discrepancy_codes", models.JSONField(blank=True, default=list)),
                ("discrepancy_details", models.JSONField(blank=True, default=list)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("signal", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="lifecycle_certification", to="ranker.tradesignal")),
            ],
            options={"ordering": ["-checked_at", "-id"]},
        ),
        migrations.CreateModel(
            name="OperationalTelegramAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("message", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent")], db_index=True, default="pending", max_length=12)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=500)),
                ("telegram_message_id", models.BigIntegerField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("signal", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operational_alerts", to="ranker.tradesignal")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
