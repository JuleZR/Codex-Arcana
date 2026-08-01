from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0323_remove_vampire_power_handler"),
    ]

    operations = [
        migrations.AddField(
            model_name="vampiretraitsemanticeffect",
            name="power_component",
            field=models.CharField(
                choices=[("power", "Power"), ("weakness", "Weakness")],
                default="power",
                help_text="For power effects: whether the effect belongs to the power or its weakness.",
                max_length=20,
            ),
        ),
    ]
