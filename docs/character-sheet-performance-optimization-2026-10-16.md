# Charakterbogen: umgesetzte Performanceoptimierungen

Stand: 16.10.2026. Vergleichsbasis: Git-Revision
`c8e1da7113328a00e9cd49e1ee7d135083eab2ac`.

## Ergebnis

Die nachgewiesenen wiederholten Datenbankzugriffe in Shop, Inventar,
Kreaturenberechnung und Schulklassifikation wurden gezielt reduziert.
In zehn lokalen Vergleichspaaren sinkt der Median für Kontextaufbau und
Rendering von **3,7979 auf 2,4759 Sekunden (34,8 %)**. Die mediane Queryanzahl
sinkt von **2.983 auf 1.612 (46,0 %)**.

Alle 20 HTML-Ausgaben sind nach Normalisierung der CSRF-Tokens identisch.
Die Dokumentgröße bleibt bei 3.661.398 UTF-8-Bytes. Der SHA-256 des
normalisierten HTML lautet für jeden Lauf:

`c4aead54551df19c287f9dca68d480c2f00c661b95c5cca176ca268677288336`

Das sind **Serverteilmessungen**, keine gemessenen Browserladezeiten,
Produktionswerte oder vollständigen HTTP-Antwortzeiten.

## Änderungen

### Shop und Inventar: `charsheet/sheet_context.py`

- Waffenprofile werden nach `id` geordnet vorab geladen. Die Kaufzeile nimmt
  das erste Profil aus dieser bereits geladenen Liste. Damit entfallen die
  467 nachgewiesenen zusätzlichen Einzelabfragen; die Wahl des niedrigsten
  Profil-IDs und das Verhalten ohne Profil bleiben erhalten.
- Artikelkarten, Kauf- und Verkaufszeilen reichen vorhandene Quality-Objekte
  an den bestehenden Formatierungshelfer weiter. Damit entfällt das erneute
  Auflösen derselben Qualitätscodes; Materialüberschreibung und Preisformeln
  verwenden weiterhin die bestehenden ItemEngine-Funktionen.
- Inventar- und Verkaufsquerysets laden die erforderlichen Qualitäts- und
  Materialrelationen gemeinsam. Das Inventar lädt außerdem den Itemtyp mit.
- Die Lernliste lädt Druiden-/Schamanenrelationen für ihre Katalogschulen
  gesammelt. Ein Stackprofil nach dem ersten Umsetzungsschritt hatte dort
  noch 187 einzelne Existenzprüfungen nachgewiesen.

### Kreaturen: `charsheet/engine/creature_engine.py`

Die Basisattribute werden einmal pro CreatureEngine in einer Map gelesen,
entsprechend dem bestehenden Cached-Property-Muster. Die Reihenfolge der
Override-, Basiswert-, Effekt- und Trainingsberechnung bleibt erhalten.
Auch fehlende Werte und die bisherige Auswahl des ersten Attributdatensatzes
bleiben erhalten. Es gibt keinen Cache zwischen Requests oder Engines.

### Schulklassifikation: `charsheet/religion_rules.py`

Die aktiven Schulen laden ihre Druiden-/Schamanenrelationen gemeinsam;
die bisherigen Klassifikationsfunktionen verwenden danach den normalen
Django-Prefetchcache. Ihre fachlichen Bedingungen bleiben erhalten.
Erneute Aufrufe laden den aktuellen Datenstand.

Es wurden keine Templates, Stylesheets, JavaScriptdateien, URLs, Modelle,
Migrationen oder Berechtigungsregeln geändert. Alle Fenster einschließlich
des Shops werden weiterhin beim vollständigen Seitenaufruf gerendert.
AJAX-/Partialverträge und Synchronisierungen bleiben erhalten. Die größere
Umstellung auf nachgeladenes Shop-HTML wurde nicht eingeführt, weil deren
unveränderte unmittelbare Bedienbarkeit hier nicht nachgewiesen werden kann.

## Messverfahren und Grenzen

- PostgreSQL erzwingt `SET TRANSACTION READ ONLY` innerhalb von
  `transaction.atomic()`. Keine Anwendungsdaten wurden geändert.
- Lokaler Charakter 75, 14 Inventarzeilen, zwei aktive Kreaturenkarten;
  559 Katalogitems ohne Kataloggruppe, davon 467 Kaufzeilen, acht Qualitäten.
- Derselbe Django-Prozess, `DEBUG=True`, jeweils frischer Character und
  RequestFactory-Request mit bereits geladenem Benutzer und Session im
  Speicher. Kein Middleware-, HTTP-, Netzwerk- oder Browserprofil.
- Bestehenden `_build_sheet_context_for_request(..., read_only=True)`
  ausführen, anschließend für die diagnostische Ausgabe lediglich
  `context['read_only'] = False` setzen und `charsheet.html` rendern.
  Dadurch werden auch die Besitzerfenster gemessen, ohne den schreibenden
  Besitzerpfad auszuführen. Diese Kombination ist kein vollständiger
  Besitzer- oder SL-Request.
- Die ursprünglichen sieben betroffenen Funktionen wurden für den
  Vorherlauf aus `git show HEAD:<datei>` per AST geladen und ausschließlich
  im Messprozess temporär eingesetzt. Quelldateien wurden dafür nicht
  zurückgesetzt. Der Nachherlauf nutzt die aktuellen Funktionen.
- Zehn Vergleichspaare, Reihenfolge vor/nach pro Paar abwechselnd.
  Betriebssystem-/Datenbankcaches wurden nicht geleert; keine Kaltstart-
  oder p95-Aussage. Während der Abschlussserie liefen keine Tests parallel.
- Wallclock mit `perf_counter`, SQL-Anzahl/-Zeit mit
  `connection.execute_wrapper`. SQL-Zeit umfasst `execute`, nicht sämtliche
  ORM-Arbeit oder separat bestimmte PostgreSQL-interne Ausführungszeit.

| Metrik, jeweils Median | Vorher | Nachher |
|---|---:|---:|
| Kontextzeit | 2,4924 s | 2,0586 s |
| Kontextqueries | 1.965 | 1.570 |
| Templatezeit | 1,3756 s | 0,3872 s |
| Templatequeries | 1.018 | 42 |
| Gesamtzeit pro Lauf | 3,7979 s | 2,4759 s |
| Queries pro Lauf | 2.983 | 1.612 |
| SQL-Ausführung pro Lauf | 1,7853 s | 1,0787 s |
| Kreaturenattributqueries | 143 | 13 |
| DruidCult-Existenzqueries | 136 | 5 |
| ShamanPatron-Existenzqueries | 106 | 2 |

Mediantotal und Summe der Teilmediane können voneinander abweichen.
Gesamtlaufzeitbereich: vorher 3,6339–4,0670 s, nachher 2,2604–2,7793 s.

| Paar | Vorher gesamt | Nachher gesamt |
|---|---:|---:|
| 1 | 3,9453 s | 2,2604 s |
| 2 | 3,8102 s | 2,4713 s |
| 3 | 3,7113 s | 2,3096 s |
| 4 | 3,6713 s | 2,4707 s |
| 5 | 3,6339 s | 2,5532 s |
| 6 | 3,7855 s | 2,5622 s |
| 7 | 3,9342 s | 2,5522 s |
| 8 | 3,7178 s | 2,4805 s |
| 9 | 3,9973 s | 2,3096 s |
| 10 | 4,0670 s | 2,7793 s |

Schon der isolierte Shop-/Inventarschritt reduzierte in einem Zwischenlauf
die Queryanzahl von 2.989 auf 1.953 bei identischem normalisiertem HTML.
Die abschließende Serie enthält zusätzlich Kreaturen- und Schuloptimierungen.
Die relationenspezifischen Regressionstests sichern die einzelnen Eingriffe
ab, statt nur eine fragile Gesamtqueryzahl festzuschreiben.

## Regressionstests und statische Prüfung

Neue Tests ausschließlich in
`charsheet/tests/test_sheet_loading_performance.py`:

1. Niedrigstes Waffenprofil-ID, mehrere Profile und Items ohne Profil;
   nur eine Sammelabfrage für Waffenprofile.
2. Kaufqualitäten und Materialüberschreibung ohne Qualitätscode-Lookups;
   Preise identisch zur bestehenden ItemEngine.
3. Verkaufsqualität, Material, Preis und Menge ohne zusätzliche
   Qualitäts-/Materialabfragen.
4. Wiederholte Kreaturenattribute einschließlich fehlender/ungültiger Werte
   mit nur einer Attributabfrage pro Engine.
5. Kreaturenoverride und Trainingszuwachs ohne Verändern des Basiswerts.
6. Neue Engine berücksichtigt geänderte Kreaturenvorlagen.
7. Klassifikation von klerikalen, profanen, Druiden-, Schamanen- und
   Kultistenschulen mit gebündelten Abfragen; neue Aufrufe sehen Änderungen.
8. Vollständiger Besitzer-GET und unveränderter Poll; Login erforderlich,
   fremde Benutzer erhalten weiterhin 404.
9. Zusätzliche Katalogschulen erzeugen keine zusätzlichen einzelnen
   Druiden-/Schamanenprüfungen; Schulen bleiben im Lernangebot vorhanden.

Abschließender gezielter Testaufruf:

```powershell
.venv\Scripts\python.exe manage.py test charsheet.tests.test_sheet_loading_performance charsheet.tests.test_learning_refresh charsheet.tests.test_shop_redesign charsheet.tests.test_shop_partial_refresh charsheet.tests.test_druid_arcane_lock --keepdb
```

**Ergebnis: 37 Tests erfolgreich in 10,184 s; Django-Systemcheck ohne
Befund.** Davon sind neun neue Regressionstests. Keine volle Suite
ausgeführt; die Testdatenbank wurde erhalten.

Separater Bestandsvergleich der drei betroffenen älteren Module
`test_creature_cards`, `test_druid_arcane_lock` und
`test_creature_trait_semantic_effects`: jeweils 80 Tests mit den bisherigen
und mit den aktuellen Funktionen. Beide Läufe haben dieselben zwei
Assertions und 69 Errors. Der Vergleich der Testmethoden, Fehlertypen und
Fehlermeldungen einschließlich Mehrfachvorkommen ist identisch, ohne neue
oder entfallene Fehler. Die Errors betreffen 40 Fremdschlüsselverletzungen
für fehlende Itemtyp-Katalogdaten, zwei fehlende Itemtypen und 27
fehlende Standardqualitäten. Die beiden Assertions betreffen bestehende
Adminformular-Pflichtfelder und eine Kraftbestien-GW-Variante. Diese
Bestandsprobleme wurden nicht durch Regel- oder Katalogänderungen umgangen.
Temporäre Diagnose-Testmodule wurden wieder entfernt.

`git diff --check` ist sauber. Flake8 ist für die neuen Tests und
`religion_rules.py` sauber. Ein zeilenweise zugeordneter Vergleich gegen
HEAD weist in den Änderungen keine neuen Flake8-Befunde aus. Es verbleiben
vorhandene E501-Längenbefunde in `sheet_context.py` (1.037, vorher 1.038)
und `creature_engine.py` (316). Eine großflächige Umformatierung dieser
Dateien wurde wegen der verlangten minimalen Änderungen vermieden.

## Noch offene Nachweise

Der Dashboardlink für eigene Charaktere und die direkte Charakter-URL
verwenden dieselbe Besitzer-View. Die optimierten Kontext-/Renderingpfade
wirken daher auf beide Einstiege sowie entsprechende vollständige Reloads;
dies belegt keine konkrete Browserzeitersparnis.

Die Zeit bis zur vollständigen Bedienbarkeit, CSS-/Modulwasserfall,
Bild-/Fontdecodierung, JavaScriptinitialisierung und tatsächliches
AJAX-Timing bleiben ungemessen: Browser-/Visualtests sind gemäß
Repository-Vorgabe ausgeschlossen. Es wurden keine Screenshots angefertigt.
Auch Produktion und vollständige Besitzerrequests auf repräsentativen
Anwendungsdaten wurden nicht gemessen oder verändert. Dafür wäre eine
isolierte Datenbankkopie mit erlaubten GET-Synchronisierungen nötig.
Insbesondere kann der vorhandene Formularinitialisierer bei klerikalen
Charakteren auch im Lesepfad eine Religionsreparatur versuchen; der
PostgreSQL-Schreibschutz darf für solche Messungen nicht umgangen werden.

Keine Migration und kein Deployment durchgeführt. Der nachgewiesene Gewinn
betrifft die hier dokumentierte Serverarbeit bei unveränderter Ausgabe.

Die Aussagen zu unveränderter Ausgabe beziehen sich auf die beschriebenen
Vergleichsläufe. Während der Arbeit kamen weitere Änderungen anderer
Arbeitsvorgänge im selben Worktree hinzu. Diese wurden nicht verändert;
die Performanceänderung selbst umfasst die drei oben genannten Pythondateien,
die neuen Tests und diesen Bericht.
