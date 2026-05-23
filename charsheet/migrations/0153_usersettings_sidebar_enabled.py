from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0152_divine_entity_symbol_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="sidebar_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
