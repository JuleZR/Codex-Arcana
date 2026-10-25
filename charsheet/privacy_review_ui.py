"""Graphical workflow with server-checked decisions and identifiers."""

import copy
import time

from django import forms
from django.core import signing
from django.forms import formset_factory
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control

from .legal import FIELD_LABELS as LEGAL_LABELS
from .privacy_content import (
    PROTECTED,
    SERVICE_LABELS,
    recipient_payload,
    sanitize,
)
from .privacy_export import apply_approval, review_digest
from .privacy_jobs import (
    job_download,
    lock,
    owned_job,
    private_root,
    remove_job,
)
from .privacy_labels import german_label
from .privacy_review import (
    compile_review,
    decision_value,
    field_token,
    fields,
    find_field,
    included,
    invalidate,
    leaves,
    portable_categories,
    progress,
)
from .privacy_review_forms import (
    ApprovalForm,
    ControllerForm,
    FieldForm,
    FileForm,
    OutputForm,
    ProcessingForm,
    ServiceForm,
    SupplementForm,
    SupplementValueForm,
    coverage_forms,
)
from .privacy_review_worker import atomic_json, read_json

PAGE_SIZE = 8
LEAF_PAGE_SIZE = 30


def page_items(items, page, size):
    start = page * size
    end = start + size
    return items[start:end]


def resume_review(owner_id):
    try:
        for path in private_root().glob("job-*/owner.json"):
            owner = read_json(path)
            if owner["owner"] == owner_id and owner["expires"] > time.time():
                if (path.parent / "state.json").exists():
                    return url(path.parent.name[4:])
    except (OSError, ValueError, KeyError):
        pass
    return None


def url(token, step=3, **params):
    from urllib.parse import urlencode

    return (
        reverse("admin:privacy_export")
        + "?"
        + urlencode({"review": token, "step": step, **params})
    )


def render(request, context, status=200):
    response = TemplateResponse(
        request, "admin/privacy_export.html", context, status=status
    )
    patch_cache_control(response, no_store=True, private=True)
    response["Referrer-Policy"] = "same-origin"
    return response


def caption(value):
    if isinstance(value, (dict, list)):
        return "Strukturierte Angaben – einzeln öffnen und prüfen"
    if value is None:
        return "Nicht gespeichert"
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    return str(value) or "Leer"


def preview_information(public):
    sections = []
    for key, title, form in (
        ("controller", "Verantwortlicher und Kontakt", ControllerForm()),
        ("processing", "Angaben zur Verarbeitung", ProcessingForm()),
    ):
        sections.append(
            (
                title,
                [
                    (form.fields[name].label, value)
                    for name, value in public[key].items()
                    if name in form.fields
                ],
            )
        )
    labels = ServiceForm().fields
    for service in public["services"]:
        sections.append(
            (
                service["name"],
                [
                    (
                        (
                            "Übermittlungen"
                            if name == "transfers"
                            else labels[name].label
                        ),
                        value,
                    )
                    for name, value in service.items()
                    if name == "transfers" or name in labels
                ],
            )
        )
    sections.append(
        (
            "Rechte der betroffenen Person",
            [
                ("Hinweis", public["rights"]),
            ],
        )
    )
    return sections


def step_number(request, state):
    try:
        return max(
            2, min(6, int(request.GET.get("step", state.get("step", 3))))
        )
    except ValueError:
        return 3


def information(source, state, data=None):
    info = state["information"]
    controller = ControllerForm(
        data, prefix="controller", initial=info["controller"]
    )
    processing = ProcessingForm(
        data, prefix="processing", initial=info["processing"]
    )
    coverage = coverage_forms(data, info["coverage"])
    services = []
    legal = source["legal_configuration"]
    for key, label in SERVICE_LABELS.items():
        entry = info["services"].get(key, {})
        initial = copy.deepcopy(entry)
        transfer = initial.pop("transfers", {})
        if transfer:
            initial.update(
                transfer_applies="yes" if transfer["applies"] else "no",
                **{k: v for k, v in transfer.items() if k != "applies"},
            )
        stem = {"hosting": "hosting", "email": "email"}.get(key)
        if stem:
            initial.setdefault("recipients", legal.get(stem + "_provider", ""))
            initial.setdefault("details", legal.get(stem + "_location", ""))
            initial.setdefault("retention", legal.get(stem + "_retention", ""))
        initial = {
            k: v
            for k, v in initial.items()
            if not isinstance(v, str) or "Nicht konfiguriert;" not in v
        }
        services.append(
            (
                key,
                label,
                ServiceForm(data, prefix="service-" + key, initial=initial),
            )
        )
    facts = [
        (LEGAL_LABELS[key], value)
        for key, value in legal.items()
        if key in LEGAL_LABELS
        and value
        and not value.startswith("Nicht konfiguriert;")
        and key not in {"operator_name", "address", "email"}
    ]
    return {
        "controller_form": controller,
        "processing_form": processing,
        "coverage_forms": coverage,
        "service_forms": services,
        "operator_facts": facts,
    }


def save_information(bundle, state):
    all_forms = [bundle["controller_form"], bundle["processing_form"]]
    all_forms += [entry[2] for entry in bundle["coverage_forms"]]
    all_forms += [entry[2] for entry in bundle["service_forms"]]
    valid = [form.is_valid() for form in all_forms]
    if not all(valid):
        return False
    state["information"] = {
        "controller": {
            k: v for k, v in all_forms[0].cleaned_data.items() if v
        },
        "processing": {
            k: v for k, v in all_forms[1].cleaned_data.items() if v
        },
        "coverage": {
            key: form.cleaned_data
            for key, _, form in bundle["coverage_forms"]
            if form.cleaned_data["checked"]
        },
        "services": {
            key: form.review_entry()
            for key, _, form in bundle["service_forms"]
            if form.cleaned_data["status"]
        },
    }
    return True


def output_forms(source, state, data=None):
    output = OutputForm(
        data, prefix="output", mode=state["mode"], initial=state["output"]
    )
    files = []
    for index, item in enumerate(source["files"]):
        entry = state["file_decisions"].get(item["member"], {})
        if state.get("file_choices", {}).get(item["member"]) == "include":
            entry = {"action": "include"}
        files.append(
            (
                item,
                f"Dateianhang {index + 1}",
                FileForm(data, prefix=f"file-{index}", initial=entry),
            )
        )
    return output, files


def save_output(output, file_forms, state):
    valid = [output.is_valid()] + [
        form.is_valid() for _, _, form in file_forms
    ]
    if not all(valid):
        return False
    choices = {
        item["member"]: form.cleaned_data["action"]
        for item, _, form in file_forms
    }
    include = "include" in choices.values()
    if include and output.cleaned_data["format"] != "zip":
        output.add_error("format", "Dateianhänge erfordern das ZIP-Format.")
        return False
    if include and not output.cleaned_data["files_reviewed"]:
        output.add_error("files_reviewed", "Dateiprüfung bestätigen.")
        return False
    state["output"] = {**output.cleaned_data, "include_files": include}
    state["file_choices"] = choices
    state["file_decisions"] = {
        item["member"]: form.cleaned_data
        for item, _, form in file_forms
        if form.cleaned_data["action"] not in {"", "include"}
    }
    return True


def selection_form(source, state, category, data=None):
    content = portable_categories(source).get(category)
    if content is None:
        return None, []
    mapping = []
    choices = []
    labels = recipient_payload(source)["categories"][category]["fields"]
    for name, meta in content["fields"].items():
        original = meta.get("source_field", name)
        if original == "id":
            continue
        mapping.append(original)
        choices.append(
            (
                str(len(mapping) - 1),
                labels.get(name, {}).get("label", german_label(name)),
            )
        )
    rule = state["portability"].get(category, {})
    initial = {
        "enabled": bool(rule),
        "basis": rule.get("basis"),
        "provided": rule.get("provided_by_subject"),
        "fields": [
            str(i)
            for i, name in enumerate(mapping)
            if name in rule.get("fields", [])
        ],
    }
    form = forms.Form(data, prefix="selection", initial=initial)
    form.fields["enabled"] = forms.BooleanField(
        label="Kategorie aufnehmen", required=False
    )
    form.fields["basis"] = forms.ChoiceField(
        label="Geprüfte Rechtsgrundlage",
        required=False,
        choices=[
            ("", "Bitte wählen"),
            ("contract", "Vertrag"),
            ("consent", "Einwilligung"),
        ],
    )
    form.fields["provided"] = forms.BooleanField(
        label="Bereitstellung durch die betroffene Person geprüft",
        required=False,
    )
    form.fields["fields"] = forms.MultipleChoiceField(
        label="Zu übertragende Datenfelder",
        required=False,
        choices=choices,
        widget=forms.CheckboxSelectMultiple,
    )
    return form, mapping


def selected_category(source, request):
    choices = [
        (key, value["label"])
        for key, value in recipient_payload(source)["categories"].items()
        if value["records"]
    ]
    if any(field.category == "additional" for field in fields(source)):
        choices.append(("additional", "Weitere zu prüfende Inhalte"))
    try:
        index = int(
            request.POST.get("category", request.GET.get("category", 0))
        )
    except ValueError:
        raise ValueError("Ungültige Kategorie.") from None
    if not 0 <= index < len(choices):
        raise ValueError("Kategorie ist nicht verfügbar.")
    return choices, index


def edit_field(request, token, source, state, field, context):
    decision = state["decisions"].get(field.key, {})
    initial = {
        "action": decision.get("action", "include"),
        "reason": decision.get("reason", ""),
        "text": decision.get("text", caption(field.value)),
        "as_text": decision.get("as_text", False),
    }
    data = request.POST if request.method == "POST" else None
    form = FieldForm(data, field=field, prefix="field", initial=initial)
    signed = (
        request.POST.get("field_ref")
        or request.GET.get("edit")
        or field_token(token, source, field)
    )
    structured = isinstance(field.value, (dict, list))
    try:
        page = max(0, int(request.GET.get("leaf_page", 0)))
    except ValueError:
        page = 0
    entries = list(leaves(field.value)) if structured else []
    shown = page_items(entries, page, LEAF_PAGE_SIZE)
    previous = {
        tuple(edit["path"]): edit["text"] for edit in decision.get("edits", [])
    }
    leaf_rows = []
    for index, (path, value) in enumerate(shown):
        label = " › ".join(
            f"Eintrag {p + 1}" if isinstance(p, int) else german_label(p)
            for p in path
        )
        leaf_rows.append(
            {
                "label": label,
                "original": caption(value),
                "value": (
                    data.get(f"leaf-{index}-value")
                    if data is not None
                    else previous.get(path, caption(value))
                ),
                "protected": value == PROTECTED,
                "ref": signing.dumps([signed, path], salt="privacy-leaf"),
                "index": index,
            }
        )
    if data is not None and form.is_valid():
        action = form.cleaned_data["action"]
        if action == "reset":
            state["decisions"].pop(field.key, None)
        else:
            entry = {"action": action, "reason": form.cleaned_data["reason"]}
            if (
                action == "partial"
                and structured
                and form.cleaned_data["as_text"]
            ):
                entry.update(
                    as_text=True,
                    text=form.cleaned_data["text"] or "[Geschwärzt]",
                )
            elif action == "partial" and structured:
                edits = copy.deepcopy(decision.get("edits", []))
                try:
                    count = int(data.get("leaf_count", 0))
                    if count < 0 or count > LEAF_PAGE_SIZE:
                        raise ValueError
                    for index in range(count):
                        ref, path = signing.loads(
                            data.get(f"leaf-{index}-ref", ""),
                            salt="privacy-leaf",
                            max_age=3600,
                        )
                        if ref != signed:
                            raise ValueError
                        path = tuple(path)
                        original = field.value
                        for part in path:
                            original = original[part]
                        text = data.get(f"leaf-{index}-value", "")
                        if original == PROTECTED:
                            continue
                        edits = [
                            edit
                            for edit in edits
                            if tuple(edit["path"]) != path
                        ]
                        if text != caption(original):
                            edits.append(
                                {
                                    "path": list(path),
                                    "text": text or "[Geschwärzt]",
                                }
                            )
                    entry["edits"] = edits
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    IndexError,
                    signing.BadSignature,
                ):
                    form.add_error(
                        None,
                        "Ein Teilfeld wurde verändert oder ist abgelaufen.",
                    )
            elif action == "partial":
                entry["text"] = form.cleaned_data["text"] or "[Geschwärzt]"
            if not form.errors:
                value = decision_value(field, entry)
                if sanitize(value) != value:
                    form.add_error(
                        None,
                        "Zugangsdaten dürfen nicht freigegeben werden.",
                    )
                else:
                    state["decisions"][field.key] = entry
        if not form.errors:
            invalidate(state)
            return True
    context.update(
        editor=field,
        field_form=form,
        edit_ref=signed,
        structured=structured,
        leaf_rows=leaf_rows,
        leaf_page=page,
        leaf_previous=page - 1 if page else None,
        leaf_next=(
            page + 1 if (page + 1) * LEAF_PAGE_SIZE < len(entries) else None
        ),
        leaf_count=len(shown),
        original_text=caption(field.value),
        current_text=(
            caption(decision_value(field, decision))
            if decision
            else caption(field.value)
        ),
    )
    return False


def workspace_view(request, token, context):
    path = owned_job(token, request.user.pk)
    context.update(workspace_token=token, workflow=True)
    context["review_links"] = [
        (number, label, url(token, number))
        for number, label in (
            (2, "Auskunftsart"),
            (3, "Daten prüfen"),
            (4, "Verarbeitung"),
            (5, "Vorschau & Freigabe"),
            (6, "Export"),
        )
    ]
    try:
        lease = lock(path)
    except OSError:
        context.update(review_busy=True, refresh_url=url(token))
        return render(request, context, 202)
    try:
        if not (path / "state.json").exists():
            context.update(review_busy=True, refresh_url=url(token))
            return render(request, context, 202)
        source = read_json(path / "source.json")
        state = read_json(path / "state.json")
        step = step_number(request, state)
        choices, category_index = selected_category(source, request)
        category = choices[category_index][0]
        context.update(
            state=state,
            step=step,
            category_index=category_index,
            expires=round(
                max(0, read_json(path / "owner.json")["expires"] - time.time())
                / 60
            ),
            subject_name=next(
                (
                    r.get("username", "Benutzerkonto")
                    for c in source["categories"].values()
                    for r in c["records"]
                    if "username" in r
                ),
                "Benutzerkonto",
            ),
        )
        context["progress"] = progress(source, state)
        action = (
            request.POST.get("action") if request.method == "POST" else None
        )
        if action and action not in {
            "save_mode",
            "save_information",
            "save_selection",
            "accept_category",
            "save_field",
            "save_output",
            "create_preview",
            "approve",
            "create_export",
            "add_supplement",
            "remove_supplement",
            "save_supplement",
            "cancel_review",
            "download_final",
            "filter",
        }:
            raise ValueError("Unbekannte Aktion.")
        ready = (
            read_json(path / "ready.json")
            if (path / "ready.json").exists()
            else {}
        )
        if ready.get("operation") == "export":
            if action == "download_final":
                lease.close()
                return job_download(token, request.user.pk)
            context.update(export_ready=True, step=6)
            return render(request, context)
        if state["busy"]:
            context.update(
                review_busy=True, refresh_url=url(token, state["step"])
            )
            return render(request, context, 202)
        if action and str(state["version"]) != request.POST.get("version"):
            context["error"] = (
                "Dieser Prüfstand ist veraltet. Bitte die Seite neu laden."
            )
            return render(request, context, 409)
        if action == "cancel_review":
            lease.close()
            remove_job(path)
            return HttpResponseRedirect(reverse("admin:privacy_export"))
        changed = False
        target_step = step
        if action == "save_mode":
            mode = request.POST.get("mode")
            if mode not in {"access", "portability"}:
                raise ValueError("Auskunftsart ungültig.")
            state["mode"] = mode
            changed, target_step = True, 3
        if action == "save_information":
            bundle = information(source, state, request.POST)
            context.update(bundle)
            changed = save_information(bundle, state)
            if not changed:
                context.update(
                    step=4, error="Bitte die markierten Angaben korrigieren."
                )
        if action == "save_selection":
            form, mapping = selection_form(
                source, state, category, request.POST
            )
            if form is None:
                raise ValueError(
                    "Kategorie gehört nicht zur Datenübertragbarkeit."
                )
            if form.is_valid():
                data = form.cleaned_data
                if data["enabled"] and (
                    not data["basis"]
                    or not data["provided"]
                    or not data["fields"]
                ):
                    form.add_error(
                        None,
                        "Grundlage, Bereitstellung und Felder bestätigen.",
                    )
                elif data["enabled"]:
                    state["portability"][category] = {
                        "basis": data["basis"],
                        "provided_by_subject": True,
                        "fields": [
                            mapping[int(value)] for value in data["fields"]
                        ],
                    }
                    changed = True
                else:
                    state["portability"].pop(category, None)
                    changed = True
            context["selection_form"] = form
            if form.errors:
                context["error"] = "Bitte die Feldauswahl korrigieren."
        if action == "accept_category":
            for field in fields(source):
                if (
                    field.category == category
                    and included(field, state)
                    and not field.candidate
                    and field.key not in state["decisions"]
                ):
                    state["decisions"][field.key] = {
                        "action": "include",
                        "reason": "",
                    }
            changed = True
        signed = request.POST.get("field_ref") or request.GET.get("edit")
        if action == "save_field" and not signed:
            raise ValueError("Kein gültiges Datenfeld ausgewählt.")
        if signed:
            field = find_field(token, source, signed)
            saved = edit_field(request, token, source, state, field, context)
            if saved:
                atomic_json(path / "state.json", state)
                return HttpResponseRedirect(
                    url(token, 3, category=category_index)
                )
        if action in {"save_output", "create_preview"}:
            output, files = output_forms(source, state, request.POST)
            context.update(output_form=output, file_forms=files)
            changed = save_output(output, files, state)
            if changed:
                invalidate(state)
                changed = False
                if action == "create_preview":
                    try:
                        compile_review(source, state)
                    except ValueError:
                        context["error"] = (
                            "Die Auswahl ist unvollständig. Feldauswahl "
                            "und Prüfentscheidungen prüfen."
                        )
                    else:
                        state.update(busy=True, step=5)
                        atomic_json(
                            path / "options.json", {"operation": "preview"}
                        )
        if action == "approve":
            form = ApprovalForm(request.POST)
            context["approval_form"] = form
            if form.is_valid():
                if (
                    state["preview_version"] != state["version"]
                    or state["missing"]
                    or progress(source, state)["open"]
                ):
                    form.add_error(
                        None,
                        "Prüfung abschließen und Vorschau erstellen.",
                    )
                else:
                    preview = read_json(path / "preview.json")
                    approval = {
                        "subject_id": state["subject_id"],
                        "review_sha256": review_digest(preview),
                        "reviewed_at": timezone.now().isoformat(),
                    }
                    review = compile_review(source, state)
                    review["approval"] = approval
                    apply_approval(preview, review)
                    state.update(approval=approval, step=6)
        if action == "create_export":
            if (
                not state.get("approval")
                or state["preview_version"] != state["version"]
            ):
                raise ValueError("Es liegt keine aktuelle Freigabe vor.")
            state.update(busy=True, step=6)
            atomic_json(path / "options.json", {"operation": "export"})
        # Additions use labelled rows, never a JSON editor.
        values_factory = formset_factory(
            SupplementValueForm,
            extra=2,
            max_num=40,
            validate_max=True,
            absolute_max=45,
        )
        edit_index = request.POST.get("supplement_index") or request.GET.get(
            "supplement"
        )
        original_supplement = None
        if edit_index is not None:
            edit_index = int(edit_index)
            if not 0 <= edit_index < len(state["supplements"]):
                raise ValueError("Ergänzung ist nicht vorhanden.")
            original_supplement = state["supplements"][edit_index]
        supplement_data = (
            request.POST
            if action in {"add_supplement", "save_supplement"}
            else None
        )
        supplement_form = SupplementForm(
            supplement_data, prefix="supplement", initial=original_supplement
        )
        value_forms = values_factory(
            supplement_data,
            prefix="values",
            initial=(
                [
                    {"label": key, "value": value}
                    for key, value in original_supplement["records"][0].items()
                ]
                if original_supplement
                else None
            ),
        )
        context["supplement_index"] = edit_index
        if supplement_data is not None:
            valid = supplement_form.is_valid() and value_forms.is_valid()
            if valid:
                record = {}
                for form in value_forms:
                    data = form.cleaned_data
                    if data.get("label"):
                        if data["label"] in record:
                            supplement_form.add_error(
                                None, "Bezeichnungen müssen eindeutig sein."
                            )
                        record[data["label"]] = data.get("value", "")
                if not record:
                    supplement_form.add_error(
                        None, "Mindestens einen bezeichneten Wert ergänzen."
                    )
                if not supplement_form.errors:
                    entry = {
                        **supplement_form.cleaned_data,
                        "records": [record],
                    }
                    if sanitize(entry) != entry:
                        supplement_form.add_error(
                            None, "Mögliche Zugangsdaten entfernen."
                        )
                    elif action == "save_supplement" and edit_index is None:
                        supplement_form.add_error(
                            None, "Ergänzung ist nicht vorhanden."
                        )
                    else:
                        if action == "save_supplement":
                            state["supplements"][edit_index] = entry
                        else:
                            state["supplements"].append(entry)
                        changed = True
        if action == "remove_supplement":
            index = int(request.POST.get("supplement_index", "-1"))
            if not 0 <= index < len(state["supplements"]):
                raise ValueError("Ergänzung ist nicht vorhanden.")
            state["supplements"].pop(index)
            changed = True
        if changed:
            invalidate(state)
            state["step"] = target_step
        if action:
            atomic_json(path / "state.json", state)
            if (
                changed
                or state["busy"]
                or (action == "approve" and state.get("approval"))
            ):
                return HttpResponseRedirect(
                    url(token, state["step"], category=category_index)
                )
        context.update(
            information(source, state)
            if "controller_form" not in context
            else {}
        )
        if "output_form" not in context:
            context["output_form"], context["file_forms"] = output_forms(
                source, state
            )
        if "selection_form" not in context:
            context["selection_form"], _ = selection_form(
                source, state, category
            )
        context.setdefault("approval_form", ApprovalForm())
        context.update(
            supplement_form=supplement_form,
            value_forms=value_forms,
            progress=progress(source, state),
            category_choices=choices,
            review_links=[
                (number, label, url(token, number))
                for number, label in (
                    (2, "Auskunftsart"),
                    (3, "Daten prüfen"),
                    (4, "Verarbeitung"),
                    (5, "Vorschau & Freigabe"),
                    (6, "Export"),
                )
            ],
        )
        if action == "filter":
            state["filter"] = {
                "category": category_index,
                "query": request.POST.get("query", "")[:200],
                "only_open": request.POST.get("only_open") == "on",
            }
            atomic_json(path / "state.json", state)
        active_filter = state.get("filter", {})
        if active_filter.get("category") != category_index:
            active_filter = {}
        query = active_filter.get("query", "").strip().casefold()
        only_open = active_filter.get("only_open", False)
        rows = [
            field for field in fields(source) if field.category == category
        ]
        rows = [
            field
            for field in rows
            if (not only_open or field.key not in state["decisions"])
            and (
                not query
                or query
                in (
                    field.label + " " + field.record + " " + str(field.value)
                ).casefold()
            )
        ]
        try:
            page = max(0, int(request.GET.get("page", 0)))
        except ValueError:
            page = 0
        # Page by fields so a wide record cannot create a giant HTML response.
        shown = page_items(rows, page, PAGE_SIZE)
        context["review_fields"] = [
            {
                "field": field,
                "checked": field.key in state["decisions"],
                "selected": included(field, state),
                "value": (
                    caption(
                        decision_value(field, state["decisions"][field.key])
                    )
                    if field.key in state["decisions"]
                    else caption(field.value)
                ),
                "edit_url": url(
                    token,
                    3,
                    category=category_index,
                    edit=field_token(token, source, field),
                ),
            }
            for field in shown
        ]
        context.update(
            query=active_filter.get("query", ""),
            only_open=only_open,
            previous_url=(
                url(token, 3, category=category_index, page=page - 1)
                if page
                else None
            ),
            next_url=(
                url(token, 3, category=category_index, page=page + 1)
                if (page + 1) * PAGE_SIZE < len(rows)
                else None
            ),
            field_count=len(rows),
        )
        if (
            state["preview_version"] == state["version"]
            and (path / "preview.json").exists()
        ):
            public = recipient_payload(read_json(path / "preview.json"))
            context["preview_information"] = preview_information(public)
            preview_choices = [
                (key, value)
                for key, value in public["categories"].items()
                if value["records"]
            ]
            pcategory = max(
                0,
                min(
                    len(preview_choices) - 1,
                    int(request.GET.get("preview_category", 0)),
                ),
            )
            ppage = max(0, int(request.GET.get("preview_page", 0)))
            context["preview_category_index"] = pcategory
            key, value = preview_choices[pcategory]
            context["preview_choices"] = [
                (i, item[1]["label"], url(token, 5, preview_category=i))
                for i, item in enumerate(preview_choices)
            ]
            context["preview_categories"] = [
                {
                    "label": value["label"],
                    "records": [
                        [
                            {
                                "label": value["fields"]
                                .get(key, {})
                                .get("label", german_label(key)),
                                "value": caption(item),
                            }
                            for key, item in record.items()
                        ]
                        for record in page_items(value["records"], ppage, 4)
                    ],
                    "count": len(value["records"]),
                }
            ]
            context["preview_previous"] = (
                url(
                    token,
                    5,
                    preview_category=pcategory,
                    preview_page=ppage - 1,
                )
                if ppage
                else None
            )
            context["preview_next"] = (
                url(
                    token,
                    5,
                    preview_category=pcategory,
                    preview_page=ppage + 1,
                )
                if (ppage + 1) * 4 < len(value["records"])
                else None
            )
            if request.GET.get("preview_field") is not None:
                row, column = [
                    int(part)
                    for part in request.GET["preview_field"].split("-")
                ]
                if not 0 <= row < len(value["records"]):
                    raise ValueError("Vorschaufeld ist nicht verfügbar.")
                record = value["records"][row]
                if not 0 <= column < len(record):
                    raise ValueError("Vorschaufeld ist nicht verfügbar.")
                field_name = list(record)[column]
                leaf_page = max(0, int(request.GET.get("detail_page", 0)))
                detail = list(leaves(record[field_name]))
                context["preview_detail"] = [
                    {
                        "label": " › ".join(
                            (
                                str(p + 1)
                                if isinstance(p, int)
                                else german_label(p)
                            )
                            for p in path
                        ),
                        "value": caption(item),
                    }
                    for path, item in page_items(detail, leaf_page, 30)
                ]
                context["detail_previous"] = (
                    url(
                        token,
                        5,
                        preview_category=pcategory,
                        preview_field=f"{row}-{column}",
                        detail_page=leaf_page - 1,
                    )
                    if leaf_page
                    else None
                )
                context["detail_next"] = (
                    url(
                        token,
                        5,
                        preview_category=pcategory,
                        preview_field=f"{row}-{column}",
                        detail_page=leaf_page + 1,
                    )
                    if (leaf_page + 1) * 30 < len(detail)
                    else None
                )
            for offset, record in enumerate(
                context["preview_categories"][0]["records"]
            ):
                for column, field in enumerate(record):
                    field["detail_url"] = url(
                        token,
                        5,
                        preview_category=pcategory,
                        preview_field=f"{ppage * 4 + offset}-{column}",
                    )
            omission_page = max(0, int(request.GET.get("omission_page", 0)))
            context["preview_omissions"] = page_items(
                public["omissions"], omission_page, 30
            )
            context["omission_previous"] = (
                url(token, 5, omission_page=omission_page - 1)
                if omission_page
                else None
            )
            context["omission_next"] = (
                url(token, 5, omission_page=omission_page + 1)
                if (omission_page + 1) * 30 < len(public["omissions"])
                else None
            )
        return render(
            request,
            context,
            (
                400
                if context.get("error")
                or any(
                    form.errors
                    for form in (
                        context.get("field_form"),
                        context["output_form"],
                        context["approval_form"],
                        context["supplement_form"],
                        context.get("selection_form"),
                    )
                    if form is not None
                )
                or any(context["value_forms"].errors)
                else 200
            ),
        )
    finally:
        lease.close()
