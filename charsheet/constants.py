# STAT Slugs
INITIATIVE = "initiative"
ARCANE_POWER = "arcane_power"
WOUND_STAGE = "wound_stage"
WOUND_PENALTY_IGNORE = "wound_penalty_ignore"
ARMOR_PENALTY_IGNORE = "armor_penalty_ignore"
DEFENSE_VW = "vw"
DEFENSE_GW = "gw"
DEFENSE_SR = "sr"
DEFENSE_RS = "rs"

STAT_SLUG_CHOICES = [
    (INITIATIVE, "Initiative"),
    (ARCANE_POWER, "Arcane Power"),
    (WOUND_STAGE, "Wound Stage"),
    (WOUND_PENALTY_IGNORE, "Ignore Wound Penalty"),
    (ARMOR_PENALTY_IGNORE, "Ignore Armor Penalty"),
    (DEFENSE_VW, "VW"),
    (DEFENSE_GW, "GW"),
    (DEFENSE_SR, "SR"),
    (DEFENSE_RS, "RS"),
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
    DEFENSE_RS,
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
ATTR_SPEC = "spz."

ATTRIBUTE_CODE_CHOICES = [
    (ATTR_GE, "Geschicklichkeit"),
    (ATTR_WA, "Wahrnehmung"),
    (ATTR_INT, "Intelligenz"),
    (ATTR_WILL, "Willenskraft"),
    (ATTR_ST, "Stärke"),
    (ATTR_KON, "Konstitution"),
    (ATTR_CHA, "Charisma"),
    (ATTR_SPEC, "Spezial")
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

# SIZE CLASSES
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

# ITEM QUALITES
QUALITY_WRETCHED = "wretched"
QUALITY_VERY_POOR = "very_poor"
QUALITY_POOR = "poor"
QUALITY_COMMON = "common"
QUALITY_FINE = "fine"
QUALITY_EXCELLENT = "excellent"
QUALITY_LEGENDARY = "legendary"

QUALITY_CHOICES = [
    (QUALITY_WRETCHED, "Extrem schlechte Qualität"),
    (QUALITY_VERY_POOR, "Sehr schlechte Qualität"),
    (QUALITY_POOR, "Schlechte Qualität"),
    (QUALITY_COMMON, "Normale Qualität"),
    (QUALITY_FINE, "Gute Qualität"),
    (QUALITY_EXCELLENT, "Exzellente Qualität"),
    (QUALITY_LEGENDARY, "Legendäre Qualität")
]

QUALITY_PRICE_MODS = {
    QUALITY_WRETCHED: 0.25,
    QUALITY_VERY_POOR: 0.5,
    QUALITY_POOR: 0.75,
    QUALITY_COMMON: 1,
    QUALITY_FINE: 2,
    QUALITY_EXCELLENT: 5,
    QUALITY_LEGENDARY: 20,
}

QUALITY_STEPS_FROM_COMMON = {
    QUALITY_WRETCHED: -3,
    QUALITY_VERY_POOR: -2,
    QUALITY_POOR: -1,
    QUALITY_COMMON: 0,
    QUALITY_FINE: 1,
    QUALITY_EXCELLENT: 2,
    QUALITY_LEGENDARY: 3,
}

QUALITY_BEL_MODS = {
    QUALITY_WRETCHED: 3,
    QUALITY_VERY_POOR: 2,
    QUALITY_POOR: 1,
    QUALITY_COMMON: 0,
    QUALITY_FINE: 0,
    QUALITY_EXCELLENT: -1,
    QUALITY_LEGENDARY: -2,
}

QUALITY_COLOR_MAP = {
    QUALITY_WRETCHED: "#DD2828",
    QUALITY_VERY_POOR: "#7A7A7A",
    QUALITY_POOR: "#000000",
    QUALITY_COMMON: "#33CC33",
    QUALITY_FINE: "#0000FF",
    QUALITY_EXCELLENT: "#CC00CC",
    QUALITY_LEGENDARY: "#FF9933",
}

# Wield Modes
ONE_HANDED = "1h"
TWO_HANDED = "2h"
VERSATILE = "vh"

WIELD_MODES = (
    (ONE_HANDED, "Einhändig"),
    (TWO_HANDED, "Zweihändig"),
    (VERSATILE, "Ein- und Zweihändig"),
)

# Weapon Damage Types
NUMB = "B"
DEADLY = "T"

DAMAGE_TYPE_CHOICES = (
    (NUMB, "B"),
    (DEADLY, "T"),
)

# Weapon Symbols
MOUNTED_TWO_HANDED = "mounted_two_handed"
FIRST_ROUND_INIT = "first_round_init"
CHAIN_FUMBLE = "chain_fumble"
REQUIRES_DEX = "requires_dex"
CAN_ENTANGLE = "can_entangle"
DRAG_TARGET = "drag_target"
CALTROP_EFFECT = "caltrop_effect"
EXPLODE_ON_FUMBLE = "explode_on_fumble"
SET_AGAINST_CHARGE = "set_against_charge"
PARRY_BONUS = "parry_bonus"
UNARMED_DAMAGE = "unarmed_damage"

WEAPON_SYMBOL_CHOICES = (
    (MOUNTED_TWO_HANDED, "-"),
    (FIRST_ROUND_INIT, "I"),
    (CHAIN_FUMBLE, "$"),
    (REQUIRES_DEX, "(Ge)"),
    (CAN_ENTANGLE, "^"),
    (DRAG_TARGET, "^^"),
    (CALTROP_EFFECT, "+"),
    (EXPLODE_ON_FUMBLE, "#"),
    (SET_AGAINST_CHARGE, "→"),
    (PARRY_BONUS, "P"),
    (UNARMED_DAMAGE, "*"),
)
