# Setup

## Voraussetzungen
- Python 3.x
- PostgreSQL
- Optional: Docker / Docker Compose

## Abhängigkeiten installieren
```bash
python -m pip install -r requirements.txt
```

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
- Login: `http://127.0.0.1:8000/`
- Dashboard: `http://127.0.0.1:8000/dashboard/`
- Admin: `http://127.0.0.1:8000/admin/`
- Character Sheet: `http://127.0.0.1:8000/sheet/`
- Impressum: `http://127.0.0.1:8000/impressum/`
- Datenschutz: `http://127.0.0.1:8000/datenschutz/`

## Self-Hosting: rechtliche Angaben konfigurieren
Die Seiten `Impressum` und `Datenschutz` lesen Betreiberdaten aus `LEGAL_INFO`
in `codex_arcana/settings.py`. Diese Werte sollten über Umgebungsvariablen
gesetzt werden:

- `LEGAL_SITE_NAME`
- `LEGAL_OPERATOR_NAME`
- `LEGAL_ADDRESS`
- `LEGAL_EMAIL`
- `LEGAL_PHONE` (optional)
- `LEGAL_RESPONSIBLE_PERSON` (optional)

## Typische Entwicklerbefehle
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py shell
python manage.py check
```
