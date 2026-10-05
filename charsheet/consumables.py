"""Immediate effects caused by consuming inventory items."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from charsheet.models import (
    AlchemicalBrewStats,
    Character,
    ConsumableEffectStats,
    Item,
)


def consumable_stats(item):
    """Prefer dedicated stats, retaining legacy brew data as a fallback."""
    if not item.item_type.is_consumable:
        return None
    try:
        return item.consumableeffectstats
    except ConsumableEffectStats.DoesNotExist:
        pass
    if item.item_type.supports_alchemical_stats:
        try:
            return item.alchemicalbrewstats
        except AlchemicalBrewStats.DoesNotExist:
            pass
    return None


def consumable_rolls(item):
    stats = consumable_stats(item)
    rolls = []
    for effect, label in (("heal_lp", "LP"), ("restore_kp", "KP")):
        count = getattr(stats, f"{effect}_dice_count", 0)
        if count:
            faces = getattr(stats, f"{effect}_dice_faces")
            divisor = getattr(stats, f"{effect}_divisor")
            modifier = getattr(stats, f"{effect}_modifier")
            expression = f"{count}w{faces}"
            if divisor != 1:
                expression += f"/{divisor}"
            if modifier:
                expression += f"+{modifier}"
            rolls.append({
                "key": effect, "count": count, "faces": faces,
                "min": count, "max": count * faces,
                "label": f"{expression} {label}",
            })
    return rolls


def resolve_consumable_effects(item, results=None):
    """Validate every raw dice total before any character mutation."""
    stats = consumable_stats(item)
    values = {
        key: int(getattr(stats, key, 0))
        for key in ("heal_lp", "restore_kp", "heal_wound_grades")
    }
    for roll in consumable_rolls(item):
        raw = (results or {}).get(roll["key"])
        if raw is None or isinstance(raw, bool):
            raise ValidationError("Ein Würfelergebnis fehlt.")
        try:
            total = int(raw)
        except (TypeError, ValueError, OverflowError):
            raise ValidationError("Ungültiges Würfelergebnis.")
        if str(total) != str(raw) or not roll["min"] <= total <= roll["max"]:
            raise ValidationError("Würfelergebnis außerhalb des Bereichs.")
        key = roll["key"]
        divided = Decimal(total) / getattr(stats, f"{key}_divisor")
        values[key] += int(divided.quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )) + getattr(stats, f"{key}_modifier")
    return values


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
    results=None,
) -> dict[str, int]:
    """Apply configured immediate effects of one consumed item."""
    result = {
        "healed_lp": 0,
        "restored_kp": 0,
    }

    values = resolve_consumable_effects(item, results)

    total_healing = max(
        0,
        values["heal_lp"],
    )

    wound_grades = max(
        0,
        values["heal_wound_grades"],
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
        values["restore_kp"],
    )

    if result["restored_kp"]:
        update_fields.add("current_arcane_power")

    if update_fields:
        character.save(
            update_fields=sorted(update_fields)
        )

    return result
