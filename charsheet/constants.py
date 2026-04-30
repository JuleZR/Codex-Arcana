# STAT Slugs
INITIATIVE = "initiative"
ARCANE_POWER = "arcane_power"
POTENTIAL = "potential"
WOUND_STAGE = "wound_stage"
WOUND_PENALTY_IGNORE = "wound_penalty_ignore"
WOUND_PENALTY_MOD = "wound_penalty_mod"
ARMOR_PENALTY_IGNORE = "armor_penalty_ignore"
DEFENSE_VW = "vw"
DEFENSE_GW = "gw"
DEFENSE_SR = "sr"
DEFENSE_RS = "rs"
MELEE_MANEUVERS = "melee_maneuvers"

STAT_SLUG_CHOICES = [
    (INITIATIVE, "Initiative"),
    (ARCANE_POWER, "Arkane Macht"),
    (POTENTIAL, "Potenzial"),
    (WOUND_STAGE, "Wundstufe"),
    (WOUND_PENALTY_IGNORE, "Wundmalus ignorieren"),
    (WOUND_PENALTY_MOD, "Wundmalus ver\u00e4ndern"),
    (ARMOR_PENALTY_IGNORE, "Belastung ignorieren"),
    (DEFENSE_VW, "VW"),
    (DEFENSE_GW, "GW"),
    (DEFENSE_SR, "SR"),
    (DEFENSE_RS, "RS"),
    (MELEE_MANEUVERS, "Manöver mit dieser Waffe"),
]

VALID_STAT_SLUGS = {
    INITIATIVE,
    ARCANE_POWER,
    POTENTIAL,
    WOUND_STAGE,
    WOUND_PENALTY_IGNORE,
    WOUND_PENALTY_MOD,
    ARMOR_PENALTY_IGNORE,
    DEFENSE_VW,
    DEFENSE_GW,
    DEFENSE_SR,
    DEFENSE_RS,
    MELEE_MANEUVERS,
}

SOURCE_ITEM_RUNE = "item_rune"
RUNE_CRAFTER_LEVEL = "rune_crafter_level"

# School Slugs
SCHOOL_ARCANE = "arcane"
SCHOOL_DIVINE = "divine"
SCHOOL_COMBAT = "combat"

# Backward-compatible aliases used throughout the existing codebase and tests.
SCHOOL_MAGIC = SCHOOL_ARCANE

SCHOOL_TYPE_CHOICES = [
    (SCHOOL_ARCANE, "Magieschule"),
    (SCHOOL_DIVINE, "Klerikale Schule"),
    (SCHOOL_COMBAT, "Kampfschule"),
]

VALID_SCHOOL_TYPE_SLUGS = {
    SCHOOL_ARCANE,
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
LEGENDARY_ATTRIBUTE_TRAIT_SLUG = "adv_legendary_attribute"

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

PROFICIENCY_GROUP_FOREIGN_LANGUAGES = "foreign_languages"
RESOURCE_KEY_CHOICES = [
    ("personal_fame_point", "Persönliche Ruhmpunkte"),
    ("personal_fame_rank", "Persönlicher Rang"),
    ("artefact_rank", "Artefaktrang"),
    ("sacrifice_rank", "Opferrang"),
]

PROFICIENCY_GROUP_CHOICES = [
    (SKILL_FINE_MOTOR, "Feinmotorische Fertigkeiten"),
    (SKILL_GROSS_MOTOR, "Grobmotorische Fertigkeiten"),
    (SKILL_SOCIAL, "Soziale Fertigkeiten"),
    (SKILL_KNOWLEDGE, "Wissensfertigkeiten"),
    (SKILL_COMBAT, "Waffenfertigkeiten"),
    (PROFICIENCY_GROUP_FOREIGN_LANGUAGES, "Sprachen (außer Muttersprache)"),
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

# Weapon Types
WEAPON_TYPE_UNSPECIFIED = ""
WEAPON_TYPE_LONGSWORD = "longsword"
WEAPON_TYPE_TWO_HANDED_SWORD = "two_handed_sword"
WEAPON_TYPE_SHORTSWORD = "shortsword"
WEAPON_TYPE_CURVED_SWORD = "curved_sword"
WEAPON_TYPE_RAPIER = "rapier"
WEAPON_TYPE_DAGGER = "dagger"
WEAPON_TYPE_AXE = "axe"
WEAPON_TYPE_TWO_HANDED_AXE = "two_handed_axe"
WEAPON_TYPE_HAMMER = "hammer"
WEAPON_TYPE_TWO_HANDED_HAMMER = "two_handed_hammer"
WEAPON_TYPE_MACE = "mace"
WEAPON_TYPE_FLAIL = "flail"
WEAPON_TYPE_SPEAR = "spear"
WEAPON_TYPE_LANCE = "lance"
WEAPON_TYPE_POLEARM = "polearm"
WEAPON_TYPE_STAFF = "staff"
WEAPON_TYPE_CHAIN = "chain"
WEAPON_TYPE_WHIP = "whip"
WEAPON_TYPE_FIST = "fist"
WEAPON_TYPE_BOW = "bow"
WEAPON_TYPE_CROSSBOW = "crossbow"
WEAPON_TYPE_BLOWGUN = "blowgun"
WEAPON_TYPE_TRAP = "trap"
WEAPON_TYPE_SPECIAL = "special"

WEAPON_TYPE_CHOICES = (
    (WEAPON_TYPE_UNSPECIFIED, "Nicht festgelegt"),
    (WEAPON_TYPE_LONGSWORD, "Langschwert"),
    (WEAPON_TYPE_TWO_HANDED_SWORD, "Zweihandschwert"),
    (WEAPON_TYPE_SHORTSWORD, "Kurzschwert"),
    (WEAPON_TYPE_CURVED_SWORD, "Krummschwert"),
    (WEAPON_TYPE_RAPIER, "Degen / Rapier"),
    (WEAPON_TYPE_DAGGER, "Dolch"),
    (WEAPON_TYPE_AXE, "Axt"),
    (WEAPON_TYPE_TWO_HANDED_AXE, "Zweihandaxt"),
    (WEAPON_TYPE_HAMMER, "Hammer"),
    (WEAPON_TYPE_TWO_HANDED_HAMMER, "Zweihandhammer"),
    (WEAPON_TYPE_MACE, "Kolben / Keule"),
    (WEAPON_TYPE_FLAIL, "Flegel / Geissel"),
    (WEAPON_TYPE_SPEAR, "Speer"),
    (WEAPON_TYPE_LANCE, "Lanze"),
    (WEAPON_TYPE_POLEARM, "Stangenwaffe"),
    (WEAPON_TYPE_STAFF, "Stab"),
    (WEAPON_TYPE_CHAIN, "Kettenwaffe"),
    (WEAPON_TYPE_WHIP, "Peitsche"),
    (WEAPON_TYPE_FIST, "Faustwaffe / Unbewaffnet"),
    (WEAPON_TYPE_BOW, "Bogen"),
    (WEAPON_TYPE_CROSSBOW, "Armbrust"),
    (WEAPON_TYPE_BLOWGUN, "Blasrohr"),
    (WEAPON_TYPE_TRAP, "Netz / Falle"),
    (WEAPON_TYPE_SPECIAL, "Sonderwaffe"),
)

WEAPON_TYPE_LABELS = dict(WEAPON_TYPE_CHOICES)

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

# Canonical attribute display order shared across context builders and views
ATTRIBUTE_ORDER = [
    ("ST", "Stärke (St)"),
    ("KON", "Konstitution (Kon)"),
    ("GE", "Geschick (Ge)"),
    ("WA", "Wahrnehmung (Wa)"),
    ("INT", "Intelligenz (Int)"),
    ("WILL", "Willenskraft (Will)"),
    ("CHA", "Charisma (Cha)"),
]

def is_allowed_trait_attribute_choice(trait_slug: str | None, attribute_slug: str | None) -> bool:
    """Return whether one attribute can be selected for a given trait choice."""
    if str(trait_slug or "") == LEGENDARY_ATTRIBUTE_TRAIT_SLUG and str(attribute_slug or "") == ATTR_SPEC:
        return False
    return True


# Modifier system constants used by TraitSemanticEffect and the modifier engine

TARGET_DOMAIN_CHOICES = (
    ("skill", "skill"),
    ("skill_category", "skill_category"),
    ("language", "language"),
    ("proficiency_group", "proficiency_group"),
    ("trait", "trait"),
    ("attribute", "attribute"),
    ("attribute_cap", "attribute_cap"),
    ("derived_stat", "derived_stat"),
    ("resource", "resource"),
    ("resistance", "resistance"),
    ("movement", "movement"),
    ("combat", "combat"),
    ("perception", "perception"),
    ("economy", "economy"),
    ("social", "social"),
    ("rule_flag", "rule_flag"),
    ("capability", "capability"),
    ("behavior", "behavior"),
    ("tag", "tag"),
    ("metadata", "metadata"),
    ("item", "item"),
    ("item_category", "item_category"),
    ("specialization", "specialization"),
    ("entity", "entity"),
)

MODIFIER_OPERATOR_CHOICES = (
    ("flat_add", "flat_add"),
    ("flat_sub", "flat_sub"),
    ("multiply", "multiply"),
    ("override", "override"),
    ("min_value", "min_value"),
    ("max_value", "max_value"),
    ("set_flag", "set_flag"),
    ("unset_flag", "unset_flag"),
    ("add_tag", "add_tag"),
    ("remove_tag", "remove_tag"),
    ("grant_capability", "grant_capability"),
    ("remove_capability", "remove_capability"),
    ("grant_immunity", "grant_immunity"),
    ("grant_vulnerability", "grant_vulnerability"),
    ("change_resource_cap", "change_resource_cap"),
    ("change_starting_funds", "change_starting_funds"),
    ("change_appearance_class", "change_appearance_class"),
    ("change_social_status", "change_social_status"),
    ("reroll_grant", "reroll_grant"),
    ("reroll_forbid", "reroll_forbid"),
    ("repeat_action_allowed", "repeat_action_allowed"),
    ("action_cost_change", "action_cost_change"),
    ("conditional_bonus", "conditional_bonus"),
    ("conditional_penalty", "conditional_penalty"),
)

STACK_BEHAVIOR_CHOICES = (
    ("stack", "stack"),
    ("highest", "highest"),
    ("lowest", "lowest"),
    ("override", "override"),
    ("unique_by_source", "unique_by_source"),
)

MODIFIER_VISIBILITY_CHOICES = (
    ("public", "public"),
    ("internal", "internal"),
    ("story", "story"),
)
