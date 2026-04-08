from decimal import Decimal

from django.db import migrations


def sync_legacy_fullplate(apps, schema_editor):
    Item = apps.get_model("charsheet", "Item")
    ArmorStats = apps.get_model("charsheet", "ArmorStats")

    try:
        legacy_item = Item.objects.get(pk=1)
        reference_item = Item.objects.get(pk=158)
    except Item.DoesNotExist:
        return

    try:
        legacy_stats = ArmorStats.objects.get(item_id=legacy_item.pk)
        reference_stats = ArmorStats.objects.get(item_id=reference_item.pk)
    except ArmorStats.DoesNotExist:
        return

    legacy_item.price = reference_item.price
    legacy_item.default_quality = reference_item.default_quality
    legacy_item.weight = reference_item.weight or Decimal("35.00")
    legacy_item.size_class = reference_item.size_class
    legacy_item.save(update_fields=["price", "default_quality", "weight", "size_class"])

    legacy_stats.rs_total = reference_stats.rs_total
    legacy_stats.encumbrance = reference_stats.encumbrance
    legacy_stats.min_st = reference_stats.min_st
    legacy_stats.save(update_fields=["rs_total", "encumbrance", "min_st"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0097_character_current_arcane_power"),
    ]

    operations = [
        migrations.RunPython(sync_legacy_fullplate, migrations.RunPython.noop),
    ]
