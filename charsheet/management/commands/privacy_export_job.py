"""Isolated export worker and periodic janitor for private HTTP exports."""

import logging

from django.core.management.base import BaseCommand, CommandError

from charsheet.privacy_jobs import cleanup_expired, run_job, watch_job


class Command(BaseCommand):
    help = "DSGVO-Hintergrundexport oder Bereinigung abgelaufener Exporte."
    requires_system_checks = []

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--watch")
        group.add_argument("--job")
        group.add_argument("--cleanup", action="store_true")

    def handle(self, *args, **options):
        # Only these application loggers emit the measured, PII-free steps.
        # stderr is inherited from the service (journal/Gunicorn error log).
        loggers = [logging.getLogger(name) for name in (
            "charsheet.privacy_jobs", "charsheet.privacy_pdf",
            "charsheet.privacy_performance",
        )]
        previous = [(log, log.level, log.handlers[:], log.propagate)
                    for log in loggers]
        handler = logging.StreamHandler(self.stderr)
        handler.setFormatter(logging.Formatter("[privacy-export] %(message)s"))
        for log in loggers:
            log.handlers = [handler]
            log.setLevel(logging.INFO)
            log.propagate = False
        try:
            if options["cleanup"]:
                count = cleanup_expired()
                self.stdout.write(f"Abgelaufene Exporte entfernt: {count}")
            elif options["watch"]:
                watch_job(options["watch"])
            else:
                run_job(options["job"])
        except Exception:
            raise CommandError(
                "Exportvorgang fehlgeschlagen; private Ablage, freien "
                "Speicher und Prüfangaben kontrollieren."
            ) from None
        finally:
            for log, level, handlers, propagate in previous:
                log.handlers = handlers
                log.setLevel(level)
                log.propagate = propagate
            handler.close()
