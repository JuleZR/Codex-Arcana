from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0200_shaman_card_blank_overrides"),
    ]

    operations = [
        migrations.AlterField(
            model_name="spell",
            name="extra_cost_type",
            field=models.CharField(
                blank=True,
                choices=[("wound_grade", "Wundgrad"), ("special", "spez.")],
                default="",
                max_length=30,
                verbose_name="Zusatzkosten-Art",
            ),
        ),
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
                    ("Stunde", "Stunde"),
                    ("Minute", "Minute"),
                ],
                default="",
                max_length=20,
                verbose_name="Einheit 2",
            ),
        ),
    ]
