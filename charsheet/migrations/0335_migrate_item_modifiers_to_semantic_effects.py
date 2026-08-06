from django.db import migrations


RULE_FLAG_KEYS = {
    "wound_penalty_ignore",
    "can_act_while_out_of_action",
    "coma_ignore",
    "vampire_strength_over_race_maximum",
    "vampire_power_manual_activation",
    "vampire_power_blood_theft",
    "vampire_power_blood_sacrament",
    "vampire_power_attribute_boost",
    "vampire_regeneration",
    "armor_penalty_ignore",
    "shield_penalty_ignore",
}
COMBAT_KEYS = {
    "melee_maneuvers",
    "weapon_damage",
    "weapon_damage_dice",
}
ATTRIBUTE_KEYS = {"GE", "WA", "INT", "WILL", "ST", "KON", "CHA"}


def _target_identifier(modifier, Skill, SkillCategory, Specialization, Item):
    if modifier.target_skill_id:
        return Skill.objects.filter(pk=modifier.target_skill_id).values_list("slug", flat=True).first() or ""
    if modifier.target_skill_category_id:
        return SkillCategory.objects.filter(pk=modifier.target_skill_category_id).values_list("slug", flat=True).first() or ""
    if modifier.target_specialization_id:
        return str(modifier.target_specialization_id)
    if modifier.target_item_id:
        return str(modifier.target_item_id)
    return str(modifier.target_slug or "")


def _effect_payload(modifier, source_model, Skill, SkillCategory, Specialization, Item):
    target_kind = str(modifier.target_kind or "")
    target_key = _target_identifier(modifier, Skill, SkillCategory, Specialization, Item)
    target_domain = "metadata"
    operator = "flat_sub" if int(modifier.value or 0) < 0 else "flat_add"
    value = abs(int(modifier.value or 0))

    if target_kind == "attribute":
        target_domain = "attribute"
    elif target_kind == "stat":
        if target_key in RULE_FLAG_KEYS:
            target_domain = "rule_flag"
            operator = "set_flag" if int(modifier.value or 0) else "unset_flag"
            value = "true" if operator == "set_flag" else "false"
        elif target_key in ATTRIBUTE_KEYS:
            target_domain = "attribute"
        elif target_key in COMBAT_KEYS or target_key.startswith("dmg_"):
            target_domain = "combat"
        else:
            target_domain = "derived_stat"
    elif target_kind == "skill":
        target_domain = "combat" if target_key.startswith("dmg_") else "skill"
    elif target_kind == "category":
        target_domain = "skill_category"
    elif target_kind == "item":
        target_domain = "item"
    elif target_kind == "item_category":
        target_domain = "item_category"
    elif target_kind == "specialization":
        target_domain = "specialization"
    elif target_kind == "entity":
        target_domain = "entity"

    metadata = {
        "legacy_modifier_id": modifier.id,
        "legacy_target_kind": target_kind,
        "legacy_target_slug": str(modifier.target_slug or ""),
        "legacy_source_model": source_model,
        "migrated_from_legacy_modifier": True,
    }
    if modifier.target_skill_id:
        metadata["target_skill_id"] = modifier.target_skill_id
    if modifier.target_skill_category_id:
        metadata["target_skill_category_id"] = modifier.target_skill_category_id
    if modifier.target_item_id:
        metadata["target_item_id"] = modifier.target_item_id
    if modifier.target_specialization_id:
        metadata["target_specialization_id"] = modifier.target_specialization_id

    return {
        "target_domain": target_domain,
        "target_key": target_key,
        "operator": operator,
        "mode": str(modifier.mode or "flat"),
        "value": str(value),
        "scaling": {
            "scale_source": modifier.scale_source,
            "scale_school_id": modifier.scale_school_id,
            "scale_skill_id": modifier.scale_skill_id,
            "mul": modifier.mul,
            "div": modifier.div,
            "round_mode": modifier.round_mode,
            "cap_mode": modifier.cap_mode,
            "cap_source": modifier.cap_source,
            "min_school_level": modifier.min_school_level,
        },
        "notes": str(modifier.effect_description or ""),
        "sort_order": int(getattr(modifier, "display_order", 0) or 0),
        "metadata": {key: value for key, value in metadata.items() if value not in (None, "")},
    }


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ItemSemanticEffect = apps.get_model("charsheet", "ItemSemanticEffect")
    Modifier = apps.get_model("charsheet", "Modifier")
    Skill = apps.get_model("charsheet", "Skill")
    SkillCategory = apps.get_model("charsheet", "SkillCategory")
    Specialization = apps.get_model("charsheet", "Specialization")
    Item = apps.get_model("charsheet", "Item")
    CharacterItem = apps.get_model("charsheet", "CharacterItem")

    content_types = {
        row.model: row
        for row in ContentType.objects.filter(app_label="charsheet", model__in=("item", "characteritem"))
    }
    source_filters = []
    for model_name, content_type in content_types.items():
        source_filters.append((model_name, content_type.id))

    migrated_ids = []
    orphaned_ids = []
    for source_model, content_type_id in source_filters:
        for modifier in Modifier.objects.filter(source_content_type_id=content_type_id).order_by("id"):
            if source_model == "item":
                if not Item.objects.filter(pk=modifier.source_object_id).exists():
                    orphaned_ids.append(modifier.id)
                    continue
            elif not CharacterItem.objects.filter(pk=modifier.source_object_id).exists():
                orphaned_ids.append(modifier.id)
                continue
            kwargs = _effect_payload(modifier, source_model, Skill, SkillCategory, Specialization, Item)
            if source_model == "item":
                kwargs["item_id"] = modifier.source_object_id
            else:
                kwargs["character_item_id"] = modifier.source_object_id
            ItemSemanticEffect.objects.create(**kwargs)
            migrated_ids.append(modifier.id)

    stale_ids = [*migrated_ids, *orphaned_ids]
    if stale_ids:
        Modifier.objects.filter(id__in=stale_ids).delete()


def backwards(apps, schema_editor):
    ItemSemanticEffect = apps.get_model("charsheet", "ItemSemanticEffect")
    ItemSemanticEffect.objects.filter(metadata__migrated_from_legacy_modifier=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0334_itemsemanticeffect"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
