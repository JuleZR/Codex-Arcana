import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0237_creature_special_knowledge_effect_value"),
    ]

    operations = [
        migrations.AlterField(
            model_name="creaturetraitchoicedefinition",
            name="allowed_derived_stat",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="charactercreaturetraitchoice",
            name="selected_creature_attack",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="charsheet.creatureattack",
            ),
        ),
        migrations.AddField(
            model_name="creaturetraitchoice",
            name="selected_creature_attack",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="charsheet.creatureattack",
            ),
        ),
        migrations.AddConstraint(
            model_name="charactercreaturetraitchoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(selected_creature_attack__isnull=False),
                fields=("character_creature_trait", "definition", "selected_creature_attack"),
                name="uniq_character_creature_trait_choice_attack",
            ),
        ),
        migrations.AddConstraint(
            model_name="creaturetraitchoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(selected_creature_attack__isnull=False),
                fields=("creature_trait", "definition", "selected_creature_attack"),
                name="uniq_creature_trait_choice_attack",
            ),
        ),
    ]
