"""Rules engine for validating and materializing character creation drafts."""

from __future__ import annotations

from django.db import transaction

from charsheet.modifiers import CharacterBuildValidator, TraitBuildRule
from charsheet.modifiers.definitions import TargetDomain
from charsheet.modifiers.engine import ModifierEngine
from charsheet.modifiers.registry import build_trait_semantic_modifiers
from charsheet.learning_progression import weapon_mastery_item_definitions
from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterTraitChoice,
    CharacterCreationDraft,
    CharacterItem,
    CharacterLanguage,
    CharacterSchool,
    CharacterSkill,
    CharacterTrait,
    CharacterWeaponMastery,
    CharacterWeaponMasteryArcana,
    Item,
    Language,
    Rune,
    School,
    Skill,
    TraitChoiceDefinition,
    Trait,
)
from charsheet.constants import ATTR_SPEC, LEGENDARY_ATTRIBUTE_TRAIT_SLUG, RESOURCE_KEY_CHOICES, is_allowed_trait_attribute_choice


class CharacterCreationEngine:
    """Rules engine for validating and materializing character creation drafts."""

    FREE_LOCAL_KNOWLEDGE_SKILL_SLUG = "knw_local_knowledge"
    FREE_LOCAL_KNOWLEDGE_LEVEL = 5

    def __init__(self, draft: CharacterCreationDraft):
        self.draft = draft
        self.race = draft.race
        self.state = draft.state or {}

    def get_phase(self, phase: str) -> dict:
        """Return one phase payload from the persisted draft state."""
        return self.state.get(phase, {}) or {}

    @staticmethod
    def _to_int(value: object, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # Phase 1
    def phase_1_attributes(self) -> dict[str, int]:
        attrs = self.get_phase("phase_1").get("attributes", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in attrs.items()}

    def calc_attribute_cost(self, target_level: int, max_value: int) -> int:
        threshold = max_value - 2
        if target_level <= threshold:
            return target_level
        cost = threshold
        for _ in range(threshold + 1, target_level + 1):
            cost += 2
        return cost

    def attribute_min_max_limits(self) -> dict[str, dict[str, int]]:
        return {
            limit.attribute.short_name: {
                "min": int(limit.min_value),
                "max": int(limit.max_value) + self.creation_attribute_cap_bonus(limit.attribute.short_name),
            }
            for limit in self.race.raceattributelimit_set.select_related("attribute")
        }

    def _normalize_trait_choices(self, phase_key: str) -> dict[str, dict[int, list[str]]]:
        """Return normalized draft-time trait choice selections keyed by trait slug and definition id."""
        raw_choices = self.get_phase(phase_key).get("trait_choices", {}) or {}
        normalized: dict[str, dict[int, list[str]]] = {}
        for trait_slug, payload in raw_choices.items():
            definition_map: dict[int, list[str]] = {}
            for raw_definition_id, raw_values in (payload or {}).items():
                definition_id = self._to_int(raw_definition_id, 0)
                if definition_id <= 0:
                    continue
                if isinstance(raw_values, (list, tuple)):
                    values = [str(value).strip() for value in raw_values if str(value).strip()]
                else:
                    single_value = str(raw_values or "").strip()
                    values = [single_value] if single_value else []
                if values:
                    definition_map[definition_id] = values
            if definition_map:
                normalized[str(trait_slug)] = definition_map
        return normalized

    def phase_3_trait_choices(self) -> dict[str, dict[int, list[str]]]:
        """Return normalized draft-time trait choices for selected phase-3 disadvantages."""
        return self._normalize_trait_choices("phase_3")

    def phase_4_trait_choices(self) -> dict[str, dict[int, list[str]]]:
        """Return normalized draft-time trait choices for selected phase-4 advantages."""
        return self._normalize_trait_choices("phase_4")

    def _relevant_choice_definitions(self, trait: Trait, level: int) -> list[TraitChoiceDefinition]:
        """Return the ordered trait choice definitions relevant for the selected rank."""
        definitions = list(trait.choice_definitions.filter(is_active=True).order_by("sort_order", "id"))
        if level <= 0:
            return []
        if len(definitions) > level:
            return definitions[:level]
        return definitions

    def creation_attribute_cap_bonus(self, attribute_slug: str) -> int:
        """Resolve draft-time maximum-attribute modifiers from selected phase-4 advantages."""
        total = 0
        choice_map = self.phase_4_trait_choices()
        for slug, level in self.phase_4_advantages().items():
            trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.ADV).first()
            if trait is None or level <= 0:
                continue
            modifiers = build_trait_semantic_modifiers(trait_slug=slug, level=level, trait=trait)
            trait_choices = choice_map.get(slug, {})
            for modifier in modifiers:
                if modifier.target_domain != TargetDomain.ATTRIBUTE_CAP:
                    continue
                choice_binding = modifier.metadata.get("choice_binding")
                if choice_binding:
                    selected_targets = trait_choices.get(int(choice_binding.get("id") or 0), [])
                    if attribute_slug not in selected_targets:
                        continue
                elif str(modifier.target_key or "") != str(attribute_slug):
                    continue
                modifier_engine = ModifierEngine(modifiers=[modifier])
                resolved = modifier_engine._resolve_numeric_modifier(modifier)
                total += int(resolved or 0)
        return int(total)

    def _trait_choices_are_valid(self, phase_key: str, trait_type: str) -> bool:
        """Validate required draft-time attribute choices for selected traits in one phase."""
        selected_traits = self.phase_3_disadvantages() if phase_key == "phase_3" else self.phase_4_advantages()
        choice_map = self.phase_3_trait_choices() if phase_key == "phase_3" else self.phase_4_trait_choices()
        for slug, level in selected_traits.items():
            if level <= 0:
                continue
            trait = Trait.objects.filter(slug=slug, trait_type=trait_type).first()
            if trait is None:
                return False
            selected = choice_map.get(slug, {})
            for definition in self._relevant_choice_definitions(trait, level):
                if definition.target_kind != TraitChoiceDefinition.TargetKind.ATTRIBUTE:
                    if definition.target_kind != TraitChoiceDefinition.TargetKind.RESOURCE:
                        continue
                values = selected.get(definition.id, [])
                if definition.is_required and len(values) < int(definition.min_choices):
                    return False
                for value in values:
                    if definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE:
                        if not Attribute.objects.filter(short_name=value).exists():
                            return False
                        if not is_allowed_trait_attribute_choice(trait.slug, value):
                            return False
                    elif definition.target_kind == TraitChoiceDefinition.TargetKind.RESOURCE:
                        valid_resources = {choice for choice, _label in RESOURCE_KEY_CHOICES}
                        if value not in valid_resources:
                            return False
        return True

    def _phase_3_trait_choices_are_valid(self) -> bool:
        return self._trait_choices_are_valid("phase_3", Trait.TraitType.DIS)

    def _phase_4_trait_choices_are_valid(self) -> bool:
        return self._trait_choices_are_valid("phase_4", Trait.TraitType.ADV)

    def _legendary_and_pitiful_attributes_conflict(self) -> bool:
        """Block selecting the same attribute for legendary and pitiful attribute traits."""
        pitiful_choices = self.phase_3_trait_choices().get("dis_pitiful_attribute", {})
        legendary_choices = self.phase_4_trait_choices().get("adv_legendary_attribute", {})
        if not pitiful_choices or not legendary_choices:
            return False
        pitiful_values = {value for values in pitiful_choices.values() for value in values if value}
        legendary_values = {value for values in legendary_choices.values() for value in values if value}
        return bool(pitiful_values & legendary_values)

    def _pitiful_attribute_choices_are_valid(self) -> bool:
        """Validate the special creation rules for Erbaermliche Eigenschaft."""
        pitiful_level = self.phase_3_disadvantages().get("dis_pitiful_attribute", 0)
        if pitiful_level <= 0:
            return True
        race_limits = {
            limit.attribute.short_name: int(limit.min_value)
            for limit in self.race.raceattributelimit_set.select_related("attribute")
        }
        base_attributes = self.phase_1_attributes()
        relevant_choices = self.phase_3_trait_choices().get("dis_pitiful_attribute", {})
        selected_attributes: list[str] = []
        for values in relevant_choices.values():
            for value in values:
                if value:
                    selected_attributes.append(str(value))
        if len(selected_attributes) != pitiful_level:
            return False
        if len(set(selected_attributes)) != len(selected_attributes):
            return False
        for attribute_slug in selected_attributes:
            race_min = race_limits.get(attribute_slug)
            base_value = base_attributes.get(attribute_slug)
            if race_min is None or base_value is None:
                return False
            if base_value != race_min:
                return False
            if base_value - 1 <= 0:
                return False
        return True

    def _fame_resource_choice_is_valid(self) -> bool:
        """Require exactly one fame path choice for the Ruhm advantage."""
        fame_level = self.phase_4_advantages().get("adv_fame", 0)
        if fame_level <= 0:
            return True
        selected_choices = self.phase_4_trait_choices().get("adv_fame", {})
        selected_values = [value for values in selected_choices.values() for value in values if value]
        return len(selected_values) == 1

    def _has_cross_type_trait_exclusion(self) -> bool:
        """Return whether selected advantages and disadvantages exclude each other."""
        selected_advantages = {
            slug for slug, level in self.phase_4_advantages().items()
            if int(level) > 0
        }
        selected_disadvantages = {
            slug for slug, level in self.phase_3_disadvantages().items()
            if int(level) > 0
        }
        if not selected_advantages or not selected_disadvantages:
            return False
        selected_slugs = selected_advantages | selected_disadvantages
        trait_rows = Trait.objects.filter(slug__in=selected_slugs).prefetch_related(
            "exclusions__excluded_trait",
            "excluded_by__trait",
        )
        for trait in trait_rows:
            opposing_selection = selected_disadvantages if trait.trait_type == Trait.TraitType.ADV else selected_advantages
            excluded_slugs = {
                relation.excluded_trait.slug
                for relation in trait.exclusions.all()
            }
            excluded_slugs.update(
                relation.trait.slug
                for relation in trait.excluded_by.all()
            )
            if excluded_slugs & opposing_selection:
                return True
        return False

    def is_phase_1_attribute_in_range(self) -> bool:
        attrs = self.phase_1_attributes()
        limits = self.attribute_min_max_limits()
        if not attrs:
            return False
        for short_name, value in attrs.items():
            if short_name not in limits:
                return False
            if value < limits[short_name]["min"] or value > limits[short_name]["max"]:
                return False
        return True

    def sum_phase_1_attribute_costs(self) -> int:
        attrs = self.phase_1_attributes()
        limits = self.attribute_min_max_limits()
        return sum(
            self.calc_attribute_cost(value, limits[name]["max"])
            for name, value in attrs.items()
            if name in limits
        )

    def validate_phase_1(self) -> bool:
        return self.is_phase_1_attribute_in_range() and (
            self.sum_phase_1_attribute_costs() == self.race.phase_1_points
        )

    # Phase 2
    def phase_2_free_skills(self) -> dict[str, int]:
        """Return free phase-2 base skills that do not consume creation points."""
        return {
            self.FREE_LOCAL_KNOWLEDGE_SKILL_SLUG: self.FREE_LOCAL_KNOWLEDGE_LEVEL,
        }

    def phase_2_skills(self) -> dict[str, int]:
        skills = self.get_phase("phase_2").get("skills", {}) or {}
        normalized = {str(k): max(0, self._to_int(v, 0)) for k, v in skills.items()}
        for slug, free_level in self.phase_2_free_skills().items():
            normalized[slug] = max(free_level, normalized.get(slug, 0))
        return normalized

    def calc_skill_cost(self, target_level: int) -> int:
        if target_level <= 5:
            return target_level
        cost = 5
        for _ in range(6, target_level + 1):
            cost += 2
        return cost

    def calc_phase_2_skill_cost(self, skill_slug: str, target_level: int) -> int:
        """Return the phase-2 purchase cost after subtracting free starting ranks."""
        target = max(0, int(target_level))
        free_level = int(self.phase_2_free_skills().get(str(skill_slug), 0))
        return max(0, self.calc_skill_cost(target) - self.calc_skill_cost(free_level))

    def sum_phase_2_skill_cost(self) -> int:
        return sum(
            self.calc_phase_2_skill_cost(slug, level)
            for slug, level in self.phase_2_skills().items()
        )

    def phase_2_languages(self) -> dict[str, dict]:
        languages = self.get_phase("phase_2").get("languages", {}) or {}
        normalized: dict[str, dict] = {}
        for slug, data in languages.items():
            payload = data or {}
            normalized[str(slug)] = {
                "level": max(0, self._to_int(payload.get("level"), 0)),
                "write": bool(payload.get("write")),
                "mother": bool(payload.get("mother")),
            }
        return normalized

    def calc_language_cost(self, level: int, write: bool, mother: bool) -> int:
        base = 0 if mother else level
        return base + (1 if write else 0)

    def sum_phase_2_language_cost(self) -> int:
        total = 0
        for lang in self.phase_2_languages().values():
            total += self.calc_language_cost(lang["level"], lang["write"], lang["mother"])
        return total

    def validate_phase_2(self) -> bool:
        has_mother_tongue = False
        for slug, data in self.phase_2_languages().items():
            language = Language.objects.filter(slug=slug).first()
            if language is None:
                return False
            level = data["level"]
            if level > language.max_level:
                return False
            mother_level = min(3, language.max_level)
            if data["mother"] and level != mother_level:
                return False
            if data["mother"]:
                has_mother_tongue = True
        if not has_mother_tongue:
            return False
        total = self.sum_phase_2_skill_cost() + self.sum_phase_2_language_cost()
        return total == self.race.phase_2_points

    # Phase 3
    def phase_3_disadvantages(self) -> dict[str, int]:
        disadvantages = self.get_phase("phase_3").get("disadvantages", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in disadvantages.items()}

    def calc_disadvantage_cost(self, slug: str, level: int) -> int:
        trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.DIS).first()
        if trait is None:
            return 0
        if level < trait.min_level or level > trait.max_level:
            return 0
        return trait.cost_for_level(level)

    def sum_phase_3_disadvantage_cost(self) -> int:
        return sum(
            self.calc_disadvantage_cost(slug, level)
            for slug, level in self.phase_3_disadvantages().items()
        )

    def validate_phase_3(self) -> bool:
        for slug, level in self.phase_3_disadvantages().items():
            trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.DIS).first()
            if trait is None:
                return False
            if level < trait.min_level or level > trait.max_level:
                return False
        validator = self._build_trait_validator(Trait.TraitType.DIS, max_disadvantage_cp=self.race.phase_3_points)
        return (
            self.sum_phase_3_disadvantage_cost() <= self.race.phase_3_points
            and self._phase_3_trait_choices_are_valid()
            and self._pitiful_attribute_choices_are_valid()
            and not validator.validate(self.phase_3_disadvantages())
        )

    # Phase 4
    def phase_4_advantages(self) -> dict[str, int]:
        advantages = self.get_phase("phase_4").get("advantages", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in advantages.items()}

    def calc_advantage_cost(self, slug: str, level: int) -> int:
        trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.ADV).first()
        if trait is None:
            return 0
        if level < trait.min_level or level > trait.max_level:
            return 0
        return trait.cost_for_level(level)

    def sum_phase_4_advantages_cost(self) -> int:
        return sum(
            self.calc_advantage_cost(slug, level)
            for slug, level in self.phase_4_advantages().items()
        )

    def calculate_phase_4_budget(self) -> int:
        return self.race.phase_4_points + self.sum_phase_3_disadvantage_cost()

    def calculate_phase_4_advantages_budget(self) -> int:
        return self.sum_phase_3_disadvantage_cost()

    def calculate_phase_4_rest_budget(self) -> int:
        return self.calculate_phase_4_budget() - self.sum_phase_4_advantages_cost()

    def phase_4_attribute_adds(self) -> dict[str, int]:
        adds = self.get_phase("phase_4").get("attribute_adds", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in adds.items()}

    def calc_attribute_add_cost(self, target_level: int, max_value: int) -> int:
        threshold = max_value - 2
        if target_level <= threshold:
            return target_level * 10
        cost = threshold * 10
        for _ in range(threshold + 1, target_level + 1):
            cost += 20
        return cost

    def sum_phase_4_attribute_cost(self) -> int:
        base_attrs = self.phase_1_attributes()
        attr_adds = self.phase_4_attribute_adds()
        limits = self.attribute_min_max_limits()
        total = 0
        for name, add in attr_adds.items():
            if name not in limits:
                continue
            start = base_attrs.get(name, limits[name]["min"])
            end = start + add
            max_value = limits[name]["max"]
            total += self.calc_attribute_add_cost(end, max_value) - self.calc_attribute_add_cost(start, max_value)
        return total

    def phase_4_skill_adds(self) -> dict[str, int]:
        adds = self.get_phase("phase_4").get("skill_adds", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in adds.items()}

    def sum_phase_4_skill_cost(self) -> int:
        base_skills = self.phase_2_skills()
        total = 0
        for slug, add in self.phase_4_skill_adds().items():
            start = base_skills.get(slug, 0)
            end = start + add
            total += self.calc_skill_cost(end) - self.calc_skill_cost(start)
        return total

    def phase_4_language_adds(self) -> dict[str, int]:
        adds = self.get_phase("phase_4").get("language_adds", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in adds.items()}

    def phase_4_language_write_adds(self) -> dict[str, bool]:
        write_adds = self.get_phase("phase_4").get("language_write_adds", {}) or {}
        return {str(k): bool(v) for k, v in write_adds.items() if bool(v)}

    def sum_phase_4_language_adds(self) -> int:
        base_languages = self.phase_2_languages()
        write_adds = self.phase_4_language_write_adds()
        total = 0
        language_slugs = set(base_languages.keys()) | set(self.phase_4_language_adds().keys()) | set(write_adds.keys())
        for slug in language_slugs:
            add = self.phase_4_language_adds().get(slug, 0)
            base = base_languages.get(slug, {})
            start = self._to_int(base.get("level"), 0)
            end = start + add
            base_write = bool(base.get("write"))
            write = base_write or write_adds.get(slug, False)
            mother = bool(base.get("mother"))
            total += self.calc_language_cost(end, write, mother) - self.calc_language_cost(start, base_write, mother)
        return total

    def phase_4_schools(self) -> dict[str, int]:
        schools = self.get_phase("phase_4").get("schools", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in schools.items()}

    def phase_4_weapon_masteries(self) -> list[dict[str, object]]:
        """Return normalized Waffenmeister weapon picks stored during phase 4."""
        rows = self.get_phase("phase_4").get("weapon_masteries", []) or []
        normalized: list[dict[str, object]] = []
        for row in rows:
            payload = row or {}
            weapon_item_id = self._to_int(payload.get("weapon_item_id"), 0)
            first_bonus_kind = str(payload.get("first_bonus_kind") or "").strip().lower()
            if weapon_item_id <= 0:
                continue
            normalized.append(
                {
                    "weapon_item_id": weapon_item_id,
                    "first_bonus_kind": first_bonus_kind,
                }
            )
        return normalized

    def phase_4_weapon_mastery_arcana(self) -> list[dict[str, object]]:
        """Return normalized Waffenmeister arcana picks stored during phase 4."""
        rows = self.get_phase("phase_4").get("weapon_arcana", []) or []
        normalized: list[dict[str, object]] = []
        for row in rows:
            payload = row or {}
            kind = str(payload.get("kind") or "").strip()
            rune_id = self._to_int(payload.get("rune_id"), 0)
            normalized.append(
                {
                    "kind": kind,
                    "rune_id": rune_id,
                }
            )
        return normalized

    def _phase_4_waffenmeister_school(self):
        """Return the Waffenmeister school referenced during creation when present."""
        return School.objects.filter(name__iexact="Waffenmeister").first()

    def _required_weapon_mastery_choice_count(self) -> int:
        """Return how many mandatory Waffenmeister choices the draft currently needs."""
        school = self._phase_4_waffenmeister_school()
        if school is None:
            return 0
        return min(self.phase_4_schools().get(str(school.id), 0), 10)

    def _phase_4_weapon_mastery_choices_are_valid(self) -> bool:
        """Validate concrete weapon and arcana selections for Waffenmeister in phase 4."""
        required_count = self._required_weapon_mastery_choice_count()
        weapon_rows = self.phase_4_weapon_masteries()
        arcana_rows = self.phase_4_weapon_mastery_arcana()
        if required_count <= 0:
            return not weapon_rows and not arcana_rows
        if len(weapon_rows) != required_count or len(arcana_rows) != required_count:
            return False

        seen_weapon_ids: set[int] = set()
        for row in weapon_rows:
            weapon_item_id = int(row.get("weapon_item_id") or 0)
            if weapon_item_id in seen_weapon_ids:
                return False
            if row.get("first_bonus_kind") not in {
                CharacterWeaponMastery.FirstBonusKind.MANEUVER,
                CharacterWeaponMastery.FirstBonusKind.DAMAGE,
            }:
                return False
            if not weapon_mastery_item_definitions().filter(pk=weapon_item_id).exists():
                return False
            seen_weapon_ids.add(weapon_item_id)

        seen_rune_ids: set[int] = set()
        for row in arcana_rows:
            kind = row.get("kind")
            rune_id = int(row.get("rune_id") or 0)
            if kind == CharacterWeaponMasteryArcana.ArcanaKind.BONUS_CAPACITY:
                if rune_id:
                    return False
                continue
            if kind != CharacterWeaponMasteryArcana.ArcanaKind.RUNE:
                return False
            if rune_id in seen_rune_ids or rune_id <= 0:
                return False
            if not Rune.objects.filter(pk=rune_id).exists():
                return False
            seen_rune_ids.add(rune_id)
        return True

    def sum_phase_4_school_cost(self) -> int:
        return sum(level * 8 for level in self.phase_4_schools().values())

    def phase_4_aspects(self) -> dict[str, int]:
        aspects = self.get_phase("phase_4").get("aspects", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in aspects.items()}

    def sum_phase_4_aspect_cost(self) -> int:
        return sum(level * 4 for level in self.phase_4_aspects().values())

    def sum_phase_4_total_cost(self) -> int:
        return (
            self.sum_phase_4_advantages_cost()
            + self.sum_phase_4_attribute_cost()
            + self.sum_phase_4_skill_cost()
            + self.sum_phase_4_language_adds()
            + self.sum_phase_4_school_cost()
            + self.sum_phase_4_aspect_cost()
        )

    def sum_phase_4_rest_cost(self) -> int:
        return (
            self.sum_phase_4_attribute_cost()
            + self.sum_phase_4_skill_cost()
            + self.sum_phase_4_language_adds()
            + self.sum_phase_4_school_cost()
            + self.sum_phase_4_aspect_cost()
        )

    def validate_phase_4(self) -> bool:
        limits = self.attribute_min_max_limits()
        base_attrs = self.phase_1_attributes()
        for name, add in self.phase_4_attribute_adds().items():
            if name not in limits:
                return False
            if base_attrs.get(name, limits[name]["min"]) + add > limits[name]["max"]:
                return False

        for slug, level in self.phase_4_advantages().items():
            trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.ADV).first()
            if trait is None:
                return False
            if level < trait.min_level or level > trait.max_level:
                return False

        base_skills = self.phase_2_skills()
        for slug, add in self.phase_4_skill_adds().items():
            skill = Skill.objects.filter(slug=slug).first()
            if skill is None:
                return False
            if base_skills.get(slug, 0) + add > 10:
                return False

        for slug, add in self.phase_4_language_adds().items():
            language = Language.objects.filter(slug=slug).first()
            if language is None:
                return False
            base_level = self.phase_2_languages().get(slug, {}).get("level", 0)
            if base_level + add > language.max_level:
                return False
        for slug in self.phase_4_language_write_adds().keys():
            language = Language.objects.filter(slug=slug).first()
            if language is None:
                return False
            base_level = self._to_int(self.phase_2_languages().get(slug, {}).get("level"), 0)
            if base_level + self.phase_4_language_adds().get(slug, 0) < 1:
                return False

        for school_id in self.phase_4_schools().keys():
            if not School.objects.filter(pk=self._to_int(school_id, -1)).exists():
                return False

        if self.sum_phase_4_advantages_cost() > self.calculate_phase_4_advantages_budget():
            return False
        validator = self._build_trait_validator(Trait.TraitType.ADV)
        if validator.validate(self.phase_4_advantages()):
            return False
        if not self._phase_4_trait_choices_are_valid():
            return False
        if self._legendary_and_pitiful_attributes_conflict():
            return False
        if not self._fame_resource_choice_is_valid():
            return False
        if self._has_cross_type_trait_exclusion():
            return False
        return (
            self.sum_phase_4_total_cost() <= self.calculate_phase_4_budget()
            and self._phase_4_weapon_mastery_choices_are_valid()
        )

    def _build_trait_validator(self, trait_type: str, *, max_disadvantage_cp: int = 20) -> CharacterBuildValidator:
        """Build a creation-time trait validator from persisted trait definitions."""
        rules: dict[str, TraitBuildRule] = {}
        trait_rows = Trait.objects.filter(trait_type=trait_type).prefetch_related(
            "exclusions__excluded_trait",
            "excluded_by__trait",
        )
        for trait in trait_rows:
            mutually_exclusive = {
                relation.excluded_trait.slug
                for relation in trait.exclusions.all()
                if relation.excluded_trait.trait_type == trait_type
            }
            mutually_exclusive.update(
                relation.trait.slug
                for relation in trait.excluded_by.all()
                if relation.trait.trait_type == trait_type
            )
            rules[trait.slug] = TraitBuildRule(
                slug=trait.slug,
                cp_cost=int(trait.points_per_level) if trait_type == Trait.TraitType.ADV else 0,
                cp_refund=int(trait.points_per_level) if trait_type == Trait.TraitType.DIS else 0,
                cp_cost_by_rank=tuple(trait.cost_curve()) if trait_type == Trait.TraitType.ADV else (),
                cp_refund_by_rank=tuple(trait.cost_curve()) if trait_type == Trait.TraitType.DIS else (),
                min_rank=int(trait.min_level),
                max_rank=int(trait.max_level),
                repeatable=int(trait.max_level) > 1,
                mutually_exclusive_with=tuple(sorted(mutually_exclusive)),
            )
        return CharacterBuildValidator(rules=rules, max_disadvantage_cp=max_disadvantage_cp)

    def _creation_trait_semantic_modifiers(self) -> list:
        """Build semantic trait modifiers for creation-only resolution before CharacterTrait rows exist."""
        modifiers: list = []
        for slug, level in self.phase_3_disadvantages().items():
            if level > 0:
                trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.DIS).first()
                modifiers.extend(
                    build_trait_semantic_modifiers(
                        trait_slug=slug,
                        level=level,
                        trait=trait,
                        allow_persisted_lookup=False,
                    )
                )
        for slug, level in self.phase_4_advantages().items():
            if level > 0:
                trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.ADV).first()
                modifiers.extend(
                    build_trait_semantic_modifiers(
                        trait_slug=slug,
                        level=level,
                        trait=trait,
                        allow_persisted_lookup=False,
                    )
                )
        return modifiers

    def resolve_creation_starting_funds(self) -> int:
        """Resolve one-time starting funds from creation-only economy modifiers."""
        engine = ModifierEngine(modifiers=self._creation_trait_semantic_modifiers())
        return engine.resolve_numeric_total(
            TargetDomain.ECONOMY,
            "starting_funds",
            context={"during_character_creation": True},
        )

    @staticmethod
    def grant_race_starting_items(character):
        starters = character.race.starting_items.select_related("item")

        for starter in starters:
            character_item, created = CharacterItem.objects.get_or_create(
                owner=character,
                item=starter.item,
                defaults={
                    "amount": starter.amount,
                    "quality": starter.quality or starter.item.default_quality,
                    "equipped": True,
                    "equip_locked": True,
                },
            )

            if not created:
                character_item.amount += starter.amount
                character_item.equipped = True
                character_item.equip_locked = True
                character_item.save(update_fields=["amount", "equipped", "equip_locked"])

    def finalize_character(self) -> Character:
        if not (self.validate_phase_1() and self.validate_phase_2() and self.validate_phase_3() and self.validate_phase_4()):
            raise ValueError("Character creation is not valid")

        meta = self.state.get("meta", {}) or {}
        name = (meta.get("name") or "").strip()
        if not name:
            raise ValueError("Character name is required")
        gender = (meta.get("gender") or "").strip() or None

        with transaction.atomic():
            character = Character.objects.create(
                owner=self.draft.owner,
                name=name,
                race=self.race,
                gender=gender,
            )

            limits = self.attribute_min_max_limits()
            attr_adds = self.phase_4_attribute_adds()
            for short_name, base in self.phase_1_attributes().items():
                if short_name not in limits:
                    continue
                final_value = base + attr_adds.get(short_name, 0)
                final_value = min(final_value, limits[short_name]["max"])
                attribute = Attribute.objects.filter(short_name=short_name).first()
                if attribute:
                    CharacterAttribute.objects.create(
                        character=character,
                        attribute=attribute,
                        base_value=final_value,
                    )

            skill_adds = self.phase_4_skill_adds()
            for slug, base in self.phase_2_skills().items():
                skill = Skill.objects.filter(slug=slug).first()
                if skill:
                    CharacterSkill.objects.create(
                        character=character,
                        skill=skill,
                        level=base + skill_adds.get(slug, 0),
                    )

            lang_adds = self.phase_4_language_adds()
            lang_write_adds = self.phase_4_language_write_adds()
            base_languages = self.phase_2_languages()
            language_slugs = set(base_languages.keys()) | set(lang_adds.keys()) | set(lang_write_adds.keys())
            for slug in language_slugs:
                data = base_languages.get(slug, {})
                language = Language.objects.filter(slug=slug).first()
                if not language:
                    continue
                levels = self._to_int(data.get("level"), 0) + lang_adds.get(slug, 0)
                levels = min(levels, language.max_level)
                if levels < 1:
                    continue
                base_write = data.get("write", False)
                CharacterLanguage.objects.create(
                    owner=character,
                    language=language,
                    levels=levels,
                    can_write=bool(base_write or lang_write_adds.get(slug, False)),
                    is_mother_tongue=data.get("mother", False),
                )

            for slug, level in self.phase_3_disadvantages().items():
                trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.DIS).first()
                if trait and level > 0:
                    character_trait = CharacterTrait.objects.create(owner=character, trait=trait, trait_level=level)
                    draft_choice_map = self.phase_3_trait_choices().get(slug, {})
                    if draft_choice_map:
                        definitions = {
                            definition.id: definition
                            for definition in trait.choice_definitions.all()
                        }
                        for definition_id, selected_values in draft_choice_map.items():
                            definition = definitions.get(definition_id)
                            if definition is None:
                                continue
                            for selected_value in selected_values:
                                payload = {
                                    "character_trait": character_trait,
                                    "definition": definition,
                                }
                                if definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE:
                                    payload["selected_attribute"] = Attribute.objects.filter(short_name=selected_value).first()
                                elif definition.target_kind == TraitChoiceDefinition.TargetKind.RESOURCE:
                                    payload["selected_resource"] = selected_value
                                else:
                                    continue
                                if definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE and payload.get("selected_attribute") is None:
                                    continue
                                CharacterTraitChoice.objects.create(**payload)

            for slug, level in self.phase_4_advantages().items():
                trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.ADV).first()
                if trait and level > 0:
                    character_trait = CharacterTrait.objects.create(owner=character, trait=trait, trait_level=level)
                    draft_choice_map = self.phase_4_trait_choices().get(slug, {})
                    if draft_choice_map:
                        definitions = {
                            definition.id: definition
                            for definition in trait.choice_definitions.all()
                        }
                        for definition_id, selected_values in draft_choice_map.items():
                            definition = definitions.get(definition_id)
                            if definition is None:
                                continue
                            for selected_value in selected_values:
                                payload = {
                                    "character_trait": character_trait,
                                    "definition": definition,
                                }
                                if definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE:
                                    payload["selected_attribute"] = Attribute.objects.filter(short_name=selected_value).first()
                                elif definition.target_kind == TraitChoiceDefinition.TargetKind.RESOURCE:
                                    payload["selected_resource"] = selected_value
                                else:
                                    continue
                                if definition.target_kind == TraitChoiceDefinition.TargetKind.ATTRIBUTE and payload.get("selected_attribute") is None:
                                    continue
                                CharacterTraitChoice.objects.create(**payload)

            for school_id, level in self.phase_4_schools().items():
                school = School.objects.filter(pk=self._to_int(school_id, -1)).first()
                if school and level > 0:
                    CharacterSchool.objects.create(character=character, school=school, level=level)

            weapon_master_school = self._phase_4_waffenmeister_school()
            if weapon_master_school and self.phase_4_schools().get(str(weapon_master_school.id), 0) > 0:
                for index, row in enumerate(self.phase_4_weapon_masteries(), start=1):
                    CharacterWeaponMastery.objects.create(
                        character=character,
                        school=weapon_master_school,
                        weapon_item_id=int(row["weapon_item_id"]),
                        pick_order=index,
                        first_bonus_kind=str(row["first_bonus_kind"]),
                    )
                for row in self.phase_4_weapon_mastery_arcana():
                    payload = {
                        "character": character,
                        "school": weapon_master_school,
                        "kind": str(row["kind"]),
                    }
                    if str(row["kind"]) == CharacterWeaponMasteryArcana.ArcanaKind.RUNE:
                        payload["rune_id"] = int(row["rune_id"])
                    CharacterWeaponMasteryArcana.objects.create(**payload)

            starting_funds_delta = self.resolve_creation_starting_funds()
            if starting_funds_delta:
                character.money = max(0, int(character.money) + int(starting_funds_delta))
                character.save(update_fields=["money"])

            self.grant_race_starting_items(character)
            character.current_arcane_power = max(0, int(character.get_engine(refresh=True).calculate_arcane_power()))
            character.save(update_fields=["current_arcane_power"])
            self.draft.delete()

            return character
