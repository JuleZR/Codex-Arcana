from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0227_creatureattack_append_notes_to_damage"),
    ]

    operations = [
        migrations.AddField(
            model_name="creatureskill",
            name="deviation",
            field=models.IntegerField("Abweichung", default=0),
        ),
        migrations.AddField(
            model_name="charactercreatureskill",
            name="deviation",
            field=models.IntegerField("Abweichung", default=0),
        ),
    ]
