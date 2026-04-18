from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0109_spell_grade_adds_school_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="spell",
            name="panel_badge_label",
            field=models.CharField(blank=True, default="Zauber", max_length=30),
        ),
    ]
