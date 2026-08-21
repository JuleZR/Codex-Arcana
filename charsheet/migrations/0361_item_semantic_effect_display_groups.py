from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0360_item_semantic_effect_toggle_state_inverted"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteritemsemanticeffect",
            name="display_group",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="characteritemsemanticeffect",
            name="display_group_append",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="itemsemanticeffect",
            name="display_group",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="itemsemanticeffect",
            name="display_group_append",
            field=models.BooleanField(default=False),
        ),
    ]
