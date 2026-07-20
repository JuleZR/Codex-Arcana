import uuid

from django.db import migrations, models


def backfill_character_item_provenance(apps, schema_editor):
    CharacterItem = apps.get_model("charsheet", "CharacterItem")
    CharacterItem.objects.filter(original_owner_character__isnull=True).update(
        original_owner_character_id=models.F("owner_id")
    )
    item_ids = CharacterItem.objects.filter(provenance_id__isnull=True).values_list("pk", flat=True)
    for character_item_id in item_ids.iterator():
        CharacterItem.objects.filter(pk=character_item_id).update(provenance_id=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0244_characteritem_original_owner_character_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_character_item_provenance, migrations.RunPython.noop),
    ]
