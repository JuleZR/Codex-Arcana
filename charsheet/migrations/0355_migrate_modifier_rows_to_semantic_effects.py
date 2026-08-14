from django.db import migrations


ATTRIBUTE_KEYS = {"GE", "WA", "INT", "WILL", "ST", "KON", "CHA", "spz."}
RULE_FLAG_KEYS = {
    "wound_penalty_ignore",
    "can_act_while_out_of_action",
    "armor_penalty_ignore",
    "shield_penalty_ignore",
    "coma_ignore",
    "vampire_strength_over_race_maximum",
    "vampire_power_manual_activation",
    "vampire_power_blood_theft",
    "vampire_power_blood_sacrament",
    "vampire_power_attribute_boost",
    "vampire_regeneration",
}
DAMAGE_KEYS = {
    "weapon_damage",
    "weapon_damage_dice",
    "weapon_maneuver_damage",
    "unarmed_damage",
}
COMBAT_KEYS = DAMAGE_KEYS | {"melee_maneuvers", "weapon_mastery_bonus"}


def _json_dict(value):
    return dict(value or {})


def _target_identifier(modifier):
    if modifier.target_skill_id:
        return modifier.target_skill.slug
    if modifier.target_skill_category_id:
        return modifier.target_skill_category.slug
    if modifier.target_item_id:
        return str(modifier.target_item_id)
    if modifier.target_specialization_id:
        return str(modifier.target_specialization_id)
    if modifier.target_choice_definition_id:
        return f"selected_skill:technique_choice_definition:{modifier.target_choice_definition_id}"
    if modifier.target_race_choice_definition_id:
        return f"selected_skill:race_choice_definition:{modifier.target_race_choice_definition_id}"
    if modifier.target_content_type_id and modifier.target_object_id is not None:
        return f"{modifier.target_content_type_id}:{modifier.target_object_id}"
    return modifier.target_slug or ""


def _target_domain(modifier):
    key = _target_identifier(modifier)
    if modifier.target_kind == "attribute":
        return "attribute"
    if modifier.target_kind == "skill":
        return "damage" if key in DAMAGE_KEYS or key.startswith("dmg_") else "skill"
    if modifier.target_kind == "category":
        return "skill_category"
    if modifier.target_kind == "stat":
        if key in RULE_FLAG_KEYS:
            return "rule_flag"
        if key in ATTRIBUTE_KEYS:
            return "attribute"
        if key in COMBAT_KEYS or key.startswith("dmg_"):
            return "damage" if key in DAMAGE_KEYS or key.startswith("dmg_") else "combat"
        return "derived_stat"
    if modifier.target_kind == "item":
        return "item"
    if modifier.target_kind == "item_category":
        return "item_category"
    if modifier.target_kind == "specialization":
        return "specialization"
    if modifier.target_kind == "entity":
        return "entity"
    return modifier.target_kind


def _operator_and_value(modifier):
    if _target_domain(modifier) == "rule_flag":
        enabled = bool(modifier.value)
        return ("set_flag" if enabled else "unset_flag", enabled)
    if int(modifier.value or 0) < 0:
        return "flat_sub", abs(int(modifier.value or 0))
    return "flat_add", int(modifier.value or 0)


def _scaling(modifier):
    payload = {}
    for field_name in (
        "scale_source",
        "scale_school_id",
        "scale_skill_id",
        "mul",
        "div",
        "round_mode",
        "cap_mode",
        "cap_source",
        "min_school_level",
    ):
        value = getattr(modifier, field_name)
        if value not in (None, "", 0):
            payload[field_name] = value
    return payload


def _metadata(modifier):
    payload = {
        "migrated_from_legacy_modifier": True,
        "legacy_model_name": "charsheet.Modifier",
        "legacy_modifier_id": int(modifier.id),
        "legacy_source_content_type_id": int(modifier.source_content_type_id),
        "legacy_source_object_id": int(modifier.source_object_id),
        "legacy_source_model": modifier.source_content_type.model,
        "legacy_target_kind": modifier.target_kind,
        "legacy_target_slug": modifier.target_slug,
    }
    if modifier.target_skill_id:
        payload["legacy_target_skill_id"] = int(modifier.target_skill_id)
    if modifier.target_skill_category_id:
        payload["legacy_target_skill_category_id"] = int(modifier.target_skill_category_id)
    if modifier.target_item_id:
        payload["legacy_target_item_id"] = int(modifier.target_item_id)
    if modifier.target_specialization_id:
        payload["legacy_target_specialization_id"] = int(modifier.target_specialization_id)
    if modifier.target_content_type_id and modifier.target_object_id is not None:
        payload["legacy_target_content_type_id"] = int(modifier.target_content_type_id)
        payload["legacy_target_object_id"] = int(modifier.target_object_id)
    if modifier.target_choice_definition_id:
        payload["choice_binding"] = {
            "kind": "technique_choice_definition",
            "id": int(modifier.target_choice_definition_id),
        }
    if modifier.target_race_choice_definition_id:
        payload["choice_binding"] = {
            "kind": "race_choice_definition",
            "id": int(modifier.target_race_choice_definition_id),
        }
    return payload


def _effect_target(apps, source_model):
    mapping = {
        "race": ("RaceSemanticEffect", "race_id"),
        "school": ("SchoolSemanticEffect", "school_id"),
        "trait": ("TraitSemanticEffect", "trait_id"),
        "technique": ("TechniqueSemanticEffect", "technique_id"),
        "rune": ("RuneSemanticEffect", "rune_id"),
        "item": ("ItemSemanticEffect", "item_id"),
        "characteritem": ("CharacterItemSemanticEffect", "character_item_id"),
    }
    target = mapping.get(source_model)
    if target is None:
        return None
    return apps.get_model("charsheet", target[0]), target[1]


def _source_model(apps, source_model):
    mapping = {
        "race": "Race",
        "school": "School",
        "trait": "Trait",
        "technique": "Technique",
        "rune": "Rune",
        "item": "Item",
        "characteritem": "CharacterItem",
    }
    model_name = mapping.get(source_model)
    if model_name is None:
        return None
    return apps.get_model("charsheet", model_name)


def _has_field(model, field_name):
    return any(field.name == field_name for field in model._meta.get_fields())


def forwards(apps, schema_editor):
    Modifier = apps.get_model("charsheet", "Modifier")
    modifiers = list(
        Modifier.objects.select_related(
            "source_content_type",
            "target_skill",
            "target_skill_category",
        )
        .all()
        .order_by("id")
    )
    unknown_sources = sorted({modifier.source_content_type.model for modifier in modifiers if _effect_target(apps, modifier.source_content_type.model) is None})
    if unknown_sources:
        raise RuntimeError(
            "Cannot migrate legacy Modifier rows with unsupported source types: "
            + ", ".join(unknown_sources)
        )

    skipped_orphan_modifier_ids = []
    for modifier in modifiers:
        effect_model, fk_name = _effect_target(apps, modifier.source_content_type.model)
        source_model = _source_model(apps, modifier.source_content_type.model)
        if source_model is None or not source_model.objects.filter(pk=modifier.source_object_id).exists():
            skipped_orphan_modifier_ids.append(int(modifier.id))
            continue
        existing = effect_model.objects.filter(metadata__legacy_modifier_id=modifier.id).first()
        if existing is not None:
            continue
        operator, value = _operator_and_value(modifier)
        fields = {
            fk_name: modifier.source_object_id,
            "sort_order": modifier.display_order,
            "target_domain": _target_domain(modifier),
            "target_key": _target_identifier(modifier),
            "operator": operator,
            "mode": modifier.mode,
            "value": str(value),
            "scaling": _scaling(modifier),
            "condition_set": {},
            "notes": modifier.effect_description,
            "rules_text": "",
            "metadata": _metadata(modifier),
        }
        if _has_field(effect_model, "target_choice_definition") and modifier.target_choice_definition_id:
            fields["target_choice_definition_id"] = modifier.target_choice_definition_id
        if _has_field(effect_model, "target_race_choice_definition") and modifier.target_race_choice_definition_id:
            fields["target_race_choice_definition_id"] = modifier.target_race_choice_definition_id
        effect_model.objects.create(**fields)

    migrated_count = sum(
        _effect_target(apps, modifier.source_content_type.model)[0]
        .objects.filter(metadata__legacy_modifier_id=modifier.id)
        .count()
        for modifier in modifiers
        if int(modifier.id) not in skipped_orphan_modifier_ids
    )
    expected_count = len(modifiers) - len(skipped_orphan_modifier_ids)
    if migrated_count != expected_count:
        raise RuntimeError(
            f"Legacy Modifier migration incomplete: expected {expected_count}, found {migrated_count} semantic effects."
        )
    Modifier.objects.all().delete()


def backwards(apps, schema_editor):
    for model_name in (
        "RaceSemanticEffect",
        "SchoolSemanticEffect",
        "TraitSemanticEffect",
        "TechniqueSemanticEffect",
        "RuneSemanticEffect",
        "ItemSemanticEffect",
        "CharacterItemSemanticEffect",
    ):
        model = apps.get_model("charsheet", model_name)
        model.objects.filter(metadata__migrated_from_legacy_modifier=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0354_semantic_effect_sources"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
