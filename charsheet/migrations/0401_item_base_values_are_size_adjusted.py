from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "charsheet",
            "0400_alter_charactercreaturetraitchoice_"
            "selected_derived_stat_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="base_values_are_size_adjusted",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Aktivieren, wenn Gewicht und Preis bereits fuer die "
                    "konfigurierte Groessenklasse angegeben sind."
                ),
            ),
        ),
    ]
