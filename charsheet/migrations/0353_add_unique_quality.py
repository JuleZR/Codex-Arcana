from django.db import migrations


def add_unique_quality(apps, schema_editor):
    Quality = apps.get_model("charsheet", "Quality")
    Quality.objects.update_or_create(
        code="unique",
        defaults={
            "name": "Einzigartige Qualit\u00e4t",
            "hex_color": "#FFD700",
            "sort_order": 4,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0352_characteritem_invested_cp"),
    ]

    operations = [
        migrations.RunPython(add_unique_quality, migrations.RunPython.noop),
    ]
