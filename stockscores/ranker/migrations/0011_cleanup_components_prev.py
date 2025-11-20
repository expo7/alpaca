from django.db import migrations


def drop_components_prev(apps, schema_editor):
    table = "ranker_stockscore"
    column = "components_prev"
    cursor = schema_editor.connection.cursor()
    vendor = schema_editor.connection.vendor

    drop_sql = f'ALTER TABLE "{table}" DROP COLUMN "{column}"'
    drop_if_exists_sql = f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{column}"'

    if vendor == "sqlite":
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [row[1] for row in cursor.fetchall()]
            if column not in cols:
                return
        except Exception:
            return
        try:
            cursor.execute(drop_sql)
        except Exception:
            pass
    else:
        try:
            cursor.execute(drop_if_exists_sql)
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("ranker", "0010_alter_backtestrun_created_at_and_more"),
    ]

    operations = [
        migrations.RunPython(drop_components_prev, migrations.RunPython.noop),
    ]
