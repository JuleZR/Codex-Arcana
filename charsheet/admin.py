"""Django admin configuration for character sheet domain models."""

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.http import JsonResponse
from django.urls import path, reverse

from .models import (
    ArmorStats,
    Attribute,
    Character,
    CharacterAttribute,
    CharacterItem,
    CharacterSchool,
    CharacterSkill,
    Item,
    Modifier,
    ProgressionRule,
    Race,
    RaceAttributeLimit,
    School,
    SchoolType,
    Skill,
    SkillCategory,
    Technique,
    Trait,
    CharacterTrait,
    DamageSource,
    WeaponStats,
)


class SkillInline(admin.TabularInline):
    """Inline editor for skills within a category."""

    model = Skill
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class RaceAttributeLimitInline(admin.TabularInline):
    """Inline editor for race-specific attribute limits."""

    model = RaceAttributeLimit
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class ModifierInline(GenericTabularInline):
    """Generic inline editor for modifiers attached to source models."""

    model = Modifier
    ct_field = "source_content_type"
    ct_fk_field = "source_object_id"
    extra = 0
    show_change_link = True
    fields = (
        "target_kind",
        "target_slug",
        "mode",
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
    extra = 0
    max_num = 1
    can_delete = True


class WeaponStatsInline(admin.StackedInline):
    """Inline editor for one-to-one weapon stats on an item."""

    model = WeaponStats
    extra = 0
    max_num = 1
    can_delete = True
    autocomplete_fields = ("damage_source",)


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
        js = ("charsheet/js/character_trait_inline.js",)


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


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    """Admin configuration for attributes."""

    list_display = ("name", "short_name")
    search_fields = ("name", "short_name")
    ordering = ("name",)
    inlines = (SkillInline, RaceAttributeLimitByAttributeInline, AttributeCharacterInline)


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    """Admin configuration for skill categories."""

    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (SkillInline,)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    """Admin configuration for skills."""

    list_display = ("name", "slug", "category", "category_slug", "attribute", "attribute_short_name")
    search_fields = ("name", "slug")
    list_filter = ("category", "attribute")
    ordering = ("category", "name")
    autocomplete_fields = ("category", "attribute")
    list_select_related = ("category", "attribute")
    inlines = (SkillCharacterInline,)

    @admin.display(ordering="category__slug", description="Category Slug")
    def category_slug(self, obj):
        """Return the related category slug for list display."""
        return obj.category.slug

    @admin.display(ordering="attribute__short_name", description="Attribute Short")
    def attribute_short_name(self, obj):
        """Return the related attribute short name for list display."""
        return obj.attribute.short_name


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    """Admin configuration for races."""

    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    ordering = ("name",)
    inlines = (RaceAttributeLimitInline, ModifierInline)


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
        "age",
        "country_of_origin",
        "race_slug",
    )
    search_fields = (
        "name",
        "owner__username",
        "owner__email",
        "race__name",
        "country_of_origin",
        "religion",
    )
    list_filter = ("race", "gender")
    ordering = ("name",)
    readonly_fields = ("id",)
    fieldsets = (
        ("Basis", {"fields": ("id", "owner", "name", "race", "gender", "age")}),
        (
            "Körper & Herkunft",
            {"fields": ("height", "weight", "skin_color", "hair_color", "eye_color", "country_of_origin")},
        ),
        ("Weitere Angaben", {"fields": ("religion", "appearance", "current_damage")}),
    )
    inlines = (
        CharacterAttributeInline,
        CharacterSkillInline,
        CharacterSchoolInline,
        CharacterItemInline,
        CharacterTraitInline,
    )
    autocomplete_fields = ("owner", "race")
    list_select_related = ("owner", "race")

    @admin.display(ordering="race__slug", description="Race Slug")
    def race_slug(self, obj):
        """Return the related race slug for list display."""
        return obj.race.slug

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

    list_display = ("name", "slug", "type", "type_slug")
    search_fields = ("name", "slug", "type__name")
    list_filter = ("type",)
    ordering = ("type", "name")
    inlines = (TechniqueInline, SchoolCharacterInline, ModifierInline)
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
    search_fields = ("character__name", "school__name", "school__slug")
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
    """Admin configuration for techniques."""

    list_display = ("name", "slug", "school", "school_type", "level")
    search_fields = ("name", "slug", "school__name", "school__slug")
    list_filter = ("school", "school__type", "level")
    ordering = ("school", "level", "name")
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")
    inlines = (ModifierInline,)

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the related school type for list display."""
        return obj.school.type


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin configuration for items."""

    list_display = ("name", "slug", "item_type", "stackable")
    search_fields = ("name", "slug", "item_type")
    list_filter = ("item_type", "stackable")
    ordering = ("item_type", "name")
    inlines = (ArmorStatsInline, WeaponStatsInline, ItemCharacterInline)


@admin.register(CharacterItem)
class CharacterItemAdmin(admin.ModelAdmin):
    """Admin configuration for character inventory entries."""

    list_display = ("owner", "owner_race", "item", "item_type", "amount", "equipped")
    search_fields = ("owner__name", "item__name", "item__slug")
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

    list_display = ("item", "item_slug", "rs_head", "rs_torso", "rs_arm_left", "rs_arm_right", "rs_leg_left", "rs_leg_right")
    search_fields = ("item__name", "item__slug")
    ordering = ("item__name",)
    autocomplete_fields = ("item",)
    list_select_related = ("item",)

    @admin.display(ordering="item__slug", description="Item Slug")
    def item_slug(self, obj):
        """Return the related item slug for list display."""
        return obj.item.slug


@admin.register(DamageSource)
class DamageSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "slug")
    search_fields = ("name", "short_name", "slug")
    ordering = ("name",)
    inlines = (WeaponStatsByDamageSourceInline,)


@admin.register(WeaponStats)
class WeaponStatsAdmin(admin.ModelAdmin):
    list_display = ("item", "item_slug", "damage", "damage_source", "min_st")
    search_fields = ("item__name", "item__slug", "damage_source__name")
    ordering = ("item__name",)
    autocomplete_fields = ("item", "damage_source")
    list_select_related = ("item", "damage_source")

    @admin.display(ordering="item__slug", description="Item Slug")
    def item_slug(self, obj):
        return obj.item.slug

@admin.register(Trait)
class TraitAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "trait_type","min_level", "max_level", "points_per_level")
    search_fields = ("name", "slug")
    list_filter = ("trait_type",)
    ordering = ("trait_type", "name")
    inlines = (ModifierInline, TraitCharacterInline)
    
@admin.register(CharacterTrait)
class CharacterTraitAdmin(admin.ModelAdmin):
    list_display = ("owner", "trait", "trait_type", "trait_level")
    list_filter = ("trait__trait_type",)
    search_fields = ("owner__name", "trait__name", "trait__slug")
    autocomplete_fields = ("owner", "trait")

    def trait_type(self, obj):
        return obj.trait.trait_type
