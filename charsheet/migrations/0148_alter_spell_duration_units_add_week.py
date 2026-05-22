from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0147_item_not_buyable_item_not_sellable"),
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
