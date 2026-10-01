"""Shared rounding for scaled semantic effects."""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


def round_scaled_value(value, round_up=False, round_down=False):
    """Round halves away from zero by default; overrides use ceiling/floor."""
    if round_up and round_down:
        raise ValueError(
            "Aufrunden und Abrunden schließen sich gegenseitig aus."
        )
    rounding = (
        ROUND_CEILING
        if round_up
        else ROUND_FLOOR if round_down else ROUND_HALF_UP
    )
    return int(Decimal(str(value)).to_integral_value(rounding=rounding))


def round_semantic_value(value, scaling):
    """Normalize explicit flags or legacy input to one of three states."""
    if "round_up" in scaling or "round_down" in scaling:
        return round_scaled_value(
            value,
            scaling.get("round_up", False),
            scaling.get("round_down", False),
        )
    legacy = scaling.get("round_mode")
    return round_scaled_value(value, legacy == "ceil", legacy == "floor")
