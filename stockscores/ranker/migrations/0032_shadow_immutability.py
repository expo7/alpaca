from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION ranker_shadow_immutable() RETURNS trigger AS $$
            BEGIN
              IF TG_TABLE_NAME = 'ranker_shadowevent' THEN
                RAISE EXCEPTION 'shadow events are append-only';
              END IF;
              IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'shadow decisions cannot be deleted';
              END IF;
              IF OLD.research_run_id IS DISTINCT FROM NEW.research_run_id
                 OR OLD.request_id IS DISTINCT FROM NEW.request_id
                 OR OLD.decision IS DISTINCT FROM NEW.decision
                 OR OLD.contract_symbol IS DISTINCT FROM NEW.contract_symbol
                 OR OLD.category IS DISTINCT FROM NEW.category
                 OR OLD.rejection_reason IS DISTINCT FROM NEW.rejection_reason
                 OR OLD.execution_mode IS DISTINCT FROM NEW.execution_mode
                 OR OLD.ruleset_version IS DISTINCT FROM NEW.ruleset_version
                 OR OLD.decided_at IS DISTINCT FROM NEW.decided_at THEN
                RAISE EXCEPTION 'shadow decision is immutable';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        schema_editor.execute("CREATE TRIGGER shadow_setup_guard BEFORE UPDATE OR DELETE ON ranker_shadowsetup FOR EACH ROW EXECUTE FUNCTION ranker_shadow_immutable()")
        schema_editor.execute("CREATE TRIGGER shadow_event_guard BEFORE UPDATE OR DELETE ON ranker_shadowevent FOR EACH ROW EXECUTE FUNCTION ranker_shadow_immutable()")
    elif vendor == "sqlite":
        immutable = ("research_run_id", "request_id", "decision", "contract_symbol", "category", "rejection_reason",
                     "execution_mode", "ruleset_version", "decided_at")
        condition = " OR ".join(f"OLD.{name} IS NOT NEW.{name}" for name in immutable)
        schema_editor.execute(f"CREATE TRIGGER shadow_setup_guard BEFORE UPDATE ON ranker_shadowsetup WHEN {condition} BEGIN SELECT RAISE(ABORT, 'shadow decision is immutable'); END")
        schema_editor.execute("CREATE TRIGGER shadow_setup_delete_guard BEFORE DELETE ON ranker_shadowsetup BEGIN SELECT RAISE(ABORT, 'shadow decisions cannot be deleted'); END")
        schema_editor.execute("CREATE TRIGGER shadow_event_update_guard BEFORE UPDATE ON ranker_shadowevent BEGIN SELECT RAISE(ABORT, 'shadow events are append-only'); END")
        schema_editor.execute("CREATE TRIGGER shadow_event_delete_guard BEFORE DELETE ON ranker_shadowevent BEGIN SELECT RAISE(ABORT, 'shadow events are append-only'); END")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS shadow_event_guard ON ranker_shadowevent")
        schema_editor.execute("DROP TRIGGER IF EXISTS shadow_setup_guard ON ranker_shadowsetup")
        schema_editor.execute("DROP FUNCTION IF EXISTS ranker_shadow_immutable()")
    elif schema_editor.connection.vendor == "sqlite":
        for name in ("shadow_setup_guard", "shadow_setup_delete_guard", "shadow_event_update_guard", "shadow_event_delete_guard"):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [("ranker", "0031_shadowexecutorhealth_and_more")]
    operations = [migrations.RunPython(install, uninstall)]
