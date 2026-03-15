# Engine

## Ueberblick

Die Regel- und Berechnungslogik ist heute auf mehrere Dateien verteilt. Die wichtigste Fassade bleibt `CharacterEngine`, aber sie wird von spezialisierten Hilfsmodulen unterstuetzt.

## Module im Engine-Paket

- `character_engine.py`
  zentrale Fassade fuer abgeleitete Charakterwerte
- `character_combat.py`
  Initiative, Abwehr, Wunden, arkane Kraft und verwandte Kampfwerte
- `character_equipment.py`
  Waffen, Ruestung, Schild, Belastung, Schaden und Muenzumrechnung
- `character_progression.py`
  Schulen, Pfade, Progressionsregeln, Technik-Choice-Blocks und Spezialisierungen
- `character_creation_engine.py`
  Draft-basierte Charaktererstellung ueber vier Phasen
- `item_engine.py`
  Preise, Qualitaeten, Waffenschaden und Ruestungsableitungen
- `dice_engine.py`
  einfache Wuerfelhilfen

## CharacterEngine

### Rolle

`CharacterEngine` ist die zentrale Recheninstanz fuer einen existierenden Charakter. Das `Character`-Modell stellt sie ueber `character.engine` bereit und cached sie fuer wiederholte Zugriffe innerhalb eines Requests.

### Was die Engine berechnet

- Attributwerte und Attributsmodifikatoren
- Skillwerte inklusive Breakdown
- Modifikatoren aus Rasse, Traits, Schulen und Techniken
- Kampfwerte wie Initiative, `VW`, `GW`, `SR`
- Wundstufen, Wundabzuege und Wundgrenzen
- Ruestungs- und Belastungswerte
- Waffenzeilen fuer die UI
- Progressionsstatus fuer Schulen, Techniken und Spezialisierungen

### Wichtige interne Konzepte

#### 1. Cached Maps

Die Engine laedt viele Daten nur einmal und haelt sie ueber `@cached_property`, zum Beispiel:

- Attribute nach `short_name`
- Skills mit Kategorie und Leitattribut
- gelernte Schulen
- gewaehlte Schulpfade
- gelernte Technik-Choices
- relevante Modifikatoren

Das reduziert Datenbankzugriffe und sorgt dafuer, dass mehrere UI-Bereiche denselben konsistenten Snapshot verwenden.

#### 2. Technikstatus statt Einzelabfragen

Die heutige Engine arbeitet nicht nur mit "hat Technik X oder nicht", sondern baut fuer alle Techniken gelernter Schulen strukturierte Statusobjekte auf. Diese enthalten unter anderem:

- ob die Schule bekannt ist
- ob die Stufe erreicht ist
- ob der Pfad passt
- ob Voraussetzungen erfuellt sind
- ob Ausschluesse greifen
- ob die Technik verfuegbar, gelernt und regeltechnisch aktiv ist
- ob persistente Choices vollstaendig vorliegen

Dadurch koennen Technik-, Modifier- und Spezialisierungslogik auf einem gemeinsamen Zustand aufbauen.

#### 3. Modifikatorauflosung

Die Engine wertet `Modifier` datengetrieben aus:

- passende Modifier werden nach Zielart und Zielidentifier gruppiert
- aktive Quellen werden geprueft
- optional wird skaliert, gerundet und gecappt
- das Ergebnis fliesst in Stats, Skills oder Ausruestungswerte ein

Aktive Quellen sind aktuell vor allem:

- die Rasse des Charakters
- gelernte Schulen
- gekaufte Traits
- passive, berechenbare und vollstaendig konfigurierte Techniken

## CharacterEngine-Hilfsmodule

### `character_combat.py`

Liefert unter anderem:

- `calculate_initiative`
- `calculate_arcane_power`
- `vw`, `gw`, `sr`
- `wound_thresholds`
- `current_wound_stage`
- `current_wound_penalty`

Die Funktionen arbeiten auf Engine-Daten und kapseln Kampfregeln, damit `character_engine.py` nicht unnoetig monolithisch wird.

### `character_equipment.py`

Liefert:

- ausgeruestete Waffen-, Ruestungs- und Schild-Querysets
- vorbereitete Anzeigezeilen fuer Waffen und Ausruestung
- `get_grs`, `get_bel`, `get_ms`
- qualitaetsabhaengige Waffenmodifikatoren
- Muenzumrechnung

### `character_progression.py`

Liefert:

- Schulstufen und ausgewaehlte Pfade
- offene und belegte Spezialisierungsslots
- verfuegbare Spezialisierungen
- Status fuer Technik-Choice-Blocks
- aktive Progressionsregeln pro Schultyp

## ItemEngine

`ItemEngine` berechnet abgeleitete Werte fuer ein Basismodell `Item` oder fuer ein konkretes `CharacterItem`.

### Aufgaben

- Normalisierung und Darstellung von Itemqualitaeten
- qualitaetsabhaengige Preisberechnung
- Gewichtsberechnung bei gestapelten Items
- Ermittlung von Waffenprofilen
- qualitaetsabhaengige Schadens- und Manoeverboni
- Ruestungs- und Schildwerte fuer Anzeige und Summenbildung

Wichtig ist die Trennung zwischen:

- Basismodell `Item`
  enthaelt Preis und Standardqualitaet
- Besitzobjekt `CharacterItem`
  enthaelt die konkrete Qualitaet im Inventar des Charakters

## CharacterCreationEngine

### Rolle

Diese Engine verarbeitet `CharacterCreationDraft` und bildet den vierphasigen Erstellungsworkflow ab.

### Aufgaben

- Lesen und Schreiben des JSON-Zustands pro Phase
- Kostenberechnung fuer Attribute, Skills, Sprachen, Vor- und Nachteile sowie Schulen
- Validierung jeder einzelnen Phase
- Finalisierung in echte Charakterdaten

### Typischer Ablauf

1. Draft laden oder neu anlegen.
2. Zustand der aktuellen Phase aus Formularfeldern in `draft.state` uebernehmen.
3. Passende `validate_phase_*`-Methode ausfuehren.
4. Bei Erfolg zur naechsten Phase wechseln oder finalisieren.
5. Beim Finalisieren echte Charaktermodelle erzeugen und den Draft verwerfen.

## Lernen ausserhalb der Engine

Der EP-Lernworkflow liegt bewusst nicht direkt in `CharacterEngine`, sondern in `charsheet/learning.py`. Das Modul:

- liest Lernziele aus POST-Daten
- nutzt `learning_rules.py` fuer Kostenmodelle
- validiert Ober- und Untergrenzen
- schreibt Aenderungen in einer Transaktion
- reduziert `current_experience`

Das ist eine sinnvolle Trennung, weil Lernen ein mutierender Workflow ist, waehrend `CharacterEngine` primaer lesend und ableitend arbeitet.

## DiceEngine

`charsheet/engine/dice_engine.py` ist ein kleiner Hilfsbaustein fuer konfigurierbare Wuerfelwuerfe und von der restlichen Character-Logik weitgehend unabhaengig.
