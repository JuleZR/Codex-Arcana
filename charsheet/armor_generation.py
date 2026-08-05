"""Generate physical armor component items from armor-set definitions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction

from charsheet.models import ArmorStats, Item


@dataclass(frozen=True)
class ArmorComponentBlueprint:
    """One physical component generated from an armor set."""

    component_type: str
    label: str
    weight_share: Decimal
    price_share: Decimal
    zones: tuple[str, ...]


ARMOR_COMPONENT_BLUEPRINTS = (
    ArmorComponentBlueprint("helmet", "Helm", Decimal("0.10"), Decimal("0.20"), ("head", "face", "eyes", "neck")),
    ArmorComponentBlueprint("torso", "Torso", Decimal("0.36"), Decimal("0.30"), ("torso", "organs", "soft_tissue")),
    ArmorComponentBlueprint("arm_left", "Arm links", Decimal("0"), Decimal("0"), ("arm_left", "hand_left")),
    ArmorComponentBlueprint("arm_right", "Arm rechts", Decimal("0"), Decimal("0"), ("arm_right", "hand_right")),
    ArmorComponentBlueprint("leg_left", "Bein links", Decimal("0"), Decimal("0"), ("leg_left", "foot_left")),
    ArmorComponentBlueprint("leg_right", "Bein rechts", Decimal("0"), Decimal("0"), ("leg_right", "foot_right")),
)


ZONE_COMPONENT_SHARES = {
    "arm_left": (Decimal("0.075"), Decimal("0.075")),
    "arm_right": (Decimal("0.075"), Decimal("0.075")),
    "hand_left": (Decimal("0.03"), Decimal("0.05")),
    "hand_right": (Decimal("0.03"), Decimal("0.05")),
    "leg_left": (Decimal("0.125"), Decimal("0.075")),
    "leg_right": (Decimal("0.125"), Decimal("0.075")),
    "foot_left": (Decimal("0.04"), Decimal("0.05")),
    "foot_right": (Decimal("0.04"), Decimal("0.05")),
}

ZONE_PRICE_OVERRIDE_FIELDS = {
    "arm_left": "component_price_arms_override",
    "arm_right": "component_price_arms_override",
    "hand_left": "component_price_hands_override",
    "hand_right": "component_price_hands_override",
    "leg_left": "component_price_legs_override",
    "leg_right": "component_price_legs_override",
    "foot_left": "component_price_feet_override",
    "foot_right": "component_price_feet_override",
}


def _selected_blueprints(
    armor: ArmorStats,
) -> list[tuple[ArmorComponentBlueprint, tuple[str, ...], Decimal, Decimal]]:
    selected: list[tuple[ArmorComponentBlueprint, tuple[str, ...], Decimal, Decimal]] = []
    for blueprint in ARMOR_COMPONENT_BLUEPRINTS:
        covered_zones = tuple(
            zone
            for zone in blueprint.zones
            if getattr(armor, f"covers_{zone}", False)
        )
        if covered_zones:
            if blueprint.component_type.startswith(("arm_", "leg_")):
                weight_share = sum(
                    (ZONE_COMPONENT_SHARES[zone][0] for zone in covered_zones),
                    Decimal("0"),
                )
                price_share = sum(
                    (ZONE_COMPONENT_SHARES[zone][1] for zone in covered_zones),
                    Decimal("0"),
                )
            else:
                weight_share = blueprint.weight_share
                price_share = blueprint.price_share
            selected.append((blueprint, covered_zones, weight_share, price_share))
    return selected


def _component_name(parent_name: str, label: str) -> str:
    """Return a stable, editable physical item name."""
    return f"{parent_name} – {label}"


def _has_external_references(component_item: Item) -> bool:
    """Return whether deleting a generated item would remove other game data."""
    for relation in component_item._meta.related_objects:
        if relation.related_model is ArmorStats and relation.field.name == "item":
            continue
        accessor_name = relation.get_accessor_name()
        if not accessor_name:
            continue
        try:
            related = getattr(component_item, accessor_name)
        except ObjectDoesNotExist:
            continue
        if relation.one_to_one:
            return True
        if related.exists():
            return True
    return False


@transaction.atomic
def sync_armor_set_components(armor: ArmorStats) -> list[Item]:
    """Create or update physical base items for one armor-set definition.

    CharacterItem overrides are intentionally outside this routine. Generated
    components always derive from the catalog/group base item only.
    """
    if (
        not armor.pk
        or armor.item.item_type != Item.ItemType.ARMOR
        or armor.parent_set_id
    ):
        return []

    if armor.suppress_component_generation:
        return []

    parent_item = armor.item
    selected = _selected_blueprints(armor)
    selected_types = {
        blueprint.component_type
        for blueprint, _zones, _weight_share, _price_share in selected
    }
    existing_components = {
        component.component_type: component
        for component in armor.components.select_related("item")
    }

    stale_components = [
        component
        for component_type, component in existing_components.items()
        if component_type not in selected_types
    ]
    blocked_items = [
        component.item.name
        for component in stale_components
        if _has_external_references(component.item)
    ]
    if blocked_items:
        raise ValidationError(
            {
                "suppress_component_generation": (
                    "Diese erzeugten Rüstungsteile werden bereits verwendet und können "
                    f"nicht automatisch entfernt werden: {', '.join(blocked_items)}"
                )
            }
        )

    total_weight_share = sum(
        (weight_share for _entry, _zones, weight_share, _price_share in selected),
        Decimal("0"),
    )
    component_weights = [
        (Decimal(parent_item.weight) * weight_share / total_weight_share).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )
        for _blueprint, _zones, weight_share, _price_share in selected
    ]
    override_zone_counts = {
        field_name: sum(
            1
            for _blueprint, covered_zones, _weight_share, _price_share in selected
            for zone in covered_zones
            if ZONE_PRICE_OVERRIDE_FIELDS.get(zone) == field_name
        )
        for field_name in set(ZONE_PRICE_OVERRIDE_FIELDS.values())
    }
    raw_component_prices: list[Decimal] = []
    for blueprint, covered_zones, _weight_share, _price_share in selected:
        if blueprint.component_type == "helmet":
            override = armor.component_price_helmet_override
            raw_price = (
                Decimal(override)
                if override is not None
                else Decimal(parent_item.price) * blueprint.price_share
            )
        elif blueprint.component_type == "torso":
            override = armor.component_price_torso_override
            raw_price = (
                Decimal(override)
                if override is not None
                else Decimal(parent_item.price) * blueprint.price_share
            )
        else:
            raw_price = Decimal("0")
            for zone in covered_zones:
                override_field = ZONE_PRICE_OVERRIDE_FIELDS[zone]
                override = getattr(armor, override_field)
                if override is None:
                    raw_price += Decimal(parent_item.price) * ZONE_COMPONENT_SHARES[zone][1]
                else:
                    raw_price += Decimal(override) / override_zone_counts[override_field]
        raw_component_prices.append(raw_price)
    component_prices = [
        int(raw_price.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        for raw_price in raw_component_prices
    ]
    if selected:
        component_weights[-1] += Decimal(parent_item.weight) - sum(component_weights, Decimal("0"))
        target_component_price = int(
            sum(raw_component_prices, Decimal("0")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        component_prices[-1] += target_component_price - sum(component_prices)

    generated_items: list[Item] = []

    for index, (blueprint, covered_zones, _weight_share, _price_share) in enumerate(selected):
        component_stats = existing_components.get(blueprint.component_type)
        if component_stats is None:
            component_item = Item(
                name=_component_name(parent_item.name, blueprint.label),
                price=0,
                item_type=Item.ItemType.ARMOR,
                description=f"Physisches Rüstungsteil des Sets {parent_item.name}.",
                stackable=False,
                is_consumable=False,
                is_magic=False,
                not_buyable=parent_item.not_buyable,
                not_sellable=parent_item.not_sellable,
                default_quality=parent_item.default_quality,
                weight=Decimal("0"),
                size_class=parent_item.size_class,
                catalog_group=parent_item.catalog_group,
            )
        else:
            component_item = component_stats.item

        component_item.name = _component_name(parent_item.name, blueprint.label)
        component_item.description = f"Physisches Rüstungsteil des Sets {parent_item.name}."
        component_item.weight = component_weights[index]
        component_item.price = component_prices[index]
        component_item.item_type = Item.ItemType.ARMOR
        component_item.stackable = False
        component_item.is_consumable = False
        component_item.is_magic = False
        component_item.not_buyable = parent_item.not_buyable
        component_item.not_sellable = parent_item.not_sellable
        component_item.default_quality = parent_item.default_quality
        component_item.size_class = parent_item.size_class
        component_item.catalog_group = parent_item.catalog_group
        component_item.full_clean()
        component_item.save()

        coverage_updates = {
            f"covers_{zone}": zone in covered_zones
            for zone in ArmorStats.ZONE_FIELDS
        }
        if component_stats is None:
            component_stats = ArmorStats(
                item=component_item,
                rs_total=armor.rs,
                encumbrance=0,
                min_st=max(1, armor.min_st),
                suppress_component_generation=True,
                parent_set=armor,
                component_type=blueprint.component_type,
                **coverage_updates,
            )
        else:
            component_stats.rs_total = armor.rs
            component_stats.encumbrance = 0
            component_stats.min_st = max(1, armor.min_st)
        component_stats.zone_rs_overrides = {
            zone: value
            for zone, value in (armor.zone_rs_overrides or {}).items()
            if zone in covered_zones
        }
        if component_stats.pk:
            for field_name, value in coverage_updates.items():
                setattr(component_stats, field_name, value)
        component_stats.full_clean()
        component_stats.save()
        component_item.runes.set(parent_item.runes.all())
        generated_items.append(component_item)

    for component in stale_components:
        component.item.delete()

    return generated_items
