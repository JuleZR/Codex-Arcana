# Semantic Effects

Diese Referenz beschreibt, wie neue regeltechnische Effekte im Admin gepflegt werden.
Sie gilt fuer `TraitSemanticEffect` und `TechniqueSemanticEffect`.

## Schnellstart: Welchen Effect brauche ich?

| Regeltext sagt... | Nimm `target_domain` | Beispiel |
| --- | --- | --- |
| "bekommt +1 auf Fertigkeit X" | `skill` | Reiten +1 als Modifikator |
| "erhoeht den Rang von Fertigkeit X" | `skill_rank` | Beruf Bildhauer Rang +1 |
| "darf Fertigkeit X ueber 10 steigern" | `skill_rank_cap` | Maximum 10 -> 15 |
| "bekommt +1 auf eine Eigenschaft" | `attribute` | ST +1 |
| "darf eine Eigenschaft hoeher steigern" | `attribute_cap` | GE-Max +1 |
| "bekommt +2 Initiative" | `derived_stat` | Initiative +2 |
| "ignoriert Belastung/Wunden/Regel X" | `rule_flag` | `armor_penalty_ignore` |
| "bekommt Schaden/Parade/Kampfwert" | `combat` | Waffenschaden +1 |
| "bekommt Bewegung" | `movement` | Sprint +2 |
| "bekommt sozialen Status/Tag" | `social` | Adel, Gesucht, Patron |

Wenn du unsicher bist, frage zuerst:

1. Soll der Wert automatisch steigen? Dann `skill`, `skill_rank`, `attribute`, `derived_stat`, usw.
2. Soll nur das Maximum steigen, damit der Spieler es kaufen kann? Dann eine `*_cap`-Domain.
3. Soll es nur unter einer Bedingung gelten? Dann `condition_set` oder Spezifikations-`metadata`.

## Grundidee

Ein Semantic Effect sagt:

- **Quelle**: Trait oder Technik, an der der Effect haengt.
- **Ziel**: `target_domain` + `target_key`.
- **Wirkung**: `operator`, `mode`, `value`, optional `scaling`.
- **Einschraenkung**: optional `metadata`, `condition_set` oder Choice-Bindings.

Legacy-`Modifier` bleiben fuer alte Daten erhalten. Neue Regeln sollten als Semantic Effects gepflegt werden.

## Wichtige Felder

| Feld | Bedeutung |
| --- | --- |
| `target_domain` | Welche Art von Ziel betroffen ist, z. B. `skill`, `skill_rank`, `skill_rank_cap`, `derived_stat`, `rule_flag`. |
| `target_key` | Slug/Key des Ziels, z. B. `skill_job`, `initiative`, `armor_penalty_ignore`. |
| `operator` | Wie der Wert wirkt. Meist `flat_add`. |
| `mode` | `flat` fuer festen Wert, `scaled` fuer Wert aus einer Quelle wie Schullevel. |
| `value` | Basiswert. Bei `scaled` ist das der Faktor pro Skalenwert. |
| `value_min` / `value_max` | Untere/obere Begrenzung des berechneten Effektwerts. |
| `scaling` | JSON fuer skalierte Effekte. |
| `metadata` | JSON fuer Zusatzregeln, z. B. Skill-Spezifikation oder Lernkosten ueber 10. |
| `target_choice_definition` | Optional: Effect wirkt auf das Ergebnis einer Technik-Choice statt auf einen festen `target_key`. |
| `target_skills` | Optional: Mehrfachauswahl konkreter Skills. Nutze das statt `target_key`, wenn derselbe Effect auf mehrere einzelne Fertigkeiten wirken soll. |

## Admin-Ablauf

### Technik-Effect anlegen

1. Admin -> Technik oeffnen.
2. Falls die Technik automatisiert wirken soll: `support_level = Automated`.
3. Falls die Technik passiv dauerhaft wirken soll: `technique_type = Passive`.
4. Falls eine konkrete Spezifikation an der gelernten Technik gebraucht wird: `has_specification = True`.
5. Im Inline **Semantic Effects** eine neue Zeile anlegen.
6. `target_domain`, `target_key` oder `target_skills`, `operator`, `mode`, `value` setzen.
7. Bei skalierten Effekten `scaling` setzen.
8. Bei spezifizierten Skills `metadata` setzen.

### Trait-Effect anlegen

1. Admin -> Trait oeffnen.
2. Im Inline **Semantic Effects** eine neue Zeile anlegen.
3. Felder wie bei Technik-Effects setzen.
4. Fuer Trait-Level-Skalierung `scale_source = trait_level` nutzen.

## Standard-Feldwerte

Die haeufigste Kombination ist:

```text
operator: flat_add
mode: flat
value: 1
stack_behavior: stack
active_flag: true
visibility: public
sheet_relevant: true
```

Fuer skalierte Effekte:

```text
operator: flat_add
mode: scaled
value: 1
scaling: {"scale_source":"school_level","mul":1,"div":2,"round_mode":"floor"}
```

`value` ist bei `scaled` der Basisfaktor. Bei Schullevel 4, `value=1`, `div=2` entsteht `floor(4 * 1 / 2) = 2`.

## Skill-Ziele

Du hast drei praktische Ziel-Arten:

- Einzelner Slug: `target_key = skill_job`.
- Mehrere konkrete Skills: `target_skills` aus der Skill-Auswahl befuellen und `target_key` leer lassen.
- Choice-Ziel: `target_choice_definition` setzen und `target_key` leer lassen.

`target_skills` funktioniert fuer `skill`, `skill_rank` und `skill_rank_cap`. Damit kannst du z. B. Singen, Tanzen, Musizieren, Malen, Handwerk und Mode in einem einzigen Effect auswaehlen, sofern dieselbe Regel fuer alle gilt.

Beispiel: alle ausgewaehlten Skills duerfen +1 ueber Maximum lernen:

```text
target_domain: skill_rank_cap
target_key: leer lassen
target_skills: Singen, Tanzen, Musizieren, Malen, Handwerk, Mode
operator: flat_add
mode: flat
value: 1
metadata: {"above_base_cap_cost_ep":8}
```

Wenn ein Skill eine Spezifikation braucht, z. B. `Handwerk: Bildhauer`, setzt du zusaetzlich:

```json
{"skill_specification":"Bildhauer"}
```

Bei einer Technik mit eigener Spezifikation wird fuer Skill-Effekte automatisch diese Technik-Spezifikation verwendet. Wenn der Effect trotz spezifizierter Technik auf unspezifizierte Skills wirken soll, setze:

```json
{"skill_specification_source":""}
```

### `target_domain = skill`

Gibt einen normalen Skill-Modifikator. Das erscheint als Mod/Misc-Bonus, nicht als Rang.

Beispiel: `+1` auf Beruf Bildhauer als Modifikator:

```text
target_domain: skill
target_key: skill_job
operator: flat_add
mode: flat
value: 1
metadata: {"skill_specification":"Bildhauer"}
```

Ergebnis:

```text
Rang 10, Mod +1
```

### `target_domain = skill_rank`

Erhoeht den Skillrang selbst. Das ist kein Misc-Modifikator.

Beispiel: `+1` Rang auf Beruf Bildhauer:

```text
target_domain: skill_rank
target_key: skill_job
operator: flat_add
mode: flat
value: 1
metadata: {"skill_specification":"Bildhauer"}
```

Ergebnis:

```text
Rang 10 + 1 Effekt = Rang 11
```

### `target_domain = skill_rank_cap`

Erhoeht das lernbare Maximum. Das gibt keinen automatischen Bonus, sondern erlaubt Lernen ueber Rang 10 hinaus.

Beispiel: Beruf Bildhauer darf bis 12 gelernt werden:

```text
target_domain: skill_rank_cap
target_key: skill_job
operator: flat_add
mode: flat
value: 2
metadata:
{
  "skill_specification": "Bildhauer",
  "above_base_cap_cost_ep": 8
}
```

Ergebnis:

```text
Beruf Bildhauer kann bis Rang 12 gelernt werden.
Rang 11 und 12 kosten je 8 EP.
```

## Skill-Spezifikationen

Fuer Skills wie Beruf/Handwerk, die mehrere Spezifikationen haben koennen, wird die Spezifikation in `metadata` gesetzt:

```json
{"skill_specification":"Bildhauer"}
```

Das wirkt nur auf diese eine Zeile:

```text
Beruf Bildhauer
```

Nicht auf:

```text
Beruf Baecker
Beruf Schmied
Beruf *
```

Wenn ein aktiver Effect eine spezifizierte Skill-Zeile braucht und sie fehlt, wird automatisch ein echter `CharacterSkill` mit `level=0` und dieser Spezifikation angelegt. Faellt der Effect weg, wird dieser Level-0-Eintrag wieder entfernt. Wurde der Skill inzwischen regulaer gesteigert (`level > 0`), bleibt er erhalten.

## Skalierung

### Nach Schullevel

Bei Technik-Effects kann `school_level` automatisch die Schule der Technik verwenden.

Beispiel: `+1` pro Schulstufe:

```text
mode: scaled
value: 1
scaling:
{
  "scale_source": "school_level",
  "mul": 1,
  "div": 1,
  "round_mode": "floor"
}
```

Beispiel: `+1` pro 2 Schulstufen:

```text
mode: scaled
value: 1
scaling:
{
  "scale_source": "school_level",
  "mul": 1,
  "div": 2,
  "round_mode": "floor"
}
```

Mit `value_max` kann der Bonus begrenzt werden:

```text
value_max: 5
```

## Beispiel: Liondrielle-Perfektion

Regel: Bestimmte kuenstlerische/gesellschaftliche/musische Fertigkeiten duerfen fuer alle 2 Magieschulstufen um 1 Rang ueber 10 hinaus gelernt werden, maximal bis 15. Jeder Rang ueber 10 kostet 8 EP.

Fuer Beruf Bildhauer:

```text
target_domain: skill_rank_cap
target_key: skill_job
operator: flat_add
mode: scaled
value: 1
value_max: 5
scaling:
{
  "scale_source": "school_level",
  "mul": 1,
  "div": 2,
  "round_mode": "floor"
}
metadata:
{
  "skill_specification": "Bildhauer",
  "above_base_cap_cost_ep": 8
}
```

Auswirkung:

| Schullevel | Extra-Max | Lernmaximum |
| --- | ---: | ---: |
| 2 | +1 | 11 |
| 4 | +2 | 12 |
| 6 | +3 | 13 |
| 8 | +4 | 14 |
| 10 | +5 | 15 |

Wichtig: Das ist kein automatischer Bonus. Der Charakter muss die Ränge 11-15 im Lernmenue bezahlen.

## Praxis-Cookbook

### 1. Fester Skillbonus

Regeltext:

```text
Der Charakter erhaelt +2 auf Heimlichkeit.
```

Effect:

```text
target_domain: skill
target_key: skill_sneak
operator: flat_add
mode: flat
value: 2
```

Ergebnis:

```text
Rang bleibt gleich.
Misc/Mod +2.
Gesamtwert steigt um 2.
```

### 2. Skillbonus nur fuer eine Beruf-Spezifikation

Regeltext:

```text
Der Charakter erhaelt +1 auf Beruf: Bildhauer.
```

Effect:

```text
target_domain: skill
target_key: skill_job
operator: flat_add
mode: flat
value: 1
metadata: {"skill_specification":"Bildhauer"}
```

Ergebnis:

```text
Beruf Bildhauer: +1
Beruf Baecker: kein Bonus
Beruf *: kein Bonus
```

### 3. Skillrang automatisch erhoehen

Regeltext:

```text
Der Charakter gilt in Beruf: Bildhauer als um 1 Rang hoeher.
```

Effect:

```text
target_domain: skill_rank
target_key: skill_job
operator: flat_add
mode: flat
value: 1
metadata: {"skill_specification":"Bildhauer"}
```

Ergebnis:

```text
Gekauft: Rang 10
Effekt: Rang +1
Anzeige/Berechnung: Rang 11
Misc-Mod: 0
```

### 4. Skillmaximum erhoehen

Regeltext:

```text
Beruf: Bildhauer darf bis Rang 12 gesteigert werden.
Rang ueber 10 kostet 8 EP.
```

Effect:

```text
target_domain: skill_rank_cap
target_key: skill_job
operator: flat_add
mode: flat
value: 2
metadata:
{
  "skill_specification": "Bildhauer",
  "above_base_cap_cost_ep": 8
}
```

Ergebnis:

```text
Lernmaximum: 12
Rang 11 kostet 8 EP
Rang 12 kostet 8 EP
Kein automatischer Bonus
```

### 5. Skillmaximum nach Schullevel

Regeltext:

```text
Fuer alle 2 Schulstufen darf Beruf: Bildhauer um 1 Rang ueber 10 hinaus gelernt werden, maximal +5.
```

Effect:

```text
target_domain: skill_rank_cap
target_key: skill_job
operator: flat_add
mode: scaled
value: 1
value_max: 5
scaling:
{
  "scale_source": "school_level",
  "mul": 1,
  "div": 2,
  "round_mode": "floor"
}
metadata:
{
  "skill_specification": "Bildhauer",
  "above_base_cap_cost_ep": 8
}
```

Ergebnis:

```text
Schullevel 2 -> Max 11
Schullevel 4 -> Max 12
Schullevel 6 -> Max 13
Schullevel 8 -> Max 14
Schullevel 10 -> Max 15
```

### 6. Automatischer Skillrang nach Schullevel

Regeltext:

```text
Beruf: Bildhauer gilt fuer alle 2 Schulstufen als um 1 Rang hoeher.
```

Effect:

```text
target_domain: skill_rank
target_key: skill_job
operator: flat_add
mode: scaled
value: 1
value_max: 5
scaling:
{
  "scale_source": "school_level",
  "mul": 1,
  "div": 2,
  "round_mode": "floor"
}
metadata:
{
  "skill_specification": "Bildhauer"
}
```

Ergebnis:

```text
Schullevel 4 und gekaufter Rang 10 -> effektiver Rang 12
```

### 7. Technik mit frei eingetragener Spezifikation

Regeltext:

```text
Beim Lernen der Technik wird eine Spezifikation eingetragen.
Der Effect wirkt auf genau diese Spezifikation.
```

Technik:

```text
has_specification: true
```

CharacterTechnique:

```text
specification_value: Bildhauer
```

Effect:

```text
target_domain: skill_rank
target_key: skill_job
operator: flat_add
mode: flat
value: 1
metadata:
{
  "skill_specification_source": "technique_specification"
}
```

Ergebnis:

```text
Die Technik-Spezifikation "Bildhauer" wird als Skill-Spezifikation verwendet.
```

### 8. Bonus auf ausgewaehlten Skill einer Technik-Choice

Regeltext:

```text
Waehle eine Fertigkeit. Diese Fertigkeit erhaelt +1.
```

Technik-Choice:

```text
TechniqueChoiceDefinition target_kind: Skill
```

Effect:

```text
target_domain: skill
target_key: leer lassen
target_choice_definition: <die Skill-Choice>
operator: flat_add
mode: flat
value: 1
```

Ergebnis:

```text
Der Bonus landet auf dem vom Charakter gewaehlten Skill.
```

### 9. Ausgewaehlter Skill bekommt Rang-Bonus

Regeltext:

```text
Waehle eine Fertigkeit. Sie gilt als 1 Rang hoeher.
```

Effect:

```text
target_domain: skill_rank
target_key: leer lassen
target_choice_definition: <die Skill-Choice>
operator: flat_add
mode: flat
value: 1
```

### 10. Ausgewaehlter Skill darf hoeher gelernt werden

Regeltext:

```text
Waehle eine Fertigkeit. Sie darf bis Rang 12 gelernt werden.
```

Effect:

```text
target_domain: skill_rank_cap
target_key: leer lassen
target_choice_definition: <die Skill-Choice>
operator: flat_add
mode: flat
value: 2
metadata:
{
  "above_base_cap_cost_ep": 8
}
```

### 11. Attributbonus

Regeltext:

```text
ST +1.
```

Effect:

```text
target_domain: attribute
target_key: ST
operator: flat_add
mode: flat
value: 1
```

### 12. Attributmaximum erhoehen

Regeltext:

```text
GE darf um 1 hoeher gesteigert werden.
```

Effect:

```text
target_domain: attribute_cap
target_key: GE
operator: flat_add
mode: flat
value: 1
```

### 13. Initiativebonus

Regeltext:

```text
Initiative +2.
```

Effect:

```text
target_domain: derived_stat
target_key: initiative
operator: flat_add
mode: flat
value: 2
```

### 14. Wunden ignorieren

Regeltext:

```text
Der Charakter ignoriert Wundabzuege.
```

Effect:

```text
target_domain: rule_flag
target_key: wound_penalty_ignore
operator: set_flag
mode: flat
value: true
```

### 15. Ruestungsbelastung ignorieren

Regeltext:

```text
Ruestungsbelastung wird ignoriert.
```

Effect:

```text
target_domain: rule_flag
target_key: armor_penalty_ignore
operator: set_flag
mode: flat
value: true
```

### 16. Schildmalus ignorieren

Regeltext:

```text
Schildmalus wird ignoriert.
```

Effect:

```text
target_domain: rule_flag
target_key: shield_penalty_ignore
operator: set_flag
mode: flat
value: true
```

### 17. Bewegungswert erhoehen

Regeltext:

```text
Sprintgeschwindigkeit +2.
```

Effect:

```text
target_domain: movement
target_key: ground_sprint
operator: flat_add
mode: flat
value: 2
```

### 18. Widerstand / Resistenz

Regeltext:

```text
Feuerresistenz +3.
```

Effect:

```text
target_domain: resistance
target_key: fire
operator: flat_add
mode: flat
value: 3
```

### 19. Immunitaet

Regeltext:

```text
Immun gegen Gift.
```

Effect:

```text
target_domain: resistance
target_key: poison
operator: grant_immunity
mode: flat
value: true
```

### 20. Verwundbarkeit

Regeltext:

```text
Verwundbarkeit gegen Feuer 2.
```

Effect:

```text
target_domain: resistance
target_key: fire
operator: grant_vulnerability
mode: flat
value: 2
```

### 21. Soziales Tag

Regeltext:

```text
Der Charakter gilt als adelig.
```

Effect:

```text
target_domain: social
target_key: status
operator: add_tag
mode: flat
value: noble
```

### 22. Capability

Regeltext:

```text
Der Charakter kann im Dunkeln sehen.
```

Effect:

```text
target_domain: capability
target_key: darkvision
operator: grant_capability
mode: flat
value: true
```

### 23. Oekonomie / Startgeld

Regeltext:

```text
Startgeld +50.
```

Effect:

```text
target_domain: economy
target_key: starting_funds
operator: flat_add
mode: flat
value: 50
```

### 24. Resource-Cap

Regeltext:

```text
Arkane Macht Maximum +2.
```

Effect:

```text
target_domain: resource
target_key: arcane_power
operator: change_resource_cap
mode: flat
value: 2
```

Hinweis: Nicht jeder Resource-Effect ist schon in jeder UI gleich sichtbar. Wenn ein Resource-Wert nicht reagiert, muss die konkrete Anzeige/Engine-Stelle noch angebunden werden.

### 25. Bedingter Effect

Regeltext:

```text
+2 auf Wahrnehmung bei Dunkelheit.
```

Effect:

```text
target_domain: perception
target_key: perception
operator: conditional_bonus
mode: flat
value: 2
condition_set:
{
  "applies_in_darkness": true
}
```

Hinweis: Conditions wirken nur dort, wo die aufrufende Engine auch passenden Kontext uebergibt.

## Beispiel: Automatischer Rang statt Lernmaximum

Wenn eine Technik den Rang selbst erhoehen soll:

```text
target_domain: skill_rank
target_key: skill_job
operator: flat_add
mode: scaled
value: 1
value_max: 5
scaling:
{
  "scale_source": "school_level",
  "mul": 1,
  "div": 2,
  "round_mode": "floor"
}
metadata:
{
  "skill_specification": "Bildhauer"
}
```

Auswirkung bei Schullevel 4:

```text
Beruf Bildhauer Rang 10 wird als Rang 12 angezeigt.
```

## Beispiel: Normaler Skill-Modifikator

Wenn wirklich nur ein Bonus auf den Wurf/Skillwert gemeint ist:

```text
target_domain: skill
target_key: skill_job
operator: flat_add
mode: flat
value: 2
metadata:
{
  "skill_specification": "Bildhauer"
}
```

Auswirkung:

```text
Rang bleibt gleich.
Modifikator +2.
Gesamtwert steigt um 2.
```

## Choice-Bound Effects

Wenn der Effect auf eine ausgewaehlte Fertigkeit aus einer Technik-Choice wirken soll:

```text
target_domain: skill
target_key: leer lassen
target_choice_definition: <Choice Definition der Technik>
operator: flat_add
mode: flat
value: 1
```

Dann wirkt der Effect auf den Skill, den der Charakter in dieser Choice gewaehlt hat.

Wenn zusaetzlich eine Spezifikation noetig ist:

```json
{"skill_specification":"Bildhauer"}
```

Oder bei einer Technik mit eigener Spezifikation kann die Technik-Spezifikation automatisch genutzt werden:

```json
{"skill_specification_source":"technique_specification"}
```

## Weitere haeufige Domains

### `derived_stat`

Beispiel: Initiative +2:

```text
target_domain: derived_stat
target_key: initiative
operator: flat_add
mode: flat
value: 2
```

### `attribute`

Beispiel: ST +1:

```text
target_domain: attribute
target_key: ST
operator: flat_add
mode: flat
value: 1
```

### `attribute_cap`

Beispiel: GE-Maximum +1:

```text
target_domain: attribute_cap
target_key: GE
operator: flat_add
mode: flat
value: 1
```

### `rule_flag`

Beispiel: Belastung ignorieren:

```text
target_domain: rule_flag
target_key: armor_penalty_ignore
operator: set_flag
mode: flat
value: true
```

### `combat`

Beispiel: Schaden +1:

```text
target_domain: combat
target_key: weapon_damage
operator: flat_add
mode: flat
value: 1
```

## Operatoren

| Operator | Zweck |
| --- | --- |
| `flat_add` | Addiert den Wert. Standard fuer Zahlen. |
| `flat_sub` | Zieht den Wert ab. |
| `multiply` | Multipliziert den aktuellen Wert. Nur gezielt verwenden. |
| `override` | Ueberschreibt den Wert. Vorsichtig verwenden. |
| `min_value` | Erzwingt einen Mindestwert. |
| `max_value` | Erzwingt einen Hoechstwert. |
| `set_flag` | Setzt ein Regel-Flag. |
| `unset_flag` | Entfernt/unterdrueckt ein Regel-Flag. |
| `add_tag` | Fuegt ein Tag hinzu. |
| `remove_tag` | Entfernt ein Tag. |

## Regeln fuer die Wahl der Domain

| Du willst... | Verwende |
| --- | --- |
| Einen Skillwert-Bonus geben | `skill` |
| Einen Skillrang automatisch erhoehen | `skill_rank` |
| Das lernbare Skillmaximum erhoehen | `skill_rank_cap` |
| Eine ganze Skillkategorie modifizieren | `skill_category` |
| Ein Attribut veraendern | `attribute` |
| Ein Attributmaximum veraendern | `attribute_cap` |
| Einen abgeleiteten Wert veraendern | `derived_stat` |
| Eine Regel an-/abschalten | `rule_flag` |
| Kampfwerte veraendern | `combat` |

## Stolperfallen

- `skill` ist ein Modifikator, kein Rang.
- `skill_rank` ist ein automatischer Rang-Bonus, aber nicht gelernt/gekauft.
- `skill_rank_cap` erlaubt Lernen ueber 10, gibt aber keinen Bonus.
- Spezifikationspflichtige Skills brauchen `metadata.skill_specification`, wenn nur eine bestimmte Spezifikation betroffen ist.
- `target_key` darf nur leer bleiben, wenn ein `target_choice_definition` gesetzt ist.
- Bei `scaled` immer `scaling.scale_source` setzen.
- Fuer `school_level` an Technik-Effects muss die Technik einer Schule gehoeren.
