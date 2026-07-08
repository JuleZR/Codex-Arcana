from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0228_creatureskill_deviation_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="creature",
            name="wound_thresholds_override",
            field=models.CharField(
                "Wundschwellen",
                blank=True,
                default="",
                help_text="Optionale exakte LP-Schwellen, kommasepariert, z. B. 2,4,8,10,12,15.",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="charactercreature",
            name="wound_thresholds_override",
            field=models.CharField(
                "Wundschwellen override",
                blank=True,
                default="",
                help_text="Optionale exakte LP-Schwellen, kommasepariert, z. B. 2,4,8,10,12,15.",
                max_length=100,
            ),
        ),
    ]
