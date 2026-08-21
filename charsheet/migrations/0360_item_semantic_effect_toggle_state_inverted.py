from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0359_semantic_effect_race_conditions"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritemsemanticeffect",
            name="toggle_state_inverted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="itemsemanticeffect",
            name="toggle_state_inverted",
            field=models.BooleanField(default=False),
        ),
    ]
