from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0262_game_group_membership_screen_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_html",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="gamegroup",
            name="screen_note_position",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
