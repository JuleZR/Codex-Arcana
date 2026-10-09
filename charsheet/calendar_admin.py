"""Calendar administration with complete inline structure validation."""

import json

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import BaseInlineFormSet
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html

from charsheet.calendar_forms import (
    CalendarLeapExceptionForm,
    CalendarLeapRuleForm,
    CalendarMonthForm,
    month_options,
)
from charsheet.calendar_editor import (
    CalendarEditor,
    IntegratedCalendarSystemForm,
    calendar_data,
)
from charsheet.engine.calendar_engine import CalendarEngine
from charsheet.engine.calendar_engine import rule_applies

from charsheet.models.calendar import (
    CalendarDefinition,
    CalendarLeapException,
    CalendarLeapRule,
    CalendarMonth,
    CalendarSeason,
    CalendarSystem,
    CharacterDate,
    used_system_ids,
)


class MonthFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        rows = [
            form.cleaned_data
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if len(rows) != self.instance.months_per_year:
            raise ValidationError(
                f"{len(rows)} Monate sind angelegt; vorgesehen sind "
                f"{self.instance.months_per_year} Monate."
            )
        if sum(row["days"] for row in rows) != self.instance.days_per_year:
            raise ValidationError(
                f"Die {len(rows)} Monate umfassen zusammen "
                f"{sum(row['days'] for row in rows)} Tage. Für dieses "
                f"Kalenderjahr sind jedoch {self.instance.days_per_year} "
                "Tage festgelegt."
            )
        if len({row["sort_order"] for row in rows}) != len(rows):
            raise ValidationError("Monatspositionen müssen eindeutig sein.")
        if (
            self.instance.pk
            and self.instance.is_used()
            and any(form.cleaned_data.get("DELETE") for form in self.forms)
        ):
            raise ValidationError(
                "Monate verwendeter Kalender können nicht gelöscht werden."
            )


class MonthInline(admin.TabularInline):
    model = CalendarMonth
    form = CalendarMonthForm
    formset = MonthFormSet
    fields = ("name", "sort_order", "days", "season")
    template = "admin/charsheet/calendar/months.html"
    extra = 0

    def get_extra(self, request, obj=None, **kwargs):
        return (
            0
            if obj
            else CalendarDefinition._meta.get_field(
                "months_per_year"
            ).get_default()
        )


@admin.register(CalendarSeason)
class CalendarSeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "visual_style", "rain_intensity")
    search_fields = ("name",)


class ProtectedCalendarAdmin(admin.ModelAdmin):
    actions = None

    class Media:
        js = ("charsheet/js/calendar-admin.js",)
        css = {"all": ("charsheet/css/calendar-admin.css",)}

    @admin.display(description="Vorschau")
    def configuration_summary(self, obj):
        exceptions = (
            list(obj.exceptions.values("effect", "period", "offset"))
            if isinstance(obj, CalendarLeapRule) and obj.pk
            else []
        )
        return format_html(
            '<div data-calendar-summary data-navigation-url="{}" '
            'data-leap-preview-url="{}" data-saved-exceptions="{}" '
            'role="status" aria-live="polite">'
            "Die Vorschau wird aus den aktuellen Eingaben erstellt.</div>",
            reverse("admin:charsheet_calendardefinition_navigation"),
            reverse("admin:charsheet_calendardefinition_leap_preview"),
            json.dumps(exceptions),
        )

    def has_delete_permission(self, request, obj=None):
        if obj:
            if isinstance(obj, CalendarSystem):
                used = obj.pk in used_system_ids()
            elif isinstance(obj, CalendarDefinition):
                used = obj.is_used()
            elif isinstance(obj, (CalendarLeapRule, CalendarMonth)):
                used = obj.calendar.is_used()
            else:
                used = obj.rule.calendar.is_used()
            if used:
                return False
        return super().has_delete_permission(request, obj)


@admin.register(CalendarDefinition)
class CalendarDefinitionAdmin(ProtectedCalendarAdmin):
    list_display = ("name", "months_per_year", "days_per_year")
    inlines = (MonthInline,)
    readonly_fields = ("configuration_summary",)
    fieldsets = (
        (
            "Aufbau des Kalenderjahres",
            {
                "fields": (
                    "name",
                    "months_per_year",
                    "days_per_year",
                    "configuration_summary",
                ),
                "description": "Ein Kalender beschreibt die Struktur "
                "eines Jahres. "
                "Die Monatsanzahl und die Summe der Monatstage "
                "müssen zu diesen Angaben passen.",
            },
        ),
    )

    def get_urls(self):
        return [
            path(
                "navigation/",
                self.admin_site.admin_view(self.navigation),
                name="charsheet_calendardefinition_navigation",
            ),
            path(
                "leap-preview/",
                self.admin_site.admin_view(self.leap_preview),
                name="charsheet_calendardefinition_leap_preview",
            ),
        ] + super().get_urls()

    def _allow_navigation(self, request):
        if not any(
            request.user.has_perm(f"charsheet.{action}_{model}")
            for action in ("view", "add", "change")
            for model in (
                "calendardefinition",
                "calendarsystem",
                "calendarleaprule",
                "calendarmonth",
            )
        ):
            raise PermissionDenied

    def navigation(self, request):
        self._allow_navigation(request)
        if request.method != "GET":
            return JsonResponse(
                {"error": "Bitte eine Leseanfrage verwenden."}, status=405
            )
        try:
            year = forms.IntegerField().clean(request.GET.get("year", "0"))
            system = None
            if request.GET.get("system"):
                system = CalendarSystem.objects.get(pk=request.GET["system"])
                calendar = system.calendar_definition
            else:
                calendar = CalendarDefinition.objects.get(
                    pk=request.GET["calendar"]
                )
            return JsonResponse(
                {
                    "calendar_name": calendar.name,
                    "system_name": system.name if system else "",
                    "abbreviation": system.abbreviation if system else "",
                    "months": month_options(calendar, year),
                }
            )
        except (
            ValueError,
            KeyError,
            CalendarDefinition.DoesNotExist,
            CalendarSystem.DoesNotExist,
            ValidationError,
        ) as error:
            message = (
                " ".join(error.messages)
                if isinstance(error, ValidationError)
                else "Bitte einen vorhandenen Kalender auswählen."
            )
            return JsonResponse({"error": message}, status=400)

    def leap_preview(self, request):
        self._allow_navigation(request)
        if request.method != "POST":
            return JsonResponse(
                {"error": "Bitte eine Vorschauanfrage senden."}, status=405
            )
        try:
            data = json.loads(request.body)
            positive = forms.IntegerField(min_value=1, max_value=2**31 - 1)
            signed = forms.IntegerField(
                min_value=-(2**31), max_value=2**31 - 1
            )
            period = positive.clean(data["period"])
            added = positive.clean(data["added_days"])
            offset = signed.clean(data.get("offset") or 0)
            start = forms.IntegerField().clean(data.get("start") or 0)
            month = CalendarMonth.objects.get(
                pk=data["month"],
                calendar_id=data["calendar"],
            )
            exceptions = []
            if not isinstance(data.get("exceptions", []), list):
                raise ValueError
            for row in data.get("exceptions", []):
                if row["effect"] not in CalendarLeapException.Effect.values:
                    raise ValueError
                exceptions.append(
                    (
                        row["effect"],
                        signed.clean(row.get("offset") or 0),
                        positive.clean(row["period"]),
                    )
                )
            candidate = start + (offset - start) % period
            years = []
            for _ in range(128):
                if rule_applies(candidate, period, offset, exceptions):
                    years.append(str(candidate))
                    if len(years) == 8:
                        break
                candidate += period
            return JsonResponse(
                {
                    "summary": f"Alle {period} Jahre hat der Monat "
                    f"{month.name} "
                    f"{month.days + added} statt {month.days} Tage. "
                    f"Versatz: {offset}.",
                    "years": years,
                    "start": str(start),
                    "exception_summaries": [
                        f"Alle {p} Jahre "
                        + (
                            "gelten die Schalttage trotz anderer Ausnahmen."
                            if effect == "include"
                            else "entfallen die zusätzlichen Schalttage."
                        )
                        + (f" Versatz: {o}." if o else "")
                        for effect, o, p in exceptions
                    ],
                    "notice": "„Gelten trotzdem“ hat Vorrang vor „entfallen“. "
                    "Ausnahmen gelten nur in Jahren der Grundregel.",
                    "limited": len(years) < 8,
                }
            )
        except (
            ValueError,
            TypeError,
            KeyError,
            CalendarMonth.DoesNotExist,
            ValidationError,
        ) as error:
            message = (
                " ".join(error.messages)
                if isinstance(error, ValidationError)
                else "Bitte Kalender, Monat und Schaltregel "
                "vollständig angeben."
            )
            return JsonResponse({"error": message}, status=400)


@admin.register(CalendarMonth)
class CalendarMonthAdmin(ProtectedCalendarAdmin):
    form = CalendarMonthForm
    list_display = ("name", "calendar", "sort_order", "days", "season")
    list_filter = ("calendar", "season")


class ExceptionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if (
            self.instance.pk
            and self.instance.calendar.is_used()
            and any(form.cleaned_data.get("DELETE") for form in self.forms)
        ):
            raise ValidationError(
                "Schaltausnahmen verwendeter Kalender sind gesperrt."
            )


class ExceptionInline(admin.TabularInline):
    model = CalendarLeapException
    formset = ExceptionFormSet
    form = CalendarLeapExceptionForm
    fields = ("effect", "period", "offset")
    extra = 0


@admin.register(CalendarLeapRule)
class CalendarLeapRuleAdmin(ProtectedCalendarAdmin):
    form = CalendarLeapRuleForm
    list_display = ("calendar", "month", "added_days", "period", "offset")
    inlines = (ExceptionInline,)
    readonly_fields = ("configuration_summary",)
    fieldsets = (
        (
            "Schaltjahrregel",
            {
                "fields": (
                    "calendar",
                    "month",
                    "added_days",
                    "period",
                    "configuration_summary",
                ),
                "description": "Wähle, welcher Monat in regelmäßigen "
                "Abständen "
                "zusätzliche Tage erhält. Ohne Schaltjahrregel "
                "gibt es keine Schalttage.",
            },
        ),
        (
            "Erweiterte Einstellung: Versatz",
            {
                "fields": ("offset",),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(CalendarSystem)
class CalendarSystemAdmin(ProtectedCalendarAdmin):
    form = IntegratedCalendarSystemForm
    change_form_template = "admin/charsheet/calendar/system_change_form.html"

    class Media:
        js = ("charsheet/js/calendar-editor.js",)
        css = {"all": ("charsheet/css/calendar-editor.css",)}

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)

        class RequestForm(base):
            def __init__(self, *args, **kw):
                kw["user"] = request.user
                super().__init__(*args, **kw)

        return RequestForm

    def render_change_form(self, request, context, *args, **kwargs):
        form = context["adminform"].form
        context["calendar_editor"] = form.editor
        context["calendar_snapshot"] = calendar_data(form.editor.selected)
        context["calendar_data_url"] = reverse(
            "admin:charsheet_calendarsystem_editor_data"
        )
        context["calendar_preview_url"] = reverse(
            "admin:charsheet_calendarsystem_editor_preview"
        )
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        form.save_calendar()
        super().save_model(request, obj, form, change)

    def get_urls(self):
        return [
            path(
                "editor-data/",
                self.admin_site.admin_view(self.editor_data),
                name="charsheet_calendarsystem_editor_data",
            ),
            path(
                "editor-preview/",
                self.admin_site.admin_view(self.editor_preview),
                name="charsheet_calendarsystem_editor_preview",
            ),
        ] + super().get_urls()

    def editor_data(self, request):
        if not (
            self.has_view_or_change_permission(request)
            or self.has_add_permission(request)
        ):
            raise PermissionDenied
        if request.method != "GET":
            return JsonResponse(
                {"error": "Nur Leseanfragen erlaubt."}, status=405
            )
        try:
            calendar = CalendarDefinition.objects.get(
                pk=request.GET["calendar"]
            )
            return JsonResponse(calendar_data(calendar))
        except (KeyError, ValueError, CalendarDefinition.DoesNotExist):
            return JsonResponse(
                {"error": "Bitte einen Kalender auswählen."}, status=400
            )

    def editor_preview(self, request):
        if not (
            self.has_add_permission(request)
            or self.has_change_permission(request)
        ):
            raise PermissionDenied
        if request.method != "POST":
            return JsonResponse(
                {"error": "Bitte Vorschau senden."}, status=405
            )
        try:
            data = request.POST
            selected = CalendarDefinition.objects.filter(
                pk=data.get("calendar_definition") or None
            ).first()
            mode = data.get("calendar_mode", "existing")
            engine = CalendarEngine()
            notice = ""
            if mode == "existing":
                calendar = selected
            else:
                editor = CalendarEditor(data, selected, mode, request.user)
                engine = editor.engine(preview=True)
                calendar = editor.calendar
                if not editor.months.management_form.is_valid():
                    raise ValidationError(
                        "Die Monatsverwaltung ist unvollständig."
                    )
                if not editor.rules.is_valid():
                    raise ValidationError(
                        "Bitte Monats- und Schaltregelfelder vervollständigen."
                    )
                if (
                    not editor.months.is_valid()
                    or not editor.definition.is_valid()
                    or editor.definition.cleaned_data.get("months_per_year")
                    != calendar.months_per_year
                    or editor.definition.cleaned_data.get("days_per_year")
                    != calendar.days_per_year
                ):
                    notice = (
                        "Vorläufige Vorschau der vollständigen Monatszeilen. "
                        "Der Kalenderentwurf ist noch unvollständig."
                    )
                if any(
                    not b["exceptions"].is_valid()
                    for b in editor.bundles
                    if not b["form"].cleaned_data.get("DELETE")
                ):
                    raise ValidationError(
                        "Bitte die Schaltausnahmen vervollständigen."
                    )
            if calendar is None:
                raise ValidationError(
                    "Bitte einen Kalender auswählen oder Monate anlegen."
                )
            year = forms.IntegerField().clean(data.get("anchor_year", 0))
            own = month_options(calendar, year, engine)
            reference = CalendarSystem.objects.filter(
                pk=data.get("reference_system") or None
            ).first()
            ref_year = forms.IntegerField().clean(
                data.get("reference_year") or 0
            )
            other = (
                month_options(reference.calendar_definition, ref_year, engine)
                if reference
                else []
            )
            return JsonResponse(
                {
                    "months": own,
                    "reference_months": other,
                    "reference_name": reference.name if reference else "",
                    "days": sum(row["days"] for row in own),
                    "notice": notice,
                }
            )
        except (ValueError, TypeError, ValidationError) as error:
            message = (
                " ".join(error.messages)
                if isinstance(error, ValidationError)
                else "Ungültige Eingaben."
            )
            return JsonResponse({"error": message}, status=400)

    readonly_fields = ("configuration_summary",)
    fieldsets = (
        (
            "Kalenderdefinition",
            {
                "fields": (
                    "calendar_mode",
                    "calendar_definition",
                    "confirm_shared_calendar",
                )
            },
        ),
        (
            "Allgemeine Angaben",
            {
                "fields": (
                    "name",
                    "abbreviation",
                    "reference_system",
                    "configuration_summary",
                ),
            },
        ),
        (
            "Eigenes Datum",
            {
                "fields": (("anchor_year", "anchor_month", "anchor_day"),),
                "description": "Dieses Datum entspricht demselben Tag wie das "
                "folgende Bezugsdatum. Bei der Ausgangszeitrechnung "
                "ist es der absolute Tag 0.",
                "classes": ("calendar-own-date",),
            },
        ),
        (
            "Entspricht folgendem Datum in der Bezugszeitrechnung",
            {
                "fields": (
                    ("reference_year", "reference_month", "reference_day"),
                ),
                "classes": ("calendar-reference-date",),
            },
        ),
        (
            "Standardlayout der Datumsanzeige",
            {"fields": ("date_layout",)},
        ),
        (
            "Verwendung auf Charakterbögen",
            {
                "fields": ("default_for_characters", "real_date_reference"),
                "description": "Die Übernahme des realen Datums erfolgt nur "
                "einmal beim ersten Öffnen des Charakterkalenders.",
            },
        ),
    )
    list_display = (
        "name",
        "abbreviation",
        "calendar_definition",
        "reference_system",
    )


@admin.register(CalendarLeapException)
class CalendarLeapExceptionAdmin(ProtectedCalendarAdmin):
    form = CalendarLeapExceptionForm
    list_display = ("rule", "effect", "period", "offset")


@admin.register(CharacterDate)
class CharacterDateAdmin(admin.ModelAdmin):
    list_display = ("character", "system", "absolute_day")
