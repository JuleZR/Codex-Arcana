from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0327_semantic_effect_creature_card_grants"),
    ]

    operations = [
        migrations.AddField(
            model_name="vampirepower",
            name="can_be_learned_multiple_times",
            field=models.BooleanField(
                default=False,
                help_text="Allows this power to be purchased in multiple ranks.",
            ),
        ),
        migrations.AddField(
            model_name="charactervampirepower",
            name="level",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="creaturevampirepower",
            name="level",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="charactercreaturevampirepower",
            name="level",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gamegroupcreaturevampirepower",
            name="level",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
