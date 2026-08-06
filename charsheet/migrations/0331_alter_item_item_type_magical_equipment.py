from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0330_alter_spell_duration_units_add_year"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="item_type",
            field=models.CharField(
                choices=[
                    ("armor", "Rüstung"),
                    ("weapon", "Waffe"),
                    ("shield", "Schild"),
                    ("clothing", "Kleidung"),
                    ("ring", "Ring"),
                    ("amulet", "Amulett"),
                    ("magical_weapon", "Magische Waffe"),
                    ("magical_armor", "Magisches Rüstzeug"),
                    ("consumable", "Verbrauchsgegenstand"),
                    ("ammo", "Monition"),
                    ("creature", "Tiere & Kreaturen"),
                    ("misc", "Sonstiges"),
                ],
                max_length=20,
            ),
        ),
    ]
