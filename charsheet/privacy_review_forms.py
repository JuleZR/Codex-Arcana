"""Ordinary form controls for every administrative privacy decision."""

from django import forms

from .privacy_content import (
    CONTROLLER_LABELS,
    COVERAGE_LABELS,
    PROCESSING_LABELS,
    meaningful,
)


def text_field(label, required=False, rows=3):
    return forms.CharField(
        label=label,
        required=required,
        max_length=1000000,
        widget=forms.Textarea(attrs={"rows": rows}),
    )


class InformationForm(forms.Form):
    def __init__(self, *args, labels, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label in labels.items():
            self.fields[key] = text_field(label)

    def clean(self):
        data = super().clean()
        for key, value in list(data.items()):
            if value and not meaningful(value):
                self.add_error(
                    key,
                    "Bitte eine geprüfte Sachangabe ohne "
                    "Platzhalter oder Zugangsdaten eintragen.",
                )
        return data


class ControllerForm(InformationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, labels=CONTROLLER_LABELS, **kwargs)
        self.fields["email"] = forms.EmailField(
            label="Kontakt-E-Mail", required=False
        )
        for key in ("name", "address", "email"):
            self.fields[key].help_text = (
                "Pflichtangabe vor der Art.-15-Freigabe."
            )


class ProcessingForm(InformationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, labels=PROCESSING_LABELS, **kwargs)
        for key, field in self.fields.items():
            if key != "legal_bases":
                field.help_text = (
                    "Pflichtangabe für eine Auskunft nach Art. 15."
                )


class CoverageForm(forms.Form):
    checked = forms.BooleanField(label="Prüfung abgeschlossen", required=False)
    statement = text_field("Konkretes Prüfergebnis")

    def clean(self):
        data = super().clean()
        if data.get("checked") and not meaningful(data.get("statement")):
            self.add_error(
                "statement", "Das konkrete Ergebnis der Prüfung fehlt."
            )
        return data


class ServiceForm(forms.Form):
    status = forms.ChoiceField(
        label="Bezug zu diesem Benutzer",
        required=False,
        choices=[
            ("", "Noch ungeprüft"),
            ("used", "Personenbezogene Verarbeitung"),
            ("not_used", "Kein Personenbezug festgestellt"),
        ],
    )
    recipients = text_field("Tatsächliche Empfänger")
    data = text_field("Betroffene personenbezogene Daten")
    purposes = text_field("Verwendungszwecke")
    retention = text_field("Speicherdauer oder konkrete Kriterien")
    transfer_applies = forms.ChoiceField(
        label="Drittlandübermittlung",
        required=False,
        choices=[("", "Noch ungeprüft"), ("no", "Nein"), ("yes", "Ja")],
    )
    details = text_field(
        "Geprüfte Angaben zu Verarbeitungsorten / Übermittlungen"
    )
    safeguards = text_field("Geeignete Garantien")
    copy_source = text_field("Kopie der Garantien / Bezugsquelle")
    reason = text_field("Begründung der Nichtbetroffenheit")

    def clean(self):
        data = super().clean()
        required = []
        if data.get("status") == "used":
            required = [
                "recipients",
                "data",
                "purposes",
                "retention",
                "details",
            ]
            if not data.get("transfer_applies"):
                self.add_error(
                    "transfer_applies", "Drittlandbetroffenheit prüfen."
                )
            if data.get("transfer_applies") == "yes":
                required += ["safeguards", "copy_source"]
        elif data.get("status") == "not_used":
            required = ["reason"]
        for key in required:
            if not meaningful(data.get(key)):
                self.add_error(key, "Bitte die geprüfte Angabe ergänzen.")
        return data

    def review_entry(self):
        data = self.cleaned_data
        if data["status"] == "not_used":
            return {"status": "not_used", "reason": data["reason"]}
        if not data["status"]:
            return None
        entry = {
            key: data[key]
            for key in (
                "status",
                "recipients",
                "data",
                "purposes",
                "retention",
            )
        }
        transfer = {
            "applies": data["transfer_applies"] == "yes",
            "details": data["details"],
        }
        if transfer["applies"]:
            transfer.update(
                safeguards=data["safeguards"], copy_source=data["copy_source"]
            )
        entry["transfers"] = transfer
        return entry


class FieldForm(forms.Form):
    action = forms.ChoiceField(
        label="Entscheidung",
        choices=[
            ("include", "Übernehmen"),
            ("redact", "Schwärzen"),
            ("partial", "Teilweise schwärzen / geprüften Auszug ergänzen"),
            ("withhold", "Begründete Ausnahme"),
            ("not_personal", "Kein personenbezogener Anteil"),
            ("reset", "Entscheidung rückgängig machen"),
        ],
    )
    reason = text_field("Begründung")
    text = text_field("Freizugebender Text", rows=9)
    as_text = forms.BooleanField(
        label="Statt der Struktur einen geprüften Textauszug verwenden",
        required=False,
    )

    def __init__(self, *args, field, **kwargs):
        self.review_field = field
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        action = data.get("action")
        if action == "reset":
            return data
        if action == "include" and not self.review_field.can_take:
            self.add_error(
                "action",
                "Hier einen geprüften Auszug ergänzen "
                "oder eine Ausnahme begründen.",
            )
        if (
            self.review_field.candidate or action != "include"
        ) and not meaningful(data.get("reason")):
            self.add_error(
                "reason", "Diese Entscheidung benötigt eine Begründung."
            )
        return data


class BulkForm(forms.Form):
    scope = forms.ChoiceField(label="Umfang", choices=[
        ("selected", "Markierte Felder dieser Seite"),
        ("filtered", "Alle gefilterten Felder dieser Kategorie"),
    ])
    action = forms.ChoiceField(label="Sammelentscheidung", choices=[
        ("include", "Übernehmen"), ("redact", "Schwärzen"),
        ("reset", "Entscheidungen zurücksetzen"),
    ])
    reason = text_field("Gemeinsame Begründung", rows=2)

    def clean(self):
        data = super().clean()
        if (data.get("action") == "redact"
                and not meaningful(data.get("reason"))):
            self.add_error("reason", "Schwärzung bitte begründen.")
        return data


class OutputForm(forms.Form):
    format = forms.ChoiceField(
        label="Exportformat",
        choices=[
            ("zip", "ZIP – PDF, JSON und gewählte Anhänge"),
            ("pdf", "PDF – lesbarer Auskunftsbericht"),
            ("json", "JSON – maschinenlesbare Datenkopie"),
        ],
    )
    audience = forms.ChoiceField(
        label="Verwendungszweck",
        choices=[
            ("recipient", "Datenkopie für die betroffene Person"),
            ("internal", "Interne Prüfkopie – nicht weitergeben"),
        ],
    )
    files_reviewed = forms.BooleanField(
        label="Weitere Anhänge (außer Bildern) auf Rechte Dritter geprüft",
        required=False,
    )

    def __init__(self, *args, mode, **kwargs):
        self.mode = mode
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("format") == "pdf" and (
            self.mode == "portability" or data.get("audience") == "internal"
        ):
            self.add_error("format", "Für diese Ausgabe JSON oder ZIP wählen.")
        return data


class FileForm(forms.Form):
    action = forms.ChoiceField(
        label="Umgang mit dem Anhang",
        required=False,
        choices=[
            ("", "Noch ungeprüft"),
            ("include", "Im ZIP beifügen"),
            ("separate_delivery", "Getrennt zustellen"),
            ("withhold", "Begründete Ausnahme"),
            ("not_personal", "Kein Personenbezug"),
        ],
    )
    reason = text_field("Begründung / geschützter Zustellweg")

    def clean(self):
        data = super().clean()
        if data.get("action") not in {None, "", "include"} and not meaningful(
            data.get("reason")
        ):
            self.add_error("reason", "Begründung oder Zustellweg ergänzen.")
        return data


class SupplementForm(forms.Form):
    category = forms.CharField(
        label="Bezeichnung der ergänzten Daten", max_length=160
    )
    source = text_field("Geprüfte Herkunft", required=True)
    purpose = text_field("Verwendungszweck", required=True)
    retention = text_field("Speicherdauer / Kriterien", required=True)


class SupplementValueForm(forms.Form):
    label = forms.CharField(
        label="Bezeichnung", max_length=160, required=False
    )
    value = text_field("Personenbezogener Wert")


class ApprovalForm(forms.Form):
    confirmed = forms.BooleanField(
        label="Ich habe die angezeigte Auskunft, Schwärzungen und "
        "Ausnahmen geprüft und gebe genau diesen Stand frei."
    )


def coverage_forms(data, initial):
    return [
        (
            key,
            label,
            CoverageForm(
                data, prefix="coverage-" + key, initial=initial.get(key, {})
            ),
        )
        for key, label in COVERAGE_LABELS.items()
    ]
