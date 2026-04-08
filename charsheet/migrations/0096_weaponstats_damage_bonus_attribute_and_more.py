from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0094_add_weapon_damage_operators"),
    ]

    operations = [
        migrations.AddField(
            model_name="weaponstats",
            name="damage_bonus_attribute",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="weaponstats",
            name="damage_bonus_mode",
            field=models.CharField(blank=True, default="flat", max_length=20),
        ),
    ]
