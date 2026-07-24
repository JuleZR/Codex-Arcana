from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0264_game_group_screen_note_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroupmembership",
            name="screen_is_collapsed",
            field=models.BooleanField(default=False),
        ),
    ]
