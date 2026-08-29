from django.db import migrations


def migrate_alchemy_requirements(apps, schema_editor):
    AlchemicalBrewStats = apps.get_model(
        "charsheet",
        "AlchemicalBrewStats",
    )
    AlchemicalBrewRequirement = apps.get_model(
        "charsheet",
        "AlchemicalBrewRequirement",
    )
    Skill = apps.get_model(
        "charsheet",
        "Skill",
    )

    alchemy_skill = Skill.objects.get(
        slug="knw_alchemy"
    )

    brews = (
        AlchemicalBrewStats.objects
        .exclude(alchemy_required__isnull=True)
        .exclude(alchemy_required=0)
    )

    for brew in brews:
        AlchemicalBrewRequirement.objects.update_or_create(
            brew_stats_id=brew.pk,
            skill_id=alchemy_skill.pk,
            defaults={
                "required_level": brew.alchemy_required,
                "sort_order": 0,
            },
        )


def reverse_migration(apps, schema_editor):
    AlchemicalBrewStats = apps.get_model(
        "charsheet",
        "AlchemicalBrewStats",
    )
    AlchemicalBrewRequirement = apps.get_model(
        "charsheet",
        "AlchemicalBrewRequirement",
    )
    Skill = apps.get_model(
        "charsheet",
        "Skill",
    )

    alchemy_skill = Skill.objects.get(
        slug="knw_alchemy"
    )

    for requirement in AlchemicalBrewRequirement.objects.filter(
        skill_id=alchemy_skill.pk
    ):
        AlchemicalBrewStats.objects.filter(
            pk=requirement.brew_stats_id
        ).update(
            alchemy_required=requirement.required_level
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "charsheet",
            "0375_add_alchemical_brew_requirements",
        ),
    ]

    operations = [
        migrations.RunPython(
            migrate_alchemy_requirements,
            reverse_migration,
        ),
    ]
