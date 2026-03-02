from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterSchool,
    CharacterSkill,
    Modifier,
    ProgressionRule,
    Race,
    RaceAttributeLimit,
    School,
    SchoolType,
    Skill,
    SkillCategory,
    Technique,
)


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class RaceAttributeLimitInline(admin.TabularInline):
    model = RaceAttributeLimit
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class ModifierInline(GenericTabularInline):
    model = Modifier
    ct_field = "source_content_type"
    ct_fk_field = "source_object_id"
    extra = 0
    show_change_link = True
    fields = ("target_kind", "target_slug", "value", "min_school_level")


class CharacterAttributeInline(admin.TabularInline):
    model = CharacterAttribute
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class CharacterSkillInline(admin.TabularInline):
    model = CharacterSkill
    extra = 0
    show_change_link = True
    autocomplete_fields = ("skill",)


class CharacterSchoolInline(admin.TabularInline):
    model = CharacterSchool
    extra = 0
    show_change_link = True
    autocomplete_fields = ("school",)


class SchoolInline(admin.TabularInline):
    model = School
    extra = 0
    show_change_link = True


class TechniqueInline(admin.TabularInline):
    model = Technique
    extra = 0
    show_change_link = True


class ProgressionRuleInline(admin.TabularInline):
    model = ProgressionRule
    extra = 0
    show_change_link = True


class SchoolCharacterInline(admin.TabularInline):
    model = CharacterSchool
    fk_name = "school"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("character",)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name")
    search_fields = ("name", "short_name")
    ordering = ("name",)


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (SkillInline,)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "attribute")
    search_fields = ("name", "slug")
    list_filter = ("category", "attribute")
    ordering = ("category", "name")
    autocomplete_fields = ("category", "attribute")
    list_select_related = ("category", "attribute")


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (RaceAttributeLimitInline, ModifierInline)


@admin.register(RaceAttributeLimit)
class RaceAttributeLimitAdmin(admin.ModelAdmin):
    list_display = ("race", "attribute", "min_value", "max_value")
    search_fields = ("race__name", "attribute__name")
    list_filter = ("race", "attribute")
    ordering = ("race", "attribute")
    autocomplete_fields = ("race", "attribute")
    list_select_related = ("race", "attribute")


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "race")
    search_fields = ("name", "owner__username", "owner__email", "race__name")
    list_filter = ("race",)
    ordering = ("name",)
    inlines = (CharacterAttributeInline, CharacterSkillInline, CharacterSchoolInline)
    autocomplete_fields = ("owner", "race")
    list_select_related = ("owner", "race")


@admin.register(CharacterAttribute)
class CharacterAttributeAdmin(admin.ModelAdmin):
    list_display = ("character", "attribute", "base_value")
    search_fields = ("character__name", "attribute__name")
    list_filter = ("attribute",)
    ordering = ("character", "attribute")
    autocomplete_fields = ("character", "attribute")
    list_select_related = ("character", "attribute")


@admin.register(CharacterSkill)
class CharacterSkillAdmin(admin.ModelAdmin):
    list_display = ("character", "skill", "level")
    search_fields = ("character__name", "skill__name", "skill__slug")
    list_filter = ("skill__category", "skill__attribute")
    ordering = ("character", "skill")
    autocomplete_fields = ("character", "skill")
    list_select_related = ("character", "skill", "skill__category", "skill__attribute")


@admin.register(SchoolType)
class SchoolTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (SchoolInline, ProgressionRuleInline)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "type")
    search_fields = ("name", "slug", "type__name")
    list_filter = ("type",)
    ordering = ("type", "name")
    inlines = (TechniqueInline, SchoolCharacterInline, ModifierInline)
    autocomplete_fields = ("type",)
    list_select_related = ("type",)


@admin.register(CharacterSchool)
class CharacterSchoolAdmin(admin.ModelAdmin):
    list_display = ("character", "school", "level")
    search_fields = ("character__name", "school__name", "school__slug")
    list_filter = ("school__type", "school")
    ordering = ("character", "school")
    autocomplete_fields = ("character", "school")
    list_select_related = ("character", "school", "school__type")


@admin.register(ProgressionRule)
class ProgressionRuleAdmin(admin.ModelAdmin):
    list_display = ("school_type", "min_level", "grant_kind", "amount")
    search_fields = ("school_type__name", "grant_kind")
    list_filter = ("school_type", "grant_kind")
    ordering = ("school_type", "min_level")
    autocomplete_fields = ("school_type",)
    list_select_related = ("school_type",)


@admin.register(Modifier)
class ModifierAdmin(admin.ModelAdmin):
    list_display = (
        "display_source",
        "target_kind",
        "target_slug",
        "value",
        "min_school_level",
    )
    list_filter = ("source_content_type", "target_kind")
    search_fields = ("target_slug",)
    ordering = ("source_content_type", "source_object_id", "target_kind", "target_slug")

    @admin.display(description="Source")
    def display_source(self, obj):
        if obj.source is None:
            return f"{obj.source_content_type} #{obj.source_object_id} (missing)"
        return str(obj.source)

@admin.register(Technique)
class TechniqueAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "school", "level")
    search_fields = ("name", "slug", "school__name", "school__slug")
    list_filter = ("school", "school__type", "level")
    ordering = ("school", "level", "name")
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")
    inlines = (ModifierInline,)
