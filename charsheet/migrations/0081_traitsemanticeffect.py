from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0080_modifier_scale_skill_alter_modifier_cap_source_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TraitSemanticEffect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("target_domain", models.CharField(choices=[("skill", "skill"), ("skill_category", "skill_category"), ("trait", "trait"), ("attribute", "attribute"), ("derived_stat", "derived_stat"), ("resource", "resource"), ("resistance", "resistance"), ("movement", "movement"), ("combat", "combat"), ("perception", "perception"), ("economy", "economy"), ("social", "social"), ("rule_flag", "rule_flag"), ("capability", "capability"), ("behavior", "behavior"), ("tag", "tag"), ("metadata", "metadata"), ("item", "item"), ("item_category", "item_category"), ("specialization", "specialization"), ("entity", "entity")], default="rule_flag", max_length=40)),
                ("target_key", models.CharField(max_length=120)),
                ("operator", models.CharField(choices=[("flat_add", "flat_add"), ("flat_sub", "flat_sub"), ("multiply", "multiply"), ("override", "override"), ("min_value", "min_value"), ("max_value", "max_value"), ("set_flag", "set_flag"), ("unset_flag", "unset_flag"), ("add_tag", "add_tag"), ("remove_tag", "remove_tag"), ("grant_capability", "grant_capability"), ("remove_capability", "remove_capability"), ("grant_immunity", "grant_immunity"), ("grant_vulnerability", "grant_vulnerability"), ("change_resource_cap", "change_resource_cap"), ("change_starting_funds", "change_starting_funds"), ("change_appearance_class", "change_appearance_class"), ("change_social_status", "change_social_status"), ("reroll_grant", "reroll_grant"), ("reroll_forbid", "reroll_forbid"), ("repeat_action_allowed", "repeat_action_allowed"), ("action_cost_change", "action_cost_change"), ("conditional_bonus", "conditional_bonus"), ("conditional_penalty", "conditional_penalty")], default="flat_add", max_length=40)),
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
                ("trait", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="semantic_effects", to="charsheet.trait")),
            ],
            options={
                "ordering": ["trait", "sort_order", "id"],
            },
        ),
    ]
