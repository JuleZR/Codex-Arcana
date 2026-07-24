from django.db import migrations, models


def copy_existing_damage(apps, schema_editor):
    group_creature = apps.get_model("charsheet", "GameGroupCreature")
    for card in group_creature.objects.exclude(current_damage=0).iterator():
        card.current_lethal_damage = card.current_damage
        card.save(update_fields=["current_lethal_damage"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0268_game_group_creature"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamegroupcreature",
            name="current_stun_damage",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="gamegroupcreature",
            name="current_lethal_damage",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(
            copy_existing_damage,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="gamegroupcreature",
            name="current_damage",
        ),
    ]
