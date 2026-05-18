from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0144_alter_charactertraitchoice_selected_derived_stat_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="weapon_maneuver_attribute_override",
            field=models.CharField(
                blank=True,
                choices=[
                    ("st", "Stärke"),
                    ("ge", "Geschicklichkeit"),
                    ("both", "Stärke oder Geschicklichkeit"),
                ],
                default="",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="weaponstats",
            name="maneuver_attribute_mode",
            field=models.CharField(
                choices=[
                    ("st", "Stärke"),
                    ("ge", "Geschicklichkeit"),
                    ("both", "Stärke oder Geschicklichkeit"),
                ],
                default="st",
                help_text="Welcher Attributsmodifikator für Waffenmanöver und Waffenwürfe gilt.",
                max_length=10,
            ),
        ),
    ]
