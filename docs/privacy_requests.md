# Interne Bearbeitung von Datenschutzanfragen

Messwerte, Speicheroptionen und Integritätsnachweise für große PDF-Ausgaben:
[Performancekorrektur des PDF-Exports](privacy_pdf_performance.md).

Das Werkzeug ist über eine interne Superuser-Maske im Django-Admin und über das
Management-Command `privacy_export` verfügbar. Es gibt keinen öffentlichen
Export-Endpunkt, öffentlichen Downloadlink oder E-Mail-Versand.
Eine technische Zusammenstellung ersetzt keine Prüfung durch den Verantwortlichen.
Die inhaltliche Modellzuordnung, neue Prüfabschnitte, bekannte Datenflüsse und
rechtliche Aussagegrenzen stehen in [der Inhaltsprüfung](privacy_content_audit.md).

## Admin-Maske: Hintergrundexport und einmaliger Download

Auf der Admin-Startseite führt **DSGVO-Auskunft** zu `/admin/privacy-export/`.
Zugriff haben ausschließlich aktive Superuser mit Admin-Zugang. Normale
Staff-Berechtigungen reichen nicht. Auch hier ist `DEBUG=False` erforderlich.

1. Nach Benutzername, E-Mail-Adresse oder Charaktername suchen. Teilbegriffe
   reichen aus; archivierte Charaktere und deaktivierte Konten sind enthalten.
2. Das anhand von Konto-ID, Benutzername und E-Mail eindeutig bestimmte Konto
   auswählen. Die Suche zeigt höchstens 25 Konten; bei mehr Treffern eingrenzen.
3. Art. 15 oder Art. 20 wählen, die außerhalb des Werkzeugs erfolgte
   Anfragenprüfung bestätigen und **Prüfung starten** wählen. Die Auskunft
   betrifft das gewählte Konto, auch wenn es über einen Charakter gefunden wurde.
4. **Daten prüfen:** Unkritische Standardwerte werden ohne zusätzliche
   Bestätigung übernommen. Die Ansicht öffnet direkt eine Kategorie mit
   verbleibenden Ausnahmen und zeigt zunächst nur ungeprüfte Einzelprüfungen.
   Art. 20 bietet je Kategorie Checkboxen für Felder, Bereitstellung und
   Rechtsgrundlage. Art. 15 verlangt begründete Einschränkungen am einzelnen Feld.
5. **Verarbeitung:** Betreiberangaben, Zwecke, Empfänger, Speicherdauer,
   Dienstprüfungen und Rechercheergebnisse in beschrifteten Formularen prüfen.
   Ergänzende Daten etwa aus E-Mails werden als bezeichnete Werte erfasst.
6. **Vorschau und Freigabe:** PDF, JSON oder ZIP sowie Benutzerkopie oder
   interne Prüfgrundlage wählen. Für Art. 20 sind JSON und ZIP verfügbar.
   Dateianhänge einzeln prüfen; beigefügte Dateien erfordern ZIP und die
   Dateiprüfbestätigung. Die tatsächliche Ausgabe wird im Hintergrund erzeugt
   und seitenweise angezeigt. Offene Pflichtprüfungen sperren die Freigabe.
   Nach abschließender Bestätigung wird der aktuelle Stand freigegeben.
7. **Export:** Hintergrundexport starten und die fertige Datei einmalig mit
   **Auskunft herunterladen** abrufen. Die Statusseite aktualisiert sich selbst.

Jedes Datenfeld bietet Übernehmen, Schwärzen, teilweise Schwärzen, begründete
Ausnahme und Rückgängigmachen. Im Texteditor schwärzt **Auswahl schwärzen**
den markierten Text; die Vorschau reagiert sofort. Strukturierte Werte werden
einzeln mit verständlichen Bezeichnungen bearbeitet; unveränderte Unterwerte
behalten ihren Datentyp. Alternativ kann ein geprüfter Textauszug eingesetzt
werden. Schwärzungen entfernen keine ganzen Datensätze und ändern keine
Originaldaten. Ohne JavaScript bleiben die serverseitigen Formulare bedienbar.
Es gibt keinen JSON-Editor und keine manuell einzugebenden Feldpfade oder Hashes.

### Automatische Vorprüfung und Ausnahmeprüfung

Die zentralen, versionierten Regeln stehen in `charsheet/privacy_rules.py`.
Automatisch übernommen werden typgeprüfte Zahlen, Wahrheitswerte, Zeitangaben,
geschlossene Auswahlwerte sowie nachgewiesene eigene oder öffentliche Bezüge.
Auch Metadaten eines sicher ermittelten gemeinsamen Datensatzes brauchen keine
Einzelbestätigung; daraus folgt keine automatische Übernahme seiner Freitexte.
Die automatisch erzeugten groben Browser-/Gerätebezeichnungen bei
Sicherheitsereignissen (etwa „Firefox on Windows“ oder „Safari on iPhone“)
gelten ebenfalls als unkritische technische Angaben.
Auch die fünf frei wählbaren Würfel-Ergebnistexte sowie DDDice-Raum-ID,
Würfelbox und Darstellungs-ID werden ohne zusätzliche Inhaltsprüfung
übernommen. API-Schlüssel, Raum-Passwörter und erkannte Zugangsdaten bleiben
unter dem bestehenden Geheimnisschutz; manuelle Schwärzungen haben Vorrang.
Die gespeicherte MMO-Toolbar einschließlich Basis-, Ctrl- und Shift-Leiste,
Slotbelegung, Beschriftungen und Würfelmodifikatoren wird anhand des bestehenden
Hotbar-Speicherformats automatisch übernommen. Die Vorprüfung verändert oder
kürzt die gespeicherten Einstellungen nicht.
Auch das persönliche Wurfprotokoll dieser Toolbar gilt als unkritisch.
Aktuell hält `quickslot_history.js` höchstens zehn Einträge ausschließlich im
Browser-LocalStorage; diese Einträge werden serverseitig nicht gespeichert
und sind deshalb nicht Bestandteil des DSGVO-Serverexports. Sie erzeugen dort
keine zusätzlichen Einzelprüfpunkte.
Nicht durch eine konkrete Standardregel abgedeckte Inhalte bleiben zur Prüfung
vorgemerkt und werden nicht entfernt.

Eigentumsübertragungen, Eigentumshistorien, Berechtigungsvergaben und ihre
Benachrichtigungen werden einschließlich Texten und Snapshots automatisch
übernommen. Eine Suche nach Benutzer- oder Charakternamen ist hierfür nicht
mehr erforderlich. Geheimnisse und bestehende Maskierungen fremder direkter
Benutzerbezüge bleiben geschützt. Die endgültige Freigabe bleibt erforderlich.

Selbstgewählte Passkey-Namen, sichere Sicherheitsmetadaten einschließlich
Sitzungsanzahl sowie eigene Skill-Ausprägungen und Spezifikationen sind
Standarddaten. Hochgeladene Bilder einschließlich ihrer Dateinamen werden
automatisch übernommen und im ZIP vorausgewählt. Dafür ist keine gesonderte
Dateiprüfbestätigung erforderlich; für andere Anhänge bleibt sie bestehen.
Dateinamen werden ohne Speicherverzeichnis ausgegeben. Die bisherigen
Pfad-, Dateityp- und Integritätsprüfungen gelten weiterhin.

Eine nach dem bestehenden Kalenderschema validierte Anordnung einschließlich
reiner Trennzeichen wird vollständig automatisch übernommen. Enthält sie freien
Zusatztext, konzentriert sich der Editor auf diesen Text; Positionen, Größen
und Ausrichtung werden nicht zur Einzelprüfung vorgelegt.

Spielgruppeneinladungen werden automatisch übernommen, sofern keine fremden
Benutzernamen oder Benutzerkennungen enthalten sind. Charakterbezeichnungen
und Charakter-, Gruppen- und Einladungskennungen sind zulässig; fremde
Benutzerbezüge und nicht eindeutig zuordenbare ID-Angaben bleiben offen.
Eigene Benutzerkennungen lösen keine Ausnahme aus. Die Erkennung arbeitet
mit einer einmal geladenen Kontoliste, berücksichtigt strukturierte Inhalte
und HTML und speichert ausschließlich Trefferkennzeichen. Fehlende Nachweise
werden vor der Prüfung neu erstellt; neue Namenstreffer entwerten alte Freigaben.

Eigene Kreaturenangriffe einschließlich Namen und Notizen sind Standarddaten.
Eigene Charakterangaben einschließlich Beschreibungen und Erscheinungsmerkmalen,
Charaktertagebücher und selbstgewählte Charakterkreatur-Namen werden ebenfalls
automatisch übernommen. Eigene Spielgruppen einschließlich Namen und Notizen
sind Standarddaten. Geheimnisse und manuelle Schwärzungen behalten Vorrang.
Auch eigene Charaktergegenstände, Runenspezifikationen, konkrete Effekte,
Identifikations- und Offenlegungsangaben sowie Kreaturengegenstände werden
automatisch übernommen. Das gilt für Freitexte und strukturierte Angaben
einschließlich darin enthaltener Charakternamen; eine gesonderte Suche nach
fremden Charakternamen findet nicht statt. Angeschlossene Gegenstandswerte
und Bezüge sind ebenfalls Standarddaten; Geheimnisse und direkte fremde
Benutzerbezüge bleiben nach den bestehenden Schutzregeln geschützt.

Zugeordnete Gruppentabellen einschließlich Spalten, Zellen und gespeicherter
Würfelprotokolle wie „Fehlschlag: Elementarmagie“ sind Standarddaten. Das gilt
auch für Inhalte, die bislang unter „Weitere zu prüfende Inhalte“ erschienen.
Die Zuordnung erfolgt über den Ersteller oder eine eigene Spielgruppe,
nicht allein über den Tabellentitel. Auch zugehörige Tabellen anderer Ersteller
werden einschließlich ihrer Strukturangaben automatisch übernommen.
Die erfassten Anmeldeprotokolle (AccessLog, AccessAttempt, AccessFailureLog)
werden einschließlich Browser, IP-Adresse und Zeitangaben automatisch
übernommen, wenn ihr Benutzername exakt dem ausgewählten Konto entspricht.
Unklare Kontozuordnungen, Sicherheitsgeheimnisse und manuelle Schwärzungen
bleiben geschützt; die abschließende Freigabe ist weiterhin erforderlich.

Administrative Vorgänge werden einschließlich historischer Objektbezeichnungen
und Protokolltexte automatisch übernommen, sofern keine Benutzeranlage
protokolliert wurde. Die Erkennung verwendet Aktionstyp und Zielmodell sowie
strukturierte Angaben über zusätzlich angelegte Benutzer, auch bei Änderungen
an anderen Objekten. Änderungen und Löschungen bereits bestehender Benutzer
sind keine Benutzeranlage. Bei einer Benutzeranlage bleibt der gesamte Eintrag
zur Einzelprüfung offen. Auch historische Aktionen und Objekttypen sind
Standarddaten, sofern die Verwaltungsmetadaten vorliegen. Geheimnisse,
bestehende Maskierungen fremder
Verwaltungsakteure und manuelle Schwärzungen bleiben erhalten.

Die Zusammenfassung nennt automatisch übernommene Felder, Einzelprüfungen,
offene Ausnahmen und geschwärzte/geschützte Werte. Regeln und ihre Anzahlen
sind aufklappbar nachvollziehbar. Manuelle Entscheidungen haben immer Vorrang;
das Rückgängigmachen einer automatischen Übernahme macht genau dieses Feld
wieder offen. Die optionale globale Neuausführung der Standardprüfung
überschreibt weder Schwärzungen noch solche manuellen Rücknahmen.

Die Sammelbearbeitung in Schritt 3 übernimmt, schwärzt oder öffnet markierte
Felder einer Seite oder alle gefilterten Felder der ausgewählten Kategorie
einschließlich weiterer Ergebnisseiten. Eine gemeinsame Begründung wird im
Prüfstand gespeichert. Geschützte Werte lassen sich ebenfalls gesammelt
bearbeiten; beim Übernehmen bleiben ihre Maskierungen erhalten. Nicht verfügbare
Inhalte werden dabei mit dokumentierter Begründung geschützt beibehalten.
Auswahl, Filter, Signaturen und Prüfversion werden auf dem
Server geprüft; eine Änderung entwertet Vorschau und Freigabe. Es wird nur ein
Request benötigt, unabhängig von der Anzahl gefilterter Felder.

Eine Klassifizierung wird je unveränderlichem Datenbestand und Regelversion
einmal berechnet und in einer signierten privaten `precheck.json` abgelegt.
Seitenwechsel und Filter verwenden diesen Nachweis erneut. Die Regelanwendung
wird kompakt je Kategorie gespeichert, nicht als zehntausende Einzelbestätigungen.
Der interne Export enthält unter `automatic_review` Regelstand, Bestandsbindung,
verwendete Regeln, Anzahlen und manuelle Abweichungen. Diese Angaben gehören
nicht in die Benutzerkopie. Alle neuen Prüfdateien unterliegen derselben
automatischen Bereinigung. Änderungen am Bestand oder Regelstand entwerten die
bisherige Freigabe; eine endgültige Freigabe erfolgt niemals automatisch.

Die Datensammlung und PDF-/ZIP-Erstellung laufen in einem separaten Prozess,
außerhalb des synchronen Gunicorn-Requests. Jede Anfrage erhält ein isoliertes,
privates Verzeichnis. JSON, PDF und ZIP werden dateibasiert geschrieben; auch
Anhänge werden blockweise kopiert. Der HTTP-Download verwendet `FileResponse`.
Der Speicherort auf dem Client richtet sich nach den Browser-Einstellungen.

Ein grafischer Prüfvorgang läuft höchstens **60 Minuten ab Beginn**; der Rest
wird angezeigt. Ein fertiger Export läuft spätestens **15 Minuten nach
Fertigstellung**, begrenzt durch die ursprüngliche Prüffrist, ab. Die ältere
direkte Exportschnittstelle bleibt auf 15 Minuten ab Beauftragung begrenzt.
Nach Ablauf darf kein neuer Download beginnen. Ein laufender Download hält
die Dateisperre bis zum Schließen der Response; ein eigener Zeitgeber beendet
auch einen festhängenden Download spätestens mit der verbleibenden Jobfrist.
Dann werden Datei, Prüfangaben, Jobmetadaten und das ganze Jobverzeichnis entfernt.
Das gilt auch für den WSGI-Abbruchpfad bei getrennten Browser-Verbindungen.
Fehler bei Sammlung, Vorschauerstellung oder Export entfernen den gesamten
Prüfvorgang einschließlich Teilausgaben sofort. Normale Formularfehler werden
vorher angezeigt und lassen sich direkt korrigieren.
**Prüfung beenden und löschen** entfernt den Vorgang sofort.

Ein unabhängiger Monitorprozess überlebt den Renderer oder Gunicorn-Worker,
beendet überlange Renderer und bereinigt abgelaufene Jobs. Zusätzlich ist der
unten beschriebene systemd-Timer oder ein entsprechender Benutzer-Cronjob
zwingend einzurichten: Er beseitigt Rückstände
auch nach Ausfall sämtlicher beteiligter Prozesse oder einem Serverneustart.
Vorhandene Original-Uploads werden ausschließlich gelesen.

Suche, Kontowahl und Export erfolgen per CSRF-geschütztem POST. Suchbegriffe
stehen nicht in der URL. Antworten sind mit `Cache-Control: private, no-store`
versehen. Status-URLs enthalten nur eine zufällige Kennung, keine Kontodaten.
Status und späterer Abruf erfordern erneut einen aktiven Superuser und die
Übereinstimmung mit dem beauftragenden Administrator. Der Abruf ist ein
CSRF-geschützter POST und nur einmal möglich. Es gibt keine Export-DB-Einträge.
Die Webserver-/Proxykonfiguration muss diese Vorgaben beachten und darf keine
Antwortinhalte oder Formulardaten in Logs, Caches oder temporären Dateien
persistieren. Für den Download wird zusätzlich `X-Accel-Buffering: no` gesetzt.

Prüfstruktur, Prüfwert, Konto-ID und Zeitpunkt erzeugt die Oberfläche automatisch.
Jede Änderung an Entscheidungen, Angaben oder Ausgabeoptionen entwertet Vorschau
und Freigabe. Veraltete Formulare und manipulierte Feld-/Unterwertreferenzen
werden serverseitig abgewiesen. Vor Vorschau und Export wird der aktuelle
Datenbestand erneut geprüft; auch Änderungen hinter einer Schwärzung entwerten
die Freigabe. Die Prüfung bleibt ausschließlich in privaten temporären Dateien.

Die folgenden Aufruf-/Pfadangaben betreffen ausschließlich das weiterhin
verfügbare Server-Command. Dessen ausdrücklich angeforderte Dateien werden im
angegebenen privaten Verzeichnis gespeichert und separat entfernt.

### Servereinrichtung und automatische Restebereinigung

Unter Linux ist die Standardablage `/var/lib/codex-arcana/privacy-exports`.
Alternativ `PRIVACY_EXPORT_TEMP_ROOT` als absolute Umgebungsvariable setzen
(auch in der `.env` möglich). Unter Windows wird standardmäßig ein privates
Unterverzeichnis des System-Tempverzeichnisses verwendet. Keine Webserver-Aliase,
Backups oder öffentliche Freigaben für diese Ablage konfigurieren. Repository,
`MEDIA_ROOT`, `STATIC_ROOT`, Static-Verzeichnisse und Pfadverknüpfungen werden
abgewiesen. Verzeichnisrechte: `0700`, Dateirechte: `0600`; unter Windows private
DACL für Prozesskonto und SYSTEM. Die Ablage muss dem Dienstkonto gehören.

Beispiel für Linux (Dienstkonto und Installationspfad anpassen):

```sh
sudo install -d -o codex -g codex -m 0700 /var/lib/codex-arcana/privacy-exports
```

Ohne zusätzliche sudo-Rechte kann das Dienstkonto eine private Ablage außerhalb
des Repositorys in seinem Home-Verzeichnis verwenden:

```sh
install -d -m 0700 "$HOME/.local/share/codex-arcana/privacy-exports"
```

In der bestehenden `.env` anschließend `PRIVACY_EXPORT_TEMP_ROOT` auf den
vollständigen absoluten Pfad setzen und Gunicorn neu starten. Die Standardablage
unter `/var/lib` wird ohne entsprechende Rechte nicht automatisch eingerichtet.
Eine fehlende oder unbeschreibbare Ablage verhindert bereits den Start.

`/etc/systemd/system/codex-privacy-cleanup.service`:

```ini
[Unit]
Description=Codex Arcana private export cleanup

[Service]
Type=oneshot
User=codex
Group=codex
WorkingDirectory=/srv/codex-arcana
Environment=PRIVACY_EXPORT_TEMP_ROOT=/var/lib/codex-arcana/privacy-exports
ExecStart=/srv/codex-arcana/.venv/bin/python manage.py privacy_export_job --cleanup
UMask=0077
```

`/etc/systemd/system/codex-privacy-cleanup.timer`:

```ini
[Unit]
Description=Remove expired Codex Arcana exports every minute

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s
Unit=codex-privacy-cleanup.service

[Install]
WantedBy=timers.target
```

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now codex-privacy-cleanup.timer
sudo systemctl start codex-privacy-cleanup.service
systemctl list-timers codex-privacy-cleanup.timer
```

Unter Windows denselben Befehl `manage.py privacy_export_job --cleanup` jede
Minute und beim Systemstart unter dem Dienstkonto über die Aufgabenplanung
ausführen. Ein kompletter Systemausfall verzögert die physische Löschung bis
zum nächsten Start; abgelaufene Dateien bleiben bereits für Downloads gesperrt.
Die effektive Restefrist beträgt die jeweilige Jobfrist zuzüglich des
Timerintervalls. Aktive OS-Dateisperren schützen laufende Downloads bis zum
Responseende oder zum begrenzenden Download-Zeitgeber.
Nach Prozessende gibt das Betriebssystem diese Sperren automatisch frei.

Unter Linux kann alternativ der vorhandene Cron-Dienst die Bereinigung unter
dem Anwendungskonto ausführen. Beispiel für dessen Benutzer-Crontab
(Installationspfad anpassen, bestehende Einträge erhalten):

```cron
* * * * * cd /srv/codex-arcana && /srv/codex-arcana/.venv/bin/python manage.py privacy_export_job --cleanup >/dev/null 2>&1
@reboot cd /srv/codex-arcana && /srv/codex-arcana/.venv/bin/python manage.py privacy_export_job --cleanup >/dev/null 2>&1
```

Der Bereiniger löscht ausschließlich mit passendem Marker gekennzeichnete
Jobverzeichnisse und bekannte Arbeitsdateien. Fremde Dateien, Verknüpfungen und
unmarkierte Verzeichnisse bleiben erhalten. Schreibfehler und weniger als
256 MiB freier Speicher brechen kontrolliert ab. Es gelten höchstens vier
offene Jobs insgesamt und ein offener Job pro Administrator. In eigenen Django-
Settings sind `PRIVACY_EXPORT_MAX_JOBS` und `PRIVACY_EXPORT_MIN_FREE_BYTES`
anpassbar. Für Betrieb mit mehreren Hosts muss Erstellung, Status und Download
auf dasselbe private Dateisystem zugreifen. Keine Erhöhung des Gunicorn-Timeouts
ist für die Hintergrundgenerierung nötig. Auch die grafische Ausgangssammlung
und die tatsächliche Vorschau laufen im Hintergrund.

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
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --request-verified --format zip --internal-review --output-dir C:\Private\CodexExports
```

`--request-verified` bestätigt die bereits außerhalb des Werkzeugs erfolgte
Anfragenprüfung; der Schalter authentifiziert die anfragende Person nicht.
Die Vorschau zeigt nur Kategorien und Anzahlen, keine Namen, Adressen oder Inhalte.
Art. 15 ist der Standardmodus `--mode access`.

Jeder Aufruf erstellt ein neues, zufällig benanntes Unterverzeichnis
`privacy-export-…`. Eine PDF-Ausgabe enthält den A4-Bericht; JSON enthält den
strukturierten Export; ZIP enthält `report.pdf` und `data.json`. Auch leere
Datenkategorien bleiben im JSON ausgewiesen.
`--internal-review` erzeugt bei JSON stattdessen `audit.json`; bei ZIP wird
`audit.json` zusätzlich aufgenommen. Die interne Ausgabe enthält Prüfkandidaten
und Bearbeitungsangaben und darf nicht als Benutzerkopie weitergegeben werden.

Für zuvor administrativ geprüfte Anhänge:

```powershell
.venv\Scripts\python.exe manage.py privacy_export --user-id 123 --request-verified --format zip --include-files --files-reviewed --output-dir C:\Private\CodexExports
```

Ohne diese beiden Dateischalter enthält das Paket ein Dateiverzeichnis, jedoch
keine hochgeladenen Dateiinhalte. Das steht als „Nicht beigefügt“ im Bericht
und als `not_included` im JSON. Auch ohne Dateikopien werden lokale
Dateizuordnungen validiert.
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
PDF und Benutzer-JSON verwenden dieselben persönlichen Datensätze und geprüften
Ergänzungen. Administrative Prüfwerte und die vollständige Prüfstruktur stehen
ausschließlich in der gesonderten internen `audit.json`.
Im ZIP werden Dateigröße und SHA-256 der tatsächlich kopierten Bytes
vor der Erstellung beider Berichte ergänzt. Anhänge stammen aus dem lokalen
Dateisystem; für gleichzeitig veränderte Uploads sollte der Betreiber eine
ruhige Betriebsphase wählen. Die DB-Transaktion sperrt das Dateisystem nicht.

Erfasst werden über geprüfte Eigentumsbeziehungen insbesondere:

| Bereich | Automatisch zusammengestellte Informationen |
| --- | --- |
| Konto | ID, Benutzername, E-Mail, Name, Aktiv-/Adminstatus, Registrierung und letzter Login |
| Einstellungen | Darstellung, Druck, Spiel-/Würfeloptionen, Kalender und Schnellzugriffe, Verifizierungs- und 2FA-Status ohne Geheimnisse |
| Entwürfe | Charaktererstellungsentwürfe und eigene Erstellungsvorlagen |
| Charaktere | Alle gespeicherten Charakterfelder, einschließlich archivierter Charaktere |
| Regelzuordnungen | Attribute, Fertigkeiten, Spezifikationen, Sprachen, Eigenschaften und Entscheidungen |
| Fortschritt | Schulen, Pfade, Techniken, Spezialisierungen, Meisterschaften, Lektionen, Zauber und gespeicherte Erwerbsdaten |
| Weitere Charakterdaten | Glaubens-/Traditionsbindungen, Aspekte, Vampirismus und dämonische Kräfte |
| Inventar | Eigene Gegenstände, Beschreibungen, Overrides, Runen, semantische Effekte, Offenlegungs- und Identifikationszustände |
| Kreaturen | Eigene Kreaturen samt Ausrüstung, Fertigkeiten, Angriffen, Eigenschaften, Befehlen und Unterdatensätzen |
| Chronik und Kalender | Tagebucheinträge, Reihenfolge, gespeicherte Zeiten/Spieldaten, Kalenderlayout und Charakterdatum |
| Gruppen | Rollen, Mitgliedschaften, Einladungen, eigene Gruppenkreaturen und zugeordnete Unterdaten; gemeinsame Inhalte werden zur Einzelfallprüfung ermittelt |
| Transfers | Eigene Sender-/Empfänger-/Akteurbezüge, Zustände, Mengen, Zeiten, Eigentumsereignisse, Berechtigungen und Benachrichtigungen |
| Sicherheit | Eigene AccountSecurityEvents samt zugelassenen Zusatzangaben, Passkey-Metadaten, Recovery-Code-Zeiten und rekonstruierbare kontogebundene Zugriffszähler |
| Sitzungen | Ablauf-/Anmeldestatus und zugeordnete persönliche Zustände ohne Schlüssel oder Challenges; auch noch gespeicherte abgelaufene Sitzungen |
| Weitere Anmeldeinformationen | Axes-Zeilen zum aktuellen Benutzernamen; Zuordnung administrativ prüfen |
| Verwaltung | Eigene Admin-Aktivitäten sowie Änderungen über das Konto und eigene Datensätze durch andere Administratoren; gemischte Inhalte gesondert prüfen |
| Dateien | Direkte Dateifelder der exportierten eigenen Datensätze; optional geprüfte lokale Bytes im ZIP |

Die Konto-/Charakterkategorien werden anhand der tatsächlichen
Modellbeziehungen aufgelöst. Zusätzliche gemeinsam genutzte Kategorien werden
gesondert und eingeschränkt erfasst. Neue direkt personenbezogene Modelle ohne
geprüfte Zuordnung lassen die Sammlung abbrechen. Dies ersetzt bei einer
Modellerweiterung keine erneute Prüfung von Feldern, JSON und indirekten Bezügen.

Die interne `audit.json` enthält unter `data.categories` je Modell ein
Feldverzeichnis und die Datensätze. Das Verzeichnis nennt Feldbedeutung, Django-Typ, verfügbare Choices und
Zielmodell von Beziehungen. IDs sind interne Datenbankkennungen; unter
`data.references` stehen Namen referenzierter allgemeiner Katalogdaten. Private
Gruppenkataloge werden dafür nicht aufgelöst. Fehlende Werte sind `null`, leere
Texte `""`, Zeiten ISO 8601 mit Zeitzone, reine Datumswerte Kalenderdaten.
Dezimal-/UUID-Werte werden verlustfrei als Zeichenfolge serialisiert.
Die Benutzerkopie `data.json` enthält die persönlichen Datensätze mit passenden
Feldbezeichnungen und minimalen Zuordnungsangaben. Sie enthält keine Legal-
Konfiguration, Prüfkandidaten, Prüfnotizen oder Freigabe-Hashes. Das vollständige
interne Modellinventar steht in `audit.json` unter `data.category_mapping`.

Der öffentliche, bisherige Kontoexport bleibt unverändert. Sein schmales Format
enthält nur einige Charakter-, Inventar- und Tagebuchfelder und eignet sich
deshalb nicht als Grundlage dieser umfassenden internen Auskunft.

## Grenzen, Schwärzungen und manuelle Ergänzungen

Passwort-Hashes, TOTP-Secrets, Recovery-Code-Hashes, Verifizierungstoken,
private Schlüssel, API-Schlüssel, Raum-Passwörter,
Geheime Sitzungs-/Challenge-Inhalte und Drosselungs-Digests verlassen den
Snapshot nicht.
Öffentliche Passkey-Registrierungskennungen und öffentliche Schlüssel sind
gesonderte Base64-Prüfkandidaten. Nach konkreter Entscheidung können sie als
öffentliche Registrierungsdaten bereitgestellt werden; sie werden nicht pauschal
als Geheimnisse behandelt. Persönliche Sitzungszustände sind von den geheimen
Sitzungsschlüsseln und Challenges zu unterscheiden.
Die zugelassenen Sicherheitszusatzangaben `label` und `session_count` sowie
bereinigte persönliche Quickslot-JSON-Inhalte werden ausgegeben. Weitere
Sicherheitsmetadaten benötigen eine explizite Einzelfallentscheidung; ihre
unbekannten Werte werden nicht ungeprüft in die Prüfgrundlage kopiert.
Verdächtige Schlüssel und Zugangsdatenmuster in eigenen JSON-Daten werden rekursiv
geschützt; beliebige Freitexte können technisch nicht zuverlässig anonymisiert
werden und bleiben prüfpflichtig. Eigene Berechtigungsgruppen und wirksame
Zugriffsrechte werden ohne die Mitgliederdaten anderer Konten ausgegeben.

Fremde Konto-/Charakterzuordnungen, Gruppennamen, gemeinsame Nachrichten,
Transfer-Snapshots/-Details und Gruppennotizen werden im Entwurf geschützt. Das gilt auch
für eigene Nachrichten in gemeinsam genutzten Datensätzen, weil sie Angaben
über Dritte enthalten können. Diese Inhalte bleiben als interne Prüfkandidaten
nachvollziehbar; über `resolutions` sind geprüfte persönliche Auszüge freigebbar.
Generische Objektzuordnungen werden nicht ungeprüft aufgelöst, sondern erzeugen
offene Prüfungen. Jede automatische oder administrative Schwärzung wird intern in
`data.omissions` mit Modell, Datensatz, Feld und Grund dokumentiert, soweit sie
einen konkreten ausgegebenen Datensatz betrifft.

Gesondert zu prüfen sind insbesondere Gruppen-SL-Notizen, Tabellen samt Zellen,
SL-Kreaturenkarten, Gruppenkataloge, gemeinsame Inventare, Text-/Bild-Erwähnungen
in fremden Charakteren und Datensätze ohne verbleibende Eigentumszuordnung.
Die Erstellerschaft einer Gruppe oder Tabelle beweist keine alleinige
Dateneigentümerschaft. Gruppennotizen und zugeordnete Tabellen werden als
Prüfkandidaten erfasst; andere Inhalte ohne sichere Zuordnung sind ergänzend zu
recherchieren. Sie werden nicht pauschal exportiert. Nach
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

## Prüfdatei und finale Freigabe beim Server-Command

Nur das optionale Server-Command verwendet eine manuelle Prüfdatei; die
reguläre Adminoberfläche erzeugt diese Struktur vollständig aus Formularen.
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
Die zusätzlich erforderlichen Bereiche `coverage`, `services`, `resolutions`,
`supplements`, `controller` und `file_decisions` sind in
[der Inhaltsprüfung](privacy_content_audit.md) beschrieben. Dieses kurze Beispiel
allein erlaubt keine endgültige Freigabe.
Validierte `LEGAL_INFO`-Werte bleiben als interne Recherchegrundlage erhalten.
Geprüfte Kontakt- und Dienstangaben erscheinen verständlich im Bericht.
Redaktionelle Verantwortung und Berufsaufsicht werden nicht als Datenschutz-
Verantwortlicher oder Datenschutzaufsicht umetikettiert. Interne Schalter, Prüffelder und
Dienstekonfigurationen werden nicht ausgegeben. Tatsächliche Verarbeitung durch
Turnstile oder administrative Dienste muss in den geprüften Zwecken, Empfängern,
Fristen und Drittlandangaben enthalten sein. Fehlende Pflichtangaben stehen in
einem Entwurfshinweis; Konfigurationsplatzhalter werden nicht als Auskunftstext
ausgegeben. Eine Freigabe wird bei fehlenden Angaben abgewiesen.

Nach vollständiger Prüfung des so erzeugten Entwurfs den Wert `review_sha256`
aus der internen `audit.json` zusammen mit der geprüften Konto-ID und dem realen Prüfzeitpunkt
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
Bei Art. 15 müssen Zwecke, Empfänger, Speicherdauer, Herkunft, Drittland-/
Garantieangaben, Angaben zu Art.-22-Entscheidungen sowie Verantwortlicher,
Anschrift und Kontakt vollständig sein. Die Rechtsgrundlagen sind ergänzend.
Prüfbereiche, Dienste, Einzelfallkandidaten und fehlende Dateikopien ohne
Zustellungs-/Ausnahmeentscheidung sperren ebenfalls die Freigabe. Stimmen Daten, Dateien
oder Konto nicht mehr mit der Prüfung überein, wird die Freigabe abgelehnt.
Ein neues Erstellungsdatum allein invalidiert die Freigabe nicht. Das fertige
PDF dokumentiert den Freigabestatus; Prüfzeitpunkt und Datenprüfwerte stehen im
internen JSON. Die technische Freigabe ist eine dokumentierte
administrative Erklärung, keine elektronische Signatur oder Rechtsprüfung.

Für die Freigabe daher zuerst eine interne JSON-/ZIP-Prüfgrundlage erstellen.
Dateischalter und
Ausgabeumfang müssen zwischen Prüfung und Freigabe
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

Für ausdrücklich mit dem Server-Command erstellte Ausgaben ist der Betreiber
für die zeitnahe Entfernung nach Bearbeitung verantwortlich. Diese sind keine
HTTP-Jobdateien und werden nicht vom HTTP-Bereiniger gelöscht:

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
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_jobs --keepdb
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_content --keepdb
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_review --keepdb
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_rules --keepdb
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_transfer_rules --keepdb
node charsheet/tests/test_privacy_review_ui.js
```

Geprüft werden Eigentumsbeziehungen, archivierte Daten, geschützte gemeinsame
Inhalte, Geheimnisausschluss, Sitzungen, Inventarunterdaten, Art.-20-Feldauswahl,
Schwärzungen/Freigabebindung, Vorschau, JSON-Prüfwerte, PDF-/ZIP-Konsistenz,
Anhänge, Fehlerbereinigung, geschützte Pfade und Löschung. Lange Historien und
ununterbrochene Texte werden anhand der PDF-Textinhalte und Textgrenzen geprüft.
Browser, Screenshots und visuelle Tests werden nicht verwendet.

Die Admin-Tests prüfen zusätzlich Benutzer-/E-Mail-/Charaktersuche, archivierte
Charaktere und deaktivierte Zielkonten, Superuser-Zugriff, CSRF, Vorschau,
Art.-20-Prüfangaben, asynchrone Erstellung, PDF-/JSON-/ZIP-Antworten und die
erneute Berechtigungs-/CSRF-Prüfung beim Abruf. Lifecycle-Tests weisen die
vollständige Bereinigung nach Erfolg, Abbruch, Schreib-/Rendererfehlern und
Fristablauf nach. Ein realer separater Prozess wird absichtlich beendet; danach
muss der Bereiniger dessen verwaiste Dateien entfernen. Unbekannte Dateien
bleiben erhalten. Ein festhängender Download wird innerhalb der definierten
Frist geschlossen und vollständig bereinigt. Die grafischen Tests prüfen
zusätzlich strukturierte Teilschwärzungen mit Typerhalt, Rückgängigmachen,
Formulargenerierung, Pflichtangaben, signierte Feldreferenzen, veraltete
Formulare/Freigaben, Ergänzungen, tatsächliche PDF-/JSON-/ZIP-Ausgaben und
die Löschung sämtlicher neuer Prüf- und Zwischenstandsdateien.

Lange Texte werden ohne Kürzung als über Seiten fortsetzbare Absätze gesetzt.
Das HTML pro Layoutblock ist auf 16.000 Zeichen begrenzt. Jeder Block wird einmal
in eine private Arbeitsdatei gerendert. Inhaltsverzeichnis und Links entstehen
nach dem Bericht; endgültige Seitenzahlen und Lesezeichen nach dem Zusammenfügen.
A4-Ränder, Seitenzahlen, Verweisziele und Textvollständigkeit werden automatisch
geprüft. Interne Feldverzeichnisse bleiben in `audit.json`. HTML aus
gespeicherten Daten wird als Text behandelt und nicht ausgeführt oder nachgeladen.

ORM-Ergebnisse werden blockweise gelesen; Dateiinhalt wird blockweise ins ZIP
geschrieben und ZIP64 unterstützt. Der normalisierte Snapshot sowie das PDF-
Seitenstrukturen liegen im Arbeitsspeicher, dessen Bedarf mit dem Konto wächst.
Große PDF-/ZIP-Bytepuffer werden vermieden; Python-Speicherspitze, Laufzeit und
die vom Betriebssystem gemeldete Prozessspeicherspitze einschließlich nativer
MuPDF-Allokationen werden am synthetischen großen PDF-Test gemessen.
Laufzeiten der Sammlung, Layoutblöcke und
Dateierstellung werden ohne Kontodaten protokolliert. Bei sehr
großen Konten ausreichend RAM und privaten Speicher bereitstellen; es gibt keine
stille Kürzung oder Datensatzobergrenze. Der Test mit langer Historie ist kein
Nachweis für beliebig große Produktivkonten. Vor Weitergabe bleibt die konkrete
inhaltliche und rechtliche Vollständigkeitsprüfung erforderlich.
