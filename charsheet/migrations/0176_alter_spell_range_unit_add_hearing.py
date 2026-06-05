from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0175_spell_ep_cost_label"),
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
                    ("Hörweite", "Hörweite"),
                    ("Berührung", "Berührung"),
                    ("selbst", "Selbst"),
                ],
                default="",
                max_length=20,
                verbose_name="Einheit",
            ),
        ),
    ]
