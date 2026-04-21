from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0123_spell_extra_cost"),
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
