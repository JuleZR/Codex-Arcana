"""Content-free timings and atomic status for private export workers."""

import json
import logging
import os
from contextlib import contextmanager
from time import perf_counter


logger = logging.getLogger(__name__)
STAGES = {
    "prepare": "Daten werden aufbereitet",
    "review": "Freigaben und Schwärzungen werden angewendet",
    "pdf_content": "PDF-Inhalt wird erstellt",
    "pdf_toc": "Inhaltsverzeichnis wird erstellt",
    "pdf_merge": "PDF-Dokumentteile werden zusammengeführt",
    "pdf_navigation": "Seitenzahlen und Verweise werden eingefügt",
    "pdf_save": "PDF wird gespeichert",
    "json": "JSON-Ausgabe wird erstellt",
    "zip": "ZIP-Archiv wird erstellt",
    "complete": "Export abgeschlossen",
}


def progress_label(path):
    try:
        options = path / "options.json"
        status = path / "progress.json"
        if (options.exists() and options.stat().st_mtime_ns
                > status.stat().st_mtime_ns):
            return STAGES["prepare"]
        value = json.loads(
            status.read_text(encoding="utf-8"))
        return STAGES.get(value.get("stage"), STAGES["prepare"])
    except (OSError, ValueError, AttributeError):
        return STAGES["prepare"]


def publish_progress(path, stage):
    # Never accept arbitrary text or export values in progress metadata.
    label = STAGES[stage]
    pending = path / "progress.pending"
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump({"stage": stage, "label": label}, stream)
    pending.replace(path / "progress.json")


class Performance:
    def __init__(self, progress=None):
        self.progress = progress
        self.started = perf_counter()
        self.seconds = {}
        self.stack = []
        self.pages = 0
        self.last_stage = None

    def record(self, stage, seconds):
        if stage not in STAGES:
            raise ValueError("Unknown export stage")
        self.seconds[stage] = self.seconds.get(stage, 0) + seconds
        if self.stack:
            self.stack[-1][1] += seconds

    @contextmanager
    def phase(self, stage, publish=True):
        if stage not in STAGES:
            raise ValueError("Unknown export stage")
        if publish and self.progress and self.last_stage != stage:
            self.progress(stage)
            self.last_stage = stage
        frame = [perf_counter(), 0]
        self.stack.append(frame)
        try:
            yield
        finally:
            elapsed = perf_counter() - frame[0]
            self.stack.pop()
            if self.stack:
                self.stack[-1][1] += elapsed
            self.seconds[stage] = self.seconds.get(stage, 0) + (
                elapsed - frame[1])

    def finish(self, *, pages=None, size=0):
        for stage, seconds in self.seconds.items():
            logger.info("privacy_export stage=%s seconds=%.6f", stage, seconds)
        logger.info(
            "privacy_export total_seconds=%.6f pages=%d bytes=%d",
            perf_counter() - self.started,
            self.pages if pages is None else pages, size,
        )
