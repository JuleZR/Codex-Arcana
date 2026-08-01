from django.db import migrations


def unify_regeneration_effects(apps, schema_editor):
    Effect = apps.get_model("charsheet", "VampireTraitSemanticEffect")
    for effect in Effect.objects.filter(
        target_domain="capability",
        target_key="vampire_regeneration",
    ):
        effect.target_domain = "rule_flag"
        effect.operator = "unset_flag" if effect.operator == "remove_capability" else "set_flag"
        effect.value = "true"
        effect.save(update_fields=["target_domain", "operator", "value"])
    Effect.objects.filter(
        target_domain="rule_flag",
        target_key="vampire_power_regeneration",
    ).update(target_key="vampire_regeneration")
    Effect.objects.filter(
        target_domain="metadata",
        target_key="disallow_schools",
        operator="remove_capability",
    ).update(operator="unset_flag")


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0324_vampire_semantic_effect_power_component"),
    ]

    operations = [
        migrations.RunPython(unify_regeneration_effects, migrations.RunPython.noop),
    ]
