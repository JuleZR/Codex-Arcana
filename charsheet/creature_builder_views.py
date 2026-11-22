"""Standalone workshop opened from the character sheet creature choice."""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils.translation import override

from charsheet.creature_builder_service import (
    active_forms,
    clone_creature,
    creation_for,
    damage_previews,
    damage_formula_options,
    damage_editor_states,
    inputs_from_forms,
    rules_from_forms,
    saved_rule_parameters,
    template_power,
    workshop_forms,
)
from charsheet.engine.creature_power import (
    CATEGORY_TYPES,
    CreaturePowerCalculator,
    SIZE_MODIFIERS,
)
from charsheet.creature_survival import apply_survival_floor
from charsheet.creature_abilities import (
    SOURCE_FIELDS,
    catalog_definitions,
    selection_source,
)
from charsheet.models import (
    Attribute,
    Creature,
    CreatureAttribute,
    CreatureCreation,
    CreaturePowerRule,
    CreatureTrait,
    CreatureTraitChoice,
    CreatureTraitChoiceDefinition,
    CreatureSpecialSkillValue,
    CreatureType,
    CreatureDaemonicPower,
    CreatureVampirePower,
)


def _errors(forms):
    result = []
    for collection in forms:
        errors = collection.errors
        result.append(errors)
        if hasattr(collection, "non_form_errors"):
            result.append(collection.non_form_errors())
    return result


def _power_payload(result, forms):
    power = result.as_dict()
    power["validation_errors"] = [
        {"step": step, "message": message}
        for step, message in result.errors.items()
        if step > 14
    ]
    power["damage_previews"] = damage_previews(forms)
    power["damage_formula_options"] = damage_formula_options(forms)
    power["damage_editor_states"] = damage_editor_states(forms)
    power["attack_prefixes"] = [
        row.prefix for row in active_forms(forms[2]) if not row.errors
    ]
    power["natural_survival_eligible"] = getattr(
        forms[0], "natural_survival_eligible", False
    )
    power["skill_previews"] = {
        row.prefix: row.natural_survival_preview
        for row in forms[3]
        if hasattr(row, "natural_survival_preview")
    }
    return power


def _partial_power(forms):
    result = CreaturePowerCalculator(
        inputs_from_forms(forms, partial=True)
    ).calculate()
    field_steps = {
        "category": 1,
        "element": 1,
        "creature_type": 1,
        "size_class": 3,
        "magical_strength": 3,
        "initiative_bonus": 5,
        "general_attack": 6,
        "vw_bonus": 8,
        "sr_bonus": 8,
        "gw_bonus": 8,
        "natural_rs": 9,
        "wound_step_override": 10,
        "wound_thresholds_override": 10,
        "has_kp": 14,
        "kp_override": 14,
        "potential_override": 14,
        "school_levels": 14,
        "checked": 17,
    }
    for name, messages in forms[0].errors.items():
        step = (
            11
            if "speed" in name or name == "__all__"
            else field_steps.get(name, 2)
        )
        result.errors[step] = " ".join(messages)
        result.costs.pop(step, None)
    for formset, steps in zip(
        forms[1:], ((4,), (6, 7), (12,), (13,), (12,)),
    ):
        if any(formset.errors) or formset.non_form_errors():
            for step in steps:
                result.errors[step] = (
                    "Eingaben dieses Schrittes vervollständigen."
                )
                result.costs.pop(step, None)
    if not forms[0].cleaned_data.get("checked"):
        result.errors[17] = "Bitte bestätige, dass alles erfasst ist."
    return result


def _set_traits(creature, selections):
    rules = CreaturePowerRule.objects.select_related(*SOURCE_FIELDS).in_bulk(
        [row["rule"] for row in selections]
    )
    managed = {
        field: set(
            CreaturePowerRule.objects.exclude(**{field: None}).values_list(
                field + "_id", flat=True
            )
        )
        for field in SOURCE_FIELDS
    }
    selected = {field: set() for field in SOURCE_FIELDS}
    for selection in selections:
        rule = rules[int(selection["rule"])]
        field, source = selection_source(rule, selection)
        selected[field].add(source.pk)
        if field == "special_skill":
            row, _created = CreatureSpecialSkillValue.objects.get_or_create(
                creature=creature, skill=source, defaults={"value": 0}
            )
            if "level" in selection["parameters"]:
                row.value = int(selection["parameters"]["level"])
                row.save(update_fields=["value"])
            continue
        if field == "daemonic_power":
            creature.daemonic_powers.add(source)
            row, _created = CreatureDaemonicPower.objects.get_or_create(
                creature=creature,
                power=source,
            )
            if "level" in selection["parameters"]:
                row.level = int(selection["parameters"]["level"])
                row.save(update_fields=["level"])
            continue
        if field == "vampire_power":
            CreatureVampirePower.objects.get_or_create(
                creature=creature, power=source
            )
            continue
        level = max(1, int(selection["parameters"].get("level", 1)))
        trait_row, _created = CreatureTrait.objects.get_or_create(
            creature=creature,
            trait_id=source.pk,
            defaults={"trait_level": level},
        )
        trait_row.trait_level = level
        trait_row.save(update_fields=["trait_level"])
        for name, value in selection["parameters"].items():
            specification = rule.parameters.get(name, {})
            label = specification.get("label", name)[:120]
            definition, _created = (
                CreatureTraitChoiceDefinition.objects.get_or_create(
                    trait_id=rule.trait_id,
                    name=label,
                    defaults={
                        "target_kind": "text",
                        "is_required": False,
                        "min_choices": 0,
                    },
                )
            )
            if definition.target_kind != "text":
                continue
            choices = trait_row.choices.filter(definition=definition)
            if choices.count() <= 1:
                CreatureTraitChoice.objects.update_or_create(
                    creature_trait=trait_row,
                    definition=definition,
                    defaults={"selected_text": str(value)},
                )
    creature.traits.filter(trait_id__in=managed["trait"]).exclude(
        trait_id__in=selected["trait"]
    ).delete()
    creature.special_skills.filter(
        skill_id__in=managed["special_skill"]
    ).exclude(skill_id__in=selected["special_skill"]).delete()
    creature.daemonic_power_values.filter(
        power_id__in=managed["daemonic_power"]
    ).exclude(power_id__in=selected["daemonic_power"]).delete()
    removed = managed["daemonic_power"] - selected["daemonic_power"]
    if removed:
        creature.daemonic_powers.remove(*removed)
    creature.vampire_power_defaults.filter(
        power_id__in=managed["vampire_power"]
    ).exclude(power_id__in=selected["vampire_power"]).delete()


@login_required
@require_http_methods(["GET", "POST"])
@override("de")
def creature_builder(request, pk=None):
    instance = None
    if request.GET.get("instance"):
        from charsheet.views import _owned_character_creature_or_404

        instance = _owned_character_creature_or_404(
            request, request.GET["instance"]
        )
        if pk and instance.creature_id != pk:
            raise Http404
    source = get_object_or_404(Creature, pk=pk) if pk else Creature()
    if instance:
        if instance.source_character_item_id:
            source.quality = instance.source_character_item.quality
        elif instance.source_binding_id:
            source.quality = instance.source_binding.quality
        else:
            source.quality = instance.quality
    creation = creation_for(source)
    duplicate = request.GET.get("duplicate") == "1"
    if pk and not duplicate and not request.user.is_staff:
        if not creation or creation.author_id != request.user.pk:
            # Shared catalog templates are editable as personal copies.
            duplicate = True
    draft_id = request.GET.get("draft")
    if draft_id:
        creation = get_object_or_404(
            CreatureCreation,
            pk=draft_id,
            author=request.user,
        )
        draft_source = creation.draft.get("_duplicate_source")
        if creation.creature_id != pk and draft_source != str(pk):
            raise Http404
        duplicate = bool(draft_source)
    rules = creation.rules if creation else {}
    force_kraftbestie = request.GET.get("kraftbestie") == "1"
    if creation and creation.draft.get("_builder_kraftbestie") == "1":
        force_kraftbestie = True
    data = request.POST if request.method == "POST" else None
    if data is None and creation and creation.draft and not duplicate:
        data = QueryDict("", mutable=True)
        data.update(creation.draft)
    forms = workshop_forms(source, data, rules, duplicate)
    if data is None and instance and instance.source_selection_completed:
        forms[0].initial["name"] = instance.display_name

    if request.method == "POST":
        action = request.POST.get("action", "preview")
        if action == "draft":
            with transaction.atomic():
                if creation is None or duplicate:
                    creation = CreatureCreation.objects.create(
                        author=request.user,
                        creature=None,
                        rules=rules,
                    )
                elif (
                    creation.author_id != request.user.pk
                    and not request.user.is_staff
                ):
                    raise Http404
                creation.draft = {
                    key: value
                    for key, value in request.POST.items()
                    if key not in ("csrfmiddlewaretoken", "action")
                }
                # A duplicate draft must retain its source and relation
                # identities.
                creation.draft["_duplicate_source"] = (
                    str(pk or "") if duplicate else ""
                )
                creation.draft["_builder_kraftbestie"] = (
                    "1" if force_kraftbestie else ""
                )
                creation.save(update_fields=["draft", "updated_at"])
            return JsonResponse(
                {
                    "ok": True,
                    "draft": creation.pk,
                    "message": "Entwurf gespeichert.",
                    "url": _draft_url(
                        creation,
                        pk,
                        instance,
                        force_kraftbestie,
                        request.GET.get("embedded") == "1",
                    ),
                }
            )
        valid = all([collection.is_valid() for collection in forms])
        if not valid:
            if action == "preview":
                power = _power_payload(_partial_power(forms), forms)
                return JsonResponse({"ok": True, "power": power})
            return JsonResponse(
                {"ok": False, "errors": _errors(forms)}, status=400
            )
        result = CreaturePowerCalculator(inputs_from_forms(forms)).calculate()
        if not forms[0].cleaned_data.get("checked"):
            result.errors[17] = "Bitte bestätige, dass alles erfasst ist."
        if action == "preview":
            power = _power_payload(result, forms)
            return JsonResponse({"ok": True, "power": power})
        if action != "publish":
            return JsonResponse(
                {"ok": False, "error": "Unbekannte Aktion."}, status=400
            )
        if not result.complete:
            return JsonResponse(
                {"ok": False, "power": _power_payload(result, forms)},
                status=400,
            )
        if not pk:
            label = CATEGORY_TYPES[forms[0].cleaned_data["category"]][1]
            forms[0].instance.name = f"{label} (eigene Kreatur)"
        if instance and instance.source_binding_id:
            if not instance.source_binding.allows_creature_template(
                forms[0].instance
            ):
                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            "Diese Kategorie passt nicht zur aufrufenden "
                            "Kreaturenwahl."
                        ),
                    },
                    status=400,
                )
        if instance and (instance.is_kraftbestie or force_kraftbestie):
            creature_type = forms[0].cleaned_data.get("creature_type")
            if not creature_type or creature_type.slug != "tier":
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Kraftbestien benötigen eine Tier-Vorlage.",
                    },
                    status=400,
                )
        with transaction.atomic():
            form, attributes, attacks, skills, _abilities, languages = forms
            if form.instance.creature_type_id is None:
                slug, label = CATEGORY_TYPES[form.cleaned_data["category"]]
                form.instance.creature_type, _created = (
                    CreatureType.objects.get_or_create(
                        slug=slug,
                        defaults={"name": label},
                    )
                )
            if duplicate:
                fresh_source = Creature.objects.get(pk=pk)
                target, mapping = clone_creature(fresh_source)
                form.instance.pk = target.pk
                form.instance.name = _template_name(
                    f"{fresh_source.name} (Kopie)"
                )
                form.instance.slug = ""
                form.instance._state.adding = False
                for formset in (attributes, attacks, skills, languages):
                    for row in formset:
                        if row.instance.pk:
                            row.instance.pk = mapping[
                                (type(row.instance), row.instance.pk)
                            ]
                        row.instance.creature_id = target.pk
                if creation and creation.creature_id:
                    creation = None
            elif not pk:
                form.instance.name = _template_name(form.instance.name)
            form.instance.size_modifier = SIZE_MODIFIERS[
                form.cleaned_data["size_class"]
            ]
            form.instance.initiative_override = int(
                result.derived["initiative"]
            )
            # This workshop follows the creation GW on p. 466 (INT + WA).
            # The older generic renderer uses INT + WILL, so persist the exact
            # creation value without changing existing templates' calculations.
            for stat in ("vw", "sr", "gw"):
                setattr(
                    form.instance,
                    f"{stat}_override",
                    int(result.derived[stat]),
                )
            if (
                form.cleaned_data["has_kp"]
                and form.cleaned_data["kp_override"] is None
            ):
                form.instance.kp_override = int(result.derived["arcane_power"])
            if form.cleaned_data["category"] == "V":
                form.instance.vampire_blood_capacity_override = int(
                    result.derived["arcane_power"]
                )
            creature = form.save()
            for row in active_forms(attributes):
                CreatureAttribute.objects.update_or_create(
                    creature=creature,
                    attribute=row.cleaned_data["attribute"],
                    defaults={
                        "base_value": (
                            row.cleaned_data["base_value"] + 5
                            if row.cleaned_data["base_value"] is not None
                            else None
                        )
                    },
                )
            for formset in (attacks, skills, languages):
                formset.instance = creature
                formset.save()
            creature.languages.filter(is_mother_tongue=True).update(
                is_mother_tongue=False,
            )
            rules = saved_rule_parameters(rules_from_forms(forms))
            _set_traits(creature, rules["abilities"])
            apply_survival_floor(creature, rules)
            # Read back the saved canonical data, including any unpriced legacy
            # rows.
            result = template_power(creature, rules)
            if result is None or not result.complete:
                transaction.set_rollback(True)
                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            "Vorlagendaten sind noch nicht "
                            "vollständig bepreist."
                        ),
                        "power": (
                            _power_payload(result, forms) if result else None
                        ),
                    },
                    status=400,
                )
            if creation is None:
                creation = CreatureCreation(
                    creature=creature, author=request.user
                )
            creation.creature = creature
            creation.rules = rules
            creation.released = True
            creation.draft = {}
            creation.save()
            if instance and instance.source_selection_completed:
                instance.creature = creature
                instance.name_override = form.cleaned_data["name"]
                instance.save(update_fields=["creature", "name_override"])
        return JsonResponse(
            {
                "ok": True,
                "saved": True,
                "id": creature.pk,
                "name": creature.name,
                "instance_name": form.cleaned_data["name"],
                "type_id": creature.creature_type_id,
                "power": _power_payload(result, forms),
            }
        )

    form, attributes, attacks, skills, abilities, languages = forms
    groups = [
        (1, "Kategorie", ["category", "element"]),
        (2, "Name", ["name"]),
        (3, "Größe", ["size_class", "magical_strength"]),
        (5, "Initiative", ["initiative_bonus"]),
        (6, "Angriff", ["general_attack"]),
        (7, "Schaden", []),
        (8, "Widerstandswerte", ["vw_bonus", "sr_bonus", "gw_bonus"]),
        (9, "Rüstungsschutz", ["natural_rs"]),
        (
            10,
            "Lebenspunkte",
            ["wound_step_override", "wound_thresholds_override"],
        ),
        (
            11,
            "Bewegungsweite",
            [
                "combat_speed",
                "march_speed",
                "sprint_speed",
                "swimming_speed",
                "combat_swimming_speed",
                "march_swimming_speed",
                "sprint_swimming_speed",
                "combat_fly_speed",
                "march_fly_speed",
                "sprint_fly_speed",
            ],
        ),
        (
            14,
            "Arkane Macht",
            [
                "has_kp",
                "kp_override",
                "potential_override",
                "school_levels",
            ],
        ),
        (15, "Klima und Vorkommen", ["climate_and_occurrence"]),
        (16, "Organisation", ["organization"]),
        (17, "Beschreibung", ["description", "is_swarm_creature", "checked"]),
    ]
    return render(
        request,
        "charsheet/creature_builder.html",
        {
            "groups": [
                {
                    "step": step,
                    "label": label,
                    "fields": [form[key] for key in keys],
                }
                for step, label, keys in groups
            ],
            "form": form,
            "attributes": attributes,
            "attribute_columns": _attribute_columns(attributes),
            "attacks": attacks,
            "quality": source.quality,
            "embedded": request.GET.get("embedded") == "1",
            "wizard_step": data.get("_wizard_step", 1) if data else 1,
            "skills": skills,
            "abilities": abilities,
            "languages": languages,
            "duplicate": duplicate,
            "duplicate_url": (
                (
                    reverse("creature_builder", args=[pk])
                    + "?duplicate=1"
                    + (f"&instance={instance.pk}" if instance else "")
                    + (
                        "&embedded=1"
                        if request.GET.get("embedded") == "1"
                        else ""
                    )
                )
                if pk
                else ""
            ),
            "rule_definitions": catalog_definitions(abilities.catalog),
            "drafts": [
                {
                    "name": row.draft.get("name") or "Unbenannte Kreatur",
                    "url": _draft_url(
                        row,
                        row.creature_id or row.draft.get("_duplicate_source"),
                        instance,
                        embedded=request.GET.get("embedded") == "1",
                    ),
                }
                for row in CreatureCreation.objects.filter(
                    author=request.user,
                )
                .exclude(draft={})
                .order_by("-updated_at")[:20]
            ],
        },
    )


def _template_name(label):
    base = label[:90]
    name, suffix = base, 2
    while Creature.objects.filter(name=name).exists():
        name = f"{base} ({suffix})"
        suffix += 1
    return name


def _attribute_columns(formset):
    catalog = Attribute.objects.in_bulk(
        [row["attribute"].value() for row in formset]
    )
    labels = {
        "ST": "Stärke",
        "KON": "Konstitution",
        "GE": "Geschick",
        "INT": "Intelligenz",
        "WA": "Wahrnehmung",
        "WILL": "Willenskraft",
        "CHA": "Charisma",
    }
    rows = {}
    for row in formset:
        attribute_id = row["attribute"].value()
        if attribute_id is None:
            continue
        attribute = catalog.get(int(attribute_id))
        if attribute and attribute.short_name in labels:
            row.fields["absent"].widget.attrs[
                "aria-label"
            ] = f"{labels[attribute.short_name]} nicht vorhanden"
            rows[attribute.short_name] = {
                "form": row,
                "label": labels[attribute.short_name],
            }
    return [
        [rows[code] for code in codes if code in rows]
        for codes in (("ST", "KON", "GE", "INT"), ("WA", "WILL", "CHA"))
    ]


def _draft_url(
    creation, pk, instance, force_kraftbestie=False, embedded=False
):
    url = (
        reverse("creature_builder", args=[pk])
        if pk
        else reverse("creature_builder_new")
    )
    url += f"?draft={creation.pk}"
    if instance:
        url += f"&instance={instance.pk}"
    if force_kraftbestie or creation.draft.get("_builder_kraftbestie") == "1":
        url += "&kraftbestie=1"
    if embedded:
        url += "&embedded=1"
    return url
