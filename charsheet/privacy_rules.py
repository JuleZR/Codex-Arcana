"""Versioned disclosure rules; classification never removes personal data."""

import math
import json
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db.models import ImageField
from django.apps import apps
from django.contrib.admin.models import ADDITION
from django.contrib.auth import get_user_model

from .calendar_layout import validate_layout
from .privacy_content import PROTECTED
from .privacy_mentions import (
    INVITATION_CHECK_VERSION, INVITATION_MODEL, TRANSFER_MODELS,
    ITEM_CONTENT_MODELS,
    words,
)

RULESET = "privacy-standard-v12"
RULES = {
    "owned.image.v1": (True, "Hochgeladenes Bild und Dateiname"),
    "owned.game_value.v1": (True, "Eigene Spielausprägung"),
    "owned.passkey_label.v1": (True, "Selbstgewählter Passkey-Name"),
    "owned.security_metadata.v1": (True, "Geprüfte Sicherheitsmetadaten"),
    "owned.group_table.v1": (
        True, "Eigene Gruppentabelle und Würfelprotokoll",
    ),
    "owned.item_content.v1": (
        True, "Eigene Charaktergegenstandsdaten",
    ),
    "invitation.content.v1": (True, "Einladung ohne fremde Benutzerkennung"),
    "review.invitation_account.v1": (
        False, "Fremde Benutzerkennung in einer Einladung prüfen",
    ),
    "owned.creature_attack.v1": (True, "Eigene Kreaturenangriffe"),
    "owned.login_log.v1": (True, "Anmeldeprotokoll des ausgewählten Kontos"),
    "owned.empty.v1": (True, "Leerer Wert ohne Inhaltsangaben"),
    "owned.scalar.v1": (True, "Typgeprüfter eigener Standardwert"),
    "owned.choice.v1": (True, "Eigener Wert aus festgelegter Auswahlliste"),
    "owned.reference.v1": (True, "Geprüfter eigener oder öffentlicher Bezug"),
    "owned.identity.v1": (True, "Identitätsangabe des ausgewählten Kontos"),
    "owned.layout.v1": (True, "Validierte Kalenderanordnung ohne Freitext"),
    "owned.technical.v1": (True, "Geschlossene technische Angabe"),
    "owned.default.v1": (True, "Unveränderter Standardtext der Anwendung"),
    "owned.dice.v1": (True, "Eigene Würfeleinstellungen und Ergebnistexte"),
    "owned.hotbar.v1": (True, "Eigene MMO-Toolbar und Slotbelegung"),
    "transfer.content.v1": (
        True, "Gegenstandsübertragung und Eigentumshistorie",
    ),
    "transfer.protected_account.v1": (
        True,
        "Geschützten fremden Benutzerbezug beibehalten",
    ),
    "review.username.v1": (
        False,
        "Eigentumsübertragung auf Benutzernamen prüfen",
    ),
    "related.scalar.v1": (True, "Typgeprüfte Metadaten eines Kontobezugs"),
    "related.reference.v1": (
        True,
        "Geprüfter Bezug zu zugeordneten Daten",
    ),
    "related.schema_message.v1": (
        True,
        "Änderungsprotokoll mit reinen Schemaangaben",
    ),
    "admin.activity.v1": (True, "Verwaltungsvorgang ohne Benutzeranlage"),
    "admin.protected_actor.v1": (
        True,
        "Geschützten fremden Verwaltungsakteur beibehalten",
    ),
    "review.account_creation.v1": (
        False,
        "Administrative Anlage eines Benutzers",
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
AUTOMATIC_ACTIONS = {
    "transfer.protected_account.v1": "withhold",
    "admin.protected_actor.v1": "withhold",
}
DICE_SETTINGS_FIELDS = frozenset(
    {
        "critical_success_text",
        "critical_failure_text",
        "mw_success_text",
        "mw_failure_text",
        "special_failure_text",
        "dddice_room_id",
        "dddice_dice_box",
        "dddice_theme_id",
    }
)
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


def image_field(category, name, metadata):
    if metadata.get("type") == "ImageField":
        return True
    if metadata.get("type") != "FileField":
        return False
    try:
        return isinstance(apps.get_model(category)._meta.get_field(name),
                          ImageField)
    except (LookupError, FieldDoesNotExist):
        return False


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
        self.invitation_check = source.get("review_context", {}).get(
            "invitation_accounts", {}
        )
        own_names = {
            row.get("username") for row in source["categories"].get(
                "auth.User", {}).get("records", [])
            if str(row.get("id")) == self.subject and row.get("username")
        }
        self.login_rows = {
            (label, str(row["id"]))
            for label in (
                "axes.AccessLog", "axes.AccessAttempt",
                "axes.AccessFailureLog",
            )
            for row in source["categories"].get(label, {}).get("records", [])
            if row.get("username") in own_names
        }
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
        self.admin_actions = self.classify_admin_actions(source)
        self.own_tables = {
            str(row["id"]) for row in source["categories"].get(
                "charsheet.GameGroupTable", {}).get("records", [])
            if str(row.get("creator")) == self.subject
        }
        self.inventory_catalog = set()
        for label in ITEM_CONTENT_MODELS & self.owned:
            content = source["categories"].get(label, {})
            for name, meta in content.get("fields", {}).items():
                relation = meta.get("relation", "") or ""
                if not relation.startswith("charsheet."):
                    continue
                for row in content.get("records", []):
                    values = row.get(name)
                    for pk in values if isinstance(values, list) else [values]:
                        if type(pk) in {int, str}:
                            self.inventory_catalog.add((relation, str(pk)))
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
            proof = self.audit_rule(pk, name, value, candidate)
            if proof:
                return proof
        target = metadata.get("relation")
        kind = metadata.get("type")
        if (name == "catalog_reference"
                and (category, str(pk)) in self.inventory_catalog):
            return "owned.item_content.v1"
        if image_field(category, name, metadata) and category in self.related:
            return "owned.image.v1"
        if (category == "charsheet.GameGroupTable"
                and str(pk) in self.own_tables):
            return "owned.group_table.v1"
        if category in self.owned and not target:
            if category == "charsheet.PasskeyCredential" and name == "name":
                return "owned.passkey_label.v1"
            if name in {"specification", "specialization", "expression",
                        "specification_value"}:
                return "owned.game_value.v1"
            if (category == "charsheet.AccountSecurityEvent"
                    and name == "metadata" and isinstance(value, dict)
                    and set(value) <= {"session_count", "label"}
                    and isinstance(value.get("label", ""), str)
                    and type(value.get("session_count", 0)) is int
                    and value.get("session_count", 0) >= 0):
                return "owned.security_metadata.v1"
        if (
            category in ITEM_CONTENT_MODELS and category in self.owned
            and target != "auth.User" and kind != "BinaryField"
        ):
            return "owned.item_content.v1"
        if (
            category == INVITATION_MODEL and category in self.related
            and self.invitation_check.get("version")
            == INVITATION_CHECK_VERSION
        ):
            matched = self.invitation_check.get("checked", {}).get(
                f"{category}:{pk}:{name}")
            if matched is True or (
                target == "auth.User"
                and not self.proven_reference(target, value)
            ):
                return "review.invitation_account.v1"
            if matched is False and metadata.get("type") not in {
                "FileField", "ImageField", "BinaryField",
            }:
                return "invitation.content.v1"
        if (
            (category, str(pk)) in self.login_rows and not candidate
            and name in {
                "id", "username", "user_agent", "ip_address", "attempt_time",
                "logout_time", "failures_since_start", "locked_out",
            }
        ):
            return "owned.login_log.v1"
        transfer_rule = self.transfer_rule(
            category, pk, name, metadata, value, candidate
        )
        if transfer_rule:
            return transfer_rule
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
        if (
            category == "charsheet.CharacterCreatureAttack"
            and category in self.owned and not target
            and kind != "BinaryField"
        ):
            return "owned.creature_attack.v1"
        if category == "charsheet.UserCalendarLayout" and name == "layout":
            return self.calendar_rule(value)
        if (
            category == "charsheet.CharacterQuickslotLayout"
            and name == "slots"
        ):
            return (
                "owned.hotbar.v1"
                if self.hotbar_layout(value)
                else "review.structure.v1"
            )
        if self.technical(category, name, value):
            return "owned.technical.v1"
        if (
            category == "charsheet.UserSettings"
            and name in DICE_SETTINGS_FIELDS
            and isinstance(value, str)
        ):
            return "owned.dice.v1"
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

    def transfer_rule(self, category, pk, name, metadata, value, candidate):
        if category not in TRANSFER_MODELS or category not in self.related:
            return None
        if metadata.get("type") in {"FileField", "ImageField", "BinaryField"}:
            return None
        if metadata.get(
            "relation"
        ) == "auth.User" and not self.proven_reference("auth.User", value):
            if candidate:
                return "transfer.protected_account.v1"
            return None
        return "transfer.content.v1"

    def classify_admin_actions(self, source):
        if not self.log_rows:
            return {}
        user_model = get_user_model()._meta.concrete_model
        models = list(apps.get_models())
        user_models = [
            model
            for model in models
            if model._meta.concrete_model is user_model
        ]
        user_labels = {
            tuple(words(label))
            for model in user_models
            for label in (
                str(model._meta.verbose_name),
                str(model._meta.verbose_name_plural),
            )
        }
        user_labels.update(
            {("user",), ("users",), ("benutzer",), ("benutzerkonto",)}
        )
        user_model_labels = {model._meta.label for model in user_models}
        messages = {
            str(item["record"]): item["candidate"]
            for item in source["review_candidates"]
            if item["model"] == "admin.LogEntry"
            and item["field"] == "change_message"
        }
        result = {}
        for pk, row in self.log_rows.items():
            target = self.audit.get("targets", {}).get(
                str(row.get("content_type")), {}
            )
            action = row.get("action_flag")
            if type(action) is not int:
                continue
            user_target = target.get("model") in user_model_labels
            created = user_target and action == ADDITION
            message = messages.get(pk, row.get("change_message", ""))
            if not isinstance(message, str) or message in self.protected:
                result[pk] = "creation" if created else "routine"
                continue
            try:
                entries = json.loads(message)
            except (ValueError, RecursionError):
                entries = []
            if isinstance(entries, dict):
                entries = [entries]
            for entry in entries if isinstance(entries, list) else []:
                added = entry.get("added") if isinstance(entry, dict) else None
                if not isinstance(added, dict):
                    continue
                if (user_target and not added) or tuple(
                    words(str(added.get("name", "")))
                ) in user_labels:
                    created = True
            result[pk] = "creation" if created else "routine"
        return result

    def audit_rule(self, pk, name, value, candidate):
        action = self.admin_actions.get(str(pk))
        if action == "creation":
            return "review.account_creation.v1"
        if action == "routine":
            if (
                name == "user"
                and candidate
                and not self.proven_reference("auth.User", value)
            ):
                return "admin.protected_actor.v1"
            return "admin.activity.v1"
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
    def hotbar_layout(value):
        from .quickslots import _validated_layout

        if isinstance(value, list):
            payload = {"slots": value, "collapsed": False}
            banks = [value]
        elif isinstance(value, dict) and set(value) == {
            "base",
            "ctrl",
            "shift",
        }:
            payload = {
                "slots": value["base"],
                "collapsed": False,
                "bars": {key: value[key] for key in ("ctrl", "shift")},
            }
            banks = [value["base"]] + [
                value[key].get("slots")
                for key in ("ctrl", "shift")
                if isinstance(value[key], dict)
            ]
        else:
            return False
        try:
            # The save validator strips unknown action keys. Equality ensures
            # the export never silently loses such data during prechecking.
            if _validated_layout(payload)["slots"] != value:
                return False
            return all(
                set(modifier) <= {"name", "value"}
                for bank in banks
                for action in bank
                if action
                for modifier in action.get("modifiers", [])
            )
        except (ValueError, TypeError, KeyError):
            return False

    @staticmethod
    def technical(category, name, value):
        if category == "charsheet.AccountSecurityEvent" and name == "device":
            from .auth_security import DEVICE_SUMMARIES

            return isinstance(value, str) and value in DEVICE_SUMMARIES
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
