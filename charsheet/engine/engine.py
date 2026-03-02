"""
CharacterEngine handles all rule-related calculations
based on the Character model data.
"""

class CharacterEngine:
    """Run character rules calculations using data from a Character model."""

    def __init__(self, character):
        """Initialize the engine with a character instance."""
        self.character = character

    def attributes(self):
        """Return a mapping of attribute short names to base values."""
        qs = (
            self.character.characterattribute_set
            .select_related("attribute")
        )
        return {
            ca.attribute.short_name: ca.base_value
            for ca in qs
        }

    def skills(self):
        """Return skill metadata keyed by skill slug for this character."""
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
        """
        Return the modifier for a given attribute.

        IMPORTANT:
        This method currently contains a placeholder formula.
        Replace it with your Arcane Codex modifier rule.

        Parameters:
            short_name (str): Attribute short name (e.g. "ST", "CHA").

        Returns:
            int: The calculated modifier.
        """
        value = self.attributes().get(short_name, 0)
        
        return value -5
    
    def skill_total(self, skill_slug: str) -> int:
        """
        Calculate the total value of a skill.

        The total is defined as:
            skill level + base attribute modifier
        """
        skills = self.skills()
        if skill_slug not in skills:
            return 0

        info = skills[skill_slug]
        level = int(info["level"])
        attr_short = info["attribute"]

        mod = int(self.attribute_modifier(attr_short))
        return level + mod
    
    def skill_breakdown(self, skill_slug: str) -> dict:
        """
        Explain how a skill total is calculated (base + modifiers).
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
        """
        Calculate the base value of a skill (without external modifiers).
    
        Base is defined as:
            skill level + base attribute modifier
    
        Returns 0 if the skill is not present on the character.
        """
        skills = self.skills()
        if skill_slug not in skills:
            return 0
    
        info = skills[skill_slug]
        level = int(info["level"])
        attr_short = info["attribute"]
        mod = int(self.attribute_modifier(attr_short))
    
        return level + mod


    def _skill_modifiers(self, skill_slug: str) -> int:
        """
        Calculate additional modifiers from external sources.

        Intended sources (later):
          - race bonuses (single skills or skill groups/categories)
          - school/technique bonuses
          - traits, equipment, situational effects

        For now: returns 0.
        """
        return 0


    def skill_total(self, skill_slug: str) -> int:
        """
        Calculate the final total of a skill.

        Total is defined as:
            base skill value + external modifiers
        """
        return int(self._skill_base(skill_slug)) + int(self._skill_modifiers(skill_slug))

    def active_progression_rules(self) -> list[dict]:
        """
        Return all progression rules currently active for the character,
        based on their schools and school levels.
    
        Returns:
            list of dicts with:
                - school_slug
                - school_level
                - rule (ProgressionRule instance)
        """
        from charsheet.models import CharacterSchool, ProgressionRule
    
        result = []
    
        character_schools = (
            CharacterSchool.objects
            .filter(character=self.character)
            .select_related("school", "school__school_type")
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