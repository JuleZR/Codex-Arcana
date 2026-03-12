"""Rules engine for validating and materializing character creation drafts."""

from __future__ import annotations

from django.db import transaction

from charsheet.models import (
    Attribute,
    Character,
    CharacterAttribute,
    CharacterCreationDraft,
    CharacterLanguage,
    CharacterSchool,
    CharacterSkill,
    CharacterTrait,
    Language,
    School,
    Skill,
    Trait,
)

class CharacterCreationEngine:
    """Rules engine for validating and materializing character creation drafts."""

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
                "max": int(limit.max_value),
            }
            for limit in self.race.raceattributelimit_set.select_related("attribute")
        }

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
    def phase_2_skills(self) -> dict[str, int]:
        skills = self.get_phase("phase_2").get("skills", {}) or {}
        return {str(k): max(0, self._to_int(v, 0)) for k, v in skills.items()}

    def calc_skill_cost(self, target_level: int) -> int:
        if target_level <= 5:
            return target_level
        cost = 5
        for _ in range(6, target_level + 1):
            cost += 2
        return cost

    def sum_phase_2_skill_cost(self) -> int:
        return sum(self.calc_skill_cost(level) for level in self.phase_2_skills().values())

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
        return level * trait.points_per_level

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
        return self.sum_phase_3_disadvantage_cost() <= self.race.phase_3_points

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
        return level * trait.points_per_level

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
        return self.sum_phase_4_total_cost() <= self.calculate_phase_4_budget()

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
                    CharacterTrait.objects.create(owner=character, trait=trait, trait_level=level)

            for slug, level in self.phase_4_advantages().items():
                trait = Trait.objects.filter(slug=slug, trait_type=Trait.TraitType.ADV).first()
                if trait and level > 0:
                    CharacterTrait.objects.create(owner=character, trait=trait, trait_level=level)

            for school_id, level in self.phase_4_schools().items():
                school = School.objects.filter(pk=self._to_int(school_id, -1)).first()
                if school and level > 0:
                    CharacterSchool.objects.create(character=character, school=school, level=level)

            self.draft.delete()
            return character
