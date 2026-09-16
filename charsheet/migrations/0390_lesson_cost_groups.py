from itertools import product

import django.core.validators
from django.db import migrations, models


def legacy_cost_packages(rows):
    """Return equivalent AND packages for the former AND/OR expression."""
    mandatory = [row for row in rows if row.operator == "and"]
    alternatives = {}
    for row in rows:
        if row.operator != "or":
            continue
        if row.alternative_group is None:
            raise RuntimeError(
                f"LessonCost {row.pk} besitzt keine ODER-Gruppe."
            )
        alternatives.setdefault(int(row.alternative_group), []).append(row)
    if not alternatives:
        return [list(rows)]
    return [
        [*mandatory, *chosen]
        for chosen in product(
            *(alternatives[number] for number in sorted(alternatives))
        )
    ]


def migrate_cost_groups(apps, schema_editor):
    """Preserve legacy expressions as OR alternatives of AND packages."""
    alias = schema_editor.connection.alias
    LessonCost = apps.get_model("charsheet", "LessonCost")
    lesson_ids = (
        LessonCost.objects.using(alias)
        .order_by()
        .values_list("lesson_id", flat=True)
        .distinct()
    )
    copy_fields = (
        "lesson_id",
        "cost_type",
        "value",
        "custom_label",
        "description",
        "sort_order",
    )
    for lesson_id in lesson_ids.iterator():
        rows = list(
            LessonCost.objects.using(alias)
            .filter(lesson_id=lesson_id)
            .order_by("sort_order", "id")
        )
        packages = legacy_cost_packages(rows)
        if all(row.operator == "and" for row in rows):
            LessonCost.objects.using(alias).filter(
                lesson_id=lesson_id
            ).update(cost_group=1)
            continue

        migrated = []
        for number, package in enumerate(packages, start=1):
            for source in package:
                values = {
                    field: getattr(source, field) for field in copy_fields
                }
                migrated.append(
                    LessonCost(cost_group=number, **values)
                )
        LessonCost.objects.using(alias).filter(lesson_id=lesson_id).delete()
        LessonCost.objects.using(alias).bulk_create(migrated)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0389_remove_legacy_lesson_requirements")]

    operations = [
        migrations.AddField(
            model_name="lessoncost",
            name="cost_group",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(migrate_cost_groups, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="lessoncost",
            name="operator",
        ),
        migrations.RemoveField(
            model_name="lessoncost",
            name="alternative_group",
        ),
        migrations.AlterField(
            model_name="lessoncost",
            name="cost_group",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text=(
                    "Kosten derselben Gruppe gelten gemeinsam (UND). "
                    "Verschiedene Gruppen sind Alternativen (ODER)."
                ),
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AddConstraint(
            model_name="lessoncost",
            constraint=models.CheckConstraint(
                condition=models.Q(("cost_group__gte", 1)),
                name="lesson_cost_group_gte_1",
            ),
        ),
    ]
