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
from .privacy_rules import (
    AUTOMATIC_ACTIONS,
    Classifier,
    RULES,
    RULESET,
    category_label,
    field_label,
)

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
    rule: str = "review.unknown.v1"
    fingerprint: str = ""

    @property
    def automatic(self):
        return RULES[self.rule][0]

    @property
    def rule_label(self):
        return RULES[self.rule][1]


def fields(source, rule_cache=None):
    candidates = {item["id"]: item for item in source["review_candidates"]}
    cache = rule_cache or {}
    cached = (
        cache.get("fields", {})
        if cache.get("ruleset") == RULESET
        and cache.get("source_fingerprint") == source["source_fingerprint"]
        else {}
    )
    classifier = None
    seen = set()
    for category, content in source["categories"].items():
        title = category_label(category, content)
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
                value = sanitize(value)
                rule = cached.get(key)
                if rule not in RULES:
                    if classifier is None:
                        classifier = Classifier(source)
                    rule = classifier.classify(
                        category,
                        pk,
                        original_name,
                        meta,
                        value,
                        bool(item),
                    )
                yield ReviewField(
                    key,
                    category,
                    title,
                    caption,
                    original_name,
                    field_label(name, meta),
                    value,
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
                    rule,
                    source["source_fingerprint"],
                )
    for item in source["review_candidates"]:
        if item["id"] in seen:
            continue
        value = sanitize(item["candidate"])
        rule = cached.get(item["id"])
        if rule not in RULES:
            if classifier is None:
                classifier = Classifier(source)
            rule = classifier.classify(
                item["model"], item["record"], item["field"], {}, value, True,
            )
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
            rule=rule,
            fingerprint=source["source_fingerprint"],
        )


def field_token(token, source, field):
    return signing.dumps(
        [token, source.get("source_fingerprint"), field.key],
        salt=SALT,
        compress=True,
    )


def find_field(token, source, signed, catalog=None):
    try:
        owner, fingerprint, key = signing.loads(
            signed, salt=SALT, max_age=3600
        )
    except (signing.BadSignature, ValueError, TypeError):
        raise ValueError("Das Feld ist nicht mehr verfügbar.") from None
    if owner != token or fingerprint != source.get("source_fingerprint"):
        raise ValueError("Das Feld gehört nicht zu diesem Prüfstand.")
    for field in catalog if catalog is not None else fields(source):
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


def decision_for(field, state):
    manual = state["decisions"].get(field.key)
    if manual is not None:
        return None if manual["action"] == "pending" else manual
    accepted = state.get("standard_acceptance", {})
    if (
        field.automatic
        and accepted.get("ruleset") == RULESET
        and accepted.get("source_fingerprint") == field.fingerprint
        and field.rule
        in accepted.get("categories", {}).get(field.category, [])
    ):
        return {
            "action": AUTOMATIC_ACTIONS.get(field.rule, "include"),
            "reason": field.rule_label,
            "automatic": True,
            "rule": field.rule,
        }
    return None


def accept_standards(source, state, catalog=None, category=None):
    """Store accepted rules once per category, never one entry per record."""
    accepted = state.get("standard_acceptance", {})
    if (
        accepted.get("ruleset") != RULESET
        or accepted.get("source_fingerprint") != source["source_fingerprint"]
    ):
        accepted = {
            "ruleset": RULESET,
            "source_fingerprint": source["source_fingerprint"],
            "categories": {},
        }
    grouped = {
        key: set(value) for key, value in accepted["categories"].items()
    }
    image_fields = set()
    for field in catalog if catalog is not None else fields(source):
        if field.rule == "owned.image.v1":
            image_fields.add(field.key)
        if field.automatic and (
            category is None or field.category == category
        ):
            grouped.setdefault(field.category, set()).add(field.rule)
    accepted["categories"] = {
        key: sorted(value) for key, value in grouped.items()
    }
    state["standard_acceptance"] = accepted
    choices = state.setdefault("file_choices", {})
    for item in source["files"]:
        if (item["field"] in image_fields
                and item["member"] not in state["file_decisions"]):
            choices.setdefault(item["member"], "include")
    if state["output"]["format"] == "zip" and "include" in choices.values():
        state["output"]["include_files"] = True


def ensure_precheck(source, state, catalog=None):
    accepted = state.get("standard_acceptance", {})
    if (
        accepted.get("ruleset") == RULESET
        and accepted.get("source_fingerprint") == source["source_fingerprint"]
    ):
        return False
    accept_standards(source, state, catalog)
    invalidate(state)
    return True


def compile_review(source, state, catalog=None):
    review = copy.deepcopy(state["information"])
    review.update(
        redactions={},
        resolutions={},
        supplements=copy.deepcopy(state["supplements"]),
        file_decisions=copy.deepcopy(state["file_decisions"]),
    )
    if state["mode"] == "portability":
        review["portability"] = copy.deepcopy(state["portability"])
    automatic_categories, automatic_counts, overrides = {}, {}, {}
    for field in catalog if catalog is not None else fields(source):
        if not included(field, state):
            continue
        if field.key in state["decisions"]:
            overrides[field.key] = state["decisions"][field.key]["action"]
        decision = decision_for(field, state)
        if not decision:
            continue
        action = decision["action"]
        if decision.get("automatic"):
            category = (field.key.split(":", 1)[0]
                        if field.category == "additional" else field.category)
            automatic_categories.setdefault(category, set()).add(
                field.rule
            )
            automatic_counts[field.rule] = (
                automatic_counts.get(field.rule, 0) + 1
            )
        if action == "include" and not field.candidate:
            continue
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
    if automatic_counts:
        review["automatic_review"] = {
            "ruleset": RULESET,
            "source_fingerprint": source["source_fingerprint"],
            "subject_id": source["subject"]["id"],
            "categories": {
                key: sorted(value)
                for key, value in automatic_categories.items()
            },
            "counts": automatic_counts,
            "overrides": overrides,
        }
    validate_review(review, state["mode"])
    return review


def progress(source, state, catalog=None):
    result = {
        key: 0
        for key in (
            "total",
            "checked",
            "open",
            "automatic",
            "standard_open",
            "exceptions",
            "exceptions_open",
            "redacted",
        )
    }
    rules = {}
    for field in catalog if catalog is not None else fields(source):
        if not included(field, state):
            continue
        result["total"] += 1
        decision = decision_for(field, state)
        result["checked"] += bool(decision)
        result["open"] += not decision
        result["automatic"] += bool(decision and decision.get("automatic"))
        standard_open = (
            not decision
            and field.automatic
            and field.key not in state["decisions"]
        )
        result["standard_open"] += standard_open
        result["exceptions"] += (
            not field.automatic
            or state["decisions"].get(field.key, {}).get("action") == "pending"
        )
        result["exceptions_open"] += not decision and not standard_open
        result["redacted"] += field.rule == "review.protected.v1" or bool(
            decision
            and decision["action"]
            in {
                "redact",
                "partial",
                "withhold",
                "not_personal",
            }
        )
        entry = rules.setdefault(
            field.rule,
            {
                "id": field.rule,
                "label": field.rule_label,
                "automatic": field.automatic,
                "total": 0,
                "open": 0,
                "accepted": 0,
            },
        )
        entry["total"] += 1
        entry["open"] += not decision
        entry["accepted"] += bool(decision)
    result["percent"] = (
        round(100 * result["checked"] / result["total"])
        if result["total"]
        else 0
    )
    result["rules"] = list(rules.values())
    return result


def initial_state(source, mode, catalog=None):
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
    state = {
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
    accept_standards(source, state, catalog)
    return state


def invalidate(state):
    state["version"] += 1
    state.update(
        preview_version=None,
        preview_digest=None,
        approval=None,
        missing=[],
        error="",
    )


def friendly_missing(source, missing, catalog=None):
    labels = {
        field.key: f"{field.category_label} · {field.record} · {field.label}"
        for field in (catalog if catalog is not None else fields(source))
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
