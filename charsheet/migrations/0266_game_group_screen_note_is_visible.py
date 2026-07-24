from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0265_game_group_membership_screen_is_collapsed"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_is_visible",
            field=models.BooleanField(default=True),
        ),
    ]
