"""Rule calculation helpers for character model instances."""

from __future__ import annotations

from collections import defaultdict
import math
from functools import cached_property
from typing import DefaultDict, TypeAlias, TypedDict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model, Prefetch, Q

from . import character_combat, character_equipment, character_learning, character_progression
from .item_engine import ItemEngine
from charsheet.modifiers import ModifierEngine, ModifierResolutionMode, TargetDomain
from charsheet.models import (
    Character,
    CharacterItem,
    CharacterLanguage,
    CharacterRaceChoice,
    CharacterSchool,
    CharacterSchoolPath,
    CharacterSpecialization,
    CharacterWeaponMastery,
    CharacterWeaponMasteryArcana,
    CharacterTechniqueChoice,
    CharacterTraitChoice,
    Item,
    Modifier,
    ProgressionRule,
    Race,
    RaceChoiceDefinition,
    RaceTechnique,
    School,
    SchoolPath,
    Specialization,
    Technique,
    TechniqueChoiceBlock,
    TechniqueChoiceDefinition,
    TechniqueExclusion,
    TechniqueRequirement,
    Trait,
)


ModifierTargetKey: TypeAlias = tuple[str, str]
ModifierSourceKey: TypeAlias = tuple[int, int]


class SkillInfo(TypedDict):
    """Serialized base skill metadata used during calculations."""

    skill_id: int
    level: int
    category: str
    attribute: str


class SkillBreakdown(TypedDict):
    """Structured result for one resolved skill calculation."""

    skill_slug: str
    level: int
    base_attribute: str
    attribute_value: int
    attribute_modifier: int
    base: int
    modifiers: int
    total: int


class SkillError(TypedDict):
    """Fallback payload when a requested skill cannot be resolved."""

    skill_slug: str
    error: str


class ActiveProgressionRule(TypedDict):
    """A progression rule paired with the concrete school that activates it."""

    school_id: int
    school_name: str
    school_level: int
    rule: ProgressionRule


class TechniqueChoiceBlockState(TypedDict):
    """Resolved status data for one generic technique choice block."""

    block_id: int
    block_name: str | None
    block_description: str | None
    school_id: int
    school_name: str
    school_level: int
    level: int | None
    path_id: int | None
    path_name: str | None
    selected_path_id: int | None
    selected_path_name: str | None
    min_choices: int
    max_choices: int
    learned_choice_count: int
    available_choice_count: int
    remaining_required_choices: int
    remaining_optional_choices: int
    active: bool
    open: bool
    fulfilled: bool
    violated: bool
    technique_ids: list[int]
    learned_technique_ids: list[int]
    available_technique_ids: list[int]


class TechniqueActivationData(TypedDict):
    """Prepared activation metadata for active or situational techniques."""

    action_type: str | None
    usage_type: str | None
    activation_cost: int | None
    activation_cost_resource: str | None


class TechniqueState(TypedDict):
    """Resolved availability, learning, and activation state of one technique."""

    technique_id: int
    technique_name: str
    school_id: int
    school_name: str
    school_known: bool
    school_level: int
    required_level: int
    required_level_met: bool
    path_id: int | None
    path_name: str | None
    choice_block_id: int | None
    choice_block_name: str | None
    choice_block_description: str | None
    selected_path_id: int | None
    selected_path_name: str | None
    choice_target_kind: str
    choice_limit: int
    choice_count: int
    choices_complete: bool
    path_allowed: bool
    requirements_met: bool
    available: bool
    explicitly_learned: bool
    learned: bool
    acquisition_type: str
    technique_type: str
    support_level: str
    specialization_slot_grants: int
    engine_resolves_effects: bool
    is_choice_placeholder: bool
    choice_group: str | None
    selection_notes: str | None
    passive_active: bool
    activation: TechniqueActivationData | None


class CharacterEngine:
    """Calculate derived character values from persisted model data."""

    def __init__(self, character: Character, *, modifier_resolution_mode: str | None = None) -> None:
        self.character = character
        self.modifier_resolution_mode = ModifierResolutionMode.normalize(modifier_resolution_mode)
        self._technique_learned_cache: dict[int, bool] = {}
        self._technique_available_cache: dict[int, bool] = {}
        self._technique_requirement_cache: dict[int, bool] = {}
        self._technique_exclusion_cache: dict[int, bool] = {}

    @cached_property
    def _attributes_map(self) -> dict[str, int]:
        """Cache character attributes by short name."""
        qs = self.character.characterattribute_set.select_related("attribute")
        return {entry.attribute.short_name: entry.base_value for entry in qs}

    @cached_property
    def _skills_map(self) -> dict[str, SkillInfo]:
        """Cache learned skills with their category and governing attribute."""
        qs = self.character.characterskill_set.select_related(
            "skill",
            "skill__category",
            "skill__attribute",
        )
        return {
            entry.skill.slug: {
                "skill_id": entry.skill_id,
                "level": entry.level,
                "category": entry.skill.category.slug,
                "attribute": entry.skill.attribute.short_name,
            }
            for entry in qs
        }

    @cached_property
    def _languages_map(self) -> dict[str, CharacterLanguage]:
        """Cache learned languages keyed by language slug."""
        qs = self.character.characterlanguage_set.select_related("language")
        return {entry.language.slug: entry for entry in qs}

    @cached_property
    def _school_entries(self) -> dict[int, CharacterSchool]:
        """Cache learned schools keyed by school id."""
        qs = self.character.schools.select_related("school", "school__type")
        return {entry.school_id: entry for entry in qs}

    @cached_property
    def _selected_paths(self) -> dict[int, CharacterSchoolPath]:
        """Cache selected school paths keyed by school id."""
        qs = self.character.selected_school_paths.select_related("school", "path")
        return {entry.school_id: entry for entry in qs}

    @cached_property
    def _weapon_master_school(self) -> School | None:
        """Return the Waffenmeister school definition when it exists."""
        school = School.objects.filter(name__iexact="Waffenmeister").select_related("type").first()
        return school

    @cached_property
    def _weapon_master_school_entry(self) -> CharacterSchool | None:
        """Return the character's learned Waffenmeister school entry, if any."""
        school = self._weapon_master_school
        if school is None:
            return None
        return self._school_entries.get(school.id)

    @cached_property
    def _weapon_mastery_entries_by_item_id(self) -> dict[int, CharacterWeaponMastery]:
        """Cache concrete weapon masteries keyed by weapon item id."""
        school = self._weapon_master_school
        if school is None:
            return {}
        queryset = (
            self.character.weapon_masteries.filter(school=school)
            .select_related("weapon_item", "school")
            .order_by("pick_order", "weapon_item__name", "id")
        )
        return {entry.weapon_item_id: entry for entry in queryset}

    @cached_property
    def _weapon_mastery_arcana_entries(self) -> list[CharacterWeaponMasteryArcana]:
        """Cache all persisted rune/bonus-capacity arcana purchases."""
        school = self._weapon_master_school
        if school is None:
            return []
        return list(
            self.character.weapon_mastery_arcana_entries.filter(school=school)
            .select_related("rune", "school")
            .order_by("id")
        )

    @cached_property
    def _specialization_entries_by_school_id(self) -> dict[int, list[CharacterSpecialization]]:
        """Cache learned character specializations keyed by school id."""
        grouped: DefaultDict[int, list[CharacterSpecialization]] = defaultdict(list)
        queryset = (
            self.character.learned_specializations.select_related(
                "specialization",
                "specialization__school",
                "source_technique",
            )
            .order_by(
                "specialization__school__name",
                "specialization__sort_order",
                "specialization__name",
                "id",
            )
        )
        for entry in queryset:
            grouped[entry.specialization.school_id].append(entry)
        return dict(grouped)

    @cached_property
    def _learned_specialization_ids_by_school_id(self) -> dict[int, set[int]]:
        """Cache learned specialization ids per school for fast exclusion checks."""
        return {
            school_id: {entry.specialization_id for entry in entries}
            for school_id, entries in self._specialization_entries_by_school_id.items()
        }

    @cached_property
    def _specialization_definitions_by_school_id(self) -> dict[int, list[Specialization]]:
        """Cache specialization definitions of learned schools keyed by school id."""
        school_ids = list(self._school_entries.keys())
        if not school_ids:
            return {}

        grouped: DefaultDict[int, list[Specialization]] = defaultdict(list)
        queryset = (
            Specialization.objects.filter(school_id__in=school_ids)
            .select_related("school")
            .order_by("school__name", "sort_order", "name")
        )
        for specialization in queryset:
            grouped[specialization.school_id].append(specialization)
        return dict(grouped)

    @cached_property
    def _manual_learned_technique_ids(self) -> set[int]:
        """Cache explicitly learned technique ids."""
        return set(
            self.character.learned_techniques.values_list("technique_id", flat=True)
        )

    @cached_property
    def _technique_choices_by_technique_id(self) -> dict[int, list[CharacterTechniqueChoice]]:
        """Cache persisted technique choices grouped by technique id."""
        grouped: DefaultDict[int, list[CharacterTechniqueChoice]] = defaultdict(list)
        queryset = (
            self.character.technique_choices.select_related(
                "technique",
                "definition",
                "selected_skill",
                "selected_skill_category",
                "selected_item",
                "selected_specialization",
                "selected_content_type",
            )
            .order_by("technique__school__name", "technique__level", "technique__name", "id")
        )
        for choice in queryset:
            grouped[choice.technique_id].append(choice)
        return dict(grouped)

    @cached_property
    def _technique_choices_by_definition_id(self) -> dict[int, list[CharacterTechniqueChoice]]:
        """Cache persisted technique choices grouped by explicit choice definition id."""
        grouped: DefaultDict[int, list[CharacterTechniqueChoice]] = defaultdict(list)
        for choices in self._technique_choices_by_technique_id.values():
            for choice in choices:
                if choice.definition_id is not None:
                    grouped[choice.definition_id].append(choice)
        return dict(grouped)

    @cached_property
    def _race_choices_by_definition_id(self) -> dict[int, list[CharacterRaceChoice]]:
        """Cache persisted race choices grouped by explicit race choice definition id."""
        grouped: DefaultDict[int, list[CharacterRaceChoice]] = defaultdict(list)
        queryset = (
            self.character.race_choices.select_related(
                "definition",
                "definition__race",
                "selected_skill",
                "selected_skill_category",
                "selected_item",
                "selected_specialization",
                "selected_content_type",
            )
            .order_by("definition__race__name", "definition__sort_order", "definition__name", "id")
        )
        for choice in queryset:
            grouped[choice.definition_id].append(choice)
        return dict(grouped)

    @cached_property
    def _trait_choices_by_definition_id(self) -> dict[int, list[CharacterTraitChoice]]:
        """Cache persisted trait choices grouped by explicit trait choice definition id."""
        grouped: DefaultDict[int, list[CharacterTraitChoice]] = defaultdict(list)
        queryset = (
            CharacterTraitChoice.objects.filter(character_trait__owner=self.character)
            .select_related(
                "character_trait",
                "character_trait__owner",
                "character_trait__trait",
                "definition",
                "selected_attribute",
                "selected_skill",
                "selected_skill_category",
                "selected_item",
                "selected_specialization",
                "selected_content_type",
            )
            .order_by("character_trait__trait__name", "definition__sort_order", "id")
        )
        for choice in queryset:
            grouped[choice.definition_id].append(choice)
        return dict(grouped)

    @cached_property
    def _choice_bonus_techniques(self) -> list[Technique]:
        """Cache computed passive techniques with explicit choice bonuses; choice_group is ignored here."""
        return [
            technique
            for technique in self._character_school_technique_list
            if technique.choice_bonus_value
            and technique.choice_target_kind != Technique.ChoiceTargetKind.NONE
        ]

    @cached_property
    def _choice_skill_bonus_by_skill_id(self) -> dict[int, int]:
        """Index fixed choice-based bonuses by selected skill id."""
        totals: DefaultDict[int, int] = defaultdict(int)
        for technique in self._choice_bonus_techniques:
            state = self._technique_state_map.get(technique.id)
            if state is None or not (
                state["learned"]
                and state["available"]
                and state["engine_resolves_effects"]
            ):
                continue
            if technique.choice_target_kind != Technique.ChoiceTargetKind.SKILL:
                continue
            for choice in self.technique_choices(technique):
                if choice.selected_skill_id is not None:
                    totals[choice.selected_skill_id] += technique.choice_bonus_value
        return dict(totals)

    @cached_property
    def _skill_levels_by_id(self) -> dict[int, int]:
        """Cache learned skill levels keyed by skill id for requirement checks."""
        return {
            entry.skill_id: entry.level
            for entry in self.character.characterskill_set.only("skill_id", "level")
        }

    @cached_property
    def _trait_levels(self) -> dict[int, int]:
        """Cache learned trait levels keyed by trait id."""
        return {
            entry.trait_id: entry.trait_level
            for entry in self.character.charactertrait_set.select_related("trait")
        }

    @cached_property
    def _trait_levels_by_slug(self) -> dict[str, int]:
        """Cache learned trait levels keyed by trait slug for semantic scaling."""
        return {
            entry.trait.slug: entry.trait_level
            for entry in self.character.charactertrait_set.select_related("trait")
        }

    @cached_property
    def _all_modifiers(self) -> list[Modifier]:
        """Load only modifiers whose sources are relevant for this character."""
        source_ids_by_model: dict[type[Model], set[int]] = {
            Race: {self.character.race_id},
            School: set(self._school_entries.keys()),
            Trait: set(self._trait_levels.keys()),
            Technique: set(self._computed_technique_ids),
            Item: set(
                CharacterItem.objects.filter(
                    owner=self.character,
                    equipped=True,
                )
                .filter(
                    Q(item__is_magic=True) | Q(item__item_type=Item.ItemType.MAGIC_ITEM)
                ).values_list("item_id", flat=True)
            ),
            CharacterItem: set(
                CharacterItem.objects.filter(
                    owner=self.character,
                    equipped=True,
                    is_magic=True,
                ).values_list("id", flat=True)
            ),
        }
        source_ids_by_model = {
            model_class: source_ids
            for model_class, source_ids in source_ids_by_model.items()
            if source_ids
        }
        if not source_ids_by_model:
            return []

        content_types = ContentType.objects.get_for_models(
            *source_ids_by_model.keys(),
            for_concrete_models=False,
        )
        source_filter = Q()
        for model_class, source_ids in source_ids_by_model.items():
            source_filter |= Q(
                source_content_type=content_types[model_class],
                source_object_id__in=source_ids,
            )

        return list(
            Modifier.objects.filter(source_filter)
            .select_related(
                "scale_school",
                "scale_skill",
                "source_content_type",
                "target_skill",
                "target_skill_category",
                "target_item",
                "target_specialization",
                "target_choice_definition",
                "target_race_choice_definition",
                "target_content_type",
            )
        )

    @cached_property
    def _modifiers_by_target(self) -> dict[ModifierTargetKey, list[Modifier]]:
        """Group modifiers by canonical target identifiers for O(1) resolver access."""
        grouped: DefaultDict[ModifierTargetKey, list[Modifier]] = defaultdict(list)
        for modifier in self._all_modifiers:
            grouped[(modifier.target_kind, modifier.target_identifier())].append(modifier)
        return dict(grouped)

    @cached_property
    def _modifier_sources(self) -> dict[ModifierSourceKey, Model]:
        """Preload GenericForeignKey sources used by modifiers to avoid N+1 lookups."""
        source_ids_by_ct: DefaultDict[int, set[int]] = defaultdict(set)
        content_types: dict[int, object] = {}
        for modifier in self._all_modifiers:
            source_ids_by_ct[modifier.source_content_type_id].add(modifier.source_object_id)
            content_types[modifier.source_content_type_id] = modifier.source_content_type

        loaded_sources: dict[ModifierSourceKey, Model] = {}
        for content_type_id, object_ids in source_ids_by_ct.items():
            content_type = content_types[content_type_id]
            model_class = content_type.model_class()
            if model_class is None:
                continue

            queryset = model_class._default_manager.filter(pk__in=object_ids)
            if model_class is Technique:
                queryset = queryset.select_related("school", "path")
            elif model_class is School:
                queryset = queryset.select_related("type")

            for source in queryset:
                loaded_sources[(content_type_id, source.pk)] = source
        return loaded_sources

    @cached_property
    def _character_school_technique_list(self) -> list[Technique]:
        """Load all techniques of learned schools with required relations eagerly loaded."""
        school_ids = list(self._school_entries.keys())
        if not school_ids:
            return []

        requirement_queryset = TechniqueRequirement.objects.select_related(
            "required_technique__school",
            "required_technique__path",
            "required_path",
            "required_skill",
            "required_trait",
        )
        exclusions_queryset = TechniqueExclusion.objects.select_related(
            "excluded_technique__school",
            "excluded_technique__path",
        )
        excluded_by_queryset = TechniqueExclusion.objects.select_related(
            "technique__school",
            "technique__path",
        )
        choice_definition_queryset = TechniqueChoiceDefinition.objects.order_by("sort_order", "name", "id")

        return list(
            Technique.objects.filter(school_id__in=school_ids)
            .select_related("school", "path", "choice_block", "choice_block__path")
            .prefetch_related(
                Prefetch("requirements", queryset=requirement_queryset),
                Prefetch("exclusions", queryset=exclusions_queryset),
                Prefetch("excluded_by", queryset=excluded_by_queryset),
                Prefetch("choice_definitions", queryset=choice_definition_queryset),
            )
            .order_by("school__name", "level", "name")
        )

    @cached_property
    def _computed_technique_ids(self) -> set[int]:
        """Cache technique ids whose effects may be resolved automatically."""
        return {
            technique.id
            for technique in (
                list(self._character_school_technique_list)
                + list(self._race_technique_list)
            )
            if self._technique_effect_is_computed(technique)
        }

    @cached_property
    def _race_technique_list(self) -> list[Technique]:
        """Load all techniques granted directly by the character's race."""
        return [
            relation.technique
            for relation in (
                RaceTechnique.objects
                .filter(race_id=self.character.race_id)
                .select_related("technique")
                .order_by("technique__name")
            )
        ]

    @cached_property
    def _race_technique_ids(self) -> set[int]:
        """Cache technique ids that come from the character's race."""
        return {technique.id for technique in self._race_technique_list}

    @cached_property
    def _techniques_by_id(self) -> dict[int, Technique]:
        """Index preloaded school techniques by id for fast reuse."""
        return {technique.id: technique for technique in self._character_school_technique_list}

    @cached_property
    def _technique_states_cache(self) -> list[TechniqueState]:
        """Build technique states once per engine instance and reuse them everywhere."""
        return [self._build_technique_state(technique) for technique in self._character_school_technique_list]

    @cached_property
    def _technique_state_map(self) -> dict[int, TechniqueState]:
        """Index cached technique states by technique id."""
        return {state["technique_id"]: state for state in self._technique_states_cache}

    @cached_property
    def _technique_choice_blocks_by_id(self) -> dict[int, TechniqueChoiceBlock]:
        """Load choice blocks of learned schools keyed by block id."""
        school_ids = list(self._school_entries.keys())
        if not school_ids:
            return {}
        return {
            block.id: block
            for block in TechniqueChoiceBlock.objects.filter(school_id__in=school_ids)
            .select_related("school", "path")
            .order_by("school__name", "level", "sort_order", "name", "id")
        }

    @cached_property
    def _techniques_by_choice_block_id(self) -> dict[int, list[Technique]]:
        """Group learned-school techniques by explicit choice block."""
        grouped: DefaultDict[int, list[Technique]] = defaultdict(list)
        for technique in self._character_school_technique_list:
            if technique.choice_block_id is not None:
                grouped[technique.choice_block_id].append(technique)
        return dict(grouped)

    @cached_property
    def _choice_block_states_cache(self) -> list[TechniqueChoiceBlockState]:
        """Build rule states for all choice blocks of learned schools."""
        return [self._build_choice_block_state(block) for block in self._technique_choice_blocks_by_id.values()]

    @cached_property
    def _specialization_slot_counts_by_school_id(self) -> dict[int, int]:
        """Cache granted specialization slots per school from explicit CharacterTechnique rows."""
        totals: DefaultDict[int, int] = defaultdict(int)
        queryset = (
            self.character.learned_techniques.select_related("technique", "technique__school")
            .order_by("technique__school__name", "technique__level", "technique__name", "id")
        )
        for learned_technique in queryset:
            if learned_technique.technique.specialization_slot_grants <= 0:
                continue
            totals[learned_technique.technique.school_id] += learned_technique.technique.specialization_slot_grants
        return dict(totals)

    @cached_property
    def _progression_rules_by_type(self) -> dict[int, list[ProgressionRule]]:
        """Group relevant progression rules by school type for reuse."""
        school_type_ids = {entry.school.type_id for entry in self._school_entries.values()}
        if not school_type_ids:
            return {}

        grouped: DefaultDict[int, list[ProgressionRule]] = defaultdict(list)
        rules = (
            ProgressionRule.objects.filter(school_type_id__in=school_type_ids)
            .select_related("school_type")
            .order_by("school_type_id", "min_level", "grant_kind", "id")
        )
        for rule in rules:
            grouped[rule.school_type_id].append(rule)
        return dict(grouped)

    def attributes(self) -> dict[str, int]:
        """Return the character's base attributes."""
        return dict(self._attributes_map)

    def skills(self) -> dict[str, SkillInfo]:
        """Return the character's learned skills and their metadata."""
        return dict(self._skills_map)

    # Grouped domain methods live in sibling modules to keep this class readable.
    school_level = character_progression.school_level
    selected_school_path = character_progression.selected_school_path
    specialization_slot_count = character_progression.specialization_slot_count
    character_specializations = character_progression.character_specializations
    open_specialization_slot_count = character_progression.open_specialization_slot_count
    available_specializations = character_progression.available_specializations
    technique_choice_blocks = character_progression.technique_choice_blocks
    active_technique_choice_blocks = character_progression.active_technique_choice_blocks
    open_technique_choice_blocks = character_progression.open_technique_choice_blocks
    fulfilled_technique_choice_blocks = character_progression.fulfilled_technique_choice_blocks
    violated_technique_choice_blocks = character_progression.violated_technique_choice_blocks
    _build_choice_block_state = character_progression.build_choice_block_state
    active_progression_rules = character_progression.active_progression_rules
    build_trait_validator = character_learning.build_trait_validator
    trait_rank_cost = character_learning.trait_rank_cost
    validate_trait_target_level = character_learning.validate_trait_target_level
    trait_learning_delta_cost = character_learning.trait_learning_delta_cost
    validate_trait_selection = character_learning.validate_trait_selection
    validate_cross_type_trait_selection = character_learning.validate_cross_type_trait_selection

    fame_total = character_combat.fame_total
    calculate_initiative = character_combat.calculate_initiative
    calculate_arcane_power = character_combat.calculate_arcane_power
    calculate_potential = character_combat.calculate_potential
    wound_thresholds = character_combat.wound_thresholds
    calculate_defense = character_combat.calculate_defense
    vw = character_combat.vw
    gw = character_combat.gw
    sr = character_combat.sr
    current_wound_stage = character_combat.current_wound_stage
    current_wound_penalty = character_combat.current_wound_penalty
    current_wound_penalty_raw = character_combat.current_wound_penalty_raw
    is_wound_penalty_ignored = character_combat.is_wound_penalty_ignored

    equipped_weapon_items = character_equipment.equipped_weapon_items
    equipped_armor_items = character_equipment.equipped_armor_items
    equipped_clothing_items = character_equipment.equipped_clothing_items
    equipped_magic_item_items = character_equipment.equipped_magic_item_items
    equipped_shield_items = character_equipment.equipped_shield_items
    weapon_quality_skill_modifier = character_equipment.weapon_quality_skill_modifier
    equipped_weapon_rows = character_equipment.equipped_weapon_rows
    equipped_armor_rows = character_equipment.equipped_armor_rows
    equipped_clothing_rows = character_equipment.equipped_clothing_rows
    equipped_magic_item_rows = character_equipment.equipped_magic_item_rows
    equipped_shield_rows = character_equipment.equipped_shield_rows
    get_grs = character_equipment.get_grs
    get_bel = character_equipment.get_bel
    load_penalty = character_equipment.load_penalty
    get_ms = character_equipment.get_ms
    get_dmg_modifier_sum = character_equipment.get_dmg_modifier_sum
    km_to_coins = character_equipment.km_to_coins

    def has_technique_learned(self, technique: Technique | int) -> bool:
        """Return whether a technique counts as learned for the character."""
        return self._has_technique_learned(
            self._coerce_technique(technique),
            set(),
            set(),
        )

    def are_technique_requirements_met(self, technique: Technique | int) -> bool:
        """Return whether all structured requirements of a technique are met."""
        return self._requirements_met(
            self._coerce_technique(technique),
            set(),
            set(),
        )

    def is_technique_available(self, technique: Technique | int) -> bool:
        """Return whether a technique is currently available to the character."""
        return self._is_technique_available(
            self._coerce_technique(technique),
            set(),
            set(),
        )

    def technique_state(self, technique: Technique | int) -> TechniqueState:
        """Build the full resolved state for a single technique."""
        technique_obj = self._coerce_technique(technique)
        return self._technique_state_map.get(technique_obj.id) or self._build_technique_state(technique_obj)

    def technique_states(self) -> list[TechniqueState]:
        """Return resolved state data for all techniques of learned schools."""
        return list(self._technique_states_cache)

    def available_techniques(self) -> list[Technique]:
        """Return all techniques that are currently available to learn or use."""
        return [
            self._techniques_by_id[state["technique_id"]]
            for state in self._technique_states_cache
            if state["available"]
        ]

    def effective_passive_techniques(self) -> list[Technique]:
        """Return passive techniques that are learned and currently effective."""
        return [
            self._techniques_by_id[state["technique_id"]]
            for state in self._technique_states_cache
            if state["passive_active"]
        ]

    def activatable_techniques(self) -> list[TechniqueState]:
        """Return learned non-passive techniques together with activation metadata."""
        return [
            state
            for state in self._technique_states_cache
            if state["learned"] and state["available"] and state["technique_type"] != Technique.TechniqueType.PASSIVE
        ]

    def technique_choices(self, technique: Technique | int) -> list[CharacterTechniqueChoice]:
        """Return all persisted character choices for one technique."""
        technique_obj = self._coerce_technique(technique)
        return list(self._technique_choices_by_technique_id.get(technique_obj.id, []))

    def race_choices(self, definition: RaceChoiceDefinition | int) -> list[CharacterRaceChoice]:
        """Return all persisted character race choices for one definition."""
        definition_id = definition.id if isinstance(definition, RaceChoiceDefinition) else int(definition)
        return list(self._race_choices_by_definition_id.get(definition_id, []))

    def is_technique_choice_complete(self, technique: Technique | int) -> bool:
        """Return whether a technique's persistent build choices are fully configured."""
        return self._is_technique_choice_complete(self._coerce_technique(technique))

    def is_race_choice_complete(self, definition: RaceChoiceDefinition | int) -> bool:
        """Return whether one race definition has all required persisted selections."""
        definition_obj = definition if isinstance(definition, RaceChoiceDefinition) else RaceChoiceDefinition.objects.get(pk=definition)
        selected_count = len(self.race_choices(definition_obj))
        if selected_count > definition_obj.max_choices:
            return False
        if definition_obj.is_required and selected_count < definition_obj.min_choices:
            return False
        return True

    def modifier_total_for_skill(self, skill_slug: str) -> int:
        """Return all direct skill modifiers for one exact skill slug."""
        return self.modifier_engine.resolve_numeric_total(TargetDomain.SKILL, skill_slug)

    def modifier_total_for_skill_category(self, category_slug: str) -> int:
        """Return all modifiers that target one whole skill category."""
        return self.modifier_engine.resolve_numeric_total(TargetDomain.SKILL_CATEGORY, category_slug)

    def modifier_total_for_language(self, language_key: str) -> int:
        """Return all modifiers that target one concrete language or language grouping."""
        return self.modifier_engine.resolve_numeric_total(TargetDomain.LANGUAGE, language_key)

    def modifier_total_for_stat(self, slug: str) -> int:
        """Return all modifiers that target one derived stat slug."""
        if slug in {"wound_penalty_ignore", "armor_penalty_ignore", "shield_penalty_ignore"}:
            target_domain = TargetDomain.RULE_FLAG
        elif str(slug).startswith("dmg_"):
            target_domain = TargetDomain.COMBAT
        else:
            target_domain = TargetDomain.DERIVED_STAT
        return self.modifier_engine.resolve_numeric_total(target_domain, slug)

    def modifier_total_for_item(self, item: Item | int) -> int:
        """Return all modifiers that target one specific item."""
        item_id = item.id if isinstance(item, Item) else int(item)
        return self.modifier_engine.resolve_numeric_total(TargetDomain.ITEM, str(item_id))

    def modifier_total_for_item_category(self, item_category: str) -> int:
        """Return all modifiers that target one item category key."""
        return self.modifier_engine.resolve_numeric_total(TargetDomain.ITEM_CATEGORY, item_category)

    def modifier_total_for_specialization(self, specialization: Specialization | int) -> int:
        """Return all modifiers that target one school specialization."""
        specialization_id = specialization.id if isinstance(specialization, Specialization) else int(specialization)
        return self.modifier_engine.resolve_numeric_total(TargetDomain.SPECIALIZATION, str(specialization_id))

    def modifier_total_for_entity(self, entity: Model) -> int:
        """Return all modifiers that target one arbitrary persisted game entity."""
        content_type = ContentType.objects.get_for_model(entity, for_concrete_model=False)
        return self.modifier_engine.resolve_numeric_total(TargetDomain.ENTITY, f"{content_type.id}:{entity.pk}")

    def debug_legacy_modifier_total_for_skill(self, skill_slug: str) -> int:
        """Return the legacy numeric result for one direct skill target for diagnostics."""
        return self.modifier_engine.debug_legacy_numeric_total(TargetDomain.SKILL, skill_slug)

    def debug_legacy_modifier_total_for_skill_category(self, category_slug: str) -> int:
        """Return the legacy numeric result for one skill-category target for diagnostics."""
        return self.modifier_engine.debug_legacy_numeric_total(TargetDomain.SKILL_CATEGORY, category_slug)

    def debug_legacy_modifier_total_for_stat(self, slug: str) -> int:
        """Return the legacy numeric result for one stat-like target for diagnostics."""
        if slug in {"wound_penalty_ignore", "armor_penalty_ignore", "shield_penalty_ignore"}:
            target_domain = TargetDomain.RULE_FLAG
        elif str(slug).startswith("dmg_"):
            target_domain = TargetDomain.COMBAT
        else:
            target_domain = TargetDomain.DERIVED_STAT
        return self.modifier_engine.debug_legacy_numeric_total(target_domain, slug)

    @cached_property
    def modifier_engine(self) -> ModifierEngine:
        """Return the central modifier engine bound to this character engine."""
        return ModifierEngine(self, resolution_mode=self.modifier_resolution_mode)

    def resolve_skill_value(self, skill_slug: str, context: dict | None = None) -> int:
        """Resolve one skill through the central modifier engine."""
        return self.modifier_engine.resolve_skill_value(skill_slug, context=context)

    def resolve_attribute_bonus(self, attribute_slug: str, context: dict | None = None) -> int:
        """Resolve attribute bonus modifiers through the central modifier engine."""
        return self.modifier_engine.resolve_attribute_bonus(attribute_slug, context=context)

    def resolve_attribute_cap_bonus(self, attribute_slug: str, context: dict | None = None) -> int:
        """Resolve attribute-maximum modifiers through the central modifier engine."""
        return self.modifier_engine.resolve_numeric_total(TargetDomain.ATTRIBUTE_CAP, attribute_slug, context=context)

    def resolve_language_level(self, language_slug: str) -> int:
        """Resolve the effective spoken language level after language modifiers."""
        entry = self._languages_map.get(language_slug)
        if entry is None:
            return 0
        base_level = int(entry.levels)
        modifier_parts = [self.modifier_total_for_language(language_slug)]
        if not bool(entry.is_mother_tongue):
            modifier_parts.append(self.modifier_total_for_language("foreign_languages"))
        return max(0, base_level + sum(int(part) for part in modifier_parts))

    def effective_language_write(self, language_slug: str) -> bool:
        """Return whether the character can currently write the given language."""
        entry = self._languages_map.get(language_slug)
        if entry is None:
            return False
        return bool(entry.can_write)

    def resolve_derived_stat(self, stat_key: str, context: dict | None = None) -> int:
        """Resolve one derived stat through the central modifier engine."""
        return self.modifier_engine.resolve_derived_stat(stat_key, context=context)

    def resolve_resource(self, resource_key: str, context: dict | None = None) -> int:
        """Resolve one resource key through the central modifier engine."""
        return self.modifier_engine.resolve_resource(resource_key, context=context)

    def resolve_resistances(self, context: dict | None = None):
        """Resolve resistance and immunity state through the central modifier engine."""
        return self.modifier_engine.resolve_resistances(context=context)

    def resolve_movement(self, context: dict | None = None):
        """Resolve movement profile through the central modifier engine."""
        return self.modifier_engine.resolve_movement(context=context)

    def resolve_combat_profile(self, context: dict | None = None):
        """Resolve combat profile through the central modifier engine."""
        return self.modifier_engine.resolve_combat_profile(context=context)

    def resolve_combat_value(self, target_key: str, context: dict | None = None) -> int:
        """Resolve one numeric combat-profile target through the central modifier engine."""
        return self.modifier_engine.resolve_combat_value(target_key, context=context)

    def resolve_perception_value(self, target_key: str, context: dict | None = None) -> int:
        """Resolve one numeric perception target through the central modifier engine."""
        return self.modifier_engine.resolve_perception_value(target_key, context=context)

    def resolve_flags(self, context: dict | None = None) -> dict[str, bool]:
        """Resolve boolean rule flags through the central modifier engine."""
        return self.modifier_engine.resolve_flags(context=context)

    def resolve_capabilities(self, context: dict | None = None) -> dict[str, bool]:
        """Resolve capabilities through the central modifier engine."""
        return self.modifier_engine.resolve_capabilities(context=context)

    def resolve_social_profile(self, context: dict | None = None):
        """Resolve social/legal profile through the central modifier engine."""
        return self.modifier_engine.resolve_social_profile(context=context)

    def explain_modifier_resolution(self, target_domain: str, target_key: str, context: dict | None = None) -> list[dict]:
        """Return a debug breakdown for one central modifier target."""
        return self.modifier_engine.explain_resolution((target_domain, target_key), context=context)

    def modifier_resolution_comparisons(self):
        """Return compare-mode rows collected by the central modifier engine."""
        return self.modifier_engine.comparison_log()

    def attribute_modifier(self, short_name: str) -> int:
        """Convert a base attribute value into its system modifier."""
        value = self.attributes().get(short_name, 0)
        return value - 5

    def skill_total(self, skill_slug: str) -> int:
        """Return the final resolved value for one skill."""
        return int(self._skill_base(skill_slug)) + int(self._skill_modifiers(skill_slug))

    def weapon_mastery_for_item(self, item: Item | int | None) -> CharacterWeaponMastery | None:
        """Return the mastered concrete weapon entry for one item, if learned."""
        if item is None:
            return None
        item_id = item if isinstance(item, int) else getattr(item, "id", None)
        if item_id is None:
            return None
        return self._weapon_mastery_entries_by_item_id.get(item_id)

    def weapon_mastery_bonus_for_item(self, item: Item | int | None) -> tuple[int, int]:
        """Return maneuver/damage bonuses from Waffenmeister for one concrete weapon."""
        mastery = self.weapon_mastery_for_item(item)
        school_entry = self._weapon_master_school_entry
        if mastery is None or school_entry is None:
            return 0, 0
        return mastery.maneuver_damage_bonus(school_entry.level)

    def weapon_mastery_quality_bonus_for_item(self, item: Item | int | None) -> int:
        """Return the crafting quality-step bonus for one mastered weapon type."""
        mastery = self.weapon_mastery_for_item(item)
        if mastery is None:
            return 0
        return mastery.quality_step_bonus()

    def weapon_mastery_arcana_bonus_capacity(self) -> int:
        """Return how many +1/+1 bonus-capacity unlocks the character learned."""
        return sum(
            1
            for entry in self._weapon_mastery_arcana_entries
            if entry.kind == CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY
        )

    def weapon_mastery_arcana_runes(self) -> list:
        """Return the runes learned through Waffenmeister arcana progression."""
        return [
            entry.rune
            for entry in self._weapon_mastery_arcana_entries
            if entry.kind == CharacterWeaponMasteryArcana.ArcanaKind.RUNE and entry.rune_id
        ]

    def debug_legacy_skill_total(self, skill_slug: str) -> int:
        """Return the legacy skill total for one skill for migration diagnostics."""
        return int(self._skill_base(skill_slug)) + int(self._legacy_skill_modifiers(skill_slug))

    def debug_legacy_calculate_initiative(self) -> int:
        """Return the legacy initiative result for migration diagnostics."""
        return (
            self.attribute_modifier("GE")
            + self._debug_legacy_current_wound_penalty()
            + self.debug_legacy_modifier_total_for_stat("initiative")
        )

    def debug_legacy_calculate_arcane_power(self) -> int:
        """Return the legacy arcane power result for migration diagnostics."""
        willpower = self.attributes().get("WILL", 0)
        school_levels = sum(entry.level for entry in self._school_entries.values())
        return willpower + school_levels + self.debug_legacy_modifier_total_for_stat("arcane_power")

    def debug_legacy_vw(self) -> int:
        """Return the legacy VW result for migration diagnostics."""
        return 14 + self.attribute_modifier("GE") + self.attribute_modifier("WA") + self.debug_legacy_modifier_total_for_stat("vw")

    def debug_legacy_gw(self) -> int:
        """Return the legacy GW result for migration diagnostics."""
        return 14 + self.attribute_modifier("INT") + self.attribute_modifier("WILL") + self.debug_legacy_modifier_total_for_stat("gw")

    def debug_legacy_sr(self) -> int:
        """Return the legacy SR result for migration diagnostics."""
        return 14 + self.attribute_modifier("ST") + self.attribute_modifier("KON") + self.debug_legacy_modifier_total_for_stat("sr")

    def debug_legacy_get_grs(self) -> int:
        """Return the legacy armor rating result for migration diagnostics."""
        total = sum(
            ItemEngine(armor).get_armor_rs_raw() or 0
            for armor in self.equipped_armor_items()
        )
        return total + self.debug_legacy_modifier_total_for_stat("rs")

    def skill_breakdown(self, skill_slug: str) -> SkillBreakdown | SkillError:
        """Return a detailed breakdown of a skill calculation."""
        skills = self.skills()
        if skill_slug not in skills:
            return {"skill_slug": skill_slug, "error": "skill not found"}

        info = skills[skill_slug]
        attr_short = info["attribute"]
        level = int(info["level"])
        attr_val = int(self.attributes().get(attr_short, 0))
        attr_mod = int(self.attribute_modifier(attr_short))

        base = int(self._skill_base(skill_slug))
        mods = int(self._skill_modifiers(skill_slug))
        total = base + mods

        return {
            "skill_slug": skill_slug,
            "level": level,
            "base_attribute": attr_short,
            "attribute_value": attr_val,
            "attribute_modifier": attr_mod,
            "base": base,
            "modifiers": mods,
            "total": total,
        }

    def _skill_base(self, skill_slug: str) -> int:
        """Calculate the unmodified base value of a skill."""
        skills = self.skills()
        if skill_slug not in skills:
            return 0

        info = skills[skill_slug]
        return int(info["level"]) + int(self.attribute_modifier(info["attribute"]))

    def _legacy_skill_modifiers(self, skill_slug: str) -> int:
        """Resolve skill modifiers through the legacy numeric path for diagnostics only."""
        info = self.skills().get(skill_slug)
        category_slug = info["category"] if info else None
        skill_id = info["skill_id"] if info else None

        modifier_parts = [
            self._debug_legacy_current_wound_penalty(),
            self._debug_legacy_load_penalty(),
            self.debug_legacy_modifier_total_for_skill(skill_slug),
        ]
        if category_slug:
            modifier_parts.append(self.debug_legacy_modifier_total_for_skill_category(category_slug))
        if skill_id is not None:
            modifier_parts.append(self._resolve_choice_skill_bonus(skill_id))
            modifier_parts.append(self._legacy_choice_skill_modifier_total(skill_id))
        return sum(modifier_parts)

    def _debug_legacy_is_wound_penalty_ignored(self) -> bool:
        """Return the legacy rule-flag state for wound penalty ignore."""
        return bool(self.debug_legacy_modifier_total_for_stat("wound_penalty_ignore"))

    def _debug_legacy_current_wound_penalty(self) -> int:
        """Return the effective legacy wound penalty for diagnostics."""
        penalty = self.current_wound_stage()[1]
        if penalty is None:
            return 0
        if self._debug_legacy_is_wound_penalty_ignored():
            return 0
        return penalty

    def _debug_legacy_get_bel(self) -> int:
        """Return the legacy armor encumbrance result for diagnostics."""
        if self.debug_legacy_modifier_total_for_stat("armor_penalty_ignore"):
            return 0

        armor_bel = 0
        for armor in self.equipped_armor_items():
            armor_bel += ItemEngine(armor).get_armor_encumbrance() or 0

        shield_bel = 0
        for shield in self.equipped_shield_items():
            shield_bel += ItemEngine(shield).get_shield_encumbrance() or 0

        return armor_bel + shield_bel

    def _debug_legacy_load_penalty(self) -> int:
        """Return the legacy load penalty for diagnostics."""
        bel_value = int(self._debug_legacy_get_bel())
        return bel_value if bel_value <= 0 else -bel_value

    def _build_technique_state(
        self,
        technique: Technique,
        learned_stack: set[int] | None = None,
        available_stack: set[int] | None = None,
    ) -> TechniqueState:
        """Resolve all relevant school, path, requirement, and learning flags."""
        learned_stack = set() if learned_stack is None else learned_stack
        available_stack = set() if available_stack is None else available_stack

        school_level = self.school_level(technique.school_id)
        selected_path = self.selected_school_path(technique.school_id)
        school_known = school_level > 0
        required_level_met = school_level >= technique.level
        path_allowed = self._is_path_allowed(technique, selected_path=selected_path)
        requirements_met = False
        if school_known and required_level_met and path_allowed:
            requirements_met = self._requirements_met(
                technique,
                learned_stack,
                available_stack,
                school_level=school_level,
                selected_path=selected_path,
            )

        available = False
        if school_known and required_level_met and path_allowed and requirements_met:
            available = not self._is_excluded_by_learned_techniques(
                technique,
                learned_stack,
                available_stack,
            )

        explicitly_learned = self._is_technique_explicitly_learned(technique)
        learned = explicitly_learned or self._is_automatic_technique_learned(
            technique,
            learned_stack,
            available_stack,
            available=available,
        )
        choice_count = len(self.technique_choices(technique))
        choices_complete = self._is_technique_choice_complete(technique)
        engine_resolves_effects = self._technique_effect_is_computed(technique) and choices_complete

        activation: TechniqueActivationData | None = None
        if technique.technique_type != Technique.TechniqueType.PASSIVE:
            activation = {
                "action_type": technique.action_type,
                "usage_type": technique.usage_type,
                "activation_cost": technique.activation_cost,
                "activation_cost_resource": technique.activation_cost_resource or None,
            }

        return {
            "technique_id": technique.id,
            "technique_name": technique.name,
            "school_id": technique.school_id,
            "school_name": technique.school.name,
            "school_known": school_known,
            "school_level": school_level,
            "required_level": technique.level,
            "required_level_met": required_level_met,
            "path_id": technique.path_id,
            "path_name": technique.path.name if technique.path_id else None,
            "choice_block_id": technique.choice_block_id,
            "choice_block_name": technique.choice_block.name if technique.choice_block_id and technique.choice_block.name else None,
            "choice_block_description": (
                technique.choice_block.description if technique.choice_block_id and technique.choice_block.description else None
            ),
            "selected_path_id": selected_path.id if selected_path else None,
            "selected_path_name": selected_path.name if selected_path else None,
            "choice_target_kind": technique.choice_target_kind,
            "choice_limit": technique.choice_limit,
            "choice_count": choice_count,
            "choices_complete": choices_complete,
            "path_allowed": path_allowed,
            "requirements_met": requirements_met,
            "available": available,
            "explicitly_learned": explicitly_learned,
            "learned": learned,
            "acquisition_type": technique.acquisition_type,
            "technique_type": technique.technique_type,
            "support_level": technique.support_level,
            "specialization_slot_grants": technique.specialization_slot_grants,
            "engine_resolves_effects": engine_resolves_effects,
            "is_choice_placeholder": technique.is_choice_placeholder,
            "choice_group": technique.choice_group or None,
            "selection_notes": technique.selection_notes or None,
            "passive_active": (
                learned
                and available
                and engine_resolves_effects
                and technique.technique_type == Technique.TechniqueType.PASSIVE
            ),
            "activation": activation,
        }

    def _skill_modifiers(self, skill_slug: str) -> int:
        """Resolve wound, armor, direct skill, and category modifiers."""
        info = self.skills().get(skill_slug)
        category_slug = info["category"] if info else None
        skill_id = info["skill_id"] if info else None

        modifier_parts = [
            self.current_wound_penalty(),
            self.load_penalty(),
            self.modifier_total_for_skill(skill_slug),
        ]
        if category_slug:
            modifier_parts.append(
                self.modifier_total_for_skill_category(category_slug)
            )
        if skill_id is not None:
            modifier_parts.append(self._resolve_choice_skill_bonus(skill_id))
            modifier_parts.append(self._resolve_choice_skill_modifiers(skill_id))
        return sum(modifier_parts)

    def _resolve_stat_modifiers(self, slug: str) -> int:
        """Resolve all stat-targeting modifiers for one stat slug."""
        return self.modifier_total_for_stat(slug)

    def _resolve_target_modifiers(self, target_kind: str, target_slug: str) -> int:
        """Sum all active modifiers for a concrete target kind and slug."""
        total = 0
        modifiers = self._modifiers_by_target.get((target_kind, target_slug), [])
        learned_stack: set[int] = set()
        available_stack: set[int] = set()

        for modifier in modifiers:
            total += self._modifier_value(modifier, learned_stack, available_stack)
        return total

    def _resolve_choice_skill_modifiers(self, skill_id: int) -> int:
        """Resolve choice-bound skill modifiers through the central modifier engine."""
        return self.modifier_engine.resolve_choice_skill_modifier_total(skill_id)

    def _legacy_choice_skill_modifier_total(self, skill_id: int) -> int:
        """
        Resolve modifier rows that target a skill via persisted technique or
        race choices.
        """
        learned_stack = set()
        available_stack = set()

        modifiers = [
            modifier
            for modifier in self._all_modifiers
            if modifier.target_kind == Modifier.TargetKind.SKILL
            and (
                modifier.target_choice_definition_id
                or modifier.target_race_choice_definition_id
            )
        ]

        total = 0

        for modifier in modifiers:
            if modifier.target_choice_definition_id:
                choices = self._technique_choices_by_definition_id.get(
                    modifier.target_choice_definition_id, []
                )
            else:
                choices = self._race_choices_by_definition_id.get(
                    modifier.target_race_choice_definition_id, []
                )
            for choice in choices:
                if choice.selected_skill_id != skill_id:
                    continue
                if not self._modifier_source_is_active(modifier, learned_stack, available_stack):
                    continue
                total += self._modifier_value(modifier, learned_stack, available_stack)
                break

        return total

    def _resolve_choice_skill_bonus(self, skill_id: int) -> int:
        """Resolve fixed computed bonuses granted by persistent technique choices."""
        return self._choice_skill_bonus_by_skill_id.get(skill_id, 0)

    def _modifier_value(
        self,
        modifier: Modifier,
        learned_stack: set[int],
        available_stack: set[int],
    ) -> int:
        """Resolve the numeric value of one modifier if its source is active."""
        if not self._modifier_source_is_active(modifier, learned_stack, available_stack):
            return 0
        if not self._modifier_school_gate_is_open(modifier):
            return 0
        if modifier.mode == Modifier.Mode.FLAT:
            return modifier.value

        scale_value = self._modifier_scale_value(modifier, modifier.scale_source)
        if scale_value is None:
            return 0

        raw_value = (scale_value * modifier.value * modifier.mul) / modifier.div
        if modifier.round_mode == Modifier.RoundMode.CEIL:
            resolved_value = math.ceil(raw_value)
        else:
            resolved_value = math.floor(raw_value)

        if modifier.cap_mode != Modifier.CapMode.NONE:
            cap_value = self._modifier_scale_value(modifier, modifier.cap_source)
            if cap_value is not None:
                if modifier.cap_mode == Modifier.CapMode.MIN:
                    resolved_value = max(resolved_value, cap_value)
                elif modifier.cap_mode == Modifier.CapMode.MAX:
                    resolved_value = min(resolved_value, cap_value)

        return resolved_value

    def _modifier_source_is_active(
        self,
        modifier: Modifier,
        learned_stack: set[int],
        available_stack: set[int],
    ) -> bool:
        """Check whether the modifier source currently contributes effects."""
        source = self._modifier_source(modifier)
        if source is None:
            return False
        if isinstance(source, Race):
            return self.character.race_id == source.id
        if isinstance(source, School):
            return self.school_level(source) > 0
        if isinstance(source, Trait):
            return source.id in self._trait_levels
        if isinstance(source, Technique):
            if source.id in self._race_technique_ids:
                return (
                    self._technique_effect_is_computed(source)
                    and self._is_technique_choice_complete(source)
                    and source.technique_type == Technique.TechniqueType.PASSIVE
                )
            return (
                self._technique_effect_is_computed(source)
                and self._is_technique_choice_complete(source)
                and source.technique_type == Technique.TechniqueType.PASSIVE
                and self._has_technique_learned(source, learned_stack, available_stack)
                and self._is_technique_available(source, learned_stack, available_stack)
            )
        if isinstance(source, Item):
            return CharacterItem.objects.filter(
                owner=self.character,
                equipped=True,
                item_id=source.id,
            ).filter(
                Q(item__is_magic=True) | Q(item__item_type=Item.ItemType.MAGIC_ITEM)
            ).exists()
        if isinstance(source, CharacterItem):
            return source.equipped and bool(source.is_magic)
        return False

    def _technique_effect_is_computed(self, technique: Technique) -> bool:
        """Return whether the engine should resolve passive effects for this technique."""
        return technique.support_level == Technique.SupportLevel.COMPUTED

    def _is_technique_choice_complete(self, technique: Technique) -> bool:
        """Check whether the configured persistent technique choices are fully stored."""
        if self._technique_has_explicit_choice_definitions(technique):
            for definition in self._active_technique_choice_definitions(technique):
                selected_count = len(self._technique_choices_by_definition_id.get(definition.id, []))
                if selected_count > definition.max_choices:
                    return False
                if definition.is_required and selected_count < definition.min_choices:
                    return False
            return True
        if technique.choice_target_kind == Technique.ChoiceTargetKind.NONE:
            return True
        legacy_choices = [choice for choice in self.technique_choices(technique) if choice.definition_id is None]
        return len(legacy_choices) >= technique.choice_limit

    def _technique_has_explicit_choice_definitions(self, technique: Technique) -> bool:
        """Return whether a technique uses definition rows instead of the legacy single-choice fields."""
        return bool(self._active_technique_choice_definitions(technique))

    def _active_technique_choice_definitions(self, technique: Technique) -> list[TechniqueChoiceDefinition]:
        """Return active choice definitions for one technique."""
        return [definition for definition in technique.choice_definitions.all() if definition.is_active]

    def _modifier_school_gate_is_open(self, modifier: Modifier) -> bool:
        """Check optional minimum school-level gating for a modifier."""
        if modifier.min_school_level is None:
            return True
        gate_school = self._modifier_gate_school(modifier)
        if gate_school is None:
            return False
        return self.school_level(gate_school) >= modifier.min_school_level

    def _modifier_gate_school(self, modifier: Modifier) -> School | None:
        """Resolve which school drives school-level scaling or gating."""
        if modifier.scale_school_id:
            return modifier.scale_school
        source = self._modifier_source(modifier)
        if isinstance(source, School):
            return source
        if isinstance(source, Technique):
            return source.school
        return None

    def _modifier_scale_value(self, modifier: Modifier, scale_source: str | None) -> int | None:
        """Resolve the raw numeric input used for scaled modifier math."""
        if not scale_source:
            return None
        if scale_source == Modifier.ScaleSource.SCHOOL_LEVEL:
            gate_school = self._modifier_gate_school(modifier)
            return self.school_level(gate_school) if gate_school else None
        if scale_source == Modifier.ScaleSource.FAME_TOTAL:
            return self.fame_total()
        if scale_source == Modifier.ScaleSource.TRAIT_LVL:
            source = self._modifier_source(modifier)
            if isinstance(source, Trait):
                return self._trait_levels.get(source.id)
        if scale_source == Modifier.ScaleSource.SKILL_LEVEL:
            if not modifier.scale_skill_id:
                return None
            skill_info = self.skills().get(modifier.scale_skill.slug)
            return int(skill_info["level"]) if skill_info else 0
        if scale_source == Modifier.ScaleSource.SKILL_TOTAL:
            if not modifier.scale_skill_id:
                return None
            return self.skill_total(modifier.scale_skill.slug)
        return None

    def _modifier_source(self, modifier: Modifier) -> Model | None:
        """Return a preloaded modifier source instead of resolving the GFK repeatedly."""
        return self._modifier_sources.get((modifier.source_content_type_id, modifier.source_object_id))

    def _coerce_school_id(self, school: School | Technique | CharacterSchool | int | None) -> int:
        """Normalize supported school-like inputs to a school id."""
        if isinstance(school, CharacterSchool):
            return school.school_id
        if isinstance(school, Technique):
            return school.school_id
        if isinstance(school, School):
            return school.id
        if school is None:
            raise ValueError("school must not be None")
        return int(school)

    def _coerce_technique(self, technique: Technique | int) -> Technique:
        """Normalize supported technique-like inputs to a technique instance."""
        if isinstance(technique, Technique):
            return technique
        cached = self._techniques_by_id.get(int(technique))
        if cached is not None:
            return cached
        return (
            Technique.objects.select_related("school", "path")
            .get(pk=int(technique))
        )

    def _character_school_techniques(self) -> list[Technique]:
        """Load all techniques that belong to schools the character knows."""
        return self._character_school_technique_list

    def _has_technique_learned(
        self,
        technique: Technique,
        learned_stack: set[int],
        available_stack: set[int],
    ) -> bool:
        """Resolve explicit learning plus automatic technique acquisition."""
        if technique.id in self._technique_learned_cache:
            return self._technique_learned_cache[technique.id]
        if self._is_technique_explicitly_learned(technique):
            self._technique_learned_cache[technique.id] = True
            return True

        return self._is_automatic_technique_learned(
            technique,
            learned_stack,
            available_stack,
        )

    def _is_technique_explicitly_learned(self, technique: Technique) -> bool:
        """Return whether the technique was stored as an explicit character pick."""
        return technique.id in self._manual_learned_technique_ids

    def _is_automatic_technique_learned(
        self,
        technique: Technique,
        learned_stack: set[int],
        available_stack: set[int],
        *,
        available: bool | None = None,
    ) -> bool:
        """Return whether an automatic technique counts as learned right now."""
        if technique.acquisition_type != Technique.AcquisitionType.AUTOMATIC:
            self._technique_learned_cache[technique.id] = False
            return False
        if technique.id in learned_stack:
            return False
        learned_stack.add(technique.id)
        try:
            resolved = False
            if available is not None:
                resolved = available
            else:
                resolved = self._is_technique_available(technique, learned_stack, available_stack)
            self._technique_learned_cache[technique.id] = resolved
            return resolved
        finally:
            learned_stack.remove(technique.id)

    def _is_technique_available(
        self,
        technique: Technique,
        learned_stack: set[int],
        available_stack: set[int],
    ) -> bool:
        """Check school, path, requirements, and exclusions for one technique."""
        if technique.id in self._technique_available_cache:
            return self._technique_available_cache[technique.id]
        if technique.id in available_stack:
            return False
        available_stack.add(technique.id)
        try:
            school_level = self.school_level(technique.school_id)
            selected_path = self.selected_school_path(technique.school_id)
            if school_level <= 0:
                self._technique_available_cache[technique.id] = False
                return False
            if school_level < technique.level:
                self._technique_available_cache[technique.id] = False
                return False
            if not self._is_path_allowed(technique, selected_path=selected_path):
                self._technique_available_cache[technique.id] = False
                return False
            if not self._requirements_met(
                technique,
                learned_stack,
                available_stack,
                school_level=school_level,
                selected_path=selected_path,
            ):
                self._technique_available_cache[technique.id] = False
                return False
            resolved = not self._is_excluded_by_learned_techniques(technique, learned_stack, available_stack)
            self._technique_available_cache[technique.id] = resolved
            if not resolved:
                return False
            return True
        finally:
            available_stack.remove(technique.id)

    def _is_path_allowed(
        self,
        technique: Technique,
        *,
        selected_path: SchoolPath | None = None,
    ) -> bool:
        """Check whether the current path choice permits the technique."""
        if not technique.path_id:
            return True
        if selected_path is None:
            selected_path = self.selected_school_path(technique.school_id)
        return selected_path is not None and selected_path.id == technique.path_id

    def _requirements_met(
        self,
        technique: Technique,
        learned_stack: set[int],
        available_stack: set[int],
        *,
        school_level: int | None = None,
        selected_path: SchoolPath | None = None,
    ) -> bool:
        """Evaluate all requirement rows as a strict AND conjunction."""
        if technique.id in self._technique_requirement_cache:
            return self._technique_requirement_cache[technique.id]

        school_level = self.school_level(technique.school_id) if school_level is None else school_level
        selected_path = self.selected_school_path(technique.school_id) if selected_path is None else selected_path
        requirements = technique.requirements.all()
        # Each TechniqueRequirement row is one atomic requirement. All rows must pass.
        for requirement in requirements:
            if (
                requirement.minimum_school_level is not None
                and school_level < requirement.minimum_school_level
            ):
                self._technique_requirement_cache[technique.id] = False
                return False
            if requirement.required_path_id is not None:
                if selected_path is None or selected_path.id != requirement.required_path_id:
                    self._technique_requirement_cache[technique.id] = False
                    return False
            if requirement.required_technique_id is not None and not self._has_technique_learned(
                requirement.required_technique,
                learned_stack,
                available_stack,
            ):
                self._technique_requirement_cache[technique.id] = False
                return False
            if requirement.required_skill_id is not None:
                if self._skill_levels_by_id.get(requirement.required_skill_id, 0) < (requirement.required_skill_level or 0):
                    self._technique_requirement_cache[technique.id] = False
                    return False
            if requirement.required_trait_id is not None:
                if self._trait_levels.get(requirement.required_trait_id, 0) < (requirement.required_trait_level or 0):
                    self._technique_requirement_cache[technique.id] = False
                    return False
        self._technique_requirement_cache[technique.id] = True
        return True

    def _is_excluded_by_learned_techniques(
        self,
        technique: Technique,
        learned_stack: set[int],
        available_stack: set[int],
    ) -> bool:
        """Check whether any already learned technique excludes this one."""
        if technique.id in self._technique_exclusion_cache:
            return self._technique_exclusion_cache[technique.id]

        excluded_techniques = [
            relation.excluded_technique
            for relation in technique.exclusions.all()
        ]
        excluded_techniques.extend(
            relation.technique
            for relation in technique.excluded_by.all()
        )
        resolved = any(
            self._has_technique_learned(excluded, learned_stack, available_stack)
            for excluded in excluded_techniques
        )
        self._technique_exclusion_cache[technique.id] = resolved
        return resolved
