"""Read-only, administrative privacy snapshots. Never used by public views."""

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
from django.utils import timezone


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
}
SPECIAL_OMIT = {
    "AccountSecurityEvent": {"metadata"},
    "CharacterQuickslotLayout": {"slots"},
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
    "administrative_services", "reviewed_on",
)
PROCESSING_KEYS = (
    "purposes", "recipients", "retention", "sources", "transfers",
    "automated_decisions", "legal_bases",
)


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
    return value


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
            if name == "GameGroupCreature":
                # Shared GM-screen cards require a manual third-party review.
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


def validate_review(review, mode):
    if not isinstance(review, dict):
        raise ValueError("Prüfdatei muss ein JSON-Objekt sein.")
    allowed = {"processing", "redactions", "portability", "approval"}
    if set(review) - allowed:
        raise ValueError("Unbekanntes Feld in der Prüfdatei.")
    for key in allowed:
        if not isinstance(review.get(key, {}), dict):
            raise ValueError("Ungültiger Abschnitt in der Prüfdatei.")
    processing = review.get("processing", {})
    if set(processing) - set(PROCESSING_KEYS) or any(
        not isinstance(value, str) for value in processing.values()
    ):
        raise ValueError("Ungültige Verarbeitungsinformationen.")
    redactions = review.get("redactions", {})
    if any(not isinstance(value, str) for value in redactions.values()):
        raise ValueError("Schwärzungen müssen Textwerte sein.")
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
        if any(not processing.get(key, "").strip()
               for key in PROCESSING_KEYS):
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
        self.payload = {
            "schema_version": 1,
            "generated_at": timezone.now().isoformat(),
            "mode": mode,
            "subject": {"id": user.pk},
            "status": "Administrative Abschlussprüfung erforderlich",
            "legal_configuration": {
                key: (getattr(settings, "LEGAL_INFO", {}).get(key)
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
            "references": {},
        }

    def omit(self, model, pk, field, reason):
        self.payload["omissions"].append({
            "model": model, "record": pk, "field": field, "reason": reason,
        })

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
        for obj in queryset.order_by(model._meta.pk.name).iterator(
            chunk_size=500,
        ):
            record = {}
            for field in fields:
                name = field.name
                if (requested and name not in requested
                        and not field.primary_key):
                    continue
                if only and name not in only:
                    continue
                if SECRET.search(name) or name in SPECIAL_OMIT.get(
                    model.__name__, set(),
                ):
                    self.omit(label, obj.pk, name, "Sicherheits-/Drittschutz")
                    continue
                value = getattr(obj, field.attname)
                key = f"{label}:{obj.pk}:{name}"
                if key in self.review.get("redactions", {}):
                    self.used_redactions.add(key)
                    value = self.review["redactions"][key]
                    self.omit(label, obj.pk, name, "Administrative Schwärzung")
                elif shared and name in SHARED_TEXT:
                    value = REDACTED
                    self.omit(label, obj.pk, name, "Gemeinsamer Inhalt")
                elif field.is_relation and value is not None:
                    target = field.related_model
                    if target in self.personal_ids:
                        if value not in self.personal_ids[target]:
                            value = REDACTED
                            self.omit(label, obj.pk, name, "Fremde Zuordnung")
                    elif target._meta.app_label == "charsheet" and (
                        target.__name__ in SHARED
                        or target.__name__.startswith("GameGroup")
                    ):
                        value = REDACTED
                        self.omit(label, obj.pk, name, "Gruppenbezug")
                elif isinstance(field, models.FileField):
                    value = self.file_value(obj, field, key)
                else:
                    value = scrub(value)
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
                if only:
                    continue
                target = field.related_model
                manager = getattr(obj, field.name)
                values = manager.values_list("pk", flat=True).order_by("pk")
                if target in self.personal_ids:
                    values = values.filter(pk__in=self.personal_ids[target])
                record[field.name] = normalized(list(values))
                category["fields"][field.name] = {
                    "label": str(field.verbose_name),
                    "type": "ManyToManyField",
                    "description": "IDs verknüpfter Datensätze",
                    "relation": target._meta.label,
                }
            category["records"].append(record)
        self.payload["categories"][label] = category

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
                  "last_login"},
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
            self.security_categories()
        known = set(self.payload["categories"])
        if set(self.review.get("portability", {})) - known:
            raise ValueError("Unbekannte Art.-20-Kategorie.")
        if set(self.review.get("redactions", {})) - self.used_redactions:
            raise ValueError(
                "Schwärzung passt nicht zum aktuellen Datenbestand."
            )
        self.payload["omissions"].append({
            "reason": "Passwort-Hashes, Authentifizierungsgeheimnisse, "
            "Sessiondaten/-schlüssel, Berechtigungszuordnungen und "
            "nicht sicher zuordenbare Drosselungs-Buckets ausgeschlossen. "
            "Gruppennotizen/-tabellen und fremde Spielinhalte manuell prüfen.",
        })
        self.catalog_references()

    def catalog_references(self):
        """Give catalog IDs readable names without traversing personal data."""
        targets = {}
        for category in self.payload["categories"].values():
            for name, description in category["fields"].items():
                label = description.get("relation")
                if not label or not label.startswith("charsheet."):
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
            names = [f for f in ("name", "slug", "code", "short_name")
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

    def security_categories(self):
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
        self.category(
            log, log._base_manager.filter(user_id=self.user.pk),
            only={"id", "action_time", "action_flag"},
        )
        if getattr(settings, "SESSION_ENGINE", "").endswith(
            (".db", ".cached_db"),
        ):
            session_model = apps.get_model("sessions", "Session")
            records = []
            sessions = session_model.objects.all().iterator(chunk_size=500)
            for session in sessions:
                if str(session.get_decoded().get("_auth_user_id")) == str(
                    self.user.pk,
                ):
                    records.append({"expire_date": normalized(
                        session.expire_date,
                    )})
            self.payload["categories"]["sessions.Session"] = {
                "label": "Gespeicherte Sitzungen (ohne Geheimnisse)",
                "fields": {"expire_date": {
                    "label": "Ablaufzeit", "type": "DateTimeField",
                    "description": "Gespeicherte Ablaufzeit der Sitzung",
                }},
                "records": records,
            }


def snapshot_digest(payload):
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


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
    if (approval["subject_id"] != payload["subject"]["id"]
            or approval["review_sha256"] != review_digest(payload)):
        raise ValueError("Freigabe passt nicht zum aktuellen Export.")
    payload["status"] = "Administrativ geprüft und zur Auskunft freigegeben"
    payload["administrative_approval"] = approval
