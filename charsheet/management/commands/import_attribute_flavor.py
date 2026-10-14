"""Explicit, opt-in import; never invoked by schema migrations."""

import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from charsheet.models import (
    Attribute,
    AttributeRating,
    GeneralAttributeMeaning,
    RaceAttributeFlavor,
)


class Command(BaseCommand):
    help = (
        "Importiert Eigenschaftsreferenzen und eigene Erzähltexte "
        "ohne bestehende Einträge zu ändern."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=Path(__file__).resolve().parent.parent
            / "attribute_flavor_initial.json",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        models = {
            model.__name__: model
            for model in (
                AttributeRating,
                GeneralAttributeMeaning,
                RaceAttributeFlavor,
            )
        }
        try:
            records = json.loads(options["file"].read_text(encoding="utf-8"))
            created = 0
            for record in records:
                data = dict(record)
                model = models[data.pop("model")]
                code = data.pop("attribute", None)
                if code:
                    data["attribute"] = Attribute.objects.get(short_name=code)
                scope = {
                    key: data.get(key) for key in ("min_value", "max_value")
                }
                if model is not GeneralAttributeMeaning:
                    scope["attribute"] = data.get("attribute")
                if model.objects.filter(**scope).exists():
                    continue
                instance = model(**data)
                instance.full_clean()
                instance.save()
                created += 1
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            Attribute.DoesNotExist,
            ValidationError,
        ) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{created} Einträge angelegt; "
                "vorhandene Einträge unverändert.",
            )
        )
