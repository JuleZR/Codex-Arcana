# Generated manually after Python launcher was unavailable.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0345_weapon_maneuver_attribute_none"),
    ]

    operations = [
        migrations.AddField(
            model_name="rangedweaponstats",
            name="flags",
            field=models.ManyToManyField(blank=True, to="charsheet.weaponflag"),
        ),
    ]
