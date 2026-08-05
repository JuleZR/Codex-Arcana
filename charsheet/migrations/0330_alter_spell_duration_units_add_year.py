from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0329_creature_bp_and_age_cycle_switches"),
    ]

    operations = [
        migrations.AlterField(
            model_name="spell",
            name="duration_unit",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sofort", "Sofort"),
                    ("Runde", "Runde"),
                    ("Szene", "Szene"),
                    ("Konzentration", "Konzentration"),
                    ("permanent", "Permanent"),
                    ("Nacht", "Nacht"),
                    ("Tag", "Tag"),
                    ("Woche", "Woche"),
                    ("Jahr", "Jahr"),
                    ("Stunde", "Stunde"),
                    ("Minute", "Minute"),
                ],
                default="",
                max_length=20,
                verbose_name="Einheit",
            ),
        ),
        migrations.AlterField(
            model_name="spell",
            name="duration2_unit",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sofort", "Sofort"),
                    ("Runde", "Runde"),
                    ("Szene", "Szene"),
                    ("Konzentration", "Konzentration"),
                    ("permanent", "Permanent"),
                    ("Nacht", "Nacht"),
                    ("Tag", "Tag"),
                    ("Woche", "Woche"),
                    ("Jahr", "Jahr"),
                    ("Stunde", "Stunde"),
                    ("Minute", "Minute"),
                ],
                default="",
                max_length=20,
                verbose_name="Einheit 2",
            ),
        ),
    ]
