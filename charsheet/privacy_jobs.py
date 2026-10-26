"""Private, expiring export jobs. No subject data is stored in the database."""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.utils.cache import patch_cache_control

from .management.commands.privacy_export import (
    attachments, private_directory, restrict_directory,
)
from .privacy_export import (
    apply_approval, build_snapshot,
)
from .privacy_content import json_document


logger = logging.getLogger(__name__)
JOB_NAME = re.compile(r"job-[a-f0-9]{32}\Z")
MARKER = {"tool": "codex-privacy-job", "version": 1}
TTL = 900


def private_root():
    default = (Path(tempfile.gettempdir()) / "codex-arcana-private-exports"
               if os.name == "nt"
               else Path("/var/lib/codex-arcana/privacy-exports"))
    path = private_directory(getattr(
        settings, "PRIVACY_EXPORT_TEMP_ROOT",
        os.environ.get("PRIVACY_EXPORT_TEMP_ROOT", str(default)),
    ))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or (os.name != "nt" and (
        path.stat().st_uid != os.getuid()
        or path.stat().st_mode & 0o077
    )):
        raise ValueError("Exportverzeichnis ist nicht privat.")
    restrict_directory(path)
    return path


def check_space(path):
    minimum = getattr(settings, "PRIVACY_EXPORT_MIN_FREE_BYTES", 256 * 1024**2)
    if shutil.disk_usage(path).free < minimum:
        raise OSError("Nicht genügend freier Speicher für den Export.")


def write_json(path, value):
    # O_EXCL and mode apply at creation, not only after sensitive bytes exist.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def job_path(token):
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise PermissionDenied
    path = private_root() / ("job-" + token)
    if path.is_symlink() or not path.is_dir():
        raise FileNotFoundError
    marker = json.loads((path / "marker.json").read_text(encoding="utf-8"))
    if marker != MARKER:
        raise PermissionDenied
    return path


def lock(path):
    """Keep an OS lock through streaming; release it on process death."""
    fd = os.open(path / "lease", os.O_RDWR | os.O_CREAT, 0o600)
    stream = os.fdopen(fd, "r+b")
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    return stream


def remove_job(path):
    """Only remove marked jobs directly inside the dedicated private root."""
    root = private_root()
    if (path.parent != root or not JOB_NAME.fullmatch(path.name)
            or path.is_symlink()):
        raise ValueError("Ungültiges Exportverzeichnis.")
    marker = json.loads((path / "marker.json").read_text(encoding="utf-8"))
    if marker != MARKER:
        raise ValueError("Exportmarkierung fehlt.")
    allowed = {"marker.json", "options.json", "owner.json", "lease",
               "ready.json", "ready.pending", "claimed", "report.pdf",
               "data.json", "audit.json", "export.zip", "source.json",
               "source.pending", "state.json", "state.pending", "preview.json",
               "preview.pending", "options.pending", "owner.pending",
               "precheck.json", "precheck.pending"}
    children = list(path.iterdir())
    for child in children:
        if child.is_symlink():
            raise ValueError("Verknüpfung im Exportverzeichnis.")
        if child.is_dir():
            if not child.name.startswith("pdf-block-"):
                raise ValueError("Unbekanntes Export-Unterverzeichnis.")
            if any(p.name not in {"block.pdf", "assembled.pdf"}
                   or p.is_symlink() or not p.is_file()
                   for p in child.iterdir()):
                raise ValueError("Unbekannte PDF-Arbeitsdatei.")
        elif child.name not in allowed or not child.is_file():
            raise ValueError("Unbekannte Exportdatei.")
    # Preserve the identifying marker until every sensitive file is gone.
    # A partial filesystem failure must remain eligible for a later retry.
    for child in children:
        if child.name == "marker.json":
            continue
        if child.is_dir():
            (child / "block.pdf").unlink(missing_ok=True)
            (child / "assembled.pdf").unlink(missing_ok=True)
            child.rmdir()
        else:
            child.unlink(missing_ok=True)
    (path / "marker.json").unlink()
    path.rmdir()


def cleanup_expired():
    """Run every minute from cron/systemd and on export requests."""
    root = private_root()
    count = 0
    for path in root.iterdir():
        if (not JOB_NAME.fullmatch(path.name) or path.is_symlink()
                or not path.is_dir()):
            continue
        lease = None
        try:
            marker_path = path / "marker.json"
            if json.loads(marker_path.read_text(encoding="utf-8")) != MARKER:
                continue
            owner_path = path / "owner.json"
            # Recover even a crash halfway through writing the owner metadata.
            expiry = marker_path.stat().st_mtime + TTL
            try:
                owner = json.loads(owner_path.read_text(encoding="utf-8"))
                expiry = owner["expires"]
            except (OSError, ValueError, KeyError):
                pass
            if expiry > time.time():
                continue
            lease = lock(path)
            # Windows cannot remove an open lease file.
            lease.close()
            remove_job(path)
            count += 1
        except (OSError, ValueError, KeyError):
            # Busy jobs/downloads and unknown files are left untouched.
            continue
        finally:
            if lease is not None:
                lease.close()
    return count


def start_job(owner_id, options):
    cleanup_expired()
    root = private_root()
    check_space(root)
    # Bound work per administrator; a pending job has no subject in its URL.
    live_count = 0
    for candidate in root.glob("job-*/owner.json"):
        if candidate.parent.is_symlink():
            continue
        owner = json.loads(candidate.read_text(encoding="utf-8"))
        if owner["expires"] > time.time():
            live_count += 1
            if owner["owner"] == owner_id:
                raise ValueError("Ein Export ist bereits vorgemerkt.")
    if live_count >= getattr(settings, "PRIVACY_EXPORT_MAX_JOBS", 4):
        raise ValueError("Exportkapazität ausgeschöpft.")
    token = uuid.uuid4().hex
    path = root / ("job-" + token)
    path.mkdir(mode=0o700)
    try:
        restrict_directory(path)
        write_json(path / "marker.json", MARKER)
        write_json(path / "owner.json", {
            "owner": owner_id, "expires": time.time() + (
                3600 if options.get("operation") == "workspace" else TTL),
        })
        write_json(path / "options.json", options)
        launch("--watch", token)
        return token
    except BaseException:
        if (path / "marker.json").exists():
            remove_job(path)
        else:
            path.rmdir()
        raise


def launch(action, token):
    command = [sys.executable, str(Path(settings.BASE_DIR) / "manage.py"),
               "privacy_export_job", action, token]
    kwargs = ({"creationflags": subprocess.CREATE_NO_WINDOW}
              if os.name == "nt" else {"start_new_session": True})
    return subprocess.Popen(
        command, cwd=settings.BASE_DIR, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=None,
        close_fds=True, **kwargs,
    )


def watch_job(token):
    """Expiry monitor independent of the renderer and HTTP worker."""
    path = job_path(token)
    owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
    try:
        worker = launch("--job", token)
    except BaseException:
        remove_job(path)
        raise
    try:
        while path.exists() and time.time() < owner["expires"]:
            worker.poll()  # Reap the renderer promptly after it exits.
            time.sleep(2)
            try:
                owner = json.loads((path / "owner.json").read_text(
                    encoding="utf-8"))
            except FileNotFoundError:
                break
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.wait()
        cleanup_expired()


def create_artifacts(payload, files, options, path):
    """Stream JSON, attachments and ZIP entries into private files."""
    started = time.monotonic()
    check_space(path)
    attachments(files)
    kind = options["format"]
    internal = options.get("audience") == "internal"
    archive = None
    try:
        if kind == "zip":
            archive = zipfile.ZipFile(path / "export.zip", "x",
                                      zipfile.ZIP_DEFLATED, allowZip64=True)
            if os.name != "nt":
                (path / "export.zip").chmod(0o600)
            if options["include_files"]:
                decisions = payload.get("content_review", {}).get(
                    "file_decisions", {})
                attachments([entry for entry in files
                             if entry[1]["member"] not in decisions], archive)
        apply_approval(payload, options["review"])
        if kind in {"pdf", "zip"}:
            from .privacy_pdf import write_pdf

            target = path / "report.pdf"
            target.touch(mode=0o600, exist_ok=False)
            write_pdf(payload, target)
        if kind in {"json", "zip"}:
            if kind == "zip" or not internal:
                write_json(path / "data.json", json_document(payload))
            if internal:
                write_json(path / "audit.json", json_document(payload, True))
        if archive is not None:
            check_space(path)
            archive.write(path / "report.pdf", "report.pdf")
            archive.write(path / "data.json", "data.json")
            if internal:
                archive.write(path / "audit.json", "audit.json")
    finally:
        if archive is not None:
            archive.close()
    if kind == "zip":
        (path / "report.pdf").unlink()
        (path / "data.json").unlink()
        (path / "audit.json").unlink(missing_ok=True)
    logger.info("privacy_export artifacts_seconds=%.3f",
                time.monotonic() - started)
    filenames = {"pdf": "report.pdf", "json": "data.json", "zip": "export.zip"}
    if kind == "json" and internal:
        return "audit.json"
    return filenames[kind]


def run_job(token):
    if settings.DEBUG:
        raise ValueError("Export benötigt DEBUG=False.")
    path = job_path(token)
    try:
        options = json.loads((path / "options.json").read_text(
            encoding="utf-8"))
    except Exception:
        remove_job(path)
        raise
    if options.get("operation") == "workspace":
        from .privacy_review_worker import run_workspace

        return run_workspace(token)
    lease = lock(path)
    # A stalled renderer cannot keep an OS lease forever. Abrupt termination
    # releases the lock; the scheduled janitor then removes its marked files.
    watchdog = threading.Timer(TTL, lambda: os._exit(1))
    watchdog.daemon = True
    watchdog.start()
    try:
        options = json.loads((path / "options.json").read_text(
            encoding="utf-8"))
        started = time.monotonic()
        payload, files = build_snapshot(
            options["user_id"], options["mode"], options["review"],
        )
        logger.info("privacy_export snapshot_seconds=%.3f",
                    time.monotonic() - started)
        filename = create_artifacts(payload, files, options, path)
        (path / "options.json").unlink()
        # Publish readiness only after all writers have closed.
        write_json(path / "ready.pending", {
            "filename": filename, "format": options["format"],
            "audience": options.get("audience", "recipient"),
        })
        (path / "ready.pending").replace(path / "ready.json")
    except BaseException:
        lease.close()
        remove_job(path)
        logger.warning("privacy_export failed")
        raise
    finally:
        watchdog.cancel()
        lease.close()


def owned_job(token, owner_id):
    path = job_path(token)
    owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
    if owner["owner"] != owner_id:
        raise PermissionDenied
    if owner["expires"] <= time.time():
        raise FileNotFoundError
    return path


class ExportFile:
    """FileResponse closes this handle on completion and on disconnect."""

    def __init__(self, path, filename, lease):
        self.path = path
        self.lease = lease
        self.stream = (path / filename).open("rb")
        self.deadline = None
        self.close_lock = threading.Lock()

    def arm_deadline(self):
        owner = json.loads((self.path / "owner.json").read_text(
            encoding="utf-8"))
        remaining = max(0.01, min(TTL, owner["expires"] - time.time()))
        self.deadline = threading.Timer(remaining, self.close)
        self.deadline.daemon = True
        self.deadline.start()

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def close(self):
        with self.close_lock:
            if self.stream.closed:
                return
            if self.deadline is not None:
                self.deadline.cancel()
            try:
                self.stream.close()
            finally:
                self.lease.close()
                try:
                    remove_job(self.path)
                except OSError:
                    logger.warning("privacy_export cleanup_deferred")


def job_download(token, owner_id):
    path = owned_job(token, owner_id)
    lease = lock(path)
    output = None
    claimed = False
    try:
        # Recheck after acquiring the lease: expiry may occur while waiting
        # between the initial authorization and opening the file handle.
        owned_job(token, owner_id)
        ready = json.loads((path / "ready.json").read_text(encoding="utf-8"))
        if ready.get("operation") == "workspace":
            raise ValueError("Der Prüfstand ist kein freigegebener Download.")
        kind = ready["format"]
        expected = {"pdf": {"report.pdf"}, "json": {"data.json", "audit.json"},
                    "zip": {"export.zip"}}
        if ready["filename"] not in expected[kind]:
            raise ValueError("Ungültige Exportdatei.")
        # O_EXCL makes downloads single-use, including concurrent requests.
        write_json(path / "claimed", {})
        claimed = True
        output = ExportFile(path, ready["filename"], lease)
        prefix = ("codex-arcana-pruefgrundlage"
                  if ready.get("audience") == "internal"
                  else "codex-arcana-auskunft")
        response = FileResponse(
            output, as_attachment=True,
            filename=f"{prefix}.{kind}", content_type={
                "pdf": "application/pdf", "json": "application/json",
                "zip": "application/zip",
            }[kind],
        )
        patch_cache_control(response, no_store=True, private=True)
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Accel-Buffering"] = "no"
        response["Referrer-Policy"] = "same-origin"
        output.arm_deadline()
        return response
    except BaseException:
        if output is not None:
            output.close()
        else:
            lease.close()
            if claimed:
                remove_job(path)
        raise
