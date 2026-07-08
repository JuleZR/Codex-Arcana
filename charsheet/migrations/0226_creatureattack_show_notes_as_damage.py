from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0225_creature_movement_mana_cost_and_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="creatureattack",
            name="show_notes_as_damage",
            field=models.BooleanField(
                "Notes ersetzen Schaden",
                default=False,
                help_text="Zeigt Notes auf der Kreaturenkarte statt des automatisch berechneten Schadens.",
            ),
        ),
    ]
