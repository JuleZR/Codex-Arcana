# Generated manually after Python launcher was unavailable.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0343_shieldstats_parade_bonus"),
    ]

    operations = [
        migrations.CreateModel(
            name="RangedWeaponStats",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("damage_dice_amount", models.PositiveIntegerField(default=1)),
                ("damage_dice_faces", models.PositiveIntegerField(default=10)),
                ("damage_flat_bonus", models.IntegerField(default=0)),
                (
                    "damage_flat_operator",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "Kein Operator"),
                            ("+", "+"),
                            ("-", "-"),
                            ("/", "/"),
                        ],
                        default="",
                        max_length=1,
                    ),
                ),
                (
                    "damage_type",
                    models.CharField(
                        choices=[
                            ("B", "B"),
                            ("T", "T"),
                        ],
                        default="T",
                        max_length=1,
                    ),
                ),
                (
                    "maneuver_attribute_mode",
                    models.CharField(choices=[("st", "Stärke"), ("ge", "Geschicklichkeit"), ("both", "Stärke oder Geschicklichkeit")], default="st", help_text="Welcher Attributsmodifikator fuer Fernkampf-Manoever und Waffenwuerfe gilt.", max_length=10),
                ),
                (
                    "range_short",
                    models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)]),
                ),
                (
                    "range_medium",
                    models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)]),
                ),
                (
                    "range_long",
                    models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)]),
                ),
                ("range_strength_multiplier", models.BooleanField(default=False)),
                (
                    "reload_time",
                    models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)]),
                ),
                (
                    "shots",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "minimum_strength",
                    models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)]),
                ),
                (
                    "damage_source",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="charsheet.damagesource"),
                ),
                (
                    "item",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="charsheet.item"),
                ),
                (
                    "weapon_type",
                    models.ForeignKey(
                        blank=True,
                        help_text="Regeltechnischer Waffentyp fuer Waffenmeister und aehnliche Effekte.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ranged_weapon_stats",
                        to="charsheet.weapontype",
                    ),
                ),
                (
                    "skills",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Alle Fertigkeiten, mit denen diese Fernkampfwaffe regeltechnisch gefuehrt werden kann.",
                        related_name="ranged_weapon_stats",
                        to="charsheet.skill",
                    ),
                ),
            ],
        ),
    ]
