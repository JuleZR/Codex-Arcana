from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0122_spell_duration_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="spell",
            name="extra_cost_type",
            field=models.CharField(
                blank=True,
                choices=[("wound_grade", "Wundgrad")],
                default="",
                max_length=30,
                verbose_name="Zusatzkosten-Art",
            ),
        ),
        migrations.AddField(
            model_name="spell",
            name="extra_cost_value",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Zusatzkosten-Wert"),
        ),
    ]
