from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ranker", "0014_backtestbatch_backtestbatchrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="bot",
            name="forward_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bot",
            name="last_forward_run_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="BotForwardRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("as_of", models.DateField()),
                ("equity", models.DecimalField(decimal_places=2, max_digits=20)),
                ("cash", models.DecimalField(decimal_places=2, max_digits=20)),
                ("positions_value", models.DecimalField(decimal_places=2, max_digits=20)),
                ("pnl", models.DecimalField(decimal_places=2, max_digits=20)),
                ("num_trades", models.IntegerField(default=0)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("bot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forward_runs", to="ranker.bot")),
            ],
            options={
                "ordering": ["bot", "as_of"],
                "unique_together": {("bot", "as_of")},
            },
        ),
    ]
