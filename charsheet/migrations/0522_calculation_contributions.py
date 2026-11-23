"""Replace the former VW-only flag with a component-level semantic effect."""

from django.db import migrations


def migrate_vw_contributions(apps, schema_editor):
    for model in apps.get_app_config("charsheet").get_models():
        fields = {field.name for field in model._meta.fields}
        if not {"target_domain", "target_key", "operator", "value",
                "metadata"}.issubset(fields):
            continue
        effects = model.objects.using(schema_editor.connection.alias).filter(
            target_domain="rule_flag",
            target_key="suppress_positive_vw_attribute_bonuses",
            operator="set_flag",
        )
        for effect in effects.iterator():
            metadata = dict(effect.metadata or {})
            metadata["calculation_contributions"] = ["GE", "WA"]
            effect.target_domain = "derived_stat"
            effect.target_key = "vw"
            effect.operator = "max_value"
            effect.value = "0"
            effect.metadata = metadata
            effect.save(
                using=schema_editor.connection.alias,
                update_fields=("target_domain", "target_key", "operator",
                               "value", "metadata"),
            )


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0521_creature_skill_full_descriptions")]

    operations = [
        migrations.RunPython(
            migrate_vw_contributions, migrations.RunPython.noop,
        ),
    ]
