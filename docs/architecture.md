# Architektur

## Übersicht
Das Projekt ist ein klassisches Django-Monolith-Setup mit einer fachlichen Haupt-App `charsheet`.

## Hauptkomponenten
- `codex_arcana/`
  - Projektkonfiguration (`settings.py`)
  - URL-Routing (`urls.py`)
  - WSGI/ASGI-Einstiegspunkte
  - `LEGAL_INFO` für host-spezifische Impressum/Datenschutz-Angaben
- `charsheet/`
  - `models.py`: Datenmodell und Validierung
  - `admin.py`: Admin-Konfiguration und Inlines
  - `views.py`: Character-Sheet-Ansichten und POST-Aktionen
  - `engine/character_engine.py`: Regel- und Berechnungslogik für bestehende Charaktere
  - `engine/character_creation_engine.py`: Regeln für Character-Creation-Drafts
  - `engine/dice_engine.py`: einfache Würfel-Logik für Würfelwürfe
  - `templates/charsheet/charsheet.html`: Haupt-UI für den Charakterbogen
  - `templates/charsheet/dashboard.html`: Dashboard mit Verwaltung und Inline-Fenstern
- `static/` und `charsheet/static/`
  - CSS, JS und Bildressourcen

## Laufzeit-Datenfluss
1. HTTP-Request trifft Route in `codex_arcana/urls.py`.
2. View in `charsheet/views.py` lädt Character und zugehörige Daten.
3. View nutzt `character.engine` für berechnete Werte.
4. `CharacterEngine` aggregiert Daten aus Modellen und Modifikatoren.
5. View rendert Template oder gibt JSON (bei AJAX/POST) zurück.

## Persistenz
- PostgreSQL als primäre Datenbank.
- Schemaentwicklung über Django-Migrationen in `charsheet/migrations/`.

## Erweiterungspunkte
- Neue Regeln: `charsheet/engine/character_engine.py` und `charsheet/engine/character_creation_engine.py`
- Neue Entitäten/Validierung: `charsheet/models.py`
- Neue Admin-Workflows: `charsheet/admin.py`
- Neue UI-Aktionen: `charsheet/views.py` + Template/JS
- Rechtliche Inhalte/Datenschutztext: `charsheet/templates/legal/`
