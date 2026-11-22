"""Database maintenance for official and homebrew creature cost definitions."""

from django import forms
from django.contrib import admin

from charsheet.engine.creature_power import CATEGORIES
from charsheet.models import (
    CreatureCategoryRule,
    CreatureCreation,
    CreaturePowerRule,
)


class CreatureCategoryRuleForm(forms.ModelForm):
    category = forms.ChoiceField(
        label="Kreaturenkategorie",
        choices=[(key, value[0]) for key, value in CATEGORIES.items()],
    )

    class Meta:
        model = CreatureCategoryRule
        fields = "__all__"


@admin.register(CreatureCategoryRule)
class CreatureCategoryRuleAdmin(admin.ModelAdmin):
    form = CreatureCategoryRuleForm
    list_display = ("__str__", "grants_natural_survival")
    list_editable = ("grants_natural_survival",)
    list_filter = ("grants_natural_survival",)


@admin.register(CreaturePowerRule)
class CreaturePowerRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "cost_kind", "formula", "official", "source")
    list_filter = ("official", "cost_kind")
    search_fields = ("name", "key", "description")
    autocomplete_fields = (
        "trait",
        "special_skill",
        "daemonic_power",
        "vampire_power",
    )
    prepopulated_fields = {"key": ("name",)}


@admin.register(CreatureCreation)
class CreatureCreationAdmin(admin.ModelAdmin):
    list_display = ("creature", "author", "released", "updated_at")
    list_filter = ("released",)
    readonly_fields = ("updated_at",)
