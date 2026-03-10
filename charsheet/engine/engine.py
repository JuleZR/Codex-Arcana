"""Rule calculation helpers for character model instances."""

from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict
from django.db import transaction
from django.db.models import QuerySet
from charsheet.constants import (
    ATTR_GE, ATTR_WILL, ATTR_KON, 
    ATTR_INT, ATTR_ST, ATTR_WA,
    INITIATIVE, ARCANE_POWER,
    WOUND_PENALTY_IGNORE, WOUND_STAGE,
    DEFENSE_GW, DEFENSE_SR, DEFENSE_VW,
    ARMOR_PENALTY_IGNORE
)
from charsheet.models import (
    Modifier, CharacterItem, Item, CharacterTrait,
    CharacterSchool, Technique, Trait,
    CharacterCreationDraft, CharacterAttribute,
    CharacterSkill, CharacterLanguage, Character, Attribute, 
    Skill, School, Language
    )


if TYPE_CHECKING:
    from charsheet.models import Character, ProgressionRule


class SkillInfo(TypedDict):
    """Typed representation of character skill metadata."""

    level: int
    category: str
    attribute: str


class SkillBreakdown(TypedDict):
    """Typed representation of one skill calculation breakdown."""

    skill_slug: str
    level: int
    base_attribute: str
    attribute_value: int
    attribute_modifier: int
    base: int
    modifiers: int
    total: int


class SkillError(TypedDict):
    """Typed error payload for unresolved skills."""

    skill_slug: str
    error: str


class ActiveProgressionRule(TypedDict):
    """Typed representation of an active progression rule entry."""

    school_slug: str
    school_level: int
    rule: ProgressionRule


class CharacterEngine:
    """Calculate derived character values from persisted model data."""

    def __init__(self, character: Character) -> None:
        self.character = character

    def attributes(self) -> dict[str, int]:
        """Return base attributes keyed by attribute short name.

        Returns:
            dict[str, int]: Mapping like ``{"ST": 7, "DEX": 5}``.
        """
        qs = (
            self.character.characterattribute_set
            .select_related("attribute")
        )
        return {
            ca.attribute.short_name: ca.base_value
            for ca in qs
        }

    def skills(self) -> dict[str, SkillInfo]:
        """Return skill metadata keyed by skill slug.

        Returns:
            dict[str, dict]: Metadata per skill with keys ``level``,
            ``category``, and ``attribute``.
        """
        qs = (
            self.character.characterskill_set
            .select_related("skill", "skill__category")
        )
        return {
            cs.skill.slug: {
                "level": cs.level,
                "category": cs.skill.category.slug,
                "attribute": cs.skill.attribute.short_name,
            }
            for cs in qs
        }
        
    def attribute_modifier(self, short_name: str) -> int:
        """Return the modifier for one attribute.

        Note:
            The formula is currently a placeholder and should be replaced
            with the Arcane Codex rule.

        Args:
            short_name: Attribute short name (for example ``"ST"`` or ``"CHA"``).

        Returns:
            int: Calculated modifier value.
        """
        value = self.attributes().get(short_name, 0)
        
        return value -5
    
    def skill_total(self, skill_slug: str) -> int:
        """Calculate skill total from level and attribute modifier.

        Args:
            skill_slug: Skill identifier.

        Returns:
            int: ``skill level + base attribute modifier``, or ``0`` if missing.
        """
        skills = self.skills()
        if skill_slug not in skills:
            return 0

        info = skills[skill_slug]
        level = int(info["level"])
        attr_short = info["attribute"]

        mod = int(self.attribute_modifier(attr_short))
        return level + mod
    
    def skill_breakdown(self, skill_slug: str) -> SkillBreakdown | SkillError:
        """Return a detailed breakdown for one skill calculation.

        Args:
            skill_slug: Skill identifier.

        Returns:
            dict: Breakdown with level, attribute, base, modifiers, and total.
            Returns an error payload if the skill is not found.
        """
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
        """Calculate base skill value without external modifiers.

        Args:
            skill_slug: Skill identifier.

        Returns:
            int: ``skill level + base attribute modifier``, or ``0`` if missing.
        """
        skills = self.skills()
        if skill_slug not in skills:
            return 0
    
        info = skills[skill_slug]
        level = int(info["level"])
        attr_short = info["attribute"]
        mod = int(self.attribute_modifier(attr_short))
    
        return level + mod

    def _resolve_modifiers(self, slug: str) -> int:
        """Resolve and sum all active modifiers that match a target slug."""
        def _active_source_for_character(modifier: Modifier) -> bool:
            """Check whether a modifier source is currently active for the character."""
            source = modifier.source
            if source is None:
                return False

            # Trait-bound modifiers only apply if the character owns the trait.
            if isinstance(source, Trait):
                if not self.character.charactertrait_set.filter(trait=source).exists():
                    return False

            # Technique-bound modifiers only apply if the character has the
            # corresponding school at least at the technique level.
            if isinstance(source, Technique):
                if not self.character.schools.filter(
                    school=source.school,
                    level__gte=source.level,
                ).exists():
                    return False

            # Optional explicit school gate (e.g. "only from school level 9").
            if modifier.min_school_level is not None:
                gate_school = modifier.scale_school
                if gate_school is None and isinstance(source, Technique):
                    gate_school = source.school

                if gate_school is None:
                    return False

                try:
                    owned_school = self.character.schools.get(school=gate_school)
                except CharacterSchool.DoesNotExist:
                    return False

                if owned_school.level < modifier.min_school_level:
                    return False

            return True

        total = 0
        mods = Modifier.objects.filter(
            target_kind=Modifier.TargetKind.STAT,
            target_slug=slug,
        ).select_related("source_content_type")
        
        for mod in mods:
            if not _active_source_for_character(mod):
                continue

            if mod.mode == Modifier.Mode.FLAT:
                total += mod.value
                continue
            if mod.mode == Modifier.Mode.SCALED:
                if mod.scale_source == Modifier.ScaleSource.TRAIT_LVL:
                    trait = mod.source
                    try:
                        owned = self.character.charactertrait_set.get(trait=trait)
                    except CharacterTrait.DoesNotExist:
                        continue

                    level = owned.trait_level
                    value = (level * mod.value * mod.mul) // mod.div
                    total += value

            if mod.scale_source == Modifier.ScaleSource.SCHOOL_LEVEL:
                school = mod.scale_school
                try:
                    owned = self.character.schools.get(school=mod.scale_school)
                except CharacterSchool.DoesNotExist:
                    continue
                
                level = owned.level
                value = (level * mod.value) // mod.div
                
                total += value

        return total

    def _skill_modifiers(self, skill_slug: str) -> int:
        """Collect and sum all external modifiers for one skill.

        Args:
            skill_slug: Skill identifier.

        Returns:
            int: Summed modifier value including wound penalty.
        """
        skill_mods = self._resolve_modifiers(skill_slug)
        #TODO: Add other modifiers
        modifier = [
            self.current_wound_penalty(),
            - self.get_bel(),
            + skill_mods,
            ]
        
        return sum(modifier)

    def skill_total(self, skill_slug: str) -> int:
        """Calculate final skill total as base plus external modifiers.

        Args:
            skill_slug: Skill identifier.

        Returns:
            int: Final skill total.
        """
        return int(self._skill_base(skill_slug)) + int(self._skill_modifiers(skill_slug))

    def active_progression_rules(self) -> list[ActiveProgressionRule]:
        """Return progression rules active for the character's current schools.

        Returns:
            list[dict]: Each entry contains ``school_slug``, ``school_level``,
            and ``rule``.
        """
        from charsheet.models import CharacterSchool, ProgressionRule
    
        result: list[ActiveProgressionRule] = []
    
        character_schools = (
            CharacterSchool.objects
            .filter(character=self.character)
            .select_related("school", "school__type")
        )
    
        for cs in character_schools:
            school_type = cs.school.school_type
            level = cs.level
    
            rules = ProgressionRule.objects.filter(
                school_type=school_type,
                min_level__lte=level,
            )
    
            for rule in rules:
                result.append({
                    "school_name": cs.school.name,
                    "school_level": level,
                    "rule": rule,
                })
    
        return result
    
    def calculate_initiative(self) -> int:
        """Calculate initiative.

        Returns:
            int: ``DEX modifier + all stat modifiers for 'initiative'``.
        """
        ge_mod = self.attribute_modifier(ATTR_GE)
        misc =  self._resolve_modifiers(INITIATIVE)
        misc += self.current_wound_penalty()
        
        return ge_mod + misc
    
    def calculate_arcane_power(self) -> int:
        """Calculate arcane power from WILL, schools, and stat modifiers.

        Note:
            The current implementation sums levels from all owned schools.

        Returns:
            int: Arcane power total.
        """
        willpower = self.attributes().get(ATTR_WILL, 0)
        school_levels = sum(cs.level for cs 
                            in self.character.schools
                            .select_related("school__type").all()
                            )
        misc = self._resolve_modifiers(ARCANE_POWER)

        return willpower + school_levels + misc
    
    def calculate_potential(self) -> int:
        """Calculate potential from WILL.

        Returns:
            int: Integer floor of ``WILL / 2``.
        """
        willpower = self.attributes().get(ATTR_WILL, 0)
        return willpower // 2
    
    def wound_thresholds(self) -> dict[int, tuple[str, int]]:
        """Build wound threshold map with labels and penalties.

        Returns:
            dict[int, tuple[str, int]]: Mapping of threshold value to
            ``(stage_name, penalty)``.
        """
        constitution: int = self.attributes().get(ATTR_KON, 0)
        additional_stages = self._resolve_modifiers(WOUND_STAGE)
        amount_threshold: int = 6 + additional_stages
        
        stage_numbers = [n*constitution for n in range(1, amount_threshold + 1)]
        stage_names = [
            "Angeschlagen", "Verletzt",
            "Verwundet", "Schwer verwundet",
            "AuÃŸer Gefecht", "Koma"
        ]
        stage_penalty = [0, -2, -4, -6, 0, 0]
        
        missing = max(0, len(stage_numbers) - len(stage_names))
        stages = ["-"] * missing + stage_names
        penalties = [0] * missing + stage_penalty
        
        return {
            n: (s, p) for n, s, p in zip(stage_numbers, stages, penalties)
        }

    def calculate_defense(self, mod1: str, mod2: str, slug:str) -> int:
        """Calculate a defense value from two attributes and stat modifiers.

        Args:
            mod1: First attribute short name.
            mod2: Second attribute short name.
            slug: Stat modifier slug to include.

        Returns:
            int: ``14 + modifier(mod1) + modifier(mod2) + misc``.
        """
        mod1_val = self.attribute_modifier(mod1)
        mod2_val = self.attribute_modifier(mod2)
        misc =  self._resolve_modifiers(slug)
        return 14 + mod1_val + mod2_val + misc
    
    def vw(self) -> int:
        """Calculate ``VW`` defense value.

        Returns:
            int: Computed ``VW`` defense.
        """
        return self.calculate_defense(ATTR_GE, ATTR_WA, DEFENSE_VW)
    
    def gw(self) -> int:
        """Calculate ``GW`` defense value.

        Returns:
            int: Computed ``GW`` defense.
        """
        return self.calculate_defense(ATTR_INT, ATTR_WILL, DEFENSE_GW)
    
    def sr(self) -> int:
        """Calculate ``SR`` defense value.

        Returns:
            int: Computed ``SR`` defense.
        """
        return self.calculate_defense(ATTR_ST, ATTR_KON, DEFENSE_SR)

    def current_wound_stage(self) -> tuple[str, int | None]:
        """Return current wound stage label and its penalty.

        Returns:
            tuple[str, int | None]: ``(stage_name, penalty)`` for current damage.
            If no wound stage is active yet, returns ``("-", None)``.
        """
        wound_dict = self.wound_thresholds()
        t_numbers = sorted(wound_dict.keys())

        if not t_numbers:
            return ("-", None)

        damage = self.character.current_damage

        if damage < t_numbers[0]:
            return ("-", None)

        if damage > t_numbers[-1]:
            return ("Tod", 0)

        current_stage: tuple[str, int | None] = ("-", None)
        for key in t_numbers:
            if damage >= key:
                stage_name, penalty = wound_dict[key]
                current_stage = (stage_name, penalty)
            else:
                break

        return current_stage
            
    def current_wound_penalty(self) -> int:
        """Return only the active wound penalty value.

        Returns:
            int: Active wound penalty, or ``0`` if no penalty applies.
        """
        penalty = self.current_wound_stage()[1]
        if penalty is None:
            return 0
        if self.is_wound_penalty_ignored():
            return 0
        return penalty

    def current_wound_penalty_raw(self) -> int:
        """Return active wound penalty without applying ignore effects."""
        penalty = self.current_wound_stage()[1]
        if penalty is None:
            return 0
        return penalty

    def is_wound_penalty_ignored(self) -> bool:
        """Return whether wound penalties are currently ignored.

        Returns:
            bool: ``True`` when an ignore modifier is active, else ``False``.
        """
        return bool(self._resolve_modifiers(WOUND_PENALTY_IGNORE))

    def equipped_armor_items(self) -> QuerySet:
        """Return equipped armor inventory rows for this character.

        Returns:
            QuerySet: Equipped `CharacterItem` entries with armor items.
        """

        return (
            CharacterItem.objects.filter(
                owner = self.character,
                equipped = True,
                item__item_type = Item.ItemType.ARMOR
            )
        )
    
    def get_grs(self) -> int:
        """Calculate total armor rating from equipped armor items.

        Returns:
            int: Combined armor value (``GRS``).
        """

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
        """Calculate armor burden, honoring ignore effects.

        Returns:
            int: Armor burden (``BEL``), or ``0`` if ignored.
        """

        if self._resolve_modifiers(ARMOR_PENALTY_IGNORE):
            return 0
        return self.get_grs() // 3

    def get_ms(self) -> int:
        """Calculate minimum strength requirement from current armor rating.

        Returns:
            int: Minimum strength requirement (``MS``).
        """

        return self.get_grs() // 2
    
    def get_dmg_modifier_sum(self, slug: str) -> int:
        """Return combined damage modifiers for the given damage source.

        Args:
            slug: Damage source slug.

        Returns:
            int: Summed modifier value for that damage source.
        """
        return self._resolve_modifiers(slug) + self.attribute_modifier(ATTR_ST)
        

    def km_to_coins(self) -> tuple[int, int, int]:
        """Convert copper-based money into coin denominations.

        Returns:
            tuple[int, int, int]: ``(gold, silver, copper)``.
        """
        player_km = self.character.money
        
        gm = player_km // 100
        sm = (player_km % 100) // 10
        km = player_km % 10
        
        return gm, sm, km

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
