"""Django admin configuration for character sheet domain models."""

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline
from django.http import JsonResponse
from django.urls import path, reverse

from .models import (
    ArmorStats,
    Attribute,
    Character,
    CharacterAttribute,
    CharacterDiaryEntry,
    CharacterItem,
    CharacterLanguage,
    CharacterSchool,
    CharacterSchoolPath,
    CharacterSkill,
    CharacterTechnique,
    CharacterTechniqueChoice,
    CharacterTrait,
    DamageSource,
    Item,
    Language,
    Modifier,
    ProgressionRule,
    Race,
    RaceAttributeLimit,
    School,
    SchoolPath,
    SchoolType,
    Skill,
    SkillCategory,
    SkillFamily,
    Technique,
    TechniqueExclusion,
    TechniqueRequirement,
    Trait,
    WeaponStats,
)

ArmorStats._meta.verbose_name = "Armor Stats"
ArmorStats._meta.verbose_name_plural = "Armor Stats"
WeaponStats._meta.verbose_name = "Weapon Stats"
WeaponStats._meta.verbose_name_plural = "Weapon Stats"


def _label_skill_family_field(formfield):
    """Render skill family choices with readable labels in admin widgets."""
    if formfield is not None:
        formfield.label_from_instance = lambda obj: f"{obj.name} ({obj.slug})"
    return formfield


def _format_technique_choice_context(technique):
    """Return compact editor-facing choice guidance for a technique."""
    if technique is None:
        return "-"
    parts = []
    if technique.choice_group:
        parts.append(f"Group: {technique.choice_group}")
    if technique.selection_notes:
        parts.append(technique.selection_notes)
    if not parts and technique.choice_target_kind != Technique.ChoiceTargetKind.NONE:
        parts.append("Persistent choice without extra editor notes.")
    return " | ".join(parts) if parts else "-"


class SkillInline(admin.TabularInline):
    """Inline editor for skills within a category."""

    model = Skill
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Use readable labels for optional skill family relations."""
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "family":
            return _label_skill_family_field(formfield)
        return formfield


class SkillFamilySkillInline(admin.TabularInline):
    """Inline editor for skills from the family side."""

    model = Skill
    fk_name = "family"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("category", "attribute")


class RaceAttributeLimitInline(admin.TabularInline):
    """Inline editor for race-specific attribute limits."""

    model = RaceAttributeLimit
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class ModifierInline(GenericStackedInline):
    """Generic inline editor for modifiers attached to source models."""

    model = Modifier
    ct_field = "source_content_type"
    ct_fk_field = "source_object_id"
    extra = 0
    show_change_link = True
    fieldsets = (
        ("Target", {"fields": (("target_kind", "target_slug"),)}),
        ("Value", {"fields": (("mode", "value"),)}),
        ("Scaling", {"fields": (("scale_source", "scale_school"), ("mul", "div", "round_mode"))}),
        ("Cap", {"fields": (("cap_mode", "cap_source"), "min_school_level")}),
    )
    autocomplete_fields = ("scale_school",)


class CharacterAttributeInline(admin.TabularInline):
    """Inline editor for a character's base attributes."""

    model = CharacterAttribute
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class AttributeCharacterInline(admin.TabularInline):
    """Inline editor for character attributes from the attribute side."""

    model = CharacterAttribute
    fk_name = "attribute"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("character",)


class CharacterSkillInline(admin.TabularInline):
    """Inline editor for a character's skill levels."""

    model = CharacterSkill
    extra = 0
    show_change_link = True
    autocomplete_fields = ("skill",)


class SkillCharacterInline(admin.TabularInline):
    """Inline editor for character skills from the skill side."""

    model = CharacterSkill
    fk_name = "skill"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("character",)


class CharacterSchoolInline(admin.TabularInline):
    """Inline editor for a character's learned schools."""

    model = CharacterSchool
    extra = 0
    show_change_link = True
    autocomplete_fields = ("school",)


class CharacterSchoolPathInline(admin.TabularInline):
    """Inline editor for a character's chosen school paths."""

    model = CharacterSchoolPath
    extra = 0
    show_change_link = True
    autocomplete_fields = ("school", "path")


class CharacterTechniqueInline(admin.TabularInline):
    """Inline editor for a character's explicitly learned techniques."""

    model = CharacterTechnique
    extra = 0
    show_change_link = True
    autocomplete_fields = ("technique",)
    fields = (
        "technique",
        "technique_school",
        "technique_level",
        "technique_support_level",
        "technique_choice_context",
        "learned_at",
        "notes",
    )
    readonly_fields = (
        "technique_school",
        "technique_level",
        "technique_support_level",
        "technique_choice_context",
    )

    @admin.display(description="School")
    def technique_school(self, obj):
        """Show the technique's school for faster editing context."""
        if not obj or not obj.technique_id:
            return "-"
        return obj.technique.school

    @admin.display(description="Level")
    def technique_level(self, obj):
        """Show the technique's school level requirement."""
        if not obj or not obj.technique_id:
            return "-"
        return obj.technique.level

    @admin.display(description="Support")
    def technique_support_level(self, obj):
        """Show how fully the engine supports the linked technique."""
        if not obj or not obj.technique_id:
            return "-"
        return obj.technique.support_level

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Show persistent choice guidance for the linked technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _format_technique_choice_context(obj.technique)


class CharacterTechniqueChoiceInline(admin.TabularInline):
    """Inline editor for persistent character technique choices."""

    model = CharacterTechniqueChoice
    fk_name = "character"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("technique", "selected_skill", "selected_skill_family")
    fields = (
        "technique",
        "technique_school",
        "choice_target_kind",
        "technique_choice_context",
        "selected_skill",
        "selected_skill_family",
    )
    readonly_fields = ("technique_school", "choice_target_kind", "technique_choice_context")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit choice rows to real choice techniques and readable family labels."""
        if db_field.name == "technique":
            kwargs["queryset"] = Technique.objects.exclude(
                choice_target_kind=Technique.ChoiceTargetKind.NONE
            ).select_related("school", "path")
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "selected_skill_family":
            return _label_skill_family_field(formfield)
        return formfield

    @admin.display(description="School")
    def technique_school(self, obj):
        """Show the owning school of the selected technique."""
        if not obj or not obj.technique_id:
            return "-"
        return obj.technique.school

    @admin.display(description="Target")
    def choice_target_kind(self, obj):
        """Show which persistent target type the technique expects."""
        if not obj or not obj.technique_id:
            return "-"
        return obj.technique.choice_target_kind

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Show editor-facing notes for the linked choice technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _format_technique_choice_context(obj.technique)


class CharacterItemInline(admin.TabularInline):
    """Inline editor for a character's inventory entries."""

    model = CharacterItem
    fk_name = "owner"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("item",)


class SchoolInline(admin.TabularInline):
    """Inline editor for schools inside a school type."""

    model = School
    extra = 0
    show_change_link = True


class TechniqueInline(admin.TabularInline):
    """Inline editor for techniques belonging to one school."""

    model = Technique
    extra = 0
    show_change_link = True
    autocomplete_fields = ("path",)
    fields = (
        "name",
        "level",
        "path",
        "technique_type",
        "acquisition_type",
        "support_level",
        "is_choice_placeholder",
        "choice_group",
        "selection_notes",
        "choice_target_kind",
        "choice_limit",
        "choice_bonus_value",
        "action_type",
        "usage_type",
        "activation_cost",
        "activation_cost_resource",
    )


class ProgressionRuleInline(admin.TabularInline):
    """Inline editor for school type progression rules."""

    model = ProgressionRule
    extra = 0
    show_change_link = True


class SchoolCharacterInline(admin.TabularInline):
    """Inline editor for character-school relations from the school side."""

    model = CharacterSchool
    fk_name = "school"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("character",)


class ArmorStatsInline(admin.StackedInline):
    """Inline editor for one-to-one armor stats on an item."""

    model = ArmorStats
    verbose_name_plural = "Armor Stats"
    extra = 0
    max_num = 1
    can_delete = True


class WeaponStatsInline(admin.StackedInline):
    """Inline editor for one-to-one weapon stats on an item."""

    model = WeaponStats
    verbose_name_plural = "Weapon Stats"
    extra = 0
    max_num = 1
    can_delete = True
    autocomplete_fields = ("damage_source",)


class SchoolPathInline(admin.TabularInline):
    """Inline editor for specialization paths belonging to one school."""

    model = SchoolPath
    extra = 0
    show_change_link = True


class TechniqueRequirementInline(admin.TabularInline):
    """Inline editor for structured technique requirements."""

    model = TechniqueRequirement
    fk_name = "technique"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("required_technique", "required_path", "required_skill", "required_trait")
    fields = (
        "minimum_school_level",
        "required_technique",
        "required_path",
        "required_skill",
        "required_skill_level",
        "required_trait",
        "required_trait_level",
    )


class TechniqueExclusionInline(admin.TabularInline):
    """Inline editor for techniques excluded by the current technique."""

    model = TechniqueExclusion
    fk_name = "technique"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("excluded_technique",)


class WeaponStatsByDamageSourceInline(admin.TabularInline):
    """Inline editor for weapon stats from the damage source side."""

    model = WeaponStats
    fk_name = "damage_source"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("item",)


class ItemCharacterInline(admin.TabularInline):
    """Inline editor for character ownership entries from the item side."""

    model = CharacterItem
    fk_name = "item"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("owner",)


class CharacterTraitInline(admin.TabularInline):
    """Inline editor for character trait ownership."""

    model = CharacterTrait
    fk_name = "owner"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("trait",)
    fields = ("trait", "trait_level", "trait_min_level", "trait_max_level", "trait_points_per_level")
    readonly_fields = ("trait_min_level", "trait_max_level", "trait_points_per_level")

    @admin.display(description="Min Level")
    def trait_min_level(self, obj):
        """Show the trait minimum level for quick reference."""
        if not obj or not obj.trait_id:
            return "-"
        return obj.trait.min_level

    @admin.display(description="Max Level")
    def trait_max_level(self, obj):
        """Show the trait maximum level for quick reference."""
        if not obj or not obj.trait_id:
            return "-"
        return obj.trait.max_level

    @admin.display(description="Points/Level")
    def trait_points_per_level(self, obj):
        """Show trait point cost per level for quick reference."""
        if not obj or not obj.trait_id:
            return "-"
        return obj.trait.points_per_level

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Attach metadata endpoint URL to the trait field widget for JS updates."""
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "trait":
            formfield.widget.attrs["data-trait-meta-url-template"] = reverse(
                "admin:charsheet_character_trait_meta", args=[0]
            )
        return formfield

    class Media:
        """Load JavaScript that keeps trait metadata fields in sync."""
        js = ("charsheet/js/character_trait_inline.js",)


class CharacterLanguageInline(admin.TabularInline):
    """Inline editor for character language proficiency entries."""

    model = CharacterLanguage
    fk_name = "owner"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("language",)


class CharacterDiaryEntryInline(admin.TabularInline):
    """Inline editor for one character's diary roll entries."""

    model = CharacterDiaryEntry
    fk_name = "character"
    extra = 0
    show_change_link = True
    fields = ("order_index", "entry_date", "is_fixed", "updated_at", "text")
    readonly_fields = ("updated_at",)
    ordering = ("order_index", "id")


class TraitCharacterInline(admin.TabularInline):
    """Inline editor for trait ownership from the trait side."""

    model = CharacterTrait
    fk_name = "trait"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("owner",)


class RaceAttributeLimitByAttributeInline(admin.TabularInline):
    """Inline editor for race limits from the attribute side."""

    model = RaceAttributeLimit
    fk_name = "attribute"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("race",)


class LanguageCharacterInline(admin.TabularInline):
    """Inline editor for character-language relations from the language side."""

    model = CharacterLanguage
    fk_name = "language"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("owner",)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    """Admin configuration for attributes."""

    list_display = ("name", "short_name")
    search_fields = ("name", "short_name")
    ordering = ("name",)
    inlines = (RaceAttributeLimitByAttributeInline, AttributeCharacterInline)


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    """Admin configuration for skill categories."""

    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (SkillInline,)


@admin.register(SkillFamily)
class SkillFamilyAdmin(admin.ModelAdmin):
    """Admin configuration for skill families."""

    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (SkillFamilySkillInline,)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    """Admin configuration for skills."""

    list_display = (
        "name",
        "slug",
        "category",
        "category_slug",
        "family_name",
        "family_slug",
        "attribute",
        "attribute_short_name",
    )
    search_fields = ("name", "slug", "family__name", "family__slug")
    list_filter = ("category", "attribute")
    ordering = ("category", "name")
    autocomplete_fields = ("category", "attribute")
    list_select_related = ("category", "family", "attribute")
    inlines = (SkillCharacterInline,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Use readable labels for optional skill family relations."""
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "family":
            return _label_skill_family_field(formfield)
        return formfield

    @admin.display(ordering="category__slug", description="Category Slug")
    def category_slug(self, obj):
        """Return the related category slug for list display."""
        return obj.category.slug

    @admin.display(ordering="family__name", description="Family")
    def family_name(self, obj):
        """Return the related family name for list display."""
        if obj.family_id is None:
            return "-"
        return obj.family.name

    @admin.display(ordering="family__slug", description="Family Slug")
    def family_slug(self, obj):
        """Return the related family slug for list display."""
        if obj.family_id is None:
            return "-"
        return obj.family.slug

    @admin.display(ordering="attribute__short_name", description="Attribute Short")
    def attribute_short_name(self, obj):
        """Return the related attribute short name for list display."""
        return obj.attribute.short_name


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    """Admin configuration for races."""

    list_display = (
        "name",
        "size_class",
        "movement_summary",
        "phase_1_points",
        "phase_2_points",
        "phase_3_points",
        "phase_4_points",
        "can_fly",
    )
    search_fields = ("name", "description")
    list_filter = ("size_class", "can_fly")
    ordering = ("name",)
    inlines = (RaceAttributeLimitInline, ModifierInline)
    fieldsets = (
        (
            "Race",
            {
                "fields": (
                    "name",
                    "description",
                    "size_class",
                    "combat_speed",
                    "march_speed",
                    "sprint_speed",
                    "swimming_speed",
                    "can_fly",
                    "combat_fly_speed",
                    "march_fly_speed",
                    "sprint_fly_speed",
                )
            },
        ),
        (
            "Phase Points",
            {
                "fields": (
                    "phase_1_points",
                    "phase_2_points",
                    "phase_3_points",
                    "phase_4_points",
                )
            },
        ),
    )

    class Media:
        """Load JavaScript to toggle flying speed fields by race settings."""
        js = ("charsheet/js/race_admin.js",)

    @admin.display(description="Movement")
    def movement_summary(self, obj):
        """Render ground and swim movement values in one compact column."""
        return f"G:{obj.combat_speed}/{obj.march_speed}/{obj.sprint_speed} S:{obj.swimming_speed}"


@admin.register(RaceAttributeLimit)
class RaceAttributeLimitAdmin(admin.ModelAdmin):
    """Admin configuration for race attribute limits."""

    list_display = ("race", "attribute", "min_value", "max_value")
    search_fields = ("race__name", "attribute__name")
    list_filter = ("race", "attribute")
    ordering = ("race", "attribute")
    autocomplete_fields = ("race", "attribute")
    list_select_related = ("race", "attribute")


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    """Admin configuration for characters."""

    list_display = (
        "id",
        "name",
        "owner",
        "race",
        "gender",
        "overall_experience",
        "current_experience",
        "current_damage",
        "money",
        "is_archived",
    )
    list_display_links = ("name",)
    search_fields = (
        "name",
        "owner__username",
        "owner__email",
        "race__name",
        "country_of_origin",
        "religion",
    )
    list_filter = ("race", "gender", "is_archived")
    ordering = ("name",)
    readonly_fields = ("id", "last_opened_at")
    fieldsets = (
        ("Basis", {"fields": ("id", "owner", "name", "race", "gender", "age")}),
        (
            "Körper & Herkunft",
            {"fields": ("height", "weight", "skin_color", "hair_color", "eye_color", "country_of_origin")},
        ),
        ("Weitere Angaben", {"fields": ("religion", "appearance")}),
        ("Status", {"fields": ("current_damage", "money", "overall_experience", "current_experience")}),
        (
            "Fame & Ranks",
            {"fields": ("personal_fame_point", "personal_fame_rank", "sacrifice_rank", "artefact_rank")},
        ),
        ("Archive", {"fields": ("is_archived", "last_opened_at")}),
    )
    inlines = (
        CharacterAttributeInline,
        CharacterSkillInline,
        CharacterSchoolInline,
        CharacterSchoolPathInline,
        CharacterTechniqueInline,
        CharacterTechniqueChoiceInline,
        CharacterItemInline,
        CharacterTraitInline,
        CharacterLanguageInline,
        CharacterDiaryEntryInline,
    )
    autocomplete_fields = ("owner", "race")
    list_select_related = ("owner", "race")

    def get_urls(self):
        """Expose lightweight admin API endpoints for inline trait metadata."""
        custom_urls = [
            path(
                "trait-meta/<int:trait_id>/",
                self.admin_site.admin_view(self.trait_meta_view),
                name="charsheet_character_trait_meta",
            )
        ]
        return custom_urls + super().get_urls()

    def trait_meta_view(self, request, trait_id):
        """Return selected trait metadata for inline display updates."""
        try:
            trait = Trait.objects.only("min_level", "max_level", "points_per_level").get(pk=trait_id)
        except Trait.DoesNotExist:
            return JsonResponse({"error": "Trait not found"}, status=404)

        return JsonResponse(
            {
                "min_level": trait.min_level,
                "max_level": trait.max_level,
                "points_per_level": trait.points_per_level,
            }
        )


@admin.register(CharacterAttribute)
class CharacterAttributeAdmin(admin.ModelAdmin):
    """Admin configuration for character attributes."""

    list_display = ("character", "attribute", "base_value")
    search_fields = ("character__name", "attribute__name")
    list_filter = ("attribute",)
    ordering = ("character", "attribute")
    autocomplete_fields = ("character", "attribute")
    list_select_related = ("character", "attribute")


@admin.register(CharacterSkill)
class CharacterSkillAdmin(admin.ModelAdmin):
    """Admin configuration for character skills."""

    list_display = ("character", "skill", "skill_category", "skill_attribute", "level")
    search_fields = ("character__name", "skill__name", "skill__slug")
    list_filter = ("skill__category", "skill__attribute")
    ordering = ("character", "skill")
    autocomplete_fields = ("character", "skill")
    list_select_related = ("character", "skill", "skill__category", "skill__attribute")

    @admin.display(ordering="skill__category__name", description="Skill Category")
    def skill_category(self, obj):
        """Return the related skill category for list display."""
        return obj.skill.category

    @admin.display(ordering="skill__attribute__name", description="Skill Attribute")
    def skill_attribute(self, obj):
        """Return the related skill attribute for list display."""
        return obj.skill.attribute


@admin.register(SchoolType)
class SchoolTypeAdmin(admin.ModelAdmin):
    """Admin configuration for school types."""

    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (SchoolInline, ProgressionRuleInline)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    """Admin configuration for schools."""

    list_display = ("name", "type", "type_slug")
    search_fields = ("name", "type__name", "type__slug")
    list_filter = ("type",)
    ordering = ("type", "name")
    inlines = (SchoolPathInline, TechniqueInline, SchoolCharacterInline, ModifierInline)
    autocomplete_fields = ("type",)
    list_select_related = ("type",)

    @admin.display(ordering="type__slug", description="Type Slug")
    def type_slug(self, obj):
        """Return the related school type slug for list display."""
        return obj.type.slug


@admin.register(CharacterSchool)
class CharacterSchoolAdmin(admin.ModelAdmin):
    """Admin configuration for character schools."""

    list_display = ("character", "school", "school_type", "level")
    search_fields = ("character__name", "school__name", "school__type__name")
    list_filter = ("school__type", "school")
    ordering = ("character", "school")
    autocomplete_fields = ("character", "school")
    list_select_related = ("character", "school", "school__type")

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the related school type for list display."""
        return obj.school.type


@admin.register(ProgressionRule)
class ProgressionRuleAdmin(admin.ModelAdmin):
    """Admin configuration for progression rules."""

    list_display = ("school_type", "min_level", "grant_kind", "amount")
    search_fields = ("school_type__name", "grant_kind")
    list_filter = ("school_type", "grant_kind")
    ordering = ("school_type", "min_level")
    autocomplete_fields = ("school_type",)
    list_select_related = ("school_type",)


@admin.register(Modifier)
class ModifierAdmin(admin.ModelAdmin):
    """Admin configuration for generic modifiers."""

    list_display = (
        "display_source",
        "mode",
        "target_kind",
        "target_slug",
        "value",
        "scale_source",
        "scale_school",
        "mul",
        "div",
        "round_mode",
        "cap_mode",
        "cap_source",
        "min_school_level",
    )
    list_filter = ("source_content_type", "mode", "target_kind", "scale_source", "cap_mode")
    search_fields = ("target_slug",)
    ordering = ("source_content_type", "source_object_id", "target_kind", "target_slug")
    autocomplete_fields = ("scale_school",)

    @admin.display(description="Source")
    def display_source(self, obj):
        """Render a readable source label and detect broken generic relations."""
        if obj.source is None:
            return f"{obj.source_content_type} #{obj.source_object_id} (missing)"
        return str(obj.source)


@admin.register(Technique)
class TechniqueAdmin(admin.ModelAdmin):
    """Admin configuration for techniques, including support and choice metadata."""

    list_display = (
        "name",
        "school",
        "school_type",
        "path",
        "level",
        "technique_type",
        "acquisition_type",
        "support_level",
        "choice_marker",
        "choice_group",
        "choice_target_kind",
        "choice_limit",
        "choice_bonus_value",
        "action_type",
        "usage_type",
        "activation_cost",
        "activation_cost_resource",
    )
    search_fields = (
        "name",
        "school__name",
        "school__type__name",
        "choice_group",
        "selection_notes",
        "description",
    )
    list_filter = (
        "school",
        "school__type",
        "path",
        "level",
        "technique_type",
        "acquisition_type",
        "support_level",
        "is_choice_placeholder",
        "choice_target_kind",
        "action_type",
        "usage_type",
    )
    ordering = ("school", "level", "name")
    autocomplete_fields = ("school", "path")
    list_select_related = ("school", "school__type", "path")
    inlines = (TechniqueRequirementInline, TechniqueExclusionInline, ModifierInline)
    fieldsets = (
        (
            "Technique",
            {
                "fields": (
                    ("school", "path"),
                    ("name", "level"),
                    "description",
                )
            },
        ),
        (
            "Classification",
            {
                "fields": (
                    ("technique_type", "acquisition_type"),
                    "support_level",
                )
            },
        ),
        (
            "Choice Handling",
            {
                "fields": (
                    "is_choice_placeholder",
                    "choice_group",
                    "selection_notes",
                    ("choice_target_kind", "choice_limit"),
                    "choice_bonus_value",
                )
            },
        ),
        (
            "Activation",
            {
                "fields": (
                    ("action_type", "usage_type"),
                    ("activation_cost", "activation_cost_resource"),
                )
            },
        ),
    )

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the related school type for list display."""
        return obj.school.type

    @admin.display(boolean=True, description="Choice")
    def choice_marker(self, obj):
        """Flag choice rows and editorial choice-group metadata without adding rule logic."""
        return bool(obj.is_choice_placeholder or obj.choice_group)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin configuration for items."""

    list_display = ("name", "item_type", "price", "stackable")
    search_fields = ("name", "item_type")
    list_filter = ("item_type", "stackable")
    ordering = ("item_type", "name")
    inlines = (ArmorStatsInline, WeaponStatsInline, ItemCharacterInline)


@admin.register(CharacterItem)
class CharacterItemAdmin(admin.ModelAdmin):
    """Admin configuration for character inventory entries."""

    list_display = ("owner", "owner_race", "item", "item_type", "amount", "equipped")
    search_fields = ("owner__name", "item__name")
    list_filter = ("equipped", "item__item_type", "owner__race")
    ordering = ("owner", "item")
    autocomplete_fields = ("owner", "item")
    list_select_related = ("owner", "owner__race", "item")

    @admin.display(ordering="owner__race__name", description="Owner Race")
    def owner_race(self, obj):
        """Return the owning character race for list display."""
        return obj.owner.race

    @admin.display(ordering="item__item_type", description="Item Type")
    def item_type(self, obj):
        """Return the related item type for list display."""
        return obj.item.item_type


@admin.register(ArmorStats)
class ArmorStatsAdmin(admin.ModelAdmin):
    """Admin configuration for armor stat blocks."""

    list_display = ("item", "rs_total", "rs_zone_sum", "rs_zone_average")
    search_fields = ("item__name",)
    ordering = ("item__name",)
    autocomplete_fields = ("item",)
    list_select_related = ("item",)

    @admin.display(description="Zone Sum")
    def rs_zone_sum(self, obj):
        """Return summed zone armor values for list display."""
        return obj.rs_sum()

    @admin.display(description="Zone Avg")
    def rs_zone_average(self, obj):
        """Return average per-zone armor value for list display."""
        return obj.rs_sum() // 6


@admin.register(SchoolPath)
class SchoolPathAdmin(admin.ModelAdmin):
    """Admin configuration for school specialization paths."""

    list_display = ("name", "school", "school_type")
    search_fields = ("name", "school__name", "school__type__name")
    list_filter = ("school__type", "school")
    ordering = ("school", "name")
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the linked school type for list display."""
        return obj.school.type


@admin.register(CharacterSchoolPath)
class CharacterSchoolPathAdmin(admin.ModelAdmin):
    """Admin configuration for chosen character school paths."""

    list_display = ("character", "school", "school_type", "path")
    search_fields = ("character__name", "school__name", "school__type__name", "path__name")
    list_filter = ("school__type", "school", "path")
    ordering = ("character", "school", "path")
    autocomplete_fields = ("character", "school", "path")
    list_select_related = ("character", "school", "school__type", "path")

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the linked school type for list display."""
        return obj.school.type


@admin.register(CharacterTechnique)
class CharacterTechniqueAdmin(admin.ModelAdmin):
    """Admin configuration for explicitly learned character techniques."""

    list_display = (
        "character",
        "technique",
        "technique_school",
        "technique_path",
        "technique_level",
        "technique_support_level",
        "learned_at",
    )
    search_fields = (
        "character__name",
        "technique__name",
        "technique__school__name",
        "technique__path__name",
        "technique__choice_group",
        "technique__selection_notes",
    )
    list_filter = (
        "technique__school__type",
        "technique__school",
        "technique__path",
        "technique__level",
        "technique__support_level",
        "technique__is_choice_placeholder",
    )
    ordering = ("character", "technique__school", "technique__level", "technique__name")
    autocomplete_fields = ("character", "technique")
    list_select_related = ("character", "technique", "technique__school", "technique__school__type", "technique__path")

    @admin.display(ordering="technique__school__name", description="School")
    def technique_school(self, obj):
        """Return the technique's school for list display."""
        return obj.technique.school

    @admin.display(ordering="technique__path__name", description="Path")
    def technique_path(self, obj):
        """Return the linked school path if present."""
        return obj.technique.path or "-"

    @admin.display(ordering="technique__level", description="Level")
    def technique_level(self, obj):
        """Return the technique's minimum school level."""
        return obj.technique.level

    @admin.display(ordering="technique__support_level", description="Support")
    def technique_support_level(self, obj):
        """Return how strongly the engine supports the chosen technique."""
        return obj.technique.support_level


@admin.register(CharacterTechniqueChoice)
class CharacterTechniqueChoiceAdmin(admin.ModelAdmin):
    """Admin configuration for persistent character technique choices."""

    list_display = (
        "character",
        "technique",
        "technique_school",
        "technique_level",
        "choice_target_kind",
        "technique_choice_context",
        "selected_skill",
        "selected_skill_family",
    )
    search_fields = (
        "character__name",
        "technique__name",
        "technique__school__name",
        "selected_skill__name",
        "selected_skill_family__name",
    )
    list_filter = (
        "technique__school__type",
        "technique__school",
        "technique__choice_target_kind",
    )
    ordering = ("character", "technique__school", "technique__level", "technique__name")
    autocomplete_fields = ("character", "technique", "selected_skill", "selected_skill_family")
    list_select_related = (
        "character",
        "technique",
        "technique__school",
        "technique__school__type",
        "selected_skill",
        "selected_skill_family",
    )
    fieldsets = (
        (
            "Choice",
            {
                "fields": (
                    ("character", "technique"),
                    ("technique_level", "choice_target_kind"),
                    "technique_choice_context",
                    ("selected_skill", "selected_skill_family"),
                )
            },
        ),
    )

    readonly_fields = ("technique_level", "choice_target_kind", "technique_choice_context")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit technique selection to real choice techniques in the dedicated admin."""
        if db_field.name == "technique":
            kwargs["queryset"] = Technique.objects.exclude(
                choice_target_kind=Technique.ChoiceTargetKind.NONE
            ).select_related("school", "path")
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "selected_skill_family":
            return _label_skill_family_field(formfield)
        return formfield

    @admin.display(ordering="technique__school__name", description="School")
    def technique_school(self, obj):
        """Return the school that owns the selected technique."""
        return obj.technique.school

    @admin.display(ordering="technique__level", description="Level")
    def technique_level(self, obj):
        """Return the required school level of the selected technique."""
        return obj.technique.level

    @admin.display(ordering="technique__choice_target_kind", description="Target")
    def choice_target_kind(self, obj):
        """Return which persistent target kind the technique expects."""
        return obj.technique.choice_target_kind

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Return editor-facing guidance for persistent technique choices."""
        return _format_technique_choice_context(obj.technique)


@admin.register(TechniqueRequirement)
class TechniqueRequirementAdmin(admin.ModelAdmin):
    """Admin configuration for structured technique requirements."""

    list_display = ("technique", "requirement_kind", "requirement_value")
    search_fields = (
        "technique__name",
        "required_technique__name",
        "required_path__name",
        "required_skill__name",
        "required_trait__name",
    )
    list_filter = ("technique__school__type", "technique__school")
    ordering = ("technique__school", "technique__level", "technique__name")
    autocomplete_fields = ("technique", "required_technique", "required_path", "required_skill", "required_trait")
    list_select_related = (
        "technique",
        "technique__school",
        "technique__school__type",
        "required_technique",
        "required_path",
        "required_skill",
        "required_trait",
    )

    @admin.display(description="Requirement Type")
    def requirement_kind(self, obj):
        """Render the active requirement type for quick scanning."""
        if obj.minimum_school_level is not None:
            return "School Level"
        if obj.required_technique_id:
            return "Technique"
        if obj.required_path_id:
            return "School Path"
        if obj.required_skill_id:
            return "Skill"
        if obj.required_trait_id:
            return "Trait"
        return "-"

    @admin.display(description="Requirement Value")
    def requirement_value(self, obj):
        """Render the linked requirement payload compactly."""
        if obj.minimum_school_level is not None:
            return obj.minimum_school_level
        if obj.required_technique_id:
            return obj.required_technique
        if obj.required_path_id:
            return obj.required_path
        if obj.required_skill_id:
            return f"{obj.required_skill} {obj.required_skill_level}+"
        if obj.required_trait_id:
            return f"{obj.required_trait} {obj.required_trait_level}+"
        return "-"


@admin.register(TechniqueExclusion)
class TechniqueExclusionAdmin(admin.ModelAdmin):
    """Admin configuration for mutually exclusive techniques."""

    list_display = ("technique", "technique_school", "excluded_technique", "excluded_school")
    search_fields = (
        "technique__name",
        "technique__school__name",
        "excluded_technique__name",
        "excluded_technique__school__name",
    )
    list_filter = ("technique__school__type", "technique__school", "excluded_technique__school")
    ordering = ("technique__school", "technique__name", "excluded_technique__name")
    autocomplete_fields = ("technique", "excluded_technique")
    list_select_related = (
        "technique",
        "technique__school",
        "technique__school__type",
        "excluded_technique",
        "excluded_technique__school",
    )

    @admin.display(ordering="technique__school__name", description="Technique School")
    def technique_school(self, obj):
        """Return the source technique school for list display."""
        return obj.technique.school

    @admin.display(ordering="excluded_technique__school__name", description="Excluded School")
    def excluded_school(self, obj):
        """Return the excluded technique school for list display."""
        return obj.excluded_technique.school


@admin.register(DamageSource)
class DamageSourceAdmin(admin.ModelAdmin):
    """Admin configuration for weapon damage source definitions."""
    list_display = ("name", "short_name", "slug")
    search_fields = ("name", "short_name", "slug")
    ordering = ("name",)
    inlines = (WeaponStatsByDamageSourceInline,)


@admin.register(WeaponStats)
class WeaponStatsAdmin(admin.ModelAdmin):
    """Admin configuration for weapon stat records."""
    list_display = ("item", "damage", "two_handed_damage", "damage_source", "min_st", "size_class", "two_handed")
    search_fields = ("item__name", "damage_source__name")
    ordering = ("item__name",)
    autocomplete_fields = ("item", "damage_source")
    list_select_related = ("item", "damage_source")

@admin.register(Trait)
class TraitAdmin(admin.ModelAdmin):
    """Admin configuration for traits and their level boundaries."""
    list_display = ("name", "slug", "trait_type","min_level", "max_level", "points_per_level")
    search_fields = ("name", "slug")
    list_filter = ("trait_type",)
    ordering = ("trait_type", "name")
    inlines = (ModifierInline, TraitCharacterInline)
    
@admin.register(CharacterTrait)
class CharacterTraitAdmin(admin.ModelAdmin):
    """Admin configuration for character-owned trait levels."""
    list_display = ("owner", "trait", "trait_type", "trait_level")
    list_filter = ("trait__trait_type",)
    search_fields = ("owner__name", "trait__name", "trait__slug")
    autocomplete_fields = ("owner", "trait")
    list_select_related = ("owner", "trait")

    @admin.display(ordering="trait__trait_type", description="Trait Type")
    def trait_type(self, obj):
        """Return trait category for list display and sorting."""
        return obj.trait.trait_type


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    """Admin configuration for language definitions."""
    list_display = ("name", "slug", "max_level")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (LanguageCharacterInline,)


@admin.register(CharacterLanguage)
class CharacterLanguageAdmin(admin.ModelAdmin):
    """Admin configuration for character language proficiency entries."""
    list_display = ("owner", "language", "levels", "can_write", "is_mother_tongue")
    search_fields = ("owner__name", "language__name", "language__slug")
    list_filter = ("can_write", "is_mother_tongue", "language")
    ordering = ("owner", "language")
    autocomplete_fields = ("owner", "language")
    list_select_related = ("owner", "language")


@admin.register(CharacterDiaryEntry)
class CharacterDiaryEntryAdmin(admin.ModelAdmin):
    """Admin configuration for persisted diary roll entries."""

    list_display = ("character", "order_index", "entry_date", "is_fixed", "updated_at")
    search_fields = ("character__name", "text")
    list_filter = ("is_fixed", "entry_date")
    ordering = ("character", "order_index", "id")
    autocomplete_fields = ("character",)
    list_select_related = ("character",)
