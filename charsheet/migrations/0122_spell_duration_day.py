from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0121_spell_cast_time2"),
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
                    ("Stunde", "Stunde"),
                    ("Minute", "Minute"),
                ],
                default="",
                max_length=20,
                verbose_name="Einheit 2",
            ),
        ),
    ]
