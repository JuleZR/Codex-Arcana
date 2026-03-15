# Datenmodell

## Überblick

Das Datenmodell wurde in mehrere Dateien unter `charsheet/models/` aufgeteilt. Die Aufteilung folgt nicht technischen, sondern fachlichen Grenzen. Das macht die aktuelle Struktur deutlich leichter wartbar als die frühere Einzeldatei.

## Modellpakete

### `core.py`

Enthält wiederverwendbare Stammdaten:

- `Attribute`
  Basisattribute wie `ST`, `GE`, `INT`
- `SkillCategory`
  Gruppen für Fertigkeiten und Kategorienmodifikatoren
- `Skill`
  Fertigkeitsdefinition mit Leitattribut, Kategorie und optionaler Spezifikation
- `Race`
  Rassendefinition inklusive Bewegung, Flugwerten und Punktebudgets für die Charaktererstellung
- `RaceAttributeLimit`
  Min-/Max-Werte pro Attribut und Rasse
- `DamageSource`
  Schadensarten für Waffen
- `Trait`
  Vorteile und Nachteile mit Levelgrenzen und Punktkosten
- `Language`
  Sprachdefinition mit maximalem Level

### `character.py`

Enthält den persistenten Charakterzustand:

- `Character`
  Stammdaten, Besitz, EP, Schaden, Archivstatus, Ruhmwerte und Engine-Zugriff
- `CharacterDiaryEntry`
  serverseitig persistente Tagebucheinträge inklusive Reihenfolge und Fixierungsstatus
- `CharacterAttribute`
  gekaufter Attributwert pro Charakter
- `CharacterSkill`
  Fertigkeitswert plus optionale Spezifikation pro Charakter
- `CharacterItem`
  Besitzrelation zwischen Charakter und Item inklusive Menge, Ausrüstungsstatus und Qualität
- `CharacterTrait`
  gekaufte Vorteil-/Nachteil-Stufe pro Charakter
- `CharacterLanguage`
  Sprachlevel, Schreiben und Muttersprache pro Charakter
- `CharacterCreationDraft`
  in Arbeit befindlicher Charakterentwurf mit `state`-JSON und aktueller Phase

### `items.py`

Beschreibt Items und deren Detailtabellen:

- `Item`
  Basisgegenstand mit Typ, Preis, Größenklasse, Gewicht und Standardqualität
- `ArmorStats`
  Rüstungsdaten, entweder als Gesamt-RS oder zonenbasiert
- `ShieldStats`
  Schildwerte
- `WeaponStats`
  Waffenwerte inklusive Führungsart und optionalem Zweihandprofil

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
  vom Charakter gewählter Pfad pro Schule
- `Specialization`
  definierte Spezialisierung innerhalb einer Schule
- `CharacterSpecialization`
  vom Charakter gelernte Spezialisierung
- `ProgressionRule`
  regelbasierte Freischaltung pro Schultyp und Mindeststufe

### `techniqs.py`

Hier liegt der komplexeste Regelbereich:

- `TechniqChoiceBlock`
  gruppiert Techniken, aus denen nur eine begrenzte Anzahl gelernt werden darf oder muss
- `Modifier`
  generisches Modifikatorsystem mit flexibler Quelle und flexiblem Ziel
- `Techniq`
  Technikdefinition mit Schule, Stufe, Typ, Support-Level und optionalem Choice-Verhalten
- `TechniqRequirement`
  Voraussetzungen für Techniken
- `TechniqExclusion`
  gegenseitige Ausschlüsse
- `TechniqChoiceDefinition`
  explizite, persistente Auswahlpflichten für Techniken
- `CharacterTechniq`
  explizit gelernte Technik eines Charakters
- `CharacterTechniqChoice`
  konkret gespeicherte Auswahlentscheidung zu einer Technik

## Wichtige Beziehungen

### Charakterkern

- Ein `Character` gehört genau einem Benutzer und genau einer `Race`.
- Ein `Character` besitzt viele `CharacterAttribute`, `CharacterSkill`, `CharacterLanguage`, `CharacterTrait` und `CharacterItem`.
- Die Kombinationen sind über `UniqueConstraint`s abgesichert, damit es pro Charakter keine doppelten Einträge für dieselbe Fachentität gibt.

### Schule, Technik und Spezialisierung

- Ein Charakter kann mehrere `CharacterSchool`-Einträge haben.
- Zu einer gelernten Schule kann optional genau ein `CharacterSchoolPath` gewählt werden.
- `Techniq` und `Specialization` sind immer an eine `School` gebunden.
- `CharacterTechniq` und `CharacterSpecialization` setzen implizit voraus, dass der Charakter die jeweilige Schule kennt.

### Items und Inventar

- `CharacterItem` verbindet einen Charakter mit einem `Item`.
- Itemdetails liegen in separaten 1:1-Tabellen (`ArmorStats`, `ShieldStats`, `WeaponStats`).
- Die Qualität eines konkreten Besitzobjekts liegt auf `CharacterItem`, nicht auf dem Basismodell `Item`.

## Das Modifikatorsystem

`Modifier` ist das flexibelste Regelmodell im Projekt. Es erlaubt:

- verschiedene Quellen über `GenericForeignKey`
  typische Quellen sind `Race`, `School`, `Trait` und `Techniq`
- verschiedene Zielarten
  zum Beispiel konkrete Skills, Skillkategorien, Stats, Items oder Spezialisierungen
- flache und skalierte Werte
- optionale Caps, Rundungsmodi und Mindest-Schulstufen

Dadurch kann die Engine viele Regeltexte datengetrieben auswerten, ohne für jede Technik oder jeden Trait eine Spezialbehandlung im Code zu benötigen.

## Persistente UI- und Workflow-Daten

Nicht alle Modelle repräsentieren "klassische Regeln". Ein Teil stützt direkte Anwendungsvorgänge:

- `CharacterCreationDraft`
  speichert den mehrphasigen Erstellungszustand als JSON
- `CharacterDiaryEntry`
  speichert das Tagebuch serverseitig und ersetzt lokale Browser-only Daten
- `CharacterTechniqChoice`
  speichert dauerhafte Spielerentscheidungen für Techniken

## Wichtige Validierungsregeln

- `RaceAttributeLimit` verlangt `min_val <= max_val`.
- Nicht stackbare `CharacterItem`s dürfen nur `amount = 1` haben.
- Stackbare Items dürfen nicht ausgerüstet sein.
- `ArmorStats` sind nur für Items vom Typ `armor` gültig.
- `ShieldStats` sind nur für Items vom Typ `shield` gültig.
- `WeaponStats` sind nur für Items vom Typ `weapon` gültig.
- Zweihanddaten in `WeaponStats` sind nur bei passenden Führungsarten erlaubt.
- `CharacterTrait` und `CharacterLanguage` validieren gegen die Grenzen ihrer Stammdaten.
- `CharacterSchoolPath` und `CharacterSpecialization` prüfen, ob der Charakter die zugrunde liegende Schule kennt.
- `CharacterTechniqChoice` erzwingt genau ein Ziel und prüft, ob es zum konfigurierten Choice-Typ der Technik passt.
