from django.db import migrations, models


def create_mounted_two_handed_penalty_flag(apps, schema_editor):
    WeaponFlag = apps.get_model("charsheet", "WeaponFlag")
    WeaponFlag.objects.get_or_create(key="mounted_two_handed_penalty")


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0348_ranged_weapon_damage_label_remove_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="weaponflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("mounted_two_handed", "--"),
                    ("mounted_two_handed_penalty", "(ZH)"),
                    ("first_round_init", "I"),
                    ("chain_fumble", "$"),
                    ("requires_dex", "(Ge)"),
                    ("can_entangle", "^"),
                    ("drag_target", "^^"),
                    ("caltrop_effect", "+"),
                    ("explode_on_fumble", "#"),
                    ("set_against_charge", "\u2192"),
                    ("parry_bonus", "P"),
                    ("unarmed_damage", "*"),
                ],
                max_length=50,
                unique=True,
            ),
        ),
        migrations.RunPython(create_mounted_two_handed_penalty_flag, migrations.RunPython.noop),
    ]
