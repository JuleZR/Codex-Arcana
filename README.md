# Codex Arcana

Digitales Verwaltungssystem fuer das Pen-and-Paper-Rollenspiel **Arcane Codex**, umgesetzt mit Django.

Der Fokus liegt aktuell auf Charakterverwaltung, Regelberechnungen und einer spielbaren Character-Sheet-Oberflaeche.

## Projektstatus
- Django-Projekt mit PostgreSQL laeuft lokal.
- Kernmodelle und Migrationen sind vorhanden.
- Django-Admin ist fuer die wichtigsten Entitaeten konfiguriert.
- Character Sheet zeigt Werte, Inventar, Waffen, Ruestung, Sprachen, Traits und Shop-Funktionen.
- Engine berechnet zentrale Regelwerte (Attribute, Skills, Initiative, Abwehr, Wunden, Ruestung).

## Schnellstart

### Voraussetzungen
- Python 3.x
- PostgreSQL auf `localhost:5432` oder Docker
- Installierte Python-Abhaengigkeiten (aktuell keine lock/requirements-Datei im Repo)

### Datenbank via Docker starten (optional)
```bash
docker compose up -d db
```

### Django starten
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Danach:
- Admin: `http://127.0.0.1:8000/admin/`
- Character Sheet: `http://127.0.0.1:8000/sheet/`

## Projektstruktur
```text
codex_arcana/              Django-Projektkonfiguration (settings, urls, wsgi/asgi)
charsheet/                 Fachlogik (Modelle, Views, Admin, Engine)
charsheet/engine/          Regel-Engine
charsheet/templates/       Django-Templates fuer Character Sheet
charsheet/static/          App-spezifische statische Assets
static/                    Projektweite statische Assets
docs/                      Projektdokumentation
```

## Dokumentation
Die komplette projektspezifische Dokumentation liegt unter [`docs/`](docs/README.md).

- Setup und Betrieb: [`docs/setup.md`](docs/setup.md)
- Architektur: [`docs/architecture.md`](docs/architecture.md)
- Datenmodell: [`docs/models.md`](docs/models.md)
- Engine: [`docs/engine.md`](docs/engine.md)
- Routen und Views: [`docs/routes.md`](docs/routes.md)

## Roadmap (kurz)
- Charaktererschaffung mit vollem Budget-/Regel-Flow stabilisieren
- Waffen-/Kampfwerte weiter ausbauen
- Testabdeckung fuer Models, Engine und Views erhoehen
- UI und Nutzerfluss ausserhalb des Admins weiter ausbauen
