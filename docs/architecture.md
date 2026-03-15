# Architektur

## Überblick

Codex Arcana ist weiterhin ein klassischer Django-Monolith, aber die interne Struktur ist deutlich modularer geworden. Die wichtigste fachliche App bleibt `charsheet`, doch sie ist nicht mehr nur in "Models, Views, Template" organisiert, sondern in mehrere fachlich getrennte Bausteine:

- Modellpaket für die Domain
- Engine-Paket für regelbasierte Berechnungen
- Kontextaufbereitung für das Character Sheet
- eigenständige Workflow-Module für Lernen und Shop
- JSON-Endpunkte für interaktive UI-Bereiche wie das Tagebuch

## Zentrale Schichten

### 1. Projektkonfiguration

`codex_arcana/` enthält die Django-Projektdateien:

- `settings.py` für Datenbank, Apps, statische Dateien und `LEGAL_INFO`
- `urls.py` als zentrale URL-Liste
- `wsgi.py` und `asgi.py` als Einstiegspunkte

### 2. HTTP- und UI-Schicht

`charsheet/views.py` ist die zentrale Web-Schicht. Dort liegen:

- klassische Seiten-Views wie Dashboard, Character-Erstellung und Character Sheet
- POST-Aktionen für Statusänderungen, Lern- und Shop-Vorgänge
- JSON-Endpunkte für das Tagebuch und einzelne AJAX-Updates

Die Views bleiben bewusst relativ schlank. Wiederverwendbare Hilfen sind ausgelagert nach:

- `charsheet/view_utils.py` für kleine Formatierungs- und UI-Helfer
- `charsheet/sheet_context.py` für den vollständigen Template-Kontext des Character Sheets
- `charsheet/learning.py` für EP-basierte Lernvorgänge
- `charsheet/shop.py` für Shop- und Warenkorb-Logik

### 3. Domain-Schicht

Die Modelle liegen heute in `charsheet/models/` und sind nach fachlichem Zusammenhang getrennt:

- `core.py`: Stammdaten wie Attribute, Skills, Rassen, Traits, Sprachen
- `character.py`: charaktergebundene Daten wie Attribute, Skills, Inventar, Tagebuch und Drafts
- `items.py`: Items, Waffen-, Schild- und Rüstungswerte
- `progression.py`: Schulen, Pfade, Spezialisierungen und Progressionsregeln
- `techniqs.py`: Techniken, Modifikatoren, Voraussetzungen, Ausschlüsse und persistente Choices

`charsheet/models/__init__.py` re-exportiert die wichtigsten Klassen, damit bestehende Imports stabil bleiben.

### 4. Regel- und Berechnungsschicht

Die Berechnungslogik liegt in `charsheet/engine/`.

- `character_engine.py` ist die zentrale Fassade für abgeleitete Charakterwerte.
- `character_combat.py` enthält Kampf-, Wund- und Abwehrlogik.
- `character_equipment.py` enthält Inventar-, Waffen- und Rüstungsberechnung.
- `character_progression.py` enthält Schul-, Technik- und Spezialisierungsabfragen.
- `item_engine.py` kapselt qualitätsabhängige Itemberechnung.
- `character_creation_engine.py` verarbeitet Drafts der Charaktererstellung.

Der Character-Modelleinstieg `character.engine` erzeugt und cached eine `CharacterEngine` pro Instanz.

## Typischer Request-Datenfluss

### Character Sheet

1. Die Route in `codex_arcana/urls.py` leitet auf `views.character_sheet(...)`.
2. Die View lädt den Charakter benutzerbezogen und aktualisiert `last_opened_at`.
3. `build_character_sheet_context(character)` sammelt alle UI-relevanten Daten.
4. Dabei fragt der Kontext vorbereitete Werte aus `character.engine` ab.
5. Das Template rendert fertige Zeilen und Panels, statt komplexe Logik selbst auszuführen.

### Lernen

1. Das Lernformular postet an `apply_learning`.
2. Die View delegiert an `process_learning_submission(...)`.
3. Das Modul validiert Ziele, berechnet Gesamtkosten und schreibt Änderungen atomar.
4. Die Rückmeldung wird als Django-Message zurück ins Sheet getragen.

### Shop

1. Das Shop-UI baut einen JSON-Warenkorb.
2. `buy_shop_cart(...)` validiert Items, Mengen, Qualitäten und Geld.
3. Kauf und Inventarupdate laufen in einer Transaktion.
4. Die Antwort kommt als JSON an das Frontend zurück.

### Tagebuch

1. Das Frontend fragt Einträge über `/diary/` als JSON ab.
2. Die View normalisiert serverseitig Reihenfolge und "eine leere Abschlusszeile".
3. Speichern, Fixieren, Bearbeiten und Löschen laufen über getrennte Endpunkte.
4. Jede Antwort liefert den kompletten normalisierten Zustand für die UI.

## Warum `sheet_context.py` wichtig ist

Das Character Sheet war fachlich zu groß geworden, um Berechnungen direkt in Views oder Templates lesbar zu halten. `sheet_context.py` ist deshalb die Schicht, die Engine-Daten in konkrete Anzeigeobjekte übersetzt:

- Anzeigezeilen für Attribute, Skills, Inventar, Waffen und Rüstung
- Gruppierung für Lernen und Shop
- formatierte Werte für Geld, Wunden, Initiative und Bewegungsdaten
- vorbereitete Formularinstanzen für Inline-Änderungen

Diese Trennung macht Templates einfacher, ohne die eigentliche Regel-Engine mit UI-Sonderfällen zu vermischen.

## Persistenz

- primäre Datenbank: PostgreSQL
- Migrationen: `charsheet/migrations/`
- Entwurfs- und UI-Zwischenzustände:
  - `CharacterCreationDraft.state` als JSON für die Charaktererstellung
  - persistente Tagebucheinträge über `CharacterDiaryEntry`
  - Technik-Choices über `CharacterTechniqChoice`

## Erweiterungspunkte

- Neue Regeln oder abgeleitete Werte: `charsheet/engine/`
- Neue Character-Sheet-Panels oder Anzeigegruppen: `charsheet/sheet_context.py` plus Template-Partials
- Neue benutzerseitige Workflows: separates Modul wie `learning.py` oder `shop.py`
- Neue Modellbereiche: passende Datei in `charsheet/models/`
- Neue interaktive Frontend-Teile: View + Partial + statisches JS
