from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0128_alter_rune_allow_multiple_help_text"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="characterskill",
            name="uniq_character_skill",
        ),
        migrations.AddConstraint(
            model_name="characterskill",
            constraint=models.UniqueConstraint(
                fields=("character", "skill", "specification"),
                name="uniq_character_skill_specification",
            ),
        ),
    ]
