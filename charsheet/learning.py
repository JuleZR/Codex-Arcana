"""Learning-menu processing helpers kept outside the view module."""

from __future__ import annotations

from django.db import transaction

from charsheet.attribute_layout import ATTRIBUTE_ORDER
from charsheet.learning_rules import (
    DEFAULT_SCHOOL_MAX_LEVEL,
    calc_attribute_total_cost,
    calc_language_total_cost,
    calc_skill_total_cost,
    school_max_levels,
)
from charsheet.models import (
    Character,
    CharacterAttribute,
    CharacterLanguage,
    CharacterSchool,
    CharacterSkill,
    Language,
    School,
    Skill,
)


def _read_int(post_data, name: str, default: int = 0) -> int:
    """Read one integer from POST-like data with a safe fallback."""
    try:
        return int(post_data.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def process_learning_submission(character: Character, post_data) -> tuple[str, str]:
    """Apply one learning-menu submission and return message level plus text."""
    attribute_limits = {
        limit.attribute.short_name: {
            "min": int(limit.min_value),
            "max": int(limit.max_value),
        }
        for limit in character.race.raceattributelimit_set.select_related("attribute")
    }
    attribute_rows = {
        row.attribute.short_name: row
        for row in CharacterAttribute.objects.filter(character=character).select_related("attribute")
    }
    skill_defs = {skill.slug: skill for skill in Skill.objects.all()}
    skill_rows = {
        row.skill.slug: row
        for row in CharacterSkill.objects.filter(character=character).select_related("skill")
    }
    language_defs = {language.slug: language for language in Language.objects.all()}
    language_rows = {
        row.language.slug: row
        for row in CharacterLanguage.objects.filter(owner=character).select_related("language")
    }
    school_defs = {str(school.id): school for school in School.objects.all()}
    school_rows = {
        str(row.school_id): row
        for row in CharacterSchool.objects.filter(character=character)
    }
    school_level_caps = school_max_levels()

    total_cost = 0
    attr_plan: dict[str, int] = {}
    skill_plan: dict[str, int] = {}
    language_plan: dict[str, dict[str, object]] = {}
    school_plan: dict[str, int] = {}

    if any(key.startswith("learn_adv_target_") for key in post_data.keys()):
        return "error", "Vorteile koennen nicht ueber EP gelernt werden."

    for short_name, bounds in attribute_limits.items():
        key = f"learn_attr_add_{short_name}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_row = attribute_rows.get(short_name)
        base_value = int(base_row.base_value if base_row else 0)
        target_value = base_value + add
        min_value = int(bounds["min"])
        max_value = int(bounds["max"])
        if target_value < min_value:
            return "error", f"{short_name}: Zielwert ist unter dem Minimum."
        if target_value > max_value:
            return "error", f"{short_name}: Zielwert ist ueber dem Maximum."
        if add == 0:
            continue
        step_cost = calc_attribute_total_cost(target_value, max_value) - calc_attribute_total_cost(base_value, max_value)
        total_cost += step_cost
        attr_plan[short_name] = add

    for slug, skill in skill_defs.items():
        key = f"learn_skill_add_{slug}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_value = int(skill_rows.get(slug).level if slug in skill_rows else 0)
        target_value = base_value + add
        if target_value < 0:
            return "error", f"{skill.name}: Zielwert ist unter 0."
        if target_value > 10:
            return "error", f"{skill.name}: Zielwert ist ueber 10."
        if add == 0:
            continue
        step_cost = calc_skill_total_cost(target_value) - calc_skill_total_cost(base_value)
        total_cost += step_cost
        skill_plan[slug] = add

    for slug, language in language_defs.items():
        add_key = f"learn_lang_add_{slug}"
        write_key = f"learn_lang_write_{slug}"
        if add_key not in post_data and write_key not in post_data:
            continue
        add = _read_int(post_data, add_key, 0)
        write_add = str(post_data.get(write_key, "0")).lower() in {"1", "true", "on"}
        base_row = language_rows.get(slug)
        base_level = int(base_row.levels if base_row else 0)
        base_write = bool(base_row.can_write if base_row else False)
        base_mother = bool(base_row.is_mother_tongue if base_row else False)
        target_level = base_level + add
        target_write = base_write or write_add
        if base_mother and target_level != int(language.max_level):
            return "error", f"{language.name}: Muttersprache kann nicht unter Maximallevel reduziert werden."
        if target_level < 0:
            return "error", f"{language.name}: Zielwert ist unter 0."
        if target_level > int(language.max_level):
            return "error", f"{language.name}: Zielwert ist ueber dem Maximum."
        if target_write and target_level < 1:
            return "error", f"{language.name}: Schreiben benoetigt mindestens Level 1."
        if add == 0 and not write_add:
            continue
        step_cost = calc_language_total_cost(target_level, target_write, base_mother) - calc_language_total_cost(base_level, base_write, base_mother)
        total_cost += step_cost
        language_plan[slug] = {"add": add, "write_add": write_add}

    for school_id, school in school_defs.items():
        key = f"learn_school_add_{school_id}"
        if key not in post_data:
            continue
        add = _read_int(post_data, key, 0)
        base_level = int(school_rows.get(school_id).level if school_id in school_rows else 0)
        target_level = base_level + add
        max_level = max(base_level, int(school_level_caps.get(int(school_id), DEFAULT_SCHOOL_MAX_LEVEL)))
        if target_level < 0:
            return "error", f"{school.name}: Zielwert ist unter 0."
        if target_level > max_level:
            return "error", f"{school.name}: Zielwert ist ueber dem Maximum."
        if add == 0:
            continue
        total_cost += add * 8
        school_plan[school_id] = add

    if total_cost == 0:
        return "info", "Keine Lernkosten erkannt."

    if total_cost > int(character.current_experience):
        return "error", "Nicht genug aktuelle EP fuer diese Lernkosten."

    with transaction.atomic():
        for short_name, add in attr_plan.items():
            attr_row = attribute_rows.get(short_name)
            if attr_row is None:
                continue
            attr_row.base_value = int(attr_row.base_value) + add
            attr_row.save(update_fields=["base_value"])

        for slug, add in skill_plan.items():
            skill = skill_defs[slug]
            skill_row = skill_rows.get(slug)
            if skill_row is None:
                if add <= 0:
                    continue
                skill_row = CharacterSkill.objects.create(character=character, skill=skill, level=add)
                skill_rows[slug] = skill_row
            else:
                target_level = int(skill_row.level) + add
                if target_level <= 0:
                    skill_row.delete()
                    skill_rows.pop(slug, None)
                else:
                    skill_row.level = target_level
                    skill_row.save(update_fields=["level"])

        for slug, payload in language_plan.items():
            add = int(payload["add"])
            write_add = bool(payload["write_add"])
            language_row = language_rows.get(slug)
            if language_row is None:
                if add < 1:
                    continue
                language_row = CharacterLanguage.objects.create(
                    owner=character,
                    language=language_defs[slug],
                    levels=add,
                    can_write=write_add,
                    is_mother_tongue=False,
                )
                language_rows[slug] = language_row
            else:
                target_level = int(language_row.levels) + add
                target_write = bool(language_row.can_write) or write_add
                if target_level <= 0 and not target_write and not bool(language_row.is_mother_tongue):
                    language_row.delete()
                    language_rows.pop(slug, None)
                    continue
                language_row.levels = target_level
                if write_add:
                    language_row.can_write = True
                language_row.save(update_fields=["levels", "can_write"])

        for school_id, add in school_plan.items():
            school_row = school_rows.get(school_id)
            if school_row is None:
                if add <= 0:
                    continue
                school_row = CharacterSchool.objects.create(
                    character=character,
                    school=school_defs[school_id],
                    level=add,
                )
                school_rows[school_id] = school_row
            else:
                target_level = int(school_row.level) + add
                if target_level <= 0:
                    school_row.delete()
                    school_rows.pop(school_id, None)
                else:
                    school_row.level = target_level
                    school_row.save(update_fields=["level"])

        character.current_experience = max(0, int(character.current_experience) - total_cost)
        character.save(update_fields=["current_experience"])

    if total_cost > 0:
        return "success", f"Lernen abgeschlossen: {total_cost} EP ausgegeben."
    return "success", f"Lernen abgeschlossen: {-total_cost} EP gutgeschrieben."
