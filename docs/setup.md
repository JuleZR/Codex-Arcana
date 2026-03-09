# Setup

## Voraussetzungen
- Python 3.x
- PostgreSQL
- Optional: Docker / Docker Compose

Hinweis: Aktuell liegt keine `requirements.txt` oder `pyproject.toml` im Repo. Die Python-Abhaengigkeiten muessen in deiner Umgebung bereits vorhanden sein.

## Datenbank

### Option A: Lokal installierte PostgreSQL-Instanz
Die Standardkonfiguration aus `codex_arcana/settings.py` erwartet:
- Host: `localhost`
- Port: `5432`
- DB: `charsheet`
- User: `charsheet`
- Passwort: `charsheet`

### Option B: Docker
```bash
docker compose up -d db
```

## Django starten
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Wichtige URLs
- Admin: `http://127.0.0.1:8000/admin/`
- Character Sheet: `http://127.0.0.1:8000/sheet/`

## Typische Entwicklerbefehle
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py shell
python manage.py check
```
