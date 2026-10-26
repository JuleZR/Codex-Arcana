"""Local A4 privacy reports using PyMuPDF.

Architecture:
1. Render every report section exactly once.
2. Assemble bounded report blocks from private disk files.
3. Generate the table of contents after the report.
4. Insert the table of contents at the beginning.
5. Add final page numbers, clickable links, bookmarks and footers.

No repeated full-document layout or database mutations.
"""

import json
import logging
import re
import tempfile
from pathlib import Path
from time import perf_counter
from html import escape
from types import SimpleNamespace

import pymupdf

from .privacy_content import (
    CONTROLLER_LABELS, PROCESSING_LABELS, readable_value, recipient_payload,
    reference_names,
)
from .privacy_export import REDACTED
from .privacy_labels import PHRASES, german_label
from .privacy_performance import Performance


logger = logging.getLogger(__name__)
BLOCK_SIZE = 16000
PERSIST_BLOCKS = 32
SAVE_OPTIONS = {"garbage": 0, "deflate": False}
FIELD_LABELS = {
    "id": "Kennung", "username": "Benutzername", "email": "E-Mail-Adresse",
    "first_name": "Vorname", "last_name": "Nachname", "name": "Name",
    "is_active": "Konto aktiv", "is_staff": "Administrationszugang",
    "is_superuser": "Uneingeschränkte Administration",
    "date_joined": "Konto erstellt am", "last_login": "Letzte Anmeldung",
    "created_at": "Erstellt am", "updated_at": "Zuletzt geändert am",
    "owner": "Zugehöriges Konto / Charakter", "user": "Benutzerkonto",
    "character": "Charakter", "description": "Beschreibung",
    "notes": "Notizen", "data": "Gespeicherte Inhalte",
    "expire_date": "Ablaufzeit", "ip_address": "IP-Adresse",
    "user_agent": "Browserkennung", "attempt_time": "Anmeldezeitpunkt",
    "logout_time": "Abmeldezeitpunkt", "action_time": "Aktionszeitpunkt",
    "action_flag": "Aktionsart", "locked_out": "Zugang gesperrt",
    "failures_since_start": "Fehlgeschlagene Anmeldungen",
}


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


def display(value):
    """Convert values into readable, lossless text."""
    if value is None:
        return "Nicht gespeichert"
    if value is True:
        return "Ja"
    if value is False:
        return "Nein"
    if value == REDACTED:
        return "[Geschützter Inhalt]"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value) or "(leer)"


def readable_label(name, description=None):
    return ((description or {}).get("label")
            or FIELD_LABELS.get(name, PHRASES.get(name, german_label(name))))


def paragraphs(value):
    # Bound even a single giant JSON value or unbroken free-text field.
    encoder = json.JSONEncoder(ensure_ascii=False, indent=2)
    pieces = (encoder.iterencode(value)
              if isinstance(value, (dict, list)) else (display(value),))
    buffer = ''

    def paragraph(text):
        text = escape(text)
        text = re.sub(r"([^\s<>;&]{32})(?=[^\s<>;&])", r"\1 ", text)
        return '<p style="white-space:pre-wrap">' + text + '</p>'

    for piece in pieces:
        piece = piece.replace(REDACTED, "[Geschützter Inhalt]")
        for offset in range(0, len(piece), 1200):
            buffer += piece[offset:offset + 1200]
            while len(buffer) >= 1200:
                split = buffer.rfind(' ', 600, 1200)
                split = split + 1 if split >= 0 else 1200
                yield paragraph(buffer[:split])
                buffer = buffer[split:]
    if buffer:
        yield paragraph(buffer)


def rows(label, value):
    return '<h3>' + escape(label) + '</h3>' + ''.join(paragraphs(value))


def table(values):
    # Flowing paragraphs can split across pages; table rows cannot.
    return ''.join(rows(str(key), value) for key, value in values)


def bounded_blocks(parts):
    block = []
    size = 0
    for part in parts:
        if block and size + len(part) > BLOCK_SIZE:
            yield ''.join(block)
            block, size = [], 0
        block.append(part)
        size += len(part)
    if block:
        yield ''.join(block)


def sections(payload):
    payload = recipient_payload(payload)
    references = reference_names(payload)
    intro = table([
        ("Benutzerkonto-ID", payload["subject"]["id"]),
        ("Erstellt am", payload["generated_at"]),
        ("Auskunftsart", "Art. 15 DSGVO - Auskunft"
         if payload["mode"] == "access" else "Art. 20 - Datenübertragbarkeit"),
    ])
    intro += (
        '<p>Über das bezeichnete Konto werden personenbezogene Daten '
        'verarbeitet. Diese Kopie enthält die zugeordneten Daten sowie '
        'die Angaben über deren Verarbeitung.</p>'
        '<p>Kennungen dienen zur Zuordnung zusammengehöriger Einträge. '
        'Verknüpfte eigene Inhalte und Katalogbegriffe werden nach '
        'Möglichkeit mit ihrer Bezeichnung angegeben.</p>'
        '<p>Die Spielangaben beschreiben gespeicherte fiktionale Charaktere. '
        'Sie sind keine Feststellungen über Eigenschaften Ihrer realen Person.'
        '</p>'
    )
    if payload["document_status"] == "draft":
        intro += (
            '<p>Technischer Entwurf - nicht zur Weitergabe freigegeben.</p>')
    if payload["mode"] == "portability":
        intro += (
            '<p>Die Datenübertragbarkeit umfasst die gesondert ausgewählten, '
            'bereitgestellten Daten. Dieser PDF-Begleitbericht erläutert die '
            'maschinenlesbare Kopie im JSON-Format.</p>'
        )
    yield "account", "Zur Auskunft", intro

    def processing_parts():
        for key, value in payload["controller"].items():
            yield '<h3>' + escape(CONTROLLER_LABELS[key]) + '</h3>'
            yield from paragraphs(value)
        for key, label in PROCESSING_LABELS.items():
            value = payload.get("processing", {}).get(key)
            if value:
                yield '<h3>' + escape(label) + '</h3>'
                yield from paragraphs(value)
        yield '<h3>Betroffenenrechte</h3>'
        yield from paragraphs(payload["rights"])

    for body in bounded_blocks(processing_parts()):
        yield "processing", "Verarbeitung und Betroffenenrechte", body

    def category_parts():
        for item in payload["data_categories"]:
            yield '<h3>' + escape(item["category"]) + '</h3>'
            for key, label in (
                ("records", "Gespeicherte Einträge"),
                ("purpose", "Verwendung"), ("source", "Entstehung der Daten"),
                ("retention", "Speicherdauer"),
            ):
                if key in item:
                    yield '<p><b>' + label + '</b></p>'
                    yield from paragraphs(item[key])

    for body in bounded_blocks(category_parts()):
        yield "overview", "Kategorien Ihrer personenbezogenen Daten", body

    def service_parts():
        for service in payload["services"]:
            yield '<h3>' + escape(service["name"]) + '</h3>'
            for key, label in (
                ("recipients", "Empfänger"), ("data", "Übermittelte Daten"),
                ("purposes", "Zwecke"), ("retention", "Speicherdauer"),
                ("transfers", "Drittlandübermittlungen und Garantien"),
                ("safeguards", "Geeignete Garantien"),
                ("copy_source", "Kopie der Garantien / Bezugsquelle"),
            ):
                if key in service:
                    yield '<p><b>' + label + '</b></p>'
                    yield from paragraphs(service[key])

    for body in bounded_blocks(service_parts()):
        yield "services", "Tatsächlich eingesetzte Dienste und Empfänger", body

    def personal_value(value):
        if isinstance(value, dict):
            if not value:
                yield '<p>Keine Einträge.</p>'
            for name, child in value.items():
                yield from paragraphs(german_label(str(name)))
                yield from personal_value(child)
        elif isinstance(value, list):
            if not value:
                yield '<p>Keine Einträge.</p>'
            for number, child in enumerate(value, 1):
                if isinstance(child, (dict, list)):
                    yield f'<p>Eintrag {number}</p>'
                yield from personal_value(child)
        else:
            yield from paragraphs(value)

    for index, (key, category) in enumerate(payload["categories"].items()):
        title = PHRASES.get(
            key, german_label(str(category.get("label") or key)))
        if not category["records"]:
            continue

        def record_parts():
            yield (
                f'<p>{len(category["records"])} Einträge. Zeitangaben '
                'enthalten ihre Zeitzone. Kennungen ordnen zusammengehörige '
                'Einträge und Katalogbegriffe zu.</p>'
            )
            for number, record in enumerate(category["records"], 1):
                yield f'<h3>Eintrag {number}</h3>'
                for name, value in record.items():
                    meta = category["fields"].get(name, {})
                    label = readable_label(name, meta)
                    value = readable_value(value, meta, references)
                    if len(label) < 300:
                        yield '<p><b>' + escape(label) + '</b></p>'
                    else:
                        yield from paragraphs(label)
                    yield from personal_value(value)

        for body in bounded_blocks(record_parts()):
            yield f"category-{index}", title, body

    def file_parts():
        files = payload.get("files", [])
        if not files:
            yield '<p>Keine Dateien zugeordnet.</p>'
        for item in files:
            yield from paragraphs(item.get("member", ""))
            yield from paragraphs("Im ZIP enthalten" if item.get("status")
                                  == "included" else "Nicht beigefügt")
            if item.get("reason"):
                yield from paragraphs(item["reason"])

    for body in bounded_blocks(file_parts()):
        yield "files", "Zugeordnete Dateien", body

    def omission_parts():
        seen = set()
        for item in payload.get("omissions", []):
            text = ' · '.join(display(item[key]) for key in (
                "category", "record", "field", "reason") if key in item)
            if text not in seen:
                seen.add(text)
                yield from paragraphs(text)

    for body in bounded_blocks(omission_parts()):
        yield "omissions", "Auslassungen und Schwärzungen", body


def write_pdf(payload, destination, *, performance=None):
    """Generate an A4 report with a last-built table of contents.

    The data sections are rendered independently. The final
    document receives its table of contents only after all
    section page numbers are known.
    """
    metrics = performance or Performance()
    with metrics.phase("prepare"):
        payload = recipient_payload(payload)
    page_box = pymupdf.paper_rect("a4")
    content_box = page_box + (42, 52, -42, -48)

    def page_rectangles(*_):
        return page_box, content_box, None

    def title_html(title):
        return re.sub(r"([^\s<>;&]{24})(?=[^\s<>;&])", r"\1 ", escape(title))

    document = pymupdf.open()
    toc_entries = []
    started = perf_counter()
    previous_key = None
    # The HTTP/CLI caller supplies a private destination directory.
    parent = Path(destination).parent if isinstance(
        destination, (str, Path)) else None
    scratch = tempfile.TemporaryDirectory(prefix="pdf-block-", dir=parent)

    def render(story, positionfn=None):
        path = Path(scratch.name) / "block.pdf"
        path.touch(mode=0o600, exist_ok=True)
        # Own the file handle in Python: native writer references retained by
        # an exception traceback must not prevent Windows scratch cleanup.
        with path.open("wb") as stream:
            # A named file is interpreted as a path by DocumentWriter. Supply
            # its file operations explicitly so MuPDF uses the open stream.
            output = SimpleNamespace(
                write=stream.write, seek=stream.seek, tell=stream.tell,
                truncate=stream.truncate,
            )
            writer = pymupdf.DocumentWriter(output)
            try:
                story.write(writer, page_rectangles, positionfn=positionfn)
            finally:
                writer.close()
        return pymupdf.open(path)

    def persist_report():
        nonlocal document
        path = Path(scratch.name) / "assembled.pdf"
        if path.exists():
            document.saveIncr()
        else:
            path.touch(mode=0o600)
            document.save(path)
        document.close()
        document = pymupdf.open(path)

    try:
        # --------------------------------------------------
        # Phase 1: Render the actual report.
        #
        # Each section is rendered only once.
        # Each section starts on its own new page.
        # --------------------------------------------------

        iterator = iter(sections(payload))
        block_count = 0
        while True:
            block_started = perf_counter()
            with metrics.phase("pdf_content"):
                try:
                    key, title, body = next(iterator)
                except StopIteration:
                    break
                heading = (
                    f'<h2 class="section-start">{title_html(title)}</h2>'
                    if key != previous_key else '')
                story = pymupdf.Story(html=heading + body, user_css=CSS)
                section_document = render(story)

            try:
                if section_document.page_count == 0:
                    raise ValueError(
                        f"PDF-Abschnitt ohne Seiten: {key}"
                    )

                # Page numbers are 1-based for PDF bookmarks.
                start_page = document.page_count + 1

                with metrics.phase("pdf_merge", publish=False):
                    document.insert_pdf(
                        section_document,
                        links=False,
                        annots=False,
                    )

                if key != previous_key:
                    toc_entries.append((key, title, start_page))
                previous_key = key

            finally:
                section_document.close()
            # Keep completed PDF streams backed by disk rather than retaining
            # every inserted content stream on the native heap.
            block_count += 1
            if block_count % PERSIST_BLOCKS == 0:
                with metrics.phase("pdf_merge", publish=False):
                    persist_report()
            logger.info("privacy_pdf block_seconds=%.3f pages=%d",
                        perf_counter() - block_started, document.page_count)

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
            + ("<h1>Datenschutzauskunft</h1>" if payload["mode"] == "access"
               else "<h1>Datenübertragbarkeit</h1>")
            +
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
                ("Dokumentstatus", "Entwurf"
                 if payload["document_status"] == "draft"
                 else "Freigegebene Auskunft"),
            ])
            + "<h2>Inhaltsverzeichnis</h2>"
            + "".join(
                (
                    f'<p class="toc-entry" id="toc-entry-{index}">'
                    f"{title_html(title)}</p>"
                )
                for index, (_, title, _) in enumerate(toc_entries)
            )
        )

        with metrics.phase("pdf_toc"):
            toc_story = pymupdf.Story(html=toc_html, user_css=CSS)
            toc_document = render(toc_story, positionfn=record_toc)

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
            with metrics.phase("pdf_merge"):
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

        navigation_started = perf_counter()
        if metrics.progress:
            metrics.progress("pdf_navigation")
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
            "title": "Codex Arcana - " + (
                "Datenschutzauskunft" if payload["mode"] == "access"
                else "Datenübertragbarkeit"),
            "subject": (
                f"Benutzerkonto {payload['subject']['id']}"
            ),
            "creator": (
                "Codex Arcana"
            ),
        })

        total_pages = document.page_count

        for index in range(total_pages):
            page = document.load_page(index)
            decoration = page.new_shape()
            decoration.draw_line(
                (42, 34),
                (page_box.width - 42, 34),
            )
            decoration.finish(
                color=(0.48, 0.35, 0.17),
                width=0.7,
            )

            decoration.insert_text(
                (42, 26),
                "CODEX ARCANA | Vertraulich",
                fontsize=8,
            )

            decoration.insert_text(
                (42, page_box.height - 26),
                (
                    f"Konto-ID {payload['subject']['id']} | "
                    f"Seite {index + 1} / {total_pages}"
                ),
                fontsize=8,
            )
            decoration.commit()

        # --------------------------------------------------
        # Phase 6: Save.
        #
        # The production destination is a private file, never BytesIO.
        # --------------------------------------------------

        metrics.seconds["pdf_navigation"] = (
            perf_counter() - navigation_started)
        with metrics.phase("pdf_save"):
            # Only recipient text ever enters Story / PDF objects. No source
            # PDF, redaction overlay or removed original is retained here.
            document.save(destination, **SAVE_OPTIONS)
        size = (Path(destination).stat().st_size if isinstance(
            destination, (str, Path)) else destination.tell())
        metrics.pages = total_pages
        if performance is None:
            metrics.finish(pages=total_pages, size=size)
        return total_pages

    finally:
        document.close()
        scratch.cleanup()
        logger.info("privacy_pdf total_seconds=%.3f", perf_counter() - started)
