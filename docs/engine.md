# Engine

## Überblick

Die Regel- und Berechnungslogik ist heute auf mehrere Dateien verteilt. Die wichtigste Fassade bleibt `CharacterEngine`, aber sie wird von spezialisierten Hilfsmodulen unterstützt.

## Module im Engine-Paket

- `character_engine.py`
  zentrale Fassade für abgeleitete Charakterwerte
- `character_combat.py`
  Initiative, Abwehr, Wunden, arkane Kraft und verwandte Kampfwerte
- `character_equipment.py`
  Waffen, Rüstung, Schild, Belastung, Schaden und Münzumrechnung
- `character_progression.py`
  Schulen, Pfade, Progressionsregeln, Technik-Choice-Blocks und Spezialisierungen
- `character_creation_engine.py`
  Draft-basierte Charaktererstellung über vier Phasen
- `item_engine.py`
  Preise, Qualitäten, Waffenschaden und Rüstungsableitungen
- `dice_engine.py`
  einfache Würfelhilfen

## CharacterEngine

### Rolle

`CharacterEngine` ist die zentrale Recheninstanz für einen existierenden Charakter. Das `Character`-Modell stellt sie über `character.engine` bereit und cached sie für wiederholte Zugriffe innerhalb eines Requests.

### Was die Engine berechnet

- Attributwerte und Attributsmodifikatoren
- Skillwerte inklusive Breakdown
- Modifikatoren aus Rasse, Traits, Schulen und Techniken
- Kampfwerte wie Initiative, `VW`, `GW`, `SR`
- Wundstufen, Wundabzüge und Wundgrenzen
- Rüstungs- und Belastungswerte
- Waffenzeilen für die UI
- Progressionsstatus für Schulen, Techniken und Spezialisierungen

### Wichtige interne Konzepte

#### 1. Cached Maps

Die Engine lädt viele Daten nur einmal und hält sie über `@cached_property`, zum Beispiel:

- Attribute nach `short_name`
- Skills mit Kategorie und Leitattribut
- gelernte Schulen
- gewählte Schulpfade
- gelernte Technik-Choices
- relevante Modifikatoren

Das reduziert Datenbankzugriffe und sorgt dafür, dass mehrere UI-Bereiche denselben konsistenten Snapshot verwenden.

#### 2. Technikstatus statt Einzelabfragen

Die heutige Engine arbeitet nicht nur mit "hat Technik X oder nicht", sondern baut für alle Techniken gelernter Schulen strukturierte Statusobjekte auf. Diese enthalten unter anderem:

- ob die Schule bekannt ist
- ob die Stufe erreicht ist
- ob der Pfad passt
- ob Voraussetzungen erfüllt sind
- ob Ausschlüsse greifen
- ob die Technik verfügbar, gelernt und regeltechnisch aktiv ist
- ob persistente Choices vollständig vorliegen

Dadurch können Technik-, Modifier- und Spezialisierungslogik auf einem gemeinsamen Zustand aufbauen.

#### 3. Modifikatorauflösung

Die Engine wertet `Modifier` datengetrieben aus:

- passende Modifier werden nach Zielart und Zielidentifier gruppiert
- aktive Quellen werden geprüft
- optional wird skaliert, gerundet und gecappt
- skillbasierte Stat-Modifikatoren kÃ¶nnen dabei entweder den gelernten Skillrang oder den voll berechneten Skillwert verwenden
- das Ergebnis fließt in Stats, Skills oder Ausrüstungswerte ein

Aktive Quellen sind aktuell vor allem:

- die Rasse des Charakters
- gelernte Schulen
- gekaufte Traits
- passive, berechenbare und vollständig konfigurierte Techniken

## CharacterEngine-Hilfsmodule

### `character_combat.py`

Liefert unter anderem:

- `calculate_initiative`
- `calculate_arcane_power`
- `vw`, `gw`, `sr`
- `wound_thresholds`
- `current_wound_stage`
- `current_wound_penalty`

Die Funktionen arbeiten auf Engine-Daten und kapseln Kampfregeln, damit `character_engine.py` nicht unnötig monolithisch wird.

### `character_equipment.py`

Liefert:

- ausgerüstete Waffen-, Rüstungs- und Schild-Querysets
- vorbereitete Anzeigezeilen für Waffen und Ausrüstung
- `get_grs`, `get_bel`, `get_ms`
- qualitätsabhängige Waffenmodifikatoren
- Münzumrechnung

### `character_progression.py`

Liefert:

- Schulstufen und ausgewählte Pfade
- offene und belegte Spezialisierungsslots
- verfügbare Spezialisierungen
- Status für Technik-Choice-Blocks
- aktive Progressionsregeln pro Schultyp

## ItemEngine

`ItemEngine` berechnet abgeleitete Werte für ein Basismodell `Item` oder für ein konkretes `CharacterItem`.

### Aufgaben

- Normalisierung und Darstellung von Itemqualitäten
- qualitätsabhängige Preisberechnung
- Gewichtsberechnung bei gestapelten Items
- Ermittlung von Waffenprofilen
- qualitätsabhängige Schadens- und Manöverboni
- Rüstungs- und Schildwerte für Anzeige und Summenbildung

Wichtig ist die Trennung zwischen:

- Basismodell `Item`
  enthält Preis und Standardqualität
- Besitzobjekt `CharacterItem`
  enthält die konkrete Qualität im Inventar des Charakters

## CharacterCreationEngine

### Rolle

Diese Engine verarbeitet `CharacterCreationDraft` und bildet den vierphasigen Erstellungsworkflow ab.

### Aufgaben

- Lesen und Schreiben des JSON-Zustands pro Phase
- Kostenberechnung für Attribute, Skills, Sprachen, Vor- und Nachteile sowie Schulen
- Validierung jeder einzelnen Phase
- Finalisierung in echte Charakterdaten

### Typischer Ablauf

1. Draft laden oder neu anlegen.
2. Zustand der aktuellen Phase aus Formularfeldern in `draft.state` übernehmen.
3. Passende `validate_phase_*`-Methode ausführen.
4. Bei Erfolg zur nächsten Phase wechseln oder finalisieren.
5. Beim Finalisieren echte Charaktermodelle erzeugen und den Draft verwerfen.

## Lernen außerhalb der Engine

Der EP-Lernworkflow liegt bewusst nicht direkt in `CharacterEngine`, sondern in `charsheet/learning.py`. Das Modul:

- liest Lernziele aus POST-Daten
- nutzt `learning_rules.py` für Kostenmodelle
- validiert Ober- und Untergrenzen
- schreibt Änderungen in einer Transaktion
- reduziert `current_experience`

Das ist eine sinnvolle Trennung, weil Lernen ein mutierender Workflow ist, während `CharacterEngine` primär lesend und ableitend arbeitet.

## DiceEngine

`charsheet/engine/dice_engine.py` ist ein kleiner Hilfsbaustein für konfigurierbare Würfelwürfe und von der restlichen Character-Logik weitgehend unabhängig.
