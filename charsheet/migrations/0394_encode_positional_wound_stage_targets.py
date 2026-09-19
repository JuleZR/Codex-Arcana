from django.db import migrations


WOUND_STAGE = "wound_stage"
WOUND_STAGE_PREFIX = f"{WOUND_STAGE}:"
POSITION_KEY = "wound_stage_position"
VALID_POSITIONS = {
    "angeschlagen",
    "verletzt",
    "verwundet",
    "schwer_verwundet",
    "ausser_gefecht",
    "koma",
}


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


def encode_positional_wound_targets(apps, schema_editor):
    for model_name in SEMANTIC_EFFECT_MODELS:
        Model = apps.get_model("charsheet", model_name)
        for effect in Model.objects.filter(
            target_domain="derived_stat",
            target_key=WOUND_STAGE,
        ).iterator():
            metadata = dict(effect.metadata or {})
            position = str(metadata.get(POSITION_KEY) or "").strip()
            if position not in VALID_POSITIONS:
                continue
            effect.target_key = f"{WOUND_STAGE_PREFIX}{position}"
            effect.save(update_fields=["target_key"])


def decode_positional_wound_targets(apps, schema_editor):
    for model_name in SEMANTIC_EFFECT_MODELS:
        Model = apps.get_model("charsheet", model_name)
        for effect in Model.objects.filter(
            target_domain="derived_stat",
            target_key__startswith=WOUND_STAGE_PREFIX,
        ).iterator():
            position = str(effect.target_key)[len(WOUND_STAGE_PREFIX):]
            if position not in VALID_POSITIONS:
                continue
            metadata = dict(effect.metadata or {})
            metadata[POSITION_KEY] = position
            effect.target_key = WOUND_STAGE
            effect.metadata = metadata
            effect.save(update_fields=["target_key", "metadata"])


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0393_dashboard_announcement"),
    ]

    operations = [
        migrations.RunPython(
            encode_positional_wound_targets,
            decode_positional_wound_targets,
        ),
    ]
