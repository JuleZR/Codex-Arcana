# Codex Arcana

Ein digitales Verwaltungssystem für das Pen-&-Paper-Rollenspiel **Arcane Codex**, entwickelt mit Django.

## Aktueller Fokus
Das Projekt befindet sich in der frühen Prototyp-Phase. Aktuell liegt der Schwerpunkt auf der Abbildung der Kern-Regelmechaniken im Datenmodell:
- Dynamische Rassen- und Attributlogik.
- Modulares Sprach- und Fertigkeitensystem.
- Validierung von Charakterwerten gegen Regel-Constraints.

## Disclaimer
Dies ist ein privates Entwicklungsprojekt. Eine lauffähige Version für Endanwender oder eine vollständige Dokumentation folgt in späteren Meilensteinen.

# Arcane Codex – Character Sheet Roadmap

Ziel: Ein vollwertiger Charakterbogen mit automatischen Berechnungen.

Prinzipien:
- Models speichern nur Rohdaten.
- Engine berechnet alles als Snapshot (read-only).
- Keine abgeleiteten Werte persistieren (sonst Inkonsistenz-Hölle).
- Jede Regelberechnung ist zentral nachvollziehbar (optional mit Explain/Debug).

---

## Architektur (Minimal)

Django (Daten):
- `Character`, `CharacterAttribute`, `CharacterSkill`, …

Engine (Logik):
- `compute_snapshot(character)` → liefert finale Werte + optional Erklärungen.

Admin/UI:
- Zeigt Werte aus dem Snapshot an (keine Model-Properties als Regelmaschine).

---

## Phasen & Milestones

### Phase 1: Fundament (Datenmodell)
Milestone M1: Charakterdaten speicherbar und editierbar

- [x] Attribute (St, Kon, Ge, Wa, Int, Will, Cha)
- [x] SkillCategory
- [x] Skill (base_attribute, category)
- [x] Race
- [x] RaceAttributeLimit (race, attribute, max_value)
- [x] Character (name, owner, race, …)
- [x] CharacterAttribute (character, attribute, base_value)
- [x] CharacterSkill (character, skill, rank)

---

### Phase 2: Erste Engine (nur Kernwerte)
Milestone M2: Snapshot liefert Attribute final + Mods + VW/SR/GW

- [x] Engine-Modul anlegen: `charsheet/engine/` oder `charsheet/engine.py`
- [x] `compute_snapshot(character)` (minimal)
- [x] Attribut-Finalwerte = Base (erstmal ohne Mods)
- [x] Eigenschafts-Mod: `mod = final_value - 5`
- [X] Widerstandswerte:
  - [X] VW = 14 + GE_mod + WA_mod (+ GK_mod später)
  - [X] SR = 14 + ST_mod + KON_mod
  - [X] GW = 14 + INT_mod + WILL_mod

---

### Phase 3: Wunden & Zustände (erste echte Abzüge)
Milestone M3: Wunden beeinflussen Werte zuverlässig

- [x] Damage/Wunden am Charakter speichern (z.B. current_damage)
- [x] Wundstufen berechnen
- [x] Abzüge als Snapshot-Regeln anwenden (z.B. auf alle Aktionen/INI)

---

### Phase 4: Rüstung & Belastung
Milestone M4: GRS/BEL/MS korrekt + Auswirkungen auf Werte

- [ ] ArmorPiece/Loadout minimal modellieren
- [ ] GRS berechnen (RS-Zonen / 6)
- [ ] BEL = GRS / 3
- [ ] Mindeststärke = GRS / 2
- [ ] “mit Belastung” Anzeige (Skills/Probenwert - BEL) als Snapshot-View

---

### Phase 5: Charaktererschaffung (Punktkauf-Flow)
Milestone M5: Regelkonforme Erstellung mit Validierung

- [ ] CP/EP Budgets (MVP: nur CP)
- [ ] Kostenfunktionen für Skills (delta-basiert)
- [ ] Sprachen: sprechen 1/2/3, lesen+1, schreiben+1
- [ ] Validierung: Race-Limits, Budget nicht negativ, Ranggrenzen

---

### Phase 6: Schulen & Ressourcen (KP)
Milestone M6: Schulen-Stufen + KP_max

- [x] School, CharacterSchool
- [X] KP_max berechnen (WILL_mod + Schulstufen + Mods)
- [X] (optional) Aspekte für Kleriker


---

### Phase 7: Ausrüstung (Waffen etc.)
Milestone M7: Waffenwerte und Anzeige im Bogen

- [ ] Weapon Modell + Zuordnung
- [ ] Basiswerte anzeigen (Schaden, Typ, MinSt, Reichweite, …)
- [ ] (optional) Manöverhilfe später

---

### Phase 8: Magie (optional, später)
Milestone M8: Zauber DB + KP-Kosten + MW-Anzeige

- [X] Spell Modell + Zuordnung zu Schule/Aspekt
- [ ] MW/Kosten/Probeanzeigen
- [ ] KP-Verbrauch tracken (KP_used)

