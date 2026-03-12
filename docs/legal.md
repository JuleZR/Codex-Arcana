# Rechtliches und Self-Hosting

## Ziel
Das Repository ist für Self-Hosting gedacht. Deshalb sind Impressum und
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
- `LEGAL_OPERATOR_NAME` (Pflicht für produktives Hosting)
- `LEGAL_ADDRESS` (Pflicht für produktives Hosting)
- `LEGAL_EMAIL` (Pflicht für produktives Hosting)
- `LEGAL_PHONE` (optional)
- `LEGAL_RESPONSIBLE_PERSON` (optional)
- `LEGAL_REGISTER_ENTRY` (optional)
- `LEGAL_VAT_ID` (optional)
- `LEGAL_SUPERVISORY_AUTHORITY` (optional)

## Vorgehen für Betreiber
1. Eigene Werte in der Hosting-Umgebung setzen.
2. Deployment neu starten.
3. `impressum` und `datenschutz` im Browser prüfen.
4. Datenschutztext auf eigene Hosting-Realität prüfen (insb. Log-Retention,
   Hoster, Auftragsverarbeitung, ggf. weitere Drittanbieter).
5. Rechtlich verbindliche Freigabe durch qualifizierte Rechtsberatung einholen.

## Tatsächlicher technischer Stand der App (für Datenschutztext)
- Login über Django-Authentifizierung (Benutzername/Passwort).
- Session- und CSRF-Cookies für Auth/Sicherheit.
- Charakter- und Inventardaten in PostgreSQL.
- Browser-`localStorage` für UI-Zustände einzelner Fenster.
- Schriftarten werden über externe CDNs geladen (`fonts.googleapis.com`, `fonts.gstatic.com`).
- Charakter-Endpunkte sind an eingeloggte Nutzer gebunden und benutzerbezogen
  abgesichert.

## Hinweise
- Die bereitgestellten Texte sind eine schlanke technische Vorlage.
- Jeder Betreiber ist für die rechtliche Prüfung und Vollständigkeit seiner
  Angaben selbst verantwortlich.
