# Datenmodell

## Kernentitaeten

## Charakterbasis
- `Character`: Spielercharakter (Owner, Rasse, Stammdaten, Geld, EP, Schaden)
- `Race`: Rassendefinition inkl. Bewegungswerte und Phasen-Budgets
- `Attribute`: Basisattribute (z. B. ST, GE, INT)
- `CharacterAttribute`: Attributwert je Charakter
- `SkillCategory`: Gruppierung fuer Skills
- `Skill`: Fertigkeit inkl. Leitattribut und Kategorie
- `CharacterSkill`: Skill-Rang je Charakter

## Schulen und Progression
- `SchoolType`: Oberkategorie fuer Schulen
- `School`: konkrete Schule
- `CharacterSchool`: Schulstufe je Charakter
- `ProgressionRule`: regelbasierte Freischaltungen pro Schultyp und Mindestlevel
- `Technique`: Technik je Schule und Stufe

## Modifikator-System
- `Modifier`: generisches Modifikator-Modell mit:
  - Generic FK als Quelle (`source_content_type`, `source_object_id`, `source`)
  - Ziel (`target_kind`, `target_slug`)
  - Modus (`flat` oder `scaled`)
  - Skalierungsquelle (z. B. Trait-Level, School-Level)
  - optionalen Caps und Gates

## Inventar und Kampfnahe Daten
- `Item`: Gegenstand (Typ, Preis, Stackbarkeit, Beschreibung)
- `CharacterItem`: Besitzrelation Item <-> Charakter (Menge, ausgeruestet)
- `ArmorStats`: Ruestungswerte (Gesamt oder Zonenwerte)
- `DamageSource`: Schadensart/-quelle fuer Waffen
- `WeaponStats`: Waffenwerte (Schaden, Schadensquelle, Mindeststaerke)

## Traits und Sprachen
- `Trait`: Vorteil/Nachteil mit Levelgrenzen und Punktkosten
- `CharacterTrait`: gekaufte Trait-Stufe je Charakter
- `Language`: Sprachdefinition mit maximalem Level
- `CharacterLanguage`: Sprachlevel/Schrift/Muttersprache je Charakter

## Charaktererschaffung
- `CharacterCreationDraft`: persistierter Zustand fuer mehrphasige Charaktererschaffung

## Wichtige Modellregeln (Beispiele)
- Race-Attribute-Limits muessen `min_value <= max_value` sein.
- Nicht-stackbare Items duerfen nur Menge `1` haben.
- `ArmorStats` duerfen nur an Items vom Typ `armor` haengen.
- `WeaponStats` duerfen nur an Items vom Typ `weapon` haengen.
- Trait- und Sprachlevel werden gegen jeweilige Grenzen validiert.
