from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0270_game_group_screen_inventory_is_collapsed"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroupcreature",
            name="character_creature",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="game_group_screen_cards",
                to="charsheet.charactercreature",
            ),
        ),
    ]
