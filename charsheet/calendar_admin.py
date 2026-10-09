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
    CalendarSystemForm,
    month_options,
)
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
    list_display = ("name", "visual_style")
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
    form = CalendarSystemForm
    readonly_fields = ("configuration_summary",)
    fieldsets = (
        (
            "Allgemeine Angaben",
            {
                "fields": (
                    "name",
                    "abbreviation",
                    "calendar_definition",
                    "reference_system",
                    "configuration_summary",
                ),
            },
        ),
        (
            "Verwendung auf Charakterbögen",
            {
                "fields": ("default_for_characters", "real_date_reference"),
                "description": "Die Übernahme des realen Datums erfolgt nur "
                "einmal beim ersten Öffnen des Charakterkalenders.",
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
