from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0303_daemonic_powers"),
    ]

    operations = [
        migrations.AddField(
            model_name="daemonicpower",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterModelOptions(
            name="daemonicpowertier",
            options={
                "ordering": ["sort_number", "name", "id"],
                "verbose_name": "Daemonic power tier",
                "verbose_name_plural": "Daemonic power tiers",
            },
        ),
        migrations.AlterModelOptions(
            name="daemonicpower",
            options={
                "ordering": [
                    "tier__sort_number",
                    "tier__name",
                    "name",
                    "id",
                ],
                "verbose_name": "Daemonic power",
                "verbose_name_plural": "Daemonic powers",
            },
        ),
        migrations.AlterModelOptions(
            name="daemonicpowersemanticeffect",
            options={
                "ordering": ["power", "sort_order", "id"],
                "verbose_name": "Daemonic power semantic effect",
                "verbose_name_plural": "Daemonic power semantic effects",
            },
        ),
        migrations.AlterModelOptions(
            name="characterdaemonicpower",
            options={
                "ordering": [
                    "character",
                    "power__tier__sort_number",
                    "power__tier__name",
                    "power__name",
                    "id",
                ],
                "verbose_name": "Character daemonic power",
                "verbose_name_plural": "Character daemonic powers",
            },
        ),
        migrations.AlterModelOptions(
            name="charactercreaturedaemonicpower",
            options={
                "ordering": [
                    "creature",
                    "power__tier__sort_number",
                    "power__tier__name",
                    "power__name",
                    "id",
                ],
                "verbose_name": "Character creature daemonic power",
                "verbose_name_plural": "Character creature daemonic powers",
            },
        ),
        migrations.AlterField(
            model_name="creature",
            name="daemonic_powers",
            field=models.ManyToManyField(
                blank=True,
                related_name="base_creatures",
                to="charsheet.daemonicpower",
                verbose_name="Daemonic powers",
            ),
        ),
        migrations.AlterField(
            model_name="daemonicpower",
            name="weakness_description",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Associated weakness",
            ),
        ),
        migrations.AlterField(
            model_name="daemonicpowersemanticeffect",
            name="application_scope",
            field=models.CharField(
                choices=[
                    ("character", "Character"),
                    ("creature", "Creature"),
                    ("both", "Character and creature"),
                ],
                default="both",
                max_length=20,
                verbose_name="Application scope",
            ),
        ),
        migrations.AlterField(
            model_name="daemonicpowersemanticeffect",
            name="target_skills",
            field=models.ManyToManyField(
                blank=True,
                help_text="Optional concrete skill targets.",
                related_name="daemonic_power_semantic_effects",
                to="charsheet.skill",
            ),
        ),
        migrations.AlterField(
            model_name="technique",
            name="granted_daemonic_power_tier",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Grants exactly one character choice from this exact tier."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="granting_techniques",
                to="charsheet.daemonicpowertier",
                verbose_name="Granted daemonic power tier",
            ),
        ),
    ]
