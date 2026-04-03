# Modifier Refactor

## Why the Old System Was Replaced

The old `Modifier` model mixed several different rule concepts into one numeric container:

- direct skill bonuses
- derived stat bonuses
- pseudo-stats that were really flags
- choice-bound selectors
- scaling, rounding, and caps

That worked for simple arithmetic, but it was not semantically strong enough for Arcane Codex advantages, disadvantages, anatomy changes, social state, narrative constraints, or conditional rule flags.

The refactor therefore moved productive rule semantics into a dedicated typed modifier layer.

## Legacy Source Analysis

The historic source model still lives in [techniques.py](/e:/Developement/GitHub/Codex_Arcana/charsheet/models/techniques.py), not in [modifier.py](/e:/Developement/GitHub/Codex_Arcana/charsheet/models/modifier.py).

Its relevant persisted fields are:

- source selectors: `source_content_type`, `source_object_id`
- target selectors: `target_kind`, `target_slug`, `target_skill`, `target_skill_category`, `target_item`, `target_specialization`, `target_choice_definition`, `target_race_choice_definition`, `target_content_type`, `target_object_id`
- numeric shape: `mode`, `value`
- scaling: `scale_source`, `scale_school`, `scale_skill`, `mul`, `div`, `round_mode`
- gating and caps: `cap_mode`, `cap_source`, `min_school_level`

Historically used target families include:

- `skill`
- `category`
- `stat`
- `item`
- `item_category`
- `specialization`
- `entity`

Historically used stat-like keys include:

- `initiative`
- `arcane_power`
- `vw`
- `gw`
- `sr`
- `rs`
- `wound_stage`
- `wound_penalty_ignore`
- `armor_penalty_ignore`
- `shield_penalty_ignore`
- `dmg_*`

## New Productive Architecture

The productive rule system now lives in `charsheet/modifiers/`.

### Core Types

- `BaseModifier`
- `ConditionSet`
- `ModifierOperator`
- `TargetDomain`

### Typed Modifier Classes

- `SkillModifier`
- `TraitModifier`
- `DerivedStatModifier`
- `ResourceModifier`
- `ResistanceModifier`
- `MovementModifier`
- `CombatModifier`
- `PerceptionModifier`
- `EconomyModifier`
- `SocialModifier`
- `RuleFlagModifier`
- `ConditionalModifier`
- `ItemModifier`
- `SpecializationModifier`
- `EntityModifier`

### Supporting Services

- `ModifierEngine`
- `LegacyModifierMigrationService`
- `CharacterBuildValidator`
- `TraitSemanticEffect` for admin-managed trait semantics
- trait semantic registry in `registry.py` as fallback for complex hard-coded cases

## Productive State After Cutover

The new engine is now the single source of truth for productive modifier resolution.

That means:

- no productive `legacy_only` mode exists anymore
- no productive numeric total is resolved directly from legacy rows
- no productive skill total falls back to legacy arithmetic
- no productive derived stat total falls back to legacy arithmetic
- no productive combat damage modifier falls back to legacy arithmetic

Persisted legacy rows are still loaded as source data, but only after translation into typed modifiers.

## Internal Debugging

`ModifierResolutionMode.COMPARE` still exists as an internal debug aid.

Important constraints:

- productive values still come from the typed modifier layer
- legacy arithmetic is evaluated only as a comparison baseline
- comparison data is written to `NumericResolutionComparison`
- there is no mode that makes legacy arithmetic authoritative again

## Current Inventory Snapshot

The migration report in [modifier_migration_report.md](/e:/Developement/GitHub/Codex_Arcana/docs/modifier_migration_report.md) currently shows:

- 39 persisted legacy modifier rows
- sources: `race` 24, `technique` 13, `trait` 2
- target kinds: `skill` 23, `stat` 15, `category` 1

All currently observed productive legacy combinations now map into typed productive domains.

The previously suspicious `target_kind=skill` plus `dmg_slash` row is now treated as a backward-compatible `CombatModifier`, so the current live inventory no longer blocks productive new-engine resolution.

## Mapping Rules

Current migration rules include:

- skill targets -> `SkillModifier`
- category targets -> `SkillModifier` on `skill_category`
- derived stat keys -> `DerivedStatModifier`
- pseudo-stat flags -> `RuleFlagModifier`
- damage slugs -> `CombatModifier`
- choice-bound skill rows -> `SkillModifier` with `choice_binding` metadata
- item targets -> `ItemModifier`
- specialization targets -> `SpecializationModifier`
- entity targets -> `EntityModifier`

Each migrated modifier keeps provenance metadata such as:

- `legacy_modifier_id`
- `legacy_model_name`
- `migrated_from_legacy`
- `migration_note`
- `migration_confidence`
- `migration_strategy`
- `legacy_target_kind`
- `legacy_target_identifier`

## Semantic Layers

The new system explicitly separates:

- numeric modifiers
- rule flags
- capabilities
- resistance / immunity / vulnerability effects
- movement effects
- combat effects
- economy and social effects
- behavioral and narrative tags
- creation-time validation rules

This separation is the key reason the new architecture is a better fit for Arcane Codex advantages and disadvantages than the old all-in-one integer modifier model.

## Conditions, Stacking, and Priority

### Conditions

`ConditionSet` centralizes applicability rules such as:

- combat vs outside combat
- darkness, heat, cold
- wounded / unarmored
- target tags
- skill- or weapon-bound situations
- character creation only
- required or forbidden flags

### Stacking

The productive numeric resolver currently supports:

- additive stacking
- unique-by-source deduplication
- override
- min / max
- multiply

### Priority

Modifiers are processed in priority order. Current legacy-mapped rows rely on additive stacking and preserve prior outcomes, while newer semantic modifiers can opt into more explicit operators.

## Explainability

`ModifierEngine.explain_resolution()` provides target-level breakdowns.

In normal productive mode it shows the typed productive layer.

In compare mode it may additionally show debug legacy rows, but only for diagnostics.

## Trait Semantics

Traits are no longer treated as "just another number modifier."

There are now two layers for trait semantics:

- primary path: persisted `TraitSemanticEffect` rows maintained in the admin
- fallback path: the trait semantic registry in `registry.py` for complex or still-hardcoded cases

The goal is simple: ordinary trait semantics should be maintainable without editing Python code.

`TraitSemanticEffect` should be read as:

- this trait exists
- this exact semantic effect belongs to it
- the modifier engine should resolve it directly

This model can express:

- blindness, deafness, muteness
- capability loss such as `can_see` / `can_hear` / `can_speak`
- social status and legal markers
- economy effects such as regular income or starting funds
- resistance and vulnerability state
- behavioral or narrative constraints

Typical admin workflow:

1. create or edit the `Trait`
2. add one or more `Semantic Effects` rows
3. set `target_domain`, `target_key`, `operator`, `value`
4. add `condition_set` only when the effect is situational

Example:

- `Arm` can be modeled as:
  - `target_domain = economy`
  - `target_key = starting_funds`
  - `operator = override`
  - `value = 0`
  - `condition_set = {"applies_during_character_creation": true}`

Build rules remain separate and are handled by `CharacterBuildValidator`.

## Extension Guidelines

To add a new automated rule effect:

1. decide which target domain it belongs to
2. model it with the narrowest typed modifier class possible
3. use `ConditionSet` instead of ad-hoc `if` checks
4. keep narrative-only constraints separate from numeric arithmetic
5. add or update tests
6. update admin previews and docs when the semantics become editor-facing
