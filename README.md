# Codex Arcana

Digitales Verwaltungssystem fuer das Pen-and-Paper-Rollenspiel **Arcane Codex**, umgesetzt mit Django.

Der aktuelle Stand ist ein Backend mit Admin-Oberflaeche und Regel-Engine fuer zentrale Charakterwerte.

## Was aktuell funktioniert

### Projektstatus
- Django-Projekt laeuft mit PostgreSQL.
- Datenmodell ist ueber Migrationen aufgebaut.
- Django-Admin ist fuer die Kernmodelle eingerichtet.
- Codebasis ist durchgaengig mit Docstrings dokumentiert

### Fachlich umgesetzt
- Charakterstamm: `Character`, `Race`, Attribute, Skills.
- Regelgrenzen: Race-Attribute-Limits und Validierungen.
- Schulen/Progression: `SchoolType`, `School`, `CharacterSchool`, `ProgressionRule`, `Technique`.
- Modifikatoren: generisches `Modifier`-Modell fuer Skill/Category/Stat.
- Inventar: `Item`, `CharacterItem`, `ArmorStats`.

### Berechnungen in der Engine
- Attribut-Modifikatoren.
- Skill-Gesamtwerte inkl. externer Modifikatoren.
- Abwehrwerte (`VW`, `GW`, `SR`).
- Initiative.
- Magiebezogene Werte (`arcane_power`, `potential`).
- Wundstufen und aktive Wundabzuege.
- Ruestungswerte (`GRS`, `BEL`, `MS`) auf Basis ausgeruesteter Ruestung.

## Schnellstart (Entwicklung)

### Voraussetzungen
- Python 3.x
- PostgreSQL (lokal auf `localhost:5432`) oder per Docker
- Installierte Python-Abhaengigkeiten in deiner Umgebung

### Datenbank starten (optional via Docker)
```bash
docker compose up -d db
```

### Django starten
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Danach ist das Admin-Backend unter `http://127.0.0.1:8000/admin/` erreichbar.

## Roadmap

### Bereits erreicht
- [x] Kern-Datenmodell fuer Charaktere, Attribute, Skills und Rassen
- [x] Erste regelbasierte Engine-Berechnungen
- [x] Wundsystem mit Penalty-Logik
- [x] Schulen, Techniken und Progressionsregeln
- [x] Grundlegendes Inventar inkl. Ruestungswerten
- [x] Basis-Ruestungsberechnung (`GRS`, `BEL`, `MS`)
- [x] Docstring-Dokumentation der Projektmodule
- [x] Ruestungsregeln vervollstaendigen (Belastung, Mindeststaerke, Auswirkungen auf Proben)

### Als naechstes
- [ ] Charaktererschaffung mit Budget-/Regelvalidierung (CP/EP-Flow)
- [ ] Waffenmodell und Kampfwerte erweitern
- [ ] Magiesystem erweitern (Kosten, Verbrauch, Anzeige)
- [ ] Tests ausbauen (Modelle, Engine, Admin)
- [ ] Benutzeroberflaeche ausserhalb des Django-Admins aufbauen
