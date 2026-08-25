from django.db import migrations


def ensure_default_quality(apps, schema_editor):
    Quality = apps.get_model("charsheet", "Quality")

    Quality.objects.exclude(pk="common").filter(
        is_default=True
    ).update(is_default=False)

    updated = Quality.objects.filter(pk="common").update(
        is_default=True
    )

    if updated != 1:
        raise RuntimeError(
            "Quality 'common' does not exist."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0370_remove_quality_holographic_display_and_more"),
    ]

    operations = [
        migrations.RunPython(
            ensure_default_quality,
            migrations.RunPython.noop,
        ),
    ]
