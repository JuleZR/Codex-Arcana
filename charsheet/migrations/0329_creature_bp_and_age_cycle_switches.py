from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0328_vampire_power_multiple_levels"),
    ]

    operations = [
        migrations.AddField(
            model_name="creature",
            name="has_bp",
            field=models.BooleanField(default=False, verbose_name="Hat BP"),
        ),
        migrations.AddField(
            model_name="creature",
            name="has_age_cycle",
            field=models.BooleanField(default=False, verbose_name="Hat Alterszyklus"),
        ),
        migrations.AlterField(
            model_name="creature",
            name="vampire_age_cycle_default",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="Alterszyklus"),
        ),
        migrations.AlterField(
            model_name="creature",
            name="vampire_blood_capacity_override",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="BP-Override"),
        ),
    ]
