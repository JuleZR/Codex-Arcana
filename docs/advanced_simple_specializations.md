# Zusätzliche einfache Spezialisierungen

Im Lernmenü erscheint „Zusätzliche Spezialisierungen“, sobald mindestens eine
konfigurierte Option verfügbar ist oder ein bezahlter Erwerb verlernt werden kann.
Die Schulstufe bleibt unverändert. Standard: Schulstufe 10, 20 EP, +1 Arkane Macht.

## Konfiguration mit vorhandenen Modellen

Im Admin unter **Progression rules** eine Regel der Art
**Zusätzliche einfache Spezialisierung** anlegen. `school_type` ist der Typ der
besitzenden Kampfschule; `min_level` ist die erforderliche Schulstufe (10).
`amount` wird für diesen Erwerbstyp nicht verwendet. Beispiel für `params`:

```json
{
  "school_id": 17,
  "ep_cost": 20,
  "arcane_power": 1,
  "options": [
    {
      "specialization_id": 18,
      "source_technique_id": 227,
      "required_specialization_ids": [],
      "requirement_lesson_id": null
    }
  ]
}
```

Die IDs müssen auf die Datensätze der jeweiligen Datenbank zeigen. Die vorhandene
`Specialization` definiert die Fähigkeit und ihre normalen Effekte/Auswahlen.
`allow_multiple` erlaubt ausdrücklich mehrere Erwerbe. Bereits bekannte Fähigkeiten
werden ansonsten ausgeschlossen, auch wenn dieselbe Fähigkeit mehrfach als
Definition mit demselben Namen innerhalb der Schule vorliegt.

- `source_technique_id` ist optional. Die normalen Voraussetzungen, Ausschlüsse
  und Pfadbeschränkungen dieser Technik gelten beim Erwerb weiterhin.
- `required_specialization_ids` verlangt alle angegebenen bereits erworbenen
  Spezialisierungen, etwa frühere Mutationen einer Kette.
- `requirement_lesson_id` verweist optional auf eine vorhandene `Lesson`, deren
  `LessonRequirement`-Einträge geprüft werden. Die Lesson selbst wird dabei weder
  erworben noch als bereits gelernt vorausgesetzt. Gruppen behalten ihre
  vorhandene UND-/ODER-Bedeutung.
- `path_id` kann auf Regel-Ebene einen bestimmten Schulpfad voraussetzen,
  beispielsweise Schiffsbauer. Karrierepfad-Talente gehören nicht in diese Regeln.
- `ep_cost` und `arcane_power` lassen sich je Option überschreiben.
- `creature_source_binding_id` erlaubt eine zusätzliche Tiergefährten-Auswahl aus
  einer vorhandenen aktiven `CreatureSourceBinding` derselben Schule. Deren
  Auswahlmodus muss `character_choice` sein. Vorlagefilter und Qualität werden
  übernommen; jeder Erwerb erhält eine eigene Karte.

Weitere Schulen und Schiffsrune-Optionen werden über ihre vorhandenen
Spezialisierungsdefinitionen genauso konfiguriert. Waffenmeister ist ausgeschlossen.
Neue Datenbankmodelle und zusätzliche Felder werden nicht verwendet.

## Erwerb und Verlernen

Die bestehende `CharacterSpecialization` speichert unter dem reservierten Präfix
`advanced_simple:` in `notes` einen JSON-Beleg mit bezahlten EP, zusätzlicher Arkaner
Macht, erforderlicher Schulstufe und optionaler Auswahlbindung. Diesen Beleg bei
manueller Pflege nicht überschreiben. Normale Spezialisierungen behalten ihre
bisherige Bedeutung und verbrauchen weiterhin nur die normalen Slots.

Verlernen erstattet exakt die ursprünglich bezahlten EP, auch nach einer
Kostenänderung der Konfiguration. Die zusätzliche Arkane Macht und die Auswahlen
dieses Erwerbs entfallen. Beim Senken der Schule unter die gespeicherte
Freischaltstufe erfolgt dasselbe automatisch innerhalb der Lerntransaktion.
Spieler verwenden weiterhin die vorhandene EP-Buchhaltung
`overall_experience - current_experience`; NSC verwenden `used_experience`.

## Migrationen

`0417` konfiguriert die vorhandenen Kryss-, Barden-, Tiermeister- und
Seewolf/Schiffsbauer-Daten, soweit die entsprechenden Definitionen existieren.
Für Tiermeister wird eine wiederholbare Spezialisierungsdefinition ergänzt.
Fehlende Schul- oder Regelbuchdaten werden nicht erfunden; ergänzte Optionen müssen
über die obige Konfiguration aufgenommen werden. `0418` passt die bestehende
Eindeutigkeitsregel für Tierkarten an, damit normale Auswahlbindungen einmalig
bleiben und zusätzliche Karten über ihren vorhandenen Effekt-Schlüssel eindeutig
zugeordnet werden können.
