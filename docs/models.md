# Data Model

## Overview

The persisted Django models are still split across `charsheet/models/` by domain, but the rule layer now distinguishes clearly between persisted source rows and typed modifier semantics.

## Model Packages

### `core.py`

Core definitions such as:

- `Attribute`
- `SkillCategory`
- `Skill`
- `Race`
- `RaceAttributeLimit`
- `DamageSource`
- `Trait`
- `TraitSemanticEffect`
- `Language`

### `character.py`

Character-owned runtime state such as:

- `Character`
- `CharacterAttribute`
- `CharacterSkill`
- `CharacterItem`
- `CharacterTrait`
- `CharacterLanguage`
- `CharacterCreationDraft`
- `CharacterDiaryEntry`

### `items.py`

Item data:

- `Item`
- `ArmorStats`
- `ShieldStats`
- `WeaponStats`

### `progression.py`

Progression and school state:

- `SchoolType`
- `School`
- `CharacterSchool`
- `SchoolPath`
- `CharacterSchoolPath`
- `Specialization`
- `CharacterSpecialization`
- `ProgressionRule`

### `techniques.py`

Technique rules and character technique choices:

- `TechniqueChoiceBlock`
- `Technique`
- `TechniqueRequirement`
- `TechniqueExclusion`
- `TechniqueChoiceDefinition`
- `CharacterTechnique`
- `CharacterTechniqueChoice`
- `RaceChoiceDefinition`
- `CharacterRaceChoice`
- `RaceTechnique`

### `modifier.py`

The legacy rule modifier model:

- `Modifier`

This file is intentionally separate from `techniques.py` because `Modifier` is a cross-cutting concern: it can be sourced from races, traits, schools, and techniques alike.

## Persisted Legacy Modifier Rows

The Django model `Modifier` lives in `charsheet/models/modifier.py`.

It remains important because it stores existing rule content from:

- races
- traits
- schools
- techniques
- choice definitions

However, `Modifier` is no longer the productive semantic model.

It is now treated as persisted source data that is translated into typed modifiers by `LegacyModifierMigrationService`.

New rule effects should use `TraitSemanticEffect` instead of adding rows to `Modifier`.

## Typed Modifier Domain

The productive rule semantics live in `charsheet/modifiers/`.

## TraitSemanticEffect

`TraitSemanticEffect` is the persisted bridge between the admin and the new modifier engine.

In practical terms:

- `Trait` says which advantage or disadvantage exists
- `TraitSemanticEffect` says what that trait actually does in rules terms
- `ModifierEngine` materializes each effect row into a typed modifier at runtime

This model exists so that editors can maintain semantic trait behavior in the admin without changing Python code for every new trait.

Typical uses include:

- creation-only economy effects such as `starting_funds`
- rule flags such as blindness, muteness, or no bleeding
- capability changes such as `can_see` or `can_walk_normally`
- social tags and statuses
- narrative or behavioral tags
- conditional effects via `condition_set`

Important fields:

- `target_domain`
- `target_key`
- `operator`
- `value`
- `condition_set`
- `metadata`

Example mental model:

- Trait: `Arm`
- Semantic Effect: `economy / starting_funds / override / 0`
- Condition: `{"applies_during_character_creation": true}`

That means the disadvantage does not act like a generic numeric malus. It specifically overrides starting funds during character creation.

### Base Layer

- `BaseModifier`
  - generic typed modifier carrier
  - contains source, target, operator, scaling, priority, visibility, conditions, notes, and metadata
- `ConditionSet`
  - central applicability model

### Typed Specializations

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

### Why This Split Exists

Advantages and disadvantages in Arcane Codex are not only numeric.

The typed modifier domain therefore separates:

- numeric modifiers
- rule flags
- capabilities
- resistances and immunities
- movement and combat semantics
- social and economy effects
- behavioral and narrative tags
- build-time validation rules

## Build Validation Model

Structured build validation lives beside the modifier domain:

- `TraitBuildRule`
- `CharacterBuildValidator`
- `BuildValidationIssue`

This layer handles creation-only concerns such as:

- CP costs and refunds
- rank ranges
- repeatability
- overlap and exclusivity
- included disadvantages
- disadvantage caps

## Character and Engine Connection

`Character` exposes `get_engine()` / `character.engine` as the main read-side entry point.

The engine:

- loads persisted model state
- translates persisted legacy modifier rows into typed modifiers
- loads persisted `TraitSemanticEffect` rows from traits
- resolves all productive modifier outcomes through `ModifierEngine`

## What Still Counts as Legacy

The following elements still exist for continuity and editor workflows:

- the persisted `Modifier` model
- existing foreign keys and choice-definition relations pointing to `Modifier`
- migration inventory and diagnostic reporting
- debug-only legacy comparison helpers

What no longer counts as legacy in production:

- numeric modifier totals
- skill modifier totals
- derived stat modifier totals
- combat damage modifier totals
- choice-bound modifier totals

Those now come from the typed modifier engine.
