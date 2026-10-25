"""Server-only privacy export; no routes, mail, or database mutations."""

import csv
import hashlib
import json
import os
import stat
import subprocess
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from charsheet.privacy_export import (
    apply_approval, build_snapshot, review_digest, snapshot_digest,
)


MARKER = ".codex-privacy-export.json"
ARTIFACTS = {"report.pdf", "data.json", "export.zip", MARKER}


def private_directory(path):
    """Deny web roots, repository paths, links and Windows junctions."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("Exportpfad muss absolut sein.")
    for part in (path, *path.parents):
        if part.is_symlink() or (
            hasattr(part, "is_junction") and part.is_junction()
        ):
            raise ValueError("Verknüpfungen im Exportpfad sind unzulässig.")
    path = path.resolve()
    roots = [settings.BASE_DIR, settings.MEDIA_ROOT]
    roots.extend(getattr(settings, "STATICFILES_DIRS", []))
    roots.append(getattr(settings, "STATIC_ROOT", None))
    for root in roots:
        if isinstance(root, (str, os.PathLike)) and root:
            if path.is_relative_to(Path(root).resolve()):
                raise ValueError(
                    "Exportpfad liegt in einem gesperrten Bereich."
                )
    return path


def restrict_directory(path):
    if os.name != "nt":
        path.chmod(0o700)
        return
    # Windows chmod does not restrict the DACL. Fail closed if ACL setup fails.
    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        check=True, capture_output=True, text=True,
    )
    sid = next(csv.reader(identity.stdout.strip().splitlines()))[1]
    if not sid.startswith("S-1-"):
        raise ValueError("Windows-Sicherheitskennung nicht ermittelbar.")
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r",
         f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
        check=True, capture_output=True,
    )


def write_json(path, payload):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    if os.name != "nt":
        path.chmod(0o600)


def remove_export(path):
    """Delete only a marked, flat export created by this command."""
    path = private_directory(path)
    if not path.name.startswith("privacy-export-"):
        raise ValueError("Kein Exportverzeichnis dieses Werkzeugs.")
    marker = path / MARKER
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("Exportmarkierung fehlt.")
    if json.loads(marker.read_text(encoding="utf-8")) != {
        "tool": "codex-privacy-export", "version": 1,
    }:
        raise ValueError("Ungültige Exportmarkierung.")
    children = list(path.iterdir())
    if any(
        child.name not in ARTIFACTS or not child.is_file()
        or child.is_symlink() for child in children
    ):
        raise ValueError("Unerwartete Dateien; Export manuell prüfen.")
    for child in children:
        if child != marker:
            child.unlink()
    marker.unlink()
    path.rmdir()


def local_attachment(stored):
    if not isinstance(stored.storage, FileSystemStorage):
        raise ValueError("Nichtlokale Dateispeicherung manuell prüfen.")
    root = Path(stored.storage.location).resolve()
    candidate = Path(stored.path)
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("Dateizuordnung außerhalb des lokalen Speichers.")
    for part in (candidate, *candidate.parents):
        if part == root:
            break
        if part.is_symlink() or (
            hasattr(part, "is_junction") and part.is_junction()
        ):
            raise ValueError("Verknüpfte Anhänge werden nicht exportiert.")
    return candidate


def attachments(files, archive=None):
    """Validate local files; stream bytes only when requested."""
    for stored, info in files:
        path = local_attachment(stored)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("Anhang ist keine reguläre Datei.")
            if archive is not None:
                digest = hashlib.sha256()
                count = 0
                with archive.open(
                    info["member"], "w", force_zip64=True,
                ) as out:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        count += len(chunk)
                        out.write(chunk)
                info.update(status="included", bytes=count,
                            sha256=digest.hexdigest())


class Command(BaseCommand):
    help = "Interne DSGVO-Auskunft: PDF, JSON oder ZIP (nur Serverzugriff)."
    # Keep database/system-check errors from dumping sensitive deployment data.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--mode", choices=["access", "portability"],
                            default="access")
        parser.add_argument("--format", choices=["pdf", "json", "zip"],
                            default="zip")
        parser.add_argument("--preview", action="store_true")
        parser.add_argument("--request-verified", action="store_true")
        parser.add_argument("--output-dir")
        parser.add_argument("--review-file")
        parser.add_argument("--include-files", action="store_true")
        parser.add_argument("--files-reviewed", action="store_true")
        parser.add_argument("--delete", metavar="EXPORT_DIRECTORY")

    def handle(self, *args, **options):
        # Debug SQL logging may include PII even though this command does
        # not log record contents. It must be disabled before the first query.
        if settings.DEBUG:
            raise CommandError("Werkzeug nur mit DEBUG=False ausführen.")
        output = None
        try:
            if options["delete"]:
                if options["user_id"] or options["output_dir"]:
                    raise ValueError("Löschung separat ausführen.")
                remove_export(options["delete"])
                self.stdout.write("Exportdateien entfernt.")
                return
            if options["user_id"] is None:
                raise ValueError("--user-id ist erforderlich.")
            if options["include_files"] and (
                options["format"] != "zip" or not options["files_reviewed"]
            ):
                raise ValueError(
                    "Anhänge erfordern --format zip und --files-reviewed."
                )
            if not options["preview"] and not options["request_verified"]:
                raise ValueError("Anfragenprüfung mit --request-verified "
                                 "bestätigen; dies ersetzt keinen Nachweis.")
            review = {}
            if options["review_file"]:
                review = json.loads(Path(options["review_file"]).read_text(
                    encoding="utf-8",
                ))
            payload, files = build_snapshot(
                options["user_id"], options["mode"], review,
            )
            if options["preview"]:
                for label, category in payload["categories"].items():
                    self.stdout.write(f"{label}: {len(category['records'])}")
                self.stdout.write(
                    f"Anhänge: {len(files)}; "
                    f"Auslassungen: {len(payload['omissions'])}. "
                    "Keine Exportdateien erstellt. Manuelle Prüfung nötig."
                )
                return
            if not options["output_dir"]:
                raise ValueError("--output-dir ist erforderlich.")
            parent = private_directory(options["output_dir"])
            if not parent.is_dir():
                raise ValueError("Privates Zielverzeichnis muss existieren.")
            output = parent / ("privacy-export-" + uuid.uuid4().hex)
            output.mkdir(mode=0o700)
            restrict_directory(output)
            write_json(output / MARKER, {
                "tool": "codex-privacy-export", "version": 1,
            })
            # Validate before writing reports, even without attachment copies.
            attachments(files)
            if options["format"] == "zip":
                with zipfile.ZipFile(
                    output / "export.zip", "x", zipfile.ZIP_DEFLATED,
                    allowZip64=True,
                ) as archive:
                    if options["include_files"]:
                        attachments(files, archive)
                    apply_approval(payload, review)
                    self.reports(payload, output, pdf=True, json_data=True)
                    archive.write(output / "report.pdf", "report.pdf")
                    archive.write(output / "data.json", "data.json")
                (output / "report.pdf").unlink()
                (output / "data.json").unlink()
            else:
                apply_approval(payload, review)
                self.reports(
                    payload, output, pdf=options["format"] == "pdf",
                    json_data=options["format"] == "json",
                )
            if os.name != "nt":
                for child in output.iterdir():
                    child.chmod(0o600)
            self.stdout.write(f"Export erstellt: {output}")
            self.stdout.write(
                payload["status"] + "."
            )
        except Exception as error:
            # No exception messages, paths, SQL, names or PII in diagnostics.
            try:
                if output is not None and output.exists():
                    for name in ARTIFACTS:
                        child = output / name
                        if child.is_file() and not child.is_symlink():
                            child.unlink()
                    output.rmdir()
            except OSError:
                raise CommandError(
                    "Export abgebrochen. Unvollständige Exportdateien im "
                    "privaten Zielordner manuell entfernen."
                ) from None
            if isinstance(error, ValueError):
                # Only explicit validation failures; parsing/library exceptions
                # can contain data and must not be displayed.
                raise CommandError(
                    "Export abgebrochen: Validierung fehlgeschlagen. "
                    "Parameter, Prüfdatei und Datenzuordnungen prüfen."
                ) from None
            raise CommandError(
                "Export unvollständig und entfernt. Konto-ID, lokale Anhänge, "
                "Datenbank und private Schreibrechte prüfen. "
                f"Fehlertyp: {type(error).__name__}."
            ) from None

    @staticmethod
    def reports(payload, output, pdf, json_data):
        if pdf:
            from charsheet.privacy_pdf import write_pdf

            write_pdf(payload, output / "report.pdf")
        if json_data:
            write_json(output / "data.json", {
                "snapshot_sha256": snapshot_digest(payload),
                "review_sha256": review_digest(payload),
                "data": payload,
            })
