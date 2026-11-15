"""Typed spiritual focus targets and their dynamic display labels."""

from django.core.exceptions import ValidationError

from charsheet.models import (
    CharacterDivineEntity, CharacterDruidCult, CharacterShamanPatron,
    DivineEntity, DruidCult, School, ShamanPatron,
)
from charsheet.religion_rules import (
    core_aspects_for_source, divine_entities_for_school,
    is_divine_entity_school, is_druid_school, is_shaman_school,
)


TARGET_TYPES = {
    "divine_entity": (DivineEntity, "Gottheit / Entität"),
    "druid_cult": (DruidCult, "Druidenzirkel"),
    "shaman_patron": (ShamanPatron, "Totem / Ahnengeist"),
}


def join_focus_labels(labels):
    if len(labels) > 1:
        return f"{', '.join(labels[:-1])} und {labels[-1]}"
    return "".join(labels)


def focus_target_kind(school):
    if is_druid_school(school):
        return "druid_cult"
    if is_shaman_school(school):
        return "shaman_patron"
    return "divine_entity" if is_divine_entity_school(school) else ""


def focus_target_options(school, kind=None):
    kind = kind or focus_target_kind(school)
    if kind == "divine_entity":
        return divine_entities_for_school(school.pk)
    if kind in TARGET_TYPES:
        return TARGET_TYPES[kind][0].objects.filter(
            school=school,
        ).order_by("name", "pk")
    return None


def focus_target_catalog():
    """Return editor options, independently for each applicable school."""
    result = {}
    for school in School.objects.select_related("type").prefetch_related(
        "druid_cults", "shaman_patrons",
    ).order_by("name"):
        kind = focus_target_kind(school)
        if kind:
            result[str(school.pk)] = {
                "name": school.name, "kind": kind,
                "label": TARGET_TYPES[kind][1],
                "options": [
                    {"pk": entry.pk, "name": entry.name}
                    for entry in focus_target_options(school, kind)
                ],
            }
    return result


def normalize_focus_targets(raw_targets, school_ids):
    """Validate typed IDs without changing ordinary saved school targets."""
    if not isinstance(raw_targets, list) or len(raw_targets) > 100:
        raise ValidationError("Ungültige spirituelle Fokusziele.")
    schools = School.objects.in_bulk(school_ids)
    targets = []
    for raw in raw_targets:
        try:
            school_id = int(raw["school_id"])
            kind = str(raw["kind"])
            object_id = int(raw["object_id"])
            school = schools[school_id]
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Ungültige spirituelle Fokuszuordnung.")
        if kind != focus_target_kind(school):
            raise ValidationError("Die Fokus-Zielart passt nicht zur Schule.")
        options = focus_target_options(school, kind)
        if options is None or not options.filter(pk=object_id).exists():
            raise ValidationError(
                "Das Fokusziel gehört nicht zu dieser Schule.",
            )
        target = {
            "school_id": school_id, "kind": kind, "object_id": object_id,
        }
        if target not in targets:
            targets.append(target)
    return targets


def active_focus_binding(character, school_id):
    """Return the actual active binding for one school, with explicit type."""
    if character is None or school_id is None:
        return None
    school = School.objects.select_related("type").filter(pk=school_id).first()
    if school is None or character.get_engine().effective_school_level(
        school.pk,
    ) <= 0:
        return None
    kind = focus_target_kind(school)
    if kind == "divine_entity":
        binding = CharacterDivineEntity.objects.filter(
            character=character,
        ).select_related("entity").first()
        if binding is None or binding.school_id != school.pk:
            return None
        source = binding.entity
    elif kind == "druid_cult":
        binding = CharacterDruidCult.objects.filter(
            character=character, cult__school=school,
        ).select_related("cult").first()
        source = binding.cult if binding else None
    elif kind == "shaman_patron":
        binding = CharacterShamanPatron.objects.filter(
            character=character, patron__school=school,
        ).select_related("patron").first()
        source = binding.patron if binding else None
    else:
        return None
    if source is None:
        return None
    return {
        "school_id": school.pk, "kind": kind, "object_id": source.pk,
        "binding": binding, "source": source,
    }


def focus_binding_key(binding):
    return {
        key: binding[key] for key in ("school_id", "kind", "object_id")
    }


def aspect_focus_binding(character, aspect_id, aspect_entry=None):
    """Resolve legacy core aspects with one unambiguous active source."""
    matches = []
    for school_id in character.get_engine().effective_school_entries():
        active = active_focus_binding(character, school_id)
        if active is None:
            continue
        source = active["source"]
        source_entity_id = (
            source.pk
            if active["kind"] == "divine_entity" else source.entity_id
        )
        if aspect_entry and aspect_entry.source_entity_id:
            if aspect_entry.source_entity_id != source_entity_id:
                continue
        if aspect_entry and aspect_entry.source_binding_id:
            if (active["kind"] != "divine_entity"
                    or aspect_entry.source_binding_id != active["binding"].pk):
                continue
        aspects = core_aspects_for_source(source, active["binding"])
        if any(aspect.pk == aspect_id for aspect in aspects):
            matches.append(active)
    return matches[0] if len(matches) == 1 else None


def focus_target_labels(targets, character=None, aspect_label=None):
    """Describe targets using current core aspects or an explicit fallback."""
    labels = []
    for target in targets:
        model, kind_label = TARGET_TYPES.get(target["kind"], (None, ""))
        if model is None:
            continue
        source = model.objects.filter(pk=target["object_id"]).first()
        school = School.objects.filter(pk=target["school_id"]).first()
        if source is None or school is None:
            continue
        active = active_focus_binding(character, school.pk)
        binding = None
        if active and focus_binding_key(active) == target:
            binding = active["binding"]
        aspects = core_aspects_for_source(source, binding)
        names = [
            aspect_label(aspect.name) if aspect_label else aspect.name
            for aspect in aspects
        ]
        scope = f"{school.name} ({kind_label}: {source.name})"
        labels.append((names or [scope], scope))
    # Preserve distinct scopes when their readable aspect names coincide.
    occurrences = {}
    for names, scope in labels:
        for name in names:
            occurrences.setdefault(name, set()).add(scope)
    return [
        f"{name} ({scope})" if len(occurrences[name]) > 1 else name
        for names, scope in labels for name in names
    ]
