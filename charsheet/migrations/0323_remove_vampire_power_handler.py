from django.db import migrations


HANDLER_FLAGS = {
    "manual_activation": "vampire_power_manual_activation",
    "blood_theft": "vampire_power_blood_theft",
    "blood_sacrament": "vampire_power_blood_sacrament",
    "attribute_boost": "vampire_power_attribute_boost",
    "regeneration": "vampire_power_regeneration",
}


def migrate_handlers_to_semantic_flags(apps, schema_editor):
    VampirePower = apps.get_model("charsheet", "VampirePower")
    SemanticEffect = apps.get_model("charsheet", "VampireTraitSemanticEffect")
    for power in VampirePower.objects.exclude(handler="").iterator():
        target_key = HANDLER_FLAGS.get(power.handler)
        if not target_key:
            continue
        SemanticEffect.objects.get_or_create(
            power=power,
            target_domain="rule_flag",
            target_key=target_key,
            defaults={
                "application_scope": "both",
                "operator": "set_flag",
                "value": "true",
                "active_flag": True,
                "notes": "Automatisch aus dem früheren VampirePower-Handler migriert.",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0322_vampire_power_weakness_text"),
    ]

    operations = [
        migrations.RunPython(migrate_handlers_to_semantic_flags, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="vampirepower",
            name="handler",
        ),
    ]
