from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0201_alter_spell_duration_units"),
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
                    ("magic_item", "Magischer Gegenstand"),
                    ("consumable", "Verbrauchsgegenstand"),
                    ("ammo", "Monition"),
                    ("creature", "Tiere & Kreaturen"),
                    ("misc", "Sonstiges"),
                ],
                max_length=20,
            ),
        ),
    ]
