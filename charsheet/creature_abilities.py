"""Existing card catalog entries and their separately maintained MP rules."""

from charsheet.models import (
    CreaturePowerRule,
    CreatureSpecialSkill,
    CreatureTraitDefinition,
    DaemonicPower,
    VampirePower,
)

ABILITY_SOURCES = (
    ("trait", CreatureTraitDefinition, "Vorzüge und Schwächen"),
    ("special_skill", CreatureSpecialSkill, "Besondere Fertigkeiten"),
    ("daemonic_power", DaemonicPower, "Dämonenkräfte"),
    ("vampire_power", VampirePower, "Vampirkräfte"),
)
SOURCE_FIELDS = tuple(row[0] for row in ABILITY_SOURCES)


def ability_catalog():
    rules = list(CreaturePowerRule.objects.select_related(*SOURCE_FIELDS))
    result = {}
    for field, model, group in ABILITY_SOURCES:
        pricing = {
            getattr(rule, field + "_id"): rule
            for rule in rules
            if getattr(rule, field + "_id")
        }
        for entry in model.objects.all().order_by("name"):
            key = f"{field}:{entry.pk}"
            result[key] = {
                "key": key,
                "field": field,
                "entry": entry,
                "group": group,
                "rule": pricing.get(entry.pk),
            }
    return result


def selection_source(rule, selection):
    """Resolve only explicit catalog references; never invent a definition."""
    key = selection.get("catalog_key")
    if key:
        field, _separator, object_id = key.partition(":")
        if field not in SOURCE_FIELDS or not object_id.isdecimal():
            raise ValueError("Ungültiger Katalogeintrag.")
        if getattr(rule, field + "_id") != int(object_id):
            raise ValueError("Machtregel gehört nicht zum Katalogeintrag.")
        return field, getattr(rule, field)
    for field in SOURCE_FIELDS:
        if getattr(rule, field + "_id"):
            return field, getattr(rule, field)
    raise ValueError("Für die Machtregel fehlt die Katalogverknüpfung.")


def catalog_definitions(catalog):
    return [
        {
            "id": key,
            "name": value["entry"].name,
            "categories": value["rule"].categories if value["rule"] else [],
            "parameters": value["rule"].parameters if value["rule"] else {},
            "description": value["entry"].description,
            "formula": value["rule"].formula if value["rule"] else None,
            "source": value["rule"].source if value["rule"] else "",
        }
        for key, value in catalog.items()
    ]
