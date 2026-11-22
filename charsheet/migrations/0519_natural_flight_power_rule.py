from django.db import migrations


def link_natural_flight(apps, schema_editor):
    skills = apps.get_model("charsheet", "CreatureSpecialSkill")
    rules = apps.get_model("charsheet", "CreaturePowerRule")
    skill = skills.objects.filter(slug="fliegen").first()
    if not skill or rules.objects.filter(special_skill=skill).exists():
        return
    # The shared catalog entry also occurs on supernatural creatures. Limit
    # this price to natural animals; their winged flight costs 25 (p. 475).
    rules.objects.get_or_create(
        key="fliegen-naturliche-tiere",
        defaults={
            "name": "Fliegen: natürliche Tiere mit Flügeln",
            "special_skill": skill,
            "categories": ["T"],
            "formula": "25",
            "official": True,
            "source": "Kompendium, S. 475: Fliegen (mit Flügeln)",
        },
    )


def unlink_natural_flight(apps, schema_editor):
    apps.get_model("charsheet", "CreaturePowerRule").objects.filter(
        key="fliegen-naturliche-tiere",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0518_charactercreature_current_kp")]

    operations = [migrations.RunPython(
        link_natural_flight, unlink_natural_flight,
    )]
