import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0337_item_invested_cp"),
    ]

    operations = [
        migrations.AddField(
            model_name="shieldstats",
            name="damage_dice_amount",
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="damage_dice_faces",
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(2)]),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="damage_flat_bonus",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="damage_flat_operator",
            field=models.CharField(blank=True, choices=[("", "Kein Operator"), ("+", "+"), ("-", "-"), ("/", "/")], default="", max_length=1),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="damage_type",
            field=models.CharField(choices=[("B", "B"), ("T", "T")], default="T", max_length=1),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="maneuver_attribute_mode",
            field=models.CharField(
                choices=[("st", "StÃ¤rke"), ("ge", "Geschicklichkeit"), ("both", "StÃ¤rke oder Geschicklichkeit")],
                default="st",
                help_text="Welcher Attributsmodifikator fuer offensive Schildaktionen gilt.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="damage_source",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="charsheet.damagesource"),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="weapon_type",
            field=models.ForeignKey(
                blank=True,
                help_text="Regeltechnischer Waffentyp, falls dieser Schild offensiv gefuehrt werden kann.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="shield_stats",
                to="charsheet.weapontype",
            ),
        ),
        migrations.AddField(
            model_name="shieldstats",
            name="skills",
            field=models.ManyToManyField(
                blank=True,
                help_text="Alle Fertigkeiten, mit denen dieser Schild offensiv gefuehrt werden kann.",
                related_name="shield_stats",
                to="charsheet.skill",
            ),
        ),
    ]
