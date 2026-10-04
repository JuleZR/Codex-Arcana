"""Keep ordinary bindings unique while allowing distinct paid choice cards."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0417_advanced_simple_specializations"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="charactercreature",
            name="uniq_character_creature_source_binding_legacy",
        ),
        migrations.AddConstraint(
            model_name="charactercreature",
            constraint=models.UniqueConstraint(
                fields=["owner", "source_binding"],
                condition=models.Q(
                    source_binding__isnull=False,
                    source_character_item__isnull=True,
                    source_character_technique__isnull=True,
                    semantic_effect_key="",
                ),
                name="uniq_character_creature_source_binding_legacy",
            ),
        ),
    ]
