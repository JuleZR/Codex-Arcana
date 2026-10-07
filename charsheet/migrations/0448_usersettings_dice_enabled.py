from django.db import migrations, models


def enable_existing_dice(apps, schema_editor):
    settings = apps.get_model("charsheet", "UserSettings")
    settings.objects.using(schema_editor.connection.alias).filter(
        dddice_enabled=True,
    ).update(dice_enabled=True)


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0447_remove_radial_menu_setting"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="dice_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(enable_existing_dice, migrations.RunPython.noop),
    ]
