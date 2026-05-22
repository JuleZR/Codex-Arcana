from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0148_alter_spell_duration_units_add_week"),
    ]

    operations = [
        migrations.AlterField(
            model_name="spell",
            name="range_unit",
            field=models.CharField(
                blank=True,
                choices=[
                    ("m", "Meter"),
                    ("km", "Kilometer"),
                    ("km²", "Quadratkilometer"),
                    ("Sichtweite", "Sichtweite"),
                    ("Berührung", "Berührung"),
                    ("selbst", "Selbst"),
                ],
                default="",
                max_length=20,
                verbose_name="Einheit",
            ),
        ),
    ]
