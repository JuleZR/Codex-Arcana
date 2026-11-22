"""Link winged flight to its full official category list."""

from django.db import migrations


def link_catalog_flight(apps, schema_editor):
    rules = apps.get_model("charsheet", "CreaturePowerRule")
    skills = apps.get_model("charsheet", "CreatureSpecialSkill")
    creations = apps.get_model("charsheet", "CreatureCreation")
    flight = skills.objects.filter(slug="fliegen").first()
    winged = rules.objects.filter(key="fliegen-mit-flugeln").first()
    limited = rules.objects.filter(key="fliegen-naturliche-tiere").first()
    if not flight or not winged:
        return
    allowed_ids = [winged.pk, *([limited.pk] if limited else [])]
    if rules.objects.filter(special_skill=flight).exclude(
        pk__in=allowed_ids,
    ).exists():
        return
    if limited:
        rules.objects.filter(pk=limited.pk, special_skill=flight).update(
            special_skill=None,
        )
        for creation in creations.objects.only("pk", "rules").iterator():
            changed = False
            for selection in creation.rules.get("abilities", []):
                if str(selection.get("rule")) == str(limited.pk):
                    selection["rule"] = winged.pk
                    changed = True
            if changed:
                creation.save(update_fields=["rules"])
    rules.objects.filter(pk=winged.pk).update(special_skill=flight)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0519_natural_flight_power_rule")]

    operations = [migrations.RunPython(
        link_catalog_flight, migrations.RunPython.noop,
    )]
