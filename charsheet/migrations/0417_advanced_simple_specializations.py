"""Configure Compendium selections without introducing models or columns."""

from django.db import migrations, models


def configure_compendium(apps, schema_editor):
    School = apps.get_model("charsheet", "School")
    Specialization = apps.get_model("charsheet", "Specialization")
    ProgressionRule = apps.get_model("charsheet", "ProgressionRule")
    Binding = apps.get_model("charsheet", "CreatureSourceBinding")
    database = schema_editor.connection.alias
    for school in School.objects.using(database).filter(
        type__slug__in=["combat", "school_combat"]
    ):
        name = school.name.casefold()
        options = []
        path_id = None
        if name in {"kryss", "barde", "bard", "bardenschule"}:
            source_name = (
                "Mutation" if name == "kryss" else "Erwachte Begabung"
            )
            source = (
                school.techniques.using(database)
                .filter(name__iexact=source_name, path__isnull=True)
                .order_by("level", "id")
                .first()
            )
            if source is None:
                continue
            options = [
                {"specialization_id": pk, "source_technique_id": source.pk}
                for pk in school.specializations.using(database)
                .filter(is_active=True)
                .exclude(name__in=["Tonbrecher", "Tone Breaker"])
                .values_list("pk", flat=True)
            ]
        elif name in {"tiermeister", "tiermaster"}:
            binding = (
                Binding.objects.using(database)
                .filter(
                    technique_trigger__school=school,
                    technique_trigger__name__iexact="Ruf der Wildnis",
                    active=True,
                    selection_mode="character_choice",
                )
                .first()
            )
            if binding is None:
                continue
            specialization, _ = Specialization.objects.using(
                database
            ).get_or_create(
                school=school,
                slug="additional-call-of-the-wild",
                defaults={
                    "name": "Zusätzlicher Ruf der Wildnis",
                    "allow_multiple": True,
                    "description": (
                        "Ein weiterer Tiergefährte nach den normalen Regeln "
                        "für Ruf der Wildnis."
                    ),
                },
            )
            options = [
                {
                    "specialization_id": specialization.pk,
                    "source_technique_id": binding.technique_trigger_id,
                    "creature_source_binding_id": binding.pk,
                }
            ]
        elif name in {"seewolf", "seawolf"}:
            path = (
                school.paths.using(database)
                .filter(
                    name__in=["Schiffsbauer", "Schiffbauer", "Shipbuilder"]
                )
                .first()
            )
            if path is None:
                continue
            path_id = path.pk
            sources = school.techniques.using(database).filter(
                path=path, choice_target_kind="specialization"
            )
            source = sources.order_by("level", "id").first()
            if source is None:
                continue
            options = [
                {"specialization_id": pk, "source_technique_id": source.pk}
                for pk in school.specializations.using(database)
                .filter(is_active=True)
                .values_list("pk", flat=True)
            ]
        if options:
            ProgressionRule.objects.using(database).get_or_create(
                school_type_id=school.type_id,
                grant_kind="advanced_simple",
                params={
                    "school_id": school.pk,
                    "path_id": path_id,
                    "ep_cost": 20,
                    "arcane_power": 1,
                    "options": options,
                },
                defaults={"min_level": 10},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0416_specialization_character_skill_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="progressionrule",
            name="grant_kind",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("technique_choice", "Technique Choice"),
                    ("spell_choice", "Spell Choice"),
                    ("aspect_access", "Aspect Access"),
                    ("aspect_spell", "Aspect Spell"),
                    (
                        "advanced_simple",
                        "Zusätzliche einfache Spezialisierung",
                    ),
                ],
            ),
        ),
        migrations.RunPython(configure_compendium, migrations.RunPython.noop),
    ]
