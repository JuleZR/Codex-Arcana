from decimal import Decimal

from django.db import migrations, models


CLOTHING_ITEMS = [
    {
        "name": "Bauernkleidung",
        "price": 60,
        "weight": Decimal("2.00"),
        "default_quality": "poor",
        "description": (
            "Unterwaesche aus einfachem Leinen, Hemd, Hose und Lederschuhe. "
            "Schlechte Qualitaet."
        ),
    },
    {
        "name": "Festtagskleidung",
        "price": 460,
        "weight": Decimal("2.50"),
        "default_quality": "fine",
        "description": (
            "Unterwaesche, Hemd, Hose, Hut, Schuhe, Struempfe, Guertel und Cape. "
            "Gute Qualitaet."
        ),
    },
    {
        "name": "Hofkleidung",
        "price": 900,
        "weight": Decimal("2.75"),
        "default_quality": "excellent",
        "description": (
            "Rueschenhemd, Samtkniebundhose, Struempfe, Unterwaesche, Hut, Schuhe, "
            "Guertel, Samthandschuhe und Cape oder Rockjacke. Exzellente Qualitaet."
        ),
    },
    {
        "name": "Jagdkleidung",
        "price": 500,
        "weight": Decimal("4.50"),
        "default_quality": "fine",
        "description": (
            "Unterwaesche, Struempfe, Kapuzenumhang, Lederhemd, Wildlederhose, "
            "Stulpenstiefel, Guertel, Guerteltaschen und Stulpenhandschuhe. Gute Qualitaet."
        ),
    },
    {
        "name": "Lumpen",
        "price": 5,
        "weight": Decimal("0.50"),
        "default_quality": "wretched",
        "description": "Zusammengebundene Fetzen einfacher Lumpen.",
    },
    {
        "name": "Magier- oder Priesterroben",
        "price": 200,
        "weight": Decimal("2.00"),
        "default_quality": "fine",
        "description": "Unterwaesche, Sandalen, Robe und Guertel. Gute Qualitaet.",
    },
    {
        "name": "Prunkvolle Abendgarderobe",
        "price": 5000,
        "weight": Decimal("4.25"),
        "default_quality": "legendary",
        "description": (
            "Unterwaesche aus Seide, verzierte Schuhe, Seidenstruempfe, aufwendige "
            "gepuderte Peruecke, Seidenhandschuhe und ein prunkvolles Ensemble fuer Ball "
            "oder Hof. Legendaere Qualitaet."
        ),
    },
    {
        "name": "Reisekleidung",
        "price": 220,
        "weight": Decimal("3.50"),
        "default_quality": "common",
        "description": (
            "Unterwaesche, Hemd, Hose oder Rock, Struempfe, Kapuzenmantel, "
            "Lederstiefel und Guertel. Normale Qualitaet."
        ),
    },
    {
        "name": "Winterreisekleidung",
        "price": 600,
        "weight": Decimal("4.75"),
        "default_quality": "fine",
        "description": (
            "Unterwaesche, Struempfe, Fellweste, warmes Hemd, gefuetterte Hose, "
            "gefuetterte Stiefel, Fellmantel, Guertel, Fellmuetze und Fellfaeustlinge. "
            "Gute Qualitaet."
        ),
    },
]


def add_clothing_items(apps, schema_editor):
    Item = apps.get_model("charsheet", "Item")
    ArmorStats = apps.get_model("charsheet", "ArmorStats")
    ShieldStats = apps.get_model("charsheet", "ShieldStats")
    WeaponStats = apps.get_model("charsheet", "WeaponStats")

    for payload in CLOTHING_ITEMS:
        item, _created = Item.objects.update_or_create(
            name=payload["name"],
            defaults={
                "price": payload["price"],
                "item_type": "clothing",
                "description": payload["description"],
                "stackable": False,
                "is_consumable": False,
                "default_quality": payload["default_quality"],
                "weight": payload["weight"],
                "size_class": "M",
            },
        )
        ArmorStats.objects.filter(item=item).delete()
        ShieldStats.objects.filter(item=item).delete()
        WeaponStats.objects.filter(item=item).delete()


def remove_clothing_items(apps, schema_editor):
    Item = apps.get_model("charsheet", "Item")
    Item.objects.filter(name__in=[payload["name"] for payload in CLOTHING_ITEMS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0092_alter_schooltype_slug"),
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
                    ("consumable", "verbrauchbar"),
                    ("ammo", "Monition"),
                    ("misc", "Misc"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(add_clothing_items, remove_clothing_items),
    ]
