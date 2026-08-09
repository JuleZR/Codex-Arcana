from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0336_split_character_item_semantic_effects"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="invested_cp",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Optional investierte CP fuer skalierende magische Items, z.B. 2/4/6/8/10.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="itemsemanticeffect",
            name="scale_source",
            field=models.CharField(
                blank=True,
                choices=[("", "-"), ("item_invested_cp", "Investierte CP des Items")],
                default="",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="itemsemanticeffect",
            name="scale_divisor",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="characteritemsemanticeffect",
            name="scale_source",
            field=models.CharField(
                blank=True,
                choices=[("", "-"), ("item_invested_cp", "Investierte CP des Items")],
                default="",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="characteritemsemanticeffect",
            name="scale_divisor",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
