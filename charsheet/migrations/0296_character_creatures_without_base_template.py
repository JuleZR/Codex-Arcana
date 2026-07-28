from django.db import migrations, models
import django.db.models.deletion


SYSTEM_EMPTY_CREATURE_SLUG = "system-leere-tierform"


def move_empty_creatures_to_character_instances(apps, schema_editor):
    Creature = apps.get_model("charsheet", "Creature")
    CharacterCreature = apps.get_model("charsheet", "CharacterCreature")
    GameGroupCreature = apps.get_model("charsheet", "GameGroupCreature")

    system_creature_ids = list(
        Creature.objects.filter(slug=SYSTEM_EMPTY_CREATURE_SLUG).values_list("pk", flat=True)
    )
    if not system_creature_ids:
        return

    character_creature_ids = list(
        CharacterCreature.objects.filter(creature_id__in=system_creature_ids).values_list("pk", flat=True)
    )
    GameGroupCreature.objects.filter(
        character_creature_id__in=character_creature_ids,
        creature_id__in=system_creature_ids,
    ).update(creature_id=None)
    CharacterCreature.objects.filter(pk__in=character_creature_ids).update(creature_id=None)
    Creature.objects.filter(pk__in=system_creature_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0295_simplify_armor_zone_override_help"),
    ]

    operations = [
        migrations.AlterField(
            model_name="charactercreature",
            name="creature",
            field=models.ForeignKey(
                blank=True,
                help_text="Optionale DB-Vorlage. Freie Kreaturen liegen vollständig auf der Charakter-Kreatur.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="character_instances",
                to="charsheet.creature",
            ),
        ),
        migrations.AlterField(
            model_name="gamegroupcreature",
            name="creature",
            field=models.ForeignKey(
                blank=True,
                help_text="Basisvorlage; bei einer freien Charakter-Kreatur leer.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="game_group_screen_instances",
                to="charsheet.creature",
            ),
        ),
        migrations.RunPython(
            move_empty_creatures_to_character_instances,
            migrations.RunPython.noop,
        ),
    ]
