import django.db.models.deletion
from django.db import migrations, models

from charsheet.constants import QUALITY_COMMON


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0215_creaturetraitdefinition_points_by_level_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="creaturecardbinding",
            name="quality",
            field=models.ForeignKey(
                db_column="quality",
                default=QUALITY_COMMON,
                help_text=(
                    "Quality used when this binding is triggered by a technique. "
                    "Item-triggered cards use the owned item's quality."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="creature_card_bindings",
                to="charsheet.quality",
            ),
        ),
        migrations.AddField(
            model_name="charactercreaturecard",
            name="source_character_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="creature_cards",
                to="charsheet.characteritem",
            ),
        ),
        migrations.AddField(
            model_name="charactercreaturecard",
            name="source_character_technique",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="creature_cards",
                to="charsheet.charactertechnique",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="charactercreaturecard",
            name="uniq_character_creature_card_binding",
        ),
        migrations.AddConstraint(
            model_name="charactercreaturecard",
            constraint=models.UniqueConstraint(
                condition=models.Q(source_character_item__isnull=True, source_character_technique__isnull=True),
                fields=("character", "binding"),
                name="uniq_character_creature_card_binding_legacy",
            ),
        ),
        migrations.AddConstraint(
            model_name="charactercreaturecard",
            constraint=models.UniqueConstraint(
                condition=models.Q(source_character_item__isnull=False),
                fields=("character", "binding", "source_character_item"),
                name="uniq_character_creature_card_item_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="charactercreaturecard",
            constraint=models.UniqueConstraint(
                condition=models.Q(source_character_technique__isnull=False),
                fields=("character", "binding", "source_character_technique"),
                name="uniq_character_creature_card_technique_source",
            ),
        ),
    ]
