# Engine

## Overview

The rules layer is centered on `CharacterEngine`, but modifier semantics now live in the dedicated `ModifierEngine`. Productive calculations no longer resolve numeric effects directly from legacy `Modifier` rows.

## Engine Modules

- `charsheet/engine/character_engine.py`
  - main facade for character calculations
  - owns cached character state, technique state, and progression state
  - delegates all modifier resolution to `ModifierEngine`
- `charsheet/modifiers/engine.py`
  - central modifier collector and resolver
  - single source of truth for numeric modifier totals, flags, capabilities, resistances, movement, combat, and social state
- `charsheet/engine/character_combat.py`
  - combat formulas such as initiative, defenses, wound stages, and arcane power
  - consumes `CharacterEngine` methods, not legacy modifier math
- `charsheet/engine/character_equipment.py`
  - armor, shields, encumbrance, weapon rows, and damage modifiers
  - consumes `CharacterEngine` methods, not legacy modifier math
- `charsheet/engine/character_progression.py`
  - schools, paths, requirements, exclusions, and specialization availability
- `charsheet/engine/character_creation_engine.py`
  - draft-based creation flow
  - uses `CharacterBuildValidator` for structured trait build validation
  - resolves creation-only trait effects such as `starting_funds`

## CharacterEngine

### Role

`CharacterEngine` is the read-side facade used by the sheet, combat helpers, and application services.

It is responsible for:

- loading and caching character attributes, skills, schools, techniques, and choices
- exposing high-level methods such as `skill_total()`, `calculate_initiative()`, `vw()`, `get_grs()`
- routing all modifier queries through `modifier_engine`
- keeping templates free of modifier math

### Productive Modifier Flow

All productive modifier entry points now call `ModifierEngine`:

- `modifier_total_for_skill()`
- `modifier_total_for_skill_category()`
- `modifier_total_for_stat()`
- `modifier_total_for_item()`
- `modifier_total_for_item_category()`
- `modifier_total_for_specialization()`
- `modifier_total_for_entity()`
- `resolve_*()` helpers for skills, resources, resistances, movement, combat, flags, capabilities, and social state

There is no productive `legacy_only` mode anymore.

### Internal Debugging

`CharacterEngine` still exposes `debug_legacy_*` helpers for migration diagnostics and report generation. These methods are intentionally non-productive and exist only to compare the new engine against historic legacy arithmetic.

## ModifierEngine

### Responsibilities

`ModifierEngine` is the central rule-resolution layer for modifier semantics.

It:

- collects active typed modifiers
- translates persisted legacy `Modifier` rows into typed modifiers via `LegacyModifierMigrationService`
- loads persisted `TraitSemanticEffect` rows from traits
- uses the trait registry only as a fallback for complex hard-coded cases
- evaluates conditions
- applies source activation and school gating
- resolves numeric totals for target domains
- resolves semantic outputs such as flags, capabilities, movement, resistance, combat, and social profiles
- provides explainability via `explain_resolution()`

### Productive Data Sources

The productive engine works with typed modifiers only:

- migrated legacy rows from `LegacyModifierMigrationService`
- persisted `TraitSemanticEffect` rows maintained in the admin
- fallback semantic trait modifiers from `charsheet/modifiers/registry.py`
- optionally injected modifiers for tests or future structured sources

Persisted legacy rows still exist as source data, but productive resolution uses their migrated typed representation and copied scaling metadata.

### Target Domains

The central engine can resolve at least these domains:

- `skill`
- `skill_category`
- `attribute`
- `derived_stat`
- `resource`
- `resistance`
- `movement`
- `combat`
- `perception`
- `economy`
- `social`
- `rule_flag`
- `capability`
- `behavior`
- `item`
- `item_category`
- `specialization`
- `entity`

### Numeric vs Semantic Resolution

Numeric targets use `resolve_numeric_total()` and are then consumed by `CharacterEngine` formulas.

Semantic targets are resolved via dedicated methods:

- `resolve_resistances()`
- `resolve_movement()`
- `resolve_combat_profile()`
- `resolve_flags()`
- `resolve_capabilities()`
- `resolve_social_profile()`

This is deliberate: advantages and disadvantages are not reduced to plain `+X/-Y`.

### Conditions

Applicability is centralized in `ConditionSet`.

Supported condition families include:

- combat vs outside combat
- wounded / unarmored
- darkness / low light / heat / cold
- target tags and weapon types
- skill-bound situations
- social interactions
- character creation only
- required or forbidden flags

### Stacking and Priority

The current numeric resolver supports:

- additive stacking as the default for migrated legacy modifiers
- `unique_by_source` deduplication
- numeric `override`
- `min_value`
- `max_value`
- `multiply`

Modifiers are processed in priority order. Legacy-mapped rows currently rely on additive behavior, which preserves the old system's effective outcomes.

### Explainability and Debug

`explain_resolution()` returns a breakdown for one target.

`ModifierResolutionMode.COMPARE` is now debug-only:

- productive values still come from the new typed modifier layer
- legacy values are calculated only as a diagnostic baseline
- differences are recorded as `NumericResolutionComparison`

There is no mode that makes legacy arithmetic authoritative again.

## Combat, Equipment, and Sheet Integration

The combat and equipment helper modules no longer interpret legacy modifier rows themselves.

Instead they call `CharacterEngine` methods such as:

- `modifier_total_for_stat()`
- `current_wound_penalty()`
- `get_grs()`
- `get_bel()`
- `get_dmg_modifier_sum()`

`sheet_context.py` only consumes prepared engine outputs. It does not perform modifier calculations in templates.

## Character Creation and Trait Validation

`CharacterCreationEngine` uses `CharacterBuildValidator` for structured build rules such as:

- CP caps for disadvantages
- overlap conflicts
- mutually exclusive traits
- included disadvantages
- rank validation

This is intentionally separate from numeric modifier resolution because many trait effects are social, anatomical, behavioral, or narrative rather than arithmetic.
