from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0085_merge_0083_0084"),
    ]

    operations = [
        migrations.AddField(
            model_name="traitchoicedefinition",
            name="allowed_proficiency_group",
            field=models.CharField(
                blank=True,
                choices=[
                    ("skill_fine_motor", "Feinmotorische Fertigkeiten"),
                    ("skill_gross_motor", "Grobmotorische Fertigkeiten"),
                    ("skill_social", "Soziale Fertigkeiten"),
                    ("skill_knowledge", "Wissensfertigkeiten"),
                    ("skill_combat", "Waffenfertigkeiten"),
                    ("foreign_languages", "Sprachen (außer Muttersprache)"),
                ],
                default="",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="charactertraitchoice",
            name="selected_proficiency_group",
            field=models.CharField(
                blank=True,
                choices=[
                    ("skill_fine_motor", "Feinmotorische Fertigkeiten"),
                    ("skill_gross_motor", "Grobmotorische Fertigkeiten"),
                    ("skill_social", "Soziale Fertigkeiten"),
                    ("skill_knowledge", "Wissensfertigkeiten"),
                    ("skill_combat", "Waffenfertigkeiten"),
                    ("foreign_languages", "Sprachen (außer Muttersprache)"),
                ],
                default="",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="traitchoicedefinition",
            name="target_kind",
            field=models.CharField(
                choices=[
                    ("attribute", "Attribute"),
                    ("skill", "Skill"),
                    ("skill_category", "Skill Category"),
                    ("proficiency_group", "Proficiency Group"),
                    ("item", "Item"),
                    ("item_category", "Item Category"),
                    ("specialization", "Specialization"),
                    ("text", "Free Text"),
                    ("entity", "Other Entity"),
                ],
                help_text="What kind of thing must be selected for this trait decision.",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="traitsemanticeffect",
            name="target_domain",
            field=models.CharField(
                choices=[
                    ("skill", "skill"),
                    ("skill_category", "skill_category"),
                    ("language", "language"),
                    ("proficiency_group", "proficiency_group"),
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
