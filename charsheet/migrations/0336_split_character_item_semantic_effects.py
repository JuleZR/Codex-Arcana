from django.db import migrations, models
import django.db.models.deletion


EFFECT_FIELD_NAMES = (
    "sort_order",
    "target_domain",
    "target_key",
    "operator",
    "mode",
    "value",
    "value_min",
    "value_max",
    "formula",
    "scaling",
    "stack_behavior",
    "condition_set",
    "active_flag",
    "priority",
    "notes",
    "rules_text",
    "visibility",
    "hidden",
    "sheet_relevant",
    "metadata",
)


def split_character_item_effects(apps, schema_editor):
    item_effect_model = apps.get_model("charsheet", "ItemSemanticEffect")
    character_item_effect_model = apps.get_model("charsheet", "CharacterItemSemanticEffect")
    migrated_rows = []
    for effect in item_effect_model.objects.filter(character_item_id__isnull=False).order_by("id"):
        values = {field_name: getattr(effect, field_name) for field_name in EFFECT_FIELD_NAMES}
        migrated_rows.append(
            character_item_effect_model(
                character_item_id=effect.character_item_id,
                **values,
            )
        )
    if migrated_rows:
        character_item_effect_model.objects.bulk_create(migrated_rows)
    item_effect_model.objects.filter(character_item_id__isnull=False).delete()


def merge_character_item_effects(apps, schema_editor):
    item_effect_model = apps.get_model("charsheet", "ItemSemanticEffect")
    character_item_effect_model = apps.get_model("charsheet", "CharacterItemSemanticEffect")
    migrated_rows = []
    for effect in character_item_effect_model.objects.order_by("id"):
        values = {field_name: getattr(effect, field_name) for field_name in EFFECT_FIELD_NAMES}
        migrated_rows.append(
            item_effect_model(
                character_item_id=effect.character_item_id,
                **values,
            )
        )
    if migrated_rows:
        item_effect_model.objects.bulk_create(migrated_rows)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0335_migrate_item_modifiers_to_semantic_effects"),
    ]

    operations = [
        migrations.CreateModel(
            name="CharacterItemSemanticEffect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("target_domain", models.CharField(choices=[("skill", "skill"), ("skill_category", "skill_category"), ("skill_rank", "skill_rank"), ("skill_rank_cap", "skill_rank_cap"), ("language", "language"), ("proficiency_group", "proficiency_group"), ("trait", "trait"), ("attribute", "attribute"), ("attribute_cap", "attribute_cap"), ("derived_stat", "derived_stat"), ("resource", "resource"), ("resistance", "resistance"), ("movement", "movement"), ("combat", "combat"), ("perception", "perception"), ("economy", "economy"), ("social", "social"), ("rule_flag", "rule_flag"), ("capability", "capability"), ("behavior", "behavior"), ("tag", "tag"), ("metadata", "metadata"), ("item", "item"), ("item_category", "item_category"), ("specialization", "specialization"), ("entity", "entity"), ("creature_card", "creature_card")], default="rule_flag", max_length=40)),
                ("target_key", models.CharField(blank=True, default="", max_length=120)),
                ("operator", models.CharField(choices=[("flat_add", "flat_add"), ("flat_sub", "flat_sub"), ("multiply", "multiply"), ("floor_divide", "floor_divide"), ("override", "override"), ("min_value", "min_value"), ("max_value", "max_value"), ("set_flag", "set_flag"), ("unset_flag", "unset_flag"), ("add_tag", "add_tag"), ("remove_tag", "remove_tag"), ("grant_capability", "grant_capability"), ("remove_capability", "remove_capability"), ("grant_immunity", "grant_immunity"), ("grant_vulnerability", "grant_vulnerability"), ("change_resource_cap", "change_resource_cap"), ("change_starting_funds", "change_starting_funds"), ("change_appearance_class", "change_appearance_class"), ("change_social_status", "change_social_status"), ("reroll_grant", "reroll_grant"), ("reroll_forbid", "reroll_forbid"), ("repeat_action_allowed", "repeat_action_allowed"), ("action_cost_change", "action_cost_change"), ("conditional_bonus", "conditional_bonus"), ("conditional_penalty", "conditional_penalty")], default="flat_add", max_length=40)),
                ("mode", models.CharField(default="flat", max_length=20)),
                ("value", models.CharField(blank=True, default="", max_length=200)),
                ("value_min", models.IntegerField(blank=True, null=True)),
                ("value_max", models.IntegerField(blank=True, null=True)),
                ("formula", models.CharField(blank=True, default="", max_length=200)),
                ("scaling", models.JSONField(blank=True, default=dict)),
                ("stack_behavior", models.CharField(choices=[("stack", "stack"), ("highest", "highest"), ("lowest", "lowest"), ("override", "override"), ("unique_by_source", "unique_by_source")], default="stack", max_length=40)),
                ("condition_set", models.JSONField(blank=True, default=dict)),
                ("active_flag", models.BooleanField(default=True)),
                ("priority", models.IntegerField(default=0)),
                ("notes", models.TextField(blank=True, default="")),
                ("rules_text", models.TextField(blank=True, default="")),
                ("visibility", models.CharField(choices=[("public", "public"), ("internal", "internal"), ("story", "story")], default="public", max_length=20)),
                ("hidden", models.BooleanField(default=False)),
                ("sheet_relevant", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("character_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="semantic_effects", to="charsheet.characteritem")),
            ],
            options={
                "ordering": ["character_item", "sort_order", "id"],
            },
        ),
        migrations.RunPython(split_character_item_effects, merge_character_item_effects),
        migrations.RemoveConstraint(
            model_name="itemsemanticeffect",
            name="item_semantic_effect_exactly_one_source",
        ),
        migrations.RemoveField(
            model_name="itemsemanticeffect",
            name="character_item",
        ),
        migrations.AlterField(
            model_name="itemsemanticeffect",
            name="item",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="semantic_effects", to="charsheet.item"),
        ),
        migrations.AlterModelOptions(
            name="itemsemanticeffect",
            options={"ordering": ["item", "sort_order", "id"]},
        ),
    ]
