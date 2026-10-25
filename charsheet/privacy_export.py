"""Read-only, administrative privacy snapshots. Never used by public views."""

import base64
import hashlib
import json
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, models, transaction
from django.db.models import Q
from django.db.models.functions import Cast
from django.utils import timezone

from .legal import inspect_legal_info
from .privacy_content import (
    REQUIRED_PROCESSING, category_policy, meaningful, missing_items, sanitize,
    validate_content_review,
)


REDACTED = "[geschützt; administrative Prüfung erforderlich]"
SECRET = re.compile(
    r"password|secret|token|api.?key|credential_id|public_key|code_hash|"
    r"session_key|session_hash|key_digest|recovery.?code", re.I,
)
# These are ownership edges, NOT arbitrary paths through the relation graph.
EDGES = {
    "Character": "owner",
    "UserSettings": "user",
    "UserCalendarLayout": "user",
    "CharacterCreationTemplate": "owner",
    "CharacterCreationDraft": "owner",
    "CharacterQuickslotLayout": "user",
    "PasskeyCredential": "user",
    "TwoFactorRecoveryCode": "user",
    "AccountSecurityEvent": "user",
    "CharacterItem": "owner",
    "CharacterTrait": "owner",
    "CharacterLanguage": "owner",
    "CharacterCreature": "owner",
    "CharacterCreatureCommandPrerequisite": "command",
    "CharacterCreatureTraitChoice": "character_creature_trait",
    "CharacterTraitChoice": "character_trait",
    "CharacterSpecializationChoice": "character_specialization",
    "ItemRune": "item",
}
SHARED = {
    "GameGroup": ("creator",),
    "GameGroupRole": ("user",),
    "GameGroupInvitation": ("character__owner", "invited_by"),
    "GameGroupMembership": ("character__owner",),
    "GameGroupTable": ("creator",),
    "GameGroupCreature": ("character_creature__owner__owner",),
    "GameGroupCreatureVampirePower": (
        "creature__character_creature__owner__owner",),
    "GameGroupCreatureVampireTrait": (
        "creature__character_creature__owner__owner",),
    "ItemTransfer": (
        "sender__owner", "recipient__owner", "initiated_by_user",
    ),
    "ItemOwnershipEvent": (
        "actor__owner", "actor_user", "original_owner__owner",
        "from_character__owner", "to_character__owner",
    ),
    "ItemPermissionGrant": ("granted_by__owner", "grantee__owner"),
    "ItemTransferNotification": ("user",),
}
SHARED_TEXT = {
    "screen_note_html", "message", "item_snapshot", "sender_snapshot",
    "recipient_snapshot", "details", "title", "name",
    "name_override",
    "object_repr", "change_message",
}
SPECIAL_OMIT = {
    "CharacterTraitChoice": {"selected_object_id"},
    "CharacterCreatureTraitChoice": {"selected_object_id"},
    "CharacterTechniqueChoice": {"selected_object_id"},
    "CharacterRaceChoice": {"selected_object_id"},
    "CharacterSpecializationChoice": {"selected_object_id"},
}
LEGAL_KEYS = (
    "site_name", "operator_name", "address", "email",
    "responsible_person", "responsible_address", "data_protection_officer",
    "supervisory_authority", "hosting_provider", "hosting_location",
    "server_log_retention", "backup_policy", "email_provider",
    "email_location", "email_retention", "contact_retention",
    "security_cleanup", "auth_log_retention", "processor_contracts",
    "transfer_safeguards", "turnstile_details", "additional_processing",
    "administrative_services", "reviewed_on", "email_tracking",
    "test_data_policy",
)
PROCESSING_KEYS = (
    "purposes", "recipients", "retention", "sources", "transfers",
    "automated_decisions", "legal_bases",
)

# Only recipient-facing information; deployment switches and review notes stay
# in the administrative JSON snapshot.
PUBLIC_LEGAL_LABELS = {
    "operator_name": "Verantwortlicher Betreiber",
    "address": "Anschrift des Betreibers",
    "email": "Kontakt zum Betreiber",
    "data_protection_officer": "Datenschutzbeauftragter / Kontakt",
    "hosting_provider": "Hosting-Dienstleister",
    "hosting_location": "Ort der Datenverarbeitung beim Hosting",
    "server_log_retention": "Speicherdauer der Serverprotokolle",
    "backup_policy": "Aufbewahrung von Sicherungskopien",
    "email_provider": "E-Mail-Dienstleister",
    "email_location": "Ort der E-Mail-Verarbeitung",
    "email_retention": "Aufbewahrung von E-Mails",
    "contact_retention": "Aufbewahrung von Kontaktanfragen",
    "auth_log_retention": "Aufbewahrung von Anmeldeprotokollen",
    "transfer_safeguards": "Garantien bei Drittlandübermittlungen",
    "additional_processing": "Weitere Verarbeitung personenbezogener Daten",
}


def information_present(value):
    return meaningful(value)


def missing_information(payload):
    """Block final approval rather than publish configuration placeholders."""
    return missing_items(payload)


def normalized(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def scrub(value):
    """Defense in depth for supplied JSON; opaque security JSON is excluded."""
    if isinstance(value, dict):
        return {
            str(key): REDACTED if SECRET.search(str(key)) else scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return sanitize(value)


def ownership_paths():
    """Resolve only reviewed containment relations from actual model fields."""
    paths = {}
    pending = list(apps.get_app_config("charsheet").get_models())
    user_model = get_user_model()
    while pending:
        progress = False
        for model in pending[:]:
            name = model.__name__
            if name in SHARED:
                pending.remove(model)
                continue
            edge = EDGES.get(name)
            fields = {field.name: field for field in model._meta.fields}
            if not edge and name.startswith("Character"):
                edge = next((key for key in (
                    "character", "character_item", "creature",
                ) if key in fields), None)
            if not edge:
                continue
            field = fields[edge]
            target = field.related_model
            if target is user_model:
                paths[model] = edge
            elif target in paths:
                paths[model] = edge + "__" + paths[target]
            else:
                continue
            pending.remove(model)
            progress = True
        if not progress:
            break
    # A new directly personal model must be reviewed before exports proceed.
    for model in pending:
        if any(
            field.is_relation and (
                field.related_model is user_model
                or field.related_model in paths
            ) for field in model._meta.fields
        ):
            raise ValueError("Nicht zugeordnete Datenkategorie: "
                             + model._meta.label)
    return paths


def category_inventory(paths):
    """Schema evidence; unlinked free text is not necessarily non-personal."""
    result = []
    shared_sources = {
        "GameGroupTableColumn", "GameGroupTableRow", "GameGroupTableCell",
    }
    for model in apps.get_app_config("charsheet").get_models():
        name = model.__name__
        entry = {"model": model._meta.label,
                 "label": str(model._meta.verbose_name_plural)}
        if model in paths:
            entry.update(scope="account_owned", ownership_path=paths[model])
        elif name in SHARED:
            entry.update(scope="shared", associations=list(SHARED[name]))
        elif name in shared_sources:
            entry.update(scope="shared_table_review")
        elif name == "AuthenticationThrottle":
            entry.update(scope="reconstructable_account_bucket")
        else:
            entry.update(scope="no_direct_account_assignment")
        if entry["scope"] != "no_direct_account_assignment":
            family, purpose, source = category_policy(model._meta.label)
            entry.update(family=family, application_purpose=purpose,
                         application_origin=source)
        entry["retention_evidence"] = (
            "Speicherdauer und technische Löschbeziehungen abgleichen")
        entry["recipient_evidence"] = (
            "Tatsächliche Offenlegungen anhand der Dienstprüfung zuordnen")
        # These are deletion mechanisms, not evidence of a running cleanup job
        # or a complete legal retention policy.
        entry["deletion_relations"] = {
            field.name: field.remote_field.on_delete.__name__
            for field in model._meta.fields if field.is_relation
        }
        result.append(entry)
    return result


def validate_review(review, mode):
    if not isinstance(review, dict):
        raise ValueError("Prüfdatei muss ein JSON-Objekt sein.")
    allowed = {
        "processing", "redactions", "portability", "approval", "coverage",
        "resolutions", "services", "controller", "supplements",
        "file_decisions",
    }
    if set(review) - allowed:
        raise ValueError("Unbekanntes Feld in der Prüfdatei.")
    for key in allowed - {"supplements"}:
        if not isinstance(review.get(key, {}), dict):
            raise ValueError("Ungültiger Abschnitt in der Prüfdatei.")
    validate_content_review(review)
    processing = review.get("processing", {})
    if set(processing) - set(PROCESSING_KEYS) or any(
        not isinstance(value, str) for value in processing.values()
    ):
        raise ValueError("Ungültige Verarbeitungsinformationen.")
    redactions = review.get("redactions", {})
    if any(sanitize(value) != value for value in redactions.values()):
        raise ValueError("Schwärzungen enthalten unzulässige Inhalte.")
    # Graphical edits preserve JSON containers and unaffected typed leaves.
    normalized(redactions)
    approval = review.get("approval", {})
    if approval and (
        set(approval) != {"subject_id", "review_sha256", "reviewed_at"}
        or not isinstance(approval["subject_id"], int)
        or not isinstance(approval["review_sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", approval["review_sha256"])
        or not isinstance(approval["reviewed_at"], str)
    ):
        raise ValueError("Ungültige administrative Freigabe.")
    if approval:
        from datetime import datetime

        timestamp = datetime.fromisoformat(approval["reviewed_at"])
        if timestamp.tzinfo is None or timestamp > timezone.now():
            raise ValueError("Freigabezeitpunkt muss eine gültige Zeitzone "
                             "enthalten und darf nicht in der Zukunft liegen.")
        if mode == "access" and any(not meaningful(processing.get(key))
                                    for key in REQUIRED_PROCESSING):
            raise ValueError(
                "Verarbeitungsinformationen vor Freigabe ergänzen."
            )
    if mode == "portability" and not review.get("portability"):
        raise ValueError("Art. 20 erfordert geprüfte Kategorien und Felder.")
    for rule in review.get("portability", {}).values():
        if (
            not isinstance(rule, dict)
            or set(rule) != {"basis", "provided_by_subject", "fields"}
            or rule["basis"] not in {"consent", "contract"}
            or rule["provided_by_subject"] is not True
            or not isinstance(rule["fields"], list)
            or not rule["fields"]
            or any(not isinstance(f, str) for f in rule["fields"])
        ):
            raise ValueError("Art.-20-Freigabe ist unvollständig.")


def build_snapshot(user_id, mode="access", review=None):
    """Collect exactly once in a consistent transaction; perform no writes."""
    review = review or {}
    validate_review(review, mode)
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
        user = get_user_model()._base_manager.get(pk=user_id)
        collector = Collector(user, mode, review)
        collector.collect()
        return collector.payload, collector.files


class Collector:
    def __init__(self, user, mode, review):
        self.user = user
        self.mode = mode
        self.review = review
        self.files = []
        self.used_redactions = set()
        self.used_resolutions = set()
        self.shared_ids = {}
        self.source_hash = hashlib.sha256()
        legal, _missing, errors = inspect_legal_info()
        self.payload = {
            "schema_version": 2,
            "generated_at": timezone.now().isoformat(),
            "mode": mode,
            "subject": {"id": user.pk},
            "status": "Administrative Abschlussprüfung erforderlich",
            "legal_configuration": {
                key: (legal.get(key)
                      or "Nicht konfiguriert; administrativ ergänzen")
                for key in LEGAL_KEYS
            },
            "processing": {
                key: review.get("processing", {}).get(key)
                or "Administrativ für diesen Betreiber zu prüfen und ergänzen"
                for key in PROCESSING_KEYS
            },
            "rights": (
                "Berichtigung, Löschung, Einschränkung und Widerspruch nach "
                "den gesetzlichen Voraussetzungen; Beschwerderecht bei "
                "einer Datenschutzaufsichtsbehörde. Kontakt: siehe Betreiber."
            ),
            "security_retention_days": getattr(
                settings, "ACCOUNT_SECURITY_ACTIVITY_RETENTION_DAYS", None,
            ),
            "categories": {},
            "omissions": [],
            "files": [],
            "manual_review": [
                "Freitexte, JSON-Inhalte und Bilder auf Drittpersonen und "
                "versehentlich gespeicherte Geheimnisse prüfen.",
                "Gemeinsame Inhalte, fremdverfasste Erwähnungen und Inhalte "
                "ohne eindeutige Kontozuordnung gesondert ermitteln.",
                "Server-/Proxylogs, E-Mail, Backups und Dienstleister "
                "außerhalb der Datenbank ergänzen.",
                "Zwecke, Rechtsgrundlagen, tatsächliche Empfänger, Fristen, "
                "Herkunft, Drittlandgarantien und automatisierte "
                "Entscheidungen anhand des Betriebs prüfen.",
                "Historische Benutzernamen und gelöste Zuordnungen prüfen; "
                "Axes-Zuordnung über aktuellen Benutzernamen ist unsicher.",
            ],
            "portability_review": review.get("portability", {}),
            "content_review": {
                key: review.get(key, {}) for key in (
                    "coverage", "resolutions", "services", "controller",
                    "file_decisions",
                )
            },
            "supplements": sanitize(review.get("supplements", [])),
            "review_candidates": [],
            "legal_validation": [error.id for error in errors],
            "references": {},
        }

    def omit(self, model, pk, field, reason):
        self.payload["omissions"].append({
            "model": model, "record": pk, "field": field, "reason": reason,
        })

    def observe(self, model, pk, field, value):
        """Bind approvals to non-secret originals, even behind a redaction."""
        encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True)
        original = [model, str(pk), field, sanitize(normalized(value))]
        for part in encoder.iterencode(original):
            self.source_hash.update(part.encode("utf-8"))

    def resolve(self, model, pk, field, value, reason):
        """Keep mixed/unattributed data internal until a specific decision."""
        key = f"{model}:{pk}:{field}"
        self.payload["review_candidates"].append({
            "id": key, "model": model, "record": pk, "field": field,
            "reason": reason, "candidate": sanitize(normalized(value)),
        })
        decision = self.review.get("resolutions", {}).get(key)
        if decision:
            self.used_resolutions.add(key)
            if decision["action"] == "include":
                if sanitize(decision["value"]) != decision["value"]:
                    raise ValueError("Freigabe enthält mögliche Geheimnisse.")
                return normalized(decision["value"])
            reason = decision["reason"]
        self.omit(model, pk, field, reason)
        return REDACTED

    def category(self, model, queryset, shared=False, only=None):
        label = model._meta.label
        rules = self.review.get("portability", {})
        if self.mode == "portability" and label not in rules:
            return
        fields = list(model._meta.fields)
        requested = rules.get(label, {}).get("fields")
        allowed_names = {f.name for f in fields} | {
            f.name for f in model._meta.local_many_to_many
        }
        if requested and set(requested) - allowed_names:
            raise ValueError("Unbekanntes Art.-20-Datenfeld: " + label)
        category = {
            "label": str(model._meta.verbose_name_plural),
            "fields": {}, "records": [],
        }
        collected_ids = set()
        for obj in queryset.order_by(model._meta.pk.name).iterator(
            chunk_size=500,
        ):
            collected_ids.add(obj.pk)
            record = {}
            for field in fields:
                name = field.name
                if (requested and name not in requested
                        and not field.primary_key):
                    continue
                if only and name not in only:
                    continue
                if not SECRET.search(name):
                    original = getattr(obj, field.attname)
                    if isinstance(field, models.FileField):
                        original = original.name or ""
                    self.observe(label, obj.pk, name, original)
                if model.__name__ == "PasskeyCredential" and name in {
                    "credential_id", "public_key",
                }:
                    value = bytes(getattr(obj, field.attname))
                    self.observe(label, obj.pk, name,
                                 base64.b64encode(value).decode("ascii"))
                    public_key = name == "public_key"
                    alias = ("registration_key" if public_key
                             else "registration_identifier")
                    record[alias] = self.resolve(
                        label, obj.pk, name,
                        {"encoding": "Base64",
                         "value": base64.b64encode(value).decode("ascii")},
                        "Öffentliche WebAuthn-Registrierungsdaten prüfen",
                    )
                    category["fields"][alias] = {
                        "label": ("Öffentlicher WebAuthn-Schlüssel (Base64)"
                                  if public_key else
                                  "Registrierungskennung (Base64)"),
                        "type": "TextField", "source_field": name,
                        "description": "Öffentliche WebAuthn-Angabe",
                    }
                    continue
                if SECRET.search(name):
                    self.omit(label, obj.pk, name, "Sicherheits-/Drittschutz")
                    continue
                value = getattr(obj, field.attname)
                key = f"{label}:{obj.pk}:{name}"
                if key in self.review.get("redactions", {}):
                    self.used_redactions.add(key)
                    value = self.review["redactions"][key]
                    reviewed = self.resolve(
                        label, obj.pk, name, {"replacement": value},
                        "Manuelle Schwärzung im Einzelfall begründen")
                    if key in self.used_resolutions:
                        if reviewed != value and reviewed != REDACTED:
                            raise ValueError("Widersprüchliche Schwärzung.")
                        value = reviewed
                elif (name in SPECIAL_OMIT.get(model.__name__, set())
                      and value is not None):
                    value = self.resolve(label, obj.pk, name, {
                        "object_id": value,
                        "content_type": getattr(
                            obj, "selected_content_type_id", None),
                    }, "Ausgewählte Zuordnung im Einzelfall auflösen")
                elif (label == "admin.LogEntry" and name == "object_id"
                      and value):
                    value = self.resolve(
                        label, obj.pk, name,
                        {"object_id": value,
                         "content_type": obj.content_type_id},
                        "Bezug des Änderungsprotokolls prüfen und erläutern")
                elif shared and name in SHARED_TEXT and value:
                    value = self.resolve(
                        label, obj.pk, name, value,
                        "Gemeinsamer Inhalt: personenbezogenen Anteil prüfen",
                    )
                elif field.is_relation and value is not None:
                    target = field.related_model
                    if target in self.personal_ids:
                        if value not in self.personal_ids[target]:
                            value = self.resolve(
                                label, obj.pk, name, value,
                                "Bezug zu weiteren Personen prüfen",
                            )
                    elif target._meta.app_label == "charsheet" and (
                        target.__name__ in SHARED
                        or target.__name__.startswith("GameGroup")
                    ):
                        if value not in self.shared_ids.get(target, set()):
                            value = self.resolve(
                                label, obj.pk, name, value,
                                "Gruppenbezug verständlich erläutern",
                            )
                elif isinstance(field, models.FileField):
                    value = self.file_value(obj, field, key)
                elif (model.__name__ == "AccountSecurityEvent"
                      and name == "metadata"):
                    from .auth_security import _safe_event_metadata

                    safe = _safe_event_metadata(
                        value if isinstance(value, dict) else {})
                    if value and (not isinstance(value, dict)
                                  or set(value) - set(safe)):
                        extra = self.resolve(
                            label, obj.pk, name,
                            {"keys": sorted(value) if isinstance(value, dict)
                             else "Abweichende Datenstruktur"},
                            "Weitere Sicherheitsangaben prüfen")
                        if extra != REDACTED:
                            safe["Weitere geprüfte Angaben"] = extra
                    value = scrub(safe)
                else:
                    cleaned = scrub(value)
                    if cleaned != value:
                        self.omit(
                            label, obj.pk, name,
                            "Mögliche Authentifizierungsgeheimnisse geschützt",
                        )
                    value = cleaned
                record[name] = normalized(value)
                category["fields"][name] = {
                    "label": str(field.verbose_name),
                    "type": field.get_internal_type(),
                    "description": str(field.help_text or field.verbose_name),
                    "relation": (
                        field.related_model._meta.label
                        if field.is_relation else None
                    ),
                    "choices": {
                        str(k): str(v) for k, v in field.flatchoices
                    } if field.choices else {},
                }
            for field in model._meta.local_many_to_many:
                if requested and field.name not in requested:
                    continue
                if only and field.name not in only:
                    continue
                target = field.related_model
                manager = getattr(obj, field.name)
                values = manager.values_list("pk", flat=True).order_by("pk")
                values = list(values)
                self.observe(label, obj.pk, field.name, values)
                if (target in self.personal_ids
                        and set(values) - self.personal_ids[target]):
                    values = self.resolve(label, obj.pk, field.name, values,
                                          "Verknüpfte fremde Inhalte prüfen")
                record[field.name] = normalized(values)
                category["fields"][field.name] = {
                    "label": str(field.verbose_name),
                    "type": "ManyToManyField",
                    "description": "IDs verknüpfter Datensätze",
                    "relation": target._meta.label,
                }
            category["records"].append(record)
        self.payload["categories"][label] = category
        if shared:
            self.shared_ids[model] = collected_ids

    def file_value(self, obj, field, key):
        stored = getattr(obj, field.name)
        if not stored:
            return None
        # No storage names, public URLs or arbitrary remote storage requests.
        suffix = Path(stored.name).suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            suffix = ".bin"
        member = f"files/{len(self.files) + 1:06d}{suffix}"
        info = {"field": key, "member": member, "status": "not_included"}
        self.files.append((stored, info))
        self.payload["files"].append(info)
        return {"attachment": member}

    def collect(self):
        paths = ownership_paths()
        self.paths = paths
        self.payload["category_mapping"] = category_inventory(paths)
        self.personal_ids = {get_user_model(): {self.user.pk}}
        for model, path in paths.items():
            self.personal_ids[model] = set(
                model._base_manager.filter(**{path: self.user.pk})
                .values_list("pk", flat=True)
            )
        self.category(
            get_user_model(),
            get_user_model()._base_manager.filter(pk=self.user.pk),
            only={"id", "username", "email", "first_name", "last_name",
                  "is_active", "is_staff", "is_superuser", "date_joined",
                  "last_login", "groups", "user_permissions"},
        )
        for model, path in paths.items():
            self.category(
                model, model._base_manager.filter(**{path: self.user.pk}),
            )
        for name, relations in SHARED.items():
            model = apps.get_model("charsheet", name)
            query = Q()
            for path in relations:
                query |= Q(**{path: self.user.pk})
            if name == "GameGroup":
                query |= Q(memberships__character__owner=self.user.pk)
                query |= Q(role_assignments__user=self.user.pk)
            self.category(
                model, model._base_manager.filter(query).distinct(),
                shared=True,
            )
        if self.mode == "access":
            self.permission_information()
            self.security_categories()
            self.shared_sources()
        known = set(self.payload["categories"])
        if set(self.review.get("portability", {})) - known:
            raise ValueError("Unbekannte Art.-20-Kategorie.")
        if set(self.review.get("redactions", {})) - self.used_redactions:
            raise ValueError(
                "Schwärzung passt nicht zum aktuellen Datenbestand."
            )
        self.payload["omissions"].append({
            "reason": "Passwort-Hashes, Authentifizierungsgeheimnisse und "
            "Sitzungsschlüssel werden zum Schutz der Zugangssicherheit "
            "nicht offengelegt. IP-Drosselungen ohne eindeutigen Kontobezug "
            "werden keinem Konto pauschal zugeschrieben. "
            "Weitere Einschränkungen sind mit ihrem Grund angegeben.",
        })
        self.catalog_references()
        self.payload["source_fingerprint"] = self.source_hash.hexdigest()
        if set(self.review.get("resolutions", {})) - self.used_resolutions:
            raise ValueError("Einzelfallentscheidung passt nicht zum Bestand.")
        if set(self.review.get("file_decisions", {})) - {
            item["member"] for item in self.payload["files"]
        }:
            raise ValueError("Dateientscheidung passt nicht zum Bestand.")

    def catalog_references(self):
        """Give catalog IDs readable names without traversing personal data."""
        targets = {}
        for category in self.payload["categories"].values():
            for name, description in category["fields"].items():
                label = description.get("relation")
                if not label or not label.startswith(("charsheet.", "auth.")):
                    continue
                model = apps.get_model(label)
                if (model in self.personal_ids or model.__name__ in SHARED
                        or model.__name__.startswith("GameGroup")):
                    continue
                ids = targets.setdefault(model, set())
                for record in category["records"]:
                    value = record.get(name)
                    for pk in value if isinstance(value, list) else [value]:
                        if pk is None or pk == REDACTED:
                            continue
                        try:
                            ids.add(model._meta.pk.to_python(pk))
                        except (ValidationError, ValueError, TypeError):
                            continue
        for model, ids in targets.items():
            fields = {f.name for f in model._meta.fields}
            names = [f for f in (
                "name", "slug", "code", "short_name", "codename")
                     if f in fields]
            if not names:
                continue
            objects = model._base_manager.filter(pk__in=ids)
            if "catalog_group" in fields:
                objects = objects.filter(catalog_group__isnull=True)
            self.payload["references"][model._meta.label] = normalized(list(
                objects.order_by(model._meta.pk.name).values(
                    model._meta.pk.name, *names,
                )
            ))
            found = {model._meta.pk.to_python(record[model._meta.pk.name])
                     for record in
                     self.payload["references"][model._meta.label]}
            for pk in sorted(ids - found):
                value = self.resolve(
                    model._meta.label, pk, "catalog_reference", {"id": pk},
                    "Private oder nicht verfügbare Katalogzuordnung")
                if value != REDACTED:
                    self.payload["references"][model._meta.label].append({
                        "id": pk, "name": value,
                    })

    def shared_sources(self):
        """Keep related tables internal until individually reviewed."""
        group_ids = [record["id"] for record in self.payload["categories"].get(
            "charsheet.GameGroup", {}).get("records", [])]
        table_model = apps.get_model("charsheet", "GameGroupTable")
        cell_model = apps.get_model("charsheet", "GameGroupTableCell")
        for table in table_model._base_manager.filter(
            Q(group_id__in=group_ids) | Q(creator_id=self.user.pk),
        ).order_by("pk").iterator(chunk_size=100):
            columns = list(table.columns.order_by("position", "pk").values(
                "heading", "position"))
            cells = list(cell_model._base_manager.filter(
                row__table=table,
            ).order_by("row__position", "column__position", "pk").values(
                "row__position", "column__heading", "text_value",
                "number_value", "number_suffix",
            ))
            value = self.resolve(
                table_model._meta.label, table.pk, "contents",
                {"title": table.title, "columns": columns, "cells": cells},
                "Beiträge und Erwähnungen in Gruppentabelle prüfen",
            )
            self.observe(table_model._meta.label, table.pk, "contents",
                         {"title": table.title, "columns": columns,
                          "cells": cells})
            if value != REDACTED:
                category = self.payload["categories"].setdefault(
                    "reviewed.SharedContent", {
                        "label": "Geprüfte gemeinsame Inhalte",
                        "fields": {
                            "source": {"label": "Herkunft"},
                            "content": {"label": "Persönliche Inhalte"}},
                        "records": [],
                    })
                category["records"].append({
                    "source": "Gruppentabelle", "content": value,
                })

    def permission_information(self):
        """Personal grants, not a dump of the complete permission catalogue."""
        if self.user.is_superuser:
            records = [{"scope": "Uneingeschränkte Administration"}]
        else:
            permission = apps.get_model("auth", "Permission")
            direct = self.user.user_permissions.values("pk")
            grouped = self.user.groups.values("permissions__pk")
            records = list(permission._base_manager.filter(
                Q(pk__in=direct) | Q(pk__in=grouped),
            ).order_by("pk").values("name", "codename"))
        self.observe("auth.EffectivePermission", self.user.pk,
                     "grants", records)
        self.payload["categories"]["auth.EffectivePermission"] = {
            "label": "Zugewiesene Zugriffsberechtigungen",
            "fields": {"scope": {"label": "Berechtigungsumfang"},
                       "name": {"label": "Berechtigung"},
                       "codename": {"label": "Zuordnung der Berechtigung"}},
            "records": normalized(records),
        }

    def security_categories(self):
        from .auth_security import _bucket_digest
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        throttle = apps.get_model("charsheet", "AuthenticationThrottle")
        query = Q(pk__in=[])
        for category in ("passkey", "two_factor", "recovery_code",
                         "verification_resend", "password_reset_confirm"):
            reference = str(self.user.pk)
            if category == "password_reset_confirm":
                reference = urlsafe_base64_encode(force_bytes(self.user.pk))
            query |= Q(category=category, key_digest=_bucket_digest(
                category, "account", reference))
        self.category(throttle, throttle._base_manager.filter(query), only={
            "id", "category", "attempts", "window_started_at", "blocked_until",
            "updated_at",
        })
        for name in ("AccessLog", "AccessAttempt", "AccessFailureLog"):
            if not apps.is_installed("axes"):
                break
            model = apps.get_model("axes", name)
            self.category(
                model, model._base_manager.filter(
                    username=self.user.get_username(),
                ),
                only={"id", "username", "user_agent", "ip_address",
                      "attempt_time", "logout_time", "failures_since_start",
                      "locked_out"},
            )
        log = apps.get_model("admin", "LogEntry")
        content_type = apps.get_model("contenttypes", "ContentType")
        content_types = {(row["app_label"], row["model"]): row["pk"]
                         for row in content_type._base_manager.values(
                             "pk", "app_label", "model")}
        user_meta = get_user_model()._meta
        log_query = Q(user_id=self.user.pk) | Q(
            content_type_id=content_types.get((user_meta.app_label,
                                              user_meta.model_name)),
            object_id=str(self.user.pk),
        )
        for model, path in self.paths.items():
            meta = model._meta
            type_id = content_types.get((meta.app_label, meta.model_name))
            if type_id is not None:
                owned = model._base_manager.filter(**{path: self.user.pk})
                owned = owned.annotate(privacy_pk=Cast(
                    "pk", models.CharField())).values("privacy_pk")
                log_query |= Q(content_type_id=type_id, object_id__in=owned)
        self.category(
            log, log._base_manager.filter(log_query), shared=True,
            only={"id", "action_time", "action_flag", "user", "content_type",
                  "object_id", "object_repr", "change_message"},
        )
        if getattr(settings, "SESSION_ENGINE", "").endswith(
            (".db", ".cached_db"),
        ):
            session_model = apps.get_model("sessions", "Session")
            records = []
            sessions = session_model.objects.order_by(
                "expire_date", "session_key").iterator(chunk_size=500)
            for session in sessions:
                data = session.get_decoded()
                subject = data.get("_auth_user_id")
                if subject is None:
                    subject = data.get(
                        "two_factor_login_user_id",
                        data.get("password_reset_policy_user_id"))
                if str(subject) != str(self.user.pk):
                    continue
                self.observe("sessions.Session", len(records) + 1, "state", {
                    "expiry": session.expire_date,
                    "temporary": data.get(
                        "charsheet.temporary_attribute_adjustments"),
                    "authenticated": "_auth_user_id" in data,
                    "pending": data.get("two_factor_login_started_at"),
                })
                record = {"expire_date": normalized(session.expire_date),
                          "authenticated": "_auth_user_id" in data}
                temporary = data.get(
                    "charsheet.temporary_attribute_adjustments")
                if isinstance(temporary, dict):
                    own = {str(pk) for pk in self.personal_ids.get(
                        apps.get_model("charsheet", "Character"), set())}
                    record["temporary_attributes"] = {
                        key: scrub(value) for key, value in temporary.items()
                        if key in own
                    }
                    if set(temporary) - own:
                        record["other_adjustments"] = self.resolve(
                            "sessions.Session", len(records) + 1,
                            "other_adjustments", {key: value
                                                  for key, value in
                                                  temporary.items()
                                                  if key not in own},
                            "Weitere temporäre Spielwerte zuordnen",
                        )
                if "two_factor_login_started_at" in data:
                    record["pending_login_started_at"] = normalized(
                        data["two_factor_login_started_at"])
                known = {
                    "_auth_user_id", "_auth_user_backend", "_auth_user_hash",
                    "_session_expiry", "_csrftoken", "two_factor_setup_secret",
                    "two_factor_login_user_id", "two_factor_login_backend",
                    "two_factor_login_next", "two_factor_login_started_at",
                    "passkey_registration", "passkey_authentication",
                    "password_reset_policy_user_id", "_password_reset_token",
                    "charsheet.temporary_attribute_adjustments",
                }
                extra = set(data) - known
                self.observe("sessions.Session", len(records) + 1,
                             "extra_keys", sorted(extra))
                if extra:
                    record["additional_state"] = self.resolve(
                        "sessions.Session", len(records) + 1,
                        "additional_state", {"keys": sorted(extra)},
                        "Weitere persönliche Sitzungsdaten prüfen",
                    )
                records.append(record)
            self.payload["categories"]["sessions.Session"] = {
                "label": "Gespeicherte Sitzungen (ohne Geheimnisse)",
                "fields": {"expire_date": {
                    "label": "Ablaufzeit", "type": "DateTimeField",
                    "description": "Gespeicherte Ablaufzeit der Sitzung",
                }, "authenticated": {"label": "Angemeldet"},
                    "temporary_attributes": {"label": "Temporäre Spielwerte"},
                    "other_adjustments": {"label": "Weitere Spielwerte"},
                    "pending_login_started_at": {
                        "label": "Anmeldung begonnen"},
                    "additional_state": {"label": "Weitere Sitzungsangaben"}},
                "records": records,
            }


def snapshot_digest(payload):
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    for part in encoder.iterencode(payload):
        digest.update(part.encode("utf-8"))
    return digest.hexdigest()


def review_digest(payload):
    """Bind approval to data, redactions and attachment bytes."""
    return snapshot_digest({
        key: value for key, value in payload.items()
        if key not in {"generated_at", "status", "administrative_approval"}
    })


def apply_approval(payload, review):
    approval = review.get("approval")
    if not approval:
        return
    if missing_information(payload):
        raise ValueError("Pflichtangaben vor Freigabe ergänzen.")
    if (approval["subject_id"] != payload["subject"]["id"]
            or approval["review_sha256"] != review_digest(payload)):
        raise ValueError("Freigabe passt nicht zum aktuellen Export.")
    payload["status"] = "Administrativ geprüft und zur Auskunft freigegeben"
    payload["administrative_approval"] = approval
