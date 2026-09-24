from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0404_optional_magic_school_lesson_requirement"),
    ]

    operations = [
        migrations.AddField(
            model_name="charactercreatureskill",
            name="specification",
            field=models.CharField(blank=True, default="", max_length=25),
        ),
    ]
