"""Versioned disclosure rules; classification never removes personal data."""

import math
import json
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError

from .calendar_layout import validate_layout
from .privacy_content import PROTECTED

RULESET = "privacy-standard-v3"
RULES = {
    "owned.empty.v1": (True, "Leerer Wert ohne Inhaltsangaben"),
    "owned.scalar.v1": (True, "Typgeprüfter eigener Standardwert"),
    "owned.choice.v1": (True, "Eigener Wert aus festgelegter Auswahlliste"),
    "owned.reference.v1": (True, "Geprüfter eigener oder öffentlicher Bezug"),
    "owned.identity.v1": (True, "Identitätsangabe des ausgewählten Kontos"),
    "owned.layout.v1": (True, "Validierte Kalenderanordnung ohne Freitext"),
    "owned.technical.v1": (True, "Geschlossene technische Angabe"),
    "owned.default.v1": (True, "Unveränderter Standardtext der Anwendung"),
    "related.scalar.v1": (True, "Typgeprüfte Metadaten eines Kontobezugs"),
    "related.reference.v1": (
        True,
        "Geprüfter Bezug zu zugeordneten Daten",
    ),
    "related.schema_message.v1": (
        True,
        "Änderungsprotokoll mit reinen Schemaangaben",
    ),
    "review.calendar_text.v1": (False, "Freier Zusatztext im Kalender"),
    "review.protected.v1": (False, "Geschützter Inhalt oder Sicherheitsfeld"),
    "review.candidate.v1": (False, "Vorhandener Einzelfall-Prüfkandidat"),
    "review.shared.v1": (
        False,
        "Gemeinsamer oder nicht sicher eigener Inhalt",
    ),
    "review.file.v1": (False, "Dateiinhalt und Rechte Dritter prüfen"),
    "review.structure.v1": (False, "Strukturierte persönliche Inhalte prüfen"),
    "review.text.v1": (False, "Freitext auf Drittinformationen prüfen"),
    "review.unknown.v1": (False, "Keine passende sichere Standardregel"),
}
AUTOMATIC_RULES = {key for key, (safe, _) in RULES.items() if safe}
INTEGER_TYPES = {
    "AutoField",
    "BigAutoField",
    "SmallAutoField",
    "IntegerField",
    "BigIntegerField",
    "SmallIntegerField",
    "PositiveIntegerField",
    "PositiveSmallIntegerField",
    "PositiveBigIntegerField",
}


def field_label(name, metadata):
    from .privacy_labels import PHRASES, german_label

    return PHRASES.get(name, german_label(metadata.get("label", name)))


def category_label(name, metadata):
    from .privacy_labels import PHRASES, german_label

    return PHRASES.get(
        name,
        PHRASES.get(
            name.rsplit(".", 1)[-1],
            german_label(metadata.get("label") or name),
        ),
    )


class Classifier:
    def __init__(self, source):
        from .privacy_export import REDACTED, SECRET

        self.secret = SECRET
        self.protected = {PROTECTED, REDACTED}
        self.subject = str(source["subject"]["id"])
        self.owned = {
            item["model"]
            for item in source["category_mapping"]
            if item["scope"] == "account_owned"
        }
        self.owned.add("auth.User")
        self.related = (
            self.owned
            | {
                item["model"]
                for item in source["category_mapping"]
                if item["scope"]
                in {"shared", "reconstructable_account_bucket"}
            }
            | {
                "admin.LogEntry",
                "sessions.Session",
                "auth.EffectivePermission",
            }
        )
        self.audit = source.get("review_context", {}).get("admin.LogEntry", {})
        self.log_rows = {
            str(row["id"]): row
            for row in source["categories"]
            .get("admin.LogEntry", {})
            .get("records", [])
        }
        self.log_object_ids = {
            str(item["record"]): item["candidate"].get("object_id")
            for item in source["review_candidates"]
            if item["model"] == "admin.LogEntry"
            and item["field"] == "object_id"
            and isinstance(item["candidate"], dict)
        }
        self.references = {
            label: {
                str(record["id"])
                for record in content["records"]
                if "id" in record
            }
            for label, content in source["categories"].items()
            if label in self.related
        }
        self.references["auth.User"] = {self.subject}
        blocked = {item["id"] for item in source["review_candidates"]}
        primary_keys = {
            item["model"]: item.get("primary_key", "id")
            for item in source["category_mapping"]
        }
        for label, records in source.get("references", {}).items():
            primary = primary_keys.get(label, "id")
            self.references[label] = {
                str(record[primary])
                for record in records
                if primary in record
                and f"{label}:{record[primary]}:catalog_reference"
                not in blocked
                and not self.has_protected(record)
            }

    def has_protected(self, value):
        if isinstance(value, str):
            return value in self.protected
        if isinstance(value, dict):
            return any(
                self.secret.search(str(key)) or self.has_protected(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(self.has_protected(item) for item in value)
        return False

    def classify(self, category, pk, name, metadata, value, candidate):
        if self.secret.search(name) or self.has_protected(value):
            return "review.protected.v1"
        if category == "admin.LogEntry":
            proof = self.audit_rule(pk, name, value)
            if proof:
                return proof
        target = metadata.get("relation")
        if (
            candidate
            and category in self.related
            and target
            and self.proven_reference(target, value)
        ):
            return "related.reference.v1"
        if candidate:
            return "review.candidate.v1"
        if category not in self.related or (
            category == "auth.User" and str(pk) != self.subject
        ):
            return "review.shared.v1"
        if value is None or value == "" or value == [] or value == {}:
            return "owned.empty.v1"
        kind = metadata.get("type")
        if kind in {"FileField", "ImageField"}:
            return "review.file.v1"
        if category == "charsheet.UserCalendarLayout" and name == "layout":
            return self.calendar_rule(value)
        if self.technical(category, name, value):
            return "owned.technical.v1"
        if target:
            if self.proven_reference(target, value):
                return (
                    "owned.reference.v1"
                    if category in self.owned
                    else "related.reference.v1"
                )
            if (
                target == "contenttypes.ContentType"
                and type(value) is int
                and value > 0
            ):
                return "related.reference.v1"
            return "review.shared.v1"
        if isinstance(value, (dict, list)):
            return "review.structure.v1"
        choices = metadata.get("choices", {})
        if choices:
            return (
                "owned.choice.v1"
                if str(value) in choices
                else "review.unknown.v1"
            )
        if (
            kind in {"CharField", "TextField"}
            and isinstance(value, str)
            and value == metadata.get("default")
        ):
            return "owned.default.v1"
        if (
            category == "auth.User"
            and name
            in {
                "username",
                "email",
                "first_name",
                "last_name",
            }
            and isinstance(value, str)
            and len(value) <= 254
            and not any(
                character in value for character in ("\n", "\r", "<", ">")
            )
        ):
            return "owned.identity.v1"
        if self.scalar(kind, value):
            return (
                "owned.scalar.v1"
                if category in self.owned
                else "related.scalar.v1"
            )
        if kind in {"CharField", "TextField", "EmailField", "SlugField"}:
            return "review.text.v1"
        return "review.unknown.v1"

    def proven_reference(self, target, value):
        values = value if isinstance(value, list) else [value]
        return all(
            str(item) in self.references.get(target, set()) for item in values
        )

    def audit_rule(self, pk, name, value):
        row = self.log_rows.get(str(pk), {})
        type_id = str(row.get("content_type"))
        target = self.audit.get("targets", {}).get(type_id, {})
        public = self.audit.get("public_objects", {}).get(type_id, {})
        if name == "object_id" and isinstance(value, dict):
            pk = str(value.get("object_id"))
            if str(value.get("content_type")) != type_id:
                return None
            if pk in public or pk in self.references.get(
                target.get("model"), set()
            ):
                return "related.reference.v1"
        if name == "object_repr":
            # A historical string is safe only if it is still an exact public
            # identifier of this particular object, never just the same type.
            original_id = self.log_object_ids.get(
                str(pk), row.get("object_id")
            )
            if isinstance(original_id, (str, int)) and value in public.get(
                str(original_id), []
            ):
                return "related.reference.v1"
        if name != "change_message" or not isinstance(value, str):
            return None
        try:
            entries = json.loads(value)
        except (ValueError, RecursionError):
            return None
        if not isinstance(entries, list) or not target:
            return None
        allowed_fields = set(target.get("fields", []))
        for entry in entries:
            if entry == {"added": {}}:
                continue
            if not isinstance(entry, dict) or set(entry) != {"changed"}:
                return None
            change = entry["changed"]
            if (
                not isinstance(change, dict)
                or set(change) != {"fields"}
                or not isinstance(change["fields"], list)
                or any(
                    not isinstance(field, str) or field not in allowed_fields
                    for field in change["fields"]
                )
            ):
                return None
        return "related.schema_message.v1"

    @staticmethod
    def calendar_rule(value):
        try:
            validate_layout(value)
        except (ValidationError, TypeError, ValueError):
            return "review.structure.v1"
        pending = [value["root"]]
        while pending:
            node = pending.pop()
            text = node.get("text", "")
            if text and not re.fullmatch(r"[\s.,:/;|–—\-()\[\]{}]*", text):
                return "review.calendar_text.v1"
            pending.extend(node.get("children", []))
        return "owned.layout.v1"

    @staticmethod
    def technical(category, name, value):
        # Closed machine codes emitted by item_transfers.py, not the message.
        if category == "charsheet.ItemTransferNotification" and name == "kind":
            return isinstance(value, str) and value in {
                "offer",
                "money",
                "gm_edit_completed",
                "accepted",
                "declined",
                "recalled",
                "returned",
                "expired",
                "enforced",
            }
        if category == "sessions.Session" and name == "authenticated":
            return isinstance(value, bool)
        if category == "auth.EffectivePermission" and name == "scope":
            return value == "Uneingeschränkte Administration"
        if category == "charsheet.PasskeyCredential":
            if name == "device_type":
                return isinstance(value, str) and value in {
                    "single_device",
                    "multi_device",
                }
            if name == "transports":
                allowed = {
                    "usb",
                    "nfc",
                    "ble",
                    "internal",
                    "hybrid",
                    "cable",
                    "smart-card",
                }
                return isinstance(value, list) and all(
                    isinstance(item, str) and item in allowed for item in value
                )
        return False

    @staticmethod
    def scalar(kind, value):
        if kind == "BooleanField":
            return isinstance(value, bool)
        if kind in INTEGER_TYPES:
            return isinstance(value, int) and not isinstance(value, bool)
        if kind == "FloatField":
            return (
                isinstance(value, (float, int))
                and not isinstance(value, bool)
                and math.isfinite(value)
            )
        if not isinstance(value, str):
            return False
        try:
            if kind == "DecimalField":
                return Decimal(value).is_finite()
            parser = {
                "DateField": date.fromisoformat,
                "DateTimeField": datetime.fromisoformat,
                "TimeField": time.fromisoformat,
                "UUIDField": UUID,
            }
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
        "ruleset",
        "source_fingerprint",
        "subject_id",
        "categories",
        "counts",
        "overrides",
    }:
        raise ValueError("Ungültiger Nachweis der Standardprüfung.")
    if (
        review["ruleset"] != RULESET
        or type(review["subject_id"]) is not int
        or not isinstance(review["source_fingerprint"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", review["source_fingerprint"])
    ):
        raise ValueError("Veraltete oder ungültige Standardprüfung.")
    categories = review["categories"]
    if not isinstance(categories, dict) or any(
        not isinstance(name, str)
        or not isinstance(rules, list)
        or any(
            not isinstance(rule, str) or rule not in AUTOMATIC_RULES
            for rule in rules
        )
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
        not isinstance(key, str)
        or not isinstance(value, str)
        or value
        not in {
            "include",
            "redact",
            "partial",
            "withhold",
            "not_personal",
            "pending",
        }
        for key, value in overrides.items()
    ):
        raise ValueError("Ungültige manuelle Prüfentscheidung.")
