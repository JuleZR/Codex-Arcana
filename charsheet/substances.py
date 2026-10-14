"""Editing helpers for passive catalog substance definitions."""

from django import forms
from django.core.exceptions import ValidationError

from charsheet.models import SubstanceStats


class SubstanceStatsForm(forms.ModelForm):
    class Meta:
        model = SubstanceStats
        exclude = ("item",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.CharField):
                field.strip = False
                field.widget.attrs["rows"] = 2


def save_substance_stats(item, post_data):
    """Validate submitted stats; omitted fields preserve existing records."""
    if not item.item_type.supports_substance_stats:
        return
    if not any(f"substance-{name}" in post_data
               for name in SubstanceStatsForm.base_fields):
        return
    instance = getattr(item, "substancestats", None)
    form = SubstanceStatsForm(
        post_data, instance=instance, prefix="substance",
    )
    form.instance.item = item
    if not form.is_valid():
        raise ValidationError(dict(form.errors))
    if any(value not in (None, "") for value in form.cleaned_data.values()):
        form.save()
    elif instance is not None:
        instance.delete()
