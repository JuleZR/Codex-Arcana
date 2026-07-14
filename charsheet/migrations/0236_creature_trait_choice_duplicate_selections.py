from django.db import migrations, models
from django.db.models import Q


def mark_special_knowledge_choices(apps, schema_editor):
    CreatureTraitChoiceDefinition = apps.get_model("charsheet", "CreatureTraitChoiceDefinition")
    CreatureTraitChoiceDefinition.objects.filter(target_kind="skill").filter(
        Q(name__icontains="Besondere Kenntnisse")
        | Q(trait__name__icontains="Besondere Kenntnisse")
    ).update(allow_duplicate_selections=True)


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0235_character_creature_extra_card_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="creaturetraitchoicedefinition",
            name="allow_duplicate_selections",
            field=models.BooleanField(
                default=False,
                help_text="Allow the same target to be selected more than once for multi-slot choices.",
            ),
        ),
        migrations.RunPython(mark_special_knowledge_choices, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="creaturetraitchoice",
            name="uniq_creature_trait_choice_skill",
        ),
        migrations.RemoveConstraint(
            model_name="creaturetraitchoice",
            name="uniq_creature_trait_choice_creature_special_skill",
        ),
        migrations.RemoveConstraint(
            model_name="charactercreaturetraitchoice",
            name="uniq_character_creature_trait_choice_skill",
        ),
        migrations.RemoveConstraint(
            model_name="charactercreaturetraitchoice",
            name="uniq_character_creature_trait_choice_creature_special_skill",
        ),
    ]
