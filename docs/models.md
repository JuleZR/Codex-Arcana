# Datenmodell

## Ueberblick

Das Datenmodell wurde in mehrere Dateien unter `charsheet/models/` aufgeteilt. Die Aufteilung folgt nicht technischen, sondern fachlichen Grenzen. Das macht die aktuelle Struktur deutlich leichter wartbar als die fruehere Einzeldatei.

## Modellpakete

### `core.py`

Enthaelt wiederverwendbare Stammdaten:

- `Attribute`
  Basisattribute wie `ST`, `GE`, `INT`
- `SkillCategory`
  Gruppen fuer Fertigkeiten und Kategorienmodifikatoren
- `Skill`
  Fertigkeitsdefinition mit Leitattribut, Kategorie und optionaler Spezifikation
- `Race`
  Rassendefinition inklusive Bewegung, Flugwerten und Punktebudgets fuer die Charaktererstellung
- `RaceAttributeLimit`
  Min-/Max-Werte pro Attribut und Rasse
- `DamageSource`
  Schadensarten fuer Waffen
- `Trait`
  Vorteile und Nachteile mit Levelgrenzen und Punktkosten
- `Language`
  Sprachdefinition mit maximalem Level

### `character.py`

Enthaelt den persistenten Charakterzustand:

- `Character`
  Stammdaten, Besitz, EP, Schaden, Archivstatus, Ruhmwerte und Engine-Zugriff
- `CharacterDiaryEntry`
  serverseitig persistente Tagebucheintraege inklusive Reihenfolge und Fixierungsstatus
- `CharacterAttribute`
  gekaufter Attributwert pro Charakter
- `CharacterSkill`
  Fertigkeitswert plus optionale Spezifikation pro Charakter
- `CharacterItem`
  Besitzrelation zwischen Charakter und Item inklusive Menge, Ausruestungsstatus und Qualitaet
- `CharacterTrait`
  gekaufte Vorteil-/Nachteil-Stufe pro Charakter
- `CharacterLanguage`
  Sprachlevel, Schreiben und Muttersprache pro Charakter
- `CharacterCreationDraft`
  in Arbeit befindlicher Charakterentwurf mit `state`-JSON und aktueller Phase

### `items.py`

Beschreibt Items und deren Detailtabellen:

- `Item`
  Basisgegenstand mit Typ, Preis, Groessenklasse, Gewicht und Standardqualitaet
- `ArmorStats`
  Ruestungsdaten, entweder als Gesamt-RS oder zonenbasiert
- `ShieldStats`
  Schildwerte
- `WeaponStats`
  Waffenwerte inklusive Fuehrungsart und optionalem Zweihandprofil

### `progression.py`

Beschreibt Schul- und Spezialisierungsfortschritt:

- `SchoolType`
  Oberkategorie einer Schule
- `School`
  konkrete Schule
- `CharacterSchool`
  gelernte Schulstufe eines Charakters
- `SchoolPath`
  Pfad oder Ausrichtung innerhalb einer Schule
- `CharacterSchoolPath`
  vom Charakter gewaehlter Pfad pro Schule
- `Specialization`
  definierte Spezialisierung innerhalb einer Schule
- `CharacterSpecialization`
  vom Charakter gelernte Spezialisierung
- `ProgressionRule`
  regelbasierte Freischaltung pro Schultyp und Mindeststufe

### `techniques.py`

Hier liegt der komplexeste Regelbereich:

- `TechniqueChoiceBlock`
  gruppiert Techniken, aus denen nur eine begrenzte Anzahl gelernt werden darf oder muss
- `Modifier`
  generisches Modifikatorsystem mit flexibler Quelle und flexiblem Ziel
- `Technique`
  Technikdefinition mit Schule, Stufe, Typ, Support-Level und optionalem Choice-Verhalten
- `TechniqueRequirement`
  Voraussetzungen fuer Techniken
- `TechniqueExclusion`
  gegenseitige Ausschluesse
- `TechniqueChoiceDefinition`
  explizite, persistente Auswahlpflichten fuer Techniken
- `CharacterTechnique`
  explizit gelernte Technik eines Charakters
- `CharacterTechniqueChoice`
  konkret gespeicherte Auswahlentscheidung zu einer Technik

## Wichtige Beziehungen

### Charakterkern

- Ein `Character` gehoert genau einem Benutzer und genau einer `Race`.
- Ein `Character` besitzt viele `CharacterAttribute`, `CharacterSkill`, `CharacterLanguage`, `CharacterTrait` und `CharacterItem`.
- Die Kombinationen sind ueber `UniqueConstraint`s abgesichert, damit es pro Charakter keine doppelten Eintraege fuer dieselbe Fachentitaet gibt.

### Schule, Technik und Spezialisierung

- Ein Charakter kann mehrere `CharacterSchool`-Eintraege haben.
- Zu einer gelernten Schule kann optional genau ein `CharacterSchoolPath` gewaehlt werden.
- `Technique` und `Specialization` sind immer an eine `School` gebunden.
- `CharacterTechnique` und `CharacterSpecialization` setzen implizit voraus, dass der Charakter die jeweilige Schule kennt.

### Items und Inventar

- `CharacterItem` verbindet einen Charakter mit einem `Item`.
- Itemdetails liegen in separaten 1:1-Tabellen (`ArmorStats`, `ShieldStats`, `WeaponStats`).
- Die Qualitaet eines konkreten Besitzobjekts liegt auf `CharacterItem`, nicht auf dem Basismodell `Item`.

## Das Modifikatorsystem

`Modifier` ist das flexibelste Regelmodell im Projekt. Es erlaubt:

- verschiedene Quellen ueber GenericForeignKey
  typische Quellen sind `Race`, `School`, `Trait` und `Technique`
- verschiedene Zielarten
  zum Beispiel konkrete Skills, Skillkategorien, Stats, Items oder Spezialisierungen
- flache und skalierte Werte
- optionale Caps, Rundungsmodi und Mindest-Schulstufen

Dadurch kann die Engine viele Regeltexte datengetrieben auswerten, ohne fuer jede Technik oder jeden Trait eine Spezialbehandlung im Code zu benoetigen.

## Persistente UI- und Workflow-Daten

Nicht alle Modelle repraesentieren "klassische Regeln". Ein Teil stuetzt direkte Anwendungsvorgaenge:

- `CharacterCreationDraft`
  speichert den mehrphasigen Erstellungszustand als JSON
- `CharacterDiaryEntry`
  speichert das Tagebuch serverseitig und ersetzt lokale Browser-only Daten
- `CharacterTechniqueChoice`
  speichert dauerhafte Spielerentscheidungen fuer Techniken

## Wichtige Validierungsregeln

- `RaceAttributeLimit` verlangt `min_value <= max_value`.
- Nicht stackbare `CharacterItem`s duerfen nur `amount = 1` haben.
- Stackbare Items duerfen nicht ausgeruestet sein.
- `ArmorStats` sind nur fuer Items vom Typ `armor` gueltig.
- `ShieldStats` sind nur fuer Items vom Typ `shield` gueltig.
- `WeaponStats` sind nur fuer Items vom Typ `weapon` gueltig.
- Zweihanddaten in `WeaponStats` sind nur bei passenden Fuehrungsarten erlaubt.
- `CharacterTrait` und `CharacterLanguage` validieren gegen die Grenzen ihrer Stammdaten.
- `CharacterSchoolPath` und `CharacterSpecialization` pruefen, ob der Charakter die zugrunde liegende Schule kennt.
- `CharacterTechniqueChoice` erzwingt genau ein Ziel und prueft, ob es zum konfigurierten Choice-Typ der Technik passt.
