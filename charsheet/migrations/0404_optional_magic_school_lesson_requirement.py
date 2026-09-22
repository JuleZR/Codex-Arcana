from django.db import migrations, models


TARGET_FIELDS = (
    "required_school",
    "required_technique",
    "specialisation",
    "magic_school",
    "druid_circle",
    "creature",
    "required_skill",
    "required_lesson",
    "aspect",
    "required_trait",
    "required_trait_specification",
    "minimum_value",
)


def requirement_shape(kind, required, optional=()):
    condition = models.Q(requirement_type=kind)
    allowed = set(required) | set(optional)
    for field in TARGET_FIELDS:
        if field == "minimum_value":
            if field in required:
                condition &= models.Q(minimum_value__isnull=False)
                condition &= models.Q(minimum_value__gte=1)
            elif field not in optional:
                condition &= models.Q(minimum_value__isnull=True)
        elif field in required:
            condition &= models.Q(**{f"{field}__isnull": False})
        elif field not in allowed:
            condition &= models.Q(**{f"{field}__isnull": True})
    return condition


VALID_FIELDS = (
    requirement_shape(
        "school_technique", ("required_school", "required_technique")
    )
    | requirement_shape(
        "school_specialisation", ("required_school", "specialisation")
    )
    | requirement_shape(
        "magic_school_level", ("minimum_value",), ("magic_school",)
    )
    | requirement_shape("clerical_magic_level", ("minimum_value",))
    | requirement_shape(
        "druid_circle_level", ("druid_circle", "minimum_value")
    )
    | requirement_shape("specific_creature", ("creature",))
    | requirement_shape(
        "school_level", ("required_school", "minimum_value")
    )
    | requirement_shape("skill_level", ("required_skill", "minimum_value"))
    | requirement_shape("lesson", ("required_lesson",))
    | requirement_shape("aspect_level", ("aspect", "minimum_value"))
    | requirement_shape(
        "trait_level",
        ("required_trait", "minimum_value"),
        ("required_trait_specification",),
    )
)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0403_character_npc_fields")]

    operations = [
        migrations.RemoveConstraint(
            model_name="lessonrequirement",
            name="lesson_requirement_valid_fields",
        ),
        migrations.AddConstraint(
            model_name="lessonrequirement",
            constraint=models.CheckConstraint(
                condition=VALID_FIELDS,
                name="lesson_requirement_valid_fields",
            ),
        ),
    ]
