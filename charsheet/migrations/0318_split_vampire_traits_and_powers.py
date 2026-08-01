from django.core.management.color import no_style
from django.db import migrations


def split_vampire_traits_and_powers(apps, schema_editor):
    VampireTrait = apps.get_model("charsheet", "VampireTrait")
    VampirePower = apps.get_model("charsheet", "VampirePower")
    Effect = apps.get_model("charsheet", "VampireTraitSemanticEffect")
    CharacterTrait = apps.get_model("charsheet", "CharacterVampireTrait")
    CharacterPower = apps.get_model("charsheet", "CharacterVampirePower")
    CreatureTrait = apps.get_model("charsheet", "CreatureVampireTrait")
    CreaturePower = apps.get_model("charsheet", "CreatureVampirePower")
    CharacterCreatureTrait = apps.get_model("charsheet", "CharacterCreatureVampireTrait")
    CharacterCreaturePower = apps.get_model("charsheet", "CharacterCreatureVampirePower")
    GroupCreatureTrait = apps.get_model("charsheet", "GameGroupCreatureVampireTrait")
    GroupCreaturePower = apps.get_model("charsheet", "GameGroupCreatureVampirePower")
    Draft = apps.get_model("charsheet", "CharacterCreationDraft")

    old_powers = list(VampireTrait.objects.filter(trait_type="power"))
    power_slugs = {row.slug for row in old_powers}
    for old_power in old_powers:
        VampirePower.objects.update_or_create(
            pk=old_power.pk,
            defaults={
                "name": old_power.name,
                "slug": old_power.slug,
                "description": old_power.description,
                "weakness_id": old_power.associated_weakness_id,
                "blood_cost": old_power.blood_cost,
                "handler": old_power.handler,
                "sort_order": old_power.sort_order,
                "is_active": old_power.is_active,
            },
        )
        Effect.objects.filter(trait_id=old_power.pk).update(
            trait_id=None,
            power_id=old_power.pk,
        )

    ownership_pairs = (
        (CharacterTrait, CharacterPower, "character_id"),
        (CreatureTrait, CreaturePower, "creature_id"),
        (CharacterCreatureTrait, CharacterCreaturePower, "creature_id"),
        (GroupCreatureTrait, GroupCreaturePower, "creature_id"),
    )
    power_ids = [row.pk for row in old_powers]
    for old_model, new_model, owner_field in ownership_pairs:
        for old_row in old_model.objects.filter(trait_id__in=power_ids):
            defaults = {"weakness_bought_off": bool(old_row.associated_weakness_bought_off)}
            if hasattr(old_row, "mode"):
                defaults["mode"] = old_row.mode
                defaults["purchased_without_weakness"] = None
                if old_row.associated_weakness_bought_off is None:
                    defaults["weakness_bought_off"] = None
            else:
                defaults["purchased_without_weakness"] = False
            new_model.objects.update_or_create(
                **{owner_field: getattr(old_row, owner_field), "power_id": old_row.trait_id},
                defaults=defaults,
            )
        old_model.objects.filter(trait_id__in=power_ids).delete()

    for draft in Draft.objects.all().iterator():
        state = dict(draft.state or {})
        phase_4 = dict(state.get("phase_4") or {})
        vampire = dict(phase_4.get("vampire") or {})
        old_traits = dict(vampire.get("traits") or {})
        powers = dict(vampire.get("powers") or {})
        changed = False
        for slug in list(old_traits):
            if slug not in power_slugs:
                continue
            payload = dict(old_traits.pop(slug) or {})
            powers[slug] = {"without_weakness": bool(payload.get("bought_off"))}
            changed = True
        if changed:
            vampire["traits"] = old_traits
            vampire["powers"] = powers
            phase_4["vampire"] = vampire
            state["phase_4"] = phase_4
            draft.state = state
            draft.save(update_fields=["state"])

    VampireTrait.objects.filter(trait_type="weakness").update(trait_type="disadvantage")
    VampireTrait.objects.filter(pk__in=power_ids).delete()
    reset_sql = schema_editor.connection.ops.sequence_reset_sql(no_style(), [VampirePower])
    with schema_editor.connection.cursor() as cursor:
        for statement in reset_sql:
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("charsheet", "0317_remove_charactercreaturevampiretrait_associated_weakness_bought_off_and_more"),
    ]

    operations = [
        migrations.RunPython(split_vampire_traits_and_powers, migrations.RunPython.noop),
    ]
