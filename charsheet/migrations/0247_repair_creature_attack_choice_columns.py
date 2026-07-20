"""Repair databases where the edited 0238 migration was recorded without its columns."""

from django.db import migrations


CHOICE_MODELS = (
    ("CreatureTraitChoice", "uniq_creature_trait_choice_attack"),
    ("CharacterCreatureTraitChoice", "uniq_character_creature_trait_choice_attack"),
)


def repair_creature_attack_choice_columns(apps, schema_editor):
    connection = schema_editor.connection
    for model_name, constraint_name in CHOICE_MODELS:
        model = apps.get_model("charsheet", model_name)
        table_name = model._meta.db_table
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }
        field = model._meta.get_field("selected_creature_attack")
        if field.column not in columns:
            schema_editor.add_field(model, field)

        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table_name)
        if constraint_name not in constraints:
            constraint = next(
                entry for entry in model._meta.constraints if entry.name == constraint_name
            )
            schema_editor.add_constraint(model, constraint)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0246_finalize_character_item_provenance"),
    ]

    operations = [
        migrations.RunPython(
            repair_creature_attack_choice_columns,
            migrations.RunPython.noop,
        ),
    ]
