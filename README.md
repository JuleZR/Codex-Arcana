<p align="center">
  <img src="static/img/codexarcana.png" alt="Codex Arcana Logo" width="560">
</p>

<p align="center">
  English | <a href="README.de.md">Deutsch</a>
</p>

# Codex Arcana

Codex Arcana is a Django-based management and rules application for the pen-and-paper RPG **Arcane Codex**.

The project combines persistent character data with a server-side rules engine so that the character sheet reflects the current mechanical state instead of acting as a passive data dump.

## Status

Early alpha / prototype. Features, rules coverage, and data structures are still evolving.

## Current Feature Areas

- dashboard, archive, and draft management
- multi-phase character creation
- character sheet with precomputed server-side context
- inventory, equipment, quality, and pricing logic
- learning and progression for attributes, skills, languages, schools, techniques, and specializations
- diary and other persistent character-side workflows
- central typed modifier engine for rule effects

## Modifier Architecture

The productive rules layer is built around `charsheet/modifiers/`.

Key points:

- `ModifierEngine` is the central modifier resolver
- productive calculations use typed modifiers such as `SkillModifier`, `DerivedStatModifier`, `CombatModifier`, `RuleFlagModifier`, `SocialModifier`, and more
- advantages and disadvantages are not modeled as numbers only
- the engine separates numeric modifiers, rule flags, capabilities, resistances, movement, combat, economy, social state, and behavioral tags
- persisted legacy `Modifier` rows still exist as source data, but productive resolution uses their translated typed representation
- there is no productive `legacy_only` mode anymore

See:

- `docs/engine.md`
- `docs/models.md`
- `docs/modifier_refactor.md`

## Technology Stack

- Python 3
- Django 5.2
- PostgreSQL 16
- Django Templates

## Getting Started

### Requirements

- Python 3.x
- PostgreSQL on `localhost:5432`
- or Docker for the provided database setup

### Start the database

```bash
docker compose up -d db
```

### Run the application

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Important URLs

- Login: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Project Structure

```text
codex_arcana/
charsheet/
  models/
  engine/
  modifiers/
  templates/
  sheet_context.py
docs/
static/
```

## DDDice Integration

Codex Arcana can use **DDDice** for animated 3D dice visuals.

The actual dice result is still calculated on the server. DDDice is only a rendering layer.

## License

GNU General Public License v3.0.
