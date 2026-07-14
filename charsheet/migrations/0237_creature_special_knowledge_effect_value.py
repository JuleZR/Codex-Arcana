from django.db import migrations
from django.db.models import Q


def set_special_knowledge_effect_to_plus_three(apps, schema_editor):
    CreatureTraitSemanticEffect = apps.get_model("charsheet", "CreatureTraitSemanticEffect")
    CreatureTraitSemanticEffect.objects.filter(
        target_domain="skill",
        target_choice_definition__isnull=False,
    ).filter(
        Q(trait__name__icontains="Besondere Kenntnisse")
        | Q(target_choice_definition__name__icontains="Besondere Kenntnisse")
    ).update(value="3")


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0236_creature_trait_choice_duplicate_selections"),
    ]

    operations = [
        migrations.RunPython(set_special_knowledge_effect_to_plus_three, migrations.RunPython.noop),
    ]
