from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0223_creature_march_swimming_speed_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE charsheet_creature
                    ADD COLUMN IF NOT EXISTS combat_swimming_speed double precision NULL;
                ALTER TABLE charsheet_creature
                    ADD COLUMN IF NOT EXISTS march_swimming_speed double precision NULL;
                ALTER TABLE charsheet_creature
                    ADD COLUMN IF NOT EXISTS sprint_swimming_speed double precision NULL;
                ALTER TABLE charsheet_creature
                    ALTER COLUMN swimming_speed DROP DEFAULT;
                UPDATE charsheet_creature
                SET
                    combat_swimming_speed = COALESCE(combat_swimming_speed, swimming_speed),
                    march_swimming_speed = COALESCE(march_swimming_speed, swimming_speed),
                    sprint_swimming_speed = COALESCE(sprint_swimming_speed, swimming_speed)
                WHERE swimming_speed IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
