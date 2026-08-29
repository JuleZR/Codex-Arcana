"""Immediate effects caused by consuming inventory items."""

from __future__ import annotations

from charsheet.models import (
    AlchemicalBrewStats,
    Character,
    Item,
)


def _restore_kp(
    character: Character,
    amount: int,
) -> int:
    """Restore ordinary arcane power and return the restored amount."""
    amount = max(0, int(amount or 0))

    if amount == 0:
        return 0

    # Vampire blood is not KP and is deliberately not restored here.
    if character.is_vampire:
        return 0

    calculated_maximum = max(
        0,
        int(
            character
            .get_engine(refresh=True)
            .calculate_arcane_power()
        ),
    )

    current = character.current_arcane_power

    if current is None:
        current = calculated_maximum

    current = max(0, int(current))

    # Keep the same cap behavior as the existing KP controls.
    maximum = max(
        calculated_maximum,
        current,
    )

    restored_value = min(
        maximum,
        current + amount,
    )

    restored = restored_value - current

    character.current_arcane_power = restored_value

    return restored


def apply_consumable_effects(
    character: Character,
    item: Item,
) -> dict[str, int]:
    """Apply configured immediate effects of one consumed item."""
    result = {
        "healed_lp": 0,
        "restored_kp": 0,
    }

    if item.item_type != Item.ItemType.ALCHEMICAL_BREW:
        return result

    try:
        stats = item.alchemicalbrewstats
    except AlchemicalBrewStats.DoesNotExist:
        return result

    total_healing = max(
        0,
        int(stats.heal_lp or 0),
    )

    wound_grades = max(
        0,
        int(stats.heal_wound_grades or 0),
    )

    if wound_grades:
        total_healing += (
            character.wound_grade_life_points()
            * wound_grades
        )

    update_fields = set()

    if total_healing:
        result["healed_lp"] = character.heal_life_points(
            total_healing
        )

        if result["healed_lp"]:
            update_fields.update({
                "current_stun_damage",
                "current_lethal_damage",
            })

    result["restored_kp"] = _restore_kp(
        character,
        stats.restore_kp,
    )

    if result["restored_kp"]:
        update_fields.add("current_arcane_power")

    if update_fields:
        character.save(
            update_fields=sorted(update_fields)
        )

    return result
