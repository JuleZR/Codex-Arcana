from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


COMPONENT_PRICE_SHARES = (
    ("helmet", Decimal("0.20")),
    ("torso", Decimal("0.30")),
    ("arm_left", Decimal("0.075")),
    ("arm_right", Decimal("0.075")),
    ("hand_left", Decimal("0.05")),
    ("hand_right", Decimal("0.05")),
    ("leg_left", Decimal("0.075")),
    ("leg_right", Decimal("0.075")),
    ("foot_left", Decimal("0.05")),
    ("foot_right", Decimal("0.05")),
)


def reprice_armor_components(apps, schema_editor):
    """Apply literal rulebook shares instead of normalizing partial sets."""
    ArmorStats = apps.get_model("charsheet", "ArmorStats")

    roots = (
        ArmorStats.objects.select_related("item")
        .filter(parent_set__isnull=True)
        .order_by("pk")
    )
    for armor in roots:
        component_by_type = {
            component.component_type: component
            for component in armor.components.select_related("item")
        }
        selected = [
            (component_type, share, component_by_type[component_type])
            for component_type, share in COMPONENT_PRICE_SHARES
            if component_type in component_by_type
        ]
        if not selected:
            continue

        total_share = sum((share for _component_type, share, _component in selected), Decimal("0"))
        prices = [
            int(
                (Decimal(armor.item.price) * share).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )
            for _component_type, share, _component in selected
        ]
        target_total = int(
            (Decimal(armor.item.price) * total_share).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        prices[-1] += target_total - sum(prices)

        for price, (_component_type, _share, component) in zip(prices, selected, strict=True):
            if component.item.price == price:
                continue
            component.item.price = price
            component.item.save(update_fields=["price"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0287_armor_component_generation_opt_out"),
    ]

    operations = [
        migrations.RunPython(reprice_armor_components, migrations.RunPython.noop),
    ]
