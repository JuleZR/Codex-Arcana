from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0191_weaponstats_h2_damage_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="usersettings",
            name="sidebar_enabled",
        ),
        migrations.AddField(
            model_name="usersettings",
            name="radial_menu_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
