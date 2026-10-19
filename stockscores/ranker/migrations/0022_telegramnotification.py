from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ranker", "0021_billingprofile"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tradesignalupdate",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("published", "Setup published"),
                    ("entry_submitted", "Entry order submitted"),
                    ("triggered", "Entry filled"),
                    ("protection_active", "Exit protection active"),
                    ("target", "Target reached"),
                    ("stop", "Stop changed"),
                    ("partial_exit", "Partial exit"),
                    ("exit_submitted", "Exit order submitted"),
                    ("closed", "Closed"),
                    ("cancelled", "Cancelled"),
                    ("execution_warning", "Execution warning"),
                    ("note", "Status note"),
                ],
                default="note",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="TelegramNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent")],
                    db_index=True,
                    default="pending",
                    max_length=12,
                )),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=500)),
                ("telegram_message_id", models.BigIntegerField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("update", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="telegram_notification",
                    to="ranker.tradesignalupdate",
                )),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
