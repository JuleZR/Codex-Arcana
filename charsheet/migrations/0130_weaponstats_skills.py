from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0129_character_skill_specification_uniqueness"),
    ]

    operations = [
        migrations.AddField(
            model_name="weaponstats",
            name="skills",
            field=models.ManyToManyField(
                blank=True,
                help_text="Alle Fertigkeiten, mit denen diese Waffe regeltechnisch gefuehrt werden kann.",
                related_name="weapon_stats",
                to="charsheet.skill",
            ),
        ),
    ]
