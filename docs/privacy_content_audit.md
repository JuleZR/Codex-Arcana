# Inhaltliche Prüfung der DSGVO-Auskunft

Stand: 25.10.2026. Untersucht wurden die Anwendung und die lokal geladenen,
validierten Betreiberangaben. Es wurden keine Produktivkonten exportiert,
Providerprotokolle abgerufen oder Betriebsfristen auf einem Server verifiziert.
Browser- und Sichtprüfungen sind nicht Bestandteil dieser Prüfung.

## Maßstab und Aussagegrenze

Art. 15 umfasst die Verarbeitungsbestätigung, die personenbezogenen Daten selbst
und die Angaben aus Abs. 1 und 2. Eine allgemeine Datenschutzerklärung ersetzt
keine auf die Person bezogene Datenkopie. Die EDSA-Leitlinien verlangen auch die
Suche in weiteren verfügbaren Beständen sowie verständliche Erläuterungen und
eine konkrete Abwägung gemischter Inhalte. Ein Bezug zu anderen Menschen erlaubt
keinen pauschalen Ausschluss aller Nachrichten oder Beiträge.

Quellen: [DSGVO, insbesondere Art. 12, 15 und 20](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX%3A32016R0679),
[EDSA-Leitlinien 01/2022, Version 2.1](https://www.edpb.europa.eu/system/files/2023-04/edpb_guidelines_202201_data_subject_rights_access_v2_en.pdf),
insbesondere Abschnitte 2.3, 4, 5 und 6.2.

Bekannte tatsächliche Empfänger sind grundsätzlich konkret zu benennen; bloße
Kategorien dürfen nicht nach Belieben an ihre Stelle treten. Besonderheiten
und begründete Ausnahmen müssen geprüft werden.
[EuGH C-154/21, insbesondere Randnummer 51](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX%3A62021CJ0154).

Die Software prüft Vollständigkeit der Prüfstruktur, Zuordnungen und die Bindung
der Freigabe an einen konkreten Datenstand. Sie kann die Wahrheit eingegebener
Betreibererklärungen, eine Abwägung der Rechte Dritter oder die Vollständigkeit
nicht angebundener Systeme nicht rechtlich bestätigen. Eine abschließende
DSGVO-Konformität wird nicht behauptet.

Der Export bildet den dokumentierten Sammlungsstand ab. Eine bereits früher
eingegangene Anfrage oder kurzlebige Daten werden nicht rückwirkend durch die
Exportfunktion gesichert. Solche Bestände rechtzeitig ermitteln und ihren
Zeitbezug prüfen. Für gelöschte Konten ohne verbleibenden Kontodatensatz kann
diese kontobasierte Maske keine vollständige Auskunft erzeugen; noch verfügbare
personenbezogene Bestände müssen dann außerhalb der automatischen Kontosammlung
geprüft und beantwortet werden.

## Tatsächliche Datenkategorien und Zuordnung

Die interne JSON-Prüfgrundlage enthält `data.category_mapping`: für jedes
registrierte `charsheet`-Modell den Modellnamen, die Bezeichnung, den geprüften
Zuordnungspfad bzw. die gemeinsame Beziehung, den Erfassungsumfang und die
technischen Löschbeziehungen. Für personenbezogen zugeordnete Modellfamilien
kommen der aus dem Code ersichtliche Verwendungszweck und die Herkunft hinzu.
Konkrete Fristen und tatsächliche Offenlegungen werden mit den geprüften
Betriebsangaben abgeglichen; `CASCADE` oder `PROTECT` sind keine Löschfrist.

Das Inventar wird aus dem aktuellen Schema erzeugt, statt eine statische Liste
bei Modelländerungen unbemerkt veralten zu lassen. Zum Prüfzeitpunkt umfasst es
186 Anwendungsmodelle. Die zusätzlich ausgewerteten Django-/Axes-Kategorien
stehen unter `data.categories`; auch leere Kategorien bleiben dort sichtbar.
`auth.EffectivePermission` ist dabei eine abgeleitete Ansicht der tatsächlich
zugewiesenen Rechte und des Superuser-Umfangs, kein zusätzliches Datenbankmodell.

| Bereich | Daten und Zuordnung | Herkunft und Verwendung | Speicherung, Dritte und Grenzen |
| --- | --- | --- | --- |
| Konto | Benutzername, E-Mail, Namen, Erstellung, letzter Login, Aktiv-/Adminstatus; unveränderliche Konto-ID | Eingaben, Kontoverwaltung und Systemereignisse; Betrieb und Zugang zum Konto | Kontolöschung und tatsächliche Betriebsfristen prüfen; keine Passwort-Hashes |
| Berechtigungen | Eigene Django-Gruppen, direkte und gruppenvermittelte Berechtigungszuweisungen; Superuser-Umfang | Administrative Zuweisungen; Steuerung des Zugriffs | Nur zugewiesene Rechte, kein vollständiger Berechtigungskatalog und keine Mitglieder anderer Konten; der separate Kontostatus bestimmt den möglichen Zugang |
| Einstellungen | `UserSettings`, Kalenderanordnung, persönliche Schnellzugriffe einschließlich bereinigter `slots` | Persönliche Auswahl und gespeicherter Darstellungszustand | Kontobezogene Löschbeziehungen im Inventar; API-Schlüssel, Raum-Passwörter, Verifizierungstoken und TOTP-Geheimnisse ausgeschlossen |
| Kontosicherheit | Sicherheitsereignisse mit Zeitpunkt, IP, Gerät, Ereignisart sowie zugelassenen Zusatzangaben `label` und `session_count`; Passkey-Metadaten und Verbrauchs-/Erstellungszeiten von Recovery-Codes | Browser, Anmeldung und Sicherheitsaktionen; Zugangsschutz und Nachvollziehbarkeit | Konfigurierte Frist lokal 365 Tage; Bereinigung wird im Code bei neuen Sicherheitsereignissen ausgelöst und ist zusätzlich als Command vorhanden. Ein unbedingter täglicher Löschlauf ist daraus nicht nachgewiesen |
| Zugriffsbegrenzungen | Zähler, Fensterbeginn und Sperrende rekonstruierbarer kontogebundener `AuthenticationThrottle`-Einträge | Sicherheitsaktionen mit Konto-ID bzw. Reset-UID; Begrenzung von Zugriffsversuchen | Kein HMAC-Schlüssel im Export. Gemeinsam genutzte IP-Buckets werden nicht pauschal einem Konto zugeschrieben. Die vorhandenen Zeitfenster beweisen keine physische Löschfrist |
| Weitere Anmeldung | Axes-Daten zum aktuellen Benutzernamen: IP, Browser, Zeit und Fehler-/Sperrstatus | Zugriffsversuche; Missbrauchsschutz | Historische bzw. wiedervergebene Namen und fremdveranlasste Versuche ausdrücklich prüfen; keine automatische Suche über erfundene frühere Namen |
| Sitzungen | Ablaufdatum, Anmeldestatus, zugeordnete temporäre Spielwerte und Beginn einer vorgemerkten Anmeldung | Eigene Browsersitzung und gespeicherte Bedienzustände | Auch noch gespeicherte abgelaufene Sitzungen werden berücksichtigt. Authentifizierungs- und Challenge-Geheimnisse fehlen bewusst. Unbekannte Zustände und Bezüge zu fremden Charakteren erzeugen Prüfkandidaten |
| Charaktere | Eigene und archivierte Charaktere, individuelle Beschreibungen, Eigenschaften, Fertigkeiten, Sprachen, Entscheidungen, Lern- und Entwicklungsstände | Eingaben, Auswahlen und gespeicherte Spielzustände; persönliche Spielverwaltung | Fiktionale Eigenschaften sind keine Feststellungen über reale Gesundheit, Religion oder andere Eigenschaften der Person. Freitexte können gleichwohl Dritte oder reale Informationen enthalten |
| Inventar und Kreaturen | Eigene Gegenstände, Mengen, Ausrüstung, individuelle Namen/Beschreibungen, Runen, Wirkungen, Offenlegungen, Kreaturen und Unterdatensätze | Persönliche Spielstände und Systemereignisse | Früheres/fremdes Eigentum und Gruppenbezüge werden gesondert behandelt. Dateien nur anhand sicherer lokaler Zuordnung |
| Chronik und Entwürfe | Tagebuchtexte, Reihenfolge, Datum, Kalenderzustände, Erstellungsentwürfe und Vorlagen | Eingaben und Erstellungsentscheidungen | Persönliche JSON-Felder bleiben erhalten; Geheimnisschlüssel/-muster werden geschützt und die Einschränkung vermerkt |
| Gruppen | Eigene Rollen, Mitgliedschaften und Einladungen einschließlich historischer Zustände; eigene Gruppenkreaturen und deren Vampir-Unterdatensätze | Eigene Beteiligung, andere Beteiligte und Gruppenabläufe | Identitäten, Namen und gemeinsame Texte nicht pauschal veröffentlichen. Ein Gruppenbezug allein beweist keine alleinige Dateneigentümerschaft |
| Gemeinsame Beiträge | Gruppennotizen sowie Titel, Spalten und Zellinhalte zugeordneter Gruppentabellen als interne Prüfkandidaten | Mitteilungen und gemeinsame Inhalte; personenbezogene Auszüge nach Prüfung | Auch fremd erstellte Tabellen in zugeordneten Gruppen werden zur Prüfung gefunden. Freigegebene Auszüge werden als persönliche Inhalte ausgegeben; der übrige Tabelleninhalt wird nicht automatisch kopiert |
| Übertragungen | Sender-/Empfängerbezüge, Akteure, Mengen, Zeiten, Zustände, Rechte und Eigentumsereignisse | Beteiligte und Übertragungsvorgänge | Gemischte Nachrichten, Snapshots und fremde Zuordnungen benötigen eine konkrete Entscheidung; eingegangene persönliche Inhalte sind grundsätzlich prüfbar, nicht pauschal ausgeschlossen |
| Änderungshistorie | Eigene Admin-Aktivitäten und Admin-Einträge über das Konto bzw. seine eindeutig eigenen Datensätze, auch bei anderem Bearbeiter | Administrative Änderungen | Objektbezeichnungen, Bearbeitungstexte, Akteure und nicht eindeutige Objektbezüge werden geprüft; keine Offenlegung fremder Änderungen allein aufgrund gleicher Modellklasse |
| Weitere Bestände | Verfügbare Server-/Proxy-/System-/DB-Protokolle, E-Mail- und Versanddaten, Backups, Testkopien, externe Dienstbestände, freie Erwähnungen ohne Kontoschlüssel | Je nach tatsächlich vorhandener Installation | Keine erfundene automatische Anbindung. Recherche und Ergebnis sind vor Freigabe zu dokumentieren; relevante Datenkopien werden über `supplements` ergänzt |

`no_direct_account_assignment` im Inventar bedeutet **nicht** „sicher keine
personenbezogenen Daten“. Darunter fallen einerseits Regelwerks- und
Katalogmodelle wie Attribute, Völker, Fertigkeiten, Gegenstandstypen, Zauber,
Techniken, allgemeine Kreaturvorlagen und Kalenderdefinitionen. Andererseits
können freie Katalogbeschreibungen, Gruppenkataloge oder Ankündigungen reale
Personen erwähnen. Solche Erwähnungen und gelöste historische Zuordnungen müssen
im Rahmen der ergänzenden Suche geprüft werden.

Referenzierte allgemeine Katalogdaten werden nur mit notwendigen Kennungen und
Bezeichnungen aufgelöst. Eine gewählte Fertigkeit oder ein Volk ist damit
nachvollziehbar, ohne sämtliche Regeltexte und Stammdatensätze zu kopieren.
Private oder nicht verfügbare Katalogbezüge sowie generische Auswahlverknüpfungen
werden als offene Prüffälle sichtbar; sie verschwinden nicht stillschweigend.

## Externe Dienste: Befund und Einzelfallprüfung

Die folgenden Angaben trennen Codebefund und lokal gespeicherte
Betreibererklärung. Letztere sind kein unabhängiger Nachweis für den
Produktivbetrieb oder den Verlauf eines bestimmten Kontos.

| Dienst | Festgestellter Befund | Erforderliche konkrete Auskunft |
| --- | --- | --- |
| Hosting | Lokal wird Hetzner Online GmbH genannt. Anwendungs- und Datenbankbetrieb, Protokolle und Sicherungen werden in den Betreiberangaben beschrieben | Tatsächliche Verarbeitung des betroffenen Kontos, benannter Empfänger, Orte, Fristen und Backup-Ausnahmen anhand des Betriebs abgleichen |
| E-Mail | Lokal wird Brevo genannt. `email_verification.py` versendet Empfängeradresse und E-Mail-Inhalt mit zeitbegrenztem Bestätigungslink. Passwort-Reset läuft über Djangos Reset-Versand und eigene Templates | Tatsächliche Empfänger-/Versandinformationen, Nachrichten und Zustellmetadaten berücksichtigen. Provider erhält auch den Linkinhalt; echte Token werden im Auskunftsexport nicht offengelegt. Anbieterfristen, Tracking und Unterauftragnehmer gesondert verifizieren |
| Turnstile | Lokal derzeit deaktiviert. Bei Verwendung sendet `verify_turnstile()` die Prüfantwort und `remoteip` an den konfigurierten Prüf-Endpunkt; das Widget erzeugt zusätzlich Browserkontakte | Eine aktuelle Einstellung belegt keine historische Nichtnutzung. Tatsächlichen Zeitraum, betroffene Abläufe, Empfänger, Aufbewahrung und Drittlandgarantien prüfen; bei Nichtbetroffenheit keine Cloudflare-Verarbeitung behaupten |
| DDDICE | Die Browserintegration übermittelt bei Nutzung Würfelart/-werte, Design, Raum und Wurfbezeichnung an `dddice.com`; sie verwendet das dienstbezogene Zugangstoken und kann Raumverbindungen herstellen | Kontobezogene Nutzung einschließlich Einstellungs-/Designabfragen prüfen. Kein automatischer Empfängerstatus für sämtliche Benutzer. Anbieterbestände und Fristen sind nicht lokal nachgewiesen |
| Discord/Betriebsdienste | Die lokale Betreiberbeschreibung nennt einen Wartungs-Webhook mit Hostname, Zeiten, Neustartstatus, Dauer und Fehlercodes sowie Server-Quell-IP, ausdrücklich ohne Konto-, E-Mail- oder Charakterdaten. Ein entsprechender Sender wurde in den untersuchten Repo-Skripten und im Anwendungscode nicht gefunden | Diese Betreiberangabe extern überprüfen. Reine Wartungsmeldungen ohne Bezug zur betroffenen Person nicht als Empfang ihrer Kontodaten darstellen. Bei abweichendem Inhalt oder einem persönlichen Bezug des Infrastrukturdatums erneut prüfen |
| Weitere Dienste/Verarbeitungen | Kein vollständiger externer Datenflussnachweis aus dem Repo ableitbar | Vor Freigabe dokumentieren, ob die Person betroffen ist; tatsächliche weitere Empfänger und Daten ergänzen |

`turnstile_details`, `additional_processing` und `administrative_services`
werden nicht blind verworfen: Ihre validierten Inhalte bleiben in der internen
Prüfgrundlage als Recherchegrundlage erhalten. Relevante Sachangaben werden
über die geprüften Dienstabschnitte verständlich in die Benutzerkopie übernommen.
`reviewed_on` bleibt ein interner Bearbeitungsstand. Zugangsdaten und
Webhook-Adressen werden nicht aus Legal-Feldern veröffentlicht.

## Benutzerbericht und interne Prüfgrundlage

| Ausgabe | Beabsichtigter Inhalt |
| --- | --- |
| PDF | Bestätigung, Kontakt zum Verantwortlichen, personenbezogene Kategorien, geprüfte Verarbeitungsinformationen, konkret betroffene Dienste, eigene Daten, nachvollziehbare Ausnahmen und Dateihinweise |
| `data.json` | Maschinenlesbare Benutzerkopie mit denselben persönlichen Datensätzen und Ergänzungen; Feldbezeichnungen und minimale Verknüpfungsmetadaten erklären die Struktur |
| Standard-ZIP | `report.pdf`, `data.json` und optional geprüfte Anhänge |
| Interne JSON-Ausgabe | `audit.json`: bereinigte Datengrundlage, Feldverzeichnis, Modellinventar, Prüfkandidaten, Entscheidungen, fehlende Angaben und Freigabe-Hashes |
| Internes ZIP | Zusätzlich zu Benutzerkopien und gegebenenfalls geprüften Anhängen die ausschließlich administrativ zu verwendende `audit.json` |

Die interne Ausgabe ist ausdrücklich auszuwählen und heißt beim Download
„Prüfgrundlage“. Sie kann gemischte Inhalte weiterer Personen zur berechtigten
Prüfung enthalten und darf nicht als Benutzerkopie weitergegeben werden. Auch
sie enthält keine bekannten Authentifizierungsgeheimnisse oder tatsächlichen
Webhook-Zugangsdaten.

Öffentliche WebAuthn-Kennungen und öffentliche Registrierungsschlüssel werden
nicht pauschal zu Geheimnissen erklärt. Sie stehen als Base64-Prüfkandidaten
zur Verfügung und können nach konkreter Entscheidung unter verständlichen
Registrierungsfeldern in die Benutzerkopie aufgenommen werden. Private Schlüssel,
Passwörter, TOTP-, Recovery- und Sitzungsgeheimnisse sind dadurch nicht freigebbar.
Base64-Werte bleiben im Benutzer-JSON unverändert; das PDF dient ihrer lesbaren,
gegebenenfalls umbrochenen Darstellung.

Die PDF-Ausgabe verwendet deutsche Feld-/Kapitelbezeichnungen und löst
Verknüpfungen soweit möglich über eigene Einträge oder minimale Katalognamen
auf. Strukturierte persönliche Daten werden als gegliederte Inhalte statt als
ungefilterter JSON-Text gesetzt. Das Benutzer-JSON behält geeignete technische
Schlüssel für die maschinelle Nutzung und die zugehörigen Bezeichnungen; es
enthält keine interne Legal-Konfiguration, Prüfanweisungen, Prüfkandidaten oder
Freigabe-Hashes. Die systeminterne generische Content-Type-Kennung wird durch
die geprüfte Beschreibung der Auswahl ersetzt; sie bleibt intern nachvollziehbar.

Redaktionell Verantwortliche und Berufs-/Zulassungsaufsichten aus der bestehenden
Legal-Konfiguration werden **nicht** als datenschutzrechtlich Verantwortliche
oder Datenschutzaufsicht umetikettiert. Standardkontakt ist der Betreiber mit
Anschrift und E-Mail. Abweichende Zuständigkeiten bzw. eine konkrete
Datenschutzaufsicht sind im Prüf-JSON gesondert anzugeben.

## Freigabesperren und Prüf-JSON

Die vorhandenen Abschnitte `processing`, `redactions`, `portability` und
`approval` bleiben unterstützt. Hinzu kommen folgende Abschnitte:

* `controller`: geprüfte Felder `name`, `address`, `email`, optional
  `data_protection_officer` und `complaint_authority`.
* `coverage`: konkret dokumentierte Prüfung von `shared_content`,
  `external_records`, `historical_identifiers` und `personal_json`.
  Jeder Eintrag hat `checked: true` und ein aussagefähiges `statement`.
* `services`: Prüfung von `hosting`, `email`, `turnstile`, `dddice`,
  `administrative_services` und `additional_processing`.
* `resolutions`: Entscheidungen zu den tatsächlich vorhandenen Kandidaten-IDs.
* `supplements`: geprüfte personenbezogene Datenkopien aus weiteren Quellen.
* `file_decisions`: begründete Entscheidung für nicht beigefügte Dateikopien.

Ein verwendeter Dienst hat `status: "used"` und konkrete Angaben in `recipients`,
`data`, `purposes`, `retention` und `transfers`. `transfers` ist ein Objekt:
`applies` muss ausdrücklich `true` oder `false` sein; `details` beschreibt die
tatsächlichen Verhältnisse. Bei `true` sind zusätzlich `safeguards` für die
geprüften Garantien und `copy_source` für deren Kopie bzw. Bezugs-/Fundstelle
zwingend. Bei `false` sind nur `applies` und die nachvollziehbare Beschreibung
`details` vorgesehen. Der Benutzerbericht zeigt hierfür deutsche Bezeichnungen,
keine internen Prüfschlüssel.
`status: "not_used"` benötigt einen konkreten `reason` und bedeutet hier:
**keine Verarbeitung personenbezogener Daten dieser betroffenen Person durch
diesen Dienst festgestellt**. Es bedeutet nicht zwingend, dass der technische
Dienst global abgeschaltet ist. Nicht betroffene Dienste werden nicht als
Empfänger im Benutzerbericht ausgegeben.

Beispiel einer einzelnen Entscheidung, mit tatsächlicher Kandidaten-ID und
tatsächlich geprüftem Inhalt zu ersetzen:

```json
{
  "resolutions": {
    "charsheet.GameGroupInvitation:123:message": {
      "action": "include",
      "value": "Der geprüfte persönliche Teil der Einladung.",
      "reason": "Persönlicher Nachrichtenteil; fremde Angaben entfernt."
    }
  }
}
```

`include` erfordert den konkret freigegebenen `value` und einen Grund.
`withhold` oder `not_personal` erfordern ebenfalls einen konkreten Grund, aber
keinen Inhalt. Bekannte Sicherheitsgeheimnisse lassen sich damit nicht freigeben.
Veraltete oder nicht passende Entscheidungen brechen die Sammlung ab.
Bestehende `redactions` bleiben als Ersetzung erhalten; zur endgültigen Freigabe
ist die jeweilige Schwärzung zusätzlich als Einzelfallentscheidung zu begründen.

Eine Ergänzung hat folgende Struktur:

```json
{
  "supplements": [
    {
      "category": "Geprüfte personenbezogene Protokollauszüge",
      "source": "Konkret benannte und geprüfte Quelle",
      "purpose": "Tatsächlicher Verarbeitungszweck dieser Quelle",
      "retention": "Tatsächliche Speicherdauer oder konkrete Kriterien",
      "records": [{"Bezeichnung": "Geprüfter personenbezogener Wert"}]
    }
  ]
}
```

Diese Strukturbeispiele sind **keine** vollständigen oder freigegebenen
Betreiberangaben. Auch ein formal vollständiges Prüf-JSON ist kein Nachweis
für die materielle Richtigkeit seiner Inhalte.

Bei Art. 15 sperren fehlende Zwecke, Empfänger, Speicherdauer, Herkunft,
Drittland-/Garantieangaben oder Angaben zu Art.-22-Entscheidungen die Freigabe.
Die tatsächlichen Kategorien werden aus dem Datenbestand erzeugt;
Betroffenenrechte und Beschwerderecht sind Bestandteil der Benutzerkopie.
Die Rechtsgrundlagen können ergänzend angegeben werden; sie werden nicht als
zusätzliche zwingende Voraussetzung des Art. 15 Abs. 1 behandelt.

Ebenso sperren ungeprüfte Suchbereiche, Dienste, Einzelfallkandidaten und
fehlende Dateikopien ohne Zustellungs-/Ausnahmeentscheidung die Freigabe.
Die Vorschau zeigt diese Sperren unmittelbar an; die interne JSON-Ausgabe
enthält dieselbe Liste unter `missing_information`. Die finale Freigabe bleibt
an Konto, Datenstand, Ergänzungen, Entscheidungen und tatsächlich kopierte
Dateibytes gebunden. Platzhalter werden nicht als fertige Information ausgegeben.
Ohne Freigabe ist die Benutzerkopie deutlich als technischer Entwurf markiert.

Für fehlende Dateien kann `file_decisions["files/000001.png"]` beispielsweise
`action: "separate_delivery"` mit konkret beschriebenem geschütztem Zustellweg
enthalten. Alternativ sind `withhold` oder `not_personal` mit geprüftem Grund
möglich. Eine separate Zustellung wird damit dokumentiert, nicht technisch
als bereits ausgeführt nachgewiesen. Eine angeforderte Dateikopie darf nicht
allein durch eine formale Bestätigung ersetzt werden.

## Art. 15 und Art. 20

Eine Art.-15-Sammlung wird nicht durch eine eventuell ebenfalls vorhandene
Art.-20-Feldauswahl beschränkt. Für Art. 20 bleiben ausdrückliche Kategorie- und
Feldregeln mit `basis: "consent"` oder `"contract"` und
`provided_by_subject: true` erforderlich. Die Kriterien und die tatsächliche
Bereitstellung einschließlich einschlägiger beobachteter Daten sind materiell
zu prüfen; die Software leitet dies nicht aus dem bloßen Vorhandensein eines
Datensatzes ab. Gemischte und sicherheitskritische Daten bleiben geschützt.

Ein reiner PDF-Download ist für Art. 20 in Maske und Command gesperrt. JSON und
ZIP liefern die maschinenlesbare Kopie, das ZIP außerdem den korrekt bezeichneten
PDF-Begleitbericht. Die Art.-15-Verarbeitungsangaben werden nicht als zusätzliche
Art.-20-Freigabebedingung verlangt. Offene gemischte Zuordnungen und fehlende
Dateikopien müssen auch bei Art. 20 behandelt werden.

## Erhaltene Architektur und Nachweise

Die Erstellung läuft weiterhin außerhalb des synchronen Webrequests. Private
Jobverzeichnisse, dateibasierte PDF-/JSON-/ZIP-Ausgaben, begrenzte Layoutblöcke,
nachträglich eingefügtes Inhaltsverzeichnis und endgültige Verweise bleiben
erhalten. Neue interne Dateien sind ausdrücklich in der sicheren Bereinigung
berücksichtigt. Ablaufzeit, Datei-/Verzeichnisschutz, Superuser-/Eigentümerprüfung,
CSRF, `Referrer-Policy: same-origin`, Download-Close-Cleanup, unabhängiger Monitor
und periodischer Restebereiniger bleiben bestehen. Für einen vollständigen
Serverausfall ist weiterhin die in `privacy_requests.md` beschriebene
Timer-Einrichtung erforderlich.

Gezielte Tests:

```powershell
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_content charsheet.tests.test_privacy_export charsheet.tests.test_privacy_admin charsheet.tests.test_privacy_jobs --keepdb
```

`test_privacy_content` prüft Datenkopie statt Katalogdump, tatsächlich gespeicherte
Sicherheits-/Sitzungsangaben, sichere Drosselungszuordnung, eigene Berechtigungen,
Änderungen durch andere Administratoren, freigebbare persönliche Teile gemeinsamer
Nachrichten und Tabellen, eigene Gruppenkreatur-Unterdaten, generische
Auswahlverknüpfungen, ergänzbare externe Bestände, Prüf- und Dateisperren,
Empfängerangaben, den Verzicht auf redaktionelle Fehlzuordnungen, getrennte
JSON-Zwecke und die unterschiedliche Reichweite von Art. 15 und 20.

Die bestehenden Tests prüfen außerdem archivierte und nahezu leere Konten,
langlaufende Kapitel, lange Texte und JSON-Felder, Inhaltsverzeichnis,
Verweisziele, PDF-/JSON-/ZIP-Datenabdeckung, Anhänge, Hashbindung der internen
Freigabe, Superuser-/CSRF-Schutz, erfolgreiche und unterbrochene Downloads,
Schreibfehler, Fristablauf, echten Prozessabbruch und die vollständige Entfernung
zugehöriger temporärer Dateien. Zusätzliche Fälle sichern ein internes ZIP und
einen vollständigen großen Kontoexport mit 250 Tagebucheinträgen ab.

Diese synthetischen Tests belegen die geprüften technischen Verträge. Sie
beweisen weder die materielle Vollständigkeit beliebiger Produktivbestände noch
die Ausführung externer Aufbewahrungs-/Löschvorgaben. Datenbanksammlung und
Anwendungsmodelle bleiben lesend; Geschäftsdatensätze werden nicht verändert.

Der abschließende gezielte Lauf umfasste 80 erfolgreiche Tests mit `--keepdb`.
Das vollständige synthetische ZIP-Konto mit 250 Tagebucheinträgen wurde in
2,86 Sekunden erstellt; der separate große PDF-Fall benötigte 3,48 Sekunden.
Dort wurden 0,20 MiB Python-Speicherspitze und eine Prozessspeicherspitze von
241,48 MiB gemessen. Letztere umfasst den gesamten Django-Testprozess und native
MuPDF-Allokationen; die Prozessspitze stieg im Messabschnitt um 4,86 MiB.
Diese lokalen Windows-Messungen sind keine Last- oder Speicherzusage für
beliebige Produktivkonten. Flake8 und die Diff-Prüfung waren fehlerfrei.
