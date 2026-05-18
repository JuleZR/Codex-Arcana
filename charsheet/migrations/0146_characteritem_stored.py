from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0145_weapon_maneuver_attribute_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="stored",
            field=models.BooleanField(default=False),
        ),
    ]
