from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "charsheet",
            "0304_daemonic_power_description_and_english_metadata",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="daemonicpowersemanticeffect",
            name="target_domain",
            field=models.CharField(
                choices=[
                    ("skill", "skill"),
                    ("skill_category", "skill_category"),
                    ("skill_rank", "skill_rank"),
                    ("skill_rank_cap", "skill_rank_cap"),
                    ("language", "language"),
                    ("proficiency_group", "proficiency_group"),
                    ("trait", "trait"),
                    ("attribute", "attribute"),
                    ("attribute_cap", "attribute_cap"),
                    ("derived_stat", "derived_stat"),
                    ("resource", "resource"),
                    ("resistance", "resistance"),
                    ("movement", "movement"),
                    ("combat", "combat"),
                    ("perception", "perception"),
                    ("economy", "economy"),
                    ("social", "social"),
                    ("rule_flag", "rule_flag"),
                    ("capability", "capability"),
                    ("behavior", "behavior"),
                    ("tag", "tag"),
                    ("metadata", "metadata"),
                    ("item", "item"),
                    ("item_category", "item_category"),
                    ("specialization", "specialization"),
                    ("entity", "entity"),
                    ("creature_special_skill", "creature_special_skill"),
                    ("creature_attack", "creature_attack"),
                    ("creature_attack_damage", "creature_attack_damage"),
                    (
                        "creature_attack_type_damage",
                        "creature_attack_type_damage",
                    ),
                    ("daemonic_power", "daemonic_power"),
                ],
                default="rule_flag",
                max_length=40,
            ),
        ),
    ]
