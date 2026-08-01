from django.db import migrations, models


def copy_weakness_text(apps, schema_editor):
    VampirePower = apps.get_model("charsheet", "VampirePower")
    for power in VampirePower.objects.select_related("weakness_trait").iterator():
        trait = power.weakness_trait
        power.weakness_text = trait.description.strip() or trait.name
        power.save(update_fields=["weakness_text"])


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0321_vampire_semantic_effect_target_schools"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RenameField(
                    model_name="vampirepower",
                    old_name="weakness",
                    new_name="weakness_trait",
                ),
                migrations.AddField(
                    model_name="vampirepower",
                    name="weakness_text",
                    field=models.TextField(default=""),
                    preserve_default=False,
                ),
                migrations.RunPython(copy_weakness_text, migrations.RunPython.noop),
                migrations.RemoveField(
                    model_name="vampirepower",
                    name="weakness_trait",
                ),
                migrations.RenameField(
                    model_name="vampirepower",
                    old_name="weakness_text",
                    new_name="weakness",
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="vampirepower",
                    name="weakness",
                    field=models.TextField(),
                ),
            ],
        ),
    ]
