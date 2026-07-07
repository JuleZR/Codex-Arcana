from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0224_repair_creature_swimming_speed_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="creature",
            name="movement_mana_cost",
            field=models.PositiveSmallIntegerField(
                "Bewegungs-Mana",
                blank=True,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="creature",
            name="movement_note",
            field=models.CharField("Bewegungshinweis", blank=True, default="", max_length=200),
        ),
    ]
