from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ranker", "0020_tradesignal_paper_execution"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stripe_customer_id", models.CharField(blank=True, default=None, max_length=64, null=True, unique=True)),
                ("stripe_subscription_id", models.CharField(blank=True, default=None, max_length=64, null=True, unique=True)),
                ("stripe_price_id", models.CharField(blank=True, default="", max_length=64)),
                ("status", models.CharField(blank=True, db_index=True, default="inactive", max_length=32)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="billing_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
