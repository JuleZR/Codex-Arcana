from django.db import migrations
from django.db.models import F


def correct_builder_scores(apps, schema_editor):
    creation_model = apps.get_model("charsheet", "CreatureCreation")
    attribute_model = apps.get_model("charsheet", "CreatureAttribute")
    database = schema_editor.connection.alias
    for creation in (
        creation_model.objects.using(database)
        .filter(released=True, creature__isnull=False)
        .iterator()
    ):
        rules = dict(creation.rules)
        if rules.get("attribute_storage") == "score":
            continue
        attribute_model.objects.using(database).filter(
            creature_id=creation.creature_id,
            base_value__isnull=False,
            attribute__short_name__in=(
                "ST",
                "KON",
                "GE",
                "INT",
                "WA",
                "WILL",
                "CHA",
            ),
        ).update(base_value=F("base_value") + 5)
        rules["attribute_storage"] = "score"
        rules["attribute_storage_repaired"] = True
        creation.rules = rules
        creation.save(using=database, update_fields=["rules"])


def restore_builder_bonuses(apps, schema_editor):
    creation_model = apps.get_model("charsheet", "CreatureCreation")
    attribute_model = apps.get_model("charsheet", "CreatureAttribute")
    database = schema_editor.connection.alias
    for creation in (
        creation_model.objects.using(database)
        .filter(released=True, creature__isnull=False)
        .iterator()
    ):
        rules = dict(creation.rules)
        if not rules.pop("attribute_storage_repaired", False):
            continue
        attribute_model.objects.using(database).filter(
            creature_id=creation.creature_id,
            base_value__isnull=False,
            attribute__short_name__in=(
                "ST",
                "KON",
                "GE",
                "INT",
                "WA",
                "WILL",
                "CHA",
            ),
        ).update(base_value=F("base_value") - 5)
        rules.pop("attribute_storage", None)
        creation.rules = rules
        creation.save(using=database, update_fields=["rules"])


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0516_creature_power_catalog_links")]
    operations = [
        migrations.RunPython(correct_builder_scores, restore_builder_bonuses)
    ]
