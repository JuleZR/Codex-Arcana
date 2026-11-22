"""Translate workshop forms into canonical creature rows and power inputs."""

from copy import copy

from django.core.exceptions import ObjectDoesNotExist

from charsheet.creature_damage import (
    damage_variants,
    legacy_formula,
    match_damage_level,
    render_formula,
    select_damage_variant,
)
from charsheet.creature_builder_forms import (
    AbilityFormSet,
    AttackFormSet,
    AttributeFormSet,
    CreatureBuildForm,
    LanguageFormSet,
    SkillFormSet,
)
from charsheet.engine.creature_power import (
    ATTRIBUTE_CODES,
    CATEGORY_TYPES,
    CreaturePowerCalculator,
    SIZE_MODIFIERS,
)
from charsheet.models import Attribute, CreaturePowerRule
from charsheet.creature_survival import skill_prices
from charsheet.creature_abilities import (
    SOURCE_FIELDS,
    ability_catalog,
    selection_source,
)

EXTRA_FIELDS = (
    "category",
    "element",
    "magical_strength",
    "general_attack",
    "school_levels",
    "checked",
    "initiative_bonus",
    "vw_bonus",
    "sr_bonus",
    "gw_bonus",
)
ATTACK_FIELDS = (
    "damage_level",
    "damage_kind",
    "acid_power",
    "short_range",
    "extra_damage_types",
    "automatic_attack",
    "attack_bonus",
    "automatic_damage",
    "damage_adjustment",
    "damage_formula_choice",
    "damage_formula",
    "damage_editor_active",
    "damage_level_confirmed",
    "legacy_damage",
    "original_notes",
)


def creation_for(creature):
    try:
        return creature.creation if creature.pk else None
    except ObjectDoesNotExist:
        return None


def attribute_bonuses(creature):
    """The workshop edits bonuses; existing catalog rows store scores."""
    return (
        {
            row.attribute.short_name: (
                row.base_value - 5 if row.base_value is not None else None
            )
            for row in creature.attributes.select_related("attribute")
        }
        if creature.pk
        else {}
    )


def workshop_forms(creature, data=None, rules=None, duplicate=False):
    rules = rules or imported_rules(creature)
    initial = {key: rules.get(key) for key in EXTRA_FIELDS if key in rules}
    initial["name"] = rules.get("instance_name", "")
    bonuses = attribute_bonuses(creature)
    if creature.pk:
        baseline = CreaturePowerCalculator(
            {
                "attributes": bonuses,
                "size_class": creature.size_class,
            }
        )
        for stat in ("initiative", "vw", "sr", "gw"):
            value = getattr(creature, f"{stat}_override")
            try:
                initial[f"{stat}_bonus"] = (
                    value - baseline.stat_base(stat)
                    if value is not None
                    else 0
                )
            except KeyError:
                initial[f"{stat}_bonus"] = 0
    if data is not None:
        data = data.copy()
        for stat in ("initiative", "vw", "sr", "gw"):
            if f"{stat}_bonus" not in data and f"{stat}_override" in data:
                data[f"{stat}_bonus"] = data.get(f"{stat}_override") or "0"
    if rules.get("category") == "V":
        initial["kp_override"] = creature.vampire_blood_capacity_override
    for key, value in rules.get("automatic_values", {}).items():
        if getattr(creature, key, None) == value:
            initial[key] = None
    if not creature.pk:
        initial.update(combat_speed=4, march_speed=8, sprint_speed=32)
    form = CreatureBuildForm(data, instance=creature, initial=initial)
    attributes = AttributeFormSet(data, instance=creature, prefix="attributes")
    if not creature.pk:
        attributes.extra = Attribute.objects.filter(
            short_name__in=ATTRIBUTE_CODES
        ).count()
        attributes.initial_extra = [
            {"attribute": row.pk, "base_value": None}
            for row in Attribute.objects.filter(short_name__in=ATTRIBUTE_CODES)
        ]
    attacks = AttackFormSet(data, instance=creature, prefix="attacks")
    skills = SkillFormSet(data, instance=creature, prefix="skills")
    if data is None:
        for row in attributes:
            attribute = row.initial.get("attribute")
            code = (
                attribute.short_name
                if hasattr(attribute, "short_name")
                else Attribute.objects.get(pk=attribute).short_name
            )
            row.initial["absent"] = code in rules.get("absent_attributes", [])
            if creature.pk:
                row.initial["base_value"] = bonuses.get(code)
        for row in attacks:
            attack_rules = rules.get("attacks", {}).get(
                str(row.instance.pk), {}
            )
            row.initial.update(attack_rules)
            row.initial.setdefault("damage_kind", "physical")
            if row.instance.pk and not attack_rules:
                row.initial["automatic_attack"] = False
                row.initial["automatic_damage"] = False
            if "original_notes" in attack_rules:
                row.initial["notes"] = attack_rules["original_notes"]
            level = attack_rules.get("damage_level")
            if level is not None:
                row.fields["damage_formula_choice"].widget.choices = [
                    (variant["key"], variant["label"])
                    for variant in damage_variants(int(level))
                ]
                row.initial["damage_formula_choice"] = select_damage_variant(
                    int(level), attack_rules.get("damage_formula_choice", "")
                )["key"]
            formula = attack_rules.get("damage_formula")
            if (
                not formula
                and level is not None
                and not attack_rules.get("legacy_damage")
            ):
                formula = select_damage_variant(
                    int(level), attack_rules.get("damage_formula_choice", "")
                )["formula"]
            if not formula and row.instance.pk:
                formula = legacy_formula(row.instance)
            if formula:
                row.initial["damage_formula_input"] = formula
                row.initial["damage_editor_active"] = True
    for row in skills:
        row.natural_survival_preferred = str(row.instance.pk) in rules.get(
            "free_survival", []
        )
    catalog = ability_catalog()
    abilities = AbilityFormSet(
        data,
        prefix="abilities",
        initial=rules.get("abilities", []),
        form_kwargs={"catalog": catalog},
    )
    abilities.catalog = catalog
    language_data = data
    if data is not None and "languages-TOTAL_FORMS" not in data:
        # Older drafts predate the language editor.
        language_data = data.copy()
        language_data.update({
            "languages-TOTAL_FORMS": "0",
            "languages-INITIAL_FORMS": "0",
        })
    languages = LanguageFormSet(
        language_data, instance=creature, prefix="languages",
    )
    return form, attributes, attacks, skills, abilities, languages


def imported_rules(creature):
    """Reuse identifiable legacy purchases; leave unknown parameters open."""
    if not creature.pk:
        return {}
    available = list(CreaturePowerRule.objects.all())
    selections = {}

    def include(field, entry, level):
        rule = next(
            (
                row
                for row in available
                if getattr(row, field + "_id") == entry.pk
            ),
            None,
        )
        if rule:
            parameters = (
                {"level": str(level)} if "level" in rule.parameters else {}
            )
            selections.setdefault(
                rule.pk,
                {
                    "rule": rule.pk,
                    "catalog_key": f"{field}:{entry.pk}",
                    "parameters": parameters,
                },
            )
        else:
            selections[(field, entry.pk)] = {
                "rule": None,
                "catalog_key": f"{field}:{entry.pk}",
                "parameters": {},
            }

    for row in creature.traits.select_related("trait"):
        include("trait", row.trait, row.trait_level)
    for row in creature.special_skills.select_related("skill"):
        include("special_skill", row.skill, row.value)
    for row in creature.daemonic_power_values.select_related("power"):
        include("daemonic_power", row.power, row.level or 1)
    for row in creature.vampire_power_defaults.select_related("power"):
        include("vampire_power", row.power, 1)
    result = {"abilities": list(selections.values())}
    if creature.creature_type_id:
        category = next(
            (
                key
                for key, (slug, _label) in CATEGORY_TYPES.items()
                if slug == creature.creature_type.slug
                and key not in ("W", "KU", "GU")
            ),
            None,
        )
        if category:
            result["category"] = category
    return result


def active_forms(formset):
    return [
        form
        for form in formset
        if form.cleaned_data and not form.cleaned_data.get("DELETE")
    ]


def ability_inputs(selections):
    definitions = CreaturePowerRule.objects.select_related(
        *SOURCE_FIELDS
    ).in_bulk([selection["rule"] for selection in selections])
    rows = []
    for selection in selections:
        rule = definitions.get(int(selection["rule"]))
        if rule is None:
            raise ValueError("Fähigkeitsdefinition fehlt.")
        _field, source = selection_source(rule, selection)
        rows.append(
            {
                "key": rule.key,
                "name": source.name,
                "formula": rule.formula,
                "categories": rule.categories,
                "requires": rule.requirements,
                "parameters": selection["parameters"],
                "parameter_schema": rule.parameters,
            }
        )
    return rows


def base_input(creature, rules):
    result = {key: rules.get(key) for key in EXTRA_FIELDS if key in rules}
    result.update(
        name=creature.name,
        size_class=creature.size_class,
        initiative=creature.initiative_override,
        vw=creature.vw_override,
        sr=creature.sr_override,
        gw=creature.gw_override,
        natural_rs=creature.natural_rs,
        wound_step=creature.wound_step_override,
        arcane_power=(
            creature.vampire_blood_capacity_override
            if rules.get("category") == "V"
            else creature.kp_override if creature.has_kp else 0
        ),
        potential=creature.potential_override,
    )
    thresholds = creature.wound_thresholds_override
    if thresholds:
        values = [int(token.strip()) for token in thresholds.split(",")]
        result["wound_zones"] = [
            value - (values[index - 1] if index else 0)
            for index, value in enumerate(values)
        ]
    movement = {}
    for mode, fields in (
        ("ground", ("combat_speed", "march_speed", "sprint_speed")),
        (
            "swim",
            (
                "combat_swimming_speed",
                "march_swimming_speed",
                "sprint_swimming_speed",
            ),
        ),
        ("fly", ("combat_fly_speed", "march_fly_speed", "sprint_fly_speed")),
    ):
        values = [getattr(creature, key) for key in fields]
        if any(value is not None for value in values):
            movement[mode] = values
    if creature.swimming_speed is not None and "swim" not in movement:
        movement["swim"] = [creature.swimming_speed]
    result["movement"] = movement
    return result


def inputs_from_forms(forms, partial=False):
    form, attributes, attacks, skills, abilities, languages = forms
    rules = {key: form.cleaned_data.get(key) for key in EXTRA_FIELDS}
    rules["school_levels"] = rules.get("school_levels") or 0

    def rows(formset):
        return [
            row
            for row in active_forms(formset)
            if not partial or not row.errors
        ]

    selections = [row.selection() for row in rows(abilities)]
    result = base_input(form.instance, rules)
    result["name"] = form.cleaned_data.get("name", "")
    if rules.get("category") == "V":
        result["arcane_power"] = form.cleaned_data.get("kp_override")
    result["attributes"] = {
        row.cleaned_data["attribute"].short_name: row.cleaned_data[
            "base_value"
        ]
        for row in rows(attributes)
    }
    baseline = CreaturePowerCalculator(result)
    for stat in ("initiative", "vw", "sr", "gw"):
        try:
            result[stat] = baseline.stat_base(stat)
            result[stat] += form.cleaned_data.get(f"{stat}_bonus") or 0
        except KeyError:
            result[stat] = None
    result["attacks"] = []
    for row in rows(attacks):
        data = row.cleaned_data
        if data.get("automatic_attack"):
            if "GE" not in result["attributes"]:
                data["attack_value"] = None
            else:
                dexterity = result["attributes"]["GE"]
                value = dexterity if dexterity is not None else -5
                value += SIZE_MODIFIERS[result["size_class"]]
                data["attack_value"] = value + (data.get("attack_bonus") or 0)
                row.instance.attack_value = data["attack_value"]
        if not data.get("damage_editor_active") and data.get(
            "automatic_damage"
        ):
            if "ST" not in result["attributes"]:
                data["damage_level"] = None
            else:
                strength = result["attributes"]["ST"]
                data["damage_level"] = max(
                    0,
                    (strength if strength is not None else -5)
                    + 5
                    + (data.get("damage_adjustment") or 0),
                )
        data["original_notes"] = data.get("notes", "")
        data["legacy_damage"] = bool(
            row.instance.pk
            and row.instance.show_notes_as_damage
            and not data.get("damage_editor_active")
            and not data.get("damage_formula_choice")
        )
        if data.get("damage_level") is not None:
            if data["legacy_damage"]:
                data["damage_formula"] = None
            elif data.get("damage_editor_active"):
                data["damage_formula"] = data["damage_formula_input"]
                data["damage_formula_choice"] = ""
            else:
                variant = select_damage_variant(
                    data["damage_level"], data.get("damage_formula_choice", "")
                )
                data["damage_formula_choice"] = variant["key"]
                data["damage_formula"] = variant["formula"]
            if not data["legacy_damage"]:
                apply_damage_level(
                    row.instance,
                    data["damage_level"],
                    data["original_notes"],
                    formula=data["damage_formula"],
                )
        result["attacks"].append(
            {
                "attack_value": data["attack_value"],
                **{key: data.get(key) for key in ATTACK_FIELDS},
            }
        )
        for key in ("short_range", "extra_damage_types"):
            data[key] = data.get(key) or 0
            result["attacks"][-1][key] = data.get(key) or 0
    skill_forms = rows(skills)
    eligible, prices = skill_prices(
        form.instance,
        [row.instance for row in skill_forms],
        rules.get("category"),
        [
            row.instance.pk
            for row in skill_forms
            if row.natural_survival_preferred
        ],
        result["attributes"],
    )
    form.natural_survival_eligible = eligible
    result["natural_survival_eligible"] = eligible
    result["skills"] = [{"paid_level": row["paid_level"]} for row in prices]
    result["languages"] = [
        {
            key: row.cleaned_data[key]
            for key in ("levels", "can_write")
        }
        for row in rows(languages)
    ]
    result["free_survival_count"] = sum(
        row["natural_survival"] for row in prices
    )
    for row, price in zip(skill_forms, prices):
        row.natural_survival_granted = price["natural_survival"]
        row.natural_survival_preview = {
            key: value for key, value in price.items() if key != "row"
        }
    result["abilities"] = ability_inputs(selections)
    return result


def apply_damage_level(
    attack, level, notes="", formula_choice="", formula=None
):
    """Use exact dice categories from p. 465, never expected dice averages."""
    attack.damage_dice_amount = 0
    attack.damage_dice_faces = 0
    attack.damage_flat_operator = ""
    attack.damage_flat_bonus = 0
    attack.show_notes_as_damage = False
    attack.append_notes_to_damage = False
    attack.notes = notes
    formula = (
        formula or select_damage_variant(level, formula_choice)["formula"]
    )
    terms = formula["terms"] if formula["kind"] == "sum" else [formula]
    die = terms[0]
    bonus = terms[1] if len(terms) == 2 else None
    if formula["kind"] == "constant" and formula["value"] > 0:
        attack.damage_flat_bonus = formula["value"]
        return
    if die["kind"] == "dice" and (
        len(terms) == 1
        or (
            len(terms) == 2
            and bonus["kind"] == "constant"
            and die["divisor"] == 1
        )
    ):
        attack.damage_dice_amount = die["count"]
        attack.damage_dice_faces = die["sides"]
        if die["divisor"] != 1:
            attack.damage_flat_operator = "/"
            attack.damage_flat_bonus = die["divisor"]
        elif bonus:
            value = bonus["value"]
            attack.damage_flat_operator = "+" if value >= 0 else "-"
            attack.damage_flat_bonus = abs(value)
        return
    # Project compound expressions into the card's existing exact-display
    # channel. Their structured source remains in the creation rules JSON.
    attack.notes = render_formula(formula)
    if attack.damage_type:
        attack.notes += f" {attack.damage_type}"
    if notes:
        attack.notes += f" ({notes})"
    attack.show_notes_as_damage = True


def damage_previews(forms):
    """Format the calculated attack instances using the card formatter."""
    from charsheet.engine.creature_engine import CreatureEngine

    result = {}
    for row in active_forms(forms[2]):
        if row.cleaned_data.get("damage_level") is None:
            continue
        attack = row.instance
        if attack.show_notes_as_damage:
            damage = attack.notes
        else:
            damage = CreatureEngine._format_damage(attack)
        result[row.prefix] = damage
    return result


def damage_formula_options(forms):
    result = {}
    for row in active_forms(forms[2]):
        level = row.cleaned_data.get("damage_level")
        if level is not None:
            result[row.prefix] = {
                "variants": damage_variants(level),
                "selected": row.cleaned_data.get("damage_formula_choice", ""),
            }
    return result


def damage_editor_states(forms):
    result = {}
    for row in active_forms(forms[2]):
        data = row.cleaned_data
        formula = (
            data.get("damage_formula_input")
            if data.get("damage_editor_active")
            else data.get("damage_formula")
        )
        if formula:
            matched = match_damage_level(formula)
            display = render_formula(formula)
        else:
            matched = None
            display = (
                row.instance.notes if row.instance.show_notes_as_damage else ""
            )
        result[row.prefix] = {
            "formula": formula,
            "matched_level": matched,
            "level": data.get("damage_level"),
            "display": display,
            "legacy": formula is None,
            "error": " ".join(row.errors.get("damage_formula_input", [])),
            "manual_confirmed": bool(
                data.get("damage_level_confirmed")
                and data.get("damage_level") is not None
            ),
        }
    return result


def rules_from_forms(forms):
    form, attributes, attacks, skills, abilities, _languages = forms
    rules = {key: form.cleaned_data.get(key) for key in EXTRA_FIELDS}
    rules["attribute_storage"] = "score"
    rules["instance_name"] = form.cleaned_data["name"]
    rules["school_levels"] = rules.get("school_levels") or 0
    rules["absent_attributes"] = [
        row.cleaned_data["attribute"].short_name
        for row in active_forms(attributes)
        if row.cleaned_data.get("absent")
    ]
    rules["attacks"] = {
        str(row.instance.pk): {
            key: row.cleaned_data.get(key) for key in ATTACK_FIELDS
        }
        for row in active_forms(attacks)
    }
    rules["free_survival"] = [
        str(row.instance.pk)
        for row in active_forms(skills)
        if getattr(row, "natural_survival_granted", False)
    ]
    rules["abilities"] = [row.selection() for row in active_forms(abilities)]
    rules["automatic_values"] = {
        key: getattr(form.instance, key)
        for key in ("kp_override",)
        if form.cleaned_data.get(key) is None
    }
    return rules


def card_creation_context(engine):
    """Expose verified template power only when the instance is unmodified."""
    from charsheet.engine.creature_engine import CreatureEngine

    creature = engine._swarm_template
    pk = getattr(creature, "pk", None)
    power = template_power(creature) if pk else None
    if engine._uses_kraftbestie_rules() or engine.swarm_mode():
        power = None
    if power and power.complete and engine.instance:
        baseline = CreatureEngine(creature)
        if engine._uses_kraftbestie_rules() or engine.swarm_mode():
            power = None
        else:
            methods = (
                "size_class",
                "size_modifier",
                "initiative",
                "vw",
                "sr",
                "gw",
                "wound_rows",
                "movement",
                "attacks",
                "skills",
                "traits",
                "special_skills",
                "kp",
                "potential",
                "armor_totals",
            )
            if any(
                getattr(engine, key)() != getattr(baseline, key)()
                for key in methods
            ):
                power = None
            elif any(
                engine.attribute_mod(code) != baseline.attribute_mod(code)
                for code in ATTRIBUTE_CODES
            ):
                power = None
    context = {
        "power": power.total.normalize() if power and power.complete else None,
    }
    creation = creation_for(creature)
    binding = (
        engine.instance.source_binding
        if engine.instance and engine.instance.source_binding_id
        else None
    )
    if (
        creation
        and creation.released
        and binding
        and binding.selection_mode == binding.SelectionMode.CHARACTER_CHOICE
        and not engine._uses_kraftbestie_rules()
        and creature.creature_type_id
    ):
        label = binding.choice_label or "Tiergestalt"
        context["typebar_label"] = f"{label} - {creature.creature_type.name}"
    return context


def template_power(creature, rules=None):
    creation = creation_for(creature)
    if rules is None:
        if creation and not creation.released:
            return None
        if creation:
            rules = creation.rules
        else:
            # Catalog templates have no workshop metadata. Reuse their linked
            # purchases and classify numeric damage using the official table.
            rules = imported_rules(creature)
            rules["checked"] = True
            rules["attacks"] = {}
            for attack in creature.attacks.all():
                if attack.notes:
                    # Notes can contain unpriced range or damage effects.
                    return None
                formula = legacy_formula(attack)
                level = match_damage_level(formula) if formula else None
                if level is None:
                    return None
                rules["attacks"][str(attack.pk)] = {"damage_level": level}
    try:
        data = base_input(creature, rules)
        data["attributes"] = attribute_bonuses(creature)
        data["attacks"] = [
            {
                "attack_value": row.attack_value,
                **rules.get("attacks", {}).get(str(row.pk), {}),
            }
            for row in creature.attacks.all()
        ]
        skill_rows = list(creature.skills.all())
        eligible, prices = skill_prices(
            creature,
            skill_rows,
            rules.get("category"),
            rules.get("free_survival", []),
        )
        data["natural_survival_eligible"] = eligible
        data["skills"] = [{"paid_level": row["paid_level"]} for row in prices]
        data["free_survival_count"] = sum(
            row["natural_survival"] for row in prices
        )
        data["abilities"] = ability_inputs(rules.get("abilities", []))
        data["languages"] = list(creature.languages.values(
            "levels", "can_write",
        ))
        result = CreaturePowerCalculator(data).calculate()
        selected_rules = {
            row.pk: row
            for row in CreaturePowerRule.objects.select_related(
                *SOURCE_FIELDS
            ).filter(
                pk__in=[row["rule"] for row in rules.get("abilities", [])]
            )
        }
        covered = {field: set() for field in SOURCE_FIELDS}
        for selection in rules.get("abilities", []):
            field, entry = selection_source(
                selected_rules[int(selection["rule"])], selection
            )
            covered[field].add(entry.pk)
        if (
            creature.traits.exclude(trait_id__in=covered["trait"]).exists()
            or creature.special_skills.exclude(
                skill_id__in=covered["special_skill"]
            ).exists()
            or creature.daemonic_powers.exclude(
                pk__in=covered["daemonic_power"]
            ).exists()
            or creature.daemonic_power_values.exclude(
                power_id__in=covered["daemonic_power"]
            ).exists()
            or creature.vampire_power_defaults.exclude(
                power_id__in=covered["vampire_power"]
            ).exists()
        ):
            result.errors[13] = (
                "Für vorhandene Katalogeinträge fehlen Machtregeln."
            )
        if creature.vampire_trait_defaults.exists():
            result.errors[13] = (
                "Zusätzliche Vorlagendaten benötigen Machtregeln."
            )
        if not rules.get("checked"):
            result.errors[17] = "Bitte bestätige, dass alles erfasst ist."
        return result
    except (ValueError, KeyError, TypeError):
        return None


def clone_creature(source):
    """Clone owned template data, retaining all shared catalog references."""
    mapping = {}

    def clone(row, changes):
        old_pk = row.pk
        result = copy(row)
        result.pk = None
        result._state = copy(row._state)
        result._state.adding = True
        result._state.fields_cache = {}
        if hasattr(result, "_prefetched_objects_cache"):
            result._prefetched_objects_cache = {}
        for key, value in changes.items():
            setattr(result, key, value)
        result.save()
        mapping[(type(row), old_pk)] = result.pk
        for field in row._meta.many_to_many:
            if field.remote_field.through._meta.auto_created:
                getattr(result, field.name).set(getattr(row, field.name).all())
        return result

    # The caller supplies the requested unique name after validation.
    import uuid

    target = clone(source, {"name": f"Entwurf {uuid.uuid4().hex}", "slug": ""})
    # Creature.save creates empty attribute rows; replace those with the
    # copies.
    target.attributes.all().delete()
    for relation in (
        "attributes",
        "attacks",
        "skills",
        "languages",
        "special_skills",
        "commands",
        "daemonic_power_values",
        "vampire_power_defaults",
        "vampire_trait_defaults",
        "traits",
    ):
        manager = getattr(source, relation, None)
        if manager is None:
            continue
        for row in manager.all():
            copied = clone(row, {"creature_id": target.pk})
            if relation == "traits":
                for choice in row.choices.all():
                    changes = {"creature_trait_id": copied.pk}
                    attack = choice.selected_creature_attack
                    if attack is not None:
                        changes["selected_creature_attack_id"] = mapping[
                            (type(attack), attack.pk)
                        ]
                    clone(choice, changes)
    try:
        profile = source.swarm_profile
    except ObjectDoesNotExist:
        profile = None
    if profile:
        copied = clone(profile, {"creature_id": target.pk})
        for row in profile.attack_overrides.all():
            clone(
                row,
                {
                    "profile_id": copied.pk,
                    "base_attack_id": mapping[
                        (type(row.base_attack), row.base_attack_id)
                    ],
                },
            )
        for row in profile.count_effects.all():
            clone(row, {"profile_id": copied.pk})
    return target, mapping


def saved_rule_parameters(rules):
    """Normalize decimals recursively for the JSON metadata column."""
    import json

    return json.loads(json.dumps(rules, default=str))
