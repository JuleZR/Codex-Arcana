# Interne Bearbeitung von Datenschutzanfragen

Das Werkzeug ist über eine interne Superuser-Maske im Django-Admin und über das
Management-Command `privacy_export` verfügbar. Es gibt keinen öffentlichen
Export-Endpunkt, öffentlichen Downloadlink oder E-Mail-Versand.
Eine technische Zusammenstellung ersetzt keine Prüfung durch den Verantwortlichen.

## Admin-Maske: lokal speichern ohne Exportdateien auf dem Server

Auf der Admin-Startseite führt **DSGVO-Auskunft** zu `/admin/privacy-export/`.
Zugriff haben ausschließlich aktive Superuser mit Admin-Zugang. Normale
Staff-Berechtigungen reichen nicht. Auch hier ist `DEBUG=False` erforderlich.

1. Nach Benutzername, E-Mail-Adresse oder Charaktername suchen. Teilbegriffe
   reichen aus; archivierte Charaktere und deaktivierte Konten sind enthalten.
2. Das anhand von Konto-ID, Benutzername und E-Mail eindeutig bestimmte Konto
   auswählen. Die Suche zeigt höchstens 25 Konten; bei mehr Treffern eingrenzen.
3. Art. 15 oder Art. 20 und PDF, JSON oder ZIP auswählen. Auf Wunsch geprüfte
   hochgeladene Dateien ins ZIP aufnehmen. **Kategorienvorschau** zeigt den Umfang.
4. Die außerhalb des Werkzeugs erfolgte Anfragenprüfung bestätigen und
   **Speichern unter …** wählen. Die Auskunft umfasst das vollständige gewählte
   Benutzerkonto, auch wenn es über einen einzelnen Charakter gefunden wurde.
5. Den lokalen Speicherort auswählen und die heruntergeladene Datei prüfen.

Der Admin-Download erzeugt PDF, JSON und ZIP ausschließlich in Speicherpuffern.
Es werden **keine Exportdateien, temporären Exportdateien, serverseitigen
Prüfdateien oder Exportarchive** geschrieben. Die geöffneten Speicherpuffer
werden beim Ende bzw. Abbruch des Downloads geschlossen. Die Bereinigung erfolgt
ohne separaten Löschschritt. Vorhandene Original-Uploads werden nur gelesen.
Der Arbeitsspeicherbedarf wächst entsprechend der Größe des Pakets.

Unterstützt der Browser die File System Access API, öffnet **Speichern unter …**
vor der Erstellung den lokalen Dateidialog und überträgt die Antwort direkt in
die gewählte Datei. In anderen Browsern oder ohne JavaScript wird ein normaler
Dateidownload ausgelöst; der Speicherort richtet sich dann nach den lokalen
Browser-Einstellungen. Ein Speicherortdialog lässt sich dort gegebenenfalls
über „Vor jedem Download nach dem Speicherort fragen“ aktivieren.

Suche, Kontowahl und Export erfolgen per CSRF-geschütztem POST. Suchbegriffe
stehen nicht in der URL. Antworten sind mit `Cache-Control: private, no-store`
versehen; die Anwendung legt keine Download-URL oder Exportdatenbankeinträge an.
Die Webserver-/Proxykonfiguration muss diese Vorgaben beachten und darf keine
Antwortinhalte oder Formulardaten in Logs, Caches oder temporären Dateien
persistieren. Für den Download wird zusätzlich `X-Accel-Buffering: no` gesetzt.

Der Abschnitt **Erweiterte Prüfangaben und Abschlussfreigabe** nimmt das weiter
unten beschriebene Prüf-JSON direkt entgegen. Es bleibt im Arbeitsspeicher der
Anfrage. Für Art. 20 ist eine geprüfte Feldauswahl notwendig. Ohne dokumentierte
Abschlussfreigabe wird ein ausdrücklich gekennzeichneter Entwurf heruntergeladen.
Zur Freigabe den `review_sha256` des lokal geprüften Entwurfs mit Konto-ID und
Prüfzeitpunkt in die Prüfangaben übernehmen und mit denselben Optionen erneut
herunterladen. Konto-/Datenänderungen machen eine erneute Prüfung erforderlich.

Die folgenden Aufruf-/Pfadangaben betreffen ausschließlich das weiterhin
verfügbare Server-Command. Dessen ausdrücklich angeforderte Dateien werden im
angegebenen privaten Verzeichnis gespeichert und separat entfernt. Für rein
lokale Speicherung die oben beschriebene Admin-Maske verwenden.

## Ablauf und Fristen

1. Eingang, Eingangsdatum, gewünschten Umfang und Bearbeitung intern dokumentieren.
2. Das richtige Konto anhand seiner unveränderlichen Datenbank-ID bestimmen.
   Eine bekannte E-Mail-Adresse allein belegt keine Berechtigung. Bei begründeten
   Zweifeln die Identität angemessen prüfen, ohne unnötige Ausweiskopien anzulegen.
3. Auskunft (Art. 15) und Übertragbarkeit (Art. 20) getrennt beurteilen.
4. Kategorienvorschau durchführen, danach einen privaten Entwurf erstellen.
5. Datenkategorien, Dateien und ausgeschlossene Inhalte auf Vollständigkeit prüfen.
   Personenbezogene Erwähnungen in fremden oder gemeinsamen Freitexten und
   externe Speicher müssen zusätzlich untersucht werden.
6. Drittinformationen und versehentlich in Freitext oder Bildern enthaltene
   Geheimnisse prüfen. Erforderliche Schwärzungen begründen und dokumentieren.
7. Tatsächliche Verarbeitungsinformationen ergänzen, endgültigen Export prüfen
   und die Freigabe dokumentieren. Nur ein freigegebenes Paket weitergeben.
8. Geschützten Übertragungsweg verwenden, etwa einen individuell abgesicherten
   Kanal; ZIP ist **nicht verschlüsselt**. Keine ungeschützte E-Mail-Anlage.
9. Erledigung, Einschränkungen und deren Gründe dokumentieren; temporäre Exporte
   und Prüfdateien nach Zweckfortfall entfernen.

Nach Art. 12 Abs. 3 DSGVO grundsätzlich unverzüglich, spätestens innerhalb eines
Monats antworten. Eine Verlängerung um bis zu zwei weitere Monate setzt
Erforderlichkeit wegen Komplexität oder Zahl der Anträge voraus. Die betroffene
Person muss innerhalb des ersten Monats über Verlängerung und Gründe informiert
werden. Ablehnungen ebenfalls fristgerecht begründen und auf Beschwerde bzw.
Rechtsbehelf hinweisen. Maßgeblich ist der
[Verordnungstext auf EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj?locale=de),
insbesondere Art. 12, 15, 20 und die Rechte Dritter nach Art. 15 Abs. 4.

## Voraussetzungen und Aufruf des Server-Commands

`DEBUG=False` ist erforderlich, damit Django keine Abfrageparameter über seine
Debug-SQL-Protokollierung ausgibt. Eine gegebenenfalls auf Infrastruktur-/DB-Ebene
aktive SQL-Protokollierung muss der Betreiber ebenfalls berücksichtigen.
Die bestehende `.env`-basierte Legal-Konfiguration wird ausschließlich gelesen.
Die vorhandene PyMuPDF-Abhängigkeit erzeugt die PDF-Dateien lokal auf dem Server.
Es werden keine externen PDF-, Datei- oder sonstigen Netzwerkdienste aufgerufen.

Ein privates Zielverzeichnis muss bereits existieren. Es darf weder im Repository
noch in den konfigurierten Medien-/Static-Verzeichnissen liegen. Beispiel unter
Windows: `C:\Private\CodexExports`; unter Linux: `/srv/private/codex-exports`.
Der Betreiber muss zusätzlich sicherstellen, dass der Webserver **keinen** Alias
oder anderweitigen Zugriff auf dieses Verzeichnis anbietet. Beliebige zusätzliche
Webserver-Wurzeln kann Django nicht automatisch erkennen.

Alle Beispiele verwenden die fiktive Konto-ID `123`; diese ersetzen.

```powershell
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --preview
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --request-verified --format zip --output-dir C:\Private\CodexExports
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --request-verified --format pdf --output-dir C:\Private\CodexExports
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --request-verified --format json --output-dir C:\Private\CodexExports
```

`--request-verified` bestätigt die bereits außerhalb des Werkzeugs erfolgte
Anfragenprüfung; der Schalter authentifiziert die anfragende Person nicht.
Die Vorschau zeigt nur Kategorien und Anzahlen, keine Namen, Adressen oder Inhalte.
Art. 15 ist der Standardmodus `--mode access`.

Jeder Aufruf erstellt ein neues, zufällig benanntes Unterverzeichnis
`privacy-export-…`. Eine PDF-Ausgabe enthält den A4-Bericht; JSON enthält den
strukturierten Export; ZIP enthält `report.pdf` und `data.json`. Auch leere
Datenkategorien werden in der Übersicht ausgewiesen.

Für zuvor administrativ geprüfte Anhänge:

```powershell
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --request-verified --format zip --include-files --files-reviewed --output-dir C:\Private\CodexExports
```

Ohne diese beiden Dateischalter enthält das Paket ein Dateiverzeichnis, jedoch
keine hochgeladenen Dateiinhalte. Das steht ausdrücklich als `not_included` im
Bericht und JSON. Auch ohne Dateikopien werden lokale Dateizuordnungen validiert.
Fehlende Dateien, nichtlokaler Storage, unzulässige Pfade oder verknüpfte Anhänge
führen zum Abbruch. Das Werkzeug kontaktiert keinen Remote-Storage. Fehlende
Dateien müssen untersucht und separat erklärt werden; ein abgebrochener Lauf ist
kein vollständiger Export. Speicher- und Datenbankfehler erscheinen ohne
personenbezogene Ausnahmeinhalte. Nach Möglichkeit werden Teilausgaben entfernt;
ein Fehlschlag der Bereinigung wird ausdrücklich gemeldet.

## Gemeinsame Datengrundlage und Umfang

Die Sammlung findet genau einmal innerhalb einer konsistenten Transaktion statt.
Unter PostgreSQL wird sie ausdrücklich `REPEATABLE READ READ ONLY` ausgeführt.
Es werden weder Geschäftsdatensätze geändert noch Exporte in der DB archiviert.
PDF und JSON verwenden denselben normalisierten Snapshot und denselben SHA-256-
Prüfwert. Im ZIP werden Dateigröße und SHA-256 der tatsächlich kopierten Bytes
vor der Erstellung beider Berichte ergänzt. Anhänge stammen aus dem lokalen
Dateisystem; für gleichzeitig veränderte Uploads sollte der Betreiber eine
ruhige Betriebsphase wählen. Die DB-Transaktion sperrt das Dateisystem nicht.

Erfasst werden über geprüfte Eigentumsbeziehungen insbesondere:

| Bereich | Automatisch zusammengestellte Informationen |
| --- | --- |
| Konto | ID, Benutzername, E-Mail, Name, Aktiv-/Adminstatus, Registrierung und letzter Login |
| Einstellungen | Darstellung, Druck, Spiel-/Würfeloptionen, Verifizierungs- und 2FA-Status ohne Geheimnisse |
| Entwürfe | Charaktererstellungsentwürfe und eigene Erstellungsvorlagen |
| Charaktere | Alle gespeicherten Charakterfelder, einschließlich archivierter Charaktere |
| Regelzuordnungen | Attribute, Fertigkeiten, Spezifikationen, Sprachen, Eigenschaften und Entscheidungen |
| Fortschritt | Schulen, Pfade, Techniken, Spezialisierungen, Meisterschaften, Lektionen, Zauber und gespeicherte Erwerbsdaten |
| Weitere Charakterdaten | Glaubens-/Traditionsbindungen, Aspekte, Vampirismus und dämonische Kräfte |
| Inventar | Eigene Gegenstände, Beschreibungen, Overrides, Runen, semantische Effekte, Offenlegungs- und Identifikationszustände |
| Kreaturen | Eigene Kreaturen samt Ausrüstung, Fertigkeiten, Angriffen, Eigenschaften, Befehlen und Unterdatensätzen |
| Chronik und Kalender | Tagebucheinträge, Reihenfolge, gespeicherte Zeiten/Spieldaten, Kalenderlayout und Charakterdatum |
| Gruppen | Rollen, Mitgliedschaften und Einladungen einschließlich beendeter/widerrufener Beziehungen sowie archivierte Gruppenbezüge |
| Transfers | Eigene Sender-/Empfänger-/Akteurbezüge, Zustände, Mengen, Zeiten, Eigentumsereignisse, Berechtigungen und Benachrichtigungen |
| Sicherheit | Eigene AccountSecurityEvents, Passkey-Metadaten und Recovery-Code-Erstellungs-/Verbrauchszeiten |
| Sitzungen | Gespeicherte Ablaufzeiten eindeutig zugeordneter Datenbanksitzungen, auch noch gespeicherter abgelaufener Sitzungen |
| Weitere Anmeldeinformationen | Axes-Zeilen zum aktuellen Benutzernamen; Zuordnung administrativ prüfen |
| Verwaltung | Zeit und Aktionsart eigener Django-Admin-Aktionen ohne fremde Objektinhalte |
| Dateien | Direkte Dateifelder der exportierten eigenen Datensätze; optional geprüfte lokale Bytes im ZIP |

Alle 60 derzeitigen Konto-/Charakterkategorien werden anhand der tatsächlichen
Modellbeziehungen aufgelöst. Zusätzliche gemeinsam genutzte Kategorien werden
gesondert und eingeschränkt erfasst. Neue direkt personenbezogene Modelle ohne
geprüfte Zuordnung lassen die Sammlung abbrechen. Dies ersetzt bei einer
Modellerweiterung keine erneute Prüfung von Feldern, JSON und indirekten Bezügen.

Das JSON enthält unter `data.categories` je Modell ein Feldverzeichnis und die
Datensätze. Das Verzeichnis nennt Feldbedeutung, Django-Typ, verfügbare Choices und
Zielmodell von Beziehungen. IDs sind interne Datenbankkennungen; unter
`data.references` stehen Namen referenzierter allgemeiner Katalogdaten. Private
Gruppenkataloge werden dafür nicht aufgelöst. Fehlende Werte sind `null`, leere
Texte `""`, Zeiten ISO 8601 mit Zeitzone, reine Datumswerte Kalenderdaten.
Dezimal-/UUID-Werte werden verlustfrei als Zeichenfolge serialisiert.

Der öffentliche, bisherige Kontoexport bleibt unverändert. Sein schmales Format
enthält nur einige Charakter-, Inventar- und Tagebuchfelder und eignet sich
deshalb nicht als Grundlage dieser umfassenden internen Auskunft.

## Grenzen, Schwärzungen und manuelle Ergänzungen

Passwort-Hashes, TOTP-Secrets, Recovery-Code-Hashes, Verifizierungstoken,
Passkey-Credential-IDs/-Schlüsselmaterial, API-Schlüssel, Raum-Passwörter,
Session-Schlüssel/-Inhalte und Drosselungs-Digests verlassen den Snapshot nicht.
Sicherheitsereignis-Metadaten und freie Quickslot-JSON-Inhalte werden vorsorglich
zurückgehalten. Verdächtige Schlüssel in eigenen JSON-Daten werden rekursiv
geschützt; beliebige Freitexte können technisch nicht zuverlässig anonymisiert
werden und bleiben prüfpflichtig. Berechtigungsgruppen werden nicht exportiert.

Fremde Konto-/Charakterzuordnungen, Gruppennamen, gemeinsame Nachrichten,
Transfer-Snapshots/-Details und Gruppennotizen werden geschützt. Das gilt auch
für eigene Nachrichten in gemeinsam genutzten Datensätzen, weil sie Angaben
über Dritte enthalten können. Generische freie Objektzuordnungen werden nicht
ungeprüft aufgelöst. Jede automatische oder administrative Schwärzung wird in
`data.omissions` mit Modell, Datensatz, Feld und Grund dokumentiert, soweit sie
einen konkreten ausgegebenen Datensatz betrifft.

Gesondert zu prüfen sind insbesondere Gruppen-SL-Notizen, Tabellen samt Zellen,
SL-Kreaturenkarten, Gruppenkataloge, gemeinsame Inventare, Text-/Bild-Erwähnungen
in fremden Charakteren und Datensätze ohne verbleibende Eigentumszuordnung.
Die Erstellerschaft einer Gruppe oder Tabelle beweist keine alleinige
Dateneigentümerschaft. Diese Inhalte werden nicht pauschal exportiert. Nach
Prüfung berechtigte personenbezogene Auszüge zur Auskunft ergänzen und jede
verbleibende Auslassung begründen. Ein Export nur der automatisch freigegebenen
Felder darf nicht ungeprüft als vollständige Antwort bezeichnet werden.

Axes speichert teilweise nur einen Benutzernamen und kann auch fehlgeschlagene
fremde Anmeldeversuche enthalten. Aktuellen/historischen Namen, Zeitraum und
Zuordnung prüfen. Alte Namen, anonymisierte oder verwaiste Datensätze,
Authentifizierungs-Drosselungs-Buckets und nicht in der DB gespeicherte
Sitzungen erfordern gegebenenfalls zusätzliche administrative Untersuchung.

Außerhalb von Django gegebenenfalls Server-/Reverse-Proxy-/Datenbanklogs,
Backups, E-Mail-Postfächer und Versandprotokolle, Kontaktanfragen, Hosting,
Turnstile, andere administrative Dienste sowie den optionalen DDDice-Dienst
berücksichtigen. Das Werkzeug ruft diese Quellen nicht ab. Tatsächliche Empfänger,
Auftragsverarbeiter, Drittlandtransfers, Garantien, Herkunft und Aufbewahrung
betreiberspezifisch ermitteln. Eine konfigurierte Löschfrist ist kein Nachweis,
dass ein Bereinigungsjob tatsächlich ausgeführt wurde.

## Prüfdatei und finale Freigabe

Eine private UTF-8-JSON-Prüfdatei kann Schwärzungen und recherchierte Angaben
enthalten. Die Originaldaten werden nicht verändert. Feldschlüssel haben die
Form `app.Model:Datensatz-ID:Feldname`. Nicht passende oder veraltete Schlüssel
brechen den Export ab. Bei gemeinsamen Inhalten kann ein nach Prüfung zulässiger
Textauszug als Ersatzwert eingesetzt werden; keine Geheimnisse freigeben.

```json
{
  "processing": {
    "purposes": "Hier tatsächlich geprüfte Zwecke eintragen.",
    "recipients": "Tatsächliche Empfänger und Dienstleister eintragen.",
    "retention": "Je Kategorie Dauer oder konkrete Festlegungskriterien angeben.",
    "sources": "Nutzereingaben, Mitspieler, Systemereignisse konkret zuordnen.",
    "transfers": "Tatsächliche Drittlandtransfers und Garantien dokumentieren.",
    "automated_decisions": "Bestehen und gegebenenfalls Logik und Auswirkungen prüfen.",
    "legal_bases": "Tatsächliche Rechtsgrundlagen je Verarbeitung prüfen."
  },
  "redactions": {
    "charsheet.Character:456:appearance": "Nach Prüfung geschwärzter Textauszug."
  }
}
```

Das Beispiel ist **keine** fertige rechtliche Auskunft. Beispielwerte ersetzen,
unbenötigte Schwärzungsschlüssel entfernen und dann etwa
`--review-file C:\Private\review.json` an den Exportaufruf anhängen. Bestehende
`LEGAL_INFO`-Werte erscheinen zusätzlich im Bericht. Fehlende Konfiguration wird
sichtbar markiert; die tatsächlichen Informationen müssen vor Weitergabe ergänzt
sein. Die Legal-Konfiguration oder Datenschutzerklärung wird nicht verändert.

Nach vollständiger Prüfung des so erzeugten Entwurfs den Wert `review_sha256`
aus `data.json` zusammen mit der geprüften Konto-ID und dem realen Prüfzeitpunkt
in der Prüfdatei ergänzen:

```json
"approval": {
  "subject_id": 123,
  "review_sha256": "Hier den 64-stelligen SHA-256-Prüfwert einsetzen",
  "reviewed_at": "2026-10-25T15:00:00+01:00"
}
```

Dieser Abschnitt gehört auf die oberste Ebene desselben JSON-Objekts. Erneut mit
denselben Optionen, Schwärzungen und Verarbeitungsinformationen exportieren.
Alle sieben Verarbeitungsfelder müssen ausgefüllt sein. Stimmen Daten, Dateien
oder Konto nicht mehr mit der Prüfung überein, wird die Freigabe abgelehnt.
Ein neues Erstellungsdatum allein invalidiert die Freigabe nicht. Das fertige
PDF und JSON dokumentieren dann den Freigabestatus, den Prüfzeitpunkt und den
gemeinsamen Datenprüfwert. Die technische Freigabe ist eine dokumentierte
administrative Erklärung, keine elektronische Signatur oder Rechtsprüfung.

Für gesonderte PDF-Ausgaben lässt sich der Freigabeprüfwert auch aus dem Entwurf
ablesen. Dateischalter und Ausgabeumfang müssen zwischen Prüfung und Freigabe
identisch bleiben. Bei laufender Kontoaktivität kann eine erneute Prüfung nötig
werden. Bereits vorhandene Entwürfe werden nicht überschrieben.

## Art. 20: engerer maschinenlesbarer Export

Art. 20 wird nicht pauschal auf sämtliche Auskunftsdaten angewendet. Der Betreiber
muss pro Kategorie tatsächlich auf Einwilligung oder Vertrag beruhende,
automatisiert verarbeitete und von der Person bereitgestellte Daten bestimmen.
Systemseitige Bewertungen und Sicherheitsdaten dürfen nicht allein deshalb
eingeschlossen werden, weil sie unter Art. 15 zugänglich sind.

Ein zusätzlicher Abschnitt in der Prüfdatei legt die Kategorien/Felder fest:

```json
"portability": {
  "auth.User": {
    "basis": "contract",
    "provided_by_subject": true,
    "fields": ["username", "email", "first_name", "last_name"]
  },
  "charsheet.CharacterDiaryEntry": {
    "basis": "consent",
    "provided_by_subject": true,
    "fields": ["character", "text", "entry_date"]
  }
}
```

`contract` und `consent` sind erlaubte technische Bestätigungswerte, keine vom
Programm festgestellten Rechtsgrundlagen. Die Beispiele begründen keine dieser
Rechtsgrundlagen für einen konkreten Betrieb. Nur tatsächlich geprüfte Angaben
einsetzen. Ohne Kategorie-/Feldfreigabe wird Art. 20 abgelehnt; interne Datensatz-
IDs werden zur Zuordnung ergänzt. Schutzregeln gelten weiterhin und können durch
die Feldauswahl nicht aufgehoben werden. Eine Abschlussfreigabe nach dem oben
beschriebenen Verfahren ist auch für Art. 20 möglich.

```powershell
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --mode portability --request-verified --format json --review-file C:\Private\review.json --output-dir C:\Private\CodexExports
```

## Schutz und Entfernen der Exportdateien

Unter POSIX erhält das neue Unterverzeichnis Modus `0700`, Dateien `0600`.
Unter Windows setzt das Werkzeug mit `icacls` eine DACL ohne geerbte Rechte:
Zugriff für das ausführende Konto und SYSTEM. Fehler bei dieser Einrichtung
brechen vor dem Schreiben von Berichtsdaten ab. Administratoren und privilegierte
Backup-/Systemdienste können weiterhin Zugriff haben. Den ausführenden Prozess,
Datenträger, Swap, Backups und Übertragungsweg entsprechend schützen.

Das Werkzeug archiviert keine Exporte automatisch und plant keine Löschung.
Der Betreiber ist für die zeitnahe Entfernung nach Bearbeitung verantwortlich:

```powershell
.venv\Scripts\python.exe manage.py privacy_export --delete C:\Private\CodexExports\privacy-export-TATSAECHLICHE_KENNUNG
```

Entfernt werden ausschließlich markierte, flache Exportverzeichnisse mit den
bekannten Ausgabedateien. Zusätzliche Dateien oder Verknüpfungen verhindern die
automatische Löschung. Hochgeladene Originale und DB-Daten werden dabei nicht
angefasst. Private Prüfdateien und weitergegebene Kopien gesondert entfernen.
Normales Löschen garantiert auf SSDs, Snapshots und Backups kein physisches
Überschreiben; verschlüsselte Speicher und deren Schlüssel-/Aufbewahrungsregeln
berücksichtigen.

## Weitere Betroffenenrechte mit vorhandenen Mitteln

| Recht | Bestehende Unterstützung und erforderliches Vorgehen |
| --- | --- |
| Art. 16, Berichtigung | Eigene Kontoeinstellungen und Charaktereditoren sowie berechtigte Django-Admin-Formulare nutzen. Identität, sachliche Richtigkeit und Auswirkungen auf historische/geteilte Datensätze prüfen. |
| Art. 17, Löschung | Bestehenden Konto-Löschworkflow verwenden; geschützte gemeinsame/historische Beziehungen können Löschung blockieren und müssen geklärt werden. Keine SQL-Pauschallöschung, keine Änderung der bestehenden Bild-/Kontolöschlogik durch dieses Werkzeug. |
| Art. 18, Einschränkung | Vorhandene Kontodeaktivierung sperrt den Login (`is_active=False`), bedeutet jedoch keine vollständige rechtliche Verarbeitungseinschränkung. Ein eigener umfassender Einschränkungsstatus ist nicht vorhanden; weitere Verarbeitung/Jobs/Weitergaben organisatorisch prüfen. |
| Art. 21, Widerspruch | Es gibt keinen eigenständigen technischen Widerspruchsworkflow. Betroffene Zwecke/Rechtsgrundlagen einzeln prüfen und zulässige Maßnahmen mit bestehenden Einstellungen bzw. organisatorisch umsetzen. |

## Prüfung und technische Grenzen

Gezielte Tests mit synthetischen Konten:

```powershell
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_export --keepdb
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_admin --keepdb
node charsheet/tests/test_privacy_admin_download.js
```

Geprüft werden Eigentumsbeziehungen, archivierte Daten, geschützte gemeinsame
Inhalte, Geheimnisausschluss, Sitzungen, Inventarunterdaten, Art.-20-Feldauswahl,
Schwärzungen/Freigabebindung, Vorschau, JSON-Prüfwerte, PDF-/ZIP-Konsistenz,
Anhänge, Fehlerbereinigung, geschützte Pfade und Löschung. Lange Historien und
ununterbrochene Texte werden anhand der PDF-Textinhalte und Textgrenzen geprüft.
Browser, Screenshots und visuelle Tests werden nicht verwendet.

Die Admin-Tests prüfen zusätzlich Benutzer-/E-Mail-/Charaktersuche, archivierte
Charaktere und deaktivierte Zielkonten, Superuser-Zugriff, CSRF, Vorschau,
Art.-20-Prüfangaben und PDF-/JSON-/ZIP-Antworten aus Speicherpuffern. Versuche,
temporäre Dateien oder dateibasierte Ausgaben anzulegen, werden dabei blockiert.
Die JavaScript-Unit-Tests prüfen die Reihenfolge Dateidialog vor Exportanfrage,
Abbruch ohne Anfrage, direktes lokales Schreiben, Browser-Fallback und Fehler.
Sie verwenden simulierte APIs und stellen keinen visuellen Browsertest dar.

Lange Texte werden ohne Kürzung in kleine, über Seiten fortsetzbare Tabellenzeilen
aufgeteilt. A4-Ränder, Seitenzahlen, internes verlinktes Inhaltsverzeichnis,
PDF-Lesezeichen und Feldverzeichnisse sind Bestandteil des Berichts. HTML aus
gespeicherten Daten wird als Text behandelt und nicht ausgeführt oder nachgeladen.

ORM-Ergebnisse werden blockweise gelesen; Dateiinhalt wird blockweise ins ZIP
geschrieben und ZIP64 unterstützt. Der normalisierte Snapshot sowie das PDF-
Layout liegen im Arbeitsspeicher, dessen Bedarf mit dem Konto wächst. Bei sehr
großen Konten ausreichend RAM und privaten Speicher bereitstellen; es gibt keine
stille Kürzung oder Datensatzobergrenze. Der Test mit langer Historie ist kein
Nachweis für beliebig große Produktivkonten. Vor Weitergabe bleibt die konkrete
inhaltliche und rechtliche Vollständigkeitsprüfung erforderlich.
