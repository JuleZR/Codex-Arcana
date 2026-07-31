from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0305_daemonic_power_semantic_target"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="CreatureDaemonicPower",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "creature",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="daemonic_power_values",
                                to="charsheet.creature",
                            ),
                        ),
                        (
                            "power",
                            models.ForeignKey(
                                db_column="daemonicpower_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="base_creature_ownerships",
                                to="charsheet.daemonicpower",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Creature daemonic power",
                        "verbose_name_plural": "Creature daemonic powers",
                        "db_table": "charsheet_creature_daemonic_powers",
                        "ordering": [
                            "power__tier__sort_number",
                            "power__tier__name",
                            "power__name",
                            "id",
                        ],
                        "unique_together": {("creature", "power")},
                    },
                ),
            ],
        ),
        migrations.AddField(
            model_name="creaturedaemonicpower",
            name="level",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Level",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="creature",
                    name="daemonic_powers",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="base_creatures",
                        through="charsheet.CreatureDaemonicPower",
                        through_fields=("creature", "power"),
                        to="charsheet.daemonicpower",
                        verbose_name="Daemonic powers",
                    ),
                ),
            ],
        ),
    ]
