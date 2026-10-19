from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ranker", "0024_tradesignal_is_test"),
    ]

    operations = [
        migrations.CreateModel(
            name="TradeExecutorHealth",
            fields=[
                ("singleton_id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("warming", "Warming up"), ("healthy", "Healthy"), ("degraded", "Degraded"), ("market_closed", "Market closed"), ("disabled", "Disabled")], default="warming", max_length=20)),
                ("entries_paused", models.BooleanField(default=True)),
                ("last_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("degraded_at", models.DateTimeField(blank=True, null=True)),
                ("recovered_at", models.DateTimeField(blank=True, null=True)),
                ("consecutive_failures", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=500)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Trade executor health",
                "verbose_name_plural": "Trade executor health",
            },
        ),
    ]
