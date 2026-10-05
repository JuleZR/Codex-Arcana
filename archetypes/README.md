# Archetypen

Hier können Archetypen als UTF-8-JSON-Dateien (`*.json`) hinterlegt werden.
Ohne ladbare JSON-Dateien erscheint keine Archetypenauswahl. Es werden noch
keine GRW-Archetypen mitgeliefert.

Jede Datei enthält `slug` (eindeutig, Kleinbuchstaben und Bindestriche), `name`,
`race` und `state`; `description` ist optional. `state` entspricht dem
`CharacterCreationDraft.state` und enthält die Objekte `meta`, `phase_1`,
`phase_2`, `phase_3`, `phase_4`. `meta.name` ist der spätere Charaktername.
Der Charaktertyp wird bei Verwendung gewählt, nicht in der Datei gespeichert.
Auf der Bestätigungsseite kann der Charaktername angepasst werden; bei bereits
vergebenen Namen wird ein freier Name vorgeschlagen.

Referenzen bleiben installationsunabhängig:

- `race`: eindeutiger Rassenname oder dessen mit Django `slugify` erzeugter Slug
  (z. B. `mensch`).
- `meta.country_of_origin`: Ländername oder dessen Slug.
- `phase_4.schools`: Schulname oder dessen Slug als Schlüssel.
- `phase_4.aspects`: Aspekt-Slug als Schlüssel.
- `phase_4.lessons`: Liste von Lektionen-Slugs.
- `phase_4.weapon_arcana[].rune_id`: Runen-Slug, trotz des bestehenden Feldnamens.
- `phase_3/phase_4.trait_specifications[trait_slug].option_id`: Name der
  Spezifikationsoption oder dessen Slug.
- `phase_3/phase_4.trait_choices[trait_slug]`: Name der Entscheidung oder dessen
  Slug als Schlüssel. Für Entitätsentscheidungen enthält die Werteliste Objekte
  mit `model` (z. B. `organization`) und `ref` (Entitäts-Slug, andernfalls Name).
  Eigenschaften und Ressourcen behalten ihre vorhandenen Kennungen.
- Fertigkeiten, Sprachen, Vorzüge, Schwächen und Vampiroptionen verwenden die
  bereits im Draft vorgesehenen Slugs; Eigenschaften ihre Kürzel.

Numerische Datenbank-IDs sind für diese Contentreferenzen nicht vorgesehen.
Unbekannte oder mehrdeutige Referenzen und fehlerhafte Dateien werden nicht
angeboten. Doppelte Archetypen-Slugs werden ebenfalls nicht angeboten.
Ladbare Archetypen müssen bei der bestätigten Erstellung zusätzlich alle vier
Validatoren der bestehenden `CharacterCreationEngine` bestehen. Regelwidrige
oder veraltete Werte führen zu einer Fehlermeldung, ohne einen Charakter oder
einen neuen Draft zu hinterlassen.
