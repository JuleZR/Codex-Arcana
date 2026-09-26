from django.db import migrations, models
from django.db.models import Q


PDF_ARTIFACTS = (
    "\ufb00",
    "\ufb01",
    "\ufb02",
    "\ufb03",
    "\ufb04",
    "\ufb05",
    "\ufb06",
    "\u00ad",
)

LIGATURE_REPLACEMENTS = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "st",
        "\ufb06": "st",
        "\u00ad": "",
    }
)


def normalize_pdf_text_artifacts(apps, schema_editor):
    database = schema_editor.connection.alias
    for model in apps.get_app_config("charsheet").get_models():
        for field in model._meta.local_fields:
            if not isinstance(field, (models.CharField, models.TextField)):
                continue
            field_query = Q()
            for artifact in PDF_ARTIFACTS:
                field_query |= Q(**{f"{field.name}__contains": artifact})
            queryset = model.objects.using(database).filter(field_query)
            for instance in queryset.iterator():
                value = getattr(instance, field.name)
                if not value:
                    continue
                normalized = (
                    value
                    .replace("\ufb01 - ", "fi")
                    .replace("\ufb02 - ", "fl")
                    .replace("\ufb01 ", "fi")
                    .replace("\ufb02 ", "fl")
                    .translate(LIGATURE_REPLACEMENTS)
                )
                if normalized != value:
                    model.objects.using(database).filter(
                        pk=instance.pk
                    ).update(**{field.name: normalized})


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0405_charactercreatureskill_specification"),
    ]

    operations = [
        migrations.RunPython(
            normalize_pdf_text_artifacts,
            migrations.RunPython.noop,
        ),
    ]
