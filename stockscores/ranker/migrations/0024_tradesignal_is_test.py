from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ranker", "0023_tradesignal_operator_request_id")]

    operations = [
        migrations.AddField(
            model_name="tradesignal",
            name="is_test",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Operator test trade: execute and notify, but never expose in public records.",
            ),
        ),
    ]
