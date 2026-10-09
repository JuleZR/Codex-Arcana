"""Named fantasy date fields for calendar administration."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from charsheet.engine.calendar_engine import CalendarEngine
from charsheet.models.calendar import (
    CalendarDefinition,
    CalendarLeapException,
    CalendarLeapRule,
    CalendarMonth,
    CalendarSystem,
)


def season_payload(month):
    if not month.season_id:
        return None
    return {
        "id": month.season_id,
        "name": month.season.name,
        "style": month.season.visual_style,
        "rain_intensity": month.season.rain_intensity,
        "falling_rain": month.season.falling_rain,
        "surface_drops": month.season.surface_drops,
    }


def month_options(calendar, year, engine=None):
    engine = engine or CalendarEngine()
    months, _ = engine.structure(calendar)
    lengths = engine.month_lengths(calendar, year)
    return [
        {
            "id": month.pk,
            "number": number,
            "name": month.name,
            "days": days,
            "season": season_payload(month),
        }
        for number, (month, days) in enumerate(zip(months, lengths), 1)
    ]


class OptionalOffsetWidget(forms.NumberInput):
    def render(self, name, value, attrs=None, renderer=None):
        field = super().render(name, value, attrs, renderer)
        return format_html(
            "<details{}><summary>Versatz (optional)</summary>{}"
            "<small>0: Jahre 0, X, 2X …; 1: Jahre 1, X+1, 2X+1 …</small>"
            "</details>",
            " open" if value not in (None, "", 0, "0") else "",
            field,
        )


class CalendarMonthForm(forms.ModelForm):
    class Meta:
        model = CalendarMonth
        fields = ("calendar", "name", "sort_order", "days", "season")


class CalendarLeapRuleForm(forms.ModelForm):
    class Meta:
        model = CalendarLeapRule
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        calendar = (
            self.data.get(self.add_prefix("calendar"))
            if self.is_bound
            else self.initial.get("calendar")
        )
        try:
            self.fields["month"].queryset = CalendarMonth.objects.filter(
                calendar_id=int(calendar),
            )
        except (TypeError, ValueError):
            self.fields["month"].queryset = CalendarMonth.objects.none()
        self.fields["month"].help_text = (
            "Zuerst den Kalender auswählen; dann den Monat mit Schalttagen."
        )


class CalendarLeapExceptionForm(forms.ModelForm):
    class Meta:
        model = CalendarLeapException
        fields = "__all__"
        widgets = {"offset": OptionalOffsetWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["offset"].required = False

    def clean_offset(self):
        return self.cleaned_data.get("offset") or 0


class CalendarSystemForm(forms.ModelForm):
    class Meta:
        model = CalendarSystem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "anchor_year" not in self.fields:
            return
        self.fields["anchor_year"].help_text = (
            "Positive und negative ganze Jahre sowie Jahr 0 sind erlaubt."
        )
        if (
            not self.is_bound
            and self.instance.pk
            and not self.instance.reference_system_id
        ):
            try:
                date = CalendarEngine().local_date(
                    self.instance.calendar_definition,
                    self.instance.root_origin_day,
                )
                for key, value in zip(("year", "month", "day"), date):
                    self.initial["anchor_" + key] = value
            except ValidationError:
                self.fields["calendar_definition"].help_text += (
                    " Der bisherige Kalender ist unvollständig. "
                    "Bitte die Monatsliste vervollständigen oder "
                    "einen gültigen Kalender wählen."
                )
        calendar = self._selected(CalendarDefinition, "calendar_definition")
        reference = self._selected(CalendarSystem, "reference_system")
        if self.is_bound and reference is None:
            self.data = self.data.copy()
            for key in ("year", "month", "day"):
                self.data[self.add_prefix("reference_" + key)] = ""
        self._date_fields("anchor", calendar, required=True)
        self._date_fields(
            "reference",
            reference.calendar_definition if reference else None,
            required=reference is not None,
        )
        self.fields["reference_year"].required = reference is not None

    def _value(self, name):
        return (
            self.data.get(self.add_prefix(name))
            if self.is_bound
            else self.initial.get(name, self.fields[name].initial)
        )

    def _selected(self, model, field):
        try:
            return model.objects.filter(pk=int(self._value(field))).first()
        except (TypeError, ValueError):
            return None

    def _date_fields(self, prefix, calendar, required, engine=None):
        options = []
        try:
            if calendar:
                options = month_options(
                    calendar, int(self._value(prefix + "_year")), engine
                )
        except (ValueError, TypeError, ValidationError):
            pass
        month_name, day_name = prefix + "_month", prefix + "_day"
        try:
            month = int(self._value(month_name))
        except (ValueError, TypeError):
            month = 0
        length = (
            options[month - 1]["days"] if 1 <= month <= len(options) else 0
        )
        errors = {
            "required": "Bitte diesen Teil des Datums angeben.",
            "invalid_choice": (
                "Das gewählte Datum existiert in diesem Kalender nicht."
            ),
        }
        self.fields[month_name] = forms.TypedChoiceField(
            label="Monat",
            coerce=int,
            required=required,
            choices=[("", "Monat auswählen")]
            + [(entry["number"], entry["name"]) for entry in options],
            error_messages=errors,
        )
        self.fields[day_name] = forms.TypedChoiceField(
            label="Tag",
            coerce=int,
            required=required,
            choices=[("", "Tag auswählen")]
            + [(day, day) for day in range(1, length + 1)],
            error_messages=errors,
        )

    def clean(self):
        data = super().clean()
        if not data.get("reference_system"):
            data.update(reference_year=0, reference_month=1, reference_day=1)
        return data
