# Setup

## Voraussetzungen

- Python 3.x
- PostgreSQL
- optional Docker / Docker Compose fuer die Datenbank

## Python-Abhaengigkeiten

Die Anwendung nutzt aktuell nur wenige Kernabhaengigkeiten:

- `Django==5.2.11`
- `psycopg2-binary==2.9.11`

Installation:

```bash
python -m pip install -r requirements.txt
```

## Datenbankkonfiguration

Die Standardkonfiguration in `codex_arcana/settings.py` erwartet PostgreSQL mit folgenden Werten:

- Host: `localhost`
- Port: `5432`
- Datenbank: `charsheet`
- Benutzer: `charsheet`
- Passwort: `charsheet`

### Option A: lokale PostgreSQL-Instanz

Lege die Datenbank und den Benutzer mit den obigen Werten lokal an.

### Option B: Docker

Die Datei `docker-compose.yml` startet genau diese Standardkonfiguration:

```bash
docker compose up -d db
```

## `.env`-Datei

`settings.py` laedt eine einfache `.env`-Datei aus dem Projektwurzelverzeichnis. Unterstuetzt werden einfache `KEY=VALUE`-Zeilen. Aktuell ist das vor allem fuer die rechtlichen Angaben relevant.

## Django initialisieren

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Wichtige URLs

- Login: `http://127.0.0.1:8000/`
- Dashboard: `http://127.0.0.1:8000/dashboard/`
- Admin: `http://127.0.0.1:8000/admin/`
- Character-Erstellung: `http://127.0.0.1:8000/character/new/`
- Character Sheet eines Charakters: `http://127.0.0.1:8000/character/<id>/`
- Impressum: `http://127.0.0.1:8000/impressum/`
- Datenschutz: `http://127.0.0.1:8000/datenschutz/`

## Rechtliche Angaben fuer Self-Hosting

Die Seiten `Impressum` und `Datenschutz` lesen Betreiberinformationen aus `LEGAL_INFO` in `codex_arcana/settings.py`. Diese Werte koennen per Umgebungsvariable oder `.env` gesetzt werden:

- `LEGAL_SITE_NAME`
- `LEGAL_OPERATOR_NAME`
- `LEGAL_ADDRESS`
- `LEGAL_EMAIL`
- `LEGAL_PHONE`
- `LEGAL_RESPONSIBLE_PERSON`
- `LEGAL_REGISTER_ENTRY`
- `LEGAL_VAT_ID`
- `LEGAL_SUPERVISORY_AUTHORITY`

Die Felder Betreibername, Adresse und E-Mail gelten im Code als erforderlich; fehlen sie, markiert die View das im Template.

## Typische Entwicklerbefehle

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check
python manage.py shell
python manage.py test
```

## Hinweise fuer lokale Entwicklung

- `DEBUG` steht derzeit fest auf `True`.
- `TIME_ZONE` ist aktuell auf `UTC` gesetzt.
- Die Login-Seite liegt auf `/`, der Redirect nach erfolgreichem Login geht auf `dashboard`.
- Fuer das Character Sheet ist `/sheet/` nicht der normale Einstieg; gearbeitet wird ueblicherweise ueber `/character/<id>/`.
