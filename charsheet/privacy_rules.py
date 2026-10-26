"""Versioned disclosure rules; classification never removes personal data."""

import math
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from uuid import UUID

from .privacy_content import PROTECTED

RULESET = "privacy-standard-v1"
RULES = {
    "owned.empty.v1": (True, "Leerer Wert im eigenen Datenbestand"),
    "owned.scalar.v1": (True, "Typgeprüfter eigener Standardwert"),
    "owned.choice.v1": (True, "Eigener Wert aus festgelegter Auswahlliste"),
    "owned.reference.v1": (True, "Geprüfter eigener oder öffentlicher Bezug"),
    "owned.identity.v1": (True, "Identitätsangabe des ausgewählten Kontos"),
    "review.protected.v1": (False, "Geschützter Inhalt oder Sicherheitsfeld"),
    "review.candidate.v1": (False, "Vorhandener Einzelfall-Prüfkandidat"),
    "review.shared.v1": (False, "Gemeinsamer oder nicht sicher eigener Inhalt"),
    "review.file.v1": (False, "Dateiinhalt und Rechte Dritter prüfen"),
    "review.structure.v1": (False, "Strukturierte persönliche Inhalte prüfen"),
    "review.text.v1": (False, "Freitext auf Drittinformationen prüfen"),
    "review.unknown.v1": (False, "Keine passende sichere Standardregel"),
}
AUTOMATIC_RULES = {key for key, (safe, _) in RULES.items() if safe}
INTEGER_TYPES = {
    "AutoField", "BigAutoField", "SmallAutoField", "IntegerField",
    "BigIntegerField", "SmallIntegerField", "PositiveIntegerField",
    "PositiveSmallIntegerField", "PositiveBigIntegerField",
}


def field_label(name, metadata):
    from .privacy_labels import PHRASES, german_label

    return PHRASES.get(name, german_label(metadata.get("label", name)))


def category_label(name, metadata):
    from .privacy_labels import PHRASES, german_label

    return PHRASES.get(name, PHRASES.get(
        name.rsplit(".", 1)[-1], german_label(metadata.get("label") or name),
    ))


class Classifier:
    def __init__(self, source):
        from .privacy_export import REDACTED, SECRET

        self.secret = SECRET
        self.protected = {PROTECTED, REDACTED}
        self.subject = str(source["subject"]["id"])
        self.owned = {item["model"] for item in source["category_mapping"]
                      if item["scope"] == "account_owned"}
        self.owned.add("auth.User")
        self.references = {
            label: {str(record["id"]) for record in content["records"]
                    if "id" in record}
            for label, content in source["categories"].items()
            if label in self.owned
        }
        self.references["auth.User"] = {self.subject}
        blocked = {item["id"] for item in source["review_candidates"]}
        for label, records in source.get("references", {}).items():
            self.references[label] = {
                str(record["id"]) for record in records if "id" in record
                and f"{label}:{record['id']}:catalog_reference" not in blocked
                and not self.has_protected(record)
            }

    def has_protected(self, value):
        if isinstance(value, str):
            return value in self.protected
        if isinstance(value, dict):
            return any(self.secret.search(str(key))
                       or self.has_protected(item)
                       for key, item in value.items())
        if isinstance(value, list):
            return any(self.has_protected(item) for item in value)
        return False

    def classify(self, category, pk, name, metadata, value, candidate):
        if self.secret.search(name) or self.has_protected(value):
            return "review.protected.v1"
        if candidate:
            return "review.candidate.v1"
        if category not in self.owned or (
            category == "auth.User" and str(pk) != self.subject
        ):
            return "review.shared.v1"
        if value is None or value == "" or value == [] or value == {}:
            return "owned.empty.v1"
        kind = metadata.get("type")
        if kind in {"FileField", "ImageField"}:
            return "review.file.v1"
        target = metadata.get("relation")
        if target:
            values = value if isinstance(value, list) else [value]
            if all(str(item) in self.references.get(target, set())
                   for item in values):
                return "owned.reference.v1"
            return "review.shared.v1"
        if isinstance(value, (dict, list)):
            return "review.structure.v1"
        choices = metadata.get("choices", {})
        if choices and str(value) in choices:
            return "owned.choice.v1"
        if category == "auth.User" and name in {
            "username", "email", "first_name", "last_name",
        } and isinstance(value, str) and len(value) <= 254 and not any(
            character in value for character in ("\n", "\r", "<", ">")
        ):
            return "owned.identity.v1"
        if self.scalar(kind, value):
            return "owned.scalar.v1"
        if kind in {"CharField", "TextField", "EmailField", "SlugField"}:
            return "review.text.v1"
        return "review.unknown.v1"

    @staticmethod
    def scalar(kind, value):
        if kind == "BooleanField":
            return isinstance(value, bool)
        if kind in INTEGER_TYPES:
            return isinstance(value, int) and not isinstance(value, bool)
        if kind == "FloatField":
            return (isinstance(value, (float, int))
                    and not isinstance(value, bool) and math.isfinite(value))
        if not isinstance(value, str):
            return False
        try:
            if kind == "DecimalField":
                return Decimal(value).is_finite()
            parser = {"DateField": date.fromisoformat,
                      "DateTimeField": datetime.fromisoformat,
                      "TimeField": time.fromisoformat, "UUIDField": UUID}
            if kind in parser:
                parser[kind](value)
                return True
        except (ValueError, InvalidOperation):
            pass
        return False


def validate_automatic_review(review):
    if not review:
        return
    if not isinstance(review, dict) or set(review) != {
        "ruleset", "source_fingerprint", "subject_id", "categories",
        "counts", "overrides",
    }:
        raise ValueError("Ungültiger Nachweis der Standardprüfung.")
    if (review["ruleset"] != RULESET
            or not isinstance(review["subject_id"], int)
            or not isinstance(review["source_fingerprint"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", review["source_fingerprint"])):
        raise ValueError("Veraltete oder ungültige Standardprüfung.")
    categories = review["categories"]
    if not isinstance(categories, dict) or any(
        not isinstance(name, str) or not isinstance(rules, list)
        or any(rule not in AUTOMATIC_RULES for rule in rules)
        for name, rules in categories.items()
    ):
        raise ValueError("Unzulässige automatische Prüfregel.")
    counts = review["counts"]
    if not isinstance(counts, dict) or any(
        key not in AUTOMATIC_RULES or type(value) is not int or value < 0
        for key, value in counts.items()
    ):
        raise ValueError("Ungültige Anzahl automatischer Entscheidungen.")
    overrides = review["overrides"]
    if not isinstance(overrides, dict) or any(
        not isinstance(key, str) or value not in {
            "include", "redact", "partial", "withhold", "not_personal",
            "pending",
        } for key, value in overrides.items()
    ):
        raise ValueError("Ungültige manuelle Prüfentscheidung.")
