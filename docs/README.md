# Dokumentation

Diese Dokumentation beschreibt den aktuellen technischen Stand von Codex Arcana. Sie ist bewusst auf die heutige Codebasis ausgerichtet und erklärt nicht nur, welche Dateien existieren, sondern auch, welche Verantwortung sie im Gesamtsystem tragen.

## Zielgruppe

- Entwickler:innen, die das Projekt lokal starten oder weiterentwickeln wollen
- Maintainer, die Regeln, Datenmodell oder UI-Flows anpassen müssen
- Mitwirkende, die die neue Modulaufteilung erst einmal verstehen wollen

## Inhalte

- [Setup](setup.md)  
  Lokale Einrichtung, Datenbank, Startbefehle und typische Wartungs-Kommandos.
- [Architektur](architecture.md)  
  Überblick über Schichten, Modulgrenzen und den Datenfluss zwischen View, Kontextaufbereitung und Engine.
- [Datenmodell](models.md)  
  Beschreibung der aufgeteilten Modellpakete, Beziehungen und Validierungsregeln.
- [Engine](engine.md)  
  Erklärt `CharacterEngine`, `ItemEngine`, die Lernlogik und das Zusammenspiel der Engine-Hilfsmodule.
- [Routen und Views](routes.md)  
  HTTP-Endpunkte, Antwortformate und die heutigen UI-/JSON-Flows.
- [Rechtliches](legal.md)  
  Hinweise zu Impressum, Datenschutz und Self-Hosting-Konfiguration.

## Was sich gegenüber alter Dokumentation geändert hat

Die frühere Doku ging noch von einer kompakteren Struktur aus. Inzwischen wurden mehrere Bereiche fachlich getrennt:

- Modelle liegen in `charsheet/models/` statt in einer einzelnen Datei.
- Die Character-Engine nutzt Hilfsmodule für Kampf, Ausrüstung und Progression.
- Das Character Sheet wird über `sheet_context.py` vorbereitet.
- Lernen, Shop und Tagebuch besitzen eigene Logik und teilweise eigene JSON-Endpunkte.
- Technik-, Choice- und Spezialisierungsmodelle sind deutlich umfangreicher geworden.

## Pflegehinweise

- Bei neuen URL- oder Antwortformaten immer `routes.md` aktualisieren.
- Bei fachlichen Regeln oder Engine-Änderungen `engine.md` nachziehen.
- Bei neuen oder umgebauten Modellen `models.md` anpassen.
- Bei größeren Strukturverschiebungen zuerst `architecture.md` aktualisieren.
