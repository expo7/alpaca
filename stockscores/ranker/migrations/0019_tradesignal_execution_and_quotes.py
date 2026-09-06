from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ranker", "0018_tradesignal_tradesignalupdate")]

    operations = [
        migrations.AddField(model_name="tradesignal", name="trigger_direction", field=models.CharField(choices=[("above", "Trades above"), ("below", "Trades below")], default="above", max_length=8)),
        migrations.AddField(model_name="tradesignal", name="underlying_trigger_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="tradesignal", name="trigger_confirmation", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="tradesignal", name="do_not_chase_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="tradesignal", name="entry_deadline", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="official_fill_method", field=models.CharField(choices=[("ask", "Ask at activation (conservative)"), ("midpoint", "Bid/ask midpoint at activation")], default="ask", max_length=12)),
        migrations.AddField(model_name="tradesignal", name="publication_underlying_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_option_bid", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_option_ask", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_option_midpoint", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_option_spread_pct", field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_option_volume", field=models.PositiveBigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_option_open_interest", field=models.PositiveBigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_quote_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="tradesignal", name="publication_quote_source", field=models.CharField(blank=True, default="", max_length=80)),
    ]
