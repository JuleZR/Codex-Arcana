"""Unsaved calendar formsets for the time-system administration."""

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms.models import construct_instance

from charsheet.calendar_forms import CalendarSystemForm
from charsheet.engine.calendar_engine import CalendarEngine, leap_terms
from charsheet.models.calendar import (
    CalendarDefinition,
    CalendarLeapException,
    CalendarLeapRule,
    CalendarMonth,
    CalendarSeason,
    CalendarSystem,
)


def calendar_data(calendar):
    months = list(calendar.months.all()) if calendar else []
    keys = {month.pk: str(index) for index, month in enumerate(months)}
    rules = []
    if calendar:
        for rule in calendar.leap_rules.prefetch_related("exceptions"):
            rules.append(
                {
                    "id": rule.pk,
                    "month": keys[rule.month_id],
                    "added_days": rule.added_days,
                    "period": rule.period,
                    "offset": rule.offset,
                    "exceptions": list(
                        rule.exceptions.values(
                            "id", "effect", "period", "offset"
                        )
                    ),
                }
            )
    return {
        "definition": {
            "name": calendar.name if calendar else "",
            "months_per_year": calendar.months_per_year if calendar else 12,
            "days_per_year": calendar.days_per_year if calendar else "",
        },
        "months": [
            {
                "id": month.pk,
                "name": month.name,
                "days": month.days,
                "sort_order": month.sort_order,
                "season": month.season_id or "",
            }
            for month in months
        ],
        "rules": rules,
        "systems": (
            list(calendar.systems.values("id", "name")) if calendar else []
        ),
    }


class DefinitionForm(forms.ModelForm):
    class Meta:
        model = CalendarDefinition
        fields = ("name", "months_per_year", "days_per_year")


class MonthForm(forms.Form):
    id = forms.ModelChoiceField(
        queryset=CalendarMonth.objects.none(),
        required=False,
        widget=forms.HiddenInput,
    )
    name = forms.CharField(label="Monatsname", max_length=80)
    sort_order = forms.IntegerField(
        label="Reihenfolge", min_value=1, max_value=2**31 - 1
    )
    days = forms.IntegerField(label="Tage", min_value=1, max_value=2**31 - 1)
    season = forms.ModelChoiceField(
        label="Jahreszeit",
        required=False,
        queryset=CalendarSeason.objects.all(),
    )

    def __init__(self, *args, calendar=None, **kwargs):
        super().__init__(*args, **kwargs)
        if calendar:
            self.fields["id"].queryset = calendar.months.all()


class RuleForm(forms.Form):
    id = forms.ModelChoiceField(
        queryset=CalendarLeapRule.objects.none(),
        required=False,
        widget=forms.HiddenInput,
    )
    month = forms.ChoiceField(label="Monat mit Schalttagen")
    added_days = forms.IntegerField(
        label="Zusätzliche Tage", min_value=1, max_value=2**31 - 1, initial=1
    )
    period = forms.IntegerField(
        label="Alle X Jahre", min_value=1, max_value=2**31 - 1, initial=4
    )
    offset = forms.IntegerField(
        label="Versatz",
        initial=0,
        required=False,
        min_value=-(2**31),
        max_value=2**31 - 1,
    )

    def __init__(self, *args, calendar=None, months=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["month"].choices = [("", "Monat auswählen"), *months]
        if calendar:
            self.fields["id"].queryset = calendar.leap_rules.all()

    def clean_offset(self):
        return self.cleaned_data.get("offset") or 0


class ExceptionForm(forms.Form):
    id = forms.ModelChoiceField(
        queryset=CalendarLeapException.objects.none(),
        required=False,
        widget=forms.HiddenInput,
    )
    effect = forms.ChoiceField(
        label="Wirkung",
        choices=CalendarLeapException.Effect.choices,
        initial="exclude",
    )
    period = forms.IntegerField(
        label="Alle X Jahre", min_value=1, max_value=2**31 - 1
    )
    offset = forms.IntegerField(
        label="Versatz",
        initial=0,
        required=False,
        min_value=-(2**31),
        max_value=2**31 - 1,
    )

    def __init__(self, *args, rule=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rule:
            self.fields["id"].queryset = rule.exceptions.all()

    def clean_offset(self):
        return self.cleaned_data.get("offset") or 0


def active_forms(formset):
    return [
        form
        for form in formset
        if form.is_valid()
        and form.cleaned_data
        and not form.cleaned_data.get("DELETE")
    ]


class CalendarEditor:
    def __init__(self, data=None, calendar=None, mode="existing", user=None):
        self.selected = calendar
        self.mode = mode
        self.user = user
        initial = calendar_data(calendar)
        instance = calendar if mode == "edit" else CalendarDefinition()
        self.definition = DefinitionForm(
            data,
            prefix="definition",
            instance=instance,
            initial=initial["definition"],
        )
        self.months = forms.formset_factory(
            MonthForm, extra=0, can_delete=True
        )(
            data,
            prefix="calendar_months",
            initial=initial["months"],
            form_kwargs={"calendar": calendar},
        )
        if data is None:
            choices = [
                (str(i), row["name"])
                for i, row in enumerate(initial["months"])
            ]
        else:
            active = active_forms(self.months)
            choices = [
                (str(i), form.cleaned_data["name"])
                for i, form in enumerate(self.months)
                if form in active
            ]
        self.rules = forms.formset_factory(RuleForm, extra=0, can_delete=True)(
            data,
            prefix="calendar_rules",
            initial=initial["rules"],
            form_kwargs={"calendar": calendar, "months": choices},
        )
        self.bundles = []
        for index, form in enumerate(self.rules):
            row = (
                initial["rules"][index]
                if index < len(initial["rules"])
                else {}
            )
            rule_id = (
                data.get(form.prefix + "-id")
                if data is not None
                else row.get("id")
            )
            rule = (
                calendar.leap_rules.filter(pk=rule_id).first()
                if calendar and str(rule_id).isdigit()
                else None
            )
            if data is not None:
                row = {
                    "exceptions": (
                        list(
                            rule.exceptions.values(
                                "id", "effect", "period", "offset"
                            )
                        )
                        if rule
                        else []
                    )
                }
            exceptions = self._exceptions(
                data, form.prefix, rule, row.get("exceptions", [])
            )
            empty = exceptions.empty_form
            empty.prefix = form.prefix + "-exceptions-__exception__"
            self.bundles.append(
                {
                    "form": form,
                    "exceptions": exceptions,
                    "empty_exception": empty,
                }
            )
        self.empty_rule = {
            "form": self.rules.empty_form,
            "exceptions": self._exceptions(None, self.rules.empty_form.prefix),
        }
        empty = self.empty_rule["exceptions"].empty_form
        empty.prefix = (
            self.empty_rule["form"].prefix + "-exceptions-__exception__"
        )
        self.empty_rule["empty_exception"] = empty
        self.other_systems = []

    @staticmethod
    def _exceptions(data, prefix, rule=None, initial=()):
        result = forms.formset_factory(
            ExceptionForm, extra=0, can_delete=True
        )(
            data,
            prefix=prefix + "-exceptions",
            initial=initial,
            form_kwargs={"rule": rule},
        )
        return result

    def engine(self, preview=False):
        """Use the existing engine cache for an unsaved structure."""
        self.definition.is_valid()
        rows = active_forms(self.months)
        if not rows:
            raise ValidationError("Bitte mindestens einen Monat angeben.")
        values = self.definition.cleaned_data
        calendar = CalendarDefinition(
            pk=(
                self.selected.pk
                if self.mode == "edit" and self.selected
                else None
            ),
            name=values.get("name", "Kalenderentwurf"),
            months_per_year=(
                len(rows) if preview else values["months_per_year"]
            ),
            days_per_year=(
                sum(f.cleaned_data["days"] for f in rows)
                if preview
                else values["days_per_year"]
            ),
        )
        months = {}
        for index, form in enumerate(self.months):
            if form in rows:
                data = form.cleaned_data
                months[str(index)] = CalendarMonth(
                    pk=-index - 1,
                    calendar=calendar,
                    name=data["name"],
                    days=data["days"],
                    sort_order=data["sort_order"],
                    season=data["season"],
                )
        rules = []
        for bundle in self.bundles:
            form = bundle["form"]
            if form not in active_forms(self.rules):
                continue
            data = form.cleaned_data
            rule = CalendarLeapRule(
                calendar=calendar,
                month=months[data["month"]],
                added_days=data["added_days"],
                period=data["period"],
                offset=data["offset"],
            )
            exceptions = [
                (
                    f.cleaned_data["effect"],
                    f.cleaned_data["offset"],
                    f.cleaned_data["period"],
                )
                for f in active_forms(bundle["exceptions"])
            ]
            rules.append(
                (
                    rule,
                    exceptions,
                    leap_terms(rule.period, rule.offset, exceptions),
                )
            )
        engine = CalendarEngine()
        engine.structures[calendar.pk] = (
            sorted(months.values(), key=lambda month: month.sort_order),
            rules,
        )
        self.calendar = calendar
        return engine

    def validate(self):
        checks = [
            self.definition.is_valid(),
            self.months.is_valid(),
            self.rules.is_valid(),
        ]
        for bundle in self.bundles:
            if not bundle["form"].cleaned_data.get("DELETE"):
                checks.append(bundle["exceptions"].is_valid())
        if not all(checks):
            return False
        rows = active_forms(self.months)
        definition = self.definition.cleaned_data
        if len(rows) != definition["months_per_year"]:
            self.definition.add_error(
                "months_per_year", f"{len(rows)} Monate sind angelegt."
            )
        total = sum(row.cleaned_data["days"] for row in rows)
        if total != definition["days_per_year"]:
            self.definition.add_error(
                "days_per_year", f"Die Monate umfassen zusammen {total} Tage."
            )
        positions = [f.cleaned_data["sort_order"] for f in rows]
        for form in rows:
            if positions.count(form.cleaned_data["sort_order"]) > 1:
                form.add_error(
                    "sort_order", "Diese Position ist doppelt vergeben."
                )
        if not self.definition.is_valid() or any(form.errors for form in rows):
            return False
        groups = [(self.months, CalendarMonth), (self.rules, CalendarLeapRule)]
        groups.extend(
            (b["exceptions"], CalendarLeapException)
            for b in self.bundles
            if not b["form"].cleaned_data.get("DELETE")
        )
        self._permission(
            "change" if self.mode == "edit" else "add", CalendarDefinition
        )
        for formset, model in groups:
            ids = []
            for form in formset:
                data = form.cleaned_data
                obj = data.get("id")
                if obj:
                    ids.append(obj.pk)
                if data.get("DELETE"):
                    if self.mode == "edit" and obj:
                        self._permission("delete", model)
                        if self.selected.is_used():
                            form.add_error(
                                "DELETE",
                                "Verwendete Kalenderdaten "
                                "können nicht gelöscht werden.",
                            )
                elif data:
                    action = "change" if self.mode == "edit" and obj else "add"
                    self._permission(action, model)
            if len(ids) != len(set(ids)):
                raise ValidationError(
                    "Ein Eintrag wurde mehrfach übermittelt."
                )
            if self.mode == "edit":
                expected = {row["id"] for row in formset.initial}
                if set(ids) != expected:
                    raise ValidationError(
                        "Bestehende Einträge fehlen. Bitte die "
                        "Definition erneut auswählen."
                    )
        return not any(form.errors for group, _ in groups for form in group)

    def _permission(self, action, model):
        if self.user and not self.user.has_perm(
            f"charsheet.{action}_{model._meta.model_name}"
        ):
            raise PermissionDenied

    @transaction.atomic
    def save(self):
        calendar = self.definition.save()
        editing = self.mode == "edit"
        # Delete dependent rows first; model deletion guards remain effective.
        for bundle in self.bundles:
            data = bundle["form"].cleaned_data
            if data.get("DELETE"):
                if editing and data.get("id"):
                    data["id"].delete()
                continue
            for form in bundle["exceptions"]:
                data = form.cleaned_data
                if editing and data.get("DELETE") and data.get("id"):
                    data["id"].delete()
        if editing:
            current = list(calendar.months.all())
            occupied = {month.sort_order for month in current}
            occupied.update(
                form.cleaned_data["sort_order"]
                for form in active_forms(self.months)
            )
            temporary = 1
            for month in current:
                while temporary in occupied:
                    temporary += 1
                month.sort_order = temporary
                occupied.add(temporary)
            CalendarMonth.objects.bulk_update(current, ["sort_order"])
        months = {}
        deleted_months = []
        for index, form in enumerate(self.months):
            data = form.cleaned_data
            if data.get("DELETE"):
                if editing and data.get("id"):
                    deleted_months.append(data["id"])
                continue
            if not data:
                continue
            obj = data.get("id") if editing else None
            obj = obj or CalendarMonth(calendar=calendar)
            for name in ("name", "days", "sort_order", "season"):
                setattr(obj, name, data[name])
            obj.save()
            months[str(index)] = obj
        for bundle in self.bundles:
            data = bundle["form"].cleaned_data
            if not data or data.get("DELETE"):
                continue
            rule = data.get("id") if editing else None
            rule = rule or CalendarLeapRule(calendar=calendar)
            rule.month = months[data["month"]]
            for name in ("added_days", "period", "offset"):
                setattr(rule, name, data[name])
            rule.save()
            for form in bundle["exceptions"]:
                row = form.cleaned_data
                if not row or row.get("DELETE"):
                    continue
                obj = row.get("id") if editing else None
                obj = obj or CalendarLeapException(rule=rule)
                for name in ("effect", "period", "offset"):
                    setattr(obj, name, row[name])
                obj.save()
        for month in deleted_months:
            month.delete()
        calendar.validate_structure()
        return calendar


class IntegratedCalendarSystemForm(CalendarSystemForm):
    calendar_mode = forms.ChoiceField(
        label="Kalender verwalten",
        choices=(
            ("existing", "Vorhandenen Kalender verwenden"),
            ("new", "Neue Kalenderdefinition anlegen"),
            ("copy", "Ausgewählten Kalender als eigene Kopie bearbeiten"),
            ("edit", "Ausgewählte Kalenderdefinition bearbeiten"),
        ),
        required=False,
        initial="existing",
    )
    confirm_shared_calendar = forms.BooleanField(
        label="Änderungen für alle aufgeführten Zeitrechnungen übernehmen",
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if "calendar_definition" not in self.fields:
            self.editor = CalendarEditor(
                calendar=self.instance.calendar_definition
            )
            groups = [
                self.editor.definition,
                *self.editor.months,
                *self.editor.rules,
            ]
            for bundle in self.editor.bundles:
                groups.extend(bundle["exceptions"])
            for form in groups:
                for field in form.fields.values():
                    field.disabled = True
            return
        self.fields["calendar_definition"].widget.can_add_related = False
        self.mode = (
            self.data.get("calendar_mode", "existing")
            if self.is_bound
            else "existing"
        )
        self.integrated = self.is_bound and "calendar_mode" in self.data
        selected = self._selected(CalendarDefinition, "calendar_definition")
        self.editor = CalendarEditor(
            self.data if self.is_bound else None, selected, self.mode, user
        )
        self.editor.other_systems = (
            list(selected.systems.exclude(pk=self.instance.pk))
            if selected
            else []
        )
        if self.mode in ("new", "copy", "edit"):
            self.fields["calendar_definition"].required = self.mode != "new"
            try:
                engine = self.editor.engine(preview=True)
                self._date_fields("anchor", self.editor.calendar, True, engine)
                reference = self._selected(CalendarSystem, "reference_system")
                if reference:
                    self._date_fields(
                        "reference",
                        reference.calendar_definition,
                        True,
                        engine,
                    )
            except ValidationError:
                pass

    def clean(self):
        data = super().clean()
        if not self.integrated or self.mode == "existing":
            return data
        if self.mode in ("copy", "edit") and not data.get(
            "calendar_definition"
        ):
            self.add_error(
                "calendar_definition", "Bitte die Definition auswählen."
            )
        try:
            if not self.editor.validate():
                raise ValidationError(
                    "Bitte die markierten Kalenderfelder korrigieren."
                )
            self.draft_engine = self.editor.engine()
            data["calendar_definition"] = self.editor.calendar
        except ValidationError as error:
            self.add_error(None, error)
        if (
            self.mode == "edit"
            and self.editor.other_systems
            and not data.get("confirm_shared_calendar")
        ):
            self.add_error(
                "confirm_shared_calendar",
                "Diese Definition wird auch "
                "von anderen Zeitrechnungen verwendet. Bitte die "
                "gemeinsame Änderung bestätigen oder eine Kopie anlegen.",
            )
        return data

    def _post_clean(self):
        if not self.integrated or self.mode == "existing":
            return super()._post_clean()
        exclude = self._get_validation_exclusions() | {"calendar_definition"}
        self.instance = construct_instance(
            self, self.instance, self._meta.fields, self._meta.exclude
        )
        try:
            self.instance.clean_fields(exclude=exclude)
            self.instance.validate_unique(exclude=exclude)
            self.instance.validate_constraints(exclude=exclude)
            if self.errors or not hasattr(self, "draft_engine"):
                return
            system = self.instance
            if system.reference_system_id == system.pk and system.pk:
                self.add_error(
                    "reference_system",
                    "Eine Zeitrechnung kann "
                    "nicht auf sich selbst verweisen.",
                )
                return
            if system.real_date_reference:
                self.draft_engine.validate_real_date_calendar(
                    system.calendar_definition
                )
            own = self.draft_engine.local_day(
                system.calendar_definition,
                system.anchor_year,
                system.anchor_month,
                system.anchor_day,
            )
            if not system.reference_system_id:
                system.root_origin_day = own
            self.draft_engine.system_offset(system)
        except ValidationError as error:
            self._update_errors(error)

    def save_calendar(self):
        if self.integrated and self.mode != "existing":
            self.instance.calendar_definition = self.editor.save()
