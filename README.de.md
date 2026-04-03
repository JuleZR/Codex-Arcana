<p align="center">
  <img src="static/img/codexarcana.png" alt="Codex Arcana Logo" width="560">
</p>

<p align="center">
  Deutsch | <a href="README.md">English</a>
</p>

# Codex Arcana

Codex Arcana ist eine Django-basierte Verwaltungs- und Regelanwendung fuer das Pen-and-Paper-Rollenspiel **Arcane Codex**.

Das Projekt verbindet persistente Charakterdaten mit einer serverseitigen Regeln-Engine, damit das Character Sheet den aktuellen mechanischen Zustand wirklich berechnet und nicht nur Werte speichert.

## Status

Fruehe Alpha / Prototyp. Funktionsumfang, Regelabdeckung und Datenstrukturen entwickeln sich noch.

## Aktuelle Funktionsbereiche

- Dashboard, Archiv und Entwurfsverwaltung
- mehrphasige Charaktererschaffung
- Character Sheet mit vorberechnetem Server-Kontext
- Inventar-, Ausruestungs-, Qualitaets- und Preislogik
- Lernen und Progression fuer Attribute, Fertigkeiten, Sprachen, Schulen, Techniken und Spezialisierungen
- Tagebuch und weitere persistente Charakter-Workflows
- zentrale typisierte Modifier-Engine fuer Regeleffekte

## Modifier-Architektur

Die produktive Regelschicht liegt in `charsheet/modifiers/`.

Wichtige Punkte:

- `ModifierEngine` ist die zentrale Modifier-Aufloesung
- produktive Berechnungen nutzen typisierte Modifier wie `SkillModifier`, `DerivedStatModifier`, `CombatModifier`, `RuleFlagModifier`, `SocialModifier` und weitere
- Vorzuege und Schwaechen werden nicht nur als Zahlen modelliert
- neue semantische Trait-Effekte werden als `TraitSemanticEffect` direkt am `Trait` gepflegt
- die Engine trennt numerische Modifier, Regel-Flags, Capabilities, Resistenzen, Bewegung, Kampf, Oekonomie, soziale Zustande und Verhaltens-Tags
- persistierte Legacy-`Modifier` existieren weiter als Quelldaten, produktiv gerechnet wird aber mit ihrer typisierten Uebersetzung
- einen produktiven `legacy_only`-Modus gibt es nicht mehr

### Trait Semantic Effects

`TraitSemanticEffect` ist der neue datengetriebene Pflegeweg fuer semantische Vorzugs- und Nachteilswirkungen.

Einfach gesagt:

- der `Trait` beschreibt, was gekauft oder gewaehlt wird
- die `Semantic Effects` darunter beschreiben, was dieser Trait regeltechnisch bewirkt
- die `ModifierEngine` liest diese Zeilen direkt

Das ist wichtig, weil viele Traits keine simplen `+X/-Y`-Boni sind. Ein Trait kann damit zum Beispiel:

- Startgeld aendern
- Flags wie Blindheit oder Stummheit setzen
- Capabilities wie `can_see` oder `can_speak` entziehen
- soziale Marker oder narrative Tags vergeben
- nur waehrend der Charaktererschaffung wirken

Pflegeweg im Admin:

1. `Trait` speichern
2. im Inline `Semantic Effects` eine oder mehrere Wirkungszeilen anlegen
3. `target_domain`, `target_key`, `operator` und bei Bedarf `condition_set` setzen

Beispiel:

- `Arm`:
  - `target_domain = economy`
  - `target_key = starting_funds`
  - `operator = override`
  - `value = 0`
  - `condition_set = {"applies_during_character_creation": true}`

Fuer einfache und mittlere Faelle soll kein Nutzer mehr Code in `registry.py` anfassen muessen. Die Code-Registry bleibt nur noch als Fallback fuer komplexe Sonderfaelle, zum Beispiel tabellenbasierte oder stark berechnete Effekte.

Siehe dazu:

- `docs/engine.md`
- `docs/models.md`
- `docs/modifier_refactor.md`

## Technologie-Stack

- Python 3
- Django 5.2
- PostgreSQL 16
- Django Templates

## Schnellstart

### Voraussetzungen

- Python 3.x
- PostgreSQL auf `localhost:5432`
- alternativ Docker fuer die mitgelieferte Datenbank

### Datenbank starten

```bash
docker compose up -d db
```

### Anwendung starten

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Wichtige URLs

- Login: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Projektstruktur

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

## DDDice-Integration

Codex Arcana kann **DDDice** fuer animierte 3D-Wuerfel verwenden.

Das eigentliche Wuerfelergebnis wird weiterhin serverseitig berechnet. DDDice ist nur die Darstellungs-Schicht.

## Lizenz

GNU General Public License v3.0.
