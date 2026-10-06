"""Convert existing image references while retaining their original files."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from charsheet.image_conversion import (
    convertible_image_fields,
    jpeg_content,
)


class Command(BaseCommand):
    help = "Convert non-symbol images to JPEG; retain originals."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Write JPEG files and update references (default: preview).",
        )

    def handle(self, *args, **options):
        converted_count = 0
        failed_count = 0
        # Share conversions where multiple rows reference the same source.
        converted_names = {}
        for model in apps.get_app_config("charsheet").get_models():
            for field in convertible_image_fields(model):
                rows = model._base_manager.exclude(**{field.name: ""}).exclude(
                    **{field.name: None}
                ).values_list("pk", field.name)
                for pk, name in rows.iterator():
                    label = f"{model._meta.label}.{field.name} pk={pk}"
                    try:
                        key = (id(field.storage), name)
                        if key not in converted_names:
                            with field.storage.open(name, "rb") as source:
                                content = jpeg_content(source, name)
                            if content is None:
                                continue
                            converted_names[key] = (
                                field.storage.save(content.name, content)
                                if options["apply"] else content.name
                            )
                        target = converted_names[key]
                        if options["apply"]:
                            updated = model._base_manager.filter(
                                pk=pk, **{field.name: name}
                            ).update(**{field.name: target})
                            if not updated:
                                raise ValueError("Image reference changed")
                        converted_count += 1
                        self.stdout.write(f"{label}: {name} -> {target}")
                    except Exception as exc:
                        failed_count += 1
                        self.stderr.write(f"{label}: {exc}")
        mode = "Converted" if options["apply"] else "Would convert"
        self.stdout.write(f"{mode} {converted_count} image references.")
        self.stdout.write("Original files retained; symbols unchanged.")
        if failed_count:
            raise CommandError(f"{failed_count} image conversions failed.")
