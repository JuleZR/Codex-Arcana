from django.db import migrations, models
import django.db.models.deletion

from charsheet.constants import WEAPON_MANEUVER_ATTRIBUTE_CHOICES, WEAPON_MANEUVER_ATTRIBUTE_NONE


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0347_alter_weaponflag_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="rangedweaponstats",
            name="damage_label",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AlterField(
            model_name="rangedweaponstats",
            name="maneuver_attribute_mode",
            field=models.CharField(
                choices=WEAPON_MANEUVER_ATTRIBUTE_CHOICES,
                default=WEAPON_MANEUVER_ATTRIBUTE_NONE,
                help_text="Welcher Attributsmodifikator fuer Fernkampf-Manoever und Waffenwuerfe gilt.",
                max_length=10,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="rangedweaponstats",
                    name="damage_source",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="charsheet.damagesource",
                    ),
                ),
                migrations.RunSQL(
                    sql="UPDATE charsheet_rangedweaponstats SET damage_source_id = NULL;",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="rangedweaponstats",
                    name="damage_source",
                ),
            ],
        ),
    ]
