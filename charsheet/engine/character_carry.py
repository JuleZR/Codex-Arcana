"""Optional carrying effects from GRW 3, page 471."""

from charsheet.constants import ATTR_GE, ATTR_KON, ATTR_ST, ATTR_WA

from .item_engine import ItemEngine


CARRY_ATTRIBUTES = frozenset({ATTR_KON, ATTR_GE, ATTR_WA, ATTR_ST})


def carry_penalty(engine, target="initiative", *, attribute=None):
    """Resolve carrying only for affected rolls and the active toggle."""
    if not engine.character.carry_load_enabled:
        return 0
    if target == "skill":
        if attribute not in CARRY_ATTRIBUTES:
            return 0
    elif target not in {"initiative", "spell", "load"}:
        return 0
    if "_carry_state" not in engine.__dict__:
        engine._carry_state = ItemEngine.carry_state_for_character(
            engine.character,
            strength=int(engine.attributes().get(ATTR_ST, 0)),
        )
    return int(engine._carry_state["penalty"])


def skill_carry_penalty(engine, skill_slug):
    """Use the governing attribute, never a translated skill name."""
    skill = engine._skill_definitions_by_slug.get(skill_slug)
    if skill is None:
        return 0
    return engine.carry_penalty("skill", attribute=skill.attribute.short_name)


def natural_flight_blocked_by_load(engine):
    """The optional rule blocks natural flight at combined load -4."""
    return (
        engine.character.carry_load_enabled
        and engine.load_penalty() + engine.carry_penalty("load") <= -4
    )
