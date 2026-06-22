import django.db.models.deletion
from django.db import migrations, models


def copy_patron_aspects(apps, schema_editor):
    ShamanPatronAspect = apps.get_model("charsheet", "ShamanPatronAspect")
    for row in ShamanPatronAspect.objects.all().iterator():
        row.patron.aspects.add(row.aspect_id)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0198_charactershamanpatron_patron_kind_override")]

    operations = [
        migrations.AlterField(
            model_name="shamanpatronaspect",
            name="patron",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="legacy_aspects",
                to="charsheet.shamanpatron",
            ),
        ),
        migrations.AlterField(
            model_name="shamanpatronaspect",
            name="aspect",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="legacy_shaman_patrons",
                to="charsheet.aspect",
            ),
        ),
        migrations.AddField(
            model_name="shamanpatron",
            name="aspects",
            field=models.ManyToManyField(blank=True, related_name="shaman_patrons", to="charsheet.aspect"),
        ),
        migrations.RunPython(copy_patron_aspects, migrations.RunPython.noop),
        migrations.DeleteModel(name="ShamanPatronAspect"),
    ]
