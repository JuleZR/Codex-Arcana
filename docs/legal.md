# Rechtliches und Self-Hosting

## Ziel
Das Repository ist fuer Self-Hosting gedacht. Deshalb sind Impressum und
Datenschutz technisch vorhanden, aber die konkreten Betreiberdaten werden nicht
hart im Code gespeichert.

## Routen
- `GET /impressum/`
- `GET /datenschutz/`

## Datenquelle
Die Seiten lesen Daten aus `LEGAL_INFO` in `codex_arcana/settings.py`.
`LEGAL_INFO` wird aus Umgebungsvariablen aufgebaut.

## Relevante Umgebungsvariablen
- `LEGAL_SITE_NAME`
- `LEGAL_OPERATOR_NAME` (Pflicht fuer produktives Hosting)
- `LEGAL_ADDRESS` (Pflicht fuer produktives Hosting)
- `LEGAL_EMAIL` (Pflicht fuer produktives Hosting)
- `LEGAL_PHONE` (optional)
- `LEGAL_RESPONSIBLE_PERSON` (optional)
- `LEGAL_REGISTER_ENTRY` (optional)
- `LEGAL_VAT_ID` (optional)
- `LEGAL_SUPERVISORY_AUTHORITY` (optional)

## Vorgehen fuer Betreiber
1. Eigene Werte in der Hosting-Umgebung setzen.
2. Deployment neu starten.
3. `impressum` und `datenschutz` im Browser pruefen.
4. Datenschutztext auf eigene Hosting-Realitaet pruefen (insb. Log-Retention,
   Hoster, Auftragsverarbeitung, ggf. weitere Drittanbieter).
5. Rechtlich verbindliche Freigabe durch qualifizierte Rechtsberatung einholen.

## Tatsaechlicher technischer Stand der App (fuer Datenschutztext)
- Login ueber Django-Authentifizierung (Benutzername/Passwort).
- Session- und CSRF-Cookies fuer Auth/Sicherheit.
- Charakter- und Inventardaten in PostgreSQL.
- Browser-`localStorage` fuer UI-Zustaende einzelner Fenster.
- Schriftarten werden lokal ueber `static/fonts/` ausgeliefert.
- Charakter-Endpunkte sind an eingeloggte Nutzer gebunden und benutzerbezogen
  abgesichert.

## Hinweise
- Die bereitgestellten Texte sind eine schlanke technische Vorlage.
- Jeder Betreiber ist fuer die rechtliche Pruefung und Vollstaendigkeit seiner
  Angaben selbst verantwortlich.
