from django.db import migrations


def assign_armor_component_subtype(apps, schema_editor):
    alias = schema_editor.connection.alias
    subtype_model = apps.get_model("charsheet", "ItemSubType")
    item_model = apps.get_model("charsheet", "Item")
    armor_model = apps.get_model("charsheet", "ArmorStats")
    subtype, _created = subtype_model.objects.using(alias).get_or_create(
        slug="armor_component",
        defaults={"name": "Rüstungsteil", "plural_name": "Rüstungsteile"},
    )
    component_ids = armor_model.objects.using(alias).filter(
        parent_set__isnull=False,
    ).values("item_id")
    item_model.objects.using(alias).filter(pk__in=component_ids).update(
        subtype_id=subtype.pk,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0476_item_subtype"),
    ]

    operations = [
        migrations.RunPython(
            assign_armor_component_subtype, migrations.RunPython.noop,
        ),
    ]
