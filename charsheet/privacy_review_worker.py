"""One bounded background worker serves the lifetime of a graphical review."""

import json
import logging
import os
import threading
import time

from django.core import signing
from django.db import close_old_connections

from .privacy_export import build_snapshot, missing_information, review_digest
from .privacy_jobs import (
    create_artifacts,
    job_path,
    lock,
    remove_job,
    write_json,
)
from .privacy_review import (
    compile_review,
    ensure_precheck,
    fields,
    friendly_missing,
    initial_state,
    progress,
)
from .privacy_rules import RULESET

logger = logging.getLogger("charsheet.privacy_jobs")
ARTIFACTS = (
    "report.pdf",
    "data.json",
    "audit.json",
    "export.zip",
    "preview.json",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value):
    pending = path.with_suffix(".pending")
    pending.unlink(missing_ok=True)
    write_json(pending, value)
    pending.replace(path)


def load_catalog(path, source):
    """Reuse signed classifications for this immutable source and rule set."""
    cache = None
    try:
        candidate = signing.loads(
            read_json(path / "precheck.json")["signed"],
            salt="privacy-precheck",
            max_age=3600,
        )
        if (
            candidate["ruleset"] == RULESET
            and candidate["source_fingerprint"] == source["source_fingerprint"]
            and isinstance(candidate["fields"], dict)
        ):
            cache = candidate
    except (OSError, ValueError, KeyError, TypeError, signing.BadSignature):
        pass
    catalog = list(fields(source, cache))
    if cache is None or len(cache["fields"]) != len(catalog):
        atomic_json(
            path / "precheck.json",
            {
                "signed": signing.dumps(
                    {
                        "ruleset": RULESET,
                        "source_fingerprint": source["source_fingerprint"],
                        "fields": {field.key: field.rule for field in catalog},
                    },
                    salt="privacy-precheck",
                    compress=True,
                )
            },
        )
    return catalog


def clear_artifacts(path):
    for name in ARTIFACTS:
        (path / name).unlink(missing_ok=True)


def perform(path, options):
    operation = options["operation"]
    if operation == "workspace":
        source, _ = build_snapshot(options["user_id"])
        catalog = load_catalog(path, source)
        state = initial_state(source, options["mode"], catalog)
        state["subject_id"] = options["user_id"]
        atomic_json(path / "source.json", source)
        atomic_json(path / "state.json", state)
    else:
        state = read_json(path / "state.json")
        source = read_json(path / "source.json")
        catalog = load_catalog(path, source)
        ensure_precheck(source, state, catalog)
        review = compile_review(source, state, catalog)
        if operation == "preview":
            review.pop("approval", None)
            if state["mode"] == "portability":
                current, _ = build_snapshot(state["subject_id"])
            else:
                current = None
            payload, files = build_snapshot(
                state["subject_id"], state["mode"], review
            )
            original = current or payload
            if original.get("source_fingerprint") != source.get(
                "source_fingerprint"
            ):
                if current is None:
                    current, _ = build_snapshot(state["subject_id"])
                fresh = initial_state(
                    current, state["mode"], load_catalog(path, current)
                )
                fresh.update(
                    subject_id=state["subject_id"],
                    version=state["version"] + 1,
                    information=state["information"],
                    output=state["output"],
                    supplements=state["supplements"],
                    error="Der Datenbestand hat sich geändert. "
                    "Bitte die aktualisierten Daten erneut prüfen.",
                )
                atomic_json(path / "source.json", current)
                atomic_json(path / "state.json", fresh)
            else:
                clear_artifacts(path)
                output = {**state["output"], "review": review}
                create_artifacts(payload, files, output, path)
                atomic_json(path / "preview.json", payload)
                state.update(
                    busy=False,
                    step=5,
                    error="",
                    preview_digest=review_digest(payload),
                    preview_version=state["version"],
                    approval=None,
                )
                state["missing"] = friendly_missing(
                    source, missing_information(payload), catalog
                )
                remaining = progress(source, state, catalog)["open"]
                if remaining:
                    state["missing"].append(
                        f"Noch {remaining} ungeprüfte Datenfelder."
                    )
                atomic_json(path / "state.json", state)
        elif operation == "export":
            if (
                not state.get("approval")
                or state["missing"]
                or state["preview_version"] != state["version"]
            ):
                raise ValueError("Keine gültige Freigabe.")
            clear_artifacts(path)
            payload, files = build_snapshot(
                state["subject_id"], state["mode"], review
            )
            filename = create_artifacts(
                payload, files, {**state["output"], "review": review}, path
            )
            state.update(busy=False, step=6)
            atomic_json(path / "state.json", state)
            owner = read_json(path / "owner.json")
            owner["expires"] = min(owner["expires"], time.time() + 900)
            atomic_json(path / "owner.json", owner)
            atomic_json(
                path / "ready.json",
                {
                    "operation": "export",
                    "filename": filename,
                    "format": state["output"]["format"],
                    "audience": state["output"]["audience"],
                },
            )
            return True
        else:
            raise ValueError("Unbekannter Prüfschritt.")
    atomic_json(path / "ready.json", {"operation": "workspace"})
    return False


def run_workspace(token):
    path = job_path(token)
    expiry = read_json(path / "owner.json")["expires"]
    watchdog = threading.Timer(
        max(1, expiry - time.time()), lambda: os._exit(1)
    )
    watchdog.daemon = True
    watchdog.start()
    try:
        while path.exists() and time.time() < expiry:
            if not (path / "options.json").is_file():
                time.sleep(0.5)
                continue
            try:
                lease = lock(path)
            except OSError:
                time.sleep(0.1)
                continue
            try:
                options = read_json(path / "options.json")
                (path / "options.json").unlink()
                if perform(path, options):
                    return
            except Exception:
                logger.warning("privacy_review operation_failed")
                lease.close()
                remove_job(path)
                return
            finally:
                lease.close()
                close_old_connections()
    finally:
        watchdog.cancel()
