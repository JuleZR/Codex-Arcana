# Modifier Target Slugs nach Kategorie

Diese Referenz listet gültige Modifier-Ziele nach praktischer Kategorie. Feste Slugs stehen direkt hier; datenbankabhängige Ziele sind mit ihrem Format beschrieben.

## Attribute

Für `target_domain=attribute`, `target_domain=attribute_cap`, Legacy-`target_kind=attribute` und Legacy-`target_kind=stat`.

| Slug | Bedeutung |
| --- | --- |
| `ST` | Stärke |
| `KON` | Konstitution |
| `GE` | Geschicklichkeit / Geschick |
| `WA` | Wahrnehmung |
| `INT` | Intelligenz |
| `WILL` | Willenskraft |
| `CHA` | Charisma |
| `spz.` | Spezial |

Hinweis: `attribute` verändert den effektiven Wert und darf über das normale Maximum hinausgehen. `attribute_cap` verändert das lernbare Maximum.

## Bogenwerte

Für `target_domain=derived_stat` und Legacy-`target_kind=stat`.

| Slug | Bedeutung |
| --- | --- |
| `initiative` | Initiative |
| `arcane_power` | Arkane Macht |
| `potential` | Potenzial |
| `wound_stage` | Wundstufe |
| `wound_penalty_mod` | Wundmalus verändern |
| `vw` | VW |
| `gw` | GW |
| `sr` | SR |
| `rs` | RS |

## Regel-Flags

Für `target_domain=rule_flag` und Legacy-`target_kind=stat`.

| Slug | Bedeutung |
| --- | --- |
| `wound_penalty_ignore` | Wundmalus ignorieren |
| `armor_penalty_ignore` | Belastung ignorieren |
| `shield_penalty_ignore` | Schildmalus ignorieren |

## Kampf

Für `target_domain=combat`. Legacy-Modifier mit `target_kind=skill` oder `target_kind=stat` und Damage-Slug werden ebenfalls als Combat-Modifier gemappt.

| Slug / Pattern | Bedeutung |
| --- | --- |
| `dmg_*` | Damage-bezogener Modifier, z. B. ein regeldefinierter Damage-Key |

## Fertigkeiten

Für `target_domain=skill` und Legacy-`target_kind=skill`.

| Ziel | Bedeutung |
| --- | --- |
| `Skill.slug` | Slug einer konkreten Fertigkeit aus der Datenbank |
| `target_skill` FK | Legacy-Modifier kann direkt auf eine Fertigkeit zeigen |

## Fertigkeitskategorien

Für `target_domain=skill_category`, `target_domain=proficiency_group` und Legacy-`target_kind=category`.

| Slug | Bedeutung |
| --- | --- |
| `skill_fine_motor` | Feinmotorische Fertigkeiten |
| `skill_gross_motor` | Grobmotorische Fertigkeiten |
| `skill_craft` | Handwerk |
| `skill_social` | Soziale Fertigkeiten |
| `skill_combat` | Waffenfertigkeiten |
| `skill_knowledge` | Wissensfertigkeiten |

## Proficiency Groups

Für `target_domain=proficiency_group`.

| Slug | Bedeutung |
| --- | --- |
| `skill_fine_motor` | Feinmotorische Fertigkeiten |
| `skill_gross_motor` | Grobmotorische Fertigkeiten |
| `skill_social` | Soziale Fertigkeiten |
| `skill_knowledge` | Wissensfertigkeiten |
| `skill_combat` | Waffenfertigkeiten |
| `foreign_languages` | Sprachen außer Muttersprache |

## Sprachen

Für `target_domain=language`.

| Ziel | Bedeutung |
| --- | --- |
| `Language.slug` | Slug einer konkreten Sprache aus der Datenbank |
| `foreign_languages` | Alle Fremdsprachen / Sprachen außer Muttersprache |

## Ressourcen

Für `target_domain=resource`.

| Slug | Bedeutung |
| --- | --- |
| `personal_fame_point` | Persönliche Ruhmpunkte |
| `personal_fame_rank` | Persönlicher Rang |
| `artefact_rank` | Artefaktrang |
| `sacrifice_rank` | Opferrang |

## Items

Für `target_domain=item` und Legacy-`target_kind=item`.

| Ziel | Bedeutung |
| --- | --- |
| Item-ID als String | Konkretes Item, z. B. `42` |
| `target_item` FK | Legacy-Modifier kann direkt auf ein Item zeigen |

## Item-Kategorien

Für `target_domain=item_category` und Legacy-`target_kind=item_category`.

| Slug | Bedeutung |
| --- | --- |
| `armor` | Rüstung |
| `weapon` | Waffe |
| `shield` | Schild |
| `clothing` | Kleidung |
| `magic_item` | Magischer Gegenstand |
| `consumable` | Verbrauchbar |
| `ammo` | Munition |
| `misc` | Misc |

## Spezialisierungen

Für `target_domain=specialization` und Legacy-`target_kind=specialization`.

| Ziel | Bedeutung |
| --- | --- |
| Specialization-ID als String | Konkrete Spezialisierung, z. B. `12` |
| `target_specialization` FK | Legacy-Modifier kann direkt auf eine Spezialisierung zeigen |

## Traits

Für `target_domain=trait`.

| Ziel | Bedeutung |
| --- | --- |
| `Trait.slug` | Slug eines Traits aus der Datenbank |

## Generische Entity-Ziele

Für `target_domain=entity` und Legacy-`target_kind=entity`.

| Ziel | Bedeutung |
| --- | --- |
| `<content_type_id>:<object_id>` | Konkretes beliebiges Django-Model-Objekt |
| `target_content_type` + `target_object_id` | Legacy-Modifier-Selector |

## Freie Regelbereiche

Diese Domains sind gültig, haben aber aktuell keine zentrale statische Slug-Liste. Die Slugs sind regeldefiniert.

| Domain | Bedeutung |
| --- | --- |
| `resistance` | Resistenzen, Immunitäten, Verwundbarkeiten |
| `movement` | Bewegungswerte oder Bewegungsfähigkeiten |
| `perception` | Wahrnehmungs-/Sinnes-Effekte |
| `economy` | Geld, Einkommen, Startmittel |
| `social` | Sozialstatus, Rechtsstatus, soziale Tags |
| `capability` | Faehigkeiten an/aus |
| `behavior` | Regelverhalten |
| `tag` | Tags |
| `metadata` | freie Metadaten |

## Alle Target Domains

Diese Werte sind technisch für `TraitSemanticEffect.target_domain` gültig:

```text
skill
skill_category
language
proficiency_group
trait
attribute
attribute_cap
derived_stat
resource
resistance
movement
combat
perception
economy
social
rule_flag
capability
behavior
tag
metadata
item
item_category
specialization
entity
```

## Legacy Target Kinds

Diese Werte sind für `Modifier.target_kind` gültig:

```text
skill
category
attribute
stat
item
item_category
specialization
entity
```

## Quellen im Code

- `charsheet/constants.py`: feste Attribute, Bogenwerte, Skill-Kategorien, Ressourcen, Domains
- `charsheet/models/items.py`: Item-Kategorien
- `charsheet/models/modifier.py`: Legacy-Modifier-Zielarten und Validierung
- `charsheet/modifiers/definitions.py`: Typed Modifier Domains
- `charsheet/modifiers/migration.py`: Legacy-zu-typed Mapping
