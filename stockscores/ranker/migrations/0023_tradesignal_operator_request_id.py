from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ranker", "0022_telegramnotification")]

    operations = [
        migrations.AddField(
            model_name="tradesignal",
            name="operator_request_id",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
