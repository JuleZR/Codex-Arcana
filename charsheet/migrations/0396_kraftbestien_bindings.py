from django.db import migrations, models
import django.db.models.deletion


def seed_kraftbestie_traits(apps, schema_editor):
    CreatureTraitDefinition = apps.get_model(
        "charsheet",
        "CreatureTraitDefinition",
    )
    seeds = [
        {
            "name": "Aura der Alten Goetter",
            "slug": "aura_der_alten_goetter",
            "trait_type": "advantage",
            "description": (
                "Kraftbestien tragen eine erkennbare Aura der Alten "
                "Goetter."
            ),
            "points_per_level": 0,
            "hide_from_creature_training": True,
        },
        {
            "name": "Eisenallergie",
            "slug": "eisenallergie",
            "trait_type": "disadvantage",
            "description": "Kraftbestien reagieren empfindlich auf Eisen.",
            "points_per_level": 0,
            "hide_from_creature_training": True,
        },
        {
            "name": "Magieresistenz",
            "slug": "magieresistenz",
            "trait_type": "advantage",
            "description": "Erhoeht die Widerstandskraft gegen Magie.",
            "points_per_level": 0,
            "hide_from_creature_training": True,
        },
    ]
    for values in seeds:
        slug = values["slug"]
        defaults = {
            key: value for key, value in values.items()
            if key != "slug"
        }
        CreatureTraitDefinition.objects.update_or_create(
            slug=slug,
            defaults=defaults,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("charsheet", "0395_migrate_legacy_wound_stage_to_unverletzt"),
    ]

    operations = [
        migrations.AddField(
            model_name="creaturesourcebinding",
            name="creature_type_filter",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Optionale Vorlagenbeschraenkung im Auswahlmodus. "
                    "Kraftbestien werden immer auf Typ 'tier' begrenzt."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="source_bindings",
                to="charsheet.creaturetype",
            ),
        ),
        migrations.AddField(
            model_name="creaturesourcebinding",
            name="is_kraftbestie",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Nur im Auswahlmodus: gewaehlte Tier-Vorlagen werden "
                    "als Kraftbestien berechnet."
                ),
                verbose_name="Kraftbestie",
            ),
        ),
        migrations.AddField(
            model_name="creaturesourcebinding",
            name="use_creature_overlay",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Nur im Auswahlmodus mit Binding-Kreatur: Note-Skills, "
                    "Traits, besondere Fertigkeiten und Sprachen werden "
                    "ergaenzt."
                ),
                verbose_name="Binding-Kreatur als Overlay nutzen",
            ),
        ),
        migrations.RunPython(
            seed_kraftbestie_traits,
            migrations.RunPython.noop,
        ),
    ]
