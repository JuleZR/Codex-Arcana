from django.db import migrations


def enable_bestiarius_components(apps, schema_editor):
    ArmorStats = apps.get_model("charsheet", "ArmorStats")
    ArmorStats.objects.filter(
        parent_set__isnull=True,
        item__name__iexact="Bestiarius",
    ).update(suppress_component_generation=False)

    from charsheet.armor_generation import sync_armor_set_components
    from charsheet.models import ArmorStats as RuntimeArmorStats

    for armor in RuntimeArmorStats.objects.filter(
        parent_set__isnull=True,
        item__name__iexact="Bestiarius",
    ).select_related("item", "item__default_quality", "item__catalog_group"):
        sync_armor_set_components(armor)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0291_resync_armor_components"),
    ]

    operations = [
        migrations.RunPython(enable_bestiarius_components, migrations.RunPython.noop),
    ]
