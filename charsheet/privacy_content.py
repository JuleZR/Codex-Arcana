"""Separate the administrative evidence from a recipient's data copy.

Static descriptions document application behaviour, not installation-specific
providers, deletion schedules or past disclosures. Those require a review.
"""

import re

from .legal import _contains_credentials
from .privacy_labels import PHRASES, VALUE_LABELS, german_label


PROCESSING_LABELS = {
    "purposes": "Verarbeitungszwecke",
    "recipients": "Tatsächliche Empfänger und Empfängerkategorien",
    "retention": "Speicherdauer und Festlegungskriterien",
    "sources": "Herkunft der personenbezogenen Daten",
    "transfers": "Drittlandübermittlungen und geeignete Garantien",
    "automated_decisions": "Automatisierte Entscheidungen und Profiling",
    "legal_bases": "Rechtsgrundlagen der Verarbeitung",
}
REQUIRED_PROCESSING = set(PROCESSING_LABELS) - {"legal_bases"}
COVERAGE_LABELS = {
    "shared_content": "Gemeinsame Inhalte und Erwähnungen durch andere",
    "external_records": "Protokolle, E-Mails, Backups und externe Bestände",
    "historical_identifiers": "Historische Namen und sichere Datenzuordnung",
    "personal_json": "Freitexte und persönliche JSON-Inhalte",
}
SERVICE_LABELS = {
    "hosting": "Hosting und Infrastruktur",
    "email": "E-Mail-Versand",
    "turnstile": "Cloudflare Turnstile",
    "dddice": "DDDICE",
    "administrative_services": "Benachrichtigungs- und Betriebsdienste",
    "additional_processing": "Weitere Verarbeitungen",
}
SERVICE_FIELDS = {"recipients", "data", "purposes", "retention", "transfers"}
CONTROLLER_LABELS = {
    "name": "Verantwortlicher Betreiber", "address": "Anschrift",
    "email": "Kontakt", "data_protection_officer": "Datenschutzbeauftragter",
    "complaint_authority": "Datenschutzaufsichtsbehörde",
}
PLACEHOLDERS = re.compile(
    r"nicht konfiguriert|administrativ ergänzen|"
    r"administrativ für diesen betreiber|administrative prüfung erforderlich|"
    r"administrative abschlussprüfung erforderlich|"
    r"bitte datenzuordnung prüfen|"
    r"\b(?:todo|tbd)\b|hier .*eintragen", re.I,
)
PROTECTED = "[Geschützter Inhalt]"


def meaningful(value):
    return (isinstance(value, str) and bool(value.strip())
            and not PLACEHOLDERS.search(value)
            and not _contains_credentials(value))


def sanitize(value):
    """Never publish credential-looking keys or values, even in supplements."""
    from .privacy_export import SECRET, REDACTED

    if isinstance(value, dict):
        return {str(k): PROTECTED if SECRET.search(str(k)) else sanitize(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        if value == REDACTED or _contains_credentials(value):
            return PROTECTED
    return value


def validate_content_review(review):
    """Validate explicit decisions; a checked box alone cannot release data."""
    for key in ("coverage", "resolutions", "services", "controller",
                "file_decisions"):
        if not isinstance(review.get(key, {}), dict):
            raise ValueError("Ungültige inhaltliche Prüfangaben.")
    controller = review.get("controller", {})
    if set(controller) - set(CONTROLLER_LABELS) or any(
        not meaningful(value) for value in controller.values()
    ):
        raise ValueError("Ungültige Betreiberangaben.")
    coverage = review.get("coverage", {})
    if set(coverage) - set(COVERAGE_LABELS):
        raise ValueError("Unbekannter Prüfbereich.")
    for entry in coverage.values():
        if (not isinstance(entry, dict)
                or set(entry) != {"checked", "statement"}
                or entry["checked"] is not True
                or not meaningful(entry["statement"])):
            raise ValueError("Konkretes Prüfergebnis fehlt.")
    services = review.get("services", {})
    if set(services) - set(SERVICE_LABELS):
        raise ValueError("Unbekannter Dienst-Prüfbereich.")
    for entry in services.values():
        if not isinstance(entry, dict):
            raise ValueError("Ungültige Dienstprüfung.")
        if entry.get("status") == "used":
            if (set(entry) != SERVICE_FIELDS | {"status"}
                    or any(not meaningful(entry.get(key))
                           for key in SERVICE_FIELDS - {"transfers"})):
                raise ValueError("Dienste vollständig beschreiben.")
            transfer = entry["transfers"]
            if (not isinstance(transfer, dict)
                    or type(transfer.get("applies")) is not bool
                    or not meaningful(transfer.get("details"))):
                raise ValueError("Drittlandbetroffenheit ausdrücklich prüfen.")
            required = {"applies", "details"}
            if transfer["applies"]:
                required |= {"safeguards", "copy_source"}
            if (set(transfer) != required
                    or any(not meaningful(transfer.get(key))
                           for key in required - {"applies"})):
                raise ValueError("Garantien und deren Bezugsquelle fehlen.")
        elif entry.get("status") == "not_used":
            if (set(entry) != {"status", "reason"}
                    or not meaningful(entry["reason"])):
                raise ValueError("Nichtnutzung konkret begründen.")
        else:
            raise ValueError("Dienststatus nicht geprüft.")
    for decision in review.get("resolutions", {}).values():
        if (not isinstance(decision, dict)
                or decision.get("action") not in {
                    "include", "withhold", "not_personal"}
                or not meaningful(decision.get("reason"))
                or set(decision) - {"action", "reason", "value"}
                or (decision["action"] == "include"
                    and "value" not in decision)
                or (decision["action"] != "include" and "value" in decision)):
            raise ValueError("Einzelfallentscheidung unvollständig.")
    for decision in review.get("file_decisions", {}).values():
        if (not isinstance(decision, dict)
                or set(decision) != {"action", "reason"}
                or decision["action"] not in {
                    "separate_delivery", "withhold", "not_personal"}
                or not meaningful(decision["reason"])):
            raise ValueError("Fehlende Dateikopie benötigt eine Begründung.")
    supplements = review.get("supplements", [])
    if not isinstance(supplements, list):
        raise ValueError("Ergänzungen müssen eine Liste sein.")
    for entry in supplements:
        if (not isinstance(entry, dict)
                or set(entry) != {
                    "category", "source", "purpose", "retention", "records"}
                or any(not meaningful(entry[key]) for key in (
                    "category", "source", "purpose", "retention"))
                or not isinstance(entry["records"], list)
                or any(not isinstance(record, dict)
                       for record in entry["records"])
                or sanitize(entry) != entry):
            raise ValueError("Ergänzungen unvollständig oder unsicher.")


def category_policy(label):
    """Map model families to observed use and origin, not legal guesses."""
    name = label.rsplit('.', 1)[-1]
    if name in {"User", "EffectivePermission", "UserSettings",
                "UserCalendarLayout",
                "CharacterQuickslotLayout"}:
        return ("Benutzerkonto und Einstellungen",
                "Kontoführung, Zugriffssteuerung und persönliche Darstellung",
                "Kontoinhaber, Administration und gespeicherte Systemzustände")
    if (label.startswith(("axes.", "sessions.", "admin."))
            or name in {"AccountSecurityEvent", "AuthenticationThrottle",
                        "PasskeyCredential", "TwoFactorRecoveryCode"}):
        return ("Authentifizierung und Kontosicherheit",
                "Anmeldung, Missbrauchsbegrenzung und Sicherheitsnachweise",
                "Zugriffsversuche, Browser und serverseitige Abläufe")
    if (label.startswith("reviewed.") or name.startswith("GameGroup")
            or name in {
        "ItemTransfer", "ItemOwnershipEvent", "ItemPermissionGrant",
        "ItemTransferNotification",
            }):
        return ("Gruppen, Berechtigungen und Übertragungen",
                "Gemeinsames Spiel und Nachvollziehbarkeit von Berechtigungen",
                "Kontoinhaber, andere Beteiligte und Systemereignisse")
    return ("Eigene Charaktere und persönlich zugeordnete Spielinhalte",
            "Speicherung individueller Spielstände und Entscheidungen",
            "Eingaben, Auswahlentscheidungen und gespeicherte Spielzustände")


def controller_information(payload):
    legal = payload.get("legal_configuration", {})
    # LEGAL_RESPONSIBLE_PERSON is editorial responsibility; LEGAL_SUPERVISORY_
    # AUTHORITY is professional oversight. Neither identifies GDPR authorities.
    result = {"name": legal.get("operator_name"),
              "address": legal.get("address"),
              "email": legal.get("email"),
              "data_protection_officer": legal.get("data_protection_officer")}
    result.update(payload.get("content_review", {}).get("controller", {}))
    return {key: value for key, value in result.items() if meaningful(value)}


def missing_items(payload):
    missing = []
    review = payload.get("content_review", {})
    if payload.get("mode") == "access":
        processing = payload.get("processing", {})
        missing.extend(PROCESSING_LABELS[key] for key in REQUIRED_PROCESSING
                       if not meaningful(processing.get(key)))
        controller = controller_information(payload)
        missing.extend(CONTROLLER_LABELS[key]
                       for key in ("name", "address", "email")
                       if key not in controller)
        coverage = review.get("coverage", {})
        missing.extend(label for key, label in COVERAGE_LABELS.items()
                       if not coverage.get(key, {}).get("checked")
                       or not meaningful(
                           coverage.get(key, {}).get("statement")))
        missing.extend("Dienstprüfung: " + label
                       for key, label in SERVICE_LABELS.items()
                       if key not in review.get("services", {}))
    missing.extend("Einzelfallprüfung: " + entry["id"]
                   for entry in payload.get("review_candidates", [])
                   if entry["id"] not in review.get("resolutions", {}))
    for item in payload.get("files", []):
        if (item.get("status") != "included" and item["member"]
                not in review.get("file_decisions", {})):
            missing.append("Dateikopie / Zustellung: " + item["member"])
    return sorted(missing)


def recipient_payload(payload):
    """Same personal records, minimal metadata; no internal review evidence."""
    if payload.get("audience") == "recipient":
        return payload
    review = payload.get("content_review", {})
    categories = {}
    summaries = {}
    for label, category in payload["categories"].items():
        title = PHRASES.get(label, PHRASES.get(
            label.rsplit('.', 1)[-1],
            german_label(category.get("label") or label)))
        fields = {name: {
            "label": PHRASES.get(name, german_label(meta.get("label", name))),
            **{key: meta[key] for key in ("relation", "choices")
               if meta.get(key)},
        } for name, meta in category["fields"].items()
            if name != "selected_content_type"}
        if (label == "charsheet.AccountSecurityEvent"
                and "event_type" in fields):
            choices = fields["event_type"].get("choices", {})
            fields["event_type"]["choices"] = {
                key: VALUE_LABELS.get(key, value)
                for key, value in choices.items()
            }
        if (label == "charsheet.AuthenticationThrottle"
                and "category" in fields):
            fields["category"]["choices"] = VALUE_LABELS
        categories[label] = {"label": title, "fields": fields,
                             "records": [sanitize({key: value
                                                   for key, value in
                                                   record.items()
                                                   if key in fields})
                                         for record in category["records"]]}
        count = len(category["records"])
        if count:
            family, purpose, source = category_policy(label)
            summary = summaries.setdefault(family, {
                "category": family, "records": 0,
                "purpose": purpose, "source": source,
            })
            summary["records"] += count
    for index, entry in enumerate(payload.get("supplements", [])):
        label = f"supplement-{index + 1}"
        fields = {name: {"label": name} for record in entry["records"]
                  for name in record}
        categories[label] = {"label": entry["category"], "fields": fields,
                             "records": entry["records"]}
        summaries[label] = {key: entry[key] for key in (
            "category", "source", "purpose", "retention")}
        summaries[label]["records"] = len(entry["records"])
    files = []
    for item in payload.get("files", []):
        exported = {key: item[key] for key in (
            "member", "status", "bytes", "filename")
                    if key in item}
        decision = review.get("file_decisions", {}).get(item["member"])
        if decision:
            exported.update(decision)
        files.append(exported)
    omissions = []
    for item in payload.get("omissions", []):
        model = item.get("model")
        omission = {"reason": item["reason"]}
        if model:
            omission["category"] = categories.get(model, {}).get(
                "label", german_label(model))
        if "record" in item:
            omission["record"] = item["record"]
        if "field" in item:
            omission["field"] = PHRASES.get(
                item["field"], german_label(item["field"]))
        omissions.append(omission)
    services = []
    for key, entry in review.get("services", {}).items():
        if entry["status"] != "used":
            continue
        transfer = entry["transfers"]
        service = {"name": SERVICE_LABELS[key],
                   **{field: entry[field]
                      for field in SERVICE_FIELDS - {"transfers"}},
                   "transfers": transfer["details"]}
        if transfer["applies"]:
            service.update({field: transfer[field]
                            for field in ("safeguards", "copy_source")})
        services.append(service)
    return {
        "schema_version": 2, "audience": "recipient",
        "generated_at": payload["generated_at"], "mode": payload["mode"],
        "subject": payload["subject"], "processing_confirmation": True,
        "document_status": "released" if payload.get("administrative_approval")
        else "draft", "controller": controller_information(payload),
        "processing": {key: value
                       for key, value in payload["processing"].items()
                       if meaningful(value)}, "rights": payload["rights"],
        "data_categories": list(summaries.values()),
        "services": services,
        "categories": categories,
        "references": sanitize(payload.get("references", {})),
        "files": files, "omissions": omissions,
    }


def json_document(payload, internal=False):
    if internal:
        from .privacy_export import review_digest, snapshot_digest

        return {"audience": "internal",
                "snapshot_sha256": snapshot_digest(payload),
                "review_sha256": review_digest(payload), "data": payload,
                "missing_information": missing_items(payload)}
    return {"data": recipient_payload(payload)}


def reference_names(payload):
    """Resolve IDs to minimal labels, without loading unrelated ORM objects."""
    result = {}
    sources = {key: value["records"] for key, value in
               payload["categories"].items()}
    sources.update(payload.get("references", {}))
    for category, records in sources.items():
        names = {}
        for number, record in enumerate(records, 1):
            if "id" not in record:
                continue
            label = next((str(record[field]) for field in (
                "name_override", "custom_name", "name", "username", "title",
                "short_name",
                "code", "codename",
            ) if record.get(field) and isinstance(record[field], str)
                and record[field] != PROTECTED), None)
            if label is None:
                label = (payload["categories"].get(category, {}).get(
                    "label", german_label(category)) + f" – Eintrag {number}")
            names[str(record["id"])] = label
        result[category] = names
    return result


def readable_value(value, meta, references):
    if isinstance(value, list) and meta.get("relation"):
        return [readable_value(item, meta, references) for item in value]
    if isinstance(value, (dict, list)):
        return value
    label = references.get(meta.get("relation"), {}).get(str(value))
    if label is not None:
        return label
    return meta.get("choices", {}).get(str(value), value)
