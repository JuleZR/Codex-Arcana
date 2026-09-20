from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0402_country_language_origins"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="is_npc",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="character",
            name="used_experience",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactercreationdraft",
            name="is_npc",
            field=models.BooleanField(default=False),
        ),
    ]
