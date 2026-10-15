"""Read-only portraits using existing attribute values and race limits."""

from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import (
    Attribute,
    AttributeRating,
    Character,
    GameGroup,
    GeneralAttributeMeaning,
    RaceAttributeFlavor,
    RaceAttributeLimit,
)
from .narrative_templates import render_narrative
from .templatetags.card_markdown import standard_markdown


def active_rules(model):
    rules = model.objects.filter(active=True)
    if model is not RaceAttributeFlavor:
        rules = rules.order_by(
            F("min_value").desc(nulls_last=True),
            "-priority",
            "pk",
        )
    return rules


def build_flavor_catalog(character):
    """Load shared definitions once for all seven rendered sheet values."""
    return {
        "attributes": {
            entry.short_name: entry for entry in Attribute.objects.all()
        },
        "limits": {
            entry.attribute_id: entry
            for entry in RaceAttributeLimit.objects.filter(
                race_id=character.race_id
            )
        },
        **{
            model: list(active_rules(model))
            for model in (
                AttributeRating,
                GeneralAttributeMeaning,
                RaceAttributeFlavor,
            )
        },
    }


def matching_rules(model, value, catalog=None, **scope):
    if catalog is not None:
        attribute = scope.get("attribute")
        return [
            entry
            for entry in catalog[model]
            if entry.matches(value)
            and (attribute is None or entry.attribute_id == attribute.pk)
        ]
    return (
        active_rules(model)
        .filter(**scope)
        .filter(
            Q(min_value__isnull=True) | Q(min_value__lte=value),
        )
        .filter(Q(max_value__isnull=True) | Q(max_value__gte=value))
    )


def description_template(rule, *, neutral=False):
    """Present legacy reference prose and templates as one description."""
    legacy = getattr(rule, "official_description", "")
    for original, replacement in (
        ("\\", "\\\\"), ("^", "\\^"), ("~", "\\~"),
        ("{", "{{"), ("}", "}}"),
    ):
        legacy = legacy.replace(original, replacement)
    template = rule.neutral_template if neutral else rule.narrative_template
    return "\n\n".join(text for text in (legacy, template) if text)


def race_narrative_values(race):
    if race is None:
        return {"race": "", "race_accusative": "", "race_plural": ""}
    return {
        "race": race.name,
        "race_accusative": race.name_accusative or race.name,
        "race_plural": race.name_plural or race.name,
    }


def narrative_html(rule, values, gender):
    text = render_narrative(
        description_template(rule),
        values,
        gender,
        description_template(rule, neutral=True),
        markdown=True,
    )
    return str(standard_markdown(text))


def resolve_attribute_flavor(character, attribute, value, catalog=None):
    """Compose absolute and relative parts without persisting prose."""
    ratings = list(
        matching_rules(
            AttributeRating,
            value,
            catalog,
            attribute=attribute,
        )
    )
    meanings = list(matching_rules(GeneralAttributeMeaning, value, catalog))
    rating = ratings[0] if ratings else None
    reference = next(
        (
            entry
            for entry in ratings
            if entry.official_designation or entry.official_description
        ),
        None,
    )
    meaning = meanings[0] if meanings else None
    values = {
        "character_name": character.name,
        **race_narrative_values(character.race),
        "attribute": attribute.name,
        "value": value,
        "rating": reference.official_designation if reference else "",
        "meaning": (
            reference.official_designation
            if reference and reference.official_designation
            else meaning.official_meaning if meaning else ""
        ),
    }
    absolute = ""
    for rule in [entry for entry in (rating, meaning) if entry is not None]:
        absolute = narrative_html(rule, values, character.gender)
        if absolute:
            break
    relative = ""
    limit = (
        catalog["limits"].get(attribute.pk)
        if catalog is not None
        else RaceAttributeLimit.objects.filter(
            race_id=character.race_id,
            attribute=attribute,
        ).first()
    )
    if limit is not None:
        rules = list(
            matching_rules(
                RaceAttributeFlavor,
                value - limit.max_value,
                catalog,
            )
        )
        for rule in [
            *[entry for entry in rules if entry.attribute_id == attribute.pk],
            *[entry for entry in rules if entry.attribute_id is None],
        ]:
            relative = narrative_html(rule, values, character.gender)
            if relative:
                break
    return {
        "attribute": attribute.name,
        "value": value,
        "absolute_html": absolute,
        "relative_html": relative,
        "designation_html": str(standard_markdown(
            reference.official_designation if reference else ""
        )),
        "meaning_html": str(standard_markdown(
            meaning.official_meaning if meaning else ""
        )),
        "official_designation": (
            reference.official_designation if reference else ""
        ),
        "official_description": (
            reference.official_description if reference else ""
        ),
        "rating_source": reference.source_reference if reference else "",
        "general_meaning": meaning.official_meaning if meaning else "",
        "meaning_source": meaning.source_reference if meaning else "",
    }


@login_required
@require_GET
@never_cache
def attribute_flavor_card(request, character_id):
    from .game_groups import require_sl_character_access
    from .views import _temporary_attribute_adjustments

    character = get_object_or_404(
        Character.objects.select_related("race"),
        pk=character_id,
    )
    group_id = request.GET.get("group")
    if group_id:
        try:
            group_id = int(group_id)
        except ValueError:
            return JsonResponse({"error": "Ungültige Gruppe."}, status=400)
        group = get_object_or_404(GameGroup, pk=group_id)
        require_sl_character_access(request.user, group, character)
    elif character.owner_id != request.user.pk:
        # Match the ownership contract of the ordinary character sheet.
        get_object_or_404(Character, pk=character_id, owner=request.user)
    attribute = get_object_or_404(
        Attribute,
        short_name=request.GET.get("attribute", ""),
    )
    engine = character.get_engine(
        refresh=True,
        runtime_attribute_adjustments=_temporary_attribute_adjustments(
            request,
            character.pk,
        ),
    )
    value = engine.attributes().get(attribute.short_name, 0)
    # The UI value is used only for this read-only portrait. This also
    # covers an optimistic temporary adjustment before its POST has finished.
    if "value" in request.GET:
        try:
            value = int(request.GET["value"])
        except (TypeError, ValueError):
            return JsonResponse(
                {"error": "Ungültiger Eigenschaftswert."}, status=400
            )
    return JsonResponse(resolve_attribute_flavor(character, attribute, value))
