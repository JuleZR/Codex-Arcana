"""Validate public deployment facts from the existing environment settings."""

from datetime import date
import re
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.checks import Error, Warning, register
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.dispatch import receiver
from django.utils import timezone
from django.utils.autoreload import autoreload_started


FIELD_LABELS = {
    "site_name": "Angebotsname",
    "operator_name": "Betreibername",
    "address": "Betreiberanschrift",
    "email": "rechtliche Kontaktadresse",
    "phone": "Telefon",
    "responsible_person": "redaktionell verantwortliche Person",
    "responsible_address": "redaktionelle Anschrift",
    "vat_id": "Umsatzsteuer-ID",
    "register_entry": "Registereintrag",
    "supervisory_authority": "Zulassungs-/Berufsaufsicht",
    "data_protection_officer": "Datenschutzbeauftragter",
    "reviewed_on": "Datum der inhaltlichen Überarbeitung",
    "hosting_provider": "Hostinganbieter",
    "hosting_location": "Hostingstandorte",
    "server_log_retention": "Serverprotokolle und deren Aufbewahrung",
    "backup_policy": "Sicherungs- und Löschkonzept",
    "email_provider": "E-Mail-Dienstleister oder lokales Versandverfahren",
    "email_location": "Verarbeitungsorte des E-Mail-Dienstes",
    "email_retention": "Aufbewahrung beim E-Mail-Versand",
    "email_tracking": "Öffnungs-/Klicktracking beim E-Mail-Versand",
    "contact_retention": "Verarbeitung und Aufbewahrung von Kontaktanfragen",
    "security_cleanup": "Bereinigung der Kontosicherheitsereignisse",
    "auth_log_retention": "Aufbewahrung weiterer Anmeldeprotokolle",
    "processor_contracts": "Auftragsverarbeitung und Empfängerrollen",
    "transfer_safeguards": "internationale Übermittlungen und Garantien",
    "test_data_policy": "Entwicklungs-/Testkopien und deren Löschung",
    "turnstile_details": "Betriebsangaben zum eingeschalteten Turnstile",
    "additional_processing": "weitere Datenverarbeitungen",
    "administrative_services": "administrative Betriebsdienste",
}
REQUIRED_FIELDS = (
    "operator_name", "address", "email", "reviewed_on", "hosting_provider",
    "hosting_location", "server_log_retention", "backup_policy",
    "email_provider", "email_location", "email_retention", "email_tracking",
    "contact_retention", "security_cleanup", "auth_log_retention",
    "processor_contracts", "transfer_safeguards", "test_data_policy",
)
SECRET_PATTERN = re.compile(
    r"(?:discord(?:app)?\.com/api(?:/v\d+)?/webhooks/"
    r"|hooks\.slack\.com/services/|-----BEGIN .*PRIVATE KEY-----"
    r"|\bBearer\s+[A-Za-z0-9._~+/=-]{10,}"
    r"|\b(?:api[_ -]?key|secret|password|token|authorization)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
SECRET_QUERY_KEYS = {
    "api_key", "apikey", "token", "secret", "password", "signature", "auth",
}


@receiver(autoreload_started, dispatch_uid="charsheet.legal_dotenv_watch")
def watch_legal_environment(sender, **kwargs):
    """Reload development settings when the installation's .env changes."""
    sender.extra_files.add(settings.BASE_DIR / ".env")


def _contains_credentials(value):
    if SECRET_PATTERN.search(value):
        return True
    for raw_url in re.findall(r'https?://[^\s<>"\']+', value):
        try:
            url = urlsplit(raw_url)
            if url.username or url.password:
                return True
            if SECRET_QUERY_KEYS.intersection(
                key.casefold() for key in parse_qs(url.query)
            ):
                return True
        except ValueError:
            return True
    return False


def inspect_legal_info():
    """Return sanitized facts and checks; never echo invalid values."""
    source = getattr(settings, "LEGAL_INFO", {})
    errors = []
    if not isinstance(source, dict):
        source = {}
        errors.append(Error(
            "LEGAL_INFO muss ein Dictionary aus Umgebungswerten sein.",
            id="legal.E001",
        ))
    if set(source).difference(FIELD_LABELS):
        errors.append(Error(
            "LEGAL_INFO enthält unbekannte Felder; Schema in docs/legal.md "
            "prüfen. Unbekannte Werte werden nicht veröffentlicht.",
            id="legal.E001",
        ))

    legal = {}
    for field in FIELD_LABELS:
        value = source.get(field, "")
        env_name = "LEGAL_" + field.upper()
        if not isinstance(value, str) or len(value) > 20000:
            errors.append(Error(
                f"{env_name} muss Text mit höchstens 20000 Zeichen sein.",
                id="legal.E002",
            ))
            value = ""
        value = value.strip()
        if _contains_credentials(value):
            errors.append(Error(
                f"{env_name} enthält möglicherweise Zugangsdaten oder eine "
                "Webhook-Adresse. Nur öffentliche Sachangaben verwenden.",
                id="legal.E005",
            ))
            value = ""
        legal[field] = value

    if legal["email"]:
        try:
            validate_email(legal["email"])
        except ValidationError:
            errors.append(Error(
                "LEGAL_EMAIL muss eine gültige E-Mail-Adresse enthalten.",
                id="legal.E003",
            ))
            legal["email"] = ""
    if legal["reviewed_on"]:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", legal["reviewed_on"]):
                raise ValueError
            now = timezone.now()
            today = (
                timezone.localtime(now).date()
                if timezone.is_aware(now) else now.date()
            )
            if date.fromisoformat(legal["reviewed_on"]) > today:
                raise ValueError
        except ValueError:
            errors.append(Error(
                "LEGAL_REVIEWED_ON muss ein vorhandenes Datum im Format "
                "YYYY-MM-DD sein und darf nicht in der Zukunft liegen.",
                id="legal.E004",
            ))
            legal["reviewed_on"] = ""

    required = list(REQUIRED_FIELDS)
    if legal["responsible_person"] or legal["responsible_address"]:
        required.extend(("responsible_person", "responsible_address"))
    if settings.AUTH_TURNSTILE_ENABLED:
        required.append("turnstile_details")
    else:
        # An unused provider description must not imply active processing.
        legal["turnstile_details"] = ""
    missing = [field for field in required if not legal[field]]
    return legal, missing, errors


@register("legal")
def check_legal_configuration(app_configs, **kwargs):
    """Report missing facts separately from invalid public configuration."""
    _legal, missing, messages = inspect_legal_info()
    if missing:
        messages.append(Warning(
            "Installationsabhängige Legal-Angaben fehlen: "
            + ", ".join("LEGAL_" + field.upper() for field in missing),
            hint="Lokale .env anhand von .env.example und docs/legal.md "
            "ergänzen. Leere Werte sind keine Freigabe zur Veröffentlichung.",
            id="legal.W001",
        ))
    return messages


def legal_page_context():
    """Use the same validation for system checks and public rendering."""
    legal, missing, errors = inspect_legal_info()
    legal["reviewed_date"] = (
        date.fromisoformat(legal["reviewed_on"])
        if legal["reviewed_on"] else None
    )
    legal["missing_required"] = any(
        not legal[field] for field in ("operator_name", "address", "email")
    )
    legal["configuration_incomplete"] = bool(missing or errors)
    legal["configuration_invalid"] = bool(errors)
    legal["missing_information"] = [FIELD_LABELS[field] for field in missing]
    return {"legal": legal}
