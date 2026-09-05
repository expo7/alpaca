from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ranker", "0016_article"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalyticsEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("occurred_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("event_name", models.CharField(db_index=True, max_length=64)),
                ("path", models.CharField(blank=True, db_index=True, default="", max_length=512)),
                ("referrer_host", models.CharField(blank=True, default="", max_length=255)),
                ("visitor_hash", models.CharField(db_index=True, max_length=64)),
                ("device_type", models.CharField(blank=True, default="unknown", max_length=16)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analytics_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-occurred_at"]},
        ),
        migrations.AddIndex(
            model_name="analyticsevent",
            index=models.Index(fields=["event_name", "occurred_at"], name="ranker_anal_event_n_e6ae18_idx"),
        ),
        migrations.AddIndex(
            model_name="analyticsevent",
            index=models.Index(fields=["path", "occurred_at"], name="ranker_anal_path_072c1b_idx"),
        ),
    ]
