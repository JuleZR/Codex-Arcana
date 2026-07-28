from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


ZONE_FIELDS = (
    "head",
    "face",
    "eyes",
    "neck",
    "torso",
    "organs",
    "soft_tissue",
    "arm_left",
    "hand_left",
    "leg_left",
    "foot_left",
    "arm_right",
    "hand_right",
    "leg_right",
    "foot_right",
)

OLD_MAIN_FIELDS = {
    "head": "rs_head",
    "torso": "rs_torso",
    "arm_left": "rs_arm_left",
    "arm_right": "rs_arm_right",
    "leg_left": "rs_leg_left",
    "leg_right": "rs_leg_right",
}

COMPONENTS = (
    ("helmet", "Helm", Decimal("0.10"), Decimal("0.20"), ("head", "face", "eyes", "neck")),
    ("torso", "Torso", Decimal("0.36"), Decimal("0.30"), ("torso", "organs", "soft_tissue")),
    ("arm_left", "Arm links", Decimal("0.075"), Decimal("0.075"), ("arm_left",)),
    ("arm_right", "Arm rechts", Decimal("0.075"), Decimal("0.075"), ("arm_right",)),
    ("hand_left", "Handschuh links", Decimal("0.03"), Decimal("0.05"), ("hand_left",)),
    ("hand_right", "Handschuh rechts", Decimal("0.03"), Decimal("0.05"), ("hand_right",)),
    ("leg_left", "Bein links", Decimal("0.125"), Decimal("0.075"), ("leg_left",)),
    ("leg_right", "Bein rechts", Decimal("0.125"), Decimal("0.075"), ("leg_right",)),
    ("foot_left", "Schuh links", Decimal("0.04"), Decimal("0.05"), ("foot_left",)),
    ("foot_right", "Schuh rechts", Decimal("0.04"), Decimal("0.05"), ("foot_right",)),
)


def _coverage_defaults(item_name):
    normalized_name = str(item_name or "").casefold()
    covers_face = any(token in normalized_name for token in ("vollplatte", "ritter", "zwergenplatte"))
    covers_eyes = "zwergenplatte" in normalized_name
    covered = {
        "head",
        "neck",
        "torso",
        "organs",
        "soft_tissue",
        "arm_left",
        "hand_left",
        "leg_left",
        "foot_left",
        "arm_right",
        "hand_right",
        "leg_right",
        "foot_right",
    }
    if covers_face:
        covered.add("face")
    if covers_eyes:
        covered.add("eyes")
    return covered


def _unique_component_name(Item, parent_item, label):
    base_name = f"{parent_item.name} – {label}"
    same_catalog = Item.objects.filter(name=base_name)
    if parent_item.catalog_group_id:
        same_catalog = same_catalog.filter(catalog_group_id=parent_item.catalog_group_id)
    else:
        same_catalog = same_catalog.filter(catalog_group__isnull=True)
    if not same_catalog.exists():
        return base_name
    return f"{base_name} (Set {parent_item.pk})"


def migrate_armor_data(apps, schema_editor):
    ArmorStats = apps.get_model("charsheet", "ArmorStats")
    CharacterCreatureItem = apps.get_model("charsheet", "CharacterCreatureItem")
    CharacterItem = apps.get_model("charsheet", "CharacterItem")
    Item = apps.get_model("charsheet", "Item")

    for armor in ArmorStats.objects.select_related("item").all().order_by("pk"):
        item = armor.item
        legacy_zones = {
            zone: int(getattr(armor, old_field, 0) or 0)
            for zone, old_field in OLD_MAIN_FIELDS.items()
        }
        if int(armor.rs_total or 0) > 0:
            covered = _coverage_defaults(item.name)
            armor.is_set = True
            armor.auto_generate_components = True
            armor.zone_rs_overrides = {}
        else:
            covered = {zone for zone, value in legacy_zones.items() if value > 0}
            armor.rs_total = max(legacy_zones.values(), default=1) or 1
            armor.is_set = False
            armor.auto_generate_components = False
            armor.zone_rs_overrides = {
                zone: value
                for zone, value in legacy_zones.items()
                if value > 0
            }
        for zone in ZONE_FIELDS:
            setattr(armor, f"covers_{zone}", zone in covered)
        armor.save(
            update_fields=[
                "rs_total",
                "is_set",
                "auto_generate_components",
                "zone_rs_overrides",
                *(f"covers_{zone}" for zone in ZONE_FIELDS),
            ]
        )

    for model in (CharacterItem, CharacterCreatureItem):
        for instance in model.objects.all().iterator():
            overrides = {
                zone: int(getattr(instance, f"armor_{old_field}_override"))
                for zone, old_field in OLD_MAIN_FIELDS.items()
                if getattr(instance, f"armor_{old_field}_override") is not None
            }
            if overrides:
                instance.armor_zone_rs_overrides = overrides
                instance.save(update_fields=["armor_zone_rs_overrides"])

    for armor in (
        ArmorStats.objects.select_related("item")
        .filter(is_set=True, auto_generate_components=True, parent_set__isnull=True)
        .order_by("pk")
    ):
        parent_item = armor.item
        selected = []
        for component_type, label, weight_share, price_share, zones in COMPONENTS:
            covered_zones = tuple(
                zone
                for zone in zones
                if getattr(armor, f"covers_{zone}", False)
            )
            if covered_zones:
                selected.append((component_type, label, weight_share, price_share, covered_zones))
        total_weight_share = sum((row[2] for row in selected), Decimal("0"))
        total_price_share = sum((row[3] for row in selected), Decimal("0"))

        for component_type, label, weight_share, price_share, covered_zones in selected:
            component_item = Item.objects.create(
                name=_unique_component_name(Item, parent_item, label),
                price=int(
                    (Decimal(parent_item.price) * price_share / total_price_share).quantize(
                        Decimal("1"),
                        rounding=ROUND_HALF_UP,
                    )
                ),
                item_type="armor",
                description=f"Physisches Rüstungsteil des Sets {parent_item.name}.",
                stackable=False,
                is_consumable=False,
                is_magic=False,
                not_buyable=parent_item.not_buyable,
                not_sellable=parent_item.not_sellable,
                default_quality_id=parent_item.default_quality_id,
                weight=(
                    Decimal(parent_item.weight) * weight_share / total_weight_share
                ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                size_class=parent_item.size_class,
                catalog_group_id=parent_item.catalog_group_id,
            )
            component_item.runes.add(*parent_item.runes.all())
            ArmorStats.objects.create(
                item=component_item,
                rs_total=armor.rs_total,
                encumbrance=0,
                min_st=max(1, int(armor.min_st or 1)),
                is_set=False,
                auto_generate_components=False,
                parent_set=armor,
                component_type=component_type,
                zone_rs_overrides={},
                **{
                    f"covers_{zone}": zone in covered_zones
                    for zone in ZONE_FIELDS
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0284_armor_component_schema"),
    ]

    operations = [
        migrations.RunPython(migrate_armor_data, migrations.RunPython.noop),
    ]
