from django.db import migrations


WOUND_STAGE = "wound_stage"
UNWOUNDED_TARGET = "wound_stage:unverletzt"

SEMANTIC_EFFECT_MODELS = (
    "TraitSemanticEffect",
    "TechniqueSemanticEffect",
    "RaceSemanticEffect",
    "SchoolSemanticEffect",
    "SpecializationSemanticEffect",
    "RuneSemanticEffect",
    "ItemSemanticEffect",
    "CharacterItemSemanticEffect",
    "DaemonicPowerSemanticEffect",
    "VampireTraitSemanticEffect",
)


def _is_positive_whole_number(value):
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return False
    return number >= 1 and number.is_integer()


def migrate_positive_legacy_wound_stages(apps, schema_editor):
    for model_name in SEMANTIC_EFFECT_MODELS:
        Model = apps.get_model("charsheet", model_name)
        queryset = Model.objects.filter(
            target_domain="derived_stat",
            target_key=WOUND_STAGE,
            operator="flat_add",
            mode="flat",
        )
        for effect in queryset.iterator():
            if dict(effect.scaling or {}):
                continue
            if not _is_positive_whole_number(effect.value):
                continue
            metadata = dict(effect.metadata or {})
            metadata["wound_stage_position"] = "unverletzt"
            effect.target_key = UNWOUNDED_TARGET
            effect.metadata = metadata
            effect.save(update_fields=["target_key", "metadata"])


def restore_legacy_wound_stages(apps, schema_editor):
    for model_name in SEMANTIC_EFFECT_MODELS:
        Model = apps.get_model("charsheet", model_name)
        queryset = Model.objects.filter(
            target_domain="derived_stat",
            target_key=UNWOUNDED_TARGET,
            operator="flat_add",
            mode="flat",
        )
        for effect in queryset.iterator():
            metadata = dict(effect.metadata or {})
            if metadata.get("wound_stage_position") != "unverletzt":
                continue
            metadata.pop("wound_stage_position", None)
            effect.target_key = WOUND_STAGE
            effect.metadata = metadata
            effect.save(update_fields=["target_key", "metadata"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0394_encode_positional_wound_stage_targets"),
    ]

    operations = [
        migrations.RunPython(
            migrate_positive_legacy_wound_stages,
            restore_legacy_wound_stages,
        ),
    ]
