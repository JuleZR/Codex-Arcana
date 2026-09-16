"""Convert active legacy prerequisites before removing their source fields.

Back up the database and export lessons/legacy requirements before deployment.
The removed, previously unused requirement expressions cannot be reconstructed.
"""

from django.db import migrations


def migrate_requirements(apps, schema_editor):
    alias = schema_editor.connection.alias
    Lesson = apps.get_model("charsheet", "Lesson")
    Requirement = apps.get_model("charsheet", "LessonRequirement")
    lessons = list(
        Lesson.objects.using(alias)
        .select_related(
            "school__type",
            "technique",
        )
        .order_by("id")
    )
    invalid = []
    for lesson in lessons:
        school_type = lesson.school.type
        combat = (
            school_type.slug in {"combat", "school_combat"}
            or school_type.name.casefold() == "kampfschule"
        )
        if (
            not combat
            or not lesson.technique_id
            or lesson.technique.school_id != lesson.school_id
        ):
            invalid.append(lesson.pk)
    if invalid:
        raise RuntimeError(
            "Ungültige School-/Technique-Paare; Migration abgebrochen. "
            f"Lesson-IDs: {invalid}"
        )
    Requirement.objects.using(alias).all().delete()
    Requirement.objects.using(alias).bulk_create(
        [
            Requirement(
                lesson_id=lesson.pk,
                requirement_type="school_technique",
                required_school_id=lesson.school_id,
                required_technique_id=lesson.technique_id,
                sort_order=0,
            )
            for lesson in lessons
        ]
    )


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0387_flexible_lesson_requirements")]

    operations = [migrations.RunPython(migrate_requirements)]
