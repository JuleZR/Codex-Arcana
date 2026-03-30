from django.db import migrations


def backfill_race_items(apps, schema_editor):
    RaceStartingItem = apps.get_model("charsheet", "RaceStartingItem")
    CharacterItem = apps.get_model("charsheet", "CharacterItem")

    for starter in RaceStartingItem.objects.all():
        CharacterItem.objects.filter(
            owner__race_id=starter.race_id,
            item_id=starter.item_id,
        ).update(equipped=True, equip_locked=True)


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0070_characteritem_equip_locked"),
    ]

    operations = [
        migrations.RunPython(backfill_race_items, migrations.RunPython.noop),
    ]
