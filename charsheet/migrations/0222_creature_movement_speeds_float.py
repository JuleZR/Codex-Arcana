from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0221_remove_charactercreaturecard_uniq_character_creature_card_binding_legacy_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="charactercreature",
            name="combat_fly_speed_override",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="combat_speed_override",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="march_fly_speed_override",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="march_speed_override",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="sprint_fly_speed_override",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="charactercreature",
            name="sprint_speed_override",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="creature",
            name="combat_fly_speed",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="creature",
            name="combat_speed",
            field=models.FloatField(default=0, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="creature",
            name="march_fly_speed",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="creature",
            name="march_speed",
            field=models.FloatField(default=0, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="creature",
            name="sprint_fly_speed",
            field=models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="creature",
            name="sprint_speed",
            field=models.FloatField(default=0, validators=[MinValueValidator(0)]),
        ),
    ]
