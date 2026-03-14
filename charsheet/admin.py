"""Django admin configuration for character sheet domain models."""

from collections import defaultdict
from copy import deepcopy

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Q
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from .constants import QUALITY_COLOR_MAP
from .engine.item_engine import ItemEngine
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
    CharacterSpecialization,
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
    ShieldStats,
    Specialization,
    Skill,
    SkillCategory,
    Technique,
    TechniqueChoiceBlock,
    TechniqueChoiceDefinition,
    TechniqueExclusion,
    TechniqueRequirement,
    Trait,
    WeaponStats,
)

ArmorStats._meta.verbose_name = "Armor Stats"
ArmorStats._meta.verbose_name_plural = "Armor Stats"
ShieldStats._meta.verbose_name = "Shield Stats"
ShieldStats._meta.verbose_name_plural = "Shield Stats"
WeaponStats._meta.verbose_name = "Weapon Stats"
WeaponStats._meta.verbose_name_plural = "Weapon Stats"


def _quality_badge(quality: str):
    """Render one quality key with configured RPG color coding."""
    resolved_quality = ItemEngine.normalize_quality(quality)
    color = QUALITY_COLOR_MAP.get(resolved_quality, QUALITY_COLOR_MAP[ItemEngine.normalize_quality(None)])
    return format_html(
        '<strong style="color:{};text-shadow:-0.75px -0.75px 0 #000,0.75px -0.75px 0 #000,-0.75px 0.75px 0 #000,0.75px 0.75px 0 #000;">{}</strong>',
        color,
        resolved_quality,
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


def _format_technique_requirements(technique):
    """Return readable rulebook-style requirement summaries for one technique."""
    rows = []
    for requirement in technique.requirements.all():
        if requirement.minimum_school_level is not None:
            rows.append(f"Schulstufe {requirement.minimum_school_level}+")
        elif requirement.required_technique_id is not None:
            rows.append(f"Technik: {requirement.required_technique.name}")
        elif requirement.required_path_id is not None:
            rows.append(f"Pfad: {requirement.required_path.name}")
        elif requirement.required_skill_id is not None:
            rows.append(f"Fertigkeit: {requirement.required_skill.name} {requirement.required_skill_level}+")
        elif requirement.required_trait_id is not None:
            rows.append(f"Eigenschaft: {requirement.required_trait.name} {requirement.required_trait_level}+")
    return rows or ["Keine"]


def _format_technique_exclusions(technique):
    """Return readable names of excluded techniques."""
    rows = {relation.excluded_technique.name for relation in technique.exclusions.all()}
    rows.update(relation.technique.name for relation in technique.excluded_by.all())
    return sorted(rows) or ["Keine"]


def _format_technique_choice_definitions(technique):
    """Return readable summaries of stored choice requirements for one technique."""
    rows = []
    for definition in technique.choice_definitions.all():
        if not definition.is_active:
            continue
        range_label = f"{definition.min_choices}-{definition.max_choices}" if definition.min_choices != definition.max_choices else str(definition.max_choices)
        description = f" ({definition.description})" if definition.description else ""
        rows.append(f"{definition.name}: {definition.get_target_kind_display()} [{range_label}]{description}")
    if not rows and technique.choice_target_kind != Technique.ChoiceTargetKind.NONE:
        rows.append(
            f"Legacy-Entscheidung: {technique.get_choice_target_kind_display()} [{technique.choice_limit}]"
        )
    return rows or ["Keine"]


def _format_choice_group_notice(technique):
    """Explain that choice_group is informational only."""
    if not technique or not technique.choice_group:
        return "-"
    return f"{technique.choice_group} (nur Anzeige/Import, keine Regelmechanik)"


def _format_technique_rule_context_html(technique):
    """Render a compact rulebook-style preview for one technique."""
    if technique is None:
        return "-"
    rows = [
        ("Schule", technique.school.name),
        ("Stufe", technique.level),
        ("Pfad", technique.path.name if technique.path_id else "Alle Pfade"),
        ("Erwerbsart", technique.get_acquisition_type_display()),
        ("Support", technique.get_support_level_display()),
        ("Voraussetzungen", ", ".join(_format_technique_requirements(technique))),
        ("Ausschluesse", ", ".join(_format_technique_exclusions(technique))),
        ("Wahlentscheidungen", ", ".join(_format_technique_choice_definitions(technique))),
        ("Spezialisierungs-Slots", technique.specialization_slot_grants or 0),
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
        ("1. Schule", "Grunddaten und Kurzbeschreibung der Schule pflegen."),
        ("2. Schulpfade", "Optionale Pfade der Schule anlegen, falls das Regelwerk welche vorsieht."),
        ("3. Techniken nach Stufe", "Techniken in der Lesereihenfolge Schule -> Stufe -> Pfad -> Technik erfassen."),
        ("4. Technikvoraussetzungen", "Auf der einzelnen Technik werden Mindeststufen, Pfade, Techniken, Fertigkeiten oder Eigenschaften hinterlegt."),
        ("5. Technik-Ausschluesse", "Auf der einzelnen Technik festhalten, welche anderen Techniken sie regeltechnisch ausschliesst."),
        ("6. Wahlentscheidungen einer Technik", "Auf der einzelnen Technik speichern, welche dauerhaften Entscheidungen noch getroffen werden muessen."),
        ("7. Spezialisierungs-Slots", "Slots entstehen nur durch tatsaechlich gelernte Techniken mit specialization_slot_grants."),
        ("8. Spezialisierungen", "Schulgebundene Spezialisierungen separat pflegen; sie sind keine Techniken."),
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
        return "Nach dem ersten Speichern erscheinen hier die angelegten Schulpfade."

    path_rows = []
    for path in school.paths.all():
        technique_count = school.techniques.filter(path=path).count()
        block_count = school.technique_choice_blocks.filter(path=path).count()
        description = f" | {path.description}" if path.description else ""
        path_rows.append((path.name, technique_count, block_count, description))

    if not path_rows:
        return "Keine Schulpfade gepflegt."

    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            "<div><strong>{}</strong>: {} Techniken, {} Wahlbloecke{}</div>",
            path_rows,
        ),
    )


def _format_school_choice_block_overview_html(school):
    """Summarize school-level choice blocks so the rulebook structure is visible."""
    if not school or not getattr(school, "pk", None):
        return "Nach dem ersten Speichern erscheinen hier die vorhandenen Wahlbloecke."

    blocks = list(
        school.technique_choice_blocks.select_related("path").prefetch_related("techniques").order_by(
            "level",
            "sort_order",
            "name",
            "id",
        )
    )
    if not blocks:
        return "Keine Wahlbloecke gepflegt."

    block_rows = []
    for block in blocks:
        level = f"Stufe {block.level}" if block.level is not None else "stufenunabhaengig"
        path = block.path.name if block.path_id else "alle Pfade"
        techniques = ", ".join(block.techniques.order_by("name").values_list("name", flat=True)) or "noch keine"
        label = block.name or "Unbenannter Wahlblock"
        description = f" | {block.description}" if block.description else ""
        block_rows.append((label, level, path, block.min_choices, block.max_choices, techniques, description))

    return format_html(
        "<div>{}</div>",
        format_html_join(
            "",
            (
                "<div><strong>{}</strong>: {} | Pfad: {} | Wahlumfang: {}-{} | "
                "Techniken: {}{}</div>"
            ),
            block_rows,
        ),
    )


def _format_school_technique_overview_html(school):
    """Render techniques grouped by level to mirror the rulebook reading order."""
    if not school or not getattr(school, "pk", None):
        return "Nach dem ersten Speichern erscheinen hier die Techniken gruppiert nach Schulstufe."

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
        return "Keine Techniken gepflegt."

    grouped_techniques = defaultdict(list)
    for technique in techniques:
        grouped_techniques[technique.level].append(technique)

    level_blocks = []
    for level in sorted(grouped_techniques):
        rows = []
        for technique in grouped_techniques[level]:
            path_name = technique.path.name if technique.path_id else "Alle Pfade"
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
                "<div><h4 style='margin:0.75em 0 0.25em;'>Stufe {}</h4>{}</div>",
                level,
                format_html_join(
                    "",
                    (
                        "<div style='margin-left:1rem;'><strong>{}</strong>: Pfad {} | Erwerb {} | "
                        "Wahlblock {} | Voraussetzungen {} | Ausschluesse {} | Entscheidungen {} | "
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
        return "Nach dem ersten Speichern erscheinen hier die Spezialisierungen der Schule."

    specializations = list(school.specializations.order_by("sort_order", "name"))
    if not specializations:
        return "Keine Spezialisierungen gepflegt."

    spec_rows = []
    for specialization in specializations:
        active_state = "aktiv" if specialization.is_active else "inaktiv"
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


class RaceAttributeLimitInline(admin.TabularInline):
    """Inline editor for race-specific attribute limits."""

    model = RaceAttributeLimit
    extra = 0
    show_change_link = True
    autocomplete_fields = ("attribute",)


class ModifierInline(GenericStackedInline):
    """Generic inline editor for modifiers attached to source models."""

    model = Modifier
    verbose_name_plural = "Regelmodifikatoren"
    ct_field = "source_content_type"
    ct_fk_field = "source_object_id"
    extra = 0
    show_change_link = True
    classes = ("collapse",)
    fieldsets = (
        (
            "Target",
            {
                "fields": (
                    ("target_kind", "target_slug"),
                    ("target_skill", "target_skill_category"),
                    ("target_item", "target_specialization"),
                    ("target_content_type", "target_object_id"),
                )
            },
        ),
        ("Value", {"fields": (("mode", "value"),)}),
        ("Scaling", {"fields": (("scale_source", "scale_school"), ("mul", "div", "round_mode"))}),
        ("Cap", {"fields": (("cap_mode", "cap_source"), "min_school_level")}),
    )
    autocomplete_fields = (
        "scale_school",
        "target_skill",
        "target_skill_category",
        "target_item",
        "target_specialization",
    )


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
    verbose_name_plural = "Schulpfade"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("school", "path")


class CharacterTechniqueInline(admin.TabularInline):
    """Inline editor for a character's explicitly learned techniques."""

    model = CharacterTechnique
    verbose_name_plural = "Gelernte Techniken"
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
        return obj.technique.get_support_level_display()

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Show persistent choice guidance for the linked technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _format_technique_choice_context(obj.technique)


class CharacterTechniqueChoiceInline(admin.StackedInline):
    """Inline editor for persistent character technique choices."""

    model = CharacterTechniqueChoice
    verbose_name_plural = "Technik-Wahlentscheidungen"
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
            "Technik",
            {
                "fields": (
                    ("technique", "definition"),
                    ("technique_school", "choice_target_kind"),
                    "technique_choice_context",
                )
            },
        ),
        (
            "Gewaehltes Ziel",
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
                    | ~Q(choice_target_kind=Technique.ChoiceTargetKind.NONE)
                )
                .select_related("school", "path")
                .distinct()
                .order_by("school__name", "level", "name")
            )
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
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
        if obj.definition_id:
            return obj.definition.get_target_kind_display()
        return obj.technique.get_choice_target_kind_display()

    @admin.display(description="Choice Notes")
    def technique_choice_context(self, obj):
        """Show editor-facing notes for the linked choice technique."""
        if not obj or not obj.technique_id:
            return "-"
        return _format_technique_choice_context(obj.technique)


class CharacterSpecializationInline(admin.TabularInline):
    """Inline editor for school-bound character specializations."""

    model = CharacterSpecialization
    verbose_name_plural = "Spezialisierungen"
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


class SchoolInline(admin.TabularInline):
    """Inline editor for schools inside a school type."""

    model = School
    extra = 0
    show_change_link = True


class TechniqueInline(admin.TabularInline):
    """Inline editor for techniques belonging to one school."""

    model = Technique
    verbose_name_plural = "Techniken nach Stufe"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("path", "choice_block")
    fields = (
        "name",
        "level",
        "path",
        "acquisition_type",
        "choice_block",
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
            .select_related("school", "path", "choice_block")
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

    @admin.display(description="Kurzinfo")
    def inline_rule_hint(self, obj):
        """Show only the most important rule hints in the school overview."""
        if not obj or not obj.pk:
            return "-"
        parts = []
        requirements = ", ".join(_format_technique_requirements(obj))
        if requirements != "Keine":
            parts.append(f"Voraussetzungen: {requirements}")
        exclusions = ", ".join(_format_technique_exclusions(obj))
        if exclusions != "Keine":
            parts.append(f"Ausschluesse: {exclusions}")
        choices = ", ".join(_format_technique_choice_definitions(obj))
        if choices != "Keine":
            parts.append(f"Entscheidungen: {choices}")
        if obj.choice_group:
            parts.append("choice_group nur fuer Anzeige/Import")
        return " | ".join(parts) if parts else "Details ueber den Aendern-Link."


class TechniqueChoiceBlockInline(admin.TabularInline):
    """Inline editor for generic school-level technique choice blocks."""

    model = TechniqueChoiceBlock
    verbose_name_plural = "Technik-Wahlbloecke"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("path",)
    fields = ("name", "level", "path", "min_choices", "max_choices", "sort_order", "block_hint")
    readonly_fields = ("block_hint",)
    ordering = ("level", "sort_order", "name")

    def get_queryset(self, request):
        """Prefetch related techniques for readable block summaries."""
        return super().get_queryset(request).select_related("school", "path").prefetch_related("techniques")

    @admin.display(description="Kurzinfo")
    def block_hint(self, obj):
        """Keep the choice block overview compact and understandable."""
        if not obj or not obj.pk:
            return "-"
        techniques = ", ".join(obj.techniques.order_by("level", "name").values_list("name", flat=True)) or "noch keine Techniken"
        if obj.description:
            return f"{obj.description} | Techniken: {techniques}"
        return f"Techniken: {techniques}"


class SpecializationInline(admin.TabularInline):
    """Inline editor for school-bound specializations."""

    model = Specialization
    verbose_name_plural = "Spezialisierungen"
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
    verbose_name_plural = "Zugeordnete Charaktere"
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
    verbose_name_plural = "Schulpfade"
    extra = 0
    show_change_link = True


class TechniqueRequirementInline(admin.TabularInline):
    """Inline editor for structured technique requirements."""

    model = TechniqueRequirement
    verbose_name_plural = "Technikvoraussetzungen"
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
    verbose_name_plural = "Technik-Ausschluesse"
    fk_name = "technique"
    extra = 0
    show_change_link = True
    autocomplete_fields = ("excluded_technique",)


class TechniqueChoiceDefinitionInline(admin.TabularInline):
    """Inline editor for persistent technique choice definitions."""

    model = TechniqueChoiceDefinition
    verbose_name_plural = "Wahlentscheidungen"
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
    fields = ("owner", "amount", "quality", "equipped")


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


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
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

    list_display = ("name", "type", "type_slug", "path_count", "choice_block_count", "technique_count", "specialization_count")
    search_fields = ("name", "type__name", "type__slug")
    list_filter = ("type",)
    ordering = ("type", "name")
    readonly_fields = ("rulebook_editor_guide",)
    fieldsets = (
        (
            "Schule",
            {
                "fields": (
                    ("name", "type"),
                    "description",
                ),
                "description": "Regelbuchorientierter Einstiegspunkt. Von hier aus werden Pfade, Wahlbloecke, Techniken und Spezialisierungen gepflegt.",
            },
        ),
        (
            "Pflegehinweis",
            {
                "fields": ("rulebook_editor_guide",),
                "description": "Erst Grunddaten speichern, danach die Inlines von oben nach unten pflegen.",
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
    autocomplete_fields = ("type",)
    list_select_related = ("type",)

    @admin.display(ordering="type__slug", description="Schultyp-Schluessel")
    def type_slug(self, obj):
        """Return the related school type slug for list display."""
        return obj.type.slug

    @admin.display(description="Pflegereihenfolge")
    def rulebook_editor_guide(self, obj):
        """Explain the recommended rulebook-oriented editing order."""
        return _format_school_rulebook_guide_html()

    @admin.display(ordering="name", description="Pfade")
    def path_count(self, obj):
        """Return how many paths are configured for the school."""
        return obj.paths.count()

    @admin.display(ordering="name", description="Wahlbloecke")
    def choice_block_count(self, obj):
        """Return how many choice blocks are configured for the school."""
        return obj.technique_choice_blocks.count()

    @admin.display(ordering="name", description="Techniken")
    def technique_count(self, obj):
        """Return how many techniques are configured for the school."""
        return obj.techniques.count()

    @admin.display(ordering="name", description="Spezialisierungen")
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
        "target_display_value",
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
    search_fields = ("target_slug", "target_skill__name", "target_skill_category__name", "target_item__name", "target_specialization__name")
    ordering = ("source_content_type", "source_object_id", "target_kind", "target_slug")
    autocomplete_fields = ("scale_school", "target_skill", "target_skill_category", "target_item", "target_specialization")
    list_select_related = ("scale_school", "target_skill", "target_skill_category", "target_item", "target_specialization")

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


@admin.register(Technique)
class TechniqueAdmin(admin.ModelAdmin):
    """Admin configuration for techniques, including support and choice metadata."""

    list_display = (
        "name",
        "school",
        "path",
        "level",
        "acquisition_type",
        "choice_block",
        "specialization_slot_grants",
        "support_level",
        "choice_marker",
    )
    search_fields = (
        "name",
        "school__name",
        "school__type__name",
        "choice_block__name",
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
        "choice_target_kind",
        "specialization_slot_grants",
        "action_type",
        "usage_type",
    )
    ordering = ("school", "level", "name")
    autocomplete_fields = ("school", "path", "choice_block")
    list_select_related = ("school", "school__type", "path", "choice_block")
    inlines = (TechniqueRequirementInline, TechniqueExclusionInline, TechniqueChoiceDefinitionInline, ModifierInline)
    fieldsets = (
        (
            "Grunddaten",
            {
                "fields": (
                    "rulebook_position",
                    ("school", "path"),
                    ("name", "level"),
                    "choice_block",
                    "description",
                ),
                "description": "Hier wird festgelegt, wo die Technik im Regelwerk der Schule steht.",
            },
        ),
        (
            "Einordnung und Erwerb",
            {
                "fields": (
                    ("technique_type", "acquisition_type"),
                    "support_level",
                ),
                "description": "Die Begriffe hier ordnen die Technik fuer Regelwerk, Admin und Engine ein.",
            },
        ),
        (
            "Wahlen und Spezialisierungen",
            {
                "fields": (
                    "is_choice_placeholder",
                    "choice_group",
                    "choice_group_notice",
                    "selection_notes",
                    ("choice_target_kind", "choice_limit"),
                    "choice_bonus_value",
                    "specialization_slot_grants",
                ),
                "description": "choice_group dient nur der Anzeige und Organisation. Verbindliche Wahlregeln kommen aus Wahlblock und Wahlentscheidungen.",
            },
        ),
        (
            "Einsatz",
            {
                "fields": (
                    ("action_type", "usage_type"),
                    ("activation_cost", "activation_cost_resource"),
                ),
                "classes": ("collapse",),
                "description": "Nur fuer Techniken mit aktivem Einsatz relevant.",
            },
        ),
        (
            "Zusammenfassung",
            {
                "fields": (
                    "requirement_summary",
                    "exclusion_summary",
                    "choice_definition_summary",
                    "rule_context_preview",
                ),
                "description": "Diese Zusammenfassung hilft beim Gegenlesen gegen das Regelwerk.",
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

    @admin.display(ordering="school__type__name", description="Schultyp")
    def school_type(self, obj):
        """Return the related school type for list display."""
        return obj.school.type

    @admin.display(ordering="level", description="Regelwerk")
    def rulebook_position(self, obj):
        """Render the rulebook position in school -> level -> path order."""
        path_name = obj.path.name if obj.path_id else "Alle Pfade"
        return f"{obj.school.name} -> {obj.level} -> {path_name}"

    @admin.display(boolean=True, description="Wahl?")
    def choice_marker(self, obj):
        """Flag choice rows and editorial choice-group metadata without adding rule logic."""
        return bool(obj.is_choice_placeholder or obj.choice_group)

    @admin.display(description="Hinweis zu choice_group")
    def choice_group_notice(self, obj):
        """Explain that choice_group is metadata only."""
        return _format_choice_group_notice(obj)

    @admin.display(description="Regelkontext")
    def rule_context_preview(self, obj):
        """Render a readable rule-context preview for the technique page."""
        if not obj or not obj.pk:
            return "-"
        return _format_technique_rule_context_html(obj)

    @admin.display(description="Voraussetzungen")
    def requirement_summary(self, obj):
        """Summarize technique requirements for the detail page."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(_format_technique_requirements(obj))

    @admin.display(description="Ausschluesse")
    def exclusion_summary(self, obj):
        """Summarize technique exclusions for the detail page."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(_format_technique_exclusions(obj))

    @admin.display(description="Wahlentscheidungen")
    def choice_definition_summary(self, obj):
        """Summarize technique choice definitions for the detail page."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(_format_technique_choice_definitions(obj))


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Admin configuration for items."""

    list_display = (
        "name",
        "item_type",
        "quality_preview",
        "price",
        "size_class",
        "weight",
        "stackable",
        "is_consumable",
    )
    search_fields = ("name", "description", "item_type")
    list_filter = ("item_type", "default_quality", "stackable", "is_consumable", "size_class")
    ordering = ("item_type", "name")
    inlines = (ArmorStatsInline, ShieldStatsInline, WeaponStatsInline, ItemCharacterInline)

    @admin.display(ordering="default_quality", description="Quality")
    def quality_preview(self, obj):
        """Render default quality with RPG item coloring."""
        return _quality_badge(obj.default_quality)


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
            "Wahlblock",
            {
                "fields": (
                    ("school", "path"),
                    ("name", "sort_order"),
                    "level",
                    ("min_choices", "max_choices"),
                    "description",
                ),
                "description": "Ein Wahlblock beschreibt eine echte Wahlstelle im Regelwerk. Techniken derselben choice_group sind dadurch nicht automatisch exklusiv.",
            },
        ),
        (
            "Uebersicht",
            {
                "fields": ("rulebook_scope_preview", "assigned_techniques"),
                "description": "Hier siehst du, wo der Block im Regelwerk sitzt und welche Techniken dazugehoeren.",
            },
        ),
    )

    @admin.display(ordering="school__type__name", description="Schultyp")
    def school_type(self, obj):
        """Return the linked school type for list display."""
        return obj.school.type

    @admin.display(ordering="level", description="Stufe / Pfad")
    def rulebook_scope(self, obj):
        """Render the choice-block position in rulebook terms for list views."""
        level = f"Stufe {obj.level}" if obj.level is not None else "ohne feste Stufe"
        path = obj.path.name if obj.path_id else "alle Pfade"
        return f"{level} | {path}"

    @admin.display(description="Regelwerk-Position")
    def rulebook_scope_preview(self, obj):
        """Render the full rulebook scope on the detail page."""
        if not obj or not getattr(obj, "school_id", None):
            return "-"
        return f"{obj.school.name} -> {self.rulebook_scope(obj)}"

    @admin.display(description="Zugeordnete Techniken")
    def assigned_techniques(self, obj):
        """Show all techniques assigned to this choice block."""
        if not obj or not obj.pk:
            return "-"
        return ", ".join(obj.techniques.order_by("level", "name").values_list("name", flat=True)) or "Noch keine"

    @admin.display(ordering="name", description="Techniken")
    def technique_count(self, obj):
        """Return how many techniques currently belong to the block."""
        return obj.techniques.count()


@admin.register(TechniqueChoiceDefinition)
class TechniqueChoiceDefinitionAdmin(admin.ModelAdmin):
    """Admin configuration for persistent technique choice definitions."""

    list_display = ("name", "technique", "technique_school", "target_kind", "min_choices", "max_choices", "is_required", "is_active")
    search_fields = ("name", "description", "technique__name", "technique__school__name")
    list_filter = ("technique__school__type", "technique__school", "target_kind", "is_required", "is_active")
    ordering = ("technique__school", "technique__level", "technique__name", "sort_order", "name")
    autocomplete_fields = ("technique",)
    list_select_related = ("technique", "technique__school", "technique__school__type")

    @admin.display(ordering="technique__school__name", description="School")
    def technique_school(self, obj):
        """Return the owning technique school for list display."""
        return obj.technique.school


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    """Admin configuration for school-bound specializations."""

    list_display = ("name", "school", "school_type", "slug", "support_level", "is_active", "sort_order")
    search_fields = ("name", "slug", "school__name")
    list_filter = ("school", "support_level", "is_active")
    ordering = ("school", "sort_order", "name")
    autocomplete_fields = ("school",)
    list_select_related = ("school", "school__type")
    fieldsets = (
        (
            "Spezialisierung",
            {
                "fields": (
                    ("school", "sort_order"),
                    ("name", "slug"),
                    "support_level",
                    "is_active",
                    "description",
                ),
                "description": "Spezialisierungen sind eigene Schulentscheidungen. Sie werden getrennt von Techniken gepflegt.",
            },
        ),
    )

    @admin.display(ordering="school__type__name", description="Schultyp")
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
        return obj.technique.get_support_level_display()


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
            "Technik",
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
            "Gewaehltes Ziel",
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
                    | ~Q(choice_target_kind=Technique.ChoiceTargetKind.NONE)
                )
                .select_related("school", "path")
                .distinct()
                .order_by("school__name", "level", "name")
            )
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
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

    list_display = (
        "item",
        "item_quality",
        "base_damage",
        "quality_damage",
        "two_handed_damage",
        "wield_mode",
        "damage_source",
        "min_st",
        "size_class",
    )
    search_fields = ("item__name", "damage_source__name")
    list_filter = ("wield_mode", "damage_source", "item__default_quality", "item__size_class")
    ordering = ("item__name",)
    autocomplete_fields = ("item", "damage_source")
    list_select_related = ("item", "damage_source")

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


ATTRIBUTE_CHOICE_HELP = {
    "short_name": "Pick the canonical attribute code used by the rules and sheet.",
}

SKILL_CATEGORY_CHOICE_HELP = {
    "slug": "Pick the fixed category key. The German labels are the actual category buckets used in the game.",
}

SIZE_CLASS_HELP = {
    "size_class": "Size class scale: S/F/W/K are smaller than average, M is average human size, G/R/Gi/Kol are progressively larger.",
}

CHARACTER_CHOICE_HELP = {
    "gender": "Display value only. Use the option that should appear on the character sheet.",
}

SCHOOL_TYPE_CHOICE_HELP = {
    "slug": "Magic = arkane Schulen, Divine = goettliche Schulen, Combat = Kampfschulen.",
}

PROGRESSION_RULE_CHOICE_HELP = {
    "grant_kind": "Technique Choice = grants selectable techniques, Spell Choice = grants selectable spells, Aspect Access = unlocks an aspect, Aspect Spell = grants a spell from an aspect.",
}

MODIFIER_CHOICE_HELP = {
    "target_kind": "Skill = eine genaue Fertigkeit, Skill Category = eine ganze Fertigkeitskategorie, Stat = ein abgeleiteter Wert, Item/Item Category = Gegenstand oder Gegenstandskategorie, Specialization = schulgebundene Spezialisierung, Other Entity = beliebige andere Spielentitaet.",
    "mode": "Flat = fixed value, Scaled = value is calculated from another source.",
    "scale_source": "School level = scales with a school level, Fame total = scales with total fame rank, Trait level = scales with the source trait level.",
    "round_mode": "Floor = round down after division, Ceil = round up after division.",
    "cap_mode": "None = no cap, Min = do not go below the cap value, Max = do not go above the cap value.",
    "cap_source": "Uses the same source types as scaling, but only to define the cap value.",
    "target_slug": "Fuer Stats und Kategorien wird hier der Regelschluessel eingetragen. Bei Skill/Category kann alternativ das jeweilige Objektfeld genutzt werden.",
}

TECHNIQUE_CHOICE_HELP = {
    "technique_type": "Passive = dauerhafter Effekt, Active = aktiv eingesetzte Technik, Situational = nur in bestimmten Situationen relevant.",
    "acquisition_type": "Automatic = wird direkt gelernt, Choice = wird aus mehreren Optionen ausgewaehlt.",
    "support_level": "Automated = die Engine berechnet die Regel vollstaendig, Partially Automated = Teile sind strukturiert und auswertbar, Manual (Rule Text Only) = nur Regeltext, keine automatische Berechnung.",
    "choice_target_kind": "Einfachmodus fuer eine einzelne dauerhafte Wahl. Fuer mehrere getrennte Entscheidungen bitte die Inline-Wahlentscheidungen nutzen.",
    "choice_group": "Reine UI-/Importmetadaten. Diese Gruppe erzeugt keine Regelmechanik.",
    "specialization_slot_grants": "So viele Spezialisierungs-Slots entstehen, sobald die Technik wirklich gelernt wurde. Nur verfuegbare Techniken zaehlen nicht.",
    "action_type": "Action = normale Aktion, Reaction = Reaktion, Free = freie Handlung, Preparation = Vorbereitung.",
    "usage_type": "At Will = beliebig oft, Per Scene = einmal pro Szene, Per Combat = einmal pro Kampf, Per Day = einmal pro Tag.",
    "choice_block": "Optionaler Wahlblock, wenn die Technik zu einer echten Wahlstelle des Regelwerks gehoert.",
    "selection_notes": "Kurzer Klartext-Hinweis, was bei dieser Technik konkret gewaehlt oder beachtet werden muss.",
}

TECHNIQUE_CHOICE_BLOCK_HELP = {
    "name": "Kurzer Name des Wahlblocks, damit die Regelstelle im Admin wiedergefunden wird.",
    "min_choices": "Wie viele Techniken aus diesem Block mindestens gelernt werden muessen.",
    "max_choices": "Wie viele Techniken aus diesem Block hoechstens gelernt werden duerfen.",
}

TECHNIQUE_CHOICE_DEFINITION_HELP = {
    "target_kind": "Definiert, welches Ziel diese Technikentscheidung dauerhaft speichert.",
    "min_choices": "Wie viele Auswahlen fuer diese eine Entscheidung mindestens gespeichert werden muessen.",
    "max_choices": "Wie viele Auswahlen fuer diese eine Entscheidung maximal gespeichert werden duerfen.",
}

SPECIALIZATION_CHOICE_HELP = {
    "support_level": "Automated = die Engine berechnet die Regel vollstaendig, Partially Automated = Teile sind strukturiert und auswertbar, Manual (Rule Text Only) = nur Regeltext, keine automatische Berechnung.",
}

SCHOOL_ADMIN_LABELS = {
    "type": "Schultyp",
    "description": "Beschreibung",
}

TECHNIQUE_LABELS = {
    "school": "Schule",
    "path": "Pfad",
    "level": "Stufe",
    "choice_block": "Wahlblock",
    "technique_type": "Technikart",
    "acquisition_type": "Erwerbsart",
    "support_level": "Regelunterstuetzung",
    "is_choice_placeholder": "Platzhalter fuer Wahl",
    "choice_group": "Organisationsgruppe",
    "selection_notes": "Hinweistext",
    "choice_target_kind": "Ziel der Wahl",
    "choice_limit": "Anzahl Wahlen",
    "choice_bonus_value": "Fester Bonus",
    "specialization_slot_grants": "Spezialisierungs-Slots",
    "action_type": "Aktionsart",
    "usage_type": "Nutzungsart",
    "activation_cost": "Kosten",
    "activation_cost_resource": "Kostenart",
    "description": "Regeltext / Beschreibung",
}

TECHNIQUE_CHOICE_BLOCK_LABELS = {
    "school": "Schule",
    "path": "Pfad",
    "level": "Stufe",
    "name": "Bezeichnung",
    "sort_order": "Sortierung",
    "min_choices": "Min. Wahlen",
    "max_choices": "Max. Wahlen",
    "description": "Regeltext / Beschreibung",
}

SPECIALIZATION_LABELS = {
    "school": "Schule",
    "name": "Name",
    "slug": "Schluessel",
    "support_level": "Regelunterstuetzung",
    "sort_order": "Sortierung",
    "is_active": "Aktiv",
    "description": "Regeltext / Beschreibung",
}

ITEM_CHOICE_HELP = {
    "item_type": "Armor = Ruestung, Shield = Schild, Weapon = Waffe, Consumable = verbrauchbares Item, Misc = sonstige Gegenstaende.",
    "default_quality": "Standardqualitaet des Items; wird verwendet, wenn keine inventarspezifische Qualitaet gesetzt wurde.",
}

WEAPON_CHOICE_HELP = {
    "size_class": "Use the same size-class scale as races and bodies: smaller codes are lighter/smaller, larger codes are heavier/larger.",
}

SHIELD_CHOICE_HELP = {
    "encumbrance": "Belastung (Bel.) des Schilds.",
    "min_st": "Mindeststaerke zum Fuehren des Schilds.",
}

TRAIT_CHOICE_HELP = {
    "trait_type": "Advantage = beneficial trait, Disadvantage = drawback or penalty trait.",
}

_install_inline_help(ModifierInline, help_texts=MODIFIER_CHOICE_HELP)
_install_inline_help(ProgressionRuleInline, help_texts=PROGRESSION_RULE_CHOICE_HELP)
_install_inline_help(TechniqueInline, help_texts=TECHNIQUE_CHOICE_HELP, labels=TECHNIQUE_LABELS)
_install_inline_help(
    TechniqueChoiceBlockInline,
    help_texts=TECHNIQUE_CHOICE_BLOCK_HELP,
    labels=TECHNIQUE_CHOICE_BLOCK_LABELS,
)
_install_inline_help(TechniqueChoiceDefinitionInline, help_texts=TECHNIQUE_CHOICE_DEFINITION_HELP)
_install_inline_help(SpecializationInline, help_texts=SPECIALIZATION_CHOICE_HELP, labels=SPECIALIZATION_LABELS)
_install_inline_help(WeaponStatsInline, help_texts=WEAPON_CHOICE_HELP)
_install_inline_help(ShieldStatsInline, help_texts=SHIELD_CHOICE_HELP)

_install_admin_help(AttributeAdmin, help_texts=ATTRIBUTE_CHOICE_HELP)
_install_admin_help(SkillCategoryAdmin, help_texts=SKILL_CATEGORY_CHOICE_HELP)
_install_admin_help(RaceAdmin, help_texts=SIZE_CLASS_HELP)
_install_admin_help(CharacterAdmin, help_texts=CHARACTER_CHOICE_HELP)
_install_admin_help(SchoolTypeAdmin, help_texts=SCHOOL_TYPE_CHOICE_HELP)
_install_admin_help(ProgressionRuleAdmin, help_texts=PROGRESSION_RULE_CHOICE_HELP)
_install_admin_help(ModifierAdmin, help_texts=MODIFIER_CHOICE_HELP)
_install_admin_help(SchoolAdmin, labels=SCHOOL_ADMIN_LABELS)
_install_admin_help(TechniqueAdmin, help_texts=TECHNIQUE_CHOICE_HELP, labels=TECHNIQUE_LABELS)
_install_admin_help(
    TechniqueChoiceBlockAdmin,
    help_texts=TECHNIQUE_CHOICE_BLOCK_HELP,
    labels=TECHNIQUE_CHOICE_BLOCK_LABELS,
)
_install_admin_help(TechniqueChoiceDefinitionAdmin, help_texts=TECHNIQUE_CHOICE_DEFINITION_HELP)
_install_admin_help(SpecializationAdmin, help_texts=SPECIALIZATION_CHOICE_HELP, labels=SPECIALIZATION_LABELS)
_install_admin_help(ItemAdmin, help_texts=ITEM_CHOICE_HELP)
_install_admin_help(WeaponStatsAdmin, help_texts=WEAPON_CHOICE_HELP)
_install_admin_help(ShieldStatsAdmin, help_texts=SHIELD_CHOICE_HELP)
_install_admin_help(TraitAdmin, help_texts=TRAIT_CHOICE_HELP)
