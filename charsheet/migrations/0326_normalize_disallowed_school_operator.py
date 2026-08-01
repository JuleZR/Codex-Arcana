from django.db import migrations


def normalize_operator(apps, schema_editor):
    Effect = apps.get_model("charsheet", "VampireTraitSemanticEffect")
    Effect.objects.filter(
        target_domain="metadata",
        target_key="disallow_schools",
        operator="remove_capability",
    ).update(operator="unset_flag")


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0325_unify_vampire_regeneration_flag"),
    ]

    operations = [
        migrations.RunPython(normalize_operator, migrations.RunPython.noop),
    ]
