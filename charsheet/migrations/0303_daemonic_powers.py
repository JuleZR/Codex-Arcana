from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0302_charactercreaturelanguage"),
    ]

    operations = [
        migrations.CreateModel(
            name="DaemonicPowerTier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("sort_number", models.PositiveIntegerField(db_index=True, default=0)),
            ],
            options={
                "verbose_name": "Dämonische-Kraft-Tier",
                "verbose_name_plural": "Dämonische-Kraft-Tiers",
                "ordering": ["sort_number", "name", "id"],
            },
        ),
        migrations.CreateModel(
            name="DaemonicPower",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("slug", models.SlugField(max_length=150, unique=True)),
                ("weakness_description", models.TextField(blank=True, default="", verbose_name="Zugehörige Schwäche")),
                ("tier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="powers", to="charsheet.daemonicpowertier")),
            ],
            options={
                "verbose_name": "Dämonische Kraft",
                "verbose_name_plural": "Dämonische Kräfte",
                "ordering": ["tier__sort_number", "tier__name", "name", "id"],
            },
        ),
        migrations.AddField(
            model_name="creature",
            name="daemonic_powers",
            field=models.ManyToManyField(blank=True, related_name="base_creatures", to="charsheet.daemonicpower", verbose_name="Dämonische Kräfte"),
        ),
        migrations.AddField(
            model_name="technique",
            name="granted_daemonic_power_tier",
            field=models.ForeignKey(blank=True, help_text="Gewährt genau eine Charakterwahl aus diesem exakten Tier.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="granting_techniques", to="charsheet.daemonicpowertier", verbose_name="Gewährt dämonische Kraft aus Tier"),
        ),
        migrations.CreateModel(
            name="DaemonicPowerSemanticEffect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("application_scope", models.CharField(choices=[("character", "Charakter"), ("creature", "Kreatur"), ("both", "Charakter und Kreatur")], default="both", max_length=20, verbose_name="Geltungsbereich")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("target_domain", models.CharField(choices=[("skill", "skill"), ("skill_category", "skill_category"), ("skill_rank", "skill_rank"), ("skill_rank_cap", "skill_rank_cap"), ("language", "language"), ("proficiency_group", "proficiency_group"), ("trait", "trait"), ("attribute", "attribute"), ("attribute_cap", "attribute_cap"), ("derived_stat", "derived_stat"), ("resource", "resource"), ("resistance", "resistance"), ("movement", "movement"), ("combat", "combat"), ("perception", "perception"), ("economy", "economy"), ("social", "social"), ("rule_flag", "rule_flag"), ("capability", "capability"), ("behavior", "behavior"), ("tag", "tag"), ("metadata", "metadata"), ("item", "item"), ("item_category", "item_category"), ("specialization", "specialization"), ("entity", "entity"), ("creature_special_skill", "creature_special_skill"), ("creature_attack", "creature_attack"), ("creature_attack_damage", "creature_attack_damage"), ("creature_attack_type_damage", "creature_attack_type_damage")], default="rule_flag", max_length=40)),
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
                ("condition_text", models.TextField(blank=True, default="")),
                ("notes", models.TextField(blank=True, default="")),
                ("rules_text", models.TextField(blank=True, default="")),
                ("visibility", models.CharField(choices=[("public", "public"), ("internal", "internal"), ("story", "story")], default="public", max_length=20)),
                ("hidden", models.BooleanField(default=False)),
                ("sheet_relevant", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("power", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="semantic_effects", to="charsheet.daemonicpower")),
                ("target_skills", models.ManyToManyField(blank=True, help_text="Optionale konkrete Fertigkeitsziele.", related_name="daemonic_power_semantic_effects", to="charsheet.skill")),
            ],
            options={
                "verbose_name": "Semantic Effect einer dämonischen Kraft",
                "verbose_name_plural": "Semantic Effects dämonischer Kräfte",
                "ordering": ["power", "sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="CharacterDaemonicPower",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daemonic_power_ownerships", to="charsheet.character")),
                ("granting_technique", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="granted_character_daemonic_powers", to="charsheet.technique")),
                ("power", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="character_ownerships", to="charsheet.daemonicpower")),
            ],
            options={
                "verbose_name": "Dämonische Kraft eines Charakters",
                "verbose_name_plural": "Dämonische Kräfte von Charakteren",
                "ordering": ["character", "power__tier__sort_number", "power__tier__name", "power__name", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="characterdaemonicpower",
            constraint=models.UniqueConstraint(fields=("character", "power"), name="uniq_character_daemonic_power"),
        ),
        migrations.AddConstraint(
            model_name="characterdaemonicpower",
            constraint=models.UniqueConstraint(fields=("character", "granting_technique"), name="uniq_character_daemonic_power_grant"),
        ),
        migrations.CreateModel(
            name="CharacterCreatureDaemonicPower",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creature", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daemonic_power_additions", to="charsheet.charactercreature")),
                ("power", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="character_creature_ownerships", to="charsheet.daemonicpower")),
            ],
            options={
                "verbose_name": "Ausgebildete dämonische Kraft einer Kreatur",
                "verbose_name_plural": "Ausgebildete dämonische Kräfte von Kreaturen",
                "ordering": ["creature", "power__tier__sort_number", "power__tier__name", "power__name", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="charactercreaturedaemonicpower",
            constraint=models.UniqueConstraint(fields=("creature", "power"), name="uniq_character_creature_daemonic_power"),
        ),
    ]
