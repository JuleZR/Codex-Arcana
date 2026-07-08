from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0226_creatureattack_show_notes_as_damage"),
    ]

    operations = [
        migrations.AddField(
            model_name="creatureattack",
            name="append_notes_to_damage",
            field=models.BooleanField(
                "Notes an Schaden anhaengen",
                default=False,
                help_text="Zeigt Notes auf der Kreaturenkarte zusaetzlich hinter dem automatisch berechneten Schaden.",
            ),
        ),
    ]
