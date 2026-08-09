from django.db import migrations


def resync_armor_components(apps, schema_editor):
    # The generator is the canonical implementation for naming, grouped
    # coverage, rulebook price overrides, and exact rounding.
    from charsheet.armor_generation import sync_armor_set_components

    ArmorStats = apps.get_model("charsheet", "ArmorStats")

    for armor in (
        ArmorStats.objects.filter(parent_set__isnull=True)
        .select_related("item", "item__default_quality", "item__catalog_group")
        .order_by("pk")
    ):
        sync_armor_set_components(armor)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0290_armor_component_price_overrides"),
    ]

    operations = [
        migrations.RunPython(resync_armor_components, migrations.RunPython.noop),
    ]
