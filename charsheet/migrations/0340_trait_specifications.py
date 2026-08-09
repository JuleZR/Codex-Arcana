from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0339_alter_shieldstats_maneuver_attribute_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="trait",
            name="has_specification",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="charactertrait",
            name="specification",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
