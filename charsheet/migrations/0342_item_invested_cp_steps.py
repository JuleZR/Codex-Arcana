from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0341_alter_shieldstats_damage_dice_amount_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="invested_cp_steps",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optionale Beschreibung der CP-Schritte, z.B. 2/4/6/8/10.",
                max_length=200,
            ),
        ),
    ]
