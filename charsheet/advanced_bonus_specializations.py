"""Configured, target-specific bonus progress without school or power grants.

ProgressionRule.params names a technique, effect_ids, increment, maximum,
initial_value, ep_cost, allow_new and options ({target, label, skill_id}).
normal_first_level/normal_initial_value/normal_every/normal_increment describe
the level 1-10 pattern and bound the maximum. source_technique_ids can group
repeated selections of the same technique without merging their bonuses.
"""

from dataclasses import replace
from hashlib import sha256

from django.core.exceptions import ValidationError

from charsheet.constants import SCHOOL_COMBAT
from charsheet.models import (
    CharacterAdvancedBonus,
    ProgressionRule,
    Skill,
    Technique,
    TechniqueSemanticEffect,
)

GRANT_KIND = "advanced_bonus"
PREFIX = "learn_advanced_bonus_"


def normal_value(configuration, level):
    first = configuration["normal_first_level"]
    if level < first:
        return 0
    return configuration["normal_initial_value"] + (
        (min(level, 10) - first)
        // configuration["normal_every"]
        * configuration["normal_increment"]
    )


def configured_options(character):
    engine = character.get_engine(refresh=True)
    result = {}
    for rule in ProgressionRule.objects.filter(grant_kind=GRANT_KIND):
        params = rule.params
        if not isinstance(params, dict):
            continue
        technique = (
            Technique.objects.select_related("school__type")
            .filter(
                pk=params.get("technique_id"),
                school__type_id=rule.school_type_id,
            )
            .first()
        )
        if technique is None:
            continue
        school = technique.school
        if school.type.slug not in {SCHOOL_COMBAT, "school_combat"}:
            continue
        if school.name.casefold() in {"waffenmeister", "weaponsmaster"}:
            continue
        if engine.school_level(school) < rule.min_level:
            continue
        state = engine.technique_state(technique)
        if not state["available"] or not state["learned"]:
            continue
        numbers = {
            key: params.get(key, default)
            for key, default in {
                "ep_cost": 10,
                "increment": 1,
                "maximum": 10,
                "initial_value": 1,
                "normal_first_level": 1,
                "normal_every": 1,
                "normal_increment": 1,
                "normal_initial_value": params.get("initial_value", 1),
            }.items()
        }
        if any(
            type(value) is not int or value < 1 for value in numbers.values()
        ):
            continue
        if numbers["normal_first_level"] > 10:
            continue
        normal_maximum = normal_value(numbers, 10)
        maximum = min(numbers["maximum"], normal_maximum)
        effects = list(
            TechniqueSemanticEffect.objects.filter(
                pk__in=params.get("effect_ids", []),
                technique=technique,
                active_flag=True,
                operator="flat_add",
                target_domain__in=["skill", "combat", "damage"],
            )
        )
        if not effects:
            continue
        bonus_type = params.get(
            "bonus_type",
            (
                "paired"
                if any(
                    effect.target_key == "weapon_maneuver_damage"
                    for effect in effects
                )
                else "single"
            ),
        )
        if bonus_type not in {"single", "paired"}:
            continue
        source_ids = params.get("source_technique_ids", [technique.pk])
        source_ids = list(
            Technique.objects.filter(
                pk__in=source_ids,
                school=school,
            ).values_list("pk", flat=True)
        )
        owned = {}
        for choice in character.technique_choices.filter(
            technique_id__in=source_ids,
        ).select_related("selected_skill", "definition"):
            if choice.selected_skill_id:
                target = f"skill:{choice.selected_skill_id}"
            elif choice.selected_text:
                target = "text:" + choice.selected_text.strip().casefold()
            else:
                continue
            owned[target] = {
                "target": target,
                "label": choice.selected_target_display(),
                "skill_id": choice.selected_skill_id,
            }
        for entry in character.learned_techniques.filter(
            technique_id__in=source_ids,
        ):
            label = entry.specification_value.strip()
            if label and label != "*":
                target = "text:" + label.casefold()
                owned[target] = {"target": target, "label": label}
        persisted = {
            entry.target: entry
            for entry in character.advanced_bonuses.filter(
                technique=technique,
            )
        }
        selections = dict(owned)
        selections.update(
            {
                target: {"target": target, "label": entry.label}
                for target, entry in persisted.items()
            }
        )
        if params.get("allow_new", False):
            for option in params.get("options", []):
                if isinstance(option, dict) and option.get("target"):
                    selections.setdefault(option["target"], option)
        for target, selection in sorted(selections.items()):
            entry = persisted.get(target)
            base = (
                normal_value(numbers, engine.school_level(school))
                if target in owned
                else 0
            )
            value = max(entry.value, base) if entry else base
            new = entry is None and not base
            if new:
                next_value = numbers["initial_value"]
            else:
                next_value = value + numbers["increment"]
            if next_value > maximum:
                continue
            skill_id = selection.get("skill_id")
            if target.startswith("skill:"):
                try:
                    skill_id = int(target.removeprefix("skill:"))
                except ValueError:
                    continue
                skill = Skill.objects.filter(pk=skill_id).first()
                if skill is None:
                    continue
                definitions = technique.choice_definitions.filter(
                    is_active=True,
                    target_kind="skill",
                )
                if definitions.exists() and not any(
                    (
                        not definition.allowed_skill_category_id
                        or definition.allowed_skill_category_id
                        == skill.category_id
                    )
                    and (
                        not definition.allowed_skill_family
                        or definition.allowed_skill_family == skill.family
                    )
                    for definition in definitions
                ):
                    continue
            key = (
                f"{rule.pk}_{sha256(target.encode('utf-8')).hexdigest()[:16]}"
            )
            result[key] = {
                "key": key,
                "technique": technique,
                "entry": entry,
                "target": target,
                "label": selection.get("label", target),
                "school_name": school.name,
                "name": technique.name,
                "paired": bonus_type == "paired",
                "cost": numbers["ep_cost"],
                "value": value,
                "next_value": next_value,
                "base_value": base,
                "max_steps": (maximum - next_value) // numbers["increment"]
                + 1,
                "configuration": {
                    "required_level": int(rule.min_level),
                    "bonus_type": bonus_type,
                    "increment": numbers["increment"],
                    "maximum": maximum,
                    "effect_ids": [effect.pk for effect in effects],
                    "skill_id": skill_id,
                    "normal_pattern": numbers,
                    "source_technique_ids": source_ids,
                },
            }
        if params.get("allow_new") and params.get("allow_free_text"):
            key = f"new_{rule.pk}"
            result[key] = {
                "key": key,
                "technique": technique,
                "entry": None,
                "target": "",
                "label": "Neue Spezialisierung",
                "school_name": school.name,
                "name": technique.name,
                "paired": bonus_type == "paired",
                "cost": numbers["ep_cost"],
                "value": 0,
                "next_value": numbers["initial_value"],
                "base_value": 0,
                "max_steps": (maximum - numbers["initial_value"])
                // numbers["increment"]
                + 1,
                "text_field": f"advanced_bonus_target_{rule.pk}",
                "owned_targets": list(selections),
                "configuration": {
                    "required_level": int(rule.min_level),
                    "bonus_type": bonus_type,
                    "increment": numbers["increment"],
                    "maximum": maximum,
                    "effect_ids": [effect.pk for effect in effects],
                    "skill_id": None,
                    "normal_pattern": numbers,
                    "source_technique_ids": source_ids,
                },
            }
    return result


def learning_context(character):
    options = list(configured_options(character).values())
    for option in options:
        if (
            option["school_name"] == "Bardenschule"
            and option["name"] == "Musisches Talent"
        ):
            option["name"] = "Musikalisches Talent"
    return {
        "learn_advanced_bonus_options": sorted(
            options,
            key=lambda option: (
                option["school_name"], option["name"], option["label"],
            ),
        )
    }


def plan_submission(character, post_data, school_levels):
    options = configured_options(character)
    updates = []
    removals = []
    for entry in character.advanced_bonuses.select_related("technique"):
        if school_levels.get(str(entry.technique.school_id), 0) < (
            entry.configuration["required_level"]
        ):
            removals.append(entry)
    cost = -sum(sum(entry.purchases) for entry in removals)
    selected = set()
    for field in post_data:
        if not str(field).startswith(PREFIX):
            continue
        try:
            count = int(post_data.get(field, 0))
        except (TypeError, ValueError):
            raise ValidationError("Ungültige Bonussteigerung.")
        if not count:
            continue
        option = options.get(str(field).removeprefix(PREFIX))
        if option is None or not 1 <= count <= option["max_steps"]:
            raise ValidationError("Bonussteigerung nicht verfügbar.")
        option = dict(option)
        if option.get("text_field"):
            label = " ".join(
                str(post_data.get(option["text_field"], "")).split()
            )
            target = "text:" + label.casefold()
            if (
                not label
                or len(label) > 100
                or target in option["owned_targets"]
            ):
                raise ValidationError(
                    "Ungültige oder bereits gewählte Spezialisierung."
                )
            option.update(target=target, label=label)
        technique = option["technique"]
        if school_levels.get(str(technique.school_id), 0) < (
            option["configuration"]["required_level"]
        ):
            raise ValidationError(
                "Die erforderliche Schulstufe ist nicht erreicht."
            )
        identity = (technique.pk, option["target"])
        if identity in selected:
            raise ValidationError("Doppelte Bonussteigerung.")
        selected.add(identity)
        updates.append((option, count))
        cost += option["cost"] * count
    return updates, removals, cost


def apply_submission(character, updates, removals):
    for entry in removals:
        entry.delete()
    for option, count in updates:
        current = next(
            (
                row
                for row in configured_options(character).values()
                if row["technique"].pk == option["technique"].pk
                and (
                    row["target"] == option["target"]
                    or row.get("text_field") == option.get("text_field")
                    and option.get("text_field")
                )
            ),
            None,
        )
        if current is None or count > current["max_steps"]:
            raise ValidationError(
                "Voraussetzungen der Bonussteigerung nicht erfüllt."
            )
        entry = option["entry"] or CharacterAdvancedBonus(
            character=character,
            technique=option["technique"],
            target=option["target"],
            label=option["label"],
            base_value=option["base_value"],
        )
        entry.value = (
            option["next_value"]
            + (count - 1) * option["configuration"]["increment"]
        )
        entry.purchases = [*entry.purchases, *([option["cost"]] * count)]
        entry.configuration = option["configuration"]
        entry.full_clean()
        entry.save()


def modifiers(engine):
    """Reuse owning effects and conditions for this target's progress."""
    for entry in engine.character.advanced_bonuses.select_related("technique"):
        state = engine.technique_state(entry.technique)
        if (
            engine.school_level(entry.technique.school_id)
            < entry.configuration["required_level"]
            or not state["available"]
            or not state["learned"]
        ):
            continue
        source_ids = entry.configuration["source_technique_ids"]
        if entry.target.startswith("skill:"):
            normally_owned = engine.character.technique_choices.filter(
                technique_id__in=source_ids,
                selected_skill_id=entry.configuration["skill_id"],
            ).exists()
        else:
            normally_owned = (
                engine.character.technique_choices.filter(
                    technique_id__in=source_ids,
                    selected_text__iexact=entry.label,
                ).exists()
                or engine.character.learned_techniques.filter(
                    technique_id__in=source_ids,
                    specification_value__iexact=entry.label,
                ).exists()
            )
        base = (
            normal_value(
                entry.configuration["normal_pattern"],
                engine.school_level(entry.technique.school_id),
            )
            if normally_owned
            else 0
        )
        if entry.value <= base:
            continue
        for effect in TechniqueSemanticEffect.objects.filter(
            pk__in=entry.configuration["effect_ids"],
            technique=entry.technique,
            active_flag=True,
            target_domain__in=["skill", "combat", "damage"],
        ):
            modifier = effect.to_modifier()
            metadata = dict(modifier.metadata)
            metadata.pop("choice_binding", None)
            metadata["semantic_effect_key"] += f":advanced:{entry.pk}"
            key = modifier.target_key
            if entry.target.startswith("skill:"):
                key = Skill.objects.get(
                    pk=entry.configuration["skill_id"]
                ).slug
            else:
                condition = metadata.get("condition_text") or "gegen @"
                metadata["condition_text"] = condition.replace(
                    "@", entry.label
                )
            yield replace(
                modifier,
                mode="flat",
                scaling={},
                target_key=key,
                value=entry.value - base,
                value_min=None,
                value_max=None,
                formula="",
                metadata=metadata,
            )
