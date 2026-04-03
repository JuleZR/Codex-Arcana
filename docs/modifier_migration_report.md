# Legacy Modifier Migration Report

## Inventory

- Legacy modifier rows: 39
- Target kinds:
  - `category`: 1
  - `skill`: 23
  - `stat`: 15
- Source models:
  - `race`: 24
  - `technique`: 13
  - `trait`: 2

## Relationships

- `outgoing` `charsheet.Modifier.source_content_type` -> `contenttypes.ContentType` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_skill` -> `charsheet.Skill` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_skill_category` -> `charsheet.SkillCategory` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_item` -> `charsheet.Item` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_specialization` -> `charsheet.Specialization` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_choice_definition` -> `charsheet.TechniqueChoiceDefinition` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_race_choice_definition` -> `charsheet.RaceChoiceDefinition` (ForeignKey)
- `outgoing` `charsheet.Modifier.target_content_type` -> `contenttypes.ContentType` (ForeignKey)
- `outgoing` `charsheet.Modifier.scale_school` -> `charsheet.School` (ForeignKey)
- `outgoing` `charsheet.Modifier.scale_skill` -> `charsheet.Skill` (ForeignKey)
- `outgoing` `charsheet.Modifier.source` -> `-` (GenericForeignKey)
- `outgoing` `charsheet.Modifier.target` -> `-` (GenericForeignKey)
- `incoming` `contenttypes.ContentType.modifier_source_relations` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `contenttypes.ContentType.modifier_target_relations` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.SkillCategory.modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.Skill.modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.Skill.scale_modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.Item.modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.School.scale_modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.Specialization.modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.TechniqueChoiceDefinition.targeting_modifiers` -> `charsheet.Modifier` (ManyToOneRel)
- `incoming` `charsheet.RaceChoiceDefinition.targeting_modifiers` -> `charsheet.Modifier` (ManyToOneRel)

## Code Readers

- `charsheet/engine/character_engine.py`: Loads persisted legacy rows as source data and routes productive resolution through ModifierEngine.
- `charsheet/engine/character_combat.py`: Consumes CharacterEngine outputs whose modifier portions now come from ModifierEngine.
- `charsheet/engine/character_equipment.py`: Consumes CharacterEngine outputs whose modifier portions now come from ModifierEngine.
- `charsheet/sheet_context.py`: Displays values resolved by CharacterEngine; no direct modifier math.
- `charsheet/admin.py`: Maintains legacy modifier rows and choice-definition targeting.

## Used Target Combinations

| target_kind | target_identifier | mode | scale_source | count |
| --- | --- | --- | --- | ---: |
| `category` | `skill_combat` | `flat` | `-` | 1 |
| `skill` | `craft_mining` | `flat` | `-` | 1 |
| `skill` | `dmg_slash` | `flat` | `-` | 1 |
| `skill` | `race_choice_definition:1` | `flat` | `-` | 1 |
| `skill` | `race_choice_definition:2` | `flat` | `-` | 1 |
| `skill` | `skill_animal_handling` | `flat` | `-` | 1 |
| `skill` | `skill_attention` | `flat` | `-` | 1 |
| `skill` | `skill_empathy` | `flat` | `-` | 1 |
| `skill` | `skill_estimate` | `flat` | `-` | 1 |
| `skill` | `skill_etiquette` | `flat` | `-` | 1 |
| `skill` | `skill_fly` | `flat` | `-` | 1 |
| `skill` | `skill_hide` | `flat` | `-` | 3 |
| `skill` | `skill_impress` | `flat` | `-` | 1 |
| `skill` | `skill_orientation` | `flat` | `-` | 1 |
| `skill` | `skill_riding` | `flat` | `-` | 1 |
| `skill` | `skill_sneak` | `flat` | `-` | 3 |
| `skill` | `skill_survival` | `flat` | `-` | 2 |
| `skill` | `skill_tracking` | `flat` | `-` | 1 |
| `skill` | `technique_choice_definition:1` | `scaled` | `school_level` | 1 |
| `stat` | `armor_penalty_ignore` | `flat` | `-` | 1 |
| `stat` | `dmg_blunt` | `scaled` | `school_level` | 1 |
| `stat` | `dmg_chain` | `scaled` | `school_level` | 1 |
| `stat` | `dmg_slash` | `scaled` | `school_level` | 1 |
| `stat` | `gw` | `flat` | `-` | 1 |
| `stat` | `gw` | `scaled` | `school_level` | 1 |
| `stat` | `initiative` | `scaled` | `skill_total` | 1 |
| `stat` | `initiative` | `scaled` | `trait_level` | 1 |
| `stat` | `rs` | `flat` | `-` | 1 |
| `stat` | `shield_penalty_ignore` | `flat` | `-` | 1 |
| `stat` | `sr` | `flat` | `-` | 1 |
| `stat` | `vw` | `flat` | `-` | 1 |
| `stat` | `vw` | `scaled` | `school_level` | 1 |
| `stat` | `wound_penalty_ignore` | `flat` | `-` | 1 |
| `stat` | `wound_stage` | `flat` | `-` | 1 |

## Mapping Table

| legacy_id | previous meaning | new type | target domain | strategy | confidence | review | risk | note |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | technique#3 applies scaled value 0 to stat:gw, scale=school_level | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 2 | technique#5 applies scaled value 1 to stat:dmg_slash, scale=school_level | `CombatModifier` | `combat` | `auto_typed` | `medium` | `False` | `medium` | Damage-style stat slug migrated as combat modifier. |
| 4 | technique#5 applies scaled value 1 to stat:dmg_chain, scale=school_level | `CombatModifier` | `combat` | `auto_typed` | `medium` | `False` | `medium` | Damage-style stat slug migrated as combat modifier. |
| 5 | technique#5 applies scaled value 1 to stat:dmg_blunt, scale=school_level | `CombatModifier` | `combat` | `auto_typed` | `medium` | `False` | `medium` | Damage-style stat slug migrated as combat modifier. |
| 6 | technique#6 applies flat value 1 to stat:wound_stage | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 7 | technique#8 applies flat value 1 to stat:armor_penalty_ignore | `RuleFlagModifier` | `rule_flag` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 8 | technique#8 applies flat value 1 to stat:shield_penalty_ignore | `RuleFlagModifier` | `rule_flag` | `auto_typed` | `high` | `False` | `low` | Flag migrated automatically into the central rule-flag resolution. |
| 9 | technique#9 applies flat value 1 to stat:wound_penalty_ignore | `RuleFlagModifier` | `rule_flag` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 10 | trait#10 applies flat value -2 to skill:skill_empathy | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 11 | trait#16 applies scaled value 1 to stat:initiative, scale=trait_level | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 12 | race#2 applies flat value 15 to stat:gw | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 13 | race#2 applies flat value 15 to skill:dmg_slash | `CombatModifier` | `combat` | `auto_typed` | `medium` | `False` | `medium` | Legacy target_kind=skill uses a damage slug. Migrated as combat modifier for backward-compatible combat resolution. |
| 14 | technique#61 applies scaled value 1 to skill:technique_choice_definition:1, scale=school_level | `SkillModifier` | `skill` | `auto_typed` | `medium` | `False` | `medium` | Choice-bound skill modifier; migrated with dynamic selection binding metadata. |
| 15 | technique#63 applies scaled value 1 to stat:vw, scale=school_level | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 16 | race#3 applies flat value 2 to skill:skill_survival | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 17 | race#4 applies flat value 2 to skill:craft_mining | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 18 | race#4 applies flat value 2 to skill:skill_orientation | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 19 | race#4 applies flat value 2 to skill:skill_estimate | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 20 | race#5 applies flat value 2 to skill:skill_fly | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 21 | race#5 applies flat value 2 to skill:skill_sneak | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 22 | race#5 applies flat value 4 to skill:skill_hide | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 23 | race#5 applies flat value 2 to category:skill_combat | `SkillModifier` | `skill_category` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 24 | race#5 applies flat value 2 to stat:vw | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 25 | race#6 applies flat value 2 to skill:skill_hide | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 26 | race#6 applies flat value 1 to skill:skill_sneak | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 27 | technique#95 applies flat value 1 to stat:rs | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 28 | race#8 applies flat value 2 to skill:skill_survival | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 29 | technique#99 applies flat value 2 to stat:sr | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 30 | race#9 applies flat value 2 to skill:skill_attention | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 31 | race#9 applies flat value 2 to skill:skill_riding | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 32 | race#9 applies flat value 2 to skill:skill_tracking | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 33 | race#9 applies flat value 0 to skill:skill_animal_handling | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 34 | race#10 applies flat value 2 to skill:skill_impress | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 35 | race#10 applies flat value 2 to skill:skill_etiquette | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 36 | race#10 applies flat value 2 to skill:race_choice_definition:1 | `SkillModifier` | `skill` | `auto_typed` | `medium` | `False` | `medium` | Choice-bound skill modifier; migrated with dynamic selection binding metadata. |
| 37 | race#10 applies flat value 0 to skill:race_choice_definition:2 | `SkillModifier` | `skill` | `auto_typed` | `medium` | `False` | `medium` | Choice-bound skill modifier; migrated with dynamic selection binding metadata. |
| 38 | race#12 applies flat value -2 to skill:skill_hide | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 39 | race#12 applies flat value -1 to skill:skill_sneak | `SkillModifier` | `skill` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |
| 40 | technique#113 applies scaled value 1 to stat:initiative, scale=skill_total | `DerivedStatModifier` | `derived_stat` | `auto_typed` | `high` | `False` | `low` | Mapped automatically from legacy modifier semantics. |

## Character Compare: Kuro Kamui (41)

### Derived Outputs

| key | legacy | new | matches |
| --- | ---: | ---: | --- |
| `initiative` | 2 | 2 | `True` |
| `arcane_power` | 15 | 15 | `True` |
| `vw` | 14 | 14 | `True` |
| `gw` | 16 | 16 | `True` |
| `sr` | 17 | 17 | `True` |
| `rs` | 0 | 0 | `True` |

### Debug Compare Log

| domain | key | legacy | new | classification | matches |
| --- | --- | ---: | ---: | --- | --- |
| `derived_stat` | `initiative` | 2 | 2 | `match` | `True` |
| `derived_stat` | `arcane_power` | 0 | 0 | `match` | `True` |
| `derived_stat` | `vw` | 0 | 0 | `match` | `True` |
| `derived_stat` | `gw` | 0 | 0 | `match` | `True` |
| `derived_stat` | `sr` | 0 | 0 | `match` | `True` |
| `derived_stat` | `rs` | 0 | 0 | `match` | `True` |
| `combat` | `dmg_blunt` | 8 | 8 | `match` | `True` |
| `combat` | `dmg_chain` | 8 | 8 | `match` | `True` |
| `combat` | `dmg_slash` | 8 | 8 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `craft_woodworking` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_fine_motor` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:7` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_attention` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_fine_motor` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:3` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_empathy` | -2 | -2 | `match` | `True` |
| `skill_category` | `skill_social` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:6` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_etiquette` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_social` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:4` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_evasion` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_gross_motor` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:5` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_feat_of_strength` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_gross_motor` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:8` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_swords` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_combat` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:1` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `skill` | `skill_torture` | 0 | 0 | `match` | `True` |
| `skill_category` | `skill_social` | 0 | 0 | `match` | `True` |
| `skill` | `selected_skill:2` | 0 | 0 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
| `derived_stat` | `wound_stage` | 1 | 1 | `match` | `True` |
