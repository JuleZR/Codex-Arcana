"""Rule calculation helpers for character model instances."""

from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict
from django.db.models import QuerySet
from charsheet.models import (
    Modifier, CharacterItem, Item, CharacterTrait,
    CharacterSchool
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
        total = 0
        mods = Modifier.objects.filter(
            target_kind=Modifier.TargetKind.STAT,
            target_slug=slug,
        ).select_related("source_content_type")
        
        for mod in mods:
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
                    "school_slug": cs.school.slug,
                    "school_level": level,
                    "rule": rule,
                })
    
        return result
    
    def calculate_initiative(self) -> int:
        """Calculate initiative.

        Returns:
            int: ``DEX modifier + all stat modifiers for 'initiative'``.
        """
        ge_mod = self.attribute_modifier("GE")
        misc =  self._resolve_modifiers('initiative')
        misc += self.current_wound_penalty()
        
        return ge_mod + misc
    
    def calculate_arcane_power(self) -> int:
        """Calculate arcane power from WILL, schools, and stat modifiers.

        School levels are counted for types with slug ``"magic"`` and
        ``"divine"``.

        Returns:
            int: Arcane power total.
        """
        willpower = self.attributes().get("WILL", 0)
        school_levels = sum(cs.level for cs 
                            in self.character.schools
                            .select_related("school__type").all()
                            )
        misc = self._resolve_modifiers("arcane_power")

        return willpower + school_levels + misc
    
    def calculate_potential(self) -> int:
        """Calculate potential from WILL.

        Returns:
            int: Integer floor of ``WILL / 2``.
        """
        willpower = self.attributes().get("WILL", 0)
        return willpower // 2
    
    def wound_thresholds(self) -> dict[int, tuple[str, int]]:
        """Build wound threshold map with labels and penalties.

        Returns:
            dict[int, tuple[str, int]]: Mapping of threshold value to
            ``(stage_name, penalty)``.
        """
        constitution: int = self.attributes().get("CON", 0)
        additional_stages = self._resolve_modifiers("wound_stage")
        amount_threshold: int = 6 + additional_stages
        
        ignore_stages = self._resolve_modifiers("wound_penalty_ignore")
        
        stage_numbers = [n*constitution for n in range(1, amount_threshold + 1)]
        stage_names = [
            "Angeschlagen", "Verletzt",
            "Verwundet", "Schwer verwundet",
            "Außer Gefecht", "Koma"
        ]
        stage_penalty = [0, -2, -4, -6, 0, 0]
        
        if ignore_stages:
            stage_penalty = [0, 0, 0, 0, 0, 0]
        
        missing = max(0, len(stage_numbers) - len(stage_names))
        stages = [""] * missing + stage_names
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
        return self.calculate_defense("GE", "WA", "vw")
    
    def gw(self) -> int:
        """Calculate GW defense value."""
        return self.calculate_defense("INT", "WILL", "gw")
    
    def sr(self) -> int:
        """Calculate SR defense value."""
        return self.calculate_defense("ST", "KON", "sr")

    def current_wound_stage(self) -> tuple[str, int]:
       """Return current wound stage label and its penalty.

       Returns:
           tuple[str, int]: ``(stage_name, penalty)`` for current damage.
       """
       wound_dict = self.wound_thresholds()
       
       t_numbers = [t for t in wound_dict.keys()]
       if self.character.current_damage >= t_numbers[-1]:
           return ("tot", 0)
       
       for key in t_numbers:
           if self.character.current_damage < key:
               return wound_dict[key]
           
    def current_wound_penalty(self):
        """Return only the active wound penalty value."""
        return self.current_wound_stage()[1]

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

        if self._resolve_modifiers("armor_penalty_ignore"):
            return 0
        return self.get_grs() // 3

    def get_ms(self) -> int:
        """Calculate minimum strength requirement from current armor rating."""

        return self.get_grs() // 2
    
    def get_dmg_modifier_sum(self, slug: str) -> int:
        return self._resolve_modifiers(slug)
