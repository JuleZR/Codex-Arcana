from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0096_weaponstats_damage_bonus_attribute_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE charsheet_character \
                        ADD COLUMN IF NOT EXISTS current_arcane_power integer NULL"
                    ),
                    reverse_sql=(
                        "ALTER TABLE charsheet_character \
                        DROP COLUMN IF EXISTS current_arcane_power"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="character",
                    name="current_arcane_power",
                    field=models.PositiveIntegerField(blank=True, null=True),
                ),
            ],
        ),
    ]
