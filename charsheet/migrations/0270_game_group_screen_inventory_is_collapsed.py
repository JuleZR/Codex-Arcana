from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0269_game_group_creature_damage_tracks"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroup",
            name="screen_inventory_is_collapsed",
            field=models.BooleanField(default=False),
        ),
    ]
