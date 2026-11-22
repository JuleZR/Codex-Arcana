"""Retain full training descriptions and recover old clipped catalog copies."""

from django.db import migrations, models


def restore_descriptions(apps, schema_editor):
    for name in ("CharacterCreatureSkill", "CharacterCreatureSpecialSkill"):
        model = apps.get_model("charsheet", name)
        rows = model.objects.exclude(notes="").select_related("skill")
        for row in rows.only("pk", "notes", "skill__description").iterator():
            description = row.skill.description or ""
            if len(description) > 200 and row.notes == description[:200]:
                model.objects.filter(pk=row.pk).update(notes=description)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0520_catalog_flight_power_link")]

    operations = [
        migrations.AlterField(
            model_name="charactercreatureskill",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="charactercreaturespecialskill",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(restore_descriptions, migrations.RunPython.noop),
    ]
