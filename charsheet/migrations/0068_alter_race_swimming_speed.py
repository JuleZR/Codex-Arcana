from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0067_alter_character_appearance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="race",
            name="swimming_speed",
            field=models.FloatField(default=0, validators=[MinValueValidator(0)]),
        ),
    ]
