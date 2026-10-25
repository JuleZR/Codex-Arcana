
"""Local A4 privacy reports using PyMuPDF.

Architecture:
1. Render every report section exactly once.
2. Assemble the report in memory.
3. Generate the table of contents after the report.
4. Insert the table of contents at the beginning.
5. Add final page numbers, clickable links, bookmarks and footers.

No temporary files, repeated full-document layout or database mutations.
"""

import json
import textwrap
from html import escape

import pymupdf

from .privacy_export import review_digest, snapshot_digest


CSS = """
body {
    font-family: sans-serif;
    font-size: 10pt;
    color: #25313e;
}

h1 {
    font-family: serif;
    font-size: 28pt;
    color: #172333;
}

h2 {
    font-family: serif;
    font-size: 17pt;
    color: #172333;
    page-break-before: always;
}

/* Each report section already starts on a new PDF page. */
h2.section-start {
    page-break-before: auto;
}

h3 {
    font-size: 11pt;
    color: #795a2c;
}

p {
    line-height: 1.4;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10pt;
}

td, th {
    padding: 5pt;
    border-bottom: 0.5pt solid #d5d0c5;
    text-align: left;
    font-size: 9pt;
}

th {
    background-color: #eee9df;
    color: #172333;
}

a {
    color: #795a2c;
}

.eyebrow {
    color: #795a2c;
    font-size: 10pt;
}

.muted {
    color: #586575;
    font-size: 9pt;
}

/* Reserve space for page numbers added after rendering. */
.toc-entry {
    padding: 5pt 64pt 5pt 0;
    margin: 0;
    border-bottom: 0.5pt solid #d5d0c5;
    color: #25313e;
}
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
    """Convert values into readable, lossless text."""
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
    """Split large field values into printable continuation rows.

    Short rows prevent PyMuPDF Story from having to place
    a single unbreakable table row across multiple pages.
    No values are intentionally truncated.
    """
    lines = []

    for line in display(value).splitlines() or [""]:
        wrapped = textwrap.wrap(
            line,
            width=34,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])

    rendered = []

    for index in range(0, len(lines), 3):
        heading = label if index == 0 else "(Fortsetzung)"

        heading = "<br>".join(
            escape(part)
            for part in textwrap.wrap(
                heading,
                width=20,
                break_long_words=True,
            )
        )

        cell = "<br>".join(
            escape(part)
            for part in lines[index:index + 3]
        )

        rendered.append(
            f"<tr><td>{heading}</td><td>{cell}</td></tr>"
        )

    return "".join(rendered)


def table(values):
    """Create a two-column HTML table."""
    return (
        "<table>"
        "<tr>"
        "<th>Feld / Bedeutung</th>"
        "<th>Gespeicherter Wert</th>"
        "</tr>"
        + "".join(rows(key, value) for key, value in values)
        + "</table>"
    )


def sections(payload):
    """Yield report sections instead of building one enormous story.

    Only the HTML for the current section needs to be
    prepared for rendering at any given time.
    """
    yield (
        "account",
        "Persönliche Daten und Erstellungsdatum",
        table([
            ("Benutzerkonto-ID", payload["subject"]["id"]),
            ("Erstellt (ISO 8601)", payload["generated_at"]),
            (
                "Exportart",
                "Art. 15 DSGVO - Auskunft"
                if payload["mode"] == "access"
                else "Art. 20 - Datenübertragbarkeit",
            ),
            ("Prüfstatus", payload["status"]),
            ("SHA-256 Datengrundlage", snapshot_digest(payload)),
            (
                "SHA-256 für administrative Freigabe",
                review_digest(payload),
            ),
            (
                "Administrative Freigabe",
                payload.get(
                    "administrative_approval",
                    "Noch nicht bestätigt",
                ),
            ),
        ]),
    )

    yield (
        "processing",
        "Verarbeitung und Betroffenenrechte",
        table([
            (PROCESSING_LABELS.get(key, key), value)
            for key, value in payload["processing"].items()
        ])
        + table([
            ("Betroffenenrechte", payload["rights"]),
            (
                "Sicherheitsereignisse: konfigurierte Frist in Tagen",
                payload["security_retention_days"],
            ),
        ])
        + table(payload["legal_configuration"].items()),
    )

    yield (
        "overview",
        "Übersicht der Datenkategorien",
        table([
            (key, len(category["records"]))
            for key, category in payload["categories"].items()
        ]),
    )

    for index, (key, category) in enumerate(
        payload["categories"].items()
    ):
        if not category["records"]:
            continue

        body = [
            f"<p>{len(category['records'])} Datensätze. "
            "Zeitwerte enthalten ihre Zeitzone; Datumswerte "
            "sind Kalenderdaten. Verknüpfungen sind interne IDs."
            "</p>"
        ]

        for number, record in enumerate(category["records"], 1):
            body.append(f"<h3>Datensatz {number}</h3>")
            body.append(
                table([
                    (
                        f"{name} / "
                        + category["fields"].get(
                            name, {}
                        ).get("label", name),
                        value,
                    )
                    for name, value in record.items()
                ])
            )

        body.append("<h3>Feldverzeichnis</h3>")
        body.append(table(category["fields"].items()))

        yield (
            f"category-{index}",
            key,
            "".join(body),
        )

    yield (
        "references",
        "Bedeutung verknüpfter Katalogdaten",
        table([
            (name, records)
            for name, records in payload["references"].items()
        ]),
    )

    files = payload["files"]

    yield (
        "files",
        "Zugeordnete Dateien",
        table([
            (str(index), item)
            for index, item in enumerate(files, 1)
        ]) if files else "<p>Keine Dateien zugeordnet.</p>",
    )

    yield (
        "omissions",
        "Auslassungen und Schwärzungen",
        table([
            (str(index), item)
            for index, item in enumerate(
                payload["omissions"], 1
            )
        ]),
    )

    yield (
        "review",
        "Administrative Abschlussprüfung",
        "".join(
            f"<p>{escape(item)}</p>"
            for item in payload["manual_review"]
        )
        + (
            "<p>Die inhaltliche und rechtliche Verantwortung "
            "für die Auskunft verbleibt beim Verantwortlichen. "
            "Der Prüfstatus und eine gegebenenfalls erteilte "
            "Freigabe stehen am Berichtsanfang.</p>"
        ),
    )


def write_pdf(payload, destination):
    """Generate an A4 report with a last-built table of contents.

    The data sections are rendered independently. The final
    document receives its table of contents only after all
    section page numbers are known.
    """
    page_box = pymupdf.paper_rect("a4")
    content_box = page_box + (42, 52, -42, -48)

    def page_rectangles(*_):
        return page_box, content_box, None

    document = pymupdf.open()
    toc_entries = []

    try:
        # --------------------------------------------------
        # Phase 1: Render the actual report.
        #
        # Each section is rendered only once.
        # Each section starts on its own new page.
        # --------------------------------------------------

        for key, title, body in sections(payload):
            section_html = (
                f'<h2 class="section-start" id="{escape(key, quote=True)}">'
                f"{escape(title)}</h2>"
                + body
            )

            story = pymupdf.Story(
                html=section_html,
                user_css=CSS,
            )

            section_document = story.write_with_links(
                page_rectangles,
            )

            try:
                if section_document.page_count == 0:
                    raise ValueError(
                        f"PDF-Abschnitt ohne Seiten: {key}"
                    )

                # Page numbers are 1-based for PDF bookmarks.
                start_page = document.page_count + 1

                document.insert_pdf(
                    section_document,
                    links=False,
                    annots=False,
                )

                toc_entries.append(
                    (key, title, start_page)
                )

            finally:
                section_document.close()

        if not toc_entries:
            raise ValueError(
                "PDF-Bericht enthält keine Abschnitte."
            )

        # --------------------------------------------------
        # Phase 2: Build the table of contents.
        #
        # At this point every report section has its final
        # relative page number.
        #
        # Page numbers are stamped on after the TOC's own
        # page count is known. No iterative document
        # layout is required.
        # --------------------------------------------------

        toc_positions = {}

        def record_toc(position):
            if (
                position.id
                and position.id.startswith("toc-entry-")
                and position.open_close & 1
            ):
                toc_positions[position.id] = (
                    position.page_num,
                    pymupdf.Rect(position.rect),
                )

        toc_html = (
            '<p class="eyebrow">'
            "CODEX ARCANA · PERSÖNLICHE VERWALTUNG"
            "</p>"
            "<h1>Datenschutzauskunft</h1>"
            '<p class="muted">'
            "Vertraulich · Nur für die betroffene Person "
            "und die berechtigte administrative Bearbeitung"
            "</p>"
            + table([
                (
                    "Benutzerkonto-ID",
                    payload["subject"]["id"],
                ),
                ("Erstellt", payload["generated_at"]),
                ("Prüfstatus", payload["status"]),
            ])
            + "<h2>Inhaltsverzeichnis</h2>"
            + "".join(
                (
                    f'<p class="toc-entry" id="toc-entry-{index}">'
                    f"{escape(title)}</p>"
                )
                for index, (_, title, _) in enumerate(toc_entries)
            )
        )

        toc_story = pymupdf.Story(
            html=toc_html,
            user_css=CSS,
        )

        toc_document = toc_story.write_with_links(
            page_rectangles,
            positionfn=record_toc,
        )

        try:
            toc_page_count = toc_document.page_count

            if not toc_page_count:
                raise ValueError(
                    "Inhaltsverzeichnis enthält keine Seiten."
                )

            # Verify navigation positions before modifying
            # the report document.
            for index in range(len(toc_entries)):
                marker = f"toc-entry-{index}"

                if marker not in toc_positions:
                    raise ValueError(
                        "Inhaltsverzeichniseintrag "
                        f"nicht positioniert: {marker}"
                    )

            # Insert the completed TOC before the report.
            document.insert_pdf(
                toc_document,
                start_at=0,
                links=False,
                annots=False,
            )

        finally:
            toc_document.close()

        # --------------------------------------------------
        # Phase 3: Add actual TOC page numbers and links.
        #
        # All target pages are now final.
        # No additional layout is performed.
        # --------------------------------------------------

        for index, (_, title, original_page) in enumerate(
            toc_entries
        ):
            marker = f"toc-entry-{index}"

            toc_page, entry_rect = toc_positions[marker]

            # Absolute destination in the completed PDF.
            final_page = toc_page_count + original_page

            # PyMuPDF document indices are zero-based.
            target_index = final_page - 1

            page = document.load_page(toc_page - 1)

            number = str(final_page)
            fontsize = 9

            number_width = pymupdf.get_text_length(
                number,
                fontname="helv",
                fontsize=fontsize,
            )

            right_edge = content_box.x1 - 3

            number_position = pymupdf.Point(
                right_edge - number_width,
                entry_rect.y0 + 10,
            )

            page.insert_text(
                number_position,
                number,
                fontname="helv",
                fontsize=fontsize,
                color=(0.48, 0.35, 0.17),
            )

            # Make the entire entry clickable.
            link_rect = pymupdf.Rect(
                content_box.x0,
                entry_rect.y0,
                content_box.x1,
                entry_rect.y1,
            )

            page.insert_link({
                "kind": pymupdf.LINK_GOTO,
                "from": link_rect,
                "page": target_index,
                "to": pymupdf.Point(0, 0),
            })

        # --------------------------------------------------
        # Phase 4: Create PDF reader bookmarks.
        # --------------------------------------------------

        document.set_toc([
            [
                1,
                title,
                toc_page_count + original_page,
            ]
            for _, title, original_page in toc_entries
        ])

        # --------------------------------------------------
        # Phase 5: PDF metadata, headers and footers.
        # --------------------------------------------------

        document.set_metadata({
            "title": "Codex Arcana - Datenschutzauskunft",
            "subject": (
                f"Benutzerkonto {payload['subject']['id']}"
            ),
            "creator": (
                "Codex Arcana privacy_export (lokal)"
            ),
        })

        total_pages = document.page_count

        for index in range(total_pages):
            page = document.load_page(index)

            page.draw_line(
                (42, 34),
                (page_box.width - 42, 34),
                color=(0.48, 0.35, 0.17),
                width=0.7,
            )

            page.insert_text(
                (42, 26),
                "CODEX ARCANA | Vertraulich",
                fontsize=8,
            )

            page.insert_text(
                (42, page_box.height - 26),
                (
                    f"Konto-ID {payload['subject']['id']} | "
                    f"Seite {index + 1} / {total_pages}"
                ),
                fontsize=8,
            )

        # --------------------------------------------------
        # Phase 6: Save.
        #
        # Works with a path or an io.BytesIO destination.
        # No temporary files are created.
        # --------------------------------------------------

        document.save(
            destination,
            garbage=3,
            deflate=True,
        )

    finally:
        document.close()
