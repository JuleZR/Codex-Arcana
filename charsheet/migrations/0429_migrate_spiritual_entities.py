from django.db import migrations
from django.db.models import Q
from django.utils.text import slugify

CARD_FIELDS = (
    "card_name",
    "description",
    "g_ability",
    "fluff",
    "symbol_image",
    "god_image",
)


def unique_value(model, alias, field, value, fallback, length):
    base = (value or fallback)[:length]
    candidate = base
    suffix = 1
    while model.objects.using(alias).filter(**{field: candidate}).exists():
        suffix += 1
        ending = f"-{suffix}"
        candidate = base[: length - len(ending)] + ending
    return candidate


def card_values(source):
    return {field: str(getattr(source, field) or "") for field in CARD_FIELDS}


def compatible_metadata(entity, values):
    return all(
        not value
        or not str(getattr(entity, field) or "")
        or str(getattr(entity, field)) == value
        for field, value in values.items()
    )


def migrate_entities(apps, schema_editor):
    alias = schema_editor.connection.alias
    Entity = apps.get_model("charsheet", "DivineEntity")
    EntityType = apps.get_model("charsheet", "DivineEntityType")
    Pantheon = apps.get_model("charsheet", "Pantheon")
    types = {}
    for slug, name in (
        ("god", "Gott"),
        ("power-animal", "Krafttier"),
        ("ancestor-spirit", "Ahnengeist"),
        ("nature-spirit", "Naturgeist"),
        ("kami", "Kami"),
        ("demon-lord", "Dämonenfürst"),
    ):
        types[slug], _ = EntityType.objects.using(alias).get_or_create(
            slug=slug,
            defaults={"name": name},
        )

    spiritual_sources = []
    for model_name in ("DruidCult", "ShamanPatron"):
        for source in (
            apps.get_model("charsheet", model_name).objects.using(alias).all()
        ):
            if model_name == "DruidCult" or source.patron_kind == "totem":
                entity_type = types["power-animal"]
            elif source.patron_kind == "ancestor_spirit":
                entity_type = types["ancestor-spirit"]
            else:
                kind = source.patron_kind or "spirit"
                entity_type, _ = EntityType.objects.using(alias).get_or_create(
                    slug=slugify(kind) or "spirit",
                    defaults={"name": kind},
                )
            spiritual_sources.append((source, entity_type))

    # Exact text is the identity; keep whitespace and case in old names.
    pantheons = {
        entry.name: entry for entry in Pantheon.objects.using(alias).all()
    }
    for entity in (
        Entity.objects.using(alias).select_related("school__type").iterator()
    ):
        text = entity.legacy_pantheon
        if text and text not in pantheons:
            pantheons[text] = Pantheon.objects.using(alias).create(
                name=text,
                slug=unique_value(
                    Pantheon, alias, "slug", slugify(text), "pantheon", 160
                ),
            )
        entity.pantheon_id = pantheons[text].pk if text else None
        school = entity.school
        school_type = school.type if school else None
        is_demon = (
            text == "Dämonenfürsten"
            or (
                school
                and school.name.casefold().startswith(("kultist", "cultist"))
            )
            or (
                school_type and school_type.name.casefold() in {"kult", "cult"}
            )
            or (
                school_type
                and school_type.slug.casefold()
                in {"kult", "cult", "school_kult", "school_cult"}
            )
        )
        entity.entity_type_id = types["demon-lord" if is_demon else "god"].pk
        # Recognize already centralized spiritual records only through matching
        # identity, school and compatible metadata, never through a fuzzy name.
        matching_types = {
            entity_type.pk
            for source, entity_type in spiritual_sources
            if source.school_id == entity.school_id
            and (
                entity.name in {source.name, source.card_name}
                or entity.slug == source.slug
            )
            and compatible_metadata(entity, card_values(source))
        }
        if len(matching_types) == 1:
            entity.entity_type_id = matching_types.pop()
        entity.save(using=alias, update_fields=["pantheon", "entity_type"])

    for source, entity_type in spiritual_sources:
        model_name = source._meta.object_name
        values = card_values(source)
        label = source.card_name or source.name
        candidates = (
            Entity.objects.using(alias)
            .filter(
                Q(name=label) | Q(name=source.name) | Q(slug=source.slug),
                entity_type=entity_type,
            )
            .order_by("pk")
        )
        # Reuse only an unambiguous identity with compatible metadata.
        matches = [
            entry for entry in candidates if compatible_metadata(entry, values)
        ]
        if len(matches) == 1:
            entity = matches[0]
            for field, value in values.items():
                if value and not getattr(entity, field):
                    setattr(entity, field, value)
            entity.save(using=alias)
        else:
            entity = Entity.objects.using(alias).create(
                name=unique_value(
                    Entity, alias, "name", label, "Entität", 120
                ),
                slug=unique_value(
                    Entity, alias, "slug", source.slug, "entity", 120
                ),
                entity_type=entity_type,
                school=None,
                **values,
            )
        source.entity_id = entity.pk
        source.save(using=alias, update_fields=["entity"])
        # Check every transferred field and both image paths before removal.
        if any(
            value and str(getattr(entity, field) or "") != value
            for field, value in values.items()
        ):
            raise RuntimeError(
                f"Incomplete entity migration: {model_name} {source.pk}"
            )

    if Entity.objects.using(alias).filter(entity_type__isnull=True).exists():
        raise RuntimeError("Divine entities without a type after migration")
    for entity in (
        Entity.objects.using(alias)
        .exclude(legacy_pantheon="")
        .select_related("pantheon")
    ):
        if (
            entity.pantheon is None
            or entity.pantheon.name != entity.legacy_pantheon
        ):
            raise RuntimeError(f"Pantheon information lost: {entity.pk}")
    for model_name in ("DruidCult", "ShamanPatron"):
        if (
            apps.get_model("charsheet", model_name)
            .objects.using(alias)
            .filter(entity__isnull=True)
            .exists()
        ):
            raise RuntimeError(
                f"Unbound spiritual configuration: {model_name}"
            )


def restore_metadata(apps, schema_editor):
    alias = schema_editor.connection.alias
    Entity = apps.get_model("charsheet", "DivineEntity")
    for entity in (
        Entity.objects.using(alias).select_related("pantheon").iterator()
    ):
        entity.legacy_pantheon = (
            entity.pantheon.name if entity.pantheon_id else ""
        )
        entity.save(using=alias, update_fields=["legacy_pantheon"])
    for model_name in ("DruidCult", "ShamanPatron"):
        Source = apps.get_model("charsheet", model_name)
        for source in (
            Source.objects.using(alias)
            .select_related("entity__entity_type")
            .iterator()
        ):
            if not source.entity_id:
                continue
            for field, value in card_values(source.entity).items():
                setattr(source, field, value)
            if model_name == "ShamanPatron":
                slug = source.entity.entity_type.slug
                source.patron_kind = {
                    "power-animal": "totem",
                    "ancestor-spirit": "ancestor_spirit",
                }.get(slug, slug)
            source.save(using=alias)


class Migration(migrations.Migration):
    dependencies = [("charsheet", "0428_divine_entity_structure")]
    operations = [migrations.RunPython(migrate_entities, restore_metadata)]
