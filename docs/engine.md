# Engine

Die Regel-Engine liegt in `charsheet/engine/engine.py` und besteht im Kern aus zwei Klassen:

- `CharacterEngine`: berechnet Werte fuer bestehende Charaktere
- `CharacterCreationEngine`: validiert und materialisiert Character-Creation-Drafts

## CharacterEngine

## Aufgaben
- Attributwerte und Attributmodifikatoren liefern
- Skillwerte und Skill-Breakdowns berechnen
- Modifikatoren anhand von Quelle und Ziel aufloesen
- Kampfnahe Kernwerte berechnen (Initiative, VW/GW/SR)
- Wundstufen und Wundabzuege aus aktuellem Schaden bestimmen
- Ruestungswerte (`GRS`, `BEL`, `MS`) aus ausgeruesteten Items berechnen
- Hilfswerte fuer Anzeige liefern (z. B. Muenzumrechnung)

## Modifikatoraufloesung
- Kernlogik in `_resolve_modifiers(slug)`
- Die Methode summiert aktive `Modifier`, deren Ziel auf den uebergebenen Slug passt.
- Aktivitaet eines Modifikators haengt von seiner Quelle ab (z. B. Trait vorhanden, Technik freigeschaltet, optionale Schulstufen-Grenzen).

## CharacterCreationEngine

## Aufgaben
- Zugriff auf Phasenstatus im Draft (`phase_1` bis `phase_4`)
- Kostenberechnung je Phase (Attribute, Skills, Sprachen, Traits, Schul-/Aspektkaeufe)
- Budget- und Regelvalidierung je Phase
- Finalisierung: Erzeugung der finalen Character-Objekte aus dem Draft

## Typischer Ablauf
1. Draft laden
2. Einzelphasen validieren (`validate_phase_1` ... `validate_phase_4`)
3. Bei gueltigem Zustand `finalize_character()` ausfuehren
4. Charakterdatensaetze persistieren und Draft entfernen
