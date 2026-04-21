from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0120_alter_spell_kp_cost"),
    ]

    operations = [
        migrations.AddField(
            model_name="spell",
            name="cast_time2_number",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Zeitaufwand 2"),
        ),
        migrations.AddField(
            model_name="spell",
            name="cast_time2_unit",
            field=models.CharField(
                blank=True,
                choices=[("Aktion", "Aktion"), ("Minute", "Minute"), ("Stunde", "Stunde")],
                default="",
                max_length=20,
                verbose_name="Einheit 2",
            ),
        ),
    ]
