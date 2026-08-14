from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0357_weapon_skill_target_domain"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritemsemanticeffect",
            name="toggleable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="itemsemanticeffect",
            name="toggleable",
            field=models.BooleanField(default=False),
        ),
    ]
