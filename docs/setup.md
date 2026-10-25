# Setup

## Voraussetzungen

- Python 3.x
- PostgreSQL
- optional Docker / Docker Compose für die Datenbank

## Python-Abhängigkeiten

Die Anwendung nutzt aktuell nur wenige Kernabhängigkeiten:

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

`settings.py` lädt eine einfache `.env`-Datei aus dem Projektwurzelverzeichnis. Unterstützt werden einfache `KEY=VALUE`-Zeilen, unter anderem für Datenbank, E-Mail, Sicherheitskonfiguration und öffentliche Betreiberangaben. Zugangsdaten und private Betreiberangaben nicht ins Repository übernehmen.

## Django initialisieren

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Wichtige URLs

- Login: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`
- Character Sheet eines Charakters: `http://127.0.0.1:8000/character/<id>/`
- Impressum: `http://127.0.0.1:8000/impressum/`
- Datenschutz: `http://127.0.0.1:8000/datenschutz/`

Hinweis: `Dashboard` und `Character-Erstellung` sind technische Routen, aber nicht als direkte Einstiegspunkte in der Doku hervorgehoben. Der normale Start erfolgt über den Login und danach über die Navigation in der App.

## Rechtliche Angaben für Self-Hosting

Alle installationsabhängigen Rechtshinweise werden ausschließlich über die
bestehenden `LEGAL_*`-Variablen in der lokalen `.env` gepflegt.
Die vollständige, bewusst ohne echte Betreiberangaben ausgefüllte Vorlage
steht in [`.env.example`](../.env.example). Eine vorhandene `.env` nicht
überschreiben, sondern die benötigten Zeilen ergänzen.

`LEGAL_INFO` wird daraus in `codex_arcana/settings.py` aufgebaut.
Es gibt keine weitere lokale Legal-Konfigurationsdatei. Für `LEGAL_*` ist
die lokale `.env` maßgeblich: alte Prozesswerte werden entfernt und ausschließlich
die lokalen Einträge geladen. Andere Django-Einstellungen behalten ihre
bestehende Prozesspriorität. UTF-8 mit oder ohne BOM wird unterstützt.

Neben Betreibername, ladungsfähiger Anschrift und Kontaktadresse werden
tatsächliche Hosting-/Mailanbieter und Länder, Log-/Mail-/Backupfristen,
Vertrags-/Übermittlungsangaben, Bereinigungsverfahren und das lokale Datum
der tatsächlichen Inhaltsprüfung benötigt. Keine Anbieter oder Fristen
werden aus einer fremden Produktionsinstallation übernommen.
Optionale Register-, Steuer-, Telefon- und redaktionelle Angaben nur setzen,
wenn sie tatsächlich vorliegen und einschlägig sind.

Turnstile-Status/Formularauswahl, E-Mail-Verifizierung, bekannte lokale
Mailbackends und technische Sicherheits-/Cookiefristen werden aus den
vorhandenen Django-Einstellungen abgeleitet. Weitere betriebliche Tatsachen
und Dienstleister sind über die dokumentierten Legal-Textfelder eintragbar;
Templates und Anwendungscode müssen dafür nicht geändert werden.

Nach dem Ergänzen produktive Worker neu starten; der normale Entwicklungsserver
überwacht Änderungen der vorhandenen `.env`. Vor Veröffentlichung prüfen:

```powershell
.venv\Scripts\python.exe manage.py check --tag legal --fail-level WARNING
```

Fehlende Angaben erzeugen `legal.W001`, nicht plausible Angaben entsprechende
`legal.E00*`-Fehler. Ungültige Werte werden öffentlich nicht ausgegeben.
Warnungen und Hinweise auf fehlende Angaben erscheinen ausschließlich intern;
vor Freigabe ist deshalb der strenge Systemcheck erforderlich.
Vollständigkeit und Plausibilität ersetzen keine inhaltliche Rechtsprüfung.

Ausführliche Bedeutung **sämtlicher Variablen**, Prüfkriterien, Beispiele und
Übergabeschritte: [Installationsabhängige Legal-Konfiguration](legal.md).
Die echte `.env` bleibt lokal und darf vom Webserver nicht ausgeliefert werden.
Geheimnisse und Webhook-Zugangsadressen gehören nicht in öffentliche
Legal-Felder.

Die Kalender-Schriftarten werden lokal mitgeliefert. Beim regulären
Staticfiles-Deployment `css/calendar-fonts.css`, beide Noto-Dateien und deren
OFL-Lizenzen übernehmen; Herkunft und Umfang stehen in
[der Fontdokumentation](../static/fonts/README.md).
Die Legal-Architektur benötigt keine Datenbankmigration.

## Typische Entwicklerbefehle

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check
python manage.py shell
.venv\Scripts\python.exe manage.py test charsheet.tests.test_legal charsheet.tests.test_local_fonts --keepdb
```

## Hinweise für lokale Entwicklung

- `DJANGO_DEBUG` steuert den Debug-Modus und ist lokal standardmäßig `True`.
- `DJANGO_SECRET_KEY` muss auf Produktivsystemen in `.env` gesetzt werden.
- `TIME_ZONE` ist aktuell auf `UTC` gesetzt.
- Die Login-Seite liegt auf `/`, der Redirect nach erfolgreichem Login geht auf `dashboard`.
- Für das Character Sheet ist `/sheet/` nicht der normale Einstieg; gearbeitet wird üblicherweise über `/character/<id>/`.
