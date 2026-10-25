# Allgemeines technisches Verarbeitungsinventar

Dieses Inventar beschreibt die Funktionen des Repositorys, nicht den Betrieb
einer bestimmten Installation. Betreiber, Anbieter, Standorte, Verträge,
Aufbewahrungsregeln und das Datum einer lokalen rechtlichen Inhaltsprüfung
werden hier nicht dokumentiert. Sie gehören ausschließlich in die lokale
`.env` nach [docs/legal.md](legal.md).

## Datenverarbeitung der Standardanwendung

| Funktion | Daten, Empfänger und Grenzen | Quelltext |
| --- | --- | --- |
| Registrierung und Konto | Benutzername, erforderliche E-Mail bei neuen Konten, Passwort-Hash, Konto-ID, Aktivstatus, Berechtigungen und Einstellungen; eigene Anwendung und tatsächlich verwendeter Hostingbetrieb | `charsheet/forms.py`: `RegistrationForm`; `views.py`: `register`, `AppLoginView`; `models/user.py` |
| E-Mail-Verifizierung | Adresse, Prüfstatus, Nonce-/Tokenbezug und Versandzeit; Bestätigungslink über das konfigurierte Mailverfahren | `email_verification.py`; Loginpflicht und Linkgültigkeit aus Django-Einstellungen, kein im Legal-Text duplizierter Wert |
| Passwort-Reset | Adresse und zeitlich begrenzter Einmallink; gleiche öffentliche Antwort bei bekannten/unbekannten Konten; Linkablauf ist keine Löschung von Versandlogs | `AppPasswordResetView`, `AppPasswordResetForm`, `AppPasswordResetConfirmView` |
| Passwortprüfung | Eingegebenes Passwort und ggf. E-Mail zur serverseitigen Policyprüfung; kein eingebundener externer Passwortprüfdienst | `password_policy_status`, `password_validation.py` |
| Optionale Passkeys | Öffentliche Credentials, Credential-ID, Zähler, Typ-/Transport-/Backupmetadaten, Zeiten; Konto-/Anzeigename an den vom Benutzer gewählten Authenticator; keine privaten Schlüssel oder Biometrie an die Anwendung | `passkeys.py`, `PasskeyCredential`, Passkey-Views und `static/js/passkeys.js` |
| Optionale TOTP-/Recovery-Anmeldung | Verschlüsseltes TOTP-Geheimnis, Aktivierungsstatus/-zeit, gehashte Recovery-Codes und Verbrauchszeiten; QR lokal erzeugt, Kontobezeichnung an gewählten Authenticator | `two_factor.py`, `TwoFactorRecoveryCode`, 2FA-Views |
| Kontosicherheitsereignisse | Konto, Ereignis, Zeitpunkt, Quell-IP, grobe Geräteübersicht und begrenzte Metadaten; keine Passwörter, Recovery-Codes oder Sitzungsschlüssel als Ereignisinhalt | `auth_security.py`, `AccountSecurityEvent`; Frist direkt aus `ACCOUNT_SECURITY_ACTIVITY_RETENTION_DAYS`, tatsächliche Bereinigung lokal beschreiben |
| Anmeldesperren | Axes verarbeitet Kontobezug, IP, Header-/Pfad-/Zeitinformationen und Versuchszähler; eigene Rate-Limits verwenden HMAC-bezogene IP-/Kontobuckets und Sperrzeiten; pseudonymisiert, nicht anonym | `auth_security.py`, `AuthenticationThrottle`, Axes-Konfiguration; tatsächliche Speicher-/Bereinigungsregeln lokal, nicht aus Cooldowns ableiten |
| Sitzungen und CSRF | Cookie-Zuordnung und serverseitiger Sitzungszustand einschließlich laufender Sicherheitsprüfungen und temporärer Spielwerte | Middleware, `session_management.py`, Sessionzugriffe in `views.py`; Erklärung liest Cookie-Namen und -Dauern direkt aus Django |
| Charaktere, Entwürfe und Vorlagen | Kontobezogene Spielwerte, Inventar, Bilder, Tagebuch und Freitexte; reale Personenbezüge können über Konten oder Inhalte entstehen | `models/character.py`, `creation_templates.py`, `calendar.py`, Charakter-/Lernviews |
| Spielgruppen und SL-Funktionen | Rollen-/Einladungshistorie, Mitgliedschaften, Nachrichten, Tabellen, Notizen und gemeinsame Karten; Sichtbarkeit nach Berechtigungen | `models/groups.py`, `game_groups.py`, `group_views.py` |
| Empfängersuche und Übergaben | Charakternamen, Rasse und Benutzername können für andere angemeldete Nutzer sichtbar werden; Übergabe-/Eigentumshistorie und Freigaben | `character_recipient_search`, Gruppen-/Transferfunktionen; keine pauschale Privatheitszusage |
| Medien | Eigene hochgeladene Bilder; direkt erreichbare Medien-URLs können ohne Anmeldung abrufbar sein; Kontolöschung entfernt zugeordnete Uploads nach erfolgreichem Commit vollständig aus dem aktiven Speicher | `account_lifecycle.py`: `schedule_account_image_deletion`, `_delete_account_image`; Speicherung und physische Löschung durch das jeweilige Storage-Backend |
| LocalStorage | Fenster-/Kartenlayout, Auswahlzustände, Kampfberechner, Modifikatoren und bis zu zehn Schnellslot-Würfe; alte Tagebuchdaten können lokal verbleiben | `static/js/charsheet/` und Legacy-Oberfläche; allgemein keine TTL, Browserdatenlöschung nötig |
| SessionStorage | Aktive Tabs, Zauberfilter, SL-Zwischenauswahl und Anzeigestände | `tabs.js`, `spell_panel.js`, `damage_panel.js`, `game_master_screen.js`; Dauer der Tab-Sitzung bzw. Browserwiederherstellung |
| Übernahme lokaler Daten | Ältere lokale Tagebücher können zu Serverdaten werden; Schnellslotlayout wird kontogebunden gespeichert | `charsheet_diary.js`, `quickslots.js`, `CharacterQuickslotLayout`; „niemals übertragen“ wäre unzutreffend |
| Deaktivierung, Löschung und Export | Deaktivierung erhält Daten; geschützte gemeinsame Verknüpfungen können automatische Löschung blockieren; JSON-Export enthält nicht sämtliche Auskunftsdaten | `account_lifecycle.py`, `session_management.py`, Konto-/Exportviews; externe Daten, Backups und Browserdaten gesondert behandeln |
| Sicherungs-/Testwerkzeuge | Werkzeuge können Datenbank und Medien kopieren; Vorhandensein beweist weder Nutzung noch Aufbewahrung | Betrieb und etwaige Kopien nur lokal beschreiben; keine tatsächlichen Sicherungsintervalle aus dem Repository ableiten |

## Feste optionale Integrationen

**Cloudflare Turnstile:** Skript und serverseitige Prüfung gehören zum
implementierten Funktionsumfang. Aktivität und Formularauswahl folgen allein
den vorhandenen Django-Einstellungen. Bei deaktiviertem Flag wird keine aktive
Verarbeitung behauptet. Tatsächlich gewählte Portal-/Cookieoptionen und lokale
Vertrags-/Transferangaben sind Betriebsinformationen.

**DDDice:** Die standardmäßig ausgeschaltete Funktion wird von jedem Benutzer
selbst aktiviert und eingerichtet. Konto-Einstellungen speichern API-Schlüssel,
Raumkennung, ggf. Raumpasswort und Würfelset. Bei vollständiger Aktivierung kann
bereits der Seitenstart eine Verbindung aufbauen; Einstellungen können externe
Würfelsets abfragen. Direkte Browserverbindungen übertragen Verbindungsdaten,
Authentifizierung und Raumdaten, Würfe zusätzlich Würfelwerte, Set und
Ergebnislabel. Die eigene Anwendung erzeugt die Basis-Zufallswerte.
Die Beschreibung ist ein allgemeiner Textbaustein, keine Betreiberkonfiguration.
Es gibt dafür kein Legal-Umgebungsfeld und keine Abfrage von Benutzerschlüsseln
für die Rechtstexte. Externe Daten-/Löschregeln sind nicht durch den Anwendungscode
garantiert; Ausschalten löscht gespeicherte Zugangsdaten nicht automatisch.

Rollen getrennt behandeln: Der Betreiber verantwortet die gespeicherten
Anbindungseinstellungen und die durch die Integration ausgelöste Übermittlung.
DDDice verarbeitet das vom Benutzer selbst eingerichtete Dienstkonto und die
Nutzung seines Dienstes für eigene Zwecke. Aus der freiwilligen Aktivierung
folgen weder ein Auftragsverarbeitungsvertrag noch automatisch eine wirksame
Einwilligung in eine Drittlandübermittlung. Der direkte Browserzugriff entbindet
den Betreiber nicht von der Prüfung seiner veranlassten Übermittlungen.
Die Anbieterinformation nennt die USA, verweist aber weiterhin auf Privacy
Shield. Sie belegt damit keine aktuelle Garantie nach Kapitel V DSGVO.
Vor Freigabe einen tatsächlich anwendbaren Übermittlungsmechanismus mit Beleg
prüfen; keine Standardvertragsklauseln, Zertifizierung oder Ausnahme nach
Art. 49 DSGVO aus der bloßen Aktivierung ableiten. Dieser Nachweis ist offen;
der öffentliche Text behauptet keine bestehende Garantie.

**Weitere Betriebsdienste:** Ein administrativer Benachrichtigungsdienst ist
nicht allein deshalb eine Übermittlung von Benutzer-/Charakterdaten. Maßgeblich
sind der tatsächlich verwendete Payload und die Empfänger. Zusätzliche
installationsabhängige Dienste werden ausschließlich lokal beschrieben.

**Fonts:** Cinzel, Cormorant Garamond, Noto Serif und Noto Serif JP werden lokal
ausgeliefert. Herkunft, unveränderte Dateien, Hashes und vollständige OFL-Texte
stehen in [der Fontdokumentation](../static/fonts/README.md). Quellen-/Lizenzdaten
von Softwareassets sind allgemeine Projektdaten, keine Betreiberinformationen.

## Prüfung der separat implementierten Kontobildlöschung

Die vorhandene Kontolöschung sammelt die Bilddateien von Charakteren,
Charaktergegenständen und deren Offenlegungen, Charakterkreaturen sowie den
kontobezogenen göttlichen Entitäten, Druidenkulten und Schamanenpatronen.
Die Datenbanklöschung und das Entfernen der Dateien sind getrennte Schritte:
Storage-Löschungen werden erst nach erfolgreichem Transaktionsabschluss
ausgeführt. Rollback und blockierte Kontolöschung erhalten die Dateien.
Weitere Datenbankreferenzen verhindern das Entfernen der zum gelöschten Konto
gehörenden Bilddateien nicht. Allgemeine Katalogbilder werden nicht als private
Kontouploads entfernt.

`AccountImageDeletionTests` prüft Speicherlöschung, direkte Kontolöschung,
Gegenstands-/Offenlegungsbilder, Rollback, blockierte Löschung und das Verhalten
bei weiteren Dateireferenzen. Ein zusätzlicher Test mit `FileSystemStorage` prüft das
tatsächliche Entfernen einer Datei vom Dateisystem und den Erhalt eines
anderen Benutzerbilds samt dessen Datenbankeintrag. Es werden ausschließlich
Testdaten und temporäre Dateien verwendet. Das ist kein Nachweis eines
produktiven Storage-Backends oder einer Backup-Löschung. Fehler des jeweiligen
Speicherdienstes und bereits früher verwaiste Dateien bleiben Betriebsaufgabe.
Die Löschlogik wurde für diese Legal-Korrektur nicht verändert.

## Konkrete Prüfung der Endgerätespeicher

Die folgende Einordnung betrifft den geprüften Anwendungscode. Sie belegt keine
zusätzlich beim Betreiber oder in Anbieterportalen aktivierten Verfahren.
`localStorage` besitzt hier keine automatische Löschfrist; `sessionStorage`
gilt für die Tab-Sitzung, gegebenenfalls einschließlich Browserwiederherstellung.
Die Zugriffshilfen fangen Speicherfehler ab: Eine funktionierende Oberfläche
ohne dauerhafte Wiederherstellung ist bei vielen Funktionen ausdrücklich vorgesehen.

| Zugriff / Quelltext | Daten und Auslöser | Einordnung / Handlungsbedarf |
| --- | --- | --- |
| Django-Sitzungscookie | Sitzungskennung für Anmeldung, Sicherheitsprüfungen und angeforderte sitzungsgebundene Funktionen; durch Middleware gelesen/gesetzt | Für diese Funktionen erforderlich, § 25 Abs. 2 Nr. 2 TDDDG. Name, Laufzeit und Browser-Ende-Regel kommen aus den tatsächlichen Einstellungen. |
| Django-CSRF-Cookie oder Sitzungswert | Schutz von Formularen und Änderungsanfragen; JavaScript liest den Cookie-Wert für den Anfrageheader | Erforderlicher Schutz der angeforderten Funktion. Bei `CSRF_USE_SESSIONS` kein zusätzlicher CSRF-Cookie. Keine Reichweitenmessung. |
| `window_manager.js`, `utils.js` | LocalStorage: Position, Größe und Öffnungszustand von Fenstern; Lesen beim Initialisieren, Schreiben beim Öffnen, Schließen oder Verschieben | Dauerhafte Komfortwiederherstellung; nicht pauschal für die aktuelle Bedienung erforderlich. Vor persistenter Wiederherstellung Einwilligung oder konkret belegte Ausnahme nötig. |
| `utils.js: initPersistentDetails`, `shop_menu.js`, `schools_panel.js` | LocalStorage: offene Bereiche, Ansichts-/Schulauswahl; Wiederherstellen beim Initialisieren, Speichern bei Bedienung | Gleicher Handlungsbedarf für dauerhafte Komforteinstellungen. Ein Klick zum Aufklappen ist nicht automatisch Einwilligung in Speicherung über Besuche hinweg. |
| `card_hand.js`, `tooltip.js` | LocalStorage: abgelegte Karten, Positionen und Ziel der geöffneten Informationskarte; automatisches Wiederherstellen und Speichern bei Bedienung | Komfortzustände; aktuelle Kartenansicht benötigt diese dauerhafte Wiederherstellung nicht. Vorherige Einwilligung bzw. belegte Ausnahme fehlt. |
| `battle_calculator.js` | LocalStorage: gewählte Fertigkeit/Waffe und Berechnungseingaben; Lesen beim Initialisieren, Schreiben bei Änderungen | Eingaben sind für die aktuelle Berechnung nötig, ihre dauerhafte Speicherung nicht. Persistenz gesondert freigeben oder auf flüchtigen Zustand beschränken. |
| `quickslot_modifiers.js` | LocalStorage: manuelle Modifikatoren, Bezeichnungen und aufgeklappter Zustand; Lesen beim Initialisieren, Speichern bei Bearbeitung | Aktuell ausdrücklich eingegebene Modifikatoren von der nicht gesondert angeforderten dauerhaften Wiederherstellung unterscheiden. Für letztere fehlt eine vorherige Abfrage. |
| `quickslot_history.js` | LocalStorage: letzte zehn Würfe mit Zeit, Bezeichnung, Ergebnis und Modifikatoren; Lesen beim Initialisieren, automatisches Schreiben nach einem Wurf | Konkrete Lücke: Dauerhafte Wurfhistorie ist nicht für die Ausführung eines Wurfs nötig. Das Öffnen des Historienfensters erfolgt unabhängig von der Speicherung. Keine vorherige Einwilligung. |
| `damage_panel.js`, `_damage_panel.html` | LocalStorage: gewählte Schadensart; SessionStorage: vorherige Schadenswerte zur Animation; Lesen schon bei Anzeige/Initialisierung, Schreiben bei Aktualisierung | Persistente Auswahl ist Komfort; vorheriger Animationsstand ist für Schadensverarbeitung nicht erforderlich. Auch SessionStorage ist nicht allein wegen kurzer Laufzeit ausgenommen. |
| `tabs.js`, Vorabskript in `charsheet.html` | SessionStorage: aktiver Tab pro Pfad/Tabgruppe; Lesen vor bzw. bei Initialisierung, Schreiben beim Wechsel | Wiederherstellung der Ansicht; aktuelle Tabwahl funktioniert ohne Speicher. Keine generelle Erforderlichkeit nur wegen Tab-Laufzeit. |
| `spell_panel.js` | SessionStorage: Suchbegriff, Schulfilter, offene Gruppen; Lesen bei Initialisierung, Schreiben bei Bedienung | Für die laufende Suche sind Eingaben nötig; persistente Wiederherstellung bei Neuladen ist gesonderter Komfort ohne vorherige Abfrage. |
| `game_master_screen.js` | SessionStorage: ausgewählte Kreatur und Wiederöffnen des Auswahlfensters nach Navigation; Schreiben bei Auswahl/Navigation, Lesen bei Rückkehr | Auf die gewünschte Auswahlfolge begrenzt; Erforderlichkeit des konkreten Wiederherstellungsschritts belegen, nicht pauschal alle Anzeigepräferenzen ausnehmen. Funktion besitzt Fallback ohne Speicher. |
| `quickslots.js` | LocalStorage: altes Schnellslotlayout wird beim Start gelesen, gegebenenfalls zum Server übernommen und danach entfernt; neue Layouts liegen im Konto | Automatische Altbestandsmigration ist ein eigener Zugriff, keine laufende lokale Layoutspeicherung. Ausdrücklichen Übernahmewunsch bzw. Ausnahme prüfen; serverseitiges Speichern allein unterliegt nicht § 25. |
| `charsheet_diary.js` | LocalStorage: ältere Tagebucheinträge und Seitenposition; bei geladenem leerem Server-Tagebuch automatische Übernahme, danach Entfernen der Altbestände | Übernahme übermittelt Inhalte zum Server. Keine Behauptung ausschließlich lokaler Verarbeitung; ausdrückliche Übernahme oder tragfähige Ausnahme vor automatischem Lesen/Import klären. |
| `charsheet_tooltips.js` (noch in der Charaktererstellung eingebunden) | DOM-abhängige Legacy-Zugriffe auf Ruf, Tagebuch/Seite, Fensterpositionen und offene Fenster; Initialisierung und Bedienung | Nicht jede enthaltene Funktion wird ohne passendes DOM ausgeführt. Soweit aktiv, gelten dieselben Anforderungen an freiwillige dauerhafte Zustände; nicht wegen neuer Module übersehen. |
| DDDice-SDK, `vendor/dddice-latest.web.js` / `.mjs` | Erst bei Laden der optionalen Software: Debug-Einstellung `debug`; Verbindungsbibliothek verwendet `pusherTransportTLS`/`pusherTransportNonTLS` mit Zeitpunkt, Transport, Latenz und Cache-Zähler | Verbindungsfunktion ist freiwillig angefordert. Diagnosepersistenz ist dadurch nicht automatisch erforderlich; Notwendigkeit des Transportcaches und Diagnosezugriffe gesondert bewerten. Enthaltene generische Cookie-Helfer beweisen allein keinen tatsächlich gesetzten Cookie. |
| Optionales Turnstile und zusätzliche Betreiberinfrastruktur | Zusätzliche Portaloptionen, etwa Pre-Clearance, sind nicht aus dem Widget-Code zuverlässig feststellbar | Tatsächlich aktivierte Cookies und Speicherzugriffe beim Betreiber prüfen und lokal beschreiben; ausgeschaltete Funktion nicht als aktiv angeben. |

**Ergebnis und konkreter Handlungsbedarf:** Es gibt in den geprüften eigenen
Speicherhelfern und Initialisierern keine vorgeschaltete Einwilligungsprüfung
und keinen zugehörigen Widerrufsmechanismus. Insbesondere automatische
Wurfhistorie, dauerhafte Anzeigepräferenzen und gespeicherte Animationsstände
können nicht allein durch den Wunsch zu würfeln oder Schaden anzuzeigen als
unbedingt erforderlich behandelt werden. Für diese Zugriffe ist vor dem Lesen
und Schreiben eine wirksame Einwilligung erforderlich, sofern keine eng
funktionsbezogene Ausnahme belegt wird. Bis zur Umsetzung betroffene Persistenz
gezielt aussetzen oder durch rein flüchtige Zustände ersetzen; Importfunktionen
gesondert an einen ausdrücklichen Übernahmewunsch knüpfen. Ein pauschales
„Weiternutzen bedeutet Zustimmung“ oder ein Hinweis auf Browserlöschung genügt
nicht. Diese redaktionelle Korrektur baut auftragsgemäß kein Consent-System ein
und behebt die dokumentierte technische Lücke nicht. Die öffentliche Erklärung
beschreibt die derzeit automatische Speicherung ohne eine vorhandene Einwilligung
zu behaupten. Diese Lücke ist vor einer entsprechenden Freigabe zu bearbeiten.

Die Bewertung folgt der engen Ausnahme in
[§ 25 TDDDG](https://www.gesetze-im-internet.de/ttdsg/__25.html);
eine mögliche DSGVO-Rechtsgrundlage ersetzt diese Prüfung nicht.

## Mailtracking: Codebefund und notwendiger Betreibernachweis

`email_verification.py`, die Passwort-Reset-Mailvorlagen und `email_base.html`
fügen selbst keinen individuellen Öffnungspixel und keine Klickumleitung ein.
Die Links werden direkt erzeugt. Das gemeinsame Logo wird vom eigenen Server
geladen; dabei können Verbindungsprotokolle entstehen, auch über Bildproxys.
Ein eigenes individuelles Analyseverfahren ist im geprüften Versandpfad nicht
implementiert. Das beweist keine Trackingfreiheit des SMTP-Anbieters.

Brevo beschreibt für transaktionale E-Mails empfängerbezogenes Öffnungs- und
Klicktracking als Standardmöglichkeit. Die dort angebotene Anonymisierung
schaltet die Messung nicht ab. Sie lässt aggregierte Messwerte bestehen.
Siehe die [offizielle Beschreibung](https://help.brevo.com/hc/en-us/articles/11643306229906-Can-I-anonymize-the-tracking-of-opens-and-clicks-for-my-emails).
Dies ist eine Anbieterfunktion, kein Nachweis für irgendeine Installation.

Öffnungs- und Klickauswertung ist vom notwendigen Versand und der Zustellung
einer Kontomail getrennt zu bewerten. Die dafür genannte Rechtsgrundlage nach
Art. 6 Abs. 1 lit. b DSGVO rechtfertigt nicht automatisch zusätzliche
Nutzungsanalysen. Vor deren Freigabe sind der tatsächliche Analysezweck, eine
eigenständige DSGVO-Rechtsgrundlage und zusätzlich die Anforderungen an
Endgerätezugriffe nach § 25 TDDDG nachzuweisen. Soweit eine vorherige
Einwilligung erforderlich ist, müssen deren Einholung, Nachweis, technische
Durchsetzung vor dem Tracking und Widerruf tatsächlich eingerichtet sein.
Eine Registrierung oder Anforderung einer Kontomail ersetzt diese Einwilligung
nicht. Ohne tragfähigen Nachweis darf eine zusätzliche Auswertung nicht auf
die Rechtsgrundlage des Mailversands gestützt werden; erforderlichenfalls ist
sie beim Anbieter zu deaktivieren. Ein Textfeld ersetzt diese Maßnahmen nicht.

Brevo erläutert inzwischen
[gesonderte Einwilligungsoptionen für Öffnungs- und Klicktracking](https://help.brevo.com/hc/en-us/articles/37114679474706-About-email-tracking-pixels-and-the-CNIL-recommendation-in-Brevo).
Die dort behandelte CNIL-Empfehlung betrifft ihren jeweiligen französischen
Anwendungsbereich; daraus weder eine pauschale Ausnahme für deutsche
Transaktionsmails noch eine nachgewiesene Einwilligung dieser Installation
ableiten. Die konkrete rechtliche Bewertung bleibt ein offener Freigabepunkt.

Vor dem Ausfüllen von `LEGAL_EMAIL_TRACKING` intern nachweisen:

1. Tatsächliche Transaktionsmail-Einstellungen im Anbieterportal prüfen:
   Öffnungspixel, Klickumleitungen, Anonymisierung, ggf. kontaktbezogene
   Trackingoptionen und weitere aktivierte Auswertungen oder Ereignisempfänger.
   Newsletter-/Marketing-Einstellungen ersetzen diese Prüfung nicht.
2. Bei einer autorisierten Testmail den empfangenen MIME-/HTML-Quelltext mit
   der Vorlage vergleichen: zusätzliche Bilder, individuelle Parameter,
   umgeschriebene Links. Erst Öffnen/Klicken und die zugehörigen Ereignisse
   im Anbieterportal gemeinsam prüfen; ein nicht sichtbarer Pixel allein
   beweist keine fehlende Auswertung.
3. Ergebnis und Prüftermin **lokal** dokumentieren. Nur belegte Aussagen zu
   tatsächlich aktiven Messungen, Daten, Zweck, Grundlage und Wahlmöglichkeiten
   veröffentlichen. Unbekannte Einstellungen nicht als deaktiviert bezeichnen.
   Bis zur Klärung Feld leer lassen; der vorhandene Pflichtfeldcheck meldet
   den fehlenden Nachweis. Das ist ein offener Freigabepunkt, keine Bestätigung
   einer vollständigen Datenschutzerklärung.
4. Getrennt davon die tatsächlich bestätigten Aufbewahrungsregeln für
   Transaktionsprotokolle und Mailvorschauen in `LEGAL_EMAIL_RETENTION`
   unverändert erhalten und nicht nochmals im Trackingtext wiederholen.
   Aus ihnen folgt nichts über Öffnungs-/Klicktracking.

Die Prüfung hat keinen Zugriff auf Anbieterportale oder produktive Mailquellen
hergestellt und keine Testnachricht versendet. Es wird deshalb kein konkreter
Trackingstatus einer Installation behauptet.

## Rechtliche Primärquellen und Prüfgrenzen

- [DSGVO](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX%3A32016R0679):
  Zweck/Rechtsgrundlage, Transparenz und direkte/indirekte Erhebung, Rechte,
  Auftragsverarbeitung und internationale Übermittlungen sind für den tatsächlichen
  Betrieb zu prüfen. Die technischen Löschhindernisse ersetzen keine Art.-17-Prüfung.
- [§ 25 TDDDG](https://www.gesetze-im-internet.de/ttdsg/__25.html):
  Endgerätezugriffe gesondert prüfen; LocalStorage oder „Komfort“ ist keine
  pauschale Ausnahme vom Einwilligungserfordernis.
- [§ 5 DDG](https://www.gesetze-im-internet.de/ddg/__5.html) und
  [§ 18 MStV](https://www.gesetze-bayern.de/Content/Document/MStV-18):
  Anbieterpflichten nach tatsächlichem Angebot bestimmen; kein automatischer
  redaktioneller Verantwortlicher allein wegen des Betriebs der Charakterverwaltung.
- [§ 327 BGB](https://www.gesetze-im-internet.de/bgb/__327.html):
  Vertrags- und Verbrauchereinordnung anhand des tatsächlichen Angebots prüfen;
  Nutzungsbedingungen bleiben bis zur Freigabe ein gesonderter Entwurf.
- [Turnstile-Datenschutzzusatz](https://www.cloudflare.com/turnstile-privacy-policy/)
  und [Clearance-Dokumentation](https://developers.cloudflare.com/cloudflare-challenges/concepts/clearance/):
  allgemeines Dienstverhalten, kein Nachweis einer konkreten Portal-/Vertragskonfiguration.
- [DDDice-Datenschutzerklärung](https://dddice.com/privacy):
  Angaben des festen optionalen Dienstes; keine automatisch zugesicherte
  Rechtsgrundlage oder Löschfrist einer bestimmten Nutzung.

Systemchecks prüfen Struktur, Vollständigkeit und Plausibilität. Sie beweisen
keine korrekte Anschrift, abgeschlossenen Vertrag, laufenden Löschjob,
rechtmäßige internationale Übermittlung oder vollständige Rechtskonformität.
Die erforderlichen lokalen Belege sind in [der Einrichtungsanleitung](legal.md)
den jeweiligen Variablen zugeordnet.
