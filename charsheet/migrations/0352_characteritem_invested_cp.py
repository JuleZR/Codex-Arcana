from django.db import migrations, models


def copy_item_invested_cp_to_character_items(apps, schema_editor):
    CharacterItem = apps.get_model("charsheet", "CharacterItem")
    for character_item in CharacterItem.objects.select_related("item").filter(item__invested_cp__isnull=False):
        character_item.invested_cp = character_item.item.invested_cp
        character_item.save(update_fields=["invested_cp"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0351_ensure_weaponflag_rows"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritem",
            name="invested_cp",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Optional investierte CP fuer diesen konkreten Besitz-Eintrag.",
                null=True,
            ),
        ),
        migrations.RunPython(copy_item_invested_cp_to_character_items, migrations.RunPython.noop),
    ]
