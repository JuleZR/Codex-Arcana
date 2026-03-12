# Engine

Die Regel-Engine liegt in `charsheet/engine/character_engine.py` und `charsheet/engine/character_creation_engine.py` und besteht im Kern aus zwei Klassen:

- `CharacterEngine`: berechnet Werte für bestehende Charaktere
- `CharacterCreationEngine`: validiert und materialisiert Character-Creation-Drafts
- `DiceEngine`: liefert einfache Würfelwürfe und Summen für Würfel-Features

## CharacterEngine

## Aufgaben
- Attributwerte und Attributmodifikatoren liefern
- Skillwerte und Skill-Breakdowns berechnen
- Modifikatoren anhand von Quelle und Ziel auflösen
- Kampfnahe Kernwerte berechnen (Initiative, VW/GW/SR)
- Wundstufen und Wundabzüge aus aktuellem Schaden bestimmen
- Rüstungswerte (`GRS`, `BEL`, `MS`) aus ausgerüsteten Items berechnen
- Hilfswerte für Anzeige liefern (z. B. Münzumrechnung)

## Modifikatorauflösung
- Kernlogik in `_resolve_modifiers(slug)`
- Die Methode summiert aktive `Modifier`, deren Ziel auf den übergebenen Slug passt.
- Aktivität eines Modifikators hängt von seiner Quelle ab (z. B. Trait vorhanden, Technik freigeschaltet, optionale Schulstufen-Grenzen).

## CharacterCreationEngine

## Aufgaben
- Zugriff auf Phasenstatus im Draft (`phase_1` bis `phase_4`)
- Kostenberechnung je Phase (Attribute, Skills, Sprachen, Traits, Schul-/Aspektkäufe)
- Budget- und Regelvalidierung je Phase
- Finalisierung: Erzeugung der finalen Character-Objekte aus dem Draft

## Typischer Ablauf
1. Draft laden
2. Einzelphasen validieren (`validate_phase_1` ... `validate_phase_4`)
3. Bei gültigem Zustand `finalize_character()` ausführen
4. Charakterdatensätze persistieren und Draft entfernen

## DiceEngine

Datei: `charsheet/engine/dice_engine.py`

Zweck:
- Konfigurierbare Würfelwürfe (Anzahl Würfel, Seitenzahl)
- Rückgabe einzelner Wurfergebnisse und Gesamtsumme
