"""Django admin configuration for character sheet domain models."""

from collections import defaultdict
from copy import deepcopy

from django.contrib import admin
from django.contrib.admin.helpers import ActionForm
from django.contrib.contenttypes.admin import GenericStackedInline
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Q
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .constants import ONE_HANDED, QUALITY_COLOR_MAP, SCHOOL_ARCANE, TWO_HANDED, VERSATILE
from .admin_help import (
    ATTRIBUTE_CHOICE_HELP,
    CHARACTER_CHOICE_HELP,
    ITEM_CHOICE_HELP,
    MODIFIER_CHOICE_HELP,
    MODIFIER_LABELS,
    PROGRESSION_RULE_CHOICE_HELP,
    RACE_ADMIN_LABELS,
    RACE_CHOICE_DEFINITION_HELP,
    RACE_CHOICE_DEFINITION_LABELS,
    SCHOOL_ADMIN_LABELS,
    SCHOOL_TYPE_CHOICE_HELP,
    SHIELD_CHOICE_HELP,
    SIZE_CLASS_HELP,
    SKILL_CATEGORY_CHOICE_HELP,
    SPECIALIZATION_CHOICE_HELP,
    SPECIALIZATION_LABELS,
    TECHNIQUE_CHOICE_BLOCK_HELP,
    TECHNIQUE_CHOICE_BLOCK_LABELS,
    TECHNIQUE_CHOICE_DEFINITION_HELP,
    TECHNIQUE_CHOICE_HELP,
    TECHNIQUE_LABELS,
    TRAIT_CHOICE_HELP,
    WEAPON_CHOICE_HELP,
)
from .engine.item_engine import ItemEngine
from .modifiers.legacy import LegacyModifierAdapter
from .modifiers.registry import build_creature_trait_semantic_modifiers, build_trait_semantic_modifiers
from .models import (
    ArmorStats,
    Aspect,
    Attribute,
    Character,
    CharacterAspect,
    CharacterAttribute,
    CharacterCreature,
    CharacterCreatureCard,
    CharacterCreatureCardAttack,
    CharacterCreatureCardCommand,
    CharacterCreatureCardCommandPrerequisite,
    CharacterCreatureCardSkill,
    CharacterCreatureCardTrait,
    CharacterCreatureItem,
    CharacterCreatureSkill,
    CharacterCreatureSpecialSkill,
    CharacterCreatureTrait,
    CharacterCreatureTraitChoice,
    CharacterCreationDraft,
    CharacterDruidCult,
    CharacterDivineEntity,
    CharacterShamanPatron,
    CharacterDiaryEntry,
    CharacterItem,
    ItemRune,
    CharacterLanguage,
    CharacterRaceChoice,
    CharacterSchool,
    CharacterSchoolPath,
    CharacterSpecialization,
    CharacterSkill,
    CharacterSpell,
    CharacterSpellSource,
    CharacterTechnique,
    CharacterTechniqueChoice,
    CharacterTrait,
    CharacterTraitChoice,
    CharacterWeaponMastery,
    CharacterWeaponMasteryArcana,
    Creature,
    CreatureAttack,
    CreatureAttribute,
    CreatureCardBinding,
    CreatureCommand,
    CreatureCommandPrerequisite,
    CreatureCommandReference,
    CreatureSkill,
    CreatureSpecialSkill,
    CreatureSpecialSkillValue,
    CreatureTrait,
    CreatureTraitChoice,
    CreatureTraitChoiceDefinition,
    CreatureTraitDefinition,
    CreatureTraitSemanticEffect,
    DamageSource,
    DivineEntity,
    DivineEntityAspect,
    DruidCult,
    DruidCultAspect,
    Item,
    Language,
    MagicItemStats,
    Modifier,
    ProgressionRule,
    Quality,
    Race,
    RaceAttributeLimit,
    RaceChoiceDefinition,
    RaceStartingItem,
    RaceTechnique,
    School,
    SchoolPath,
    SchoolType,
    ShieldStats,
    ShamanPatron,
    Specialization,
    Spell,
    Skill,
    SkillCategory,
    Technique,
    TechniqueChoiceBlock,
    TechniqueChoiceDefinition,
    TechniqueExclusion,
    TechniqueRequirement,
    TechniqueSemanticEffect,
    Trait,
    TraitChoiceDefinition,
    TraitExclusion,
    TraitSemanticEffect,
    WeaponType,
    WeaponStats,
)
from .models.items import Rune, WeaponFlag
from .models.user import UserSettings

ArmorStats._meta.verbose_name = "Armor Stats"
ArmorStats._meta.verbose_name_plural = "Armor Stats"
ShieldStats._meta.verbose_name = "Shield Stats"
ShieldStats._meta.verbose_name_plural = "Shield Stats"
WeaponStats._meta.verbose_name = "Weapon Stats"
WeaponStats._meta.verbose_name_plural = "Weapon Stats"
MagicItemStats._meta.verbose_name = "Magic Item Stats"
MagicItemStats._meta.verbose_name_plural = "Magic Item Stats"

admin.site.site_header = "Codex Arcana Administration"
admin.site.site_title = "Codex Arcana Admin"
admin.site.index_title = "Regelwerk, Charaktere und Inhalte"

ADMIN_MODEL_ORDER = {
    "Character": 10,
    "CharacterCreationDraft": 11,
    "CharacterAttribute": 12,
    "CharacterSkill": 13,
    "CharacterSchool": 14,
    "CharacterSchoolPath": 15,
    "CharacterTechnique": 16,
    "CharacterTechniqueChoice": 17,
    "CharacterTrait": 18,
    "CharacterTraitChoice": 19,
    "CharacterRaceChoice": 20,
    "CharacterSpecialization": 21,
    "CharacterItem": 22,
    "ItemRune": 23,
    "CharacterLanguage": 24,
    "CharacterDiaryEntry": 25,
    "CharacterAspect": 26,
    "CharacterSpellSource": 27,
    "CharacterSpell": 28,
    "CharacterDivineEntity": 29,
    "CharacterDruidCult": 30,
    "CharacterShamanPatron": 31,
    "CharacterWeaponMastery": 32,
    "CharacterWeaponMasteryArcana": 33,
    "CharacterCreature": 34,
    "CharacterCreatureItem": 35,
    "CharacterCreatureSkill": 36,
    "CharacterCreatureSpecialSkill": 37,
    "CharacterCreatureTrait": 38,
    "Race": 40,
    "RaceAttributeLimit": 41,
    "RaceTechnique": 42,
    "RaceStartingItem": 43,
    "RaceChoiceDefinition": 44,
    "Creature": 45,
    "CreatureAttack": 46,
    "CreatureSkill": 47,
    "CreatureSpecialSkill": 48,
    "CreatureSpecialSkillValue": 49,
    "CreatureTrait": 50,
    "Attribute": 50,
    "SkillCategory": 51,
    "Skill": 52,
    "Language": 53,
    "Trait": 60,
    "TraitExclusion": 61,
    "TraitChoiceDefinition": 62,
    "Modifier": 70,
    "SchoolType": 80,
    "School": 81,
    "SchoolPath": 82,
    "ProgressionRule": 83,
    "TechniqueChoiceBlock": 84,
    "TechniqueChoiceDefinition": 85,
    "Technique": 86,
    "TechniqueRequirement": 87,
    "TechniqueExclusion": 88,
    "Specialization": 89,
    "Item": 100,
    "ArmorStats": 101,
    "ShieldStats": 102,
    "WeaponStats": 103,
    "MagicItemStats": 104,
    "DamageSource": 105,
    "WeaponFlag": 106,
    "Rune": 107,
    "Aspect": 120,
    "Spell": 121,
    "DivineEntity": 122,
    "DivineEntityAspect": 123,
    "DruidCult": 124,
    "DruidCultAspect": 125,
    "ShamanPatron": 126,
    "UserSettings": 140,
}

ADMIN_MODEL_SECTIONS = {
    "Character": (10, "Charaktere"),
    "CharacterCreationDraft": (11, "Charaktere"),
    "CharacterDiaryEntry": (12, "Charaktere"),
    "CharacterAttribute": (20, "Charakterwerte"),
    "CharacterSkill": (21, "Charakterwerte"),
    "CharacterLanguage": (22, "Charakterwerte"),
    "CharacterItem": (23, "Charakterwerte"),
    "CharacterTrait": (24, "Charakterwerte"),
    "CharacterSchool": (25, "Charakterwerte"),
    "CharacterSchoolPath": (26, "Charakterwerte"),
    "CharacterTechnique": (27, "Charakterwerte"),
    "CharacterTechniqueChoice": (28, "Charakterwerte"),
    "CharacterTraitChoice": (29, "Charakterwerte"),
    "CharacterRaceChoice": (30, "Charakterwerte"),
    "CharacterSpecialization": (31, "Charakterwerte"),
    "CharacterAspect": (32, "Charakterwerte"),
    "CharacterSpellSource": (33, "Charakterwerte"),
    "CharacterSpell": (34, "Charakterwerte"),
    "CharacterDivineEntity": (35, "Charakterwerte"),
    "CharacterDruidCult": (36, "Charakterwerte"),
    "CharacterShamanPatron": (37, "Charakterwerte"),
    "CharacterWeaponMastery": (38, "Charakterwerte"),
    "CharacterWeaponMasteryArcana": (39, "Charakterwerte"),
    "Race": (40, "Regelwerk: Herkunft"),
    "RaceAttributeLimit": (41, "Regelwerk: Herkunft"),
    "RaceTechnique": (42, "Regelwerk: Herkunft"),
    "RaceStartingItem": (43, "Regelwerk: Herkunft"),
    "RaceChoiceDefinition": (44, "Regelwerk: Herkunft"),
    "Attribute": (50, "Regelwerk: Grundlagen"),
    "SkillCategory": (51, "Regelwerk: Grundlagen"),
    "Skill": (52, "Regelwerk: Grundlagen"),
    "Language": (53, "Regelwerk: Grundlagen"),
    "Trait": (60, "Regelwerk: Traits"),
    "TraitExclusion": (61, "Regelwerk: Traits"),
    "TraitChoiceDefinition": (62, "Regelwerk: Traits"),
    "Modifier": (70, "Regelwerk: Engine"),
    "SchoolType": (80, "Regelwerk: Schulen"),
    "School": (81, "Regelwerk: Schulen"),
    "SchoolPath": (82, "Regelwerk: Schulen"),
    "ProgressionRule": (83, "Regelwerk: Schulen"),
    "TechniqueChoiceBlock": (84, "Regelwerk: Schulen"),
    "TechniqueChoiceDefinition": (85, "Regelwerk: Schulen"),
    "Technique": (86, "Regelwerk: Schulen"),
    "TechniqueRequirement": (87, "Regelwerk: Schulen"),
    "TechniqueExclusion": (88, "Regelwerk: Schulen"),
    "Specialization": (89, "Regelwerk: Schulen"),
    "Item": (100, "Items und Kampf"),
    "ArmorStats": (101, "Items und Kampf"),
    "ShieldStats": (102, "Items und Kampf"),
    "WeaponStats": (103, "Items und Kampf"),
    "MagicItemStats": (104, "Items und Kampf"),
    "DamageSource": (105, "Items und Kampf"),
    "WeaponFlag": (106, "Items und Kampf"),
    "Rune": (107, "Items und Kampf"),
    "Aspect": (120, "Magie und Goettliches"),
    "Spell": (121, "Magie und Goettliches"),
    "DivineEntity": (122, "Magie und Goettliches"),
    "DivineEntityAspect": (123, "Magie und Goettliches"),
    "DruidCult": (124, "Magie und Goettliches"),
    "DruidCultAspect": (125, "Magie und Goettliches"),
    "ShamanPatron": (126, "Magie und Goettliches"),
    "UserSettings": (140, "System"),
}

ADMIN_SECONDARY_MODELS = {
    "CharacterAttribute",
    "CharacterSkill",
    "CharacterSchool",
    "CharacterSchoolPath",
    "CharacterTechnique",
    "CharacterTechniqueChoice",
    "CharacterTrait",
    "CharacterTraitChoice",
    "CharacterRaceChoice",
    "CharacterSpecialization",
    "CharacterItem",
    "CharacterLanguage",
    "CharacterAspect",
    "CharacterSpellSource",
    "CharacterSpell",
    "CharacterDivineEntity",
    "CharacterDruidCult",
    "CharacterShamanPatron",
    "CharacterWeaponMastery",
    "CharacterWeaponMasteryArcana",
    "RaceAttributeLimit",
    "RaceTechnique",
    "RaceStartingItem",
    "RaceChoiceDefinition",
    "TraitExclusion",
    "TraitChoiceDefinition",
    "ProgressionRule",
    "TechniqueChoiceBlock",
    "TechniqueChoiceDefinition",
    "TechniqueRequirement",
    "TechniqueExclusion",
    "ArmorStats",
    "ShieldStats",
    "WeaponStats",
    "MagicItemStats",
    "DivineEntityAspect",
    "DruidCultAspect",
}

_default_get_app_list = admin.site.get_app_list


def _get_sorted_app_list(request, app_label=None):
    """Keep the admin index and sidebar in a domain-oriented order."""
    app_list = _default_get_app_list(request, app_label)
    for app in app_list:
        for model in app["models"]:
            object_name = model.get("object_name")
            section_rank, section_name = ADMIN_MODEL_SECTIONS.get(
                object_name,
                (999, "Weitere Bereiche"),
            )
            model["section_rank"] = section_rank
            model["section_name"] = section_name
            model["is_secondary"] = object_name in ADMIN_SECONDARY_MODELS
        app["models"].sort(
            key=lambda model: (
                1 if model.get("is_secondary") else 0,
                model.get("section_rank", 999),
                ADMIN_MODEL_ORDER.get(model.get("object_name"), 999),
                model.get("name", "").lower(),
            )
        )
    app_list.sort(key=lambda app: (0 if app.get("app_label") == "charsheet" else 1, app.get("name", "").lower()))
    return app_list


admin.site.get_app_list = _get_sorted_app_list


def _quality_badge(quality):
    """Render one quality tier with configured RPG color coding."""
    resolved_quality = ItemEngine.normalize_quality(quality)
    color = getattr(quality, "hex_color", None) or QUALITY_COLOR_MAP.get(
        resolved_quality,
        QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)],
    )
    label = getattr(quality, "name", None) or resolved_quality
    return format_html(
        (
            '<strong style="color:{};'
            "text-shadow:-0.75px -0.75px 0 #000,0.75px -0.75px 0 #000,"
            "-0.75px 0.75px 0 #000,0.75px 0.75px 0 #000;"
            '">{}</strong>'
        ),
        color,
        label,
    )


def _render_readonly_lines(lines, *, empty_text="-"):
    """Render a list of admin preview lines with compact HTML line breaks."""
    normalized = tuple((str(line),) for line in lines if str(line or "").strip())
    if not normalized:
        return format_html('<span style="color:#666;">{}</span>', empty_text)
    return format_html_join(mark_safe("<br>"), "{}", normalized)


def _modifier_preview_line(modifier):
    """Render one typed modifier in a compact human-readable form."""
    value = modifier.value
    if value is True:
        value_label = "true"
    elif value is False:
        value_label = "false"
    elif value in (None, ""):
        value_label = "-"
    else:
        value_label = str(value)
    return f"{modifier.target_domain}:{modifier.target_key} [{modifier.operator}] -> {value_label}"


def _trait_semantic_preview(trait, *, level: int | None = None):
    """Render semantic central-engine effects for one trait definition or ownership row."""
    if trait is None:
        return format_html('<span style="color:#666;">{}</span>', "-")
    resolved_level = max(1, int(level or getattr(trait, "min_level", 1) or 1))
    modifiers = build_trait_semantic_modifiers(trait_slug=trait.slug, level=resolved_level, trait=trait)
    if not modifiers:
        return format_html(
            '<span style="color:#666;">{}</span>',
            "No semantic effects configured yet. Add rows in the Semantic Effects section below.",
        )
    return _render_readonly_lines(_modifier_preview_line(modifier) for modifier in modifiers)


def _creature_trait_semantic_preview(trait, *, level: int | None = None):
    """Render semantic central-engine effects for one creature trait definition or ownership row."""
    if trait is None:
        return format_html('<span style="color:#666;">{}</span>', "-")
    resolved_level = max(1, int(level or getattr(trait, "min_level", 1) or 1))
    modifiers = build_creature_trait_semantic_modifiers(trait_slug=trait.slug, level=resolved_level, trait=trait)
    if not modifiers:
        return format_html(
            '<span style="color:#666;">{}</span>',
            "No semantic effects configured yet. Add rows in the Semantic Effects section below.",
        )
    return _render_readonly_lines(_modifier_preview_line(modifier) for modifier in modifiers)


def _trait_semantic_editing_path(trait):
    """Render where new-system trait effects are maintained."""
    if trait is None:
        return format_html('<span style="color:#666;">{}</span>', "-")
    if getattr(trait, "pk", None) is None:
        return _render_readonly_lines(
            (
                "Save the trait first.",
                "Then add rows in the Semantic Effects inline to define its new-system behavior.",
            )
        )
    effect_count = getattr(getattr(trait, "semantic_effects", None), "count", lambda: 0)()
    if effect_count:
        return _render_readonly_lines(
            (
                "This trait uses persisted semantic effects from the admin-managed Semantic Effects rows.",
                "Changes here are picked up directly by the new ModifierEngine.",
            )
        )
    return _render_readonly_lines(
        (
            "No persisted semantic effects are configured yet.",
            "Add rows in the Semantic Effects inline below to activate new-system behavior for this trait.",
        )
    )


def _trait_build_rule_preview(trait):
    """Render the current creation/build rule interpretation for one trait."""
    if trait is None:
        return format_html('<span style="color:#666;">{}</span>', "-")
    if getattr(trait, "pk", None) is None:
        rank_mode = "repeatable" if int(trait.max_level) > 1 else "single pick"
        if trait.trait_type == Trait.TraitType.ADV:
            cp_line = f"Costs {trait.cost_display()} during creation."
        else:
            cp_line = f"Refunds {trait.cost_display()} during creation and counts against the disadvantage cap."
        return _render_readonly_lines(
            (
                f"Allowed ranks: {trait.min_level} to {trait.max_level}.",
                cp_line,
                f"Selection mode: {rank_mode}.",
                "Save the trait first to configure or preview mutual exclusions.",
                "Creation-only trait logic is validated centrally in the CharacterCreationEngine.",
            )
        )
    rank_mode = "repeatable" if int(trait.max_level) > 1 else "single pick"
    excluded_traits = {relation.excluded_trait.name for relation in trait.exclusions.all()}
    excluded_traits.update(relation.trait.name for relation in trait.excluded_by.all())
    exclusion_line = (
        f"Mutually exclusive with: {', '.join(sorted(excluded_traits))}."
        if excluded_traits
        else "Mutually exclusive with: none."
    )
    if trait.trait_type == Trait.TraitType.ADV:
        cp_line = f"Costs {trait.cost_display()} during creation."
    else:
        cp_line = f"Refunds {trait.cost_display()} during creation and counts against the disadvantage cap."
    return _render_readonly_lines(
        (
            f"Allowed ranks: {trait.min_level} to {trait.max_level}.",
            cp_line,
            f"Selection mode: {rank_mode}.",
            exclusion_line,
            "Creation-only trait logic is validated centrally in the CharacterCreationEngine.",
        )
    )


def _merge_help_text(existing, extra):
    """Combine existing and additional help text without duplicating content."""
    existing = (existing or "").strip()
    extra = (extra or "").strip()
    if not extra:
        return existing
    if not existing:
        return extra
    if extra in existing:
        return existing
    return f"{existing} {extra}"


def _apply_help_texts(base_fields, help_texts):
    """Attach friendly help texts to matching form fields."""
    for field_name, text in (help_texts or {}).items():
        field = base_fields.get(field_name)
        if field is not None:
            field.help_text = _merge_help_text(field.help_text, text)


def _apply_field_labels(base_fields, labels):
    """Replace technical field labels with admin-friendly aliases."""
    for field_name, label in (labels or {}).items():
        field = base_fields.get(field_name)
        if field is not None:
            field.label = label


class ItemBulkActionForm(ActionForm):
    """Extra controls for item list bulk actions."""

    target_item_type = forms.ChoiceField(
        label="Neue Kategorie",
        required=False,
        choices=(("", "Kategorie wählen"), *Item.ItemType.choices),
    )


def _apply_monospace_description_fields(base_fields):
    """Render description-like text fields in monospace for easier rule text editing."""
    mono_stack = (
        "'Fira Code', 'Cascadia Code', 'Consolas', 'SFMono-Regular', "
        "'Liberation Mono', 'Courier New', monospace"
    )
    for field_name, field in (base_fields or {}).items():
        if "description" not in field_name.lower():
            continue
        widget = getattr(field, "widget", None)
        if widget is None:
            continue
        attrs = widget.attrs
        existing_style = (attrs.get("style") or "").strip()
        mono_style = f"font-family: {mono_stack};"
        if mono_stack not in existing_style:
            attrs["style"] = f"{existing_style} {mono_style}".strip()
        if field_name.lower() == "description":
            attrs.setdefault("rows", 6)


class AutoSlugAdminMixin:
    """Autofill slug fields from names on add forms with underscore-separated keys."""

    slug_source_field = "name"
    slug_target_field = "slug"

    class Media:
        js = ("charsheet/js/admin_slug_autofill.js",)

    def get_form(self, request, obj=None, change=False, **kwargs):
        """Attach lightweight slug-autofill metadata only while creating new records."""
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        if obj is not None:
            return form
        source_field = form.base_fields.get(self.slug_source_field)
        target_field = form.base_fields.get(self.slug_target_field)
        if source_field is None or target_field is None:
            return form
        target_field.widget.attrs["data-autoslug-source"] = self.slug_source_field
        return form


def _install_admin_help(admin_cls, *, help_texts=None, fieldset_descriptions=None, labels=None):
    """Patch a ModelAdmin so friendly help text appears in the Django admin."""
    if help_texts or labels:
        original_get_form = admin_cls.get_form

        def get_form(self, request, obj=None, change=False, **kwargs):
            form = original_get_form(self, request, obj, change=change, **kwargs)
            _apply_help_texts(form.base_fields, help_texts)
            _apply_field_labels(form.base_fields, labels)
            _apply_monospace_description_fields(form.base_fields)
            return form

        admin_cls.get_form = get_form

    if fieldset_descriptions:
        original_get_fieldsets = admin_cls.get_fieldsets

        def get_fieldsets(self, request, obj=None):
            fieldsets = deepcopy(original_get_fieldsets(self, request, obj))
            enriched = []
            for name, options in fieldsets:
                updated_options = dict(options)
                description = fieldset_descriptions.get(name)
                if description:
                    updated_options["description"] = _merge_help_text(
                        updated_options.get("description", ""),
                        description,
                    )
                enriched.append((name, updated_options))
            return enriched

        admin_cls.get_fieldsets = get_fieldsets


def _install_inline_help(inline_cls, *, help_texts=None, fieldset_descriptions=None, labels=None):
    """Patch an inline admin so friendly help text appears inside parent forms."""
    if help_texts or labels:
        original_get_formset = inline_cls.get_formset

        def get_formset(self, request, obj=None, **kwargs):
            formset = original_get_formset(self, request, obj, **kwargs)
            _apply_help_texts(formset.form.base_fields, help_texts)
            _apply_field_labels(formset.form.base_fields, labels)
            _apply_monospace_description_fields(formset.form.base_fields)
            return formset

        inline_cls.get_formset = get_formset

    if fieldset_descriptions:
        original_get_fieldsets = inline_cls.get_fieldsets

        def get_fieldsets(self, request, obj=None):
            fieldsets = deepcopy(original_get_fieldsets(self, request, obj))
            enriched = []
            for name, options in fieldsets:
                updated_options = dict(options)
                description = fieldset_descriptions.get(name)
                if description:
                    updated_options["description"] = _merge_help_text(
                        updated_options.get("description", ""),
                        description,
                    )
                enriched.append((name, updated_options))
            return enriched

        inline_cls.get_fieldsets = get_fieldsets


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


def _format_trait_choice_context(definition):
    """Return compact editor-facing guidance for a trait choice definition."""
    if definition is None:
        return "-"
    parts = [definition.description or definition.name]
    if definition.allowed_attribute_id:
        parts.append(f"Allowed Attribute: {definition.allowed_attribute.short_name}")
    if definition.allowed_skill_category_id:
        parts.append(f"Allowed Skill Category: {definition.allowed_skill_category.slug}")
    if definition.allowed_skill_family:
        parts.append(f"Allowed Skill Family: {definition.allowed_skill_family}")
    if definition.allowed_derived_stat:
        parts.append(f"Allowed Derived Stat: {definition.get_allowed_derived_stat_display()}")
    if definition.allowed_resource:
        parts.append(f"Allowed Resource: {definition.get_allowed_resource_display()}")
    if definition.allowed_proficiency_group:
        parts.append(f"Allowed Group: {definition.get_allowed_proficiency_group_display()}")
    return " | ".join(part for part in parts if part) or "-"


def _format_technique_requirements(technique):
    """Return readable rulebook-style requirement summaries for one technique."""
    rows = []
    for requirement in technique.requirements.all():
        if requirement.minimum_school_level is not None:
            rows.append(f"School Level {requirement.minimum_school_level}+")
        elif requirement.required_technique_id is not None:
            rows.append(f"Technique: {requirement.required_technique.name}")
        elif requirement.required_path_id is not None:
            rows.append(f"Path: {requirement.required_path.name}")
        elif requirement.required_skill_id is not None:
            rows.append(f"Skill: {requirement.required_skill.name} {requirement.required_skill_level}+")
        elif requirement.required_trait_id is not None:
            rows.append(f"Trait: {requirement.required_trait.name} {requirement.required_trait_level}+")
    return rows or ["None"]


def _format_technique_exclusions(technique):
    """Return readable names of excluded techniques."""
    rows = {relation.excluded_technique.name for relation in technique.exclusions.all()}
    rows.update(relation.technique.name for relation in technique.excluded_by.all())
    return sorted(rows) or ["None"]


def _format_technique_choice_definitions(technique):
    """Return readable summaries of stored choice requirements for one technique."""
    rows = []
    for definition in technique.choice_definitions.all():
        if not definition.is_active:
            continue
        if definition.min_choices != definition.max_choices:
            range_label = f"{definition.min_choices}-{definition.max_choices}"
        else:
            range_label = str(definition.max_choices)
        description = f" ({definition.description})" if definition.description else ""
        rows.append(f"{definition.name}: {definition.get_target_kind_display()} [{range_label}]{description}")
    if not rows and technique.choice_target_kind != Technique.ChoiceTargetKind.NONE:
        rows.append(
            f"Legacy Choice: {technique.get_choice_target_kind_display()} [{technique.choice_limit}]"
        )
    return rows or ["None"]


def _technique_source_label(technique, *, character=None):
    """Return a readable owning source for school and race techniques."""
    if technique is None:
        return "-"
    if technique.school_id:
        return technique.school.name
    if character is not None and getattr(character, "race_id", None):
        return f"Race: {character.race.name}"
    race_names = sorted(technique.race_links.values_list("race__name", flat=True).distinct())
    if race_names:
        return "Race: " + ", ".join(race_names)
    return "Race Technique"


def _format_choice_group_notice(technique):
    """Explain that choice_group is informational only."""
    if not technique or not technique.choice_group:
        return "-"
    return f"{technique.choice_group} (display/import metadata only, no rules logic)"


def _format_technique_rule_context_html(technique):
    """Render a compact rulebook-style preview for one technique."""
    if technique is None:
        return "-"
    rows = [
        ("Source", _technique_source_label(technique)),
        ("Level", technique.level),
        ("Path", technique.path.name if technique.path_id else "All Paths"),
        ("Acquisition", technique.get_acquisition_type_display()),
        ("Support", technique.get_support_level_display()),
        ("Requirements", ", ".join(_format_technique_requirements(technique))),
        ("Exclusions", ", ".join(_format_technique_exclusions(technique))),
        ("Choice Definitions", ", ".join(_format_technique_choice_definitions(technique))),
        ("Specialization Slots", technique.specialization_slot_grants or 0),
        ("choice_group", _format_choice_group_notice(technique)),
    ]
    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            "<div><strong>{}</strong>: {}</div>",
            ((label, value) for label, value in rows),
        ),
    )


def _format_school_rulebook_guide_html():
    """Show the recommended rulebook-oriented editing order for one school."""
    sections = (
        ("1. School", "Maintain the school's base data and short description."),
        ("2. School Paths", "Create optional paths for the school if the rules require them."),
        ("3. Techniques by Level", "Enter techniques in rulebook order: school -> level -> path -> technique."),
        ("4. Technique Requirements", "Store minimum levels, paths, techniques, skills, or traits on each technique."),
        ("5. Technique Exclusions", "Record which other techniques are excluded by each technique."),
        ("6. Technique Choices", "Store any persistent choices that still need to be made for a technique."),
        ("7. Specialization Slots", "Slots only come from actually learned techniques with specialization_slot_grants."),
        ("8. Specializations", "Maintain school-bound specializations separately; they are not techniques."),
    )
    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            "<div><strong>{}</strong>: {}</div>",
            sections,
        ),
    )


def _format_school_path_overview_html(school):
    """Summarize the configured paths of one school in rulebook terms."""
    if not school or not getattr(school, "pk", None):
        return "Configured school paths will appear here after the first save."

    path_rows = []
    for school_path in school.paths.all():
        technique_count = school.techniques.filter(path=school_path).count()
        block_count = school.technique_choice_blocks.filter(path=school_path).count()
        description = f" | {school_path.description}" if school_path.description else ""
        path_rows.append((school_path.name, technique_count, block_count, description))

    if not path_rows:
        return "No school paths configured."

    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            "<div><strong>{}</strong>: {} techniques, {} choice blocks{}</div>",
            path_rows,
        ),
    )


def _format_school_choice_block_overview_html(school):
    """Summarize school-level choice blocks so the rulebook structure is visible."""
    if not school or not getattr(school, "pk", None):
        return "Configured choice blocks will appear here after the first save."

    blocks = list(
        school.technique_choice_blocks.select_related("path").prefetch_related("techniques").order_by(
            "level",
            "sort_order",
            "name",
            "id",
        )
    )
    if not blocks:
        return "No choice blocks configured."

    block_rows = []
    for block in blocks:
        level = f"Level {block.level}" if block.level is not None else "no fixed level"
        path = block.path.name if block.path_id else "all paths"
        techniques = ", ".join(block.techniques.order_by("name").values_list("name", flat=True)) or "none yet"
        label = block.name or "Unnamed Choice Block"
        description = f" | {block.description}" if block.description else ""
        block_rows.append((label, level, path, block.min_choices, block.max_choices, techniques, description))

    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            (
                "<div><strong>{}</strong>: {} | Path: {} | Choice Range: {}-{} | "
                "Techniques: {}{}</div>"
            ),
            block_rows,
        ),
    )


def _format_school_technique_overview_html(school):
    """Render techniques grouped by level to mirror the rulebook reading order."""
    if not school or not getattr(school, "pk", None):
        return "Techniques grouped by school level will appear here after the first save."

    techniques = list(
        school.techniques.select_related("path", "choice_block")
        .prefetch_related(
            "requirements__required_technique",
            "requirements__required_path",
            "requirements__required_skill",
            "requirements__required_trait",
            "exclusions__excluded_technique",
            "excluded_by__technique",
            "choice_definitions",
        )
        .order_by("level", "path__name", "name")
    )
    if not techniques:
        return "No techniques configured."

    grouped_techniques = defaultdict(list)
    for technique in techniques:
        grouped_techniques[technique.level].append(technique)

    level_blocks = []
    for level in sorted(grouped_techniques):
        rows = []
        for technique in grouped_techniques[level]:
            path_name = technique.path.name if technique.path_id else "All Paths"
            choice_block = technique.choice_block.name if technique.choice_block_id and technique.choice_block.name else "-"
            rows.append(
                (
                    technique.name,
                    path_name,
                    technique.get_acquisition_type_display(),
                    choice_block,
                    ", ".join(_format_technique_requirements(technique)),
                    ", ".join(_format_technique_exclusions(technique)),
                    ", ".join(_format_technique_choice_definitions(technique)),
                    technique.specialization_slot_grants or 0,
                    technique.get_support_level_display(),
                )
            )

        level_blocks.append(
            format_html(
                "<div><h4 style='margin:0.75em 0 0.25em;'>Level {}</h4>{}</div>",
                level,
                format_html_join(
                    "",
                    (
                        "<div style='margin-left:1rem;'><strong>{}</strong>: Path {} | Acquisition {} | "
                        "Choice Block {} | Requirements {} | Exclusions {} | Choices {} | "
                        "Slots {} | Support {}</div>"
                    ),
                    rows,
                ),
            )
        )

    return format_html_join("", "{}", ((block,) for block in level_blocks))


def _format_school_specialization_overview_html(school):
    """Summarize school-bound specializations in a compact rulebook view."""
    if not school or not getattr(school, "pk", None):
        return "School specializations appear here after the first save."

    specializations = list(school.specializations.order_by("sort_order", "name"))
    if not specializations:
        return "No specializations configured."

    spec_rows = []
    for specialization in specializations:
        active_state = "active" if specialization.is_active else "inactive"
        description = f" | {specialization.description}" if specialization.description else ""
        spec_rows.append(
            (
                specialization.name,
                specialization.slug,
                specialization.get_support_level_display(),
                active_state,
                description,
            )
        )

    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            "<div><strong>{}</strong> ({}) : Support {} | {}{}</div>",
            spec_rows,
        ),
    )


class SkillInline(admin.TabularInline):
    """Inline editor for skills within a category."""

    model = Skill
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Return default foreign key form fields for skill inlines."""
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield


class InlineValidationSafeModelForm(forms.ModelForm):
    """Remap hidden-field model validation errors into inline form non-field errors."""

    def _update_errors(self, errors):
        """Keep admin inline POSTs user-facing even when model.clean targets omitted fields."""
        if hasattr(errors, "error_dict"):
            normalized_errors = {}
            for field_name, field_errors in errors.error_dict.items():
                target_field = field_name if field_name in self.fields else NON_FIELD_ERRORS
                normalized_errors.setdefault(target_field, []).extend(field_errors)
            errors = ValidationError(normalized_errors)
        return super()._update_errors(errors)


class RaceAttributeLimitInline(admin.TabularInline):
    """Inline editor for race-specific attribute limits."""

    model = RaceAttributeLimit
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class RaceTechniqueInline(admin.TabularInline):
    """Inline editor for techniques granted or linked by a race."""

    model = RaceTechnique
    extra = 0
    show_change_link = True
    autocomplete_fields = ("technique",)


class RaceStartingItemInline(admin.TabularInline):
    """Inline editor for race-based starter equipment."""

    model = RaceStartingItem
    extra = 0
    show_change_link = True
    autocomplete_fields = ("item",)
    fields = ("item", "amount", "quality")


class ItemRaceStartingInline(admin.TabularInline):
    """Inline editor for races that start with one item."""

    model = RaceStartingItem
    fk_name = "item"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("race",)
    fields = ("race", "amount", "quality")


class TechniqueRaceInline(admin.TabularInline):
    """Inline editor for race links on one technique."""

    model = RaceTechnique
    fk_name = "technique"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("race",)


class ModifierInline(GenericStackedInline):
    """Generic inline editor for modifiers attached to source models."""

    model = Modifier
    verbose_name_plural = "Rule Modifiers"
    ct_field = "source_content_type"
    ct_fk_field = "source_object_id"
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    readonly_fields = ("resolved_target_domain", "resolved_target_key", "central_engine_summary")
    fieldsets = (
        (
            "Target",
            {
                "fields": (
                    ("target_kind", "target_slug"),
                    ("target_skill", "target_skill_category"),
                    ("target_item", "target_specialization"),
                    ("target_choice_definition", "target_race_choice_definition"),
                    ("target_content_type", "target_object_id"),
                )
            },
        ),
        ("Value", {"fields": (("mode", "value"), "effect_description")}),
        ("Scaling", {"fields": (("scale_source", "scale_school", "scale_skill"), ("mul", "div", "round_mode"))}),
        ("Cap", {"fields": (("cap_mode", "cap_source"), "min_school_level")}),
        (
            "Central Engine Mapping",
            {
                "fields": (("resolved_target_domain", "resolved_target_key"), "central_engine_summary"),
                "description": (
                    "This editor still manages the legacy numeric modifier rows. "
                    "The central ModifierEngine adapts them at runtime into the new target domains."
                ),
            },
        ),
    )
    autocomplete_fields = (
        "scale_school",
        "scale_skill",
        "target_skill",
        "target_skill_category",
        "target_item",
        "target_specialization",
        "target_choice_definition",
        "target_race_choice_definition",
    )

    @admin.display(description="Central Domain")
    def resolved_target_domain(self, obj):
        """Show which new target domain the legacy row maps to."""
        if not obj or not getattr(obj, "pk", None):
            return "-"
        return LegacyModifierAdapter.adapt(obj).target_domain

    @admin.display(description="Central Key")
    def resolved_target_key(self, obj):
        """Show the central-engine target key produced by the legacy adapter."""
        if not obj or not getattr(obj, "pk", None):
            return "-"
        return LegacyModifierAdapter.adapt(obj).target_key

    @admin.display(description="Engine Summary")
    def central_engine_summary(self, obj):
        """Show how the central engine interprets the legacy row."""
        if not obj or not getattr(obj, "pk", None):
            return format_html('<span style="color:#666;">{}</span>', "Saved rows get central-engine details here.")
        return _render_readonly_lines((_modifier_preview_line(LegacyModifierAdapter.adapt(obj)),))


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
    verbose_name_plural = "School Paths"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("school", "path")


class CharacterTechniqueInline(admin.TabularInline):
    """Inline editor for a character's explicitly learned techniques."""

    model = CharacterTechnique
    verbose_name_plural = "Learned Techniques"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("technique",)
    fields = (
        "technique",
        "technique_school",
        "technique_level",
        "technique_support_level",
        "technique_has_specification",
        "technique_choice_context",
        "learned_at",
        "specification_value",
        "notes",
    )
    readonly_fields = (
        "technique_school",
        "technique_level",
        "technique_support_level",
        "technique_has_specification",
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
        return obj.technique.get_support_level_display()

    @admin.display(boolean=True, description="Spec?")
    def technique_has_specification(self, obj):
        """Show whether the linked technique expects a specification value."""
        if not obj or not obj.technique_id:
            return False
        return obj.technique.has_specification

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Show persistent choice guidance for the linked technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _format_technique_choice_context(obj.technique)


class CharacterTechniqueChoiceInline(admin.StackedInline):
    """Inline editor for persistent character technique choices."""

    model = CharacterTechniqueChoice
    verbose_name_plural = "Technique Choices"
    fk_name = "character"
    extra = 0
    show_change_link = True
    autocomplete_fields = (
        "technique",
        "definition",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    fieldsets = (
        (
            "Technique",
            {
                "fields": (
                    ("technique", "definition"),
                    ("technique_school", "choice_target_kind"),
                    "technique_choice_context",
                )
            },
        ),
        (
            "Selected Target",
            {
                "fields": (
                    ("selected_skill"),
                    ("selected_skill_category", "selected_specialization"),
                    ("selected_item", "selected_item_category"),
                    "selected_text",
                    ("selected_content_type", "selected_object_id"),
                )
            },
        ),
    )
    readonly_fields = ("technique_school", "choice_target_kind", "technique_choice_context")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit choice rows to techniques that persist explicit choices."""
        if db_field.name == "technique":
            kwargs["queryset"] = (
                Technique.objects.filter(
                    Q(choice_definitions__isnull=False)
                    | ~Q(choice_target_kind=Technique.ChoiceTargetKind.NONE),
                    school__isnull=False,
                )
                .select_related("school", "path")
                .distinct()
                .order_by("school__name", "level", "name")
            )
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield

    @admin.display(description="Source")
    def technique_school(self, obj):
        """Show the owning source of the selected technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _technique_source_label(obj.technique, character=obj.character)

    @admin.display(description="Target")
    def choice_target_kind(self, obj):
        """Show which persistent target type the technique expects."""
        if not obj or not obj.technique_id:
            return "-"
        if obj.definition_id:
            return obj.definition.get_target_kind_display()
        return obj.technique.get_choice_target_kind_display()

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Show editor-facing notes for the linked choice technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _format_technique_choice_context(obj.technique)


class CharacterRaceChoiceInline(admin.StackedInline):
    """Inline editor for persistent character race choices."""

    model = CharacterRaceChoice
    verbose_name_plural = "Race Choices"
    fk_name = "character"
    extra = 0
    show_change_link = True
    autocomplete_fields = (
        "definition",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    fieldsets = (
        (
            "Race",
            {
                "fields": (
                    ("race_name", "definition"),
                    "choice_target_kind",
                    "choice_context",
                )
            },
        ),
        (
            "Selected Target",
            {
                "fields": (
                    ("selected_skill",),
                    ("selected_skill_category", "selected_specialization"),
                    ("selected_item", "selected_item_category"),
                    "selected_text",
                    ("selected_content_type", "selected_object_id"),
                )
            },
        ),
    )
    readonly_fields = ("race_name", "choice_target_kind", "choice_context")

    @admin.display(description="Race")
    def race_name(self, obj):
        """Show the owning race of the selected choice definition."""
        if not obj or not obj.definition_id:
            return "-"
        return obj.definition.race.name

    @admin.display(description="Target")
    def choice_target_kind(self, obj):
        """Show which persistent target type the race choice expects."""
        if not obj or not obj.definition_id:
            return "-"
        return obj.definition.get_target_kind_display()

    @admin.display(description="Choice Notes")
    def choice_context(self, obj):
        """Show editor-facing notes for the linked race choice definition."""
        if not obj or not obj.definition_id:
            return "-"
        return obj.definition.description or obj.definition.name


class CharacterSpecializationInline(admin.TabularInline):
    """Inline editor for school-bound character specializations."""

    model = CharacterSpecialization
    verbose_name_plural = "Specializations"
    fk_name = "character"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("specialization", "source_technique")
    fields = (
        "specialization",
        "specialization_school",
        "source_technique",
        "learned_at",
        "notes",
    )
    readonly_fields = ("specialization_school",)

    @admin.display(description="School")
    def specialization_school(self, obj):
        """Show the owning school of the linked specialization."""
        if not obj or not obj.specialization_id:
            return "-"
        return obj.specialization.school


class CharacterItemInline(admin.TabularInline):
    """Inline editor for a character's inventory entries."""

    model = CharacterItem
    fk_name = "owner"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("item",)
    fields = ("item", "amount", "quality", "equipped")


class ItemRuneInline(admin.TabularInline):
    """Inline editor for runes attached to one concrete owned item."""

    model = ItemRune
    extra = 0
    show_change_link = True
    autocomplete_fields = ("rune",)
    fields = ("rune", "crafter_level", "is_active", "allows_duplicate", "updated_at")
    readonly_fields = ("allows_duplicate", "updated_at")


class SchoolInline(admin.TabularInline):
    """Inline editor for schools inside a school type."""

    model = School
    extra = 0
    show_change_link = True


class TechniqueInline(admin.TabularInline):
    """Inline editor for techniques belonging to one school."""

    model = Technique
    form = InlineValidationSafeModelForm
    verbose_name_plural = "Techniques by Level"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("path", "choice_block", "target_choice_definition")
    fields = (
        "name",
        "level",
        "path",
        "acquisition_type",
        "has_specification",
        "choice_block",
        "target_choice_definition",
        "specialization_slot_grants",
        "support_level",
        "inline_rule_hint",
    )
    readonly_fields = ("inline_rule_hint",)
    ordering = ("level", "path__name", "name")

    def get_queryset(self, request):
        """Prefetch linked rule data so compact technique hints stay readable."""
        return (
            super()
            .get_queryset(request)
            .select_related("school", "path", "choice_block", "target_choice_definition")
            .prefetch_related(
                "requirements__required_technique",
                "requirements__required_path",
                "requirements__required_skill",
                "requirements__required_trait",
                "exclusions__excluded_technique",
                "excluded_by__technique",
                "choice_definitions",
            )
        )

    @admin.display(description="Summary")
    def inline_rule_hint(self, obj):
        """Show only the most important rule hints in the school overview."""
        if not obj or not obj.pk:
            return "-"
        parts = []
        requirements = ", ".join(_format_technique_requirements(obj))
        if requirements != "None":
            parts.append(f"Requirements: {requirements}")
        exclusions = ", ".join(_format_technique_exclusions(obj))
        if exclusions != "None":
            parts.append(f"Exclusions: {exclusions}")
        choices = ", ".join(_format_technique_choice_definitions(obj))
        if choices != "None":
            parts.append(f"Choices: {choices}")
        if obj.choice_group:
            parts.append("choice_group is display/import metadata only")
        return " | ".join(parts) if parts else "See details via the change link."


class TechniqueChoiceBlockInline(admin.TabularInline):
    """Inline editor for generic school-level technique choice blocks."""

    model = TechniqueChoiceBlock
    verbose_name_plural = "Technique Choice Blocks"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("path",)
    fields = ("name", "level", "path", "min_choices", "max_choices", "sort_order", "block_hint")
    readonly_fields = ("block_hint",)
    ordering = ("level", "sort_order", "name")

    def get_queryset(self, request):
        """Prefetch related techniques for readable block summaries."""
        return super().get_queryset(request).select_related("school", "path").prefetch_related("techniques")

    @admin.display(description="Summary")
    def block_hint(self, obj):
        """Keep the choice block overview compact and understandable."""
        if not obj or not obj.pk:
            return "-"
        techniques = ", ".join(obj.techniques.order_by("level", "name").values_list("name", flat=True)) or "no techniques yet"
        if obj.description:
            return f"{obj.description} | Techniques: {techniques}"
        return f"Techniques: {techniques}"


class SpecializationInline(admin.TabularInline):
    """Inline editor for school-bound specializations."""

    model = Specialization
    verbose_name_plural = "Specializations"
    extra = 0
    show_change_link = True
    fields = ("name", "slug", "support_level", "sort_order", "is_active")
    ordering = ("sort_order", "name")


class ProgressionRuleInline(admin.TabularInline):
    """Inline editor for school type progression rules."""

    model = ProgressionRule
    extra = 0
    show_change_link = True


class SchoolCharacterInline(admin.TabularInline):
    """Inline editor for character-school relations from the school side."""

    model = CharacterSchool
    fk_name = "school"
    verbose_name_plural = "Assigned Characters"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("character",)
    classes = ("collapse",)


class ArmorStatsInline(admin.StackedInline):
    """Inline editor for one-to-one armor stats on an item."""

    model = ArmorStats
    verbose_name_plural = "Armor Stats"
    extra = 0
    max_num = 1
    can_delete = True


class ShieldStatsInline(admin.StackedInline):
    """Inline editor for one-to-one shield stats on an item."""

    model = ShieldStats
    verbose_name_plural = "Shield Stats"
    extra = 0
    max_num = 1
    can_delete = True


class WeaponStatsAdminForm(forms.ModelForm):
    """Admin form with conditional two-handed weapon fields."""

    class Meta:
        model = WeaponStats
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in (
            "h2_dice_amount",
            "h2_dice_faces",
            "h2_flat_bonus",
            "h2_flat_operator",
            "h2_damage_type",
        ):
            if field_name in self.fields:
                self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()
        wield_mode = cleaned_data.get("wield_mode") or ONE_HANDED
        if wield_mode not in {TWO_HANDED, VERSATILE}:
            cleaned_data["h2_dice_amount"] = None
            cleaned_data["h2_dice_faces"] = None
            cleaned_data["h2_flat_bonus"] = None
            cleaned_data["h2_flat_operator"] = ""
            cleaned_data["h2_damage_type"] = cleaned_data.get("damage_type")
            return cleaned_data

        missing_fields = [
            field_name
            for field_name in ("h2_dice_amount", "h2_dice_faces")
            if cleaned_data.get(field_name) is None
        ]
        if not cleaned_data.get("h2_damage_type"):
            cleaned_data["h2_damage_type"] = cleaned_data.get("damage_type")
        for field_name in missing_fields:
            self.add_error(field_name, "Required for two-handed and versatile weapons.")
        return cleaned_data


class WeaponStatsInline(admin.StackedInline):
    """Inline editor for one-to-one weapon stats on an item."""

    model = WeaponStats
    form = WeaponStatsAdminForm
    verbose_name_plural = "Weapon Stats"
    extra = 0
    max_num = 1
    can_delete = True
    autocomplete_fields = ("damage_source",)
    filter_horizontal = ("flags", "skills")
    fields = (
        ("min_st_1h", "min_st_2h"),
        ("min_ge_1h", "min_ge_2h"),
        "wield_mode",
        "weapon_type",
        "maneuver_attribute_mode",
        "damage_source",
        "skills",
        ("damage_dice_amount", "damage_dice_faces", "damage_flat_operator", "damage_flat_bonus", "damage_type"),
        ("h2_dice_amount", "h2_dice_faces", "h2_flat_operator", "h2_flat_bonus", "h2_damage_type"),
        ("range_short", "range_medium", "range_long", "reload_time", "shot_count"),
        "flags",
    )

    class Media:
        css = {"all": ("charsheet/css/weapon_stats_admin_v2.css",)}
        js = ("charsheet/js/weapon_stats_inline_admin.js",)


class MagicItemStatsInline(admin.StackedInline):
    """Inline editor for one-to-one magic-item stats on an item."""

    model = MagicItemStats
    verbose_name_plural = "Magic Item Stats"
    extra = 0
    max_num = 1
    can_delete = True
    fields = ("effect_summary",)


class WeaponStatsByDamageSourceInline(admin.TabularInline):
    """Inline editor for weapon stats from the damage source side."""

    model = WeaponStats
    fk_name = "damage_source"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("item",)


class SchoolPathInline(admin.TabularInline):
    """Inline editor for specialization paths belonging to one school."""

    model = SchoolPath
    verbose_name_plural = "School Paths"
    extra = 0
    show_change_link = True


class TechniqueRequirementInline(admin.TabularInline):
    """Inline editor for structured technique requirements."""

    model = TechniqueRequirement
    verbose_name_plural = "Technique Requirements"
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
    verbose_name_plural = "Technique Exclusions"
    fk_name = "technique"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("excluded_technique",)


class TraitExclusionInline(admin.TabularInline):
    """Inline editor for traits excluded by the current trait."""

    model = TraitExclusion
    verbose_name_plural = "Trait Exclusions"
    fk_name = "trait"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("excluded_trait",)


class TraitExcludedByInline(admin.TabularInline):
    """Readonly inline showing exclusions defined on the opposite trait page."""

    model = TraitExclusion
    verbose_name_plural = "Excluded By Traits"
    fk_name = "excluded_trait"
    extra = 0
    show_change_link = True
    can_delete = False
    fields = ("trait",)
    readonly_fields = ("trait",)

    def has_add_permission(self, request, obj=None):
        """Block creating reverse rows from the readonly mirror inline."""
        return False


class TechniqueChoiceDefinitionInline(admin.TabularInline):
    """Inline editor for persistent technique choice definitions."""

    model = TechniqueChoiceDefinition
    verbose_name_plural = "Technique Choice Definitions"
    fk_name = "technique"
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "target_kind",
        "min_choices",
        "max_choices",
        "is_required",
        "sort_order",
        "is_active",
        "description",
    )


class RaceChoiceDefinitionInline(admin.TabularInline):
    """Inline editor for persistent race choice definitions."""

    model = RaceChoiceDefinition
    verbose_name_plural = "Race Choice Definitions"
    fk_name = "race"
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "target_kind",
        "min_choices",
        "max_choices",
        "is_required",
        "allowed_skill_category",
        "allowed_skill_family",
        "sort_order",
        "is_active",
        "description",
    )


class TraitChoiceDefinitionInline(admin.TabularInline):
    """Inline editor for persistent trait choice definitions."""

    model = TraitChoiceDefinition
    verbose_name_plural = "Trait Choice Definitions"
    fk_name = "trait"
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "target_kind",
        "min_choices",
        "max_choices",
        "is_required",
        "allowed_attribute",
        "allowed_skill_category",
        "allowed_skill_family",
        "allowed_derived_stat",
        "allowed_resource",
        "allowed_proficiency_group",
        "sort_order",
        "is_active",
        "description",
    )


class ItemCharacterInline(admin.TabularInline):
    """Inline editor for character ownership entries from the item side."""

    model = CharacterItem
    fk_name = "item"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("owner",)
    fields = ("owner", "amount", "quality", "equipped")


class CreatureCardItemBindingInlineFormSet(BaseInlineFormSet):
    """Persist item-page creature card bindings as item-triggered bindings."""

    def save_new(self, form, commit=True):
        obj = super().save_new(form, commit=False)
        obj.trigger_type = CreatureCardBinding.TriggerType.ITEM
        obj.technique_trigger = None
        if commit:
            obj.save()
            form.save_m2m()
        return obj

    def save_existing(self, form, instance, commit=True):
        instance.trigger_type = CreatureCardBinding.TriggerType.ITEM
        instance.technique_trigger = None
        return super().save_existing(form, instance, commit=commit)


class CreatureCardItemBindingInlineForm(forms.ModelForm):
    """Validate item inline rows as item-triggered creature card bindings."""

    class Meta:
        model = CreatureCardBinding
        fields = ("active", "creature", "note")

    def _post_clean(self):
        self.instance.trigger_type = CreatureCardBinding.TriggerType.ITEM
        self.instance.technique_trigger = None
        super()._post_clean()


class CreatureCardTechniqueBindingInlineFormSet(BaseInlineFormSet):
    """Persist technique-page creature card bindings as technique-triggered bindings."""

    def save_new(self, form, commit=True):
        obj = super().save_new(form, commit=False)
        obj.trigger_type = CreatureCardBinding.TriggerType.TECHNIQUE
        obj.item_trigger = None
        if commit:
            obj.save()
            form.save_m2m()
        return obj

    def save_existing(self, form, instance, commit=True):
        instance.trigger_type = CreatureCardBinding.TriggerType.TECHNIQUE
        instance.item_trigger = None
        return super().save_existing(form, instance, commit=commit)


class CreatureCardTechniqueBindingInlineForm(forms.ModelForm):
    """Validate technique inline rows as technique-triggered creature card bindings."""

    class Meta:
        model = CreatureCardBinding
        fields = ("active", "creature", "note")

    def _post_clean(self):
        self.instance.trigger_type = CreatureCardBinding.TriggerType.TECHNIQUE
        self.instance.item_trigger = None
        super()._post_clean()


class CreatureCardItemBindingInline(admin.TabularInline):
    """Inline editor for concrete creature cards activated by this item."""

    model = CreatureCardBinding
    fk_name = "item_trigger"
    form = CreatureCardItemBindingInlineForm
    formset = CreatureCardItemBindingInlineFormSet
    extra = 0
    fields = ("active", "creature", "note")
    autocomplete_fields = ("creature",)
    verbose_name = "Creature Card Binding"
    verbose_name_plural = "Creature Card Bindings"


class CreatureCardTechniqueBindingInline(admin.TabularInline):
    """Inline editor for concrete creature cards activated by this technique."""

    model = CreatureCardBinding
    fk_name = "technique_trigger"
    form = CreatureCardTechniqueBindingInlineForm
    formset = CreatureCardTechniqueBindingInlineFormSet
    extra = 0
    fields = ("active", "creature", "note")
    autocomplete_fields = ("creature",)
    verbose_name = "Creature Card Binding"
    verbose_name_plural = "Creature Card Bindings"


class CharacterTraitInline(admin.TabularInline):
    """Inline editor for character trait ownership."""

    model = CharacterTrait
    fk_name = "owner"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("trait",)
    fields = (
        "trait",
        "trait_level",
        "trait_min_level",
        "trait_max_level",
        "trait_points_per_level",
        "trait_semantic_effects",
    )
    readonly_fields = ("trait_min_level", "trait_max_level", "trait_points_per_level", "trait_semantic_effects")

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
        return obj.trait.cost_display()

    @admin.display(description="Central Effects")
    def trait_semantic_effects(self, obj):
        """Preview semantic central-engine effects for the selected trait level."""
        if not obj or not obj.trait_id:
            return format_html('<span style="color:#666;">{}</span>', "Pick a trait and save to preview semantic effects.")
        return _trait_semantic_preview(obj.trait, level=obj.trait_level)

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


class TraitSemanticEffectInlineForm(forms.ModelForm):
    """Admin form that allows choice-bound semantic effects without a fixed target key."""

    class Meta:
        model = TraitSemanticEffect
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_key"].required = False

    def clean(self):
        """Mirror the model rule in admin form validation with clearer field behavior."""
        cleaned_data = super().clean()
        target_key = str(cleaned_data.get("target_key") or "").strip()
        target_choice_definition = cleaned_data.get("target_choice_definition")
        target_skills = cleaned_data.get("target_skills")
        has_target_skills = bool(target_skills)
        if not target_choice_definition and not target_key and not has_target_skills:
            self.add_error(
                "target_key",
                "Set a target key, choose target skills, or bind the effect to a trait choice definition.",
            )
        return cleaned_data


class TechniqueSemanticEffectInlineForm(forms.ModelForm):
    """Admin form that allows choice-bound technique effects without a fixed target key."""

    class Meta:
        model = TechniqueSemanticEffect
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_key"].required = False

    def clean(self):
        """Mirror the model rule in admin form validation with clearer field behavior."""
        cleaned_data = super().clean()
        target_key = str(cleaned_data.get("target_key") or "").strip()
        target_choice_definition = cleaned_data.get("target_choice_definition")
        target_skills = cleaned_data.get("target_skills")
        has_target_skills = bool(target_skills)
        if not target_choice_definition and not target_key and not has_target_skills:
            self.add_error(
                "target_key",
                "Set a target key, choose target skills, or bind the effect to a technique choice definition.",
            )
        return cleaned_data


class SpellAdminForm(forms.ModelForm):
    class Meta:
        model = Spell
        fields = "__all__"

    class Media:
        js = ("charsheet/js/admin_slug_autofill.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kp_cost"].required = False
        self.fields["ep_cost"].required = False
        self.fields["range_text"].label = "Textlabel"
        self.fields["duration_text"].label = "Textlabel"
        self.fields["duration2_text"].label = "Textlabel"

    @staticmethod
    def _duration_unit_requires_number(unit: str) -> bool:
        return unit not in {
            "",
            Spell.DurationUnit.INSTANT,
            Spell.DurationUnit.SCENE,
            Spell.DurationUnit.CONCENTRATION,
            Spell.DurationUnit.PERMANENT,
        }

    def _clean_duration_group(
        self,
        cleaned_data,
        *,
        number_field: str,
        unit_field: str,
        per_grade_field: str,
    ) -> bool:
        number = cleaned_data.get(number_field)
        unit = cleaned_data.get(unit_field) or ""
        per_grade = cleaned_data.get(per_grade_field)
        has_number = number not in (None, "")
        has_unit = bool(unit)

        if has_number and not has_unit:
            self.add_error(unit_field, "Waehle eine Einheit fuer die Wirkungsdauer.")
        if has_unit and self._duration_unit_requires_number(unit) and not has_number:
            self.add_error(number_field, "Setze einen Wert fuer diese Einheit.")
        if per_grade and not (has_number and has_unit):
            self.add_error(
                per_grade_field,
                "Pro Stufe benoetigt eine numerische Wirkungsdauer mit Einheit.",
            )

        return has_unit and (has_number or not self._duration_unit_requires_number(unit))

    def clean(self):
        cleaned_data = super().clean()
        kp_cost = cleaned_data.get("kp_cost")
        ep_cost = cleaned_data.get("ep_cost")
        kp_cost_label = str(cleaned_data.get("kp_cost_label") or "").strip()
        ep_cost_label = str(cleaned_data.get("ep_cost_label") or "").strip()
        range_text = str(cleaned_data.get("range_text") or "").strip()
        range_number = cleaned_data.get("range_number")
        range_unit = cleaned_data.get("range_unit") or ""
        duration_text = str(cleaned_data.get("duration_text") or "").strip()
        duration2_text = str(cleaned_data.get("duration2_text") or "").strip()
        cleaned_data["kp_cost_label"] = kp_cost_label
        cleaned_data["ep_cost_label"] = ep_cost_label
        cleaned_data["range_text"] = range_text
        cleaned_data["duration_text"] = duration_text
        cleaned_data["duration2_text"] = duration2_text

        if kp_cost in (None, ""):
            cleaned_data["kp_cost"] = 0
            kp_cost = 0

        if not kp_cost and not ep_cost:
            message = "Setze KP-Kosten oder EP-Kosten."
            self.add_error("kp_cost", message)
            self.add_error("ep_cost", message)

        if range_unit == Spell.RangeUnit.PERSON and range_number in (None, ""):
            self.add_error("range_number", "Setze die Anzahl der Personen.")

        duration_complete = self._clean_duration_group(
            cleaned_data,
            number_field="duration_number",
            unit_field="duration_unit",
            per_grade_field="duration_per_grade",
        )
        duration2_complete = self._clean_duration_group(
            cleaned_data,
            number_field="duration2_number",
            unit_field="duration2_unit",
            per_grade_field="duration2_per_grade",
        )
        if not duration_complete and not duration2_complete and not duration_text and not duration2_text:
            message = "Setze eine Wirkungsdauer oder ein Wirkungsdauer-Textlabel."
            self.add_error("duration_number", message)
            self.add_error("duration_text", message)

        return cleaned_data


class TraitSemanticEffectInline(admin.StackedInline):
    """Inline editor for persisted new-system semantic trait effects."""

    model = TraitSemanticEffect
    form = TraitSemanticEffectInlineForm
    extra = 0
    show_change_link = True
    autocomplete_fields = ("target_choice_definition",)
    filter_horizontal = ("target_skills",)
    fieldsets = (
        (
            "Target",
            {
                "fields": (
                    ("sort_order", "active_flag", "priority"),
                    ("target_domain", "target_key", "operator"),
                    "target_choice_definition",
                    "target_skills",
                    ("mode", "stack_behavior", "visibility"),
                    ("hidden", "sheet_relevant"),
                )
            },
        ),
        (
            "Values",
            {
                "fields": (
                    ("value", "value_min", "value_max"),
                    "formula",
                    "notes",
                    "rules_text",
                )
            },
        ),
        (
            "Conditions And Metadata",
            {
                "fields": ("condition_set", "scaling", "metadata"),
                "description": (
                    "Use JSON objects for condition_set, scaling, and metadata. "
                    "Example condition_set: {\"applies_during_character_creation\": true}. "
                    "For choice-bound trait effects, select a trait choice definition and leave target_key empty."
                ),
            },
        ),
    )


class TechniqueSemanticEffectInline(admin.StackedInline):
    """Inline editor for persisted new-system semantic technique effects."""

    model = TechniqueSemanticEffect
    form = TechniqueSemanticEffectInlineForm
    extra = 0
    show_change_link = True
    autocomplete_fields = ("target_choice_definition",)
    filter_horizontal = ("target_skills",)
    fieldsets = TraitSemanticEffectInline.fieldsets


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


@admin.register(Skill)
class SkillAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    """Admin configuration for skills."""

    list_display = (
        "name",
        "slug",
        "category",
        "category_slug",
        "attribute",
        "attribute_short_name",
    )
    search_fields = ("name", "slug")
    list_filter = ("category", "attribute")
    ordering = ("category", "name")
    autocomplete_fields = ("category", "attribute")
    list_select_related = ("category", "attribute")
    inlines = (SkillCharacterInline,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Return default foreign key form fields for skills."""
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield

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
    inlines = (
        RaceAttributeLimitInline,
        RaceChoiceDefinitionInline,
        RaceTechniqueInline,
        RaceStartingItemInline,
        ModifierInline,
    )
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
        ("Basics", {"fields": ("id", "owner", "name", "race", "gender", "age")}),
        (
            "Body & Origin",
            {"fields": ("height", "weight", "skin_color", "hair_color", "eye_color", "country_of_origin")},
        ),
        ("Additional Details", {"fields": ("religion", "appearance")}),
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
        CharacterRaceChoiceInline,
        CharacterSpecializationInline,
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
            trait = Trait.objects.only("min_level", "max_level", "points_per_level", "points_by_level").get(pk=trait_id)
        except Trait.DoesNotExist:
            return JsonResponse({"error": "Trait not found"}, status=404)

        return JsonResponse(
            {
                "min_level": trait.min_level,
                "max_level": trait.max_level,
                "points_per_level": trait.cost_display(),
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


@admin.register(CharacterCreationDraft)
class CharacterCreationDraftAdmin(admin.ModelAdmin):
    """Admin configuration for persisted character creation drafts."""

    list_display = ("id", "draft_name", "owner", "race", "current_phase", "state_sections")
    list_display_links = ("id", "draft_name")
    search_fields = ("owner__username", "owner__email", "race__name", "state")
    list_filter = ("current_phase", "race")
    ordering = ("owner", "-id")
    readonly_fields = ("draft_name",)
    fieldsets = (
        ("Basis", {"fields": ("owner", "race", "current_phase", "draft_name")}),
        ("Status", {"fields": ("state",)}),
    )
    autocomplete_fields = ("owner", "race")
    list_select_related = ("owner", "race")

    @admin.display(description="Name")
    def draft_name(self, obj):
        """Render the draft character name stored in JSON metadata."""
        if not isinstance(obj.state, dict):
            return "-"
        meta = obj.state.get("meta", {})
        if not isinstance(meta, dict):
            return "-"
        return str(meta.get("name", "")).strip() or "(ohne Namen)"

    @admin.display(description="Gefuellte Bereiche")
    def state_sections(self, obj):
        """Show which draft state sections already contain data."""
        if not isinstance(obj.state, dict):
            return "-"
        section_names = sorted(key for key, value in obj.state.items() if value not in (None, "", {}, []))
        return ", ".join(section_names) if section_names else "-"


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

    list_display = (
        "name", "panel_symbol", "has_symbol_image", "type", "type_slug", "opposite",
        "path_count", "choice_block_count", "technique_count", "specialization_count",
    )
    search_fields = ("name", "type__name", "type__slug", "opposite__name")
    list_filter = ("type", "opposite")
    ordering = ("type", "name")
    readonly_fields = ("symbol_image_preview", "rulebook_editor_guide")
    fieldsets = (
        (
            "School",
            {
                "fields": (
                    ("name", "type", "opposite"),
                    ("panel_symbol", "max_level"),
                    ("symbol_image", "symbol_image_preview"),
                    "description",
                ),
                "description": (
                    "Rulebook-oriented entry point. Paths, choice blocks, techniques, "
                    "and specializations are maintained from here."
                ),
            },
        ),
        (
            "Editing Guide",
            {
                "fields": ("rulebook_editor_guide",),
                "description": "Save the base data first, then maintain the inlines from top to bottom.",
            },
        ),
    )
    inlines = (
        SchoolPathInline,
        TechniqueChoiceBlockInline,
        TechniqueInline,
        SpecializationInline,
        SchoolCharacterInline,
        ModifierInline,
    )
    autocomplete_fields = ("type", "opposite")
    list_select_related = ("type", "opposite")

    @admin.display(ordering="type__slug", description="School Type Key")
    def type_slug(self, obj):
        """Return the related school type slug for list display."""
        return obj.type.slug

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit opposite-school choices to magic schools."""
        if db_field.name == "opposite":
            kwargs["queryset"] = School.objects.filter(type__slug=SCHOOL_ARCANE).order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Editing Order")
    def rulebook_editor_guide(self, obj):
        """Explain the recommended rulebook-oriented editing order."""
        return _format_school_rulebook_guide_html()

    @admin.display(boolean=True, description="Bild")
    def has_symbol_image(self, obj):
        """Return whether the school has a custom panel image."""
        return bool(obj.symbol_image)

    @admin.display(description="Bildvorschau")
    def symbol_image_preview(self, obj):
        """Render a compact preview of the school symbol image."""
        if obj is None or not obj.symbol_image:
            return "-"
        return format_html(
            '<img src="{}" alt="{}" style="max-width:64px; max-height:64px; border-radius:6px; border:1px solid #ccc; background:#fff; padding:3px;" />',
            obj.symbol_image.url,
            obj.name,
        )

    @admin.display(ordering="name", description="Paths")
    def path_count(self, obj):
        """Return how many paths are configured for the school."""
        return obj.paths.count()

    @admin.display(ordering="name", description="Choice Blocks")
    def choice_block_count(self, obj):
        """Return how many choice blocks are configured for the school."""
        return obj.technique_choice_blocks.count()

    @admin.display(ordering="name", description="Techniques")
    def technique_count(self, obj):
        """Return how many techniques are configured for the school."""
        return obj.techniques.count()

    @admin.display(ordering="name", description="Specializations")
    def specialization_count(self, obj):
        """Return how many specializations are configured for the school."""
        return obj.specializations.count()


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


@admin.register(CharacterWeaponMastery)
class CharacterWeaponMasteryAdmin(admin.ModelAdmin):
    """Admin configuration for weapon-type based Waffenmeister picks."""

    list_display = (
        "character",
        "school",
        "weapon_type",
        "weapon_item",
        "pick_order",
        "first_bonus_kind",
    )
    search_fields = ("character__name", "school__name", "weapon_type__name", "weapon_type__slug", "weapon_item__name")
    list_filter = ("school", "first_bonus_kind", "weapon_type")
    ordering = ("character", "school", "pick_order", "weapon_type__name")
    autocomplete_fields = ("character", "school", "weapon_type", "weapon_item")
    list_select_related = ("character", "school", "weapon_type", "weapon_item")


@admin.register(CharacterWeaponMasteryArcana)
class CharacterWeaponMasteryArcanaAdmin(admin.ModelAdmin):
    """Admin configuration for Waffenmeister rune and bonus-capacity progress."""

    list_display = (
        "character",
        "school",
        "kind",
        "rune",
    )
    search_fields = ("character__name", "school__name", "rune__name")
    list_filter = ("school", "kind")
    ordering = ("character", "school", "kind", "rune")
    autocomplete_fields = ("character", "school", "rune")
    list_select_related = ("character", "school", "rune")


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
        "resolved_target_domain",
        "resolved_target_key",
        "target_display_value",
        "target_choice_definition",
        "target_race_choice_definition",
        "value",
        "scale_source",
        "scale_school",
        "scale_skill",
        "mul",
        "div",
        "round_mode",
        "cap_mode",
        "cap_source",
        "min_school_level",
    )
    list_filter = ("source_content_type", "mode", "target_kind", "scale_source", "cap_mode")
    search_fields = (
        "target_slug",
        "scale_skill__name",
        "target_skill__name",
        "target_skill_category__name",
        "target_item__name",
        "target_specialization__name",
        "target_choice_definition__name",
        "target_race_choice_definition__name",
    )
    ordering = ("source_content_type", "source_object_id", "target_kind", "target_slug")
    autocomplete_fields = (
        "scale_school",
        "scale_skill",
        "target_skill",
        "target_skill_category",
        "target_item",
        "target_specialization",
        "target_choice_definition",
        "target_race_choice_definition",
    )
    list_select_related = (
        "scale_school",
        "scale_skill",
        "target_skill",
        "target_skill_category",
        "target_item",
        "target_specialization",
        "target_choice_definition",
        "target_race_choice_definition",
    )
    readonly_fields = ("resolved_target_domain", "resolved_target_key", "central_engine_summary")
    fieldsets = (
        (
            "Source",
            {
                "fields": (
                    ("source_content_type", "source_object_id"),
                )
            },
        ),
        (
            "Target",
            {
                "fields": (
                    ("target_kind", "target_slug"),
                    ("target_skill", "target_skill_category"),
                    ("target_item", "target_specialization"),
                    ("target_choice_definition", "target_race_choice_definition"),
                    ("target_content_type", "target_object_id"),
                )
            },
        ),
        ("Value", {"fields": (("mode", "value"),)}),
        ("Scaling", {"fields": (("scale_source", "scale_school", "scale_skill"), ("mul", "div", "round_mode"))}),
        ("Limits", {"fields": (("cap_mode", "cap_source"), "min_school_level")}),
        (
            "Central Engine Mapping",
            {
                "fields": (("resolved_target_domain", "resolved_target_key"), "central_engine_summary"),
                "description": (
                    "Legacy numeric modifiers remain supported for backward compatibility. "
                    "The central ModifierEngine adapts them into the newer modifier domains at runtime."
                ),
            },
        ),
    )

    @admin.display(description="Source")
    def display_source(self, obj):
        """Render a readable source label and detect broken generic relations."""
        if obj.source is None:
            return f"{obj.source_content_type} #{obj.source_object_id} (missing)"
        return str(obj.source)

    @admin.display(description="Target")
    def target_display_value(self, obj):
        """Render the configured target in a rulebook-friendly way."""
        return obj.target_display()

    @admin.display(description="Central Domain")
    def resolved_target_domain(self, obj):
        """Show which new target domain the legacy row maps to."""
        return LegacyModifierAdapter.adapt(obj).target_domain

    @admin.display(description="Central Key")
    def resolved_target_key(self, obj):
        """Show the central-engine target key produced by the legacy adapter."""
        return LegacyModifierAdapter.adapt(obj).target_key

    @admin.display(description="Engine Summary")
    def central_engine_summary(self, obj):
        """Show how the central engine interprets the legacy row."""
        return _render_readonly_lines((_modifier_preview_line(LegacyModifierAdapter.adapt(obj)),))


@admin.register(Technique)
class TechniqueAdmin(admin.ModelAdmin):
    """Admin configuration for techniques, including support and choice metadata."""

    list_display = (
        "name",
        "school",
        "path",
        "level",
        "acquisition_type",
        "has_specification",
        "choice_block",
        "target_choice_definition",
        "specialization_slot_grants",
        "support_level",
        "choice_marker",
    )
    search_fields = (
        "name",
        "school__name",
        "school__type__name",
        "choice_block__name",
        "target_choice_definition__name",
        "choice_group",
        "selection_notes",
        "description",
    )
    list_filter = (
        "school",
        "school__type",
        "path",
        "choice_block",
        "level",
        "technique_type",
        "acquisition_type",
        "support_level",
        "is_choice_placeholder",
        "has_specification",
        "choice_target_kind",
        "specialization_slot_grants",
        "action_type",
        "usage_type",
    )
    ordering = ("school", "level", "name")
    autocomplete_fields = ("school", "path", "choice_block", "target_choice_definition")
    list_select_related = ("school", "school__type", "path", "choice_block", "target_choice_definition")
    inlines = (
        TechniqueRequirementInline,
        TechniqueExclusionInline,
        TechniqueChoiceDefinitionInline,
        TechniqueRaceInline,
        TechniqueSemanticEffectInline,
        ModifierInline,
        CreatureCardTechniqueBindingInline,
    )
    fieldsets = (
        (
            "Basics",
            {
                "fields": (
                    "rulebook_position",
                    ("school", "path"),
                    ("name", "level"),
                    "choice_block",
                    "description",
                ),
                "description": "Defines where this technique belongs in the school's rulebook structure.",
            },
        ),
        (
            "Classification and Acquisition",
            {
                "fields": (
                    ("technique_type", "acquisition_type"),
                    "has_specification",
                    "support_level",
                ),
                "description": "These fields classify the technique for rulebook, admin, and engine use.",
            },
        ),
        (
            "Choices and Specializations",
            {
                "fields": (
                    "is_choice_placeholder",
                    "choice_group",
                    "choice_group_notice",
                    "selection_notes",
                    ("choice_target_kind", "choice_limit"),
                    "target_choice_definition",
                    "choice_bonus_value",
                    "specialization_slot_grants",
                ),
                "description": (
                    "choice_group is only used for display and organization. Binding "
                    "choice rules come from the choice block and choice definitions."
                ),
            },
        ),
        (
            "Usage",
            {
                "fields": (
                    ("action_type", "usage_type"),
                    ("activation_cost", "activation_cost_resource"),
                ),
                "classes": ("collapse",),
                "description": "Relevant only for techniques with active use.",
            },
        ),
        (
            "Summary",
            {
                "fields": (
                    "requirement_summary",
                    "exclusion_summary",
                    "choice_definition_summary",
                    "rule_context_preview",
                ),
                "description": "This summary helps when checking the entry against the rulebook.",
            },
        ),
    )
    readonly_fields = (
        "rulebook_position",
        "requirement_summary",
        "exclusion_summary",
        "choice_definition_summary",
        "choice_group_notice",
        "rule_context_preview",
    )

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the related school type for list display."""
        return obj.school.type

    @admin.display(ordering="level", description="Rulebook")
    def rulebook_position(self, obj):
        """Render the rulebook position in school -> level -> path order."""
        path_name = obj.path.name if obj.path_id else "All Paths"
        return f"{obj.school.name} -> {obj.level} -> {path_name}"

    @admin.display(boolean=True, description="Choice?")
    def choice_marker(self, obj):
        """Flag choice rows and editorial choice-group metadata without adding rule logic."""
        return bool(obj.is_choice_placeholder or obj.choice_group)

    @admin.display(description="choice_group Note")
    def choice_group_notice(self, obj):
        """Explain that choice_group is metadata only."""
        return _format_choice_group_notice(obj)

    @admin.display(description="Rule Context")
    def rule_context_preview(self, obj):
        """Render a readable rule-context preview for the technique page."""
        if not obj or not obj.pk:
            return "-"
        return _format_technique_rule_context_html(obj)

    @admin.display(description="Requirements")
    def requirement_summary(self, obj):
        """Summarize technique requirements for the detail page."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(_format_technique_requirements(obj))

    @admin.display(description="Exclusions")
    def exclusion_summary(self, obj):
        """Summarize technique exclusions for the detail page."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(_format_technique_exclusions(obj))

    @admin.display(description="Choice Definitions")
    def choice_definition_summary(self, obj):
        """Summarize technique choice definitions for the detail page."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(_format_technique_choice_definitions(obj))


@admin.register(Quality)
class QualityAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "hex_color", "sort_order", "preview")
    search_fields = ("name", "code", "hex_color")
    ordering = ("sort_order", "name")

    @admin.display(description="Preview")
    def preview(self, obj):
        return _quality_badge(obj)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin configuration for items."""

    action_form = ItemBulkActionForm
    actions = ("change_item_type_action",)
    list_display = (
        "name",
        "item_type",
        "quality_preview",
        "price",
        "size_class",
        "weight",
        "stackable",
        "is_consumable",
        "not_buyable",
        "not_sellable",
    )
    search_fields = ("name", "description", "item_type")
    list_filter = ("item_type", "default_quality", "stackable", "is_consumable", "not_buyable", "not_sellable", "size_class")
    ordering = ("item_type", "name")
    inlines = (
        ArmorStatsInline,
        ShieldStatsInline,
        WeaponStatsInline,
        MagicItemStatsInline,
        ModifierInline,
        ItemRaceStartingInline,
        ItemCharacterInline,
        CreatureCardItemBindingInline,
    )

    class Media:
        css = {"all": ("charsheet/css/weapon_stats_admin_v2.css",)}
        js = ("charsheet/js/weapon_stats_inline_admin.js",)

    @admin.display(ordering="default_quality", description="Quality")
    def quality_preview(self, obj):
        """Render default quality with RPG item coloring."""
        return _quality_badge(obj.default_quality)

    @admin.action(description="Kategorie der ausgewählten Items ändern")
    def change_item_type_action(self, request, queryset):
        """Bulk-update the item category of the selected items."""
        target_item_type = (request.POST.get("target_item_type") or "").strip()
        valid_item_types = {value for value, _label in Item.ItemType.choices}
        if target_item_type not in valid_item_types:
            self.message_user(
                request,
                "Bitte oben in der Action-Leiste eine gültige Ziel-Kategorie auswählen.",
                level="warning",
            )
            return

        updated_count = queryset.exclude(item_type=target_item_type).update(item_type=target_item_type)
        target_label = dict(Item.ItemType.choices).get(target_item_type, target_item_type)
        self.message_user(
            request,
            f"{updated_count} Item(s) wurden auf die Kategorie '{target_label}' gesetzt.",
        )


@admin.register(CharacterItem)
class CharacterItemAdmin(admin.ModelAdmin):
    """Admin configuration for character inventory entries."""

    list_display = (
        "owner",
        "owner_race",
        "item",
        "item_type",
        "quality_preview",
        "amount",
        "equipped",
        "base_price",
        "effective_price",
    )
    search_fields = ("owner__name", "item__name", "item__description")
    list_filter = ("equipped", "quality", "item__item_type", "owner__race", "item__size_class")
    ordering = ("owner", "item")
    autocomplete_fields = ("owner", "item")
    list_select_related = ("owner", "owner__race", "item")
    inlines = (ItemRuneInline,)

    @admin.display(ordering="owner__race__name", description="Owner Race")
    def owner_race(self, obj):
        """Return the owning character race for list display."""
        return obj.owner.race

    @admin.display(ordering="item__item_type", description="Item Type")
    def item_type(self, obj):
        """Return the related item type for list display."""
        return obj.item.item_type

    @admin.display(ordering="quality", description="Quality")
    def quality_preview(self, obj):
        """Render effective inventory quality with RPG item coloring."""
        return _quality_badge(obj.quality)

    @admin.display(ordering="item__price", description="Base Price")
    def base_price(self, obj):
        """Return unmodified item base price."""
        return obj.item.price

    @admin.display(description="Price (Quality)")
    def effective_price(self, obj):
        """Return quality-adjusted price resolved via ItemEngine."""
        return ItemEngine(obj).get_price()


@admin.register(ItemRune)
class ItemRuneAdmin(admin.ModelAdmin):
    """Admin configuration for concrete rune assignments on owned items."""

    list_display = (
        "item",
        "rune",
        "crafter_level",
        "is_active",
        "allows_duplicate",
        "updated_at",
    )
    search_fields = ("item__owner__name", "item__item__name", "rune__name", "rune__slug")
    list_filter = ("is_active", "allows_duplicate", "rune__is_level_scaled", "rune__allow_multiple")
    ordering = ("item__owner__name", "item__item__name", "rune__name", "id")
    autocomplete_fields = ("item", "rune")
    list_select_related = ("item", "item__owner", "item__item", "rune")
    readonly_fields = ("allows_duplicate", "created_at", "updated_at")


@admin.register(ArmorStats)
class ArmorStatsAdmin(admin.ModelAdmin):
    """Admin configuration for armor stat blocks."""

    list_display = (
        "item",
        "item_quality",
        "rs_total",
        "rs_zone_sum",
        "rs_zone_average",
        "encumbrance",
        "min_st",
    )
    search_fields = ("item__name",)
    list_filter = ("item__default_quality", "item__size_class")
    ordering = ("item__name",)
    autocomplete_fields = ("item",)
    list_select_related = ("item",)

    @admin.display(ordering="item__default_quality", description="Item Quality")
    def item_quality(self, obj):
        """Render linked item default quality with RPG color coding."""
        return _quality_badge(obj.item.default_quality)

    @admin.display(description="Zone Sum")
    def rs_zone_sum(self, obj):
        """Return summed zone armor values for list display."""
        return obj.rs_sum()

    @admin.display(description="Zone Avg")
    def rs_zone_average(self, obj):
        """Return average per-zone armor value for list display."""
        return obj.rs_sum() // 6


@admin.register(ShieldStats)
class ShieldStatsAdmin(admin.ModelAdmin):
    """Admin configuration for shield stat blocks."""

    list_display = ("item", "item_quality", "rs", "encumbrance", "min_st")
    search_fields = ("item__name",)
    list_filter = ("item__default_quality", "item__size_class")
    ordering = ("item__name",)
    autocomplete_fields = ("item",)
    list_select_related = ("item",)

    @admin.display(ordering="item__default_quality", description="Item Quality")
    def item_quality(self, obj):
        """Render linked item default quality with RPG color coding."""
        return _quality_badge(obj.item.default_quality)


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


@admin.register(TechniqueChoiceBlock)
class TechniqueChoiceBlockAdmin(admin.ModelAdmin):
    """Admin configuration for generic technique choice blocks."""

    list_display = (
        "name",
        "school",
        "rulebook_scope",
        "min_choices",
        "max_choices",
        "technique_count",
    )
    search_fields = ("name", "description", "school__name", "path__name")
    list_filter = ("school__type", "school", "path", "level")
    ordering = ("school", "level", "sort_order", "name")
    autocomplete_fields = ("school", "path")
    list_select_related = ("school", "school__type", "path")
    readonly_fields = ("rulebook_scope_preview", "assigned_techniques")
    fieldsets = (
        (
            "Choice Block",
            {
                "fields": (
                    ("school", "path"),
                    ("name", "sort_order"),
                    "level",
                    ("min_choices", "max_choices"),
                    "description",
                ),
                "description": (
                    "A choice block describes a real choice point in the rulebook. "
                    "Techniques sharing the same choice_group are not automatically "
                    "exclusive because of that."
                ),
            },
        ),
        (
            "Overview",
            {
                "fields": ("rulebook_scope_preview", "assigned_techniques"),
                "description": "Shows where the block sits in the rulebook and which techniques belong to it.",
            },
        ),
    )

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the linked school type for list display."""
        return obj.school.type

    @admin.display(ordering="level", description="Level / Path")
    def rulebook_scope(self, obj):
        """Render the choice-block position in rulebook terms for list views."""
        level = f"Level {obj.level}" if obj.level is not None else "no fixed level"
        path = obj.path.name if obj.path_id else "all paths"
        return f"{level} | {path}"

    @admin.display(description="Rulebook Position")
    def rulebook_scope_preview(self, obj):
        """Render the full rulebook scope on the detail page."""
        if not obj or not getattr(obj, "school_id", None):
            return "-"
        return f"{obj.school.name} -> {self.rulebook_scope(obj)}"

    @admin.display(description="Assigned Techniques")
    def assigned_techniques(self, obj):
        """Show all techniques assigned to this choice block."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(obj.techniques.order_by("level", "name").values_list("name", flat=True)) or "None yet"

    @admin.display(ordering="name", description="Techniques")
    def technique_count(self, obj):
        """Return how many techniques currently belong to the block."""
        return obj.techniques.count()


@admin.register(TechniqueChoiceDefinition)
class TechniqueChoiceDefinitionAdmin(admin.ModelAdmin):
    """Admin configuration for persistent technique choice definitions."""

    list_display = (
        "name",
        "technique",
        "technique_school",
        "target_kind",
        "targeting_technique_count",
        "min_choices",
        "max_choices",
        "is_required",
        "is_active",
    )
    search_fields = (
        "name",
        "description",
        "technique__name",
        "technique__school__name",
        "targeting_techniques__name",
        "targeting_modifiers__target_slug",
        "targeting_modifiers__target_skill__name",
        "targeting_modifiers__target_skill_category__name",
        "targeting_modifiers__target_item__name",
        "targeting_modifiers__target_specialization__name",
    )
    list_filter = ("technique__school__type", "technique__school", "target_kind", "is_required", "is_active")
    ordering = ("technique__school", "technique__level", "technique__name", "sort_order", "name")
    autocomplete_fields = ("technique",)
    list_select_related = ("technique", "technique__school", "technique__school__type")
    readonly_fields = ("targeting_techniques", "targeting_modifiers")
    fieldsets = (
        (
            "Choice Definition",
            {
                "fields": (
                    "technique",
                    "name",
                    "target_kind",
                    "description",
                    ("min_choices", "max_choices", "is_required"),
                    ("allowed_skill_category", "allowed_skill_family"),
                    ("sort_order", "is_active"),
                ),
            },
        ),
        (
            "Links",
            {
                "fields": ("targeting_techniques", "targeting_modifiers"),
                "description": "Shows techniques and modifiers that explicitly point to this choice definition.",
            },
        ),
    )

    @admin.display(ordering="technique__school__name", description="School")
    def technique_school(self, obj):
        """Return the owning technique school for list display."""
        return obj.technique.school

    @admin.display(description="Linked Techniques")
    def targeting_techniques(self, obj):
        """Show techniques that explicitly reference this choice definition."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(
            obj.targeting_techniques.select_related("school").order_by("school__name", "level", "name").values_list("name", flat=True)
        ) or "None"

    @admin.display(description="Techniques")
    def targeting_technique_count(self, obj):
        """Return how many techniques point to this choice definition."""
        return obj.targeting_techniques.count()

    @admin.display(description="Linked Modifiers")
    def targeting_modifiers(self, obj):
        """Show modifiers that explicitly reference this choice definition."""
        if not obj or not obj.pk:
            return "-"
        modifiers = obj.targeting_modifiers.select_related(
            "target_skill",
            "target_skill_category",
            "target_item",
            "target_specialization",
        ).order_by("target_kind", "target_slug", "id")
        return ", ".join(f"{modifier.target_kind}: {modifier.target_display()}" for modifier in modifiers) or "None"


@admin.register(RaceChoiceDefinition)
class RaceChoiceDefinitionAdmin(admin.ModelAdmin):
    """Admin configuration for persistent race choice definitions."""

    list_display = (
        "name",
        "race",
        "target_kind",
        "targeting_modifier_count",
        "min_choices",
        "max_choices",
        "is_required",
        "is_active",
    )
    search_fields = (
        "name",
        "description",
        "race__name",
        "targeting_modifiers__target_slug",
        "targeting_modifiers__target_skill__name",
        "targeting_modifiers__target_skill_category__name",
        "targeting_modifiers__target_item__name",
        "targeting_modifiers__target_specialization__name",
    )
    list_filter = ("race", "target_kind", "is_required", "is_active")
    ordering = ("race__name", "sort_order", "name")
    autocomplete_fields = ("race",)
    list_select_related = ("race",)
    readonly_fields = ("targeting_modifiers",)
    fieldsets = (
        (
            "Choice Definition",
            {
                "fields": (
                    "race",
                    "name",
                    "target_kind",
                    "description",
                    ("min_choices", "max_choices", "is_required"),
                    ("allowed_skill_category", "allowed_skill_family"),
                    ("sort_order", "is_active"),
                ),
            },
        ),
        (
            "Links",
            {
                "fields": ("targeting_modifiers",),
                "description": "Shows modifiers that explicitly point to this race choice definition.",
            },
        ),
    )

    @admin.display(description="Linked Modifiers")
    def targeting_modifiers(self, obj):
        """Show modifiers that explicitly reference this race choice definition."""
        if not obj or not obj.pk:
            return "-"
        modifiers = obj.targeting_modifiers.select_related(
            "target_skill",
            "target_skill_category",
            "target_item",
            "target_specialization",
        ).order_by("target_kind", "target_slug", "id")
        return ", ".join(f"{modifier.target_kind}: {modifier.target_display()}" for modifier in modifiers) or "None"

    @admin.display(description="Modifiers")
    def targeting_modifier_count(self, obj):
        """Return how many modifiers point to this race choice definition."""
        return obj.targeting_modifiers.count()


@admin.register(TraitChoiceDefinition)
class TraitChoiceDefinitionAdmin(admin.ModelAdmin):
    """Admin configuration for persistent trait choice definitions."""

    list_display = (
        "name",
        "trait",
        "target_kind",
        "semantic_effect_count",
        "min_choices",
        "max_choices",
        "is_required",
        "is_active",
    )
    search_fields = ("name", "description", "trait__name", "trait__slug")
    list_filter = ("trait__trait_type", "trait", "target_kind", "is_required", "is_active")
    ordering = ("trait__trait_type", "trait__name", "sort_order", "name")
    autocomplete_fields = ("trait", "allowed_attribute", "allowed_skill_category")
    list_select_related = ("trait", "allowed_attribute", "allowed_skill_category")
    readonly_fields = ("linked_semantic_effects",)
    fieldsets = (
        (
            "Choice Definition",
            {
                "fields": (
                    "trait",
                    "name",
                    "target_kind",
                    "description",
                    ("min_choices", "max_choices", "is_required"),
                    ("allowed_attribute", "allowed_skill_category", "allowed_skill_family"),
                    "allowed_derived_stat",
                    "allowed_resource",
                    "allowed_proficiency_group",
                    ("sort_order", "is_active"),
                ),
            },
        ),
        (
            "Links",
            {
                "fields": ("linked_semantic_effects",),
                "description": "Shows trait semantic effects that explicitly point to this choice definition.",
            },
        ),
    )

    @admin.display(description="Linked Effects")
    def linked_semantic_effects(self, obj):
        """Show semantic effects that explicitly reference this trait choice definition."""
        if not obj or not obj.pk:
            return "-"
        effects = obj.semantic_effects.order_by("sort_order", "id")
        return ", ".join(
            f"{effect.target_domain}:{effect.target_key or '[choice-bound]'} [{effect.operator}]"
            for effect in effects
        ) or "None"

    @admin.display(description="Effects")
    def semantic_effect_count(self, obj):
        """Return how many semantic effects point to this trait choice definition."""
        return obj.semantic_effects.count()


@admin.register(Specialization)
class SpecializationAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    """Admin configuration for school-bound specializations."""

    list_display = ("name", "school", "school_type", "slug", "support_level", "is_active", "sort_order")
    search_fields = ("name", "slug", "school__name")
    list_filter = ("school", "support_level", "is_active")
    ordering = ("school", "sort_order", "name")
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")
    fieldsets = (
        (
            "Specialization",
            {
                "fields": (
                    ("school", "sort_order"),
                    ("name", "slug"),
                    "support_level",
                    "is_active",
                    "description",
                ),
                "description": "Specializations are separate school-bound choices and are maintained independently from techniques.",
            },
        ),
    )

    @admin.display(ordering="school__type__name", description="School Type")
    def school_type(self, obj):
        """Return the linked school type for list display."""
        return obj.school.type


@admin.register(CharacterSpecialization)
class CharacterSpecializationAdmin(admin.ModelAdmin):
    """Admin configuration for character-owned school specializations."""

    list_display = ("character", "specialization", "specialization_school", "source_technique", "learned_at")
    search_fields = (
        "character__name",
        "specialization__name",
        "specialization__slug",
        "specialization__school__name",
        "source_technique__name",
    )
    list_filter = ("specialization__school__type", "specialization__school", "specialization__support_level")
    ordering = (
        "character",
        "specialization__school",
        "specialization__sort_order",
        "specialization__name",
    )
    autocomplete_fields = ("character", "specialization", "source_technique")
    list_select_related = (
        "character",
        "specialization",
        "specialization__school",
        "specialization__school__type",
        "source_technique",
    )

    @admin.display(ordering="specialization__school__name", description="School")
    def specialization_school(self, obj):
        """Return the linked specialization school for list display."""
        return obj.specialization.school


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
        "specification_value",
        "learned_at",
    )
    search_fields = (
        "character__name",
        "technique__name",
        "technique__school__name",
        "technique__path__name",
        "technique__choice_group",
        "technique__selection_notes",
        "specification_value",
    )
    list_filter = (
        "technique__school__type",
        "technique__school",
        "technique__path",
        "technique__level",
        "technique__support_level",
        "technique__is_choice_placeholder",
        "technique__has_specification",
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
        return obj.technique.get_support_level_display()


@admin.register(RaceTechnique)
class RaceTechniqueAdmin(admin.ModelAdmin):
    """Admin configuration for race-technique assignments."""

    list_display = ("race", "technique", "technique_school", "technique_path", "technique_level")
    search_fields = ("race__name", "technique__name", "technique__school__name", "technique__path__name")
    list_filter = ("race", "technique__school__type", "technique__school", "technique__path", "technique__level")
    ordering = ("race__name", "technique__school__name", "technique__level", "technique__name")
    autocomplete_fields = ("race", "technique")
    list_select_related = ("race", "technique", "technique__school", "technique__school__type", "technique__path")

    @admin.display(ordering="technique__school__name", description="School")
    def technique_school(self, obj):
        """Return the linked technique school for list display."""
        return obj.technique.school

    @admin.display(ordering="technique__path__name", description="Path")
    def technique_path(self, obj):
        """Return the linked technique path if present."""
        return obj.technique.path or "-"

    @admin.display(ordering="technique__level", description="Level")
    def technique_level(self, obj):
        """Return the linked technique level."""
        return obj.technique.level


@admin.register(RaceStartingItem)
class RaceStartingItemAdmin(admin.ModelAdmin):
    """Admin configuration for race-based starter equipment."""

    list_display = ("race", "item", "item_type", "amount", "quality_preview")
    search_fields = ("race__name", "item__name", "item__description")
    list_filter = ("race", "item__item_type", "quality", "item__size_class")
    ordering = ("race__name", "item__item_type", "item__name")
    autocomplete_fields = ("race", "item")
    list_select_related = ("race", "item")

    @admin.display(ordering="item__item_type", description="Item Type")
    def item_type(self, obj):
        """Return the starter item's type for list display."""
        return obj.item.item_type

    @admin.display(ordering="quality", description="Quality")
    def quality_preview(self, obj):
        """Render starter quality, falling back to the item's default quality."""
        return _quality_badge(obj.quality or obj.item.default_quality)


@admin.register(CharacterTechniqueChoice)
class CharacterTechniqueChoiceAdmin(admin.ModelAdmin):
    """Admin configuration for persistent character technique choices."""

    list_display = (
        "character",
        "technique",
        "definition",
        "technique_school",
        "technique_level",
        "choice_target_kind",
        "technique_choice_context",
        "selected_target_value",
    )
    search_fields = (
        "character__name",
        "technique__name",
        "technique__school__name",
        "selected_skill__name",
        "selected_skill_category__name",
        "selected_item__name",
        "selected_specialization__name",
        "selected_text",
    )
    list_filter = (
        "technique__school__type",
        "technique__school",
        "technique__choice_target_kind",
        "definition__target_kind",
    )
    ordering = ("character", "technique__school", "technique__level", "technique__name")
    autocomplete_fields = (
        "character",
        "technique",
        "definition",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    list_select_related = (
        "character",
        "technique",
        "technique__school",
        "technique__school__type",
        "definition",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    fieldsets = (
        (
            "Technique",
            {
                "fields": (
                    ("character", "technique"),
                    "definition",
                    ("technique_level", "choice_target_kind"),
                    "technique_choice_context",
                )
            },
        ),
        (
            "Selected Target",
            {
                "fields": (
                    ("selected_skill"),
                    ("selected_skill_category", "selected_specialization"),
                    ("selected_item", "selected_item_category"),
                    "selected_text",
                    ("selected_content_type", "selected_object_id"),
                )
            },
        ),
    )

    readonly_fields = ("technique_level", "choice_target_kind", "technique_choice_context")

    def changelist_view(self, request, extra_context=None):
        """Drop stale legacy filter keys that reference removed family fields."""
        stale_keys = [key for key in request.GET.keys() if key.startswith("selected_skill_family")]
        if stale_keys:
            params = request.GET.copy()
            for key in stale_keys:
                params.pop(key, None)
            redirect_url = request.path
            query_string = params.urlencode()
            if query_string:
                redirect_url = f"{redirect_url}?{query_string}"
            return HttpResponseRedirect(redirect_url)
        return super().changelist_view(request, extra_context=extra_context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit technique selection to real choice techniques in the dedicated admin."""
        if db_field.name == "technique":
            kwargs["queryset"] = (
                Technique.objects.filter(
                    Q(choice_definitions__isnull=False)
                    | ~Q(choice_target_kind=Technique.ChoiceTargetKind.NONE),
                    school__isnull=False,
                )
                .select_related("school", "path")
                .distinct()
                .order_by("school__name", "level", "name")
            )
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield

    @admin.display(ordering="technique__school__name", description="Source")
    def technique_school(self, obj):
        """Return the owning source of the selected technique."""
        return _technique_source_label(obj.technique, character=obj.character)

    @admin.display(ordering="technique__level", description="Level")
    def technique_level(self, obj):
        """Return the required school level of the selected technique."""
        return obj.technique.level

    @admin.display(ordering="technique__choice_target_kind", description="Target")
    def choice_target_kind(self, obj):
        """Return which persistent target kind the technique expects."""
        if obj.definition_id:
            return obj.definition.get_target_kind_display()
        return obj.technique.get_choice_target_kind_display()

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Return editor-facing guidance for persistent technique choices."""
        return _format_technique_choice_context(obj.technique)

    @admin.display(description="Selection")
    def selected_target_value(self, obj):
        """Render the stored target in readable form."""
        return obj.selected_target_display()


@admin.register(CharacterRaceChoice)
class CharacterRaceChoiceAdmin(admin.ModelAdmin):
    """Admin configuration for persistent character race choices."""

    list_display = (
        "character",
        "race_name",
        "definition",
        "choice_target_kind",
        "choice_context",
        "selected_target_value",
    )
    search_fields = (
        "character__name",
        "definition__name",
        "definition__race__name",
        "selected_skill__name",
        "selected_skill_category__name",
        "selected_item__name",
        "selected_specialization__name",
        "selected_text",
    )
    list_filter = (
        "definition__race",
        "definition__target_kind",
    )
    ordering = ("character", "definition__race__name", "definition__sort_order", "definition__name")
    autocomplete_fields = (
        "character",
        "definition",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    list_select_related = (
        "character",
        "definition",
        "definition__race",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    fieldsets = (
        (
            "Race",
            {
                "fields": (
                    ("character", "definition"),
                    "choice_target_kind",
                    "choice_context",
                )
            },
        ),
        (
            "Selected Target",
            {
                "fields": (
                    ("selected_skill",),
                    ("selected_skill_category", "selected_specialization"),
                    ("selected_item", "selected_item_category"),
                    "selected_text",
                    ("selected_content_type", "selected_object_id"),
                )
            },
        ),
    )
    readonly_fields = ("choice_target_kind", "choice_context")

    @admin.display(ordering="definition__race__name", description="Race")
    def race_name(self, obj):
        """Return the owning race of the selected definition."""
        return obj.definition.race.name

    @admin.display(ordering="definition__target_kind", description="Target")
    def choice_target_kind(self, obj):
        """Return which persistent target kind the race choice expects."""
        return obj.definition.get_target_kind_display()

    @admin.display(description="Choice Notes")
    def choice_context(self, obj):
        """Return editor-facing guidance for persistent race choices."""
        return obj.definition.description or obj.definition.name

    @admin.display(description="Selection")
    def selected_target_value(self, obj):
        """Render the stored race target in readable form."""
        return obj.selected_target_display()


@admin.register(CharacterTraitChoice)
class CharacterTraitChoiceAdmin(admin.ModelAdmin):
    """Admin configuration for persistent character trait choices."""

    list_display = (
        "owner_name",
        "trait_name",
        "definition",
        "choice_target_kind",
        "choice_context",
        "selected_target_value",
    )
    search_fields = (
        "character_trait__owner__name",
        "character_trait__trait__name",
        "definition__name",
        "selected_attribute__name",
        "selected_skill__name",
        "selected_skill_category__name",
        "selected_derived_stat",
        "selected_resource",
        "selected_proficiency_group",
        "selected_item__name",
        "selected_specialization__name",
        "selected_text",
    )
    list_filter = ("character_trait__trait", "definition__target_kind")
    ordering = ("character_trait__owner__name", "character_trait__trait__name", "definition__sort_order", "definition__name")
    autocomplete_fields = (
        "character_trait",
        "definition",
        "selected_attribute",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    list_select_related = (
        "character_trait",
        "character_trait__owner",
        "character_trait__trait",
        "definition",
        "selected_attribute",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )
    fieldsets = (
        (
            "Trait",
            {
                "fields": (
                    ("character_trait", "definition"),
                    "choice_target_kind",
                    "choice_context",
                )
            },
        ),
        (
            "Selected Target",
            {
                "fields": (
                    "selected_attribute",
                    ("selected_skill",),
                    ("selected_skill_category", "selected_specialization"),
                    "selected_derived_stat",
                    "selected_resource",
                    "selected_proficiency_group",
                    ("selected_item", "selected_item_category"),
                    "selected_text",
                    ("selected_content_type", "selected_object_id"),
                )
            },
        ),
    )
    readonly_fields = ("choice_target_kind", "choice_context")

    @admin.display(ordering="character_trait__owner__name", description="Character")
    def owner_name(self, obj):
        """Return the owning character name."""
        return obj.character_trait.owner.name

    @admin.display(ordering="character_trait__trait__name", description="Trait")
    def trait_name(self, obj):
        """Return the owning trait name."""
        return obj.character_trait.trait.name

    @admin.display(ordering="definition__target_kind", description="Target")
    def choice_target_kind(self, obj):
        """Return which persistent target kind the trait choice expects."""
        return obj.definition.get_target_kind_display()

    @admin.display(description="Choice Notes")
    def choice_context(self, obj):
        """Return editor-facing guidance for persistent trait choices."""
        return _format_trait_choice_context(obj.definition)

    @admin.display(description="Selection")
    def selected_target_value(self, obj):
        """Render the stored trait target in readable form."""
        return obj.selected_target_display()


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


@admin.register(TraitExclusion)
class TraitExclusionAdmin(admin.ModelAdmin):
    """Admin configuration for mutually exclusive traits."""

    list_display = ("trait", "trait_type", "excluded_trait")
    search_fields = ("trait__name", "trait__slug", "excluded_trait__name", "excluded_trait__slug")
    list_filter = ("trait__trait_type",)
    ordering = ("trait__trait_type", "trait__name", "excluded_trait__name")
    autocomplete_fields = ("trait", "excluded_trait")
    list_select_related = ("trait", "excluded_trait")

    @admin.display(ordering="trait__trait_type", description="Trait Type")
    def trait_type(self, obj):
        """Return the source trait type for list display."""
        return obj.trait.trait_type


@admin.register(DamageSource)
class DamageSourceAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    """Admin configuration for weapon damage source definitions."""
    list_display = ("name", "short_name", "slug")
    search_fields = ("name", "short_name", "slug")
    ordering = ("name",)
    inlines = (WeaponStatsByDamageSourceInline,)


@admin.register(WeaponFlag)
class WeaponFlagAdmin(admin.ModelAdmin):
    """Admin configuration for reusable weapon flag definitions."""

    list_display = ("key", "label")
    search_fields = ("key",)
    ordering = ("key",)

    @admin.display(ordering="key", description="Label")
    def label(self, obj):
        """Return the translated flag label for quick scanning."""
        return obj.get_key_display()


@admin.register(Rune)
class RuneAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    """Admin configuration for reusable rune definitions."""

    list_display = ("name", "slug", "short_description", "is_level_scaled", "allow_multiple")
    search_fields = ("name", "slug", "short_description", "description", "image")
    list_filter = ("is_level_scaled", "allow_multiple")
    ordering = ("name",)
    inlines = (ModifierInline,)

    def get_form(self, request, obj=None, change=False, **kwargs):
        """Render the short description as a larger textarea in the admin form."""
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        short_description_field = form.base_fields.get("short_description")
        if short_description_field is not None:
            short_description_field.widget = forms.Textarea(
                attrs={
                    "rows": 4,
                    "cols": 80,
                }
            )
        return form


@admin.register(WeaponStats)
class WeaponStatsAdmin(admin.ModelAdmin):
    """Admin configuration for weapon stat records."""

    form = WeaponStatsAdminForm
    list_display = (
        "item",
        "item_quality",
        "base_damage",
        "quality_damage",
        "two_handed_damage",
        "wield_mode",
        "maneuver_attribute_mode",
        "damage_source",
        "skill_summary",
        "damage_type",
        "flag_summary",
        "min_st_summary",
        "range_summary",
        "size_class",
    )
    search_fields = ("item__name", "weapon_type__name", "weapon_type__slug", "damage_source__name", "flags__key", "skills__name", "skills__slug")
    list_filter = ("weapon_type", "wield_mode", "damage_source", "damage_type", "flags", "item__default_quality", "item__size_class")
    ordering = ("item__name",)
    autocomplete_fields = ("item", "weapon_type", "damage_source")
    list_select_related = ("item", "weapon_type", "damage_source")
    filter_horizontal = ("flags", "skills")
    fields = (
        "item",
        ("min_st_1h", "min_st_2h"),
        ("min_ge_1h", "min_ge_2h"),
        "wield_mode",
        "weapon_type",
        "maneuver_attribute_mode",
        "damage_source",
        "skills",
        ("damage_dice_amount", "damage_dice_faces", "damage_flat_operator", "damage_flat_bonus", "damage_type"),
        ("h2_dice_amount", "h2_dice_faces", "h2_flat_operator", "h2_flat_bonus", "h2_damage_type"),
        ("range_short", "range_medium", "range_long", "reload_time", "shot_count"),
        "flags",
    )

    class Media:
        css = {"all": ("charsheet/css/weapon_stats_admin_v2.css",)}
        js = ("charsheet/js/weapon_stats_inline_admin.js",)

    @admin.display(ordering="item__default_quality", description="Item Quality")
    def item_quality(self, obj):
        """Render linked item default quality with RPG color coding."""
        return _quality_badge(obj.item.default_quality)

    @admin.display(description="Base Damage")
    def base_damage(self, obj):
        """Render raw one-handed damage without quality modifiers."""
        return obj.damage

    @admin.display(description="Damage (Quality)")
    def quality_damage(self, obj):
        """Render quality-adjusted one-handed damage through ItemEngine."""
        return ItemEngine(obj.item).get_one_handed_damage_label()

    @admin.display(description="Flags")
    def flag_summary(self, obj):
        """Render assigned weapon flags compactly for list display."""
        return ", ".join(obj.flags.order_by("key").values_list("key", flat=True)) or "-"

    @admin.display(description="Skills")
    def skill_summary(self, obj):
        """Render assigned weapon skills compactly for list display."""
        return ", ".join(obj.skills.order_by("name").values_list("name", flat=True)) or "-"

    @admin.display(description="Min-St")
    def min_st_summary(self, obj):
        """Render effective one-handed and two-handed minimum strength."""
        one_handed = obj.effective_min_st(ONE_HANDED)
        two_handed = obj.effective_min_st(TWO_HANDED)
        ge_one_handed = obj.effective_min_ge(ONE_HANDED)
        ge_two_handed = obj.effective_min_ge(TWO_HANDED)
        st_label = str(one_handed) if one_handed == two_handed else f"1H {one_handed} / 2H {two_handed}"
        if ge_one_handed is None and ge_two_handed is None:
            return st_label
        ge_label = (
            str(ge_one_handed)
            if ge_one_handed == ge_two_handed
            else f"1H {ge_one_handed or '-'} / 2H {ge_two_handed or '-'}"
        )
        return f"ST {st_label} | GE {ge_label}"

    @admin.display(description="Range")
    def range_summary(self, obj):
        """Render short/medium/long range values."""
        return obj.range_label or "-"


@admin.register(WeaponType)
class WeaponTypeAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    """Admin configuration for rule-level weapon types."""

    list_display = ("name", "slug", "sort_order")
    search_fields = ("name", "slug")
    ordering = ("sort_order", "name")


@admin.register(Trait)
class TraitAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    """Admin configuration for traits and their level boundaries."""
    list_display = (
        "name",
        "slug",
        "trait_type",
        "min_level",
        "max_level",
        "trait_cost_display",
        "rule_support_level",
    )
    search_fields = ("name", "slug")
    list_filter = ("trait_type",)
    ordering = ("trait_type", "name")
    inlines = (
        TraitExclusionInline,
        TraitExcludedByInline,
        TraitChoiceDefinitionInline,
        TraitSemanticEffectInline,
        TraitCharacterInline,
    )
    readonly_fields = ("rule_support_level", "semantic_modifier_preview", "semantic_editing_path", "build_rule_preview")
    fieldsets = (
        (
            "Trait",
            {
                "fields": (
                    ("name", "slug"),
                    ("trait_type", "points_per_level"),
                    "points_by_level",
                    ("min_level", "max_level"),
                    "description",
                )
            },
        ),
        (
            "Central Rule Layer",
            {
                "fields": ("rule_support_level", "semantic_modifier_preview", "semantic_editing_path", "build_rule_preview"),
                "description": (
                    "Traits are no longer treated as pure +X/-Y containers. "
                    "Semantic effects, flags, capabilities, social markers, trait-bound choices, and build rules are surfaced here. "
                    "Legacy modifier rows are not edited on traits anymore; "
                    "maintain new-system effects in the Choice Definitions and Semantic Effects inlines."
                ),
            },
        ),
    )

    @admin.display(description="Rule Support")
    def rule_support_level(self, obj):
        """Show whether the trait already has semantic central-engine support."""
        if not obj:
            return "-"
        return "Semantic + Data" if build_trait_semantic_modifiers(trait_slug=obj.slug, level=max(1, obj.min_level)) else "Data / Legacy"

    @admin.display(description="Costs")
    def trait_cost_display(self, obj):
        """Show linear or explicit per-level trait costs."""
        return obj.cost_display()

    @admin.display(description="Semantic Effects")
    def semantic_modifier_preview(self, obj):
        """Preview semantic central-engine effects for the trait definition."""
        return _trait_semantic_preview(obj, level=getattr(obj, "min_level", 1))

    @admin.display(description="Editing Path")
    def semantic_editing_path(self, obj):
        """Show where semantic trait effects are maintained in the new system."""
        return _trait_semantic_editing_path(obj)

    @admin.display(description="Build Rules")
    def build_rule_preview(self, obj):
        """Show the current build/creation interpretation of the trait."""
        return _trait_build_rule_preview(obj)


@admin.register(CharacterTrait)
class CharacterTraitAdmin(admin.ModelAdmin):
    """Admin configuration for character-owned trait levels."""
    list_display = ("owner", "trait", "trait_type", "trait_level", "rule_support_level")
    list_filter = ("trait__trait_type",)
    search_fields = ("owner__name", "trait__name", "trait__slug")
    autocomplete_fields = ("owner", "trait")
    list_select_related = ("owner", "trait")
    readonly_fields = (
        "trait_type",
        "rule_support_level",
        "trait_semantic_effects",
        "trait_semantic_editing_path",
        "trait_build_rule_preview",
    )
    fields = (
        "owner",
        "trait",
        "trait_level",
        "trait_type",
        "rule_support_level",
        "trait_semantic_effects",
        "trait_semantic_editing_path",
        "trait_build_rule_preview",
    )

    @admin.display(ordering="trait__trait_type", description="Trait Type")
    def trait_type(self, obj):
        """Return trait category for list display and sorting."""
        return obj.trait.trait_type

    @admin.display(description="Rule Support")
    def rule_support_level(self, obj):
        """Show whether the owned trait already has semantic central-engine support."""
        return (
            "Semantic + Data"
            if build_trait_semantic_modifiers(
                trait_slug=obj.trait.slug,
                level=max(1, obj.trait_level),
            )
            else "Data / Legacy"
        )

    @admin.display(description="Central Effects")
    def trait_semantic_effects(self, obj):
        """Preview semantic central-engine effects for the owned trait level."""
        return _trait_semantic_preview(obj.trait, level=obj.trait_level)

    @admin.display(description="Editing Path")
    def trait_semantic_editing_path(self, obj):
        """Show where semantic trait effects are maintained in the new system."""
        return _trait_semantic_editing_path(obj.trait)

    @admin.display(description="Build Rules")
    def trait_build_rule_preview(self, obj):
        """Show the current build/creation interpretation of the owned trait."""
        return _trait_build_rule_preview(obj.trait)


@admin.register(Language)
class LanguageAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
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


class DivineEntityAspectInline(admin.TabularInline):
    model = DivineEntityAspect
    extra = 0
    autocomplete_fields = ("aspect",)
    fields = ("aspect", "is_starting_aspect")


class DruidCultAspectInline(admin.TabularInline):
    model = DruidCultAspect
    extra = 0
    autocomplete_fields = ("aspect",)
    fields = ("aspect", "is_starting_aspect")


class CharacterBindingAspectInline(admin.TabularInline):
    model = CharacterAspect
    fk_name = "source_binding"
    extra = 0
    fields = ("aspect", "level", "source_entity", "source_school", "tracks_school_level", "is_bonus_aspect")
    autocomplete_fields = ("aspect", "source_entity", "source_school")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("aspect", "source_entity", "source_school")


class CharacterDivineEntityAdminForm(forms.ModelForm):
    class Meta:
        model = CharacterDivineEntity
        fields = "__all__"

    def clean_core_aspects(self):
        core_aspects = self.cleaned_data.get("core_aspects")
        entity = self.cleaned_data.get("entity")
        if entity is None or core_aspects is None:
            return core_aspects

        selected_count = core_aspects.count()
        if entity.aspect_selection_mode == DivineEntity.AspectSelectionMode.FIXED and selected_count:
            raise forms.ValidationError("Diese Entitaet nutzt feste Aspekte; bitte keine Kernaspekte am Charakter waehlen.")

        allowed_count = int(entity.starting_aspect_count or 0)
        if allowed_count > 0 and selected_count > allowed_count:
            raise forms.ValidationError(f"Diese Bindung erlaubt maximal {allowed_count} Kernaspekte.")

        if entity.aspect_selection_mode == DivineEntity.AspectSelectionMode.CHOOSE_FROM_ENTITY:
            allowed_ids = set(entity.aspects.values_list("aspect_id", flat=True))
            invalid = [aspect.name for aspect in core_aspects if aspect.id not in allowed_ids]
            if invalid:
                raise forms.ValidationError("Nicht erlaubte Aspekte: " + ", ".join(sorted(invalid)))

        return core_aspects


class CharacterDruidCultAdminForm(forms.ModelForm):
    class Meta:
        model = CharacterDruidCult
        fields = "__all__"

    def clean_core_aspects(self):
        core_aspects = self.cleaned_data.get("core_aspects")
        cult = self.cleaned_data.get("cult")
        if cult is None or core_aspects is None:
            return core_aspects

        selected_count = core_aspects.count()
        if cult.aspect_selection_mode == DivineEntity.AspectSelectionMode.FIXED and selected_count:
            raise forms.ValidationError("Dieser Druidenzirkel nutzt feste Aspekte; bitte keine Kernaspekte am Charakter waehlen.")

        allowed_count = int(cult.starting_aspect_count or 0)
        if allowed_count > 0 and selected_count > allowed_count:
            raise forms.ValidationError(f"Diese Bindung erlaubt maximal {allowed_count} Kernaspekte.")

        if cult.aspect_selection_mode == DivineEntity.AspectSelectionMode.CHOOSE_FROM_ENTITY:
            allowed_ids = set(cult.aspects.values_list("aspect_id", flat=True))
            invalid = [aspect.name for aspect in core_aspects if aspect.id not in allowed_ids]
            if invalid:
                raise forms.ValidationError("Nicht erlaubte Aspekte: " + ", ".join(sorted(invalid)))

        return core_aspects


class CharacterShamanPatronAdminForm(forms.ModelForm):
    class Meta:
        model = CharacterShamanPatron
        fields = "__all__"

    def clean_core_aspects(self):
        core_aspects = self.cleaned_data.get("core_aspects")
        patron = self.cleaned_data.get("patron")
        if patron is None or core_aspects is None:
            return core_aspects

        selected_count = core_aspects.count()
        if patron.aspect_selection_mode == DivineEntity.AspectSelectionMode.FIXED and selected_count:
            raise forms.ValidationError("Dieses Totem oder dieser Ahnengeist nutzt feste Aspekte; bitte keine Kernaspekte am Charakter waehlen.")

        allowed_count = int(patron.starting_aspect_count or 0)
        if allowed_count > 0 and selected_count > allowed_count:
            raise forms.ValidationError(f"Diese Bindung erlaubt maximal {allowed_count} Kernaspekte.")

        if patron.aspect_selection_mode == DivineEntity.AspectSelectionMode.CHOOSE_FROM_ENTITY:
            allowed_ids = set(patron.aspects.values_list("id", flat=True))
            invalid = [aspect.name for aspect in core_aspects if aspect.id not in allowed_ids]
            if invalid:
                raise forms.ValidationError("Nicht erlaubte Aspekte: " + ", ".join(sorted(invalid)))

        return core_aspects


@admin.register(Aspect)
class AspectAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "opposite",
        "has_aspect_image",
    )
    search_fields = ("name", "slug")
    list_filter = ("opposite",)
    ordering = ("name",)
    autocomplete_fields = ("opposite",)
    list_select_related = ("opposite",)
    readonly_fields = ("aspect_image_preview",)

    fieldsets = (
        (None, {
            "fields": (
                "name",
                "slug",
                "opposite",
            )
        }),
        ("Beschreibung", {
            "fields": (
                "description",
            )
        }),
        ("Symbol", {
            "fields": (
                "aspect_image",
                "aspect_image_preview",
            )
        }),
    )

    @admin.display(description="Symbol")
    def has_aspect_image(self, obj):
        return bool(obj.aspect_image)

    @admin.display(description="Symbolvorschau")
    def aspect_image_preview(self, obj):
        if obj is None or not obj.aspect_image:
            return format_html('<span style="color:#666;">{}</span>', "-")

        return format_html(
            '<img src="{}" alt="{}" style="max-width:96px; max-height:96px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.aspect_image.url,
            obj.name,
        )


@admin.register(Spell)
class SpellAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    form = SpellAdminForm
    list_display = ("name", "spell_owner", "spell_family", "grade", "panel_badge_label", "spell_attribute", "is_base_spell", "kp_cost")
    search_fields = ("name", "slug")
    list_filter = ("school", "aspect", "grade", "is_base_spell", "spell_attribute")
    ordering = ("school__name", "aspect__name", "grade", "name")
    autocomplete_fields = ("aspect", "spell_attribute")
    list_select_related = ("school", "school__type", "aspect", "spell_attribute")
    exclude = ("attribute",)
    fieldsets = (
        (
            "Quelle",
            {
                "fields": (
                    ("school", "aspect", "is_base_spell"),
                ),
            },
        ),
        (
            "Zauberdaten",
            {
                "fields": (
                    ("name", "slug", "panel_badge_label"),
                    ("spell_attribute", "grade", "grade_adds_level"),
                    ("mw", "grade_adds_school_level", "resistance_value"),
                    ("kp_cost", "kp_cost_label", "ep_cost", "ep_cost_label"),
                    ("extra_cost_type", "extra_cost_value"),
                    ("cast_time_number", "cast_time_unit"),
                    ("cast_time2_number", "cast_time2_unit"),
                    ("range_number", "range_unit", "range_per_grade", "range_text"),
                    (
                        "duration_number",
                        "duration_unit",
                        "duration_per_grade",
                        "duration_text",
                    ),
                    ("duration2_number", "duration2_unit", "duration2_per_grade", "duration2_text"),
                    "description",
                ),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "school":
            kwargs["queryset"] = db_field.related_model.objects.filter(
                type__slug="arcane"
            ).select_related("type")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Quelle")
    def spell_owner(self, obj):
        return obj.school or obj.aspect

    @admin.display(description="Zauberart")
    def spell_family(self, obj):
        if obj.school_id:
            return "Arkane Schule"
        if obj.aspect_id:
            return "Aspekt"
        return "-"


@admin.register(DivineEntity)
class DivineEntityAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "school",
        "pantheon",
        "aspect_selection_mode",
        "starting_aspect_count",
        "fixed_aspect_count",
        "is_customizable",
        "has_symbol_image",
        "has_god_image",
        "grants_arcane_spell_choice_per_level",
    )
    search_fields = ("name", "slug", "card_name", "pantheon")
    list_filter = (
        "aspect_selection_mode",
        "is_customizable",
        "school",
        "pantheon",
        "grants_arcane_spell_choice_per_level",
    )
    ordering = ("name",)
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")
    inlines = (DivineEntityAspectInline,)
    readonly_fields = ("symbol_image_preview", "god_image_preview")

    fieldsets = (
        (None, {
            "fields": (
                "name",
                "slug",
                "school",
                "aspect_selection_mode",
                "starting_aspect_count",
                "is_customizable",
            )
        }),
        ("Beschreibung", {
            "fields": (
                "divine_function",
                "vow",
                "description",
                "goals",
                "allies_and_enemies",
                "worshippers",
                "doctrines",
                "granted_abilities",
            )
        }),
        ("Regeloptionen", {
            "fields": (
                "grants_arcane_spell_choice_per_level",
            )
        }),
        ("Symbol", {
            "fields": (
                "symbol_image",
                "symbol_image_preview",
            )
        }),
        ("Goetterkarte", {
            "fields": (
                "card_name",
                "pantheon",
                "god_image",
                "god_image_preview",
                "g_ability",
                "fluff",
            )
        }),
    )

    @admin.display(description="Fixe Aspekte")
    def fixed_aspect_count(self, obj):
        return obj.aspects.filter(is_starting_aspect=True).count()

    @admin.display(description="Symbol")
    def has_symbol_image(self, obj):
        return bool(obj.symbol_image)

    @admin.display(description="Goetterbild")
    def has_god_image(self, obj):
        return bool(obj.god_image)

    @admin.display(description="Symbolvorschau")
    def symbol_image_preview(self, obj):
        if obj is None or not obj.symbol_image:
            return format_html('<span style="color:#666;">{}</span>', "-")

        return format_html(
            '<img src="{}" alt="{}" style="max-width:96px; max-height:96px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.symbol_image.url,
            obj.name,
        )

    @admin.display(description="Goetterbildvorschau")
    def god_image_preview(self, obj):
        if obj is None or not obj.god_image:
            return format_html('<span style="color:#666;">{}</span>', "-")

        return format_html(
            '<img src="{}" alt="{}" style="max-width:160px; max-height:220px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.god_image.url,
            obj.name,
        )


@admin.register(DruidCult)
class DruidCultAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "school",
        "aspect_selection_mode",
        "starting_aspect_count",
        "fixed_aspect_count",
        "is_customizable",
        "has_symbol_image",
        "has_god_image",
    )
    search_fields = ("name", "slug", "card_name", "description", "school__name")
    list_filter = ("aspect_selection_mode", "is_customizable", "school")
    ordering = ("name",)
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")
    readonly_fields = ("symbol_image_preview", "god_image_preview")
    inlines = (DruidCultAspectInline,)
    fieldsets = (
        (None, {
            "fields": (
                "name",
                "slug",
                "school",
                "aspect_selection_mode",
                "starting_aspect_count",
                "is_customizable",
                "description",
            )
        }),
        ("Karte", {
            "fields": (
                "card_name",
                "symbol_image",
                "symbol_image_preview",
                "god_image",
                "god_image_preview",
                "g_ability",
                "fluff",
            )
        }),
    )

    @admin.display(description="Fixe Aspekte")
    def fixed_aspect_count(self, obj):
        return obj.aspects.filter(is_starting_aspect=True).count()

    @admin.display(description="Symbol")
    def has_symbol_image(self, obj):
        return bool(obj.symbol_image)

    @admin.display(description="Kartenbild")
    def has_god_image(self, obj):
        return bool(obj.god_image)

    @admin.display(description="Symbolvorschau")
    def symbol_image_preview(self, obj):
        if obj is None or not obj.symbol_image:
            return format_html('<span style="color:#666;">{}</span>', "-")
        return format_html(
            '<img src="{}" alt="{}" style="max-width:96px; max-height:96px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.symbol_image.url,
            obj.name,
        )

    @admin.display(description="Kartenbildvorschau")
    def god_image_preview(self, obj):
        if obj is None or not obj.god_image:
            return format_html('<span style="color:#666;">{}</span>', "-")
        return format_html(
            '<img src="{}" alt="{}" style="max-width:160px; max-height:220px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.god_image.url,
            obj.name,
        )


@admin.register(ShamanPatron)
class ShamanPatronAdmin(AutoSlugAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "patron_kind",
        "school",
        "aspect_selection_mode",
        "starting_aspect_count",
        "fixed_aspect_count",
        "is_customizable",
        "has_symbol_image",
        "has_god_image",
    )
    search_fields = ("name", "slug", "card_name", "description", "school__name")
    list_filter = ("patron_kind", "aspect_selection_mode", "is_customizable", "school")
    ordering = ("patron_kind", "name")
    autocomplete_fields = ("school", "aspects")
    list_select_related = ("school", "school__type")
    readonly_fields = ("symbol_image_preview", "god_image_preview")
    fieldsets = (
        (None, {
            "fields": (
                "name",
                "slug",
                "patron_kind",
                "school",
                "aspect_selection_mode",
                "starting_aspect_count",
                "aspects",
                "is_customizable",
                "description",
            )
        }),
        ("Karte", {
            "fields": (
                "card_name",
                "symbol_image",
                "symbol_image_preview",
                "god_image",
                "god_image_preview",
                "g_ability",
                "fluff",
            )
        }),
    )

    @admin.display(description="Fixe Aspekte")
    def fixed_aspect_count(self, obj):
        return obj.aspects.count()

    @admin.display(description="Symbol")
    def has_symbol_image(self, obj):
        return bool(obj.symbol_image)

    @admin.display(description="Kartenbild")
    def has_god_image(self, obj):
        return bool(obj.god_image)

    @admin.display(description="Symbolvorschau")
    def symbol_image_preview(self, obj):
        if obj is None or not obj.symbol_image:
            return format_html('<span style="color:#666;">{}</span>', "-")
        return format_html(
            '<img src="{}" alt="{}" style="max-width:96px; max-height:96px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.symbol_image.url,
            obj.name,
        )

    @admin.display(description="Kartenbildvorschau")
    def god_image_preview(self, obj):
        if obj is None or not obj.god_image:
            return format_html('<span style="color:#666;">{}</span>', "-")
        return format_html(
            '<img src="{}" alt="{}" style="max-width:160px; max-height:220px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.god_image.url,
            obj.name,
        )


@admin.register(DivineEntityAspect)
class DivineEntityAspectAdmin(admin.ModelAdmin):
    list_display = ("entity", "aspect", "is_starting_aspect")
    search_fields = ("entity__name", "aspect__name", "aspect__slug")
    list_filter = ("is_starting_aspect", "entity", "aspect")
    ordering = ("entity__name", "aspect__name")
    autocomplete_fields = ("entity", "aspect")
    list_select_related = ("entity", "aspect")


@admin.register(DruidCultAspect)
class DruidCultAspectAdmin(admin.ModelAdmin):
    list_display = ("cult", "aspect", "is_starting_aspect")
    search_fields = ("cult__name", "aspect__name", "aspect__slug")
    list_filter = ("is_starting_aspect", "cult", "aspect")
    ordering = ("cult__name", "aspect__name")
    autocomplete_fields = ("cult", "aspect")
    list_select_related = ("cult", "aspect")


@admin.register(CharacterSpellSource)
class CharacterSpellSourceAdmin(admin.ModelAdmin):
    list_display = ("character", "label", "source_kind", "trait", "capacity", "used_slots", "remaining_slots", "is_active")
    search_fields = ("character__name", "label", "trait__name", "trait__slug")
    list_filter = ("source_kind", "is_active")
    ordering = ("character__name", "source_kind", "label")
    autocomplete_fields = ("character", "trait")
    list_select_related = ("character", "trait")

    @admin.display(description="Verbraucht")
    def used_slots(self, obj):
        return obj.granted_spells.count()

    @admin.display(description="Frei")
    def remaining_slots(self, obj):
        return max(0, int(obj.capacity) - int(obj.granted_spells.count()))


@admin.register(CharacterAspect)
class CharacterAspectAdmin(admin.ModelAdmin):
    list_display = ("character", "aspect", "level", "source_display", "tracks_school_level", "entry_mode")
    search_fields = ("character__name", "aspect__name", "aspect__slug", "source_entity__name", "source_binding__custom_name")
    list_filter = ("is_bonus_aspect", "tracks_school_level", "source_entity", "source_school", "aspect")
    ordering = ("character__name", "aspect__name")
    autocomplete_fields = ("character", "aspect", "source_entity", "source_binding", "source_school")
    list_select_related = ("character", "aspect", "source_entity", "source_binding", "source_school")
    readonly_fields = ("entry_mode",)

    @admin.display(description="Quelle")
    def source_display(self, obj):
        if obj.source_binding_id:
            return obj.source_binding.custom_name or obj.source_binding.entity.name
        if obj.source_school_id and obj.tracks_school_level:
            return obj.source_school
        return obj.source_entity or ("Bonusaspekt" if obj.is_bonus_aspect else "Automatisch")

    @admin.display(description="Modus")
    def entry_mode(self, obj):
        return "Manuell/Bonus" if obj.is_bonus_aspect else "Automatisch"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and not obj.is_bonus_aspect:
            readonly.extend(["character", "aspect", "source_entity", "source_binding", "source_school"])
        return tuple(dict.fromkeys(readonly))


@admin.register(CharacterDivineEntity)
class CharacterDivineEntityAdmin(admin.ModelAdmin):
    form = CharacterDivineEntityAdminForm
    list_display = ("character", "display_name", "entity", "entity_school", "chosen_aspect_count", "has_custom_god_image")
    search_fields = ("character__name", "entity__name", "entity__slug", "custom_name", "tradition_name")
    list_filter = ("entity__aspect_selection_mode", "entity__is_customizable", "entity__school")
    ordering = ("character__name",)
    autocomplete_fields = ("character", "entity")
    list_select_related = ("character", "entity", "entity__school")
    filter_horizontal = ("core_aspects",)
    readonly_fields = ("custom_god_image_preview",)

    fieldsets = (
        (None, {
            "fields": (
                "character",
                "entity",
                "core_aspects",
            )
        }),
        ("Persoenliche Auspraegung", {
            "fields": (
                "custom_name",
                "tradition_name",
                "custom_description",
                "custom_god_image",
                "custom_god_image_preview",
            )
        }),
    )

    @admin.display(description="Name")
    def display_name(self, obj):
        return obj.custom_name or obj.entity.name

    @admin.display(description="Kernaspekte")
    def chosen_aspect_count(self, obj):
        return obj.core_aspects.count()

    @admin.display(description="Eigenes Kartenbild")
    def has_custom_god_image(self, obj):
        return bool(obj.custom_god_image)

    @admin.display(description="Kartenbildvorschau")
    def custom_god_image_preview(self, obj):
        if obj is None or not obj.custom_god_image:
            return format_html('<span style="color:#666;">{}</span>', "-")

        return format_html(
            '<img src="{}" alt="{}" style="max-width:160px; max-height:220px; border-radius:8px; border:1px solid #ccc; background:#fff; padding:4px;" />',
            obj.custom_god_image.url,
            obj.custom_name or obj.entity.name,
        )

    @admin.display(description="Schule")
    def entity_school(self, obj):
        return obj.entity.school


@admin.register(CharacterDruidCult)
class CharacterDruidCultAdmin(admin.ModelAdmin):
    form = CharacterDruidCultAdminForm
    list_display = ("character", "cult", "cult_school", "chosen_aspect_count")
    search_fields = ("character__name", "cult__name", "cult__slug")
    list_filter = ("cult__school",)
    ordering = ("character__name",)
    autocomplete_fields = ("character", "cult")
    list_select_related = ("character", "cult", "cult__school")
    filter_horizontal = ("core_aspects",)

    @admin.display(description="Schule")
    def cult_school(self, obj):
        return obj.cult.school or "-"

    @admin.display(description="Kernaspekte")
    def chosen_aspect_count(self, obj):
        return obj.core_aspects.count()


@admin.register(CharacterShamanPatron)
class CharacterShamanPatronAdmin(admin.ModelAdmin):
    form = CharacterShamanPatronAdminForm
    list_display = ("character", "patron", "patron_kind", "patron_school", "chosen_aspect_count")
    search_fields = ("character__name", "patron__name", "patron__slug")
    list_filter = ("patron__patron_kind", "patron__school")
    ordering = ("character__name",)
    autocomplete_fields = ("character", "patron")
    list_select_related = ("character", "patron", "patron__school")
    filter_horizontal = ("core_aspects",)

    @admin.display(description="Art")
    def patron_kind(self, obj):
        return obj.patron.get_patron_kind_display()

    @admin.display(description="Schule")
    def patron_school(self, obj):
        return obj.patron.school or "-"

    @admin.display(description="Kernaspekte")
    def chosen_aspect_count(self, obj):
        return obj.core_aspects.count()


@admin.register(CharacterSpell)
class CharacterSpellAdmin(admin.ModelAdmin):
    list_display = ("character", "spell", "spell_owner", "source_kind", "granted_by_entity", "bonus_source", "entry_mode")
    search_fields = ("character__name", "spell__name", "spell__slug", "bonus_source__label", "granted_by_entity__name")
    list_filter = ("source_kind", "spell__school", "spell__aspect", "bonus_source", "granted_by_entity")
    ordering = ("character__name", "spell__name")
    autocomplete_fields = ("character", "spell", "bonus_source", "granted_by_entity")
    list_select_related = ("character", "spell", "spell__school", "spell__aspect", "bonus_source", "granted_by_entity")
    readonly_fields = ("entry_mode", "special_rule_flags")

    @admin.display(description="Quelle")
    def spell_owner(self, obj):
        return obj.spell.school or obj.spell.aspect

    @admin.display(description="Modus")
    def entry_mode(self, obj):
        automatic_kinds = {
            CharacterSpell.SourceKind.BASE,
            CharacterSpell.SourceKind.DIVINE_GRANTED,
            CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
        }
        return "Automatisch" if obj.source_kind in automatic_kinds else "Manuell/Auswahl"

    @admin.display(description="Sonderregeln")
    def special_rule_flags(self, obj):
        lines = []
        if obj.uses_divine_school_level:
            lines.append("Nutzt goettliche Schulstufe")
        if obj.ignore_critical_fumble_table:
            lines.append("Ignoriert Fehlschlagstabelle")
        if obj.granted_for_level:
            lines.append(f"Freigeschaltet auf Stufe {int(obj.granted_for_level)}")
        return _render_readonly_lines(lines)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        automatic_kinds = {
            CharacterSpell.SourceKind.BASE,
            CharacterSpell.SourceKind.DIVINE_GRANTED,
            CharacterSpell.SourceKind.DIVINE_ARCANE_GRANTED,
        }
        if obj is not None and obj.source_kind in automatic_kinds:
            readonly.extend(
                [
                    "character",
                    "spell",
                    "source_kind",
                    "bonus_source",
                    "granted_by_entity",
                    "granted_for_level",
                    "uses_divine_school_level",
                    "ignore_critical_fumble_table",
                ]
            )
        return tuple(dict.fromkeys(readonly))


@admin.register(CharacterDiaryEntry)
class CharacterDiaryEntryAdmin(admin.ModelAdmin):
    """Admin configuration for persisted diary roll entries."""

    list_display = ("character", "order_index", "entry_date", "is_fixed", "updated_at")
    search_fields = ("character__name", "text")
    list_filter = ("is_fixed", "entry_date")
    ordering = ("character", "order_index", "id")
    autocomplete_fields = ("character",)
    list_select_related = ("character",)


class CreatureAttackInline(admin.TabularInline):
    model = CreatureAttack
    extra = 0
    fields = ("order", "name", "attack_value", "damage_dice_amount", "damage_dice_faces", "damage_flat_operator", "damage_flat_bonus", "damage_type", "notes")


class CreatureSkillInline(admin.TabularInline):
    model = CreatureSkill
    extra = 0
    fields = ("skill", "level", "notes")
    autocomplete_fields = ("skill",)


class CreatureSpecialSkillValueInline(admin.TabularInline):
    model = CreatureSpecialSkillValue
    extra = 0
    fields = ("skill", "value", "notes")
    autocomplete_fields = ("skill",)


class CreatureCommandReferenceInline(admin.TabularInline):
    model = CreatureCommandReference
    extra = 0
    fields = ("order", "command")
    autocomplete_fields = ("command",)


class CreatureTraitInline(admin.TabularInline):
    model = CreatureTrait
    extra = 0
    fields = ("trait", "trait_level", "trait_points", "trait_semantic_effects")
    readonly_fields = ("trait_points", "trait_semantic_effects")
    autocomplete_fields = ("trait",)

    def trait_points(self, obj):
        if not obj or not obj.trait_id:
            return "-"
        return obj.trait.cost_display()

    def trait_semantic_effects(self, obj):
        if not obj or not obj.trait_id:
            return format_html('<span style="color:#666;">{}</span>', "Pick a trait and save to preview semantic effects.")
        return _creature_trait_semantic_preview(obj.trait, level=obj.trait_level)


class CreatureTraitChoiceInline(admin.TabularInline):
    model = CreatureTraitChoice
    extra = 0
    fields = (
        "definition",
        "selected_attribute",
        "selected_skill",
        "selected_skill_category",
        "selected_derived_stat",
        "selected_resource",
        "selected_proficiency_group",
        "selected_item",
        "selected_item_category",
        "selected_specialization",
        "selected_text",
        "selected_content_type",
        "selected_object_id",
    )
    autocomplete_fields = (
        "definition",
        "selected_attribute",
        "selected_skill",
        "selected_skill_category",
        "selected_item",
        "selected_specialization",
    )


class CharacterCreatureTraitChoiceInline(admin.TabularInline):
    model = CharacterCreatureTraitChoice
    extra = 0
    fields = CreatureTraitChoiceInline.fields
    autocomplete_fields = CreatureTraitChoiceInline.autocomplete_fields


class CreatureTraitChoiceDefinitionInline(admin.TabularInline):
    model = CreatureTraitChoiceDefinition
    extra = 0
    fields = (
        "sort_order",
        "name",
        "target_kind",
        "min_choices",
        "max_choices",
        "is_required",
        "is_active",
        "allowed_attribute",
        "allowed_skill_category",
        "allowed_skill_family",
        "allowed_derived_stat",
        "allowed_resource",
        "allowed_proficiency_group",
    )
    autocomplete_fields = ("allowed_attribute", "allowed_skill_category")


class CreatureTraitSemanticEffectInline(admin.StackedInline):
    model = CreatureTraitSemanticEffect
    extra = 0
    fields = (
        "sort_order",
        "target_choice_definition",
        "target_skills",
        "target_domain",
        "target_key",
        "operator",
        "mode",
        "value",
        "value_min",
        "value_max",
        "formula",
        "scaling",
        "stack_behavior",
        "condition_set",
        "active_flag",
        "priority",
        "notes",
        "rules_text",
        "visibility",
        "hidden",
        "sheet_relevant",
        "metadata",
    )
    autocomplete_fields = ("target_choice_definition", "target_skills")


class CreatureAdminForm(forms.ModelForm):
    strength_mod = forms.IntegerField(label="Staerke", required=False, initial=0)
    constitution_mod = forms.IntegerField(label="Konstitution", required=False, initial=0)
    dexterity_mod = forms.IntegerField(label="Geschick", required=False, initial=0)
    intelligence_mod = forms.IntegerField(label="Intelligenz", required=False, initial=0)
    perception_mod = forms.IntegerField(label="Wahrnehmung", required=False, initial=0)
    willpower_mod = forms.IntegerField(label="Willenskraft", required=False, initial=0)
    charisma_mod = forms.IntegerField(label="Charisma", required=False)

    ATTRIBUTE_FORM_FIELDS = {
        "strength_mod": "ST",
        "constitution_mod": "KON",
        "dexterity_mod": "GE",
        "intelligence_mod": "INT",
        "perception_mod": "WA",
        "willpower_mod": "WILL",
        "charisma_mod": "CHA",
    }

    class Meta:
        model = Creature
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            return
        values_by_code = {
            row.attribute.short_name: row.base_value
            for row in self.instance.attributes.select_related("attribute")
        }
        for field_name, code in self.ATTRIBUTE_FORM_FIELDS.items():
            self.fields[field_name].initial = values_by_code.get(code)

    def save(self, commit=True):
        creature = super().save(commit=commit)
        if commit:
            self._save_attribute_values(creature)
        else:
            save_m2m = self.save_m2m

            def save_m2m_with_attributes():
                save_m2m()
                if self.instance.pk:
                    self._save_attribute_values(self.instance)

            self.save_m2m = save_m2m_with_attributes
        return creature

    def save_m2m(self):
        super().save_m2m()
        if self.instance.pk:
            self._save_attribute_values(self.instance)

    def _save_attribute_values(self, creature):
        attributes = {
            attribute.short_name: attribute
            for attribute in Attribute.objects.filter(short_name__in=self.ATTRIBUTE_FORM_FIELDS.values())
        }
        for field_name, code in self.ATTRIBUTE_FORM_FIELDS.items():
            attribute = attributes.get(code)
            if attribute is None:
                continue
            CreatureAttribute.objects.update_or_create(
                creature=creature,
                attribute=attribute,
                defaults={"base_value": self.cleaned_data.get(field_name)},
            )


@admin.register(CreatureCardBinding)
class CreatureCardBindingAdmin(admin.ModelAdmin):
    list_display = ("creature", "trigger_type", "trigger_label", "active")
    search_fields = ("creature__name", "creature__card_name", "item_trigger__name", "technique_trigger__name", "note")
    list_filter = ("trigger_type", "active")
    autocomplete_fields = ("creature", "item_trigger", "technique_trigger")


class CharacterCreatureCardAttackInline(admin.TabularInline):
    model = CharacterCreatureCardAttack
    extra = 0
    fields = ("order", "name", "attack_value", "damage", "notes")


class CharacterCreatureCardSkillInline(admin.TabularInline):
    model = CharacterCreatureCardSkill
    extra = 0
    fields = ("order", "name", "value", "notes")


class CharacterCreatureCardTraitInline(admin.TabularInline):
    model = CharacterCreatureCardTrait
    extra = 0
    fields = ("order", "name", "level", "description")


class CharacterCreatureCardCommandPrerequisiteInline(admin.TabularInline):
    model = CharacterCreatureCardCommandPrerequisite
    fk_name = "command"
    extra = 0
    fields = ("alternative_group", "order", "prerequisite")
    autocomplete_fields = ("prerequisite",)


class CharacterCreatureCardCommandInline(admin.TabularInline):
    model = CharacterCreatureCardCommand
    extra = 0
    fields = ("order", "name", "slug", "ep_cost", "difficulty", "prerequisite_display", "description")
    readonly_fields = ("prerequisite_display",)


@admin.register(CharacterCreatureCard)
class CharacterCreatureCardAdmin(admin.ModelAdmin):
    list_display = ("name", "character", "creature", "trigger_label", "active", "has_source_deviations", "current_damage")
    search_fields = ("name", "character__name", "creature__name", "creature__card_name", "binding__item_trigger__name", "binding__technique_trigger__name")
    list_filter = ("active", "creature__size_class", "binding__trigger_type")
    autocomplete_fields = ("character", "creature", "binding")
    list_select_related = ("character", "creature", "binding", "binding__item_trigger", "binding__technique_trigger")
    readonly_fields = ("has_source_deviations", "trigger_label")
    inlines = (
        CharacterCreatureCardAttackInline,
        CharacterCreatureCardSkillInline,
        CharacterCreatureCardTraitInline,
        CharacterCreatureCardCommandInline,
    )
    fieldsets = (
        ("Zuordnung", {"fields": ("character", "creature", "binding", "active", "trigger_label", "has_source_deviations")}),
        ("Basis", {"fields": ("name", "creature_type", "image", "description", "source_reference", "current_damage", "notes")}),
        ("Werte", {"fields": ("initiative", "vw", "sr", "gw", "fear_resistance_bonus", "rs", "wound_step")}),
        ("Groesse", {"fields": ("size_class", "size_modifier")}),
        ("Bewegung", {"fields": ("combat_speed", "march_speed", "sprint_speed", "swimming_speed", "combat_fly_speed", "march_fly_speed", "sprint_fly_speed")}),
        ("Eigenschaften", {"fields": ("strength_mod", "constitution_mod", "dexterity_mod", "intelligence_mod", "perception_mod", "willpower_mod", "charisma_mod")}),
    )


@admin.register(Creature)
class CreatureAdmin(admin.ModelAdmin):
    form = CreatureAdminForm
    list_display = ("name", "size_class", "initiative_override", "natural_rs", "organization")
    search_fields = ("name", "slug", "card_name", "climate_and_occurrence", "organization")
    list_filter = ("size_class",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (
        CreatureAttackInline,
        CreatureSkillInline,
        CreatureSpecialSkillValueInline,
        CreatureCommandReferenceInline,
        CreatureTraitInline,
    )
    fieldsets = (
        ("Basis", {"fields": ("name", "slug", "card_name", "image", "description")}),
        (
            "Kampfwerte",
            {
                "fields": (
                    "initiative_override",
                    ("vw_override", "sr_override", "gw_override"),
                    ("natural_rs", "wound_step_override", "fear_resistance_bonus"),
                )
            },
        ),
        ("Groesse", {"fields": ("size_class", "size_modifier")}),
        (
            "Bewegung",
            {
                "fields": (
                    ("combat_speed", "march_speed", "sprint_speed", "swimming_speed"),
                    ("combat_fly_speed", "march_fly_speed", "sprint_fly_speed"),
                )
            },
        ),
        (
            "Eigenschaften",
            {
                "fields": (
                    ("strength_mod", "constitution_mod", "dexterity_mod"),
                    ("intelligence_mod", "perception_mod", "willpower_mod", "charisma_mod"),
                )
            },
        ),
        ("Vorkommen", {"fields": ("climate_and_occurrence", "organization")}),
    )


class CharacterCreatureItemInline(admin.TabularInline):
    model = CharacterCreatureItem
    extra = 0
    fields = ("item", "amount", "equipped", "quality", "armor_rs_total_override", "armor_encumbrance_override", "armor_min_st_override", "notes")
    autocomplete_fields = ("item",)


class CharacterCreatureSkillInline(admin.TabularInline):
    model = CharacterCreatureSkill
    extra = 0
    fields = ("skill", "level_override", "notes")
    autocomplete_fields = ("skill",)


class CharacterCreatureSpecialSkillInline(admin.TabularInline):
    model = CharacterCreatureSpecialSkill
    extra = 0
    fields = ("skill", "value_override", "notes")
    autocomplete_fields = ("skill",)


class CharacterCreatureTraitInline(admin.TabularInline):
    model = CharacterCreatureTrait
    extra = 0
    fields = ("base_trait", "trait", "trait_level", "active", "trait_points", "trait_semantic_effects")
    readonly_fields = ("trait_points", "trait_semantic_effects")
    autocomplete_fields = ("base_trait", "trait")

    def trait_points(self, obj):
        if not obj or not obj.trait_id:
            return "-"
        return obj.trait.cost_display()

    def trait_semantic_effects(self, obj):
        if not obj or not obj.trait_id:
            return format_html('<span style="color:#666;">{}</span>', "Pick a trait and save to preview semantic effects.")
        return _creature_trait_semantic_preview(obj.trait, level=obj.trait_level)


@admin.register(CharacterCreature)
class CharacterCreatureAdmin(admin.ModelAdmin):
    list_display = ("display_name", "owner", "creature", "active", "current_damage")
    search_fields = ("name_override", "owner__name", "creature__name", "creature__slug")
    list_filter = ("active", "creature__size_class")
    autocomplete_fields = ("owner", "creature")
    list_select_related = ("owner", "creature")
    inlines = (
        CharacterCreatureItemInline,
        CharacterCreatureSkillInline,
        CharacterCreatureSpecialSkillInline,
        CharacterCreatureTraitInline,
    )
    fieldsets = (
        ("Basis", {"fields": ("owner", "creature", "name_override", "image_override", "active", "current_damage", "notes")}),
        ("Groesse", {"fields": ("size_class_override", "size_modifier_override")}),
        (
            "Eigenschafts-Overrides",
            {
                "fields": (
                    "strength_mod_override",
                    "constitution_mod_override",
                    "dexterity_mod_override",
                    "intelligence_mod_override",
                    "perception_mod_override",
                    "willpower_mod_override",
                    "charisma_mod_override",
                )
            },
        ),
        ("Werte-Overrides", {"fields": ("initiative_override", "vw_override", "sr_override", "gw_override", "fear_resistance_bonus_override", "natural_rs_override", "wound_step_override")}),
        ("Bewegungs-Overrides", {"fields": ("combat_speed_override", "march_speed_override", "sprint_speed_override", "swimming_speed_override", "combat_fly_speed_override", "march_fly_speed_override", "sprint_fly_speed_override")}),
    )


@admin.register(CharacterCreatureItem)
class CharacterCreatureItemAdmin(admin.ModelAdmin):
    list_display = ("creature", "item", "equipped", "quality", "amount")
    search_fields = ("creature__name_override", "creature__creature__name", "item__name")
    list_filter = ("equipped", "quality", "item__item_type")
    autocomplete_fields = ("creature", "item")
    list_select_related = ("creature", "creature__creature", "item")


@admin.register(CreatureAttack)
class CreatureAttackAdmin(admin.ModelAdmin):
    list_display = ("creature", "name", "attack_value", "damage_dice_amount", "damage_dice_faces", "damage_flat_operator", "damage_flat_bonus", "damage_type")
    search_fields = ("creature__name", "name")
    autocomplete_fields = ("creature",)
    list_select_related = ("creature",)


@admin.register(CreatureSkill)
class CreatureSkillAdmin(admin.ModelAdmin):
    list_display = ("creature", "skill", "level")
    search_fields = ("creature__name", "skill__name")
    autocomplete_fields = ("creature", "skill")
    list_select_related = ("creature", "skill")


@admin.register(CreatureSpecialSkill)
class CreatureSpecialSkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CreatureSpecialSkillValue)
class CreatureSpecialSkillValueAdmin(admin.ModelAdmin):
    list_display = ("creature", "skill", "value")
    search_fields = ("creature__name", "skill__name", "skill__slug")
    autocomplete_fields = ("creature", "skill")
    list_select_related = ("creature", "skill")


@admin.register(CreatureTraitDefinition)
class CreatureTraitDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "trait_type", "min_level", "max_level", "cost_display")
    search_fields = ("name", "slug", "description")
    list_filter = ("trait_type",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("semantic_effect_preview",)
    inlines = (CreatureTraitChoiceDefinitionInline, CreatureTraitSemanticEffectInline)
    fieldsets = (
        ("Basis", {"fields": ("name", "slug", "trait_type", "description")}),
        ("Ranks & Costs", {"fields": ("min_level", "max_level", "points_per_level", "points_by_level")}),
        ("Semantic Preview", {"fields": ("semantic_effect_preview",)}),
    )

    def semantic_effect_preview(self, obj):
        return _creature_trait_semantic_preview(obj)


@admin.register(CreatureTraitChoiceDefinition)
class CreatureTraitChoiceDefinitionAdmin(admin.ModelAdmin):
    list_display = ("trait", "name", "target_kind", "min_choices", "max_choices", "is_active")
    search_fields = ("trait__name", "trait__slug", "name", "description")
    list_filter = ("target_kind", "is_required", "is_active")
    autocomplete_fields = ("trait", "allowed_attribute", "allowed_skill_category")
    list_select_related = ("trait", "allowed_attribute", "allowed_skill_category")


@admin.register(CreatureTraitSemanticEffect)
class CreatureTraitSemanticEffectAdmin(admin.ModelAdmin):
    list_display = ("trait", "target_domain", "target_key", "operator", "active_flag", "sort_order")
    search_fields = ("trait__name", "trait__slug", "target_key", "notes", "rules_text")
    list_filter = ("target_domain", "operator", "active_flag", "visibility")
    autocomplete_fields = ("trait", "target_choice_definition", "target_skills")
    list_select_related = ("trait", "target_choice_definition")


class CreatureCommandPrerequisiteInline(admin.TabularInline):
    model = CreatureCommandPrerequisite
    fk_name = "command"
    extra = 0
    fields = ("alternative_group", "order", "prerequisite")
    autocomplete_fields = ("prerequisite",)


@admin.register(CreatureCommand)
class CreatureCommandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "ep_cost", "difficulty", "prerequisite_display")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (CreatureCommandPrerequisiteInline,)


@admin.register(CharacterCreatureCardCommand)
class CharacterCreatureCardCommandAdmin(admin.ModelAdmin):
    list_display = ("card", "name", "slug", "ep_cost", "difficulty", "prerequisite_display", "order")
    search_fields = ("card__name", "name", "slug", "description")
    autocomplete_fields = ("card",)
    list_select_related = ("card",)
    inlines = (CharacterCreatureCardCommandPrerequisiteInline,)


@admin.register(CreatureCommandReference)
class CreatureCommandReferenceAdmin(admin.ModelAdmin):
    list_display = ("creature", "command", "order")
    search_fields = ("creature__name", "command__name", "command__slug")
    autocomplete_fields = ("creature", "command")
    list_select_related = ("creature", "command")


@admin.register(CreatureTrait)
class CreatureTraitAdmin(admin.ModelAdmin):
    list_display = ("creature", "trait", "trait_level")
    search_fields = ("creature__name", "trait__name")
    autocomplete_fields = ("creature", "trait")
    list_select_related = ("creature", "trait")
    inlines = (CreatureTraitChoiceInline,)


@admin.register(CreatureTraitChoice)
class CreatureTraitChoiceAdmin(admin.ModelAdmin):
    list_display = ("creature_trait", "definition", "selected_target_display")
    search_fields = ("creature_trait__creature__name", "creature_trait__trait__name", "definition__name")
    autocomplete_fields = CreatureTraitChoiceInline.autocomplete_fields
    list_select_related = ("creature_trait", "creature_trait__creature", "creature_trait__trait", "definition")


@admin.register(CharacterCreatureSkill)
class CharacterCreatureSkillAdmin(admin.ModelAdmin):
    list_display = ("creature", "skill", "level_override")
    search_fields = ("creature__name_override", "creature__creature__name", "skill__name")
    autocomplete_fields = ("creature", "skill")
    list_select_related = ("creature", "creature__creature", "skill")


@admin.register(CharacterCreatureSpecialSkill)
class CharacterCreatureSpecialSkillAdmin(admin.ModelAdmin):
    list_display = ("creature", "skill", "value_override")
    search_fields = ("creature__name_override", "creature__creature__name", "skill__name", "skill__slug")
    autocomplete_fields = ("creature", "skill")
    list_select_related = ("creature", "creature__creature", "skill")


@admin.register(CharacterCreatureTrait)
class CharacterCreatureTraitAdmin(admin.ModelAdmin):
    list_display = ("creature", "trait", "trait_level", "active")
    search_fields = ("creature__name_override", "creature__creature__name", "trait__name", "base_trait__trait__name")
    autocomplete_fields = ("creature", "base_trait", "trait")
    list_select_related = ("creature", "creature__creature", "base_trait", "trait")
    inlines = (CharacterCreatureTraitChoiceInline,)


@admin.register(CharacterCreatureTraitChoice)
class CharacterCreatureTraitChoiceAdmin(admin.ModelAdmin):
    list_display = ("character_creature_trait", "definition", "selected_target_display")
    search_fields = (
        "character_creature_trait__creature__name_override",
        "character_creature_trait__creature__creature__name",
        "character_creature_trait__trait__name",
        "definition__name",
    )
    autocomplete_fields = CharacterCreatureTraitChoiceInline.autocomplete_fields
    list_select_related = (
        "character_creature_trait",
        "character_creature_trait__creature",
        "character_creature_trait__trait",
        "definition",
    )


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    """Admin configuration for per-user sheet integration settings."""

    list_display = ("user", "radial_menu_enabled", "dddice_enabled", "dddice_room_id", "dddice_dice_box", "dddice_theme_id")
    search_fields = ("user__username", "user__email", "dddice_room_id", "dddice_dice_box", "dddice_theme_id")
    list_filter = ("radial_menu_enabled", "dddice_enabled",)
    ordering = ("user",)
    fieldsets = (
        ("Benutzer", {"fields": ("user",)}),
        (
            "Charsheet",
            {
                "fields": ("radial_menu_enabled",)
            },
        ),
        (
            "dddice",
            {
                "fields": (
                    "dddice_enabled",
                    "dddice_api_key",
                    "dddice_room_id",
                    "dddice_room_password",
                    "dddice_dice_box",
                    "dddice_theme_id",
                )
            },
        ),
    )
    autocomplete_fields = ("user",)
    list_select_related = ("user",)


_install_inline_help(ModifierInline, help_texts=MODIFIER_CHOICE_HELP, labels=MODIFIER_LABELS)
_install_inline_help(ProgressionRuleInline, help_texts=PROGRESSION_RULE_CHOICE_HELP)
_install_inline_help(TechniqueInline, help_texts=TECHNIQUE_CHOICE_HELP, labels=TECHNIQUE_LABELS)
_install_inline_help(
    TechniqueChoiceBlockInline,
    help_texts=TECHNIQUE_CHOICE_BLOCK_HELP,
    labels=TECHNIQUE_CHOICE_BLOCK_LABELS,
)
_install_inline_help(TechniqueChoiceDefinitionInline, help_texts=TECHNIQUE_CHOICE_DEFINITION_HELP)
_install_inline_help(RaceChoiceDefinitionInline, help_texts=RACE_CHOICE_DEFINITION_HELP, labels=RACE_CHOICE_DEFINITION_LABELS)
_install_inline_help(SpecializationInline, help_texts=SPECIALIZATION_CHOICE_HELP, labels=SPECIALIZATION_LABELS)
_install_inline_help(WeaponStatsInline, help_texts=WEAPON_CHOICE_HELP)
_install_inline_help(ShieldStatsInline, help_texts=SHIELD_CHOICE_HELP)

_install_admin_help(AttributeAdmin, help_texts=ATTRIBUTE_CHOICE_HELP)
_install_admin_help(SkillCategoryAdmin, help_texts=SKILL_CATEGORY_CHOICE_HELP)
_install_admin_help(RaceAdmin, help_texts=SIZE_CLASS_HELP, labels=RACE_ADMIN_LABELS)
_install_admin_help(CharacterAdmin, help_texts=CHARACTER_CHOICE_HELP)
_install_admin_help(SchoolTypeAdmin, help_texts=SCHOOL_TYPE_CHOICE_HELP)
_install_admin_help(ProgressionRuleAdmin, help_texts=PROGRESSION_RULE_CHOICE_HELP)
_install_admin_help(ModifierAdmin, help_texts=MODIFIER_CHOICE_HELP, labels=MODIFIER_LABELS)
_install_admin_help(SchoolAdmin, labels=SCHOOL_ADMIN_LABELS)
_install_admin_help(TechniqueAdmin, help_texts=TECHNIQUE_CHOICE_HELP, labels=TECHNIQUE_LABELS)
_install_admin_help(
    TechniqueChoiceBlockAdmin,
    help_texts=TECHNIQUE_CHOICE_BLOCK_HELP,
    labels=TECHNIQUE_CHOICE_BLOCK_LABELS,
)
_install_admin_help(TechniqueChoiceDefinitionAdmin, help_texts=TECHNIQUE_CHOICE_DEFINITION_HELP)
_install_admin_help(RaceChoiceDefinitionAdmin, help_texts=RACE_CHOICE_DEFINITION_HELP, labels=RACE_CHOICE_DEFINITION_LABELS)
_install_admin_help(SpecializationAdmin, help_texts=SPECIALIZATION_CHOICE_HELP, labels=SPECIALIZATION_LABELS)
_install_admin_help(ItemAdmin, help_texts=ITEM_CHOICE_HELP)
_install_admin_help(WeaponStatsAdmin, help_texts=WEAPON_CHOICE_HELP)
_install_admin_help(ShieldStatsAdmin, help_texts=SHIELD_CHOICE_HELP)
_install_admin_help(TraitAdmin, help_texts=TRAIT_CHOICE_HELP)
