from django.db import migrations


def set_choice_count(apps, schema_editor, old_count, new_count):
    definition_model = apps.get_model("charsheet", "TechniqueChoiceDefinition")
    definition_model.objects.using(schema_editor.connection.alias).filter(
        technique__school__name="Kriegshund",
        technique__name="Hülle des Stahls",
        target_kind="skill",
        min_choices=old_count,
        max_choices=old_count,
    ).update(min_choices=new_count, max_choices=new_count)


def forwards(apps, schema_editor):
    set_choice_count(apps, schema_editor, 1, 2)


def backwards(apps, schema_editor):
    set_choice_count(apps, schema_editor, 2, 1)


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0422_configure_existing_career_paths"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
