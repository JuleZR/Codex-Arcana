"""Rule calculation helpers for character model instances."""

from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict
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
    CharacterSkill, CharacterLanguage, Attribute, 
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

        School levels are counted for types with slug ``"magic"`` and
        ``"divine"``.

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
            "Außer Gefecht", "Koma"
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
        """Calculate VW defense value."""
        return self.calculate_defense(ATTR_GE, ATTR_WA, DEFENSE_VW)
    
    def gw(self) -> int:
        """Calculate GW defense value."""
        return self.calculate_defense(ATTR_INT, ATTR_WILL, DEFENSE_GW)
    
    def sr(self) -> int:
        """Calculate SR defense value."""
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
            
    def current_wound_penalty(self):
        """Return only the active wound penalty value."""
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
        """Return whether wound penalties are currently ignored."""
        return bool(self._resolve_modifiers(WOUND_PENALTY_IGNORE))

    def equipped_armor_items(self) -> QuerySet:
        """Return equipped armor inventory rows for a given character."""

        return (
            CharacterItem.objects.filter(
                owner = self.character,
                equipped = True,
                item__item_type = Item.ItemType.ARMOR
            )
        )
    
    def get_grs(self) -> int:
        """Calculate total armor rating from equipped armor items."""

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
        """Calculate armor burden, honoring armor-penalty ignore effects."""

        if self._resolve_modifiers(ARMOR_PENALTY_IGNORE):
            return 0
        return self.get_grs() // 3

    def get_ms(self) -> int:
        """Calculate minimum strength requirement from current armor rating."""

        return self.get_grs() // 2
    
    def get_dmg_modifier_sum(self, slug: str) -> int:
        """Return combined damage modifiers for the given damage source slug."""
        return self._resolve_modifiers(slug)

    def km_to_coins(self) -> tuple[int, int, int]:
        """Convert copper-based money into gold, silver, and copper tuples."""
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
        self.state = draft.state
    
    def get_phase(self, phase: str) -> dict:
        """Return one phase payload from the persisted draft state."""
        return self.state.get(phase, {})
    
    # Phase 1
    def phase_1_attributes(self) -> dict:
        """Return selected base attributes from phase 1."""
        return self.get_phase("phase_1").get("attributes", {})
    
    def calc_attribute_cost(
        self, target_level: int, max_value: int
        ) -> int:
        """Calculate phase-1 point cost for one attribute target value."""
        
        threshold = max_value - 2
        
        if target_level <= threshold:
            return target_level
        
        cost = threshold
        for _ in range(threshold +1 , target_level +1):
            cost += 2
        
        return cost
       
    def attribute_min_max_limits(self) -> dict[str, dict[str, int]]:
        """Return race-specific min/max limits keyed by attribute short name."""
        return {
            limit.attribute.short_name: {
                "min": limit.min_value,
                "max": limit.max_value,
            }
            for limit in self.race.raceattributelimit_set.select_related("attribute").all()
        }
        
    def is_phase_1_attribute_in_range(self) -> bool:
        """Validate that all phase-1 attributes stay within race limits."""
        attrs = self.phase_1_attributes()
        limits = self.attribute_min_max_limits()
        
        for name, value in attrs.items():
            min_val = limits[name]["min"]
            max_val = limits[name]["max"]
            
            if value < min_val:
                return False
            
            if value > max_val:
                return False
        
        return True
    
    def sum_phase_1_attribute_costs(self) -> int:
        """Sum total point spend for all phase-1 attributes."""
        attrs = self.phase_1_attributes()
        limits = self.attribute_min_max_limits()
        
        return sum(
            self.calc_attribute_cost(value, limits[name][max])
            for name, value in attrs.items()
        )
    
    def validate_phase_1(self) -> bool:
        """Validate phase 1 bounds and exact point budget usage."""
        return (
            self.is_phase_1_attribute_in_range()
            and self.sum_phase_1_attribute_costs() == self.race.phase_1_points
            )
        
    # Phase 2
    def phase_2_skills(self) -> dict:
        """Return selected skill levels from phase 2."""
        phase = self.get_phase("phase_2")
        return phase.get("skills", {})
    
    def calc_skill_cost(self, target_level: int) -> int:
        """Calculate point cost for one skill level target."""
        if target_level <= 5:
            return target_level
        cost = 5
        for _ in range(6, target_level +1):
            cost += 2

        return cost

    def sum_phase_2_skill_cost(self) -> int:
        """Sum total point spend for all phase-2 skills."""
        skills = self.phase_2_skills()
        
        return sum(
            self.calc_skill_cost(level)
            for level in skills.values()
        )
        
    def phase_2_languages(self) -> dict:
        """Return selected languages from phase 2."""
        phase = self.get_phase("phase_2")
        return phase.get("languages", {})
    
    def calc_language_cost(
        self, level: int, write: bool, mother: bool
        ) -> int:
        """Calculate phase-2 language cost including writing and mother tongue."""
        if mother:
            cost = 0
        else:
            cost = level
        
        if write:
            cost += 1
        
        return cost
    
    def sum_phase_2_language_cost(self) -> int:
        """Sum total point spend for all phase-2 languages."""
        languages = self.phase_2_languages()
        
        return sum(
            self.calc_language_cost(
                lang["level"],
                lang.get("write", False),
                lang.get("mother", False),
            )
            for lang in languages.values()
        )
    
    def validate_phase_2(self) -> bool:
        """Validate phase 2 by comparing total spend with race budget."""
        total = self.sum_phase_2_skill_cost + self.sum_phase_2_language_cost
        return total == self.race.phase_2_points
    
    # Phase 3
    def phase_3_disadvantages(self) -> dict:
        """Return selected disadvantages from phase 3."""
        phase = self.get_phase("phase_3")
        return phase.get("disadvantages", {})

    def calc_disadvantage_cost(self, slug: str, level: int) -> int:
        """Calculate disadvantage points granted by one trait selection."""
        trait = Trait.objects.get(slug=slug)
        return level * trait.points_per_level
    
    def sum_phase_3_disadvantage_cost(self) -> int:
        """Sum all disadvantage points from phase 3."""
        disadvantages = self.phase_3_disadvantages()
        
        return sum(
            self.calc_disadvantage_cost(slug, level)
            for slug, level in disadvantages.items()
        )
    
    def validate_phase_3(self) -> bool:
        """Validate that phase-3 disadvantage points stay within limit."""
        return self.sum_phase_3_disadvantage_cost <= self.race.phase_3_points
    
    # Phase 4
    def phase_4_advantages(self) -> dict:
        """Return selected advantages from phase 4."""
        phase = self.get_phase("phase_4")
        return phase.get("advantages", {})
    
    def calc_advantage_cost(self, slug: str, level: int) -> int:
        """Calculate point cost for one advantage selection."""
        trait = Trait.objects.get(slug=slug)
        return level * trait.points_per_level
    
    def sum_phase_4_advantages_cost(self) -> int:
        """Sum total point spend for phase-4 advantages."""
        advantages = self.phase_4_advantages()
        
        return sum(
            self.calc_advantage_cost(
                self.calc_advantage_cost(slug, level)
                for slug, level in advantages.items()
            )
        )
        
    def validate_advantages(self) -> bool:
        """Validate that bought advantages do not exceed disadvantage points."""
        return (self.sum_phase_4_advantages_cost() 
                <= self.sum_phase_3_disadvantage_cost()
        )
        
    def calculate_phase_4_budget(self) -> int:
        """Calculate available phase-4 budget including disadvantage gain."""
        return (
            self.race.phase_4_points
            + self.sum_phase_3_disadvantage_cost()
        )
    
    def phase_4_attribute_adds(self) -> dict:
        """Return attribute increases selected in phase 4."""
        phase = self.get_phase("phase_4")
        return phase.get("attribute_adds", {})
    
    def calc_attribute_add_cost(self, target_level: int, max_value: int) -> int:
        """Calculate cumulative cost for raised attributes in phase 4."""
        threshold = max_value - 2

        if target_level <= threshold:
            return target_level * 10

        cost = threshold * 10
        for _ in range(threshold + 1, target_level + 1):
            cost += 20

        return cost 
    
    def sum_phase_4_attribute_cost(self) -> int:
        """Sum incremental cost of all phase-4 attribute increases."""
        base_attrs = self.phase_1_attributes()
        attr_adds = self.phase_4_attribute_adds()
        limits = self.attribute_min_max_limits()
        
        total: int = 0
        
        for name, add in attr_adds.items():
            start = base_attrs.get(name, 0)
            end = start + add
            max_value = limits[name]["max"]
            
            total += (
                self.calc_attribute_add_cost(end, max_value)
                - self.calc_attribute_add_cost(start, max_value)
            )
        
        return total
    
    def phase_4_skill_adds(self) -> dict:
        """Return skill increases selected in phase 4."""
        phase = self.get_phase("phase_4")
        return phase.get("skill_adds", {})
    
    def sum_phase_4_skill_cost(self) -> int:
        """Sum incremental cost of all phase-4 skill increases."""
        base_skills = self.phase_2_skills()
        skill_adds = self.phase_4_skill_adds()
        
        total: int = 0
        
        for name, add in skill_adds.items():
            start = base_skills.get(name, 0)
            end = start + add
            
            total += (
                self.calc_skill_cost(end)
                - self.calc_skill_cost(start)
            )
        return total
    
    def phase_4_language_adds(self) -> dict:
        """Return language increases selected in phase 4."""
        phase = self.get_phase("phase_4")
        return phase.get("language", {})
    
    def sum_phase_4_language_adds(self) -> int:
        """Sum incremental cost of all phase-4 language increases."""
        base_languages = self.phase_2_languages()
        languages_add = self.phase_4_language_adds()
        
        total: int = 0
        
        for name, add in languages_add.items():
            base: dict = base_languages.get(name, {})
        
            start = base.get("level", 0)
            end = start + add
        
            write = base.get("write", False)
            mother = base.get("mother", False)
        
            total += (
                self.calc_language_cost(end, write, mother)
                - self.calc_advantage_cost(start, write, mother)
            )

        return total
    
    def phase_4_schools(self) -> dict:
        """Return school level purchases selected in phase 4."""
        phase = self.get_phase("phase_4")
        return phase.get("schools", {})
    
    def sum_phase_4_school_cost(self) -> int:
        """Sum cost for phase-4 school levels."""
        schools = self.phase_4_schools()

        return sum(
            level * 8
            for level in schools.values()
        )
        
    def phase_4_aspects(self) -> dict:
        """Return aspect level purchases selected in phase 4."""
        phase = self.get_phase("phase_4")
        return phase.get("aspects", {})
    
    def sum_phase_4_aspect_cost(self) -> int:
        """Sum cost for phase-4 aspect levels."""
        aspects = self.phase_4_aspects()

        return sum(
            level * 4
            for level in aspects.values()
        )
        
    def sum_phase_4_total_cost(self) -> int:
        """Return combined phase-4 spend across all configurable categories."""
        return (
            self.sum_phase_4_advantages_cost()
            + self.sum_phase_4_attribute_cost()
            + self.sum_phase_4_skill_cost()
            + self.sum_phase_4_language_adds()
            + self.sum_phase_4_school_cost()
            + self.sum_phase_4_aspect_cost()
        )
    
    def validate_phase_4(self) -> bool:
        """Validate phase-4 spends against budget and advantage rules."""
        total_cost = self.sum_phase_4_total_cost()
        budget = self.calculate_phase_4_budget()

        advantages_ok = (
            self.sum_phase_4_advantages_cost()
            <= self.sum_phase_3_disadvantage_cost()
        )

        budget_ok = total_cost <= budget

        return advantages_ok and budget_ok
    
    def finalize_character(self) -> Character:
        """Create and persist the final character from a valid draft."""

        if not (
            self.validate_phase_1()
            and self.validate_phase_2()
            and self.validate_phase_3()
            and self.validate_phase_4()
        ):
            raise ValueError("Character creation is not valid")

        character = Character.objects.create(
            owner=self.draft.owner,
            race=self.race
        )

        # Write Attributes
        attrs = self.phase_1_attributes()

        for name, value in attrs.items():
            attribute = Attribute.objects.get(short_name=name)

            CharacterAttribute.objects.create(
                character=character,
                attribute=attribute,
                base_value=value
            )
        
        # Write Skills
        skills = self.phase_2_skills()

        for slug, level in skills.items():
            skill = Skill.objects.get(slug=slug)

            CharacterSkill.objects.create(
                character=character,
                skill=skill,
                level=level
            )
            
        # Wirte Languages
        languages = self.phase_2_languages()

        for slug, data in languages.items():
            language = Language.objects.get(slug=slug)

            CharacterLanguage.objects.create(
                character=character,
                language=language,
                level=data["level"],
                can_write=data.get("write", False),
                is_mother_tongue=data.get("mother", False)
            )
        
        # Write disadvantages
        disadvantages = self.phase_3_disadvantages()

        for slug, level in disadvantages.items():
            trait = Trait.objects.get(slug=slug)

            CharacterTrait.objects.create(
                character=character,
                trait=trait,
                trait_level=level
            )
        
        # Write advantages
        advantages = self.phase_4_advantages()

        for slug, level in advantages.items():
            trait = Trait.objects.get(slug=slug)

            CharacterTrait.objects.create(
                character=character,
                trait=trait,
                trait_level=level
            )
            
        # Wirte Schools
        schools = self.phase_4_schools()

        for slug, level in schools.items():
            school = School.objects.get(slug=slug)

            CharacterSchool.objects.create(
                character=character,
                school=school,
                level=level
            )
        
        self.draft.delete()

        return character
