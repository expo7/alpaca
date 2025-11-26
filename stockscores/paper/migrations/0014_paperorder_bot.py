from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ranker", "0015_botforwardrun"),
        ("paper", "0013_cash_movement_risk_caps"),
    ]

    operations = [
        migrations.AddField(
            model_name="paperorder",
            name="bot",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                related_name="paper_orders",
                to="ranker.bot",
            ),
        ),
    ]
