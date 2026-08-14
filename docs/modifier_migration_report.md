# SemanticEffect Migration Report

The former rule-modifier inventory was used to validate the SemanticEffect cutover.

Current state:

- Persistent SemanticEffects are the rule-data source for productive modifier resolution.
- Legacy rows are migrated by Django migration `0355_migrate_modifier_rows_to_semantic_effects` using historical migration-state models.
- The legacy table is dropped by migration `0356_remove_modifier_model` after migration validation succeeds.
- Typed domain objects such as `BaseModifier`, `SkillModifier`, and `CombatModifier` remain part of the modifier engine.
