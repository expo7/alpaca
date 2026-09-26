from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ranker", "0033_alter_shadowsetup_status")]

    operations = [
        migrations.AlterField(
            model_name="telegramnotification",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("skipped", "Skipped")],
                db_index=True,
                default="pending",
                max_length=12,
            ),
        ),
    ]
