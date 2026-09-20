from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0396_kraftbestien_bindings"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="creaturesourcebinding",
            name="is_kraftbestie",
        ),
        migrations.AlterField(
            model_name="creaturesourcebinding",
            name="creature_type_filter",
            field=models.ForeignKey(
                blank=True,
                help_text="Optionale Vorlagenbeschraenkung im Auswahlmodus.",
                null=True,
                on_delete=models.PROTECT,
                related_name="source_bindings",
                to="charsheet.creaturetype",
            ),
        ),
        migrations.AddField(
            model_name="charactercreature",
            name="is_kraftbestie",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Diese gewaehlte Tier-Vorlage wird als Kraftbestie "
                    "berechnet."
                ),
                verbose_name="Kraftbestie",
            ),
        ),
    ]
