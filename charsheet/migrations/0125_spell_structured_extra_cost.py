from django.db import migrations, models


def migrate_extra_cost_to_structured(apps, schema_editor):
    connection = schema_editor.connection
    table = "charsheet_spell"
    with connection.cursor() as cursor:
        columns = {
            col.name
            for col in connection.introspection.get_table_description(cursor, table)
        }
        if "extra_cost" not in columns:
            return

        cursor.execute(
            f"""
            UPDATE {table}
            SET extra_cost_type = 'wound_grade',
                extra_cost_value = NULLIF(REGEXP_REPLACE(extra_cost, '\\D', '', 'g'), '')::smallint
            WHERE COALESCE(extra_cost, '') <> ''
              AND COALESCE(extra_cost_type, '') = ''
              AND extra_cost ~ '\\d'
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0124_spell_range_sight"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE charsheet_spell
                        ADD COLUMN IF NOT EXISTS extra_cost_type varchar(30) NOT NULL DEFAULT '';
                    """,
                    reverse_sql="""
                        ALTER TABLE charsheet_spell
                        DROP COLUMN IF EXISTS extra_cost_type;
                    """,
                ),
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE charsheet_spell
                        ADD COLUMN IF NOT EXISTS extra_cost_value smallint NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE charsheet_spell
                        DROP COLUMN IF EXISTS extra_cost_value;
                    """,
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE charsheet_spell DROP COLUMN IF EXISTS extra_cost",
                    reverse_sql="ALTER TABLE charsheet_spell ADD COLUMN IF NOT EXISTS extra_cost varchar(150) NOT NULL DEFAULT ''",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="spell",
                    name="extra_cost_type",
                    field=models.CharField(
                        blank=True,
                        choices=[("wound_grade", "Wundgrad")],
                        default="",
                        max_length=30,
                        verbose_name="Zusatzkosten-Art",
                    ),
                ),
                migrations.AddField(
                    model_name="spell",
                    name="extra_cost_value",
                    field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Zusatzkosten-Wert"),
                ),
                migrations.RemoveField(
                    model_name="spell",
                    name="extra_cost",
                ),
            ],
        ),
        migrations.RunPython(migrate_extra_cost_to_structured, migrations.RunPython.noop),
    ]
