# STAT Slugs

INITIATIVE = "initiative"
ARCANE_POWER = "arcane_power"
WOUND_STAGE = "wound_stage"
WOUND_PENALTY_IGNORE = "wound_penalty_ignore"
ARMOR_PENALTY_IGNORE = "armor_penalty_ignore"
DEFENSE_VW = "vw"
DEFENSE_GW = "gw"
DEFENSE_SR = "sr"

STAT_SLUG_CHOICES = [
    (INITIATIVE, "Initiative"),
    (ARCANE_POWER, "Arcane Power"),
    (WOUND_STAGE, "Wound Stage"),
    (WOUND_PENALTY_IGNORE, "Ignore Wound Penalty"),
    (ARMOR_PENALTY_IGNORE, "Ignore Armor Penalty"),
    (DEFENSE_VW, "VW"),
    (DEFENSE_GW, "GW"),
    (DEFENSE_SR, "SR"),
]

VALID_STAT_SLUGS = {
    INITIATIVE,
    ARCANE_POWER,
    WOUND_STAGE,
    WOUND_PENALTY_IGNORE,
    ARMOR_PENALTY_IGNORE,
    DEFENSE_VW,
    DEFENSE_GW,
    DEFENSE_SR,
}

# School SLugs

SCHOOL_MAGIC = "magic"
SCHOOL_DIVINE = "divine"
SCHOOL_COMBAT = "combat"

SCHOOL_TYPE_CHOICES = [
    (SCHOOL_MAGIC, "Magic"),
    (SCHOOL_DIVINE, "Divine"),
    (SCHOOL_COMBAT, "Combat"),
]

VALID_SCHOOL_TYPE_SLUGS = {
    SCHOOL_MAGIC,
    SCHOOL_DIVINE,
    SCHOOL_COMBAT,
}

# Attribute Codes

ATTR_GE = "GE"
ATTR_WA = "WA"
ATTR_INT = "INT"
ATTR_WILL = "WILL"
ATTR_ST = "ST"
ATTR_KON = "KON"
ATTR_CHA = "CHA"

ATTRIBUTE_CODE_CHOICES = [
    (ATTR_GE, "Geschicklichkeit"),
    (ATTR_WA, "Wahrnehmung"),
    (ATTR_INT, "Intelligenz"),
    (ATTR_WILL, "Willenskraft"),
    (ATTR_ST, "Stärke"),
    (ATTR_KON, "Konstitution"),
    (ATTR_CHA, "Charisma")
]

# Skill Category Slugs

SKILL_FINE_MOTOR = "skill_fine_motor"
SKILL_GROSS_MOTOR = "skill_gross_motor"
SKILL_CRAFT = "skill_craft"
SKILL_SOCIAL = "skill_social"
SKILL_COMBAT = "skill_combat"
SKILL_KNOWLEDGE = "skill_knowledge"

SKILL_CATEGORY_CHOICES = [
    (SKILL_FINE_MOTOR, "Feinmotorische Fertigkeiten"),
    (SKILL_GROSS_MOTOR, "Grobmotorische Fertigkeiten"),
    (SKILL_CRAFT, "Handwerk"),
    (SKILL_SOCIAL, "Soziale Fertigkeiten"),
    (SKILL_COMBAT, "Waffenfertigkeiten"),
    (SKILL_KNOWLEDGE, "Wissensfertigkeiten"),
]

GK_VERYFINE = "S"
GK_FINE = "F"
GK_TINY = "W"
GK_SMALL = "K"
GK_AVERAGE = "M"
GK_LARGE = "G"
GK_HUGE = "R"
GK_GIANT = "Gi"
GK_COLOSSAL = "Kol"

GK_CHOICES = [
    (GK_VERYFINE, GK_VERYFINE),
    (GK_FINE, GK_FINE),
    (GK_TINY, GK_TINY),
    (GK_SMALL, GK_SMALL),
    (GK_AVERAGE, GK_AVERAGE),
    (GK_LARGE, GK_LARGE),
    (GK_HUGE, GK_HUGE),
    (GK_GIANT, GK_GIANT),
    (GK_COLOSSAL, GK_COLOSSAL),
]

GK_MODS = {
    GK_VERYFINE: 8,
    GK_FINE: 4,
    GK_TINY: 2,
    GK_SMALL: 1,
    GK_AVERAGE: 0,
    GK_LARGE: -1,
    GK_HUGE: -2,
    GK_GIANT: -4,
    GK_COLOSSAL: -8,
}