"""Graphical review state and translation into the existing review contract."""

import copy
from dataclasses import dataclass

from django.core import signing

from .privacy_content import (
    PROTECTED,
    controller_information,
    meaningful,
    recipient_payload,
    sanitize,
)
from .privacy_export import ownership_paths, validate_review, SHARED
from .privacy_labels import PHRASES, german_label

SALT = "charsheet.privacy-review.field.v1"
REDACTION = "[Geschwärzt]"


@dataclass
class ReviewField:
    key: str
    category: str
    category_label: str
    record: str
    name: str
    label: str
    value: object
    candidate: bool = False
    can_take: bool = True
    explanation: str = ""


def fields(source):
    candidates = {item["id"]: item for item in source["review_candidates"]}
    public = recipient_payload(source)
    seen = set()
    for category, content in source["categories"].items():
        title = public["categories"][category]["label"]
        for number, record in enumerate(content["records"], 1):
            pk = record.get("id", number)
            caption = next(
                (
                    str(record[key])
                    for key in (
                        "name_override",
                        "name",
                        "username",
                        "title",
                    )
                    if record.get(key)
                    and isinstance(record[key], str)
                    and sanitize(record[key]) != PROTECTED
                ),
                f"Eintrag {number}",
            )
            for name, value in record.items():
                if name == "selected_content_type":
                    continue
                meta = content["fields"].get(name, {})
                original_name = meta.get("source_field", name)
                key = f"{category}:{pk}:{original_name}"
                item = candidates.get(key)
                available = not (
                    item
                    and isinstance(item["candidate"], dict)
                    and set(item["candidate"]) == {"keys"}
                )
                if item and available:
                    value = item["candidate"]
                    if isinstance(value, dict) and set(value) == {
                        "encoding",
                        "value",
                    }:
                        value = value["value"]
                seen.add(key)
                yield ReviewField(
                    key,
                    category,
                    title,
                    caption,
                    original_name,
                    public["categories"][category]["fields"]
                    .get(name, {})
                    .get("label", PHRASES.get(name, german_label(name))),
                    sanitize(value),
                    bool(item),
                    available,
                    (
                        "Zusatzwerte sind nicht automatisch verfügbar. "
                        "Geprüften Auszug ergänzen oder Ausnahme begründen."
                        if not available
                        else (
                            "Persönlichen Anteil und Rechte Dritter prüfen."
                            if item
                            else ""
                        )
                    ),
                )
    for item in source["review_candidates"]:
        if item["id"] in seen:
            continue
        value = sanitize(item["candidate"])
        yield ReviewField(
            item["id"],
            "additional",
            "Weitere zu prüfende Inhalte",
            (
                str(value.get("title", "Gemeinsamer Inhalt"))
                if isinstance(value, dict)
                else "Weiterer Inhalt"
            ),
            item["field"],
            PHRASES.get(item["field"], german_label(item["field"])),
            value,
            True,
        )


def field_token(token, source, field):
    return signing.dumps(
        [token, source.get("source_fingerprint"), field.key],
        salt=SALT,
        compress=True,
    )


def find_field(token, source, signed):
    try:
        owner, fingerprint, key = signing.loads(
            signed, salt=SALT, max_age=3600
        )
    except (signing.BadSignature, ValueError, TypeError):
        raise ValueError("Das Feld ist nicht mehr verfügbar.") from None
    if owner != token or fingerprint != source.get("source_fingerprint"):
        raise ValueError("Das Feld gehört nicht zu diesem Prüfstand.")
    for field in fields(source):
        if field.key == key:
            return field
    raise ValueError("Das Feld ist nicht mehr vorhanden.")


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, path + (index,))
    else:
        yield path, value


def replace_leaf(value, path, replacement):
    if not path:
        return replacement
    parent = value
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = replacement
    return value


def decision_value(field, decision):
    action = decision["action"]
    if action in {"withhold", "not_personal", "redact"}:
        return REDACTION
    if action == "include":
        return copy.deepcopy(field.value)
    if decision.get("as_text"):
        return decision["text"]
    if not isinstance(field.value, (dict, list)):
        return decision["text"]
    value = copy.deepcopy(field.value)
    for edit in decision.get("edits", []):
        value = replace_leaf(value, tuple(edit["path"]), edit["text"])
    return value


def portable_categories(source):
    allowed = {model._meta.label for model in ownership_paths()}
    allowed |= {"charsheet." + name for name in SHARED}
    allowed.add("auth.User")
    return {
        key: value
        for key, value in source["categories"].items()
        if key in allowed and value["records"]
    }


def included(field, state):
    if state["mode"] == "access":
        return True
    rule = state.get("portability", {}).get(field.category, {})
    return (
        field.name == "id"
        and bool(rule)
        or field.name in rule.get("fields", [])
    )


def compile_review(source, state):
    review = copy.deepcopy(state["information"])
    review.update(
        redactions={},
        resolutions={},
        supplements=copy.deepcopy(state["supplements"]),
        file_decisions=copy.deepcopy(state["file_decisions"]),
    )
    if state["mode"] == "portability":
        review["portability"] = copy.deepcopy(state["portability"])
    for field in fields(source):
        if not included(field, state):
            continue
        decision = state["decisions"].get(field.key)
        if not decision:
            continue
        action = decision["action"]
        value = decision_value(field, decision)
        reason = decision.get("reason", "")
        if field.candidate or action != "include":
            if not meaningful(reason):
                raise ValueError(
                    "Für diese Entscheidung fehlt eine Begründung."
                )
            resolution = {
                "action": "include",
                "reason": reason,
                "value": value,
            }
            if action in {"withhold", "not_personal"} and field.candidate:
                resolution = {"action": action, "reason": reason}
            review["resolutions"][field.key] = resolution
        if action != "include" and field.category != "additional":
            # Exceptions to mixed-source extras are handled by the existing
            # collector; all ordinary field edits preserve the containing row.
            if not (
                field.candidate and action in {"withhold", "not_personal"}
            ):
                review["redactions"][field.key] = value
    removed_files = {
        item["member"]
        for item in source["files"]
        if item["field"] in review["redactions"]
    }
    review["file_decisions"] = {
        key: value
        for key, value in review["file_decisions"].items()
        if key not in removed_files
    }
    if state.get("approval"):
        review["approval"] = copy.deepcopy(state["approval"])
    validate_review(review, state["mode"])
    return review


def progress(source, state):
    relevant = [field for field in fields(source) if included(field, state)]
    checked = sum(field.key in state["decisions"] for field in relevant)
    return {
        "total": len(relevant),
        "checked": checked,
        "open": len(relevant) - checked,
        "percent": round(100 * checked / len(relevant)) if relevant else 0,
    }


def initial_state(source, mode):
    categories = recipient_payload(source)["data_categories"]
    processing = {
        "purposes": "; ".join(dict.fromkeys(c["purpose"] for c in categories)),
        "sources": "; ".join(dict.fromkeys(c["source"] for c in categories)),
    }
    legal = source["legal_configuration"]
    retention = [
        ("Sicherheitsereignisse", "security_cleanup"),
        ("Serverprotokolle", "server_log_retention"),
        ("Sicherungen", "backup_policy"),
        ("E-Mail", "email_retention"),
    ]
    processing["retention"] = "\n\n".join(
        label + ": " + legal[key]
        for label, key in retention
        if meaningful(legal.get(key))
    )
    return {
        "version": 0,
        "mode": mode,
        "decisions": {},
        "portability": {},
        "information": {
            "controller": controller_information(source),
            "processing": processing,
            "coverage": {},
            "services": {},
        },
        "supplements": [],
        "file_decisions": {},
        "output": {
            "format": "zip",
            "audience": "recipient",
            "include_files": False,
            "files_reviewed": False,
        },
        "preview_version": None,
        "preview_digest": None,
        "approval": None,
        "missing": [],
        "error": "",
        "busy": False,
        "step": 3,
    }


def invalidate(state):
    state["version"] += 1
    state.update(
        preview_version=None,
        preview_digest=None,
        approval=None,
        missing=[],
        error="",
    )


def friendly_missing(source, missing):
    labels = {
        field.key: f"{field.category_label} · {field.record} · {field.label}"
        for field in fields(source)
    }
    result = []
    for text in missing:
        if text.startswith("Einzelfallprüfung: "):
            key = text.split(": ", 1)[1]
            result.append(
                "Noch prüfen: " + labels.get(key, "Weitere Zuordnung")
            )
        elif text.startswith("Dateikopie / Zustellung: "):
            result.append(
                "Für einen Dateianhang fehlt die Zustellungsentscheidung."
            )
        else:
            result.append(text)
    return result
