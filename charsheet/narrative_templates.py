"""Small, validated narrative language; no executable template expressions."""

import re
from string import Formatter

from django.core.exceptions import ValidationError

PLACEHOLDERS = frozenset(
    {
        "character_name",
        "race",
        "race_accusative",
        "race_plural",
        "attribute",
        "value",
        "meaning",
        "rating",
    }
)


def _segments(text):
    parts = []
    literal = []
    marker = None
    index = 0
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            following = text[index + 1]
            if following in "^~\\":
                literal.append(following)
                index += 2
                continue
        delimiter = (
            "~~"
            if text.startswith("~~", index)
            else "^" if text[index] == "^" else None
        )
        if delimiter:
            if marker is not None and marker != delimiter:
                raise ValidationError(
                    "Geschlechtsmarker dürfen nicht verschachtelt werden."
                )
            parts.append((marker, "".join(literal)))
            literal = []
            marker = None if marker else delimiter
            index += len(delimiter)
        else:
            literal.append(text[index])
            index += 1
    if marker:
        raise ValidationError("Nicht geschlossener Geschlechtsmarker.")
    parts.append((None, "".join(literal)))
    return parts


def _scale_parameters(spec):
    match = re.fullmatch(
        r"\s*([+-]?[0-9]+)\s*,\s*([+-]?[0-9]+)"
        r"\s*(?:,\s*([+-]?[0-9]+)\s*)?",
        spec,
    )
    if match is None:
        raise ValidationError(
            "Berechnete Zahl: {scale:Startwert,Zuschlag,Grundmenge}. "
            "Nur ganze Zahlen; die Grundmenge ist optional."
        )
    start, step, base = match.groups()
    return int(start), int(step), int(base or 0)


def validate_narrative(text, *, neutral=False):
    parts = _segments(str(text or ""))
    if neutral and any(marker for marker, _ in parts):
        raise ValidationError(
            "Die neutrale Vorlage darf keine Geschlechtsmarker enthalten."
        )
    try:
        for _, field, spec, conversion in Formatter().parse(str(text or "")):
            if field == "scale" and conversion is None:
                _scale_parameters(spec)
                continue
            if field is not None and (
                field not in PLACEHOLDERS or spec or conversion
            ):
                raise ValidationError(
                    "Unbekannter oder ungültiger Platzhalter: {%s}" % field
                )
    except ValueError as exc:
        raise ValidationError("Ungültige Platzhalterklammern.") from exc


def render_narrative(
    text, values, gender=None, neutral_template="", *, markdown=False
):
    """Resolve markers before substitution, so values cannot inject syntax."""
    from .models.character import Character

    try:
        validate_narrative(text)
        validate_narrative(neutral_template, neutral=True)
        marker = {
            Character.Gender.M: "^",
            Character.Gender.W: "~~",
        }.get(gender)
        parts = _segments(str(text or ""))
        if marker is None and any(kind for kind, _ in parts):
            parts = _segments(neutral_template)
        resolved = "".join(
            part for kind, part in parts if kind is None or kind == marker
        )
        replacements = {
            key: "" if values.get(key) is None else str(values[key])
            for key in PLACEHOLDERS
        }
        if markdown:
            replacements = {
                key: value if key in {"rating", "meaning"} else re.sub(
                    r"([\\`*_{}\[\]()#+.!<>~^|\-])", r"\\\1", value
                )
                for key, value in replacements.items()
            }
        rendered = []
        for literal, field, spec, _ in Formatter().parse(resolved):
            rendered.append(literal)
            if field == "scale":
                start, step, base = _scale_parameters(spec)
                value = values.get("value")
                rendered.append(
                    "" if value in (None, "") else str(
                        base + max(0, int(value) - start + 1) * step
                    )
                )
            elif field is not None:
                rendered.append(replacements[field])
        resolved = "".join(rendered)
        resolved = re.sub(r"\s+", " ", resolved).strip()
        return re.sub(r"\s+([,.;:!?])", r"\1", resolved)
    except (ValidationError, ValueError, KeyError):
        return ""
