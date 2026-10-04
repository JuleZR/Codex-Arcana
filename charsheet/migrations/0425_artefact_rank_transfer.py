from django.db import migrations


def preserve_artefact_reputation_points(apps, schema_editor):
    Character = apps.get_model("charsheet", "Character")
    for character in Character.objects.exclude(reputation_artefact_points=0).iterator():
        character.reputation_personal_points += character.reputation_artefact_points
        character.save(update_fields=["reputation_personal_points"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0424_reputation_points"),
    ]

    operations = [
        migrations.RunPython(
            preserve_artefact_reputation_points,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="character",
            name="reputation_artefact_points",
        ),
    ]
