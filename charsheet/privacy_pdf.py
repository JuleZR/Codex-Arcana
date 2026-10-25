"""Local A4 privacy reports using the project's existing PyMuPDF dependency."""

import json
import textwrap
from html import escape

import pymupdf

from .privacy_export import review_digest, snapshot_digest


CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #25313e; }
h1 { font-family: serif; font-size: 28pt; color: #172333; }
h2 { font-family: serif; font-size: 17pt; color: #172333;
     page-break-before: always; }
h3 { font-size: 11pt; color: #795a2c; }
p { line-height: 1.4; }
table { width: 100%; border-collapse: collapse; margin-bottom: 10pt; }
td, th { padding: 5pt; border-bottom: 0.5pt solid #d5d0c5;
         text-align: left; font-size: 9pt; }
th { background-color: #eee9df; color: #172333; }
a { color: #795a2c; }
.eyebrow { color: #795a2c; font-size: 10pt; }
.muted { color: #586575; font-size: 9pt; }
"""
PROCESSING_LABELS = {
    "purposes": "Verarbeitungszwecke",
    "recipients": "Empfänger und Empfängerkategorien",
    "retention": "Aufbewahrungsfristen und Kriterien",
    "sources": "Herkunft der Daten",
    "transfers": "Drittlandübermittlungen und Garantien",
    "automated_decisions": "Automatisierte Entscheidungen und Profiling",
    "legal_bases": "Geprüfte Rechtsgrundlagen",
}


def display(value):
    if value is None:
        return "Nicht gespeichert"
    if value is True:
        return "Ja"
    if value is False:
        return "Nein"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value) or "(leer)"


def rows(label, value):
    """Bound every table row so a huge text/JSON field can cross pages safely.

    Story keeps table rows together. Splitting values into short continuation
    rows avoids both overheight rows and unbreakable identifiers. No value is
    truncated. There are never more than two columns.
    """
    lines = []
    for line in display(value).splitlines() or [""]:
        lines.extend(textwrap.wrap(
            line, width=34, break_long_words=True, break_on_hyphens=False,
            replace_whitespace=False, drop_whitespace=False,
        ) or [""])
    rendered = []
    for index in range(0, len(lines), 3):
        heading = label if index == 0 else "(Fortsetzung)"
        # Field names also have bounded line lengths.
        heading = "<br>".join(escape(part) for part in textwrap.wrap(
            heading, width=20, break_long_words=True,
        ))
        cell = "<br>".join(escape(part) for part in lines[index:index + 3])
        rendered.append(f"<tr><td>{heading}</td><td>{cell}</td></tr>")
    return "".join(rendered)


def table(values):
    return (
        "<table><tr><th>Feld / Bedeutung</th><th>Gespeicherter Wert</th></tr>"
        + "".join(rows(key, value) for key, value in values) + "</table>"
    )


def sections(payload):
    result = [
        ("account", "Persönliche Daten und Erstellungsdatum", table([
            ("Benutzerkonto-ID", payload["subject"]["id"]),
            ("Erstellt (ISO 8601)", payload["generated_at"]),
            ("Exportart", "Art. 15 DSGVO - Auskunft" if
             payload["mode"] == "access"
             else "Art. 20 - Datenübertragbarkeit"),
            ("Prüfstatus", payload["status"]),
            ("SHA-256 Datengrundlage", snapshot_digest(payload)),
            ("SHA-256 für administrative Freigabe", review_digest(payload)),
            ("Administrative Freigabe", payload.get(
                "administrative_approval", "Noch nicht bestätigt",
            )),
        ])),
        ("processing", "Verarbeitung und Betroffenenrechte", table(
            [(PROCESSING_LABELS[key], value)
             for key, value in payload["processing"].items()],
        ) + table([
            ("Betroffenenrechte", payload["rights"]),
            ("Sicherheitsereignisse: konfigurierte Frist in Tagen",
             payload["security_retention_days"]),
        ]) + table(payload["legal_configuration"].items())),
        ("overview", "Übersicht der Datenkategorien", table([
            (key, len(category["records"]))
            for key, category in payload["categories"].items()
        ])),
    ]
    for index, (key, category) in enumerate(payload["categories"].items()):
        if not category["records"]:
            continue
        body = [f"<p>{len(category['records'])} Datensätze. "
                "Zeitwerte enthalten ihre Zeitzone; Datumswerte sind "
                "Kalenderdaten. Verknüpfungen sind interne IDs.</p>"]
        for number, record in enumerate(category["records"], 1):
            body.append(f"<h3>Datensatz {number}</h3>")
            body.append(table([
                (f"{name} / " + category["fields"].get(name, {}).get(
                    "label", name,
                ), value) for name, value in record.items()
            ]))
        body.append("<h3>Feldverzeichnis</h3>")
        body.append(table(category["fields"].items()))
        result.append((f"category-{index}", key, "".join(body)))
    result.extend([
        ("references", "Bedeutung verknüpfter Katalogdaten", table([
            (name, records)
            for name, records in payload["references"].items()
        ])),
        ("files", "Zugeordnete Dateien", table([
            (str(index), item)
            for index, item in enumerate(payload["files"], 1)
        ]) or "<p>Keine Dateien.</p>"),
        ("omissions", "Auslassungen und Schwärzungen", table([
            (str(index), item)
            for index, item in enumerate(payload["omissions"], 1)
        ])),
        ("review", "Administrative Abschlussprüfung", "".join(
            f"<p>{escape(item)}</p>" for item in payload["manual_review"]
        ) + "<p>Die inhaltliche und rechtliche Verantwortung für die Auskunft "
            "verbleibt beim Verantwortlichen. Der Prüfstatus und eine "
            "gegebenenfalls erteilte Freigabe stehen am Berichtsanfang.</p>"),
    ])
    return result


def write_pdf(payload, destination):
    report_sections = sections(payload)
    page_box = pymupdf.paper_rect("a4")
    content_box = page_box + (42, 52, -42, -48)
    headings = {}
    iterations = 0

    def content(positions):
        nonlocal iterations
        iterations += 1
        if iterations > 12:
            raise ValueError("PDF-Inhaltsverzeichnis stabilisiert sich nicht.")
        pages = {
            item.id: item.page_num for item in positions
            if item.id and item.open_close & 1
        }
        toc = "".join(
            f'<p><a href="#{key}">{escape(title)}</a> '
            f"... {pages.get(key, '-')}</p>"
            for key, title, _ in report_sections
        )
        body = "".join(
            f'<h2 id="{key}">{escape(title)}</h2>{body}'
            for key, title, body in report_sections
        )
        return (
            '<p class="eyebrow">CODEX ARCANA · PERSÖNLICHE VERWALTUNG</p>'
            '<h1>Datenschutzauskunft</h1>'
            '<p class="muted">Vertraulich · Nur für die betroffene Person '
            'und die berechtigte administrative Bearbeitung</p>'
            + table([
                ("Benutzerkonto-ID", payload["subject"]["id"]),
                ("Erstellt", payload["generated_at"]),
                ("Prüfstatus", payload["status"]),
            ])
            + '<h2>Inhaltsverzeichnis</h2>' + toc + body
        )

    def record(position):
        if position.id and position.open_close & 1:
            headings[position.id] = position.page_num

    document = pymupdf.Story.write_stabilized_with_links(
        content, lambda *_: (page_box, content_box, None),
        user_css=CSS, positionfn=record,
    )
    try:
        document.set_toc([
            [1, title, headings[key]] for key, title, _ in report_sections
        ])
        document.set_metadata({
            "title": "Codex Arcana - Datenschutzauskunft",
            "subject": f"Benutzerkonto {payload['subject']['id']}",
            "creator": "Codex Arcana privacy_export (lokal)",
        })
        for index, page in enumerate(document):
            page.draw_line((42, 34), (page_box.width - 42, 34),
                           color=(0.48, 0.35, 0.17), width=0.7)
            page.insert_text(
                (42, 26), "CODEX ARCANA | Vertraulich", fontsize=8,
            )
            page.insert_text(
                (42, page_box.height - 26),
                f"Konto-ID {payload['subject']['id']} | "
                f"Seite {index + 1} / {len(document)}", fontsize=8,
            )
        document.save(destination, garbage=4, deflate=True)
    finally:
        document.close()
