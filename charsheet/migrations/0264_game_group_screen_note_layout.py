from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0263_game_group_screen_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_is_detached",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_is_wide",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_x",
            field=models.PositiveIntegerField(default=24),
        ),
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_y",
            field=models.PositiveIntegerField(default=24),
        ),
    ]
