from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0027_rename_phase_1_attribute_points_race_phase_1_points_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="character",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="character",
            name="last_opened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
