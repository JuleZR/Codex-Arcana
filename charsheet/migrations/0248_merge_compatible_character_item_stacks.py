"""Consolidate existing plain duplicate stacks without discarding transfer history."""

from collections import defaultdict

from django.db import migrations


def _field_value(instance, field):
    value = getattr(instance, field.attname)
    return str(value.name or "") if hasattr(value, "name") else value


def merge_compatible_stacks(apps, schema_editor):
    CharacterItem = apps.get_model("charsheet", "CharacterItem")
    CharacterCreature = apps.get_model("charsheet", "CharacterCreature")
    CharacterItemRuneSpec = apps.get_model("charsheet", "CharacterItemRuneSpec")
    ItemRune = apps.get_model("charsheet", "ItemRune")
    ItemPermissionGrant = apps.get_model("charsheet", "ItemPermissionGrant")
    ItemOwnershipEvent = apps.get_model("charsheet", "ItemOwnershipEvent")
    ItemTransfer = apps.get_model("charsheet", "ItemTransfer")
    Modifier = apps.get_model("charsheet", "Modifier")
    ContentType = apps.get_model("contenttypes", "ContentType")

    pending_ids = set(
        ItemTransfer.objects.filter(status="pending", item_id__isnull=False).values_list(
            "item_id", flat=True
        )
    )
    content_type = ContentType.objects.filter(
        app_label="charsheet", model="characteritem"
    ).first()
    excluded_fields = {
        "id",
        "amount",
        "provenance_id",
        "ownership_version",
        "equipped",
        "equip_locked",
        "stored",
    }
    comparison_fields = [
        field
        for field in CharacterItem._meta.concrete_fields
        if not field.primary_key and field.name not in excluded_fields
    ]
    groups = defaultdict(list)
    for item in CharacterItem.objects.filter(item__stackable=True).order_by("pk"):
        if item.pk in pending_ids:
            continue
        if (
            item.runes.exists()
            or ItemRune.objects.filter(item_id=item.pk).exists()
            or CharacterItemRuneSpec.objects.filter(character_item_id=item.pk).exists()
            or ItemPermissionGrant.objects.filter(item_id=item.pk).exists()
            or CharacterCreature.objects.filter(source_character_item_id=item.pk).exists()
            or (
                content_type
                and Modifier.objects.filter(
                    source_content_type_id=content_type.pk,
                    source_object_id=item.pk,
                ).exists()
            )
        ):
            continue
        key = tuple(_field_value(item, field) for field in comparison_fields)
        groups[key].append(item)

    for items in groups.values():
        if len(items) < 2:
            continue
        survivor = items[0]
        for duplicate in items[1:]:
            survivor.amount += duplicate.amount
            ItemTransfer.objects.filter(item_id=duplicate.pk).update(item_id=survivor.pk)
            ItemOwnershipEvent.objects.filter(item_id=duplicate.pk).update(item_id=survivor.pk)
            duplicate.delete()
        survivor.save(update_fields=["amount"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0247_repair_creature_attack_choice_columns"),
    ]

    operations = [
        migrations.RunPython(
            merge_compatible_stacks,
            migrations.RunPython.noop,
        ),
    ]
