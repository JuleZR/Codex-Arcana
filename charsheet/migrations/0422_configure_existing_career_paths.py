"""Derive additional progression from existing school paths."""

from django.db import migrations


def configure_paths(apps, schema_editor):
    SchoolPath = apps.get_model("charsheet", "SchoolPath")
    Technique = apps.get_model("charsheet", "Technique")
    Step = apps.get_model("charsheet", "CareerPathTechnique")
    School = apps.get_model("charsheet", "School")
    for school in School.objects.filter(
        type__slug__in=["combat", "school_combat"]
    ):
        for path in SchoolPath.objects.filter(school=school):
            techniques = list(
                Technique.objects.filter(
                    path=path,
                    level__gte=1,
                    level__lte=10,
                ).order_by("level", "id")
            )
            if not techniques:
                continue
            for order, technique in enumerate(techniques, 1):
                Step.objects.get_or_create(
                    technique=technique,
                    defaults={
                        "path": path,
                        "order": order,
                        "effective_level": technique.level,
                    },
                )
            path.additional_progression = True
            path.completion_purchase = techniques[-1].level < 10
            path.save(
                update_fields=["additional_progression", "completion_purchase"]
            )
        if school.name.casefold() in {
            "kriegshund",
            "kriegshunde",
            "dogs of war",
        }:
            SchoolPath.objects.get_or_create(
                school=school,
                name="Maschinenreiter",
                defaults={
                    "additional_progression": True,
                    "additional_only": True,
                    "description": (
                        "Megalys: zusätzliche Laufbahn des Kriegshunds."
                    ),
                },
            )
    tone_names = [
        ("Kristallbrecher", "Crystal Breaker"),
        ("Steinbrecher", "Stone Breaker"),
        ("Stahlbrecher", "Steel Breaker"),
        ("Brecher toter Formen", "Breaker of Dead Form"),
        ("Lebensbrecher", "Life Breaker"),
    ]
    for school in School.objects.filter(
        name__in=["Barde", "Bardenschule", "Bard"]
    ):
        path, _ = SchoolPath.objects.get_or_create(
            school=school,
            name="Tonbrecher",
            defaults={
                "additional_progression": True,
                "additional_only": True,
            },
        )
        techniques = []
        for names in tone_names:
            technique = Technique.objects.filter(
                school=school, name__in=names
            ).first()
            if technique is None or technique.level is None:
                break
            techniques.append(technique)
        if len(techniques) != len(tone_names):
            continue
        for order, technique in enumerate(techniques, 1):
            Step.objects.get_or_create(
                technique=technique,
                defaults={
                    "path": path,
                    "order": order,
                    "effective_level": technique.level,
                },
            )
        path.completion_purchase = techniques[-1].level < 10
        path.save(update_fields=["completion_purchase"])


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0421_additional_career_paths")]
    operations = [
        migrations.RunPython(configure_paths, migrations.RunPython.noop)
    ]
