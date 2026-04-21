"""Reusable admin help text and label configuration."""

ATTRIBUTE_CHOICE_HELP = {
    "short_name": "Pick the canonical attribute code used by the rules and sheet.",
}

SKILL_CATEGORY_CHOICE_HELP = {
    "slug": "Pick the fixed category key. The German labels are the actual category buckets used in the game.",
}

SIZE_CLASS_HELP = {
    "size_class": "Size class scale: S/F/W/K are smaller than average, M is average human size, G/R/Gi/Kol are progressively larger.",
}

CHARACTER_CHOICE_HELP = {
    "gender": "Display value only. Use the option that should appear on the character sheet.",
}

SCHOOL_TYPE_CHOICE_HELP = {
    "slug": "Magieschule = arkane Schulen, Klerikaler Aspekt = goettliche Schulen, Kampfschule = Kampfschulen.",
}

PROGRESSION_RULE_CHOICE_HELP = {
    "grant_kind": (
        "Technique Choice = grants selectable techniques, Spell Choice = grants "
        "selectable spells, Aspect Access = unlocks an aspect, Aspect Spell = "
        "grants a spell from an aspect."
    ),
}

MODIFIER_CHOICE_HELP = {
    "target_kind": (
        "Skill = one specific skill, Skill Category = one entire skill category, "
        "Stat = a derived stat, Item/Item Category = an item or item category, "
        "Specialization = a school-bound specialization, Other Entity = any other "
        "game entity. Persisted legacy rows are translated into the central "
        "modifier architecture; semantic trait effects live there as well."
    ),
    "target_choice_definition": (
        "Optional choice definition link. If set, the modifier target kind must "
        "match the choice definition target kind."
    ),
    "target_race_choice_definition": (
        "Optional race choice definition link. If set, the modifier target kind "
        "must match the race choice definition target kind."
    ),
    "mode": (
        "Flat = fixed value, Scaled = value is calculated from another source. "
        "Persisted rows are translated into typed central-engine modifiers before "
        "they are resolved."
    ),
    "scale_source": (
        "School level = scales with a school level, Fame total = scales with total "
        "fame rank, Trait level = scales with the source trait level, Skill level "
        "= uses the learned ranks of one skill, Skill total = uses the fully "
        "resolved value of one skill. Skill-based scaling is limited to stat "
        "targets."
    ),
    "scale_skill": "Required for skill-based scaling or caps. Choose which skill provides the learned level or full total.",
    "round_mode": "Floor = round down after division, Ceil = round up after division.",
    "cap_mode": "None = no cap, Min = do not go below the cap value, Max = do not go above the cap value.",
    "cap_source": "Uses the same source types as scaling, but only to define the cap value. Skill-based caps also require scale_skill.",
    "target_slug": (
        "For stats and categories, enter the rule key here. For Skill/Category "
        "targets, you can use the related object field instead."
    ),
}

TECHNIQUE_CHOICE_HELP = {
    "technique_type": "Passive = persistent effect, Active = technique used actively, Situational = only relevant in specific situations.",
    "acquisition_type": "Automatic = learned directly, Choice = selected from multiple options.",
    "support_level": (
        "Automated = the engine evaluates the rule fully, Partially Automated = "
        "parts are structured and evaluable, Manual (Rule Text Only) = rule text "
        "only with no automatic calculation."
    ),
    "choice_target_kind": (
        "Simple mode for a single persistent choice. For multiple separate "
        "decisions, use the inline choice definitions instead."
    ),
    "choice_group": "Pure UI/import metadata. This group does not create any rule mechanics.",
    "specialization_slot_grants": (
        "How many specialization slots become available once the technique is "
        "actually learned. Techniques that are only available do not count."
    ),
    "action_type": "Action = standard action, Reaction = reaction, Free = free action, Preparation = preparation.",
    "usage_type": "At Will = unlimited use, Per Scene = once per scene, Per Combat = once per combat, Per Day = once per day.",
    "choice_block": "Optional choice block if the technique belongs to a real rulebook choice point.",
    "selection_notes": "Short plain-language note describing what must be selected or observed for this technique.",
    "target_choice_definition": (
        "Optional target definition if this technique explicitly points to a "
        "specific choice definition of another technique."
    ),
}

TECHNIQUE_CHOICE_BLOCK_HELP = {
    "name": "Short name of the choice block so the rulebook location can be found again in the admin.",
    "min_choices": "How many techniques from this block must be learned at minimum.",
    "max_choices": "How many techniques from this block may be learned at most.",
}

TECHNIQUE_CHOICE_DEFINITION_HELP = {
    "target_kind": "Defines which kind of target this technique decision stores persistently.",
    "min_choices": "How many selections must be stored for this single decision at minimum.",
    "max_choices": "How many selections may be stored for this single decision at maximum.",
    "allowed_skill_category": "Optional filter restricting skill choices to one specific skill category.",
    "allowed_skill_family": "Optional filter restricting skill choices to one specific skill family.",
}

RACE_CHOICE_DEFINITION_HELP = {
    "target_kind": "Defines which kind of target this race decision stores persistently.",
    "min_choices": "How many selections must be stored for this single race decision at minimum.",
    "max_choices": "How many selections may be stored for this single race decision at maximum.",
    "allowed_skill_category": "Optional filter restricting skill choices to one specific skill category.",
    "allowed_skill_family": "Optional filter restricting skill choices to one specific skill family.",
}

SPECIALIZATION_CHOICE_HELP = {
    "support_level": (
        "Automated = the engine evaluates the rule fully, Partially Automated = "
        "parts are structured and evaluable, Manual (Rule Text Only) = rule text "
        "only with no automatic calculation."
    ),
}

SCHOOL_ADMIN_LABELS = {
    "type": "School Type",
    "panel_symbol": "Panel Symbol",
    "description": "Description",
}

RACE_ADMIN_LABELS = {
    "size_class": "SizeClass",
}

MODIFIER_LABELS = {
    "target_choice_definition": "Technique Choice Definition",
    "target_race_choice_definition": "Race Choice Definition",
}

RACE_CHOICE_DEFINITION_LABELS = {
    "race": "Race",
}

TECHNIQUE_LABELS = {
    "school": "School",
    "path": "Path",
    "level": "Level",
    "choice_block": "Choice Block",
    "technique_type": "Technique Type",
    "acquisition_type": "Acquisition Type",
    "support_level": "Rule Support",
    "is_choice_placeholder": "Choice Placeholder",
    "choice_group": "Organization Group",
    "selection_notes": "Selection Notes",
    "choice_target_kind": "Choice Target",
    "choice_limit": "Choice Count",
    "target_choice_definition": "Target Choice Definition",
    "choice_bonus_value": "Fixed Bonus",
    "specialization_slot_grants": "Specialization Slots",
    "action_type": "Action Type",
    "usage_type": "Usage Type",
    "activation_cost": "Cost",
    "activation_cost_resource": "Cost Resource",
    "description": "Rule Text / Description",
}

TECHNIQUE_CHOICE_BLOCK_LABELS = {
    "school": "School",
    "path": "Path",
    "level": "Level",
    "name": "Name",
    "sort_order": "Sort Order",
    "min_choices": "Min. Choices",
    "max_choices": "Max. Choices",
    "description": "Rule Text / Description",
}

SPECIALIZATION_LABELS = {
    "school": "School",
    "name": "Name",
    "slug": "Key",
    "support_level": "Rule Support",
    "sort_order": "Sort Order",
    "is_active": "Active",
    "description": "Rule Text / Description",
}

ITEM_CHOICE_HELP = {
    "item_type": (
        "Armor = armor, Shield = shield, Weapon = weapon, Consumable = consumable "
        "item, Ammo = ammunition, Misc = miscellaneous item."
    ),
    "default_quality": "Default item quality; used when no inventory-specific quality has been set.",
    "stackable": "Armor, shields, and weapons are validated as non-stackable.",
    "is_consumable": "Marks items that are actively consumed on use; separate from stackability.",
}

WEAPON_CHOICE_HELP = {
    "damage_source": "Optional finer-grained damage source such as slash, thrust, projectile, or elemental source for modifier resolution.",
    "damage_type": "Deadly = lethal physical damage, Stun = non-lethal damage.",
    "wield_mode": "1H = one-handed only, 2H = two-handed only, V/H = versatile with separate two-handed damage values.",
    "h2_dice_amount": "Required for 2H and versatile weapons.",
    "h2_dice_faces": "Required for 2H and versatile weapons.",
    "h2_flat_bonus": "Optional flat bonus for the two-handed profile.",
    "flags": "Optional weapon symbols or traits such as rulebook keywords.",
}

SHIELD_CHOICE_HELP = {
    "encumbrance": "Shield encumbrance.",
    "min_st": "Minimum strength required to use the shield.",
}

TRAIT_CHOICE_HELP = {
    "trait_type": (
        "Advantage = beneficial trait, Disadvantage = drawback or penalty trait. "
        "Traits can now also project semantic effects such as flags, capabilities, "
        "social markers, or narrative constraints in the central modifier layer."
    ),
    "description": (
        "Keep the full rules text here. The central modifier layer may add "
        "structured automation on top of this text, but it does not replace the "
        "complete rule wording."
    ),
}
