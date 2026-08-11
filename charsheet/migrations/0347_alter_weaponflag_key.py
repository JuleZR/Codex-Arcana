# Generated manually after Python launcher was unavailable.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0346_rangedweaponstats_flags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="weaponflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("mounted_two_handed", "(ZH)"),
                    ("first_round_init", "I"),
                    ("chain_fumble", "$"),
                    ("requires_dex", "(Ge)"),
                    ("can_entangle", "^"),
                    ("drag_target", "^^"),
                    ("caltrop_effect", "+"),
                    ("explode_on_fumble", "#"),
                    ("set_against_charge", "→"),
                    ("parry_bonus", "P"),
                    ("unarmed_damage", "*"),
                ],
                max_length=50,
                unique=True,
            ),
        ),
    ]
