"""Superuser-only privacy search and memory-only export downloads."""

import io
import json
import zipfile
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.cache import patch_cache_control
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .management.commands.privacy_export import attachments
from .models import Character
from .privacy_export import (
    apply_approval,
    build_snapshot,
    review_digest,
    snapshot_digest,
    validate_review,
)


FORMATS = {
    "pdf": "application/pdf",
    "json": "application/json",
    "zip": "application/zip",
}


class SearchForm(forms.Form):
    query = forms.CharField(
        label="Benutzername, E-Mail oder Charaktername", min_length=1,
        max_length=200,
        widget=forms.TextInput(attrs={"size": 48, "autocomplete": "off"}),
    )


class ExportForm(forms.Form):
    user_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    mode = forms.ChoiceField(label="Auskunftsart", choices=[
        ("access", "Art. 15 - Auskunft"),
        ("portability", "Art. 20 - Datenübertragbarkeit"),
    ])
    format = forms.ChoiceField(label="Dateiformat", initial="zip", choices=[
        ("zip", "ZIP mit PDF und JSON"), ("pdf", "PDF"), ("json", "JSON"),
    ])
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


def download(payload, files, options):
    """Never use temporary files, spools, storage or export directories."""
    kind = options["format"]
    output = io.BytesIO()
    try:
        attachments(files)
        if kind == "zip":
            with zipfile.ZipFile(
                output, "w", zipfile.ZIP_DEFLATED, allowZip64=True,
            ) as archive:
                if options["include_files"]:
                    attachments(files, archive)
                apply_approval(payload, options["review"])
                with io.BytesIO() as pdf:
                    from .privacy_pdf import write_pdf

                    write_pdf(payload, pdf)
                    archive.writestr("report.pdf", pdf.getvalue())
                archive.writestr("data.json", json_bytes(payload))
        else:
            apply_approval(payload, options["review"])
            if kind == "pdf":
                from .privacy_pdf import write_pdf

                write_pdf(payload, output)
            else:
                output.write(json_bytes(payload))
        output.seek(0)
        response = FileResponse(
            output, as_attachment=True, content_type=FORMATS[kind],
            filename=f"codex-arcana-auskunft.{kind}",
        )
        patch_cache_control(response, no_store=True, private=True)
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Accel-Buffering"] = "no"
        response["Referrer-Policy"] = "no-referrer"
        return response
    except Exception:
        output.close()
        raise


def json_bytes(payload):
    return json.dumps({
        "snapshot_sha256": snapshot_digest(payload),
        "review_sha256": review_digest(payload),
        "data": payload,
    }, ensure_ascii=False, indent=2).encode("utf-8")


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
    elif request.method == "POST":
        action = request.POST.get("action")
        if action == "search":
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
                context["export_form"] = ExportForm(initial={
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
                        payload, files = build_snapshot(
                            selected.pk, options["mode"], options["review"],
                        )
                        if action == "download":
                            return download(payload, files, options)
                        context["preview"] = [
                            (key, len(category["records"]))
                            for key, category in payload["categories"].items()
                        ]
                        context["attachment_count"] = len(files)
                        context["omission_count"] = len(payload["omissions"])
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
    response = TemplateResponse(
        request, "admin/privacy_export.html", context, status=status,
    )
    patch_cache_control(response, no_store=True, private=True)
    response["Referrer-Policy"] = "no-referrer"
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
