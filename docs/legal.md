# Installationsabhängige Legal-Konfiguration

Codex Arcana ist ein Self-Hosting-Projekt. Jede Installation benötigt eigene
Betreiber-, Hosting-, Aufbewahrungs- und Empfängerangaben. Das Repository enthält
die allgemeinen Funktionsbeschreibungen und die Darstellungslogik; es enthält
keine Betriebsdaten einer bestimmten produktiven Installation.

## Eine Konfigurationsschnittstelle: die lokale .env

Alle individuellen Angaben kommen aus den bestehenden `LEGAL_*`-Variablen.
`codex_arcana/settings.py` baut daraus das einzige `LEGAL_INFO` auf.
Es gibt weder eine zusätzliche Legal-Datei noch einen JSON-Loader oder eine
zweite manuell gepflegte Anbieterliste im Anwendungscode.

Die Ladefolge für rechtliche Angaben ist eindeutig:

1. Alte oder geerbte `LEGAL_*`-Werte werden beim Laden entfernt. Damit bleiben
   auch entfernte lokale Einträge nicht im Entwicklungsserver erhalten.
2. Ausschließlich die lokale `.env` im Projektwurzelverzeichnis liefert die
   `LEGAL_*`-Werte. Fehlende oder leere Einträge bleiben leer, auch wenn die
   Prozessumgebung zuvor einen anderen Wert enthielt. Ohne `.env` fehlen
   entsprechend die individuellen Legal-Angaben.
3. `LEGAL_INFO` übernimmt diese Werte. Nur der allgemeine Angebotsname
   hat einen Softwaredefault; Anbieter, Orte, Fristen, Verträge und
   Überarbeitungsdatum haben **keine erfundenen Ersatzwerte**.

Andere Django-Einstellungen behalten ihre bestehende Prozesspriorität;
die Änderung betrifft nur `LEGAL_*`. Innerhalb der `.env` Variablen nicht
mehrfach definieren; bei doppelten Legal-Einträgen gilt der letzte Eintrag.
Keine eigenen `LEGAL_INFO`-Zuweisungen in Python oder Templates hinzufügen.

Die lokale `.env` ist durch die bestehende Git-Regel ausgeschlossen.
Sie gehört weder nach `static/` noch nach `media/` und darf vom Webserver
nicht ausgeliefert werden. Zugriff auf den Projektordner und die Datei
betrieblich beschränken; den Webserver nur für die vorgesehenen öffentlichen
Ressourcen konfigurieren. Die Legal-Funktion legt keine lokale Datei an,
ändert keine Zugangsdaten und ruft keine Anbieterportale auf.

## Einrichtung einer neuen Installation

1. [Die vollständige Vorlage](../.env.example) lesen. In einer neuen Umgebung
   die benötigten Zeilen in der lokalen `.env` anlegen. Eine vorhandene
   `.env` **nicht überschreiben**: Legal-Zeilen dort gezielt ergänzen.
2. Anbieterunterlagen und tatsächliche Server-/Dienstkonfiguration prüfen.
   Die leeren Felder anhand belegter Tatsachen ausfüllen. Ein unbekannter
   Standort oder eine unbekannte Löschfrist wird nicht durch einen
   fremden Produktionswert oder einen geratenen Standard ersetzt.
3. Optional einschlägige Betreiberangaben ergänzen; nicht vorhandene Register-,
   Steuer- oder redaktionelle Angaben leer lassen.
4. Alle allgemeinen und zusätzlichen Datenverarbeitungen rechtlich prüfen.
   Das lokale Datum dieser tatsächlichen Inhaltsprüfung eintragen.
5. Produktive Django-Worker nach Änderungen neu starten. Der normale
   Entwicklungsserver überwacht die vorhandene `.env` zusätzlich und lädt
   Änderungen neu; bei abgeschalteter automatischer Neuladung manuell neu starten.
6. Den strengen Legal-Systemcheck ausführen und die öffentlichen Seiten
   kontrollieren. Änderungen an Templates oder Python sind dafür nicht nötig.

Die Vorlage enthält ausschließlich allgemeine Hinweise und leere individuelle
Werte. Sie ist selbst **keine fertige oder rechtskonforme Betreiberkonfiguration**.
Es gibt keine automatisierte Einrichtung einer bestimmten Domain.

## Format

Werte sind einfacher öffentlicher Klartext in UTF-8, auch mit UTF-8-BOM. Eine Variable steht auf
einer Zeile. Für Absätze und Anschriften kann das literale `\n` verwendet
werden; die Ausgabe zeigt daraus Zeilenumbrüche. In
`LEGAL_ADMINISTRATIVE_SERVICES` wird `**fett gedruckter Text**` als Fettschrift
ausgegeben. Sonstige Markdown-Funktionen, HTML und JSON werden nicht ausgewertet;
HTML-Zeichen bleiben escaped. Beispiel für die lokale `.env`:

```dotenv
LEGAL_ADMINISTRATIVE_SERVICES="**Administrative Benachrichtigungen:** Beschreibung des Dienstes.\n**Aufbewahrung:** Beschreibung der tatsächlichen Frist."
```

**Alle Legal-Werte sind zur Veröffentlichung bestimmt.** Keine API-/SMTP-Schlüssel,
Passwörter, signierten Zugangslinks, vollständigen Webhook-Adressen oder privaten
Vertragsunterlagen hinterlegen. Verträge nur in einer öffentlich geeigneten
Beschreibung nachweisen, nicht in die Texte kopieren.

Der Maximalumfang je Feld beträgt 20.000 Zeichen. Die Textfelder erlauben
umfangreiche Beschreibungen, zum Beispiel getrennte Löschregeln für mehrere
Protokollarten oder mehrere beauftragte Anbieter.

## Betreiber und Überarbeitungsdatum

| Variable | Pflicht / Inhalt |
| --- | --- |
| `LEGAL_SITE_NAME` | Optionaler Angebotsname; Softwaredefault Codex Arcana |
| `LEGAL_OPERATOR_NAME` | Erforderlich: tatsächlicher vollständiger Betreiber-/Verantwortlichenname |
| `LEGAL_ADDRESS` | Erforderlich: ladungsfähige Anschrift, einschließlich ggf. erforderlicher Vertretungsangaben |
| `LEGAL_EMAIL` | Erforderlich: tatsächlich erreichbare rechtliche Kontaktadresse; syntaktische E-Mail-Prüfung |
| `LEGAL_REVIEWED_ON` | Erforderlich: Datum der letzten tatsächlichen lokalen Inhaltsprüfung, `YYYY-MM-DD`; gültig und nicht zukünftig |
| `LEGAL_PHONE` | Optional: zur Veröffentlichung bestimmte Telefonnummer |
| `LEGAL_REGISTER_ENTRY` | Nur tatsächlich vorhandener und einschlägiger Registereintrag |
| `LEGAL_VAT_ID` | Nur tatsächlich vorhandene und einschlägige USt-ID |
| `LEGAL_SUPERVISORY_AUTHORITY` | Nur einschlägige Zulassungs-/Berufsaufsicht; nicht pauschal die Datenschutzaufsicht |
| `LEGAL_DATA_PROTECTION_OFFICER` | Öffentliche Kontaktdaten eines tatsächlich benannten Datenschutzbeauftragten, sofern einschlägig |
| `LEGAL_RESPONSIBLE_PERSON` | Nur nach Prüfung journalistisch-redaktioneller Verantwortlichkeit nach § 18 Abs. 2 MStV |
| `LEGAL_RESPONSIBLE_ADDRESS` | Die Anschrift genau dieser redaktionell verantwortlichen Person; bei redaktioneller Angabe müssen beide Felder vorliegen |

Name und Anschrift sind für ein nicht ausschließlich persönliches/familiäres
öffentliches Angebot insbesondere anhand § 18 Abs. 1 MStV zu prüfen.
Die Kontaktadresse gehört auch in die Datenschutzinformation.
Die Anwendbarkeit von § 5 DDG und § 18 Abs. 2 MStV hängt vom tatsächlichen
Angebot ab. Kostenlosigkeit oder ein Fanprojekt-Hinweis begründen weder pauschal
eine Ausnahme noch automatisch redaktionelle Verantwortlichkeit.

Das Datum wird nicht aus Serverzeit, Repositorystand oder einer bekannten
Produktionsinstallation übernommen. Es erscheint nur aus `LEGAL_REVIEWED_ON`.
Bei späteren inhaltlichen Änderungen lokal erneut prüfen und aktualisieren.

## Hosting, Logs, Backups und Testkopien

Alle folgenden Felder sind für die vollständige technische Beschreibung
erforderlich. Auch die nachgewiesene Nichtverwendung eines Verfahrens kann
sachlich beschrieben werden; sie darf nicht ohne Prüfung angenommen werden.

| Variable | Was der Betreiber eintragen muss |
| --- | --- |
| `LEGAL_HOSTING_PROVIDER` | Tatsächlicher Hostinganbieter; ggf. weitere beteiligte Infrastruktur-/Datenbankanbieter |
| `LEGAL_HOSTING_LOCATION` | Bestätigte Verarbeitungsorte und Länder einschließlich Datenbank und relevanter Supportzugriffe |
| `LEGAL_SERVER_LOG_RETENTION` | Tatsächliche Kategorien, Zwecke, Zugriffe, Fristen und Rotation von Webserver-, Anwendungs-, System- und Datenbankprotokollen sowie Archiven |
| `LEGAL_AUTH_LOG_RETENTION` | Zusätzliche Regeln für Axes-Zugriffslogs, Rate-Limit-Datensätze und deren tatsächliche Bereinigung; Sperrdauer ist keine Speicherfrist |
| `LEGAL_SECURITY_CLEANUP` | Wie die konfigurierte Sicherheitsereignisfrist umgesetzt wird: vorhandene Ereignisbereinigung, tatsächlich eingerichtete Jobs oder noch fehlende Umsetzung |
| `LEGAL_BACKUP_POLICY` | Tatsächlich genutzte Anbieter/Verfahren, Datenumfang, Standorte, Intervalle, Zugriffe, Verschlüsselung, Aufbewahrung/Löschung und Wiederherstellungsabgleich |
| `LEGAL_TEST_DATA_POLICY` | Ob Produktionsdaten/-medien in Entwicklungs-/Testumgebungen kopiert werden; ggf. Zweck, Datenminimierung, Anonymisierung, Empfänger, Länder, Zugriffe und Löschung |

`ACCOUNT_SECURITY_ACTIVITY_RETENTION_DAYS` ist die bereits vorhandene
technische Einstellung für Kontosicherheitsereignisse. Die öffentliche Erklärung
übernimmt die Aufbewahrungsangaben ausschließlich aus `LEGAL_AUTH_LOG_RETENTION`
und die Verfahrensbeschreibung aus `LEGAL_SECURITY_CLEANUP`. Das Template ergänzt
keine eigene Frist oder Bereinigungsaussage aus Django-Einstellungen.
Die Textfelder richten selbst keine Löschjobs ein und ändern keine
Sicherheitsfunktionen oder Datenbankinhalte. Fristen und Umsetzung müssen
übereinstimmen. Ohne bekanntes Verfahren bleibt die Konfiguration unvollständig.

### Sicherheitsereignisse unabhängig von neuen Anmeldungen bereinigen

`record_security_event` bereinigt ältere `AccountSecurityEvent`-Einträge beim
Erfassen neuer Ereignisse. Ohne weitere Ereignisse läuft diese Bereinigung
nicht. Der vorhandene Befehl `purge_security_activity` arbeitet unabhängig davon;
allein sein Vorhandensein richtet jedoch keinen regelmäßigen Job ein.
Die lokalen Legal-Angaben müssen das tatsächlich eingerichtete Verfahren und
die dazu passende Aufbewahrung beschreiben. Die technische Löschschwelle wird
anhand des Erstellungszeitpunkts geprüft; ohne regelmäßige Bereinigung können
ältere Einträge verbleiben.

Für Linux mit systemd stehen eine
[Service-Vorlage](../scripts/systemd/codex-security-cleanup.service.example) und
eine [Timer-Vorlage](../scripts/systemd/codex-security-cleanup.timer.example)
bereit. **Sie werden nicht automatisch installiert oder aktiviert.** Einrichtung
durch den Betreiber:

1. Beide Dateien nach `/etc/systemd/system/` kopieren, dabei die Endung
   `.example` entfernen. In der Service-Datei `CHANGE_ME` durch den tatsächlichen
   unprivilegierten Anwendungsbenutzer und die absoluten Installationspfade
   ersetzen. Der Benutzer muss die lokale `.env` lesen und die richtige
   Datenbank erreichen können. Benötigte zusätzliche Laufzeitumgebung wie beim
   Anwendungsdienst einrichten; keine Geheimnisse in versionierte Units schreiben.
2. Units mit `systemd-analyze verify` prüfen. Dann als Administrator:

   ```sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now codex-security-cleanup.timer
   sudo systemctl start codex-security-cleanup.service
   sudo systemctl status codex-security-cleanup.service
   sudo journalctl -u codex-security-cleanup.service
   sudo systemctl list-timers --all codex-security-cleanup.timer
   ```

   Der manuelle Start löscht bereits abgelaufene Sicherheitsereignisse in der
   gewählten Datenbank. Richtige Installation und Frist vor dem Start prüfen.
3. Erfolgreichen Lauf und nächsten Termin nachweisen und Ausfälle überwachen.
   Der Timer läuft täglich mit bis zu 15 Minuten Zufallsverzögerung. `Persistent`
   holt einen während Abschaltung verpassten Termin nach; fehlgeschlagene Läufe
   werden nach fünf Minuten erneut versucht. Ein ausgeschalteter Server oder
   dauerhaft gestörter Datenbankzugriff kann trotzdem keine Löschung ausführen.
   Betrieb und Überwachung bleiben erforderlich. Die Löschschwelle ist daher
   keine Zusicherung minutengenauer Löschung beim Erreichen der Frist.
4. Erst nach tatsächlich erfolgreicher Einrichtung `LEGAL_SECURITY_CLEANUP`
   lokal in verständlichem öffentlichem Text anpassen, etwa zum regelmäßigen
   Bereinigungsrhythmus. Keine Befehle, Modellnamen oder Einrichtungsaufträge
   in dieses öffentliche Feld schreiben. Die Aufbewahrungsfrist ausschließlich
   in den lokalen Legal-Angaben pflegen und nicht mehrfach wiederholen.

Andere Betriebsumgebungen müssen denselben Befehl mit einem externen Scheduler
unter dem Anwendungsbenutzer ausführen und den Erfolg überwachen. Weder
Webworker-Start noch neue Kontoaktivität ist ein Ersatz für diesen Zeitplan.
Backups und andere Authentifizierungsprotokolle werden dadurch nicht bereinigt.

## E-Mail, Empfängerrollen und internationale Übermittlungen

| Variable | Erforderliche öffentliche Angaben |
| --- | --- |
| `LEGAL_EMAIL_PROVIDER` | Tatsächlicher Dienstleister oder lokales Versand-/Testverfahren; keine automatisch aus Hostnamen erratene Anbieterzuordnung |
| `LEGAL_EMAIL_LOCATION` | Empfänger und tatsächliche Verarbeitungsorte/Länder einschließlich relevanter Unterauftragnehmer-/Supportzugriffe |
| `LEGAL_EMAIL_RETENTION` | Fristen/Regeln für Empfängerbezüge, Versandereignisse, Logs und gespeicherte Mailinhalte/Vorschauen beim verwendeten Verfahren |
| `LEGAL_EMAIL_TRACKING` | Tatsächliche Einstellungen und Verarbeitung von Öffnungs-/Klicktracking oder belegte Deaktivierung; ggf. Daten, Zweck, Grundlage und Wahlmöglichkeiten |
| `LEGAL_CONTACT_RETENTION` | Zuständiges Kontaktpostfach/Mailanbieter, Anfrageverarbeitung, Empfänger, Grundlage und Aufbewahrung |
| `LEGAL_PROCESSOR_CONTRACTS` | Tatsächliche Empfängerrollen und anwendbare Auftragsverarbeitungsverträge; keine unterstellten Abschlüsse |
| `LEGAL_TRANSFER_SAFEGUARDS` | Tatsächliche internationale Übermittlungen, Empfänger/Länder und passende Garantien oder sachlich begründete Beschreibung ohne solche Übermittlungen |

Ein in Europa gelegenes Datenbankhosting beweist nicht, dass kein Drittlandzugriff
stattfindet. Vertragsrolle, Unterauftragnehmer und Übermittlungsmechanismus
anhand der konkreten Verträge prüfen. Die Befristung eines Reset-Links ist
keine Löschfrist für Mailvorschauen oder Zustelllogs.

Die bekannten lokalen Django-Backends `console`, `filebased`, `locmem` und
`dummy` werden aus `EMAIL_BACKEND` als lokale Test-/Ausgabeverfahren erkannt.
Für andere Backends wird kein bestimmter Anbieter oder Übermittlungsort erraten.
Auch lokale Mailausgaben können Daten speichern; das muss in den Feldern
zutreffend beschrieben werden.

Die Aussage „nur Transaktionsmails, kein Marketing“ beantwortet nicht die
Trackingfrage. Der Anwendungscode baut selbst keine individuellen Öffnungspixel
oder Klickumleitungen ein; ein SMTP-Dienst kann die Mail jedoch nachträglich
verändern. Anbieterfunktionen und tatsächlich aktivierte Kontoeinstellungen
getrennt prüfen. Die [konkrete interne Prüfliste](legal-data-processing.md#mailtracking-codebefund-und-notwendiger-betreibernachweis)
beschreibt den erforderlichen Nachweis. Bei unbekanntem Status keine
Trackingfreiheit behaupten; `LEGAL_EMAIL_TRACKING` bleibt bis zur Klärung leer
und wird intern als fehlend gemeldet. Bestätigte Regeln zu Transaktionslogs und
Mailvorschauen in `LEGAL_EMAIL_RETENTION` bleiben davon unabhängig erhalten.

## Browserdaten und optionale Integrationen

| Variable | Verwendung |
| --- | --- |
| `LEGAL_TURNSTILE_DETAILS` | Nur bei `AUTH_TURNSTILE_ENABLED=True` erforderlich und sichtbar: tatsächlich gewählte Widget-/Portaloptionen, insbesondere zusätzliche Pre-Clearance-Cookies und deren Laufzeiten; keine erneute Beschreibung der allgemeinen Funktion |
| `LEGAL_ADDITIONAL_PROCESSING` | Optional: weitere tatsächlich vorhandene Verarbeitung von Anwendungs-/Benutzerdaten, vollständig mit Daten, Zweck, Grundlage, Empfängern, Ländern/Garantien, Fristen und Rechten beschreiben |
| `LEGAL_ADMINISTRATIVE_SERVICES` | Optional: tatsächlich genutzte administrative Betriebsdienste, etwa reine Wartungsmeldungen; Anbieter, exakter Payload, Zweck/Grundlage, Empfänger, Länder/Garantien und Aufbewahrung beschreiben |

Turnstile-Status und Formularauswahl kommen ausschließlich aus den vorhandenen
`AUTH_TURNSTILE_ENABLED`-/`AUTH_TURNSTILE_CATEGORIES`-Einstellungen.
Ein manueller Legal-Text schaltet Turnstile nicht ein. Bei ausgeschaltetem
Turnstile werden die dazu hinterlegten Betriebsangaben nicht ausgegeben und
nicht als aktive Verarbeitung bezeichnet. Zusätzliche, außerhalb des
Anwendungscodes eingerichtete Proxy-/Sicherheitsdienste gehören in die
passenden lokalen Betriebsangaben.

DDDice ist eine feste, vom einzelnen Benutzer gewünschte und konfigurierte
Anwendungsfunktion. Ihre allgemeinen Datenflüsse, Empfänger und Grenzen stehen
direkt im Datenschutztemplate. Dafür gibt es kein `LEGAL_*`-Feld: weder eine
globale Aktivitätsangabe noch Betreibertexte oder Benutzerzugangsdaten in der
`.env`. Auch die allgemeine Beschreibung des Browserspeichers bleibt ein fester
Textbaustein. Tatsächlich zusätzlich eingerichtete Verfahren einer Installation
werden nur über die Felder für zusätzliche Verarbeitungen beschrieben.

Administrative Meldungen sind nicht automatisch eine Übermittlung von Konto-
oder Charakterdaten. Nur der tatsächlich konfigurierte Payload bestimmt den
zu beschreibenden Umfang. Vollständige Webhook-Zugangsadressen sind verboten.
Weitere Dienstleister erfordern dank der Textfelder keine Templateänderung.

Die Standardtexte enthalten die allgemeinen Browser-Speicherfunktionen und
machen keine pauschale Notwendigkeitsausnahme für Komfortspeicher.
Rechtlich notwendige Einwilligung oder technische Löschmaßnahmen müssen
gesondert umgesetzt werden; ein eingetragener Text ersetzt sie nicht.
Das [funktionsbezogene Speicherinventar](legal-data-processing.md#konkrete-prüfung-der-endgerätespeicher)
benennt die konkreten automatischen Zugriffe und die fehlende vorgeschaltete
Einwilligungssteuerung für nicht erforderliche Persistenz. Insbesondere
dauerhafte Wurfhistorie und reine Anzeigezustände benötigen eine gezielte
Korrektur vor Freigabe; es wird keine bereits vorhandene Zustimmung behauptet.

## Validierung und Systemchecks

`charsheet/legal.py` ist die gemeinsame Validierung für Systemchecks und die
öffentliche Ausgabe. Die gemeinsame Legal-Basis liest die validierten Angaben
über einen Template-Tag; rohe Kontextwerte können diese Ausgabe nicht ersetzen.

| Check-ID | Bedeutung |
| --- | --- |
| `legal.W001` | Für diese Installation erforderliche Angaben fehlen; bei eingeschaltetem Turnstile einschließlich dessen Betriebsangaben |
| `legal.E001` | Ungültige Struktur oder unbekannte Schlüssel in `LEGAL_INFO` |
| `legal.E002` | Kein Text oder mehr als 20.000 Zeichen |
| `legal.E003` | Kontaktadresse syntaktisch ungültig |
| `legal.E004` | Überarbeitungsdatum ungültig, nicht ISO-formatiert oder zukünftig |
| `legal.E005` | Erkennbare Zugangsdaten-/Privatschlüssel-/Webhook-Muster oder zugangsgeschützte URLs |

Ungültige Werte werden nicht ausgegeben. Fehlende Pflichtangaben und ungültige
Konfiguration werden ausschließlich intern über die Systemchecks gemeldet.
Die öffentlichen Seiten zeigen weder Konfigurationswarnungen noch leere
Platzhalter oder Hinweise zur Selbstinstallation. Die Prüfmeldungen geben
Feldnamen, aber keine ungültigen Werte
oder Zugangsdaten wieder. Erkennbare Secrets werden zurückgewiesen; eine
Heuristik kann nicht jedes beliebige Geheimnis erkennen. Alle Einträge müssen
deshalb vorab bewusst für die Veröffentlichung bestimmt sein.

Die Vollständigkeitsprüfung kann keine tatsächliche ladungsfähige Anschrift,
bestehenden Vertrag, korrekte Anbieterfrist oder Rechtmäßigkeit beweisen.
Sie prüft Struktur und Plausibilität; Inhalt und Belege bleiben Betreiberaufgabe.
Warnungsfreiheit bedeutet keine vollständige Rechtskonformität.

```powershell
.venv\Scripts\python.exe manage.py check --tag legal
.venv\Scripts\python.exe manage.py check --tag legal --fail-level WARNING
```

Der erste Befehl zeigt unvollständige Angaben an. Der zweite muss vor einer
Veröffentlichung erfolgreich sein und schlägt auch bei `legal.W001` fehl.
Die öffentliche Ausgabe ersetzt diese Freigabeprüfung nicht; Checks nicht
pauschal stummschalten. Eine Seite ohne Warnkasten ist kein Nachweis vollständiger Angaben.

## Redaktionelle Trennung von Rechtstexten und Entwicklerdokumentation

Öffentliche Texte beschreiben aus Betreibersicht Daten, Zwecke, Rechtsgrundlagen,
Empfänger, Speicherfristen und Rechte. Sie enthalten keine Repository-Audits,
Implementierungshistorie, Testberichte, Variablennamen oder Arbeitsaufträge an
Administratoren. Dasselbe gilt für die lokal eingetragenen Legal-Textfelder:
Sie müssen unmittelbar als verständliche öffentliche Information formuliert sein.
Prüffragen und fehlende Nachweise gehören in die interne Betriebsdokumentation.

Die allgemeinen Beschreibungen von Schriftarten, Anmeldesicherheit,
Browserdaten, Mailzwecken und DDDice stehen in den Templates. Turnstile wird
nur bei tatsächlich eingeschaltetem Django-Flag beschrieben. Discord ist keine
Anwendungsintegration: Ein etwaiges getrenntes Wartungsskript liegt in der
Verantwortung des Serverbetreibers und wird nur über das optionale Feld
`LEGAL_ADMINISTRATIVE_SERVICES` beschrieben. Ohne Feldinhalt erscheint kein Abschnitt.

Vor Freigabe weiterhin rechtlich klären und organisatorisch nachweisen:

- Die funktionsbezogene Einordnung der Komfortspeicher nach § 25 TDDDG;
  eine bloße Textüberarbeitung richtet keinen Einwilligungsmechanismus ein.
- Die tatsächliche Rechtsgrundlage, Aufbewahrung und Übermittlungsabsicherung
  aktivierter externer Dienste. Insbesondere nennt DDDice eine US-Verarbeitung,
  veröffentlicht in seiner Datenschutzerklärung aber keine konkrete allgemeine
  Löschfrist und verweist noch auf Privacy Shield. Daraus keine aktuelle
  Transfergarantie ableiten.
- Tatsächlich ausgeführte Löschjobs, Bereinigung von Bildresten, gemeinsame
  Spielhistorien sowie Löschfristen von Backups, Testkopien und Maildiensten.
- Erforderliche Betreiberangaben, Verträge und ggf. redaktionelle Verantwortung.

Maßgebliche Primärquellen sind die
[DSGVO, insbesondere Art. 12 und 13](https://eur-lex.europa.eu/legal-content/DE/TXT/?qid=1667467297769&uri=CELEX%3A32016R0679),
[§ 25 TDDDG](https://www.gesetze-im-internet.de/ttdsg/__25.html), der
[Turnstile-Datenschutzzusatz](https://www.cloudflare.com/turnstile-privacy-policy/)
und die [DDDice-Datenschutzerklärung](https://dddice.com/privacy).

## Öffentliche Seiten, Layout und Mailfooter

`/impressum/` und `/datenschutz/` bleiben ohne Anmeldung erreichbar.
Die bestehende Gestaltung, mobile Regeln und Tastaturbedienung bleiben.
Die Seiten verlinken sich gegenseitig; Login/Registrierung, Resetseiten,
Verifizierungsseite, 2FA und Dashboard führen zu beiden Dokumenten.
HTML-/Text-Kontomails enthalten installationsbezogene absolute Legal-Links
aus dem vorhandenen Versandkontext. Für HTTPS korrektes Host-/Proxy-Schema
der jeweiligen Installation prüfen.

Cinzel, Cormorant Garamond, Noto Serif und Noto Serif JP bleiben lokal
eingebunden. Die [Fontdokumentation](../static/fonts/README.md) enthält die
unveränderten OFL-Lizenzen, Quellen und Hashes. Allgemeine Software-/Asset-
Herkunftsdaten sind keine Betreiberangaben.

## Rechtliche Prüfung und Übergabe

Das [technische Verarbeitungsinventar](legal-data-processing.md) enthält
generische Codebelege und Primärquellen ohne Produktionsangaben.
[Nutzungsbedingungen](nutzungsbedingungen-entwurf.md) bleiben ein nicht
veröffentlichter Entwurf ohne Zustimmungszwang.

Vor Veröffentlichung mindestens die lokalen Anbieter-/Vertragsnachweise,
Fristen und tatsächlichen Löschverfahren, Bildreste und gemeinsame
Löschverknüpfungen, Einwilligungs-/Drittlandfragen und die eigenen
Betreiberangaben abschließend prüfen. Danach regulär deployen, Staticfiles
samt Fontlizenzen ausliefern und die tatsächliche Produktionsdarstellung
kontrollieren. Die Architekturänderung benötigt keine Datenbankmigration.

Gezielte Regressionstests:

```powershell
.venv\Scripts\python.exe manage.py test charsheet.tests.test_legal charsheet.tests.test_legal_configuration --keepdb
```

Sie prüfen unter anderem getrennte Installationen, vollständige und fehlende
Konfiguration, Datum/E-Mail, sichere Ausgabe, Integrationserkennung,
Vorrang der lokalen `.env` und vollständige Abdeckung der Variablen in `.env.example`.
Die lokale echte `.env` wird dafür weder als Testfixture ausgelesen noch geändert.
