from django.db import migrations, models


SPELL_SLOT_SOURCE_KINDS = (
    "arcane_free",
    "arcane_extra",
    "arcane_bonus",
    "divine_extra",
    "divine_bonus",
)


def backfill_spent_spell_learning_slots(apps, schema_editor):
    Character = apps.get_model("charsheet", "Character")
    CharacterSpell = apps.get_model("charsheet", "CharacterSpell")

    spent_counts = {}
    for row in (
        CharacterSpell.objects.filter(source_kind__in=SPELL_SLOT_SOURCE_KINDS)
        .values("character_id")
        .order_by()
    ):
        character_id = int(row["character_id"])
        spent_counts[character_id] = spent_counts.get(character_id, 0) + 1

    for character in Character.objects.all().only("id", "spent_spell_learning_slots"):
        character.spent_spell_learning_slots = int(spent_counts.get(character.id, 0))
        character.save(update_fields=["spent_spell_learning_slots"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0149_alter_spell_range_unit_add_square_km"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="spent_spell_learning_slots",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_spent_spell_learning_slots, migrations.RunPython.noop),
    ]
