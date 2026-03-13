"""Rule calculation helpers for character model instances."""

from __future__ import annotations

from collections import defaultdict
import math
from functools import cached_property
from typing import DefaultDict, TypeAlias, TypedDict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model, Prefetch, Q, QuerySet

from charsheet.constants import (
    ARCANE_POWER,
    ARMOR_PENALTY_IGNORE,
    ATTR_GE,
    ATTR_INT,
    ATTR_KON,
    ATTR_ST,
    ATTR_WA,
    ATTR_WILL,
    DEFENSE_GW,
    DEFENSE_SR,
    DEFENSE_VW,
    INITIATIVE,
    WOUND_PENALTY_IGNORE,
    WOUND_STAGE,
)
from charsheet.models import (
    Character,
    CharacterItem,
    CharacterSchool,
    CharacterSchoolPath,
    CharacterTechniqueChoice,
    Item,
    Modifier,
    ProgressionRule,
    Race,
    School,
    SchoolPath,
    Technique,
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
    family_id: int | None


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
    engine_resolves_effects: bool
    is_choice_placeholder: bool
    choice_group: str | None
    selection_notes: str | None
    passive_active: bool
    activation: TechniqueActivationData | None


class CharacterEngine:
    """Calculate derived character values from persisted model data."""

    def __init__(self, character: Character) -> None:
        self.character = character

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
            "skill__family",
        )
        return {
            entry.skill.slug: {
                "skill_id": entry.skill_id,
                "level": entry.level,
                "category": entry.skill.category.slug,
                "attribute": entry.skill.attribute.short_name,
                "family_id": entry.skill.family_id,
            }
            for entry in qs
        }

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
                "selected_skill",
                "selected_skill_family",
            )
            .order_by("technique__school__name", "technique__level", "technique__name", "id")
        )
        for choice in queryset:
            grouped[choice.technique_id].append(choice)
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
    def _choice_skill_bonus_by_family_id(self) -> dict[int, int]:
        """Index fixed choice-based bonuses by selected skill family id."""
        totals: DefaultDict[int, int] = defaultdict(int)
        for technique in self._choice_bonus_techniques:
            state = self._technique_state_map.get(technique.id)
            if state is None or not (
                state["learned"]
                and state["available"]
                and state["engine_resolves_effects"]
            ):
                continue
            if technique.choice_target_kind != Technique.ChoiceTargetKind.SKILL_FAMILY:
                continue
            for choice in self.technique_choices(technique):
                if choice.selected_skill_family_id is not None:
                    totals[choice.selected_skill_family_id] += technique.choice_bonus_value
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
    def _all_modifiers(self) -> list[Modifier]:
        """Load only modifiers whose sources are relevant for this character."""
        source_ids_by_model: dict[type[Model], set[int]] = {
            Race: {self.character.race_id},
            School: set(self._school_entries.keys()),
            Trait: set(self._trait_levels.keys()),
            Technique: set(self._computed_technique_ids),
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
            .select_related("scale_school", "source_content_type")
        )

    @cached_property
    def _modifiers_by_target(self) -> dict[ModifierTargetKey, list[Modifier]]:
        """Group modifiers by target kind and slug for O(1) resolver access."""
        grouped: DefaultDict[ModifierTargetKey, list[Modifier]] = defaultdict(list)
        for modifier in self._all_modifiers:
            grouped[(modifier.target_kind, modifier.target_slug)].append(modifier)
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
    def _technique_learned_cache(self) -> dict[int, bool]:
        """Memoize resolved learned-state checks across recursive technique logic."""
        return {}

    @cached_property
    def _technique_available_cache(self) -> dict[int, bool]:
        """Memoize resolved availability checks across recursive technique logic."""
        return {}

    @cached_property
    def _technique_requirement_cache(self) -> dict[int, bool]:
        """Memoize structured requirement checks for techniques."""
        return {}

    @cached_property
    def _technique_exclusion_cache(self) -> dict[int, bool]:
        """Memoize exclusion checks against already learned techniques."""
        return {}

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

        return list(
            Technique.objects.filter(school_id__in=school_ids)
            .select_related("school", "path")
            .prefetch_related(
                Prefetch("requirements", queryset=requirement_queryset),
                Prefetch("exclusions", queryset=exclusions_queryset),
                Prefetch("excluded_by", queryset=excluded_by_queryset),
            )
            .order_by("school__name", "level", "name")
        )

    @cached_property
    def _computed_technique_ids(self) -> set[int]:
        """Cache technique ids whose effects may be resolved automatically."""
        return {
            technique.id
            for technique in self._character_school_technique_list
            if self._technique_effect_is_computed(technique)
        }

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

    def school_level(self, school: School | Technique | CharacterSchool | int) -> int:
        """Return the learned level for a school-like input."""
        school_id = self._coerce_school_id(school)
        entry = self._school_entries.get(school_id)
        return entry.level if entry else 0

    def selected_school_path(self, school: School | Technique | CharacterSchool | int) -> SchoolPath | None:
        """Return the selected path for a school if one exists."""
        school_id = self._coerce_school_id(school)
        entry = self._selected_paths.get(school_id)
        return entry.path if entry else None

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

    def is_technique_choice_complete(self, technique: Technique | int) -> bool:
        """Return whether a technique's persistent build choices are fully configured."""
        return self._is_technique_choice_complete(self._coerce_technique(technique))

    def attribute_modifier(self, short_name: str) -> int:
        """Convert a base attribute value into its system modifier."""
        value = self.attributes().get(short_name, 0)
        return value - 5

    def skill_total(self, skill_slug: str) -> int:
        """Return the final resolved value for one skill."""
        return int(self._skill_base(skill_slug)) + int(self._skill_modifiers(skill_slug))

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
        family_id = info["family_id"] if info else None

        modifier_parts = [
            self.current_wound_penalty(),
            -self.get_bel(),
            self._resolve_target_modifiers(Modifier.TargetKind.SKILL, skill_slug),
        ]
        if category_slug:
            modifier_parts.append(
                self._resolve_target_modifiers(Modifier.TargetKind.CATEGORY, category_slug)
            )
        if skill_id is not None:
            modifier_parts.append(self._resolve_choice_skill_bonus(skill_id, family_id))
        return sum(modifier_parts)

    def _resolve_stat_modifiers(self, slug: str) -> int:
        """Resolve all stat-targeting modifiers for one stat slug."""
        return self._resolve_target_modifiers(Modifier.TargetKind.STAT, slug)

    def _resolve_target_modifiers(self, target_kind: str, target_slug: str) -> int:
        """Sum all active modifiers for a concrete target kind and slug."""
        total = 0
        modifiers = self._modifiers_by_target.get((target_kind, target_slug), [])
        learned_stack: set[int] = set()
        available_stack: set[int] = set()

        for modifier in modifiers:
            total += self._modifier_value(modifier, learned_stack, available_stack)
        return total

    def _resolve_choice_skill_bonus(self, skill_id: int, family_id: int | None) -> int:
        """Resolve fixed computed bonuses granted by persistent technique choices."""
        total = self._choice_skill_bonus_by_skill_id.get(skill_id, 0)
        if family_id is not None:
            total += self._choice_skill_bonus_by_family_id.get(family_id, 0)
        return total

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
            return (
                self._technique_effect_is_computed(source)
                and self._is_technique_choice_complete(source)
                and source.technique_type == Technique.TechniqueType.PASSIVE
                and self._has_technique_learned(source, learned_stack, available_stack)
                and self._is_technique_available(source, learned_stack, available_stack)
            )
        return False

    def _technique_effect_is_computed(self, technique: Technique) -> bool:
        """Return whether the engine should resolve passive effects for this technique."""
        return technique.support_level == Technique.SupportLevel.COMPUTED

    def _is_technique_choice_complete(self, technique: Technique) -> bool:
        """Check whether the configured persistent technique choices are fully stored."""
        if technique.choice_target_kind == Technique.ChoiceTargetKind.NONE:
            return True
        return len(self.technique_choices(technique)) >= technique.choice_limit

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

    def active_progression_rules(self) -> list[ActiveProgressionRule]:
        """Return all progression rules activated by the character's schools."""
        result: list[ActiveProgressionRule] = []
        for entry in self._school_entries.values():
            rules = self._progression_rules_by_type.get(entry.school.type_id, [])
            for rule in rules:
                if rule.min_level > entry.level:
                    continue
                result.append(
                    {
                        "school_id": entry.school_id,
                        "school_name": entry.school.name,
                        "school_level": entry.level,
                        "rule": rule,
                    }
                )
        return result

    def fame_total(self) -> int:
        """Return the combined fame-related score used by scaling rules."""
        return (
            self.character.personal_fame_point
            + self.character.personal_fame_rank
            + self.character.sacrifice_rank
            + self.character.artefact_rank
        )

    def calculate_initiative(self) -> int:
        """Calculate the character's initiative value."""
        return self.attribute_modifier(ATTR_GE) + self.current_wound_penalty() + self._resolve_stat_modifiers(INITIATIVE)

    def calculate_arcane_power(self) -> int:
        """Calculate the character's arcane power value."""
        willpower = self.attributes().get(ATTR_WILL, 0)
        school_levels = sum(entry.level for entry in self._school_entries.values())
        return willpower + school_levels + self._resolve_stat_modifiers(ARCANE_POWER)

    def calculate_potential(self) -> int:
        """Calculate the character's potential value."""
        willpower = self.attributes().get(ATTR_WILL, 0)
        return willpower // 2

    def wound_thresholds(self) -> dict[int, tuple[str, int]]:
        """Build the wound-stage threshold table for the current character."""
        constitution = self.attributes().get(ATTR_KON, 0)
        additional_stages = self._resolve_stat_modifiers(WOUND_STAGE)
        amount_threshold = 6 + additional_stages

        stage_numbers = [number * constitution for number in range(1, amount_threshold + 1)]
        stage_names = [
            "Angeschlagen",
            "Verletzt",
            "Verwundet",
            "Schwer verwundet",
            "Ausser Gefecht",
            "Koma",
        ]
        stage_penalties = [0, -2, -4, -6, 0, 0]

        missing = max(0, len(stage_numbers) - len(stage_names))
        stages = ["-"] * missing + stage_names
        penalties = [0] * missing + stage_penalties

        return {
            threshold: (stage, penalty)
            for threshold, stage, penalty in zip(stage_numbers, stages, penalties)
        }

    def calculate_defense(self, mod1: str, mod2: str, slug: str) -> int:
        """Resolve one defense value from two attributes and stat modifiers."""
        return (
            14
            + self.attribute_modifier(mod1)
            + self.attribute_modifier(mod2)
            + self._resolve_stat_modifiers(slug)
        )

    def vw(self) -> int:
        """Return the avoidance defense."""
        return self.calculate_defense(ATTR_GE, ATTR_WA, DEFENSE_VW)

    def gw(self) -> int:
        """Return the mental resistance defense."""
        return self.calculate_defense(ATTR_INT, ATTR_WILL, DEFENSE_GW)

    def sr(self) -> int:
        """Return the physical resistance defense."""
        return self.calculate_defense(ATTR_ST, ATTR_KON, DEFENSE_SR)

    def current_wound_stage(self) -> tuple[str, int | None]:
        """Return the current wound stage and its raw penalty."""
        wound_dict = self.wound_thresholds()
        threshold_numbers = sorted(wound_dict.keys())
        if not threshold_numbers:
            return ("-", None)

        damage = self.character.current_damage
        if damage < threshold_numbers[0]:
            return ("-", None)
        if damage > threshold_numbers[-1]:
            return ("Tod", 0)

        current_stage: tuple[str, int | None] = ("-", None)
        for threshold in threshold_numbers:
            if damage >= threshold:
                stage_name, penalty = wound_dict[threshold]
                current_stage = (stage_name, penalty)
            else:
                break
        return current_stage

    def current_wound_penalty(self) -> int:
        """Return the effective wound penalty after ignore effects."""
        penalty = self.current_wound_stage()[1]
        if penalty is None:
            return 0
        if self.is_wound_penalty_ignored():
            return 0
        return penalty

    def current_wound_penalty_raw(self) -> int:
        """Return the raw wound penalty without ignore effects."""
        penalty = self.current_wound_stage()[1]
        if penalty is None:
            return 0
        return penalty

    def is_wound_penalty_ignored(self) -> bool:
        """Return whether wound penalties are currently ignored."""
        return bool(self._resolve_stat_modifiers(WOUND_PENALTY_IGNORE))

    def equipped_armor_items(self) -> QuerySet:
        """Return all currently equipped armor items of the character."""
        return CharacterItem.objects.filter(
            owner=self.character,
            equipped=True,
            item__item_type=Item.ItemType.ARMOR,
        )

    def get_grs(self) -> int:
        """Calculate the total armor rating from equipped armor."""
        total = 0
        zone_sum = 0
        for armor in self.equipped_armor_items():
            stats = armor.item.armorstats
            if stats.rs_total > 0:
                total += stats.rs_total
            else:
                zone_sum += stats.rs_sum()
        return total + (zone_sum // 6)

    def get_bel(self) -> int:
        """Calculate the armor encumbrance value."""
        if self._resolve_stat_modifiers(ARMOR_PENALTY_IGNORE):
            return 0
        return self.get_grs() // 3

    def get_ms(self) -> int:
        """Calculate the movement penalty derived from armor."""
        return self.get_grs() // 2

    def get_dmg_modifier_sum(self, slug: str) -> int:
        """Return the total damage modifier for one damage-related stat slug."""
        return self._resolve_stat_modifiers(slug) + self.attribute_modifier(ATTR_ST)

    def km_to_coins(self) -> tuple[int, int, int]:
        """Split stored copper-equivalent money into coin denominations."""
        player_km = self.character.money
        gm = player_km // 100
        sm = (player_km % 100) // 10
        km = player_km % 10
        return gm, sm, km
