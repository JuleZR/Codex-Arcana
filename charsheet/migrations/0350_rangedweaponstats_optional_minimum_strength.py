from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0349_weaponflag_mounted_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rangedweaponstats",
            name="minimum_strength",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]
