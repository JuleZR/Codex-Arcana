"""Category entitlement and exact total-value pricing for natural survival."""

from charsheet.models import CreatureCategoryRule
from charsheet.constants import GK_MODS


def survival_entitled(category):
    return CreatureCategoryRule.objects.filter(
        category=category, grants_natural_survival=True
    ).exists()


def is_survival(skill):
    return bool(
        skill
        and (
            skill.slug == "skill_survival"
            or "überleben" in skill.name.casefold()
        )
    )


def skill_prices(creature, rows, category, preferred=(), attributes=None):
    """Price one free total of 6; never treat it as six free skill ranks."""
    from charsheet.engine.creature_engine import CreatureEngine

    entitled = survival_entitled(category)
    candidates = [
        row for row in rows if row.skill_id and is_survival(row.skill)
    ]
    preferred = set(map(str, preferred))
    chosen = (
        next(
            (row for row in candidates if str(row.pk) in preferred),
            candidates[0] if candidates else None,
        )
        if entitled
        else None
    )
    engine = CreatureEngine(creature) if creature.pk else None
    prices = []
    for row in rows:
        attribute_bonus = 0
        size_bonus = 0
        other_bonus = 0
        code = ""
        if row.skill_id:
            skill = row.skill
            code = skill.attribute.short_name if skill.attribute_id else ""
            if attributes is not None:
                # Inputs from step 4 already are bonuses, not scores.
                attribute_bonus = attributes.get(code) or 0
                if engine:
                    attribute_bonus += engine._modifier_total(
                        "attribute", code
                    )
                    attribute_bonus += int(
                        engine.attribute_increase_totals.get(code, 0) or 0
                    )
            elif engine:
                attribute_bonus = engine._skill_attribute_modifier(skill)
            if engine:
                size_bonus = engine._skill_size_modifier(skill)
                other_bonus += engine._modifier_total(
                    "skill_category", skill.category.slug
                )
                other_bonus += engine._modifier_total("skill", skill.slug)
            else:
                size_bonus = CreatureEngine._skill_size_bonus(
                    skill, int(GK_MODS.get(creature.size_class, 0))
                )
        base = attribute_bonus + size_bonus + other_bonus
        free = row is chosen
        level = row.level
        if free:
            level = max(level, 6 - row.deviation - base)
        paid = level + row.deviation
        if free:
            paid = max(0, paid - max(0, 6 - base))
        prices.append(
            {
                "row": row,
                "level": level,
                "total": level + row.deviation + base,
                "paid_level": paid,
                "natural_survival": free,
                "attribute": code,
                "attribute_bonus": attribute_bonus,
                "size_bonus": size_bonus,
                "other_bonus": other_bonus,
            }
        )
    return entitled, prices


def apply_survival_floor(creature, rules):
    """Persist missing ranks after attributes and traits have been saved."""
    rows = list(
        creature.skills.select_related("skill__attribute", "skill__category")
    )
    _entitled, prices = skill_prices(
        creature, rows, rules.get("category"), rules.get("free_survival", [])
    )
    rules["free_survival"] = []
    for price in prices:
        if price["natural_survival"]:
            row = price["row"]
            rules["free_survival"].append(str(row.pk))
            if row.level < price["level"]:
                row.level = price["level"]
                row.save(update_fields=["level"])
