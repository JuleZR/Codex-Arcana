from django.db import migrations


WEAPON_FLAG_KEYS = (
    "mounted_two_handed",
    "mounted_two_handed_penalty",
    "first_round_init",
    "chain_fumble",
    "requires_dex",
    "can_entangle",
    "drag_target",
    "caltrop_effect",
    "explode_on_fumble",
    "set_against_charge",
    "parry_bonus",
    "unarmed_damage",
)


def ensure_weaponflag_rows(apps, schema_editor):
    WeaponFlag = apps.get_model("charsheet", "WeaponFlag")
    for key in WEAPON_FLAG_KEYS:
        WeaponFlag.objects.get_or_create(key=key)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0350_rangedweaponstats_optional_minimum_strength"),
    ]

    operations = [
        migrations.RunPython(ensure_weaponflag_rows, migrations.RunPython.noop),
    ]
