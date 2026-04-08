from django.db import migrations, models


def normalize_weapon_bonus_operators(apps, schema_editor):
    WeaponStats = apps.get_model("charsheet", "WeaponStats")

    for stats in WeaponStats.objects.all():
        base_bonus = int(stats.damage_flat_bonus or 0)
        if base_bonus > 0:
            stats.damage_flat_operator = "+"
        elif base_bonus < 0:
            stats.damage_flat_operator = "-"
            stats.damage_flat_bonus = abs(base_bonus)
        else:
            stats.damage_flat_operator = ""

        h2_bonus = stats.h2_flat_bonus
        if h2_bonus is None:
            stats.h2_flat_operator = ""
        elif h2_bonus > 0:
            stats.h2_flat_operator = "+"
        elif h2_bonus < 0:
            stats.h2_flat_operator = "-"
            stats.h2_flat_bonus = abs(h2_bonus)
        else:
            stats.h2_flat_operator = ""

        stats.save(update_fields=["damage_flat_bonus", "damage_flat_operator", "h2_flat_bonus", "h2_flat_operator"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0093_item_clothing_and_garnitures"),
    ]

    operations = [
        migrations.AddField(
            model_name="weaponstats",
            name="damage_flat_operator",
            field=models.CharField(
                blank=True,
                choices=[("", "Kein Operator"), ("+", "+"), ("-", "-"), ("/", "/")],
                default="",
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="weaponstats",
            name="h2_flat_operator",
            field=models.CharField(
                blank=True,
                choices=[("", "Kein Operator"), ("+", "+"), ("-", "-"), ("/", "/")],
                default="",
                max_length=1,
            ),
        ),
        migrations.RunPython(normalize_weapon_bonus_operators, migrations.RunPython.noop),
    ]
