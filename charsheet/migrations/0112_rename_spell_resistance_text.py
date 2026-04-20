from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0111_school_panel_symbol"),
    ]

    operations = [
        migrations.RenameField(
            model_name="spell",
            old_name="resistance_text",
            new_name="resistance_value",
        ),
        migrations.AlterField(
            model_name="spell",
            name="resistance_value",
            field=models.CharField(
                blank=True,
                default="",
                max_length=100,
                verbose_name="Widerstandswert",
            ),
        ),
        migrations.AddField(
            model_name="spell",
            name="mw",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="MW",
            ),
        ),
    ]
