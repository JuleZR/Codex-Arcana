"""Superuser-only privacy search and private export jobs."""

import json
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.cache import patch_cache_control
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .models import Character
from .privacy_jobs import (
    cleanup_expired, job_download, owned_job, start_job,
)
from .privacy_export import (
    build_snapshot,
    missing_information,
    validate_review,
)


class SearchForm(forms.Form):
    query = forms.CharField(
        label="Benutzername, E-Mail oder Charaktername", min_length=1,
        max_length=200,
        widget=forms.TextInput(attrs={"size": 48, "autocomplete": "off"}),
    )


class ReviewStartForm(forms.Form):
    user_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    mode = forms.ChoiceField(label="Auskunftsart", choices=[
        ("access", "Art. 15 – Auskunft und Datenkopie"),
        ("portability", "Art. 20 – Datenübertragbarkeit"),
    ])
    request_verified = forms.BooleanField(
        label="Anfrage und Berechtigung der anfragenden Person geprüft")


class ExportForm(forms.Form):
    user_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    mode = forms.ChoiceField(label="Auskunftsart", choices=[
        ("access", "Art. 15 - Auskunft"),
        ("portability", "Art. 20 - Datenübertragbarkeit"),
    ])
    format = forms.ChoiceField(label="Dateiformat", initial="zip", choices=[
        ("zip", "ZIP mit PDF und JSON"), ("pdf", "PDF"), ("json", "JSON"),
    ])
    audience = forms.ChoiceField(
        label="Verwendungszweck", required=False, initial="recipient",
        choices=[("recipient", "Datenkopie für die betroffene Person"),
                 ("internal", "Interne Prüfgrundlage – nicht weitergeben")],
        help_text="Die interne JSON-/ZIP-Ausgabe enthält zusätzliche "
        "Prüfkandidaten und Freigabeprüfwerte.",
    )
    request_verified = forms.BooleanField(
        required=False,
        label="Anfrage und Berechtigung der anfragenden Person geprüft",
    )
    include_files = forms.BooleanField(
        required=False, label="Hochgeladene Dateien ins ZIP aufnehmen",
    )
    files_reviewed = forms.BooleanField(
        required=False,
        label="Angehängte Dateien auf Drittinformationen geprüft",
    )
    review_json = forms.CharField(
        required=False, max_length=131072,
        label="Prüfangaben (JSON, optional)",
        widget=forms.Textarea(attrs={"rows": 8, "cols": 70}),
        help_text="Schwärzungen, Verarbeitungsangaben, Art.-20-Feldauswahl "
        "oder Abschlussfreigabe im Format der Betreiberanleitung.",
    )

    def clean(self):
        cleaned = super().clean()
        cleaned["audience"] = cleaned.get("audience") or "recipient"
        if cleaned.get("format") == "pdf" and (
            cleaned.get("mode") == "portability"
            or cleaned["audience"] == "internal"
        ):
            self.add_error("format", "Hier JSON oder ZIP wählen; das ZIP "
                           "enthält zusätzlich den PDF-Begleitbericht.")
        try:
            review = json.loads(cleaned.get("review_json") or "{}")
            validate_review(review, cleaned.get("mode", "access"))
            cleaned["review"] = review
        except (ValueError, TypeError):
            self.add_error(
                "review_json", "Prüfangaben ungültig. Art. 20 benötigt eine "
                "geprüfte Kategorie-/Feldauswahl mit Rechtsgrundlage.",
            )
        if cleaned.get("include_files") and (
            cleaned.get("format") != "zip" or not cleaned.get("files_reviewed")
        ):
            self.add_error(
                "include_files",
                "Anhänge erfordern ZIP und eine Dateiprüfung.",
            )
        return cleaned


@sensitive_post_parameters()
@require_http_methods(["GET", "POST"])
def privacy_export_view(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied
    context = {
        **admin.site.each_context(request),
        "title": "DSGVO-Auskunft und Export",
        "search_form": SearchForm(),
        "export_form": None,
        "selected_user": None,
        "results": [],
    }
    status = 200
    if settings.DEBUG:
        context["error"] = "DSGVO-Werkzeug nur mit DEBUG=False verwenden."
        status = 503
    elif request.GET.get("review") or request.POST.get("workspace"):
        from .privacy_review_ui import workspace_view

        try:
            return workspace_view(request, request.GET.get("review")
                                  or request.POST["workspace"], context)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            context["error"] = (
                "Prüfstand oder Eingabe nicht verfügbar. Die Prüfung erneut "
                "öffnen oder mit der Benutzerauswahl neu beginnen.")
            status = 400
    elif request.method == "GET" and request.GET.get("job"):
        token = request.GET["job"]
        try:
            cleanup_expired()
            job = owned_job(token, request.user.pk)
            context["job_token"] = token
            context["job_ready"] = (job / "ready.json").is_file()
            if context["job_ready"]:
                metadata = json.loads((job / "ready.json").read_text(
                    encoding="utf-8"))
                context["job_internal"] = (
                    metadata.get("audience") == "internal")
        except (OSError, ValueError):
            context["error"] = (
                "Export fehlgeschlagen, abgelaufen oder bereits abgerufen.")
            status = 410
    elif request.method == "POST":
        action = request.POST.get("action")
        if action == "begin_review":
            form = context["export_form"] = ReviewStartForm(request.POST)
            if form.is_valid():
                try:
                    selected = get_user_model()._base_manager.get(
                        pk=form.cleaned_data["user_id"])
                    context["selected_user"] = selected
                    token = start_job(request.user.pk, {
                        "operation": "workspace", "user_id": selected.pk,
                        "mode": form.cleaned_data["mode"], "format": "json",
                        "audience": "internal", "review": {},
                        "include_files": False,
                    })
                    from .privacy_review_ui import url

                    return HttpResponseRedirect(url(token))
                except get_user_model().DoesNotExist:
                    form.add_error(
                        None, "Benutzerkonto nicht gefunden. "
                        "Bitte das Konto erneut auswählen.")
                except PermissionError:
                    form.add_error(
                        None, "Die private Exportablage ist nicht "
                        "beschreibbar. Die Schreibrechte der Ablage "
                        "müssen für das Anwendungskonto eingerichtet sein.")
                except (OSError, ValueError):
                    form.add_error(None, (
                        "Prüfung nicht gestartet. Eine laufende Prüfung "
                        "zuerst beenden; private Ablage prüfen."))
            elif "user_id" in form.errors:
                form.add_error(None, "Bitte zuerst ein Benutzerkonto "
                               "auswählen; die Kontozuordnung fehlt.")
            status = 400
        elif action == "fetch":
            try:
                return job_download(request.POST.get("job_token", ""),
                                    request.user.pk)
            except (OSError, ValueError, KeyError):
                context["error"] = (
                    "Export nicht bereit, abgelaufen oder bereits abgerufen.")
                status = 410
        elif action == "search":
            form = context["search_form"] = SearchForm(request.POST)
            if form.is_valid():
                query = form.cleaned_data["query"]
                matching_characters = Character._base_manager.filter(
                    name__icontains=query,
                ).values("owner_id")
                users = list(get_user_model()._base_manager.filter(
                    Q(username__icontains=query) | Q(email__icontains=query)
                    | Q(pk__in=matching_characters),
                ).order_by("username", "pk").values(
                    "pk", "username", "email", "is_active",
                )[:26])
                context["more_results"] = len(users) > 25
                context["results"] = users[:25]
                by_id = {user["pk"]: user for user in users[:25]}
                for user in by_id.values():
                    user["characters"] = []
                matches = Character._base_manager.filter(
                    owner_id__in=by_id, name__icontains=query,
                ).order_by("name", "pk").values(
                    "owner_id", "name", "is_archived",
                )[:101]
                for character in list(matches)[:100]:
                    owner = by_id[character["owner_id"]]
                    owner["characters"].append(character)
                context["searched"] = True
        elif action == "select":
            try:
                selected = get_user_model()._base_manager.get(
                    pk=int(request.POST.get("user_id", "")),
                )
                context["selected_user"] = selected
                context["export_form"] = ReviewStartForm(initial={
                    "user_id": selected.pk,
                })
            except (ValueError, get_user_model().DoesNotExist):
                context["error"] = "Benutzerkonto nicht gefunden."
                status = 400
        elif action in {"preview", "download"}:
            form = context["export_form"] = ExportForm(request.POST)
            if form.is_valid():
                options = form.cleaned_data
                try:
                    selected = get_user_model()._base_manager.get(
                        pk=options["user_id"],
                    )
                    context["selected_user"] = selected
                    if (action == "download"
                            and not options["request_verified"]):
                        form.add_error("request_verified",
                                       "Anfragenprüfung bestätigen.")
                    else:
                        if action == "download":
                            token = start_job(request.user.pk, options)
                            context["job_token"] = token
                            context["job_ready"] = False
                            context["job_internal"] = (
                                options["audience"] == "internal")
                            status = 202
                            payload = None
                        else:
                            payload, files = build_snapshot(
                                selected.pk, options["mode"],
                                options["review"],
                            )
                        if payload is not None:
                            context["preview"] = [
                                (key, len(category["records"]))
                                for key, category in
                                payload["categories"].items()
                            ]
                            context["attachment_count"] = len(files)
                            context["omission_count"] = len(
                                payload["omissions"])
                            context["missing_information"] = (
                                missing_information(payload))
                except Exception:
                    # Neither record contents nor exception details in logs.
                    context["error"] = (
                        "Auskunft nicht erstellt. Konto, Prüfangaben und "
                        "lokale Dateizuordnungen prüfen."
                    )
                    status = 400
            if form.errors:
                status = 400
        else:
            context["error"] = "Unbekannte Aktion."
            status = 400
    if not settings.DEBUG:
        from .privacy_review_ui import resume_review

        context["resume_review"] = resume_review(request.user.pk)
    response = TemplateResponse(
        request, "admin/privacy_export.html", context, status=status,
    )
    patch_cache_control(response, no_store=True, private=True)
    response["Referrer-Policy"] = "same-origin"
    return response


def install_privacy_admin():
    site = admin.site
    if getattr(site, "_privacy_export_installed", False):
        return
    original = site.get_urls

    @wraps(original)
    def get_urls():
        return [path(
            "privacy-export/", site.admin_view(privacy_export_view),
            name="privacy_export",
        )] + original()

    site.get_urls = get_urls
    site._privacy_export_installed = True
