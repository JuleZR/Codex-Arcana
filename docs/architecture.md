# Architektur

## Uebersicht
Das Projekt ist ein klassisches Django-Monolith-Setup mit einer fachlichen Haupt-App `charsheet`.

## Hauptkomponenten
- `codex_arcana/`
  - Projektkonfiguration (`settings.py`)
  - URL-Routing (`urls.py`)
  - WSGI/ASGI-Einstiegspunkte
- `charsheet/`
  - `models.py`: Datenmodell und Validierung
  - `admin.py`: Admin-Konfiguration und Inlines
  - `views.py`: Character-Sheet-Ansichten und POST-Aktionen
  - `engine/engine.py`: Regel- und Berechnungslogik
  - `templates/charsheet/charsheet.html`: Haupt-UI fuer den Charakterbogen
- `static/` und `charsheet/static/`
  - CSS, JS und Bildressourcen

## Laufzeit-Datenfluss
1. HTTP-Request trifft Route in `codex_arcana/urls.py`.
2. View in `charsheet/views.py` laedt Character und zugehoerige Daten.
3. View nutzt `character.engine` fuer berechnete Werte.
4. `CharacterEngine` aggregiert Daten aus Modellen und Modifikatoren.
5. View rendert Template oder gibt JSON (bei AJAX/POST) zurueck.

## Persistenz
- PostgreSQL als primare Datenbank.
- Schemaentwicklung ueber Django-Migrationen in `charsheet/migrations/`.

## Erweiterungspunkte
- Neue Regeln: `charsheet/engine/engine.py`
- Neue Entitaeten/Validierung: `charsheet/models.py`
- Neue Admin-Workflows: `charsheet/admin.py`
- Neue UI-Aktionen: `charsheet/views.py` + Template/JS
