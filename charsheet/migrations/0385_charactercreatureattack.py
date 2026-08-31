from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0384_creaturesourcebinding_creature_name_filter"),
    ]

    operations = [
        migrations.CreateModel(
            name="CharacterCreatureAttack",
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
                ("name", models.CharField(max_length=100)),
                ("attack_value", models.IntegerField(default=0)),
                ("damage_dice_amount", models.PositiveIntegerField(default=0)),
                ("damage_dice_faces", models.PositiveIntegerField(default=0)),
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
                ("damage_flat_bonus", models.IntegerField(default=0)),
                (
                    "damage_type",
                    models.CharField(
                        blank=True,
                        choices=[("B", "B"), ("T", "T")],
                        default="",
                        max_length=1,
                    ),
                ),
                ("notes", models.CharField(blank=True, default="", max_length=200)),
                ("show_notes_as_damage", models.BooleanField(default=False)),
                ("append_notes_to_damage", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "attack_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_creature_attacks",
                        to="charsheet.creatureattacktype",
                    ),
                ),
                (
                    "base_attack",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_overrides",
                        to="charsheet.creatureattack",
                    ),
                ),
                (
                    "creature",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attack_overrides",
                        to="charsheet.charactercreature",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "name", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="charactercreatureattack",
            constraint=models.UniqueConstraint(
                fields=("creature", "base_attack"),
                name="uniq_character_creature_base_attack_override",
            ),
        ),
    ]
