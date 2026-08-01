from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0320_require_vampire_power_weakness"),
    ]

    operations = [
        migrations.AddField(
            model_name="vampiretraitsemanticeffect",
            name="target_schools",
            field=models.ManyToManyField(
                blank=True,
                related_name="vampire_disallow_semantic_effects",
                to="charsheet.school",
            ),
        ),
    ]
