from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0082_trait_choice_definitions_and_semantic_effect_binding"),
    ]

    operations = [
        migrations.AlterField(
            model_name="traitsemanticeffect",
            name="target_domain",
            field=models.CharField(
                choices=[
                    ("skill", "skill"),
                    ("skill_category", "skill_category"),
                    ("language", "language"),
                    ("trait", "trait"),
                    ("attribute", "attribute"),
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
                ],
                default="rule_flag",
                max_length=40,
            ),
        ),
    ]
