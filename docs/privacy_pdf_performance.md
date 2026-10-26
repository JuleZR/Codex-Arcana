# DSGVO-PDF: Performancekorrektur vom 26. Oktober 2026

## Messung und Aussagegrenzen

Gemessen lokal unter Windows mit Python 3.12 und PyMuPDF 2.0. Ausschließlich
synthetische Daten: 5.000 Datensätze mit insgesamt 50.000 Feldern, davon ein
geschützter Wert, zusätzlich ausgeschlossene Originaltexte in internen
Prüfkandidaten und nicht freigegebenen Feldern. Ergebnis: 3.467 A4-Seiten.
Keine Produktivdaten, Browserprüfungen oder Änderungen an laufenden Jobs.

Der produktive Stack im Speichern beweist keinen Zeitanteil. Die gemeldeten
33 Minuten werden durch diesen einfachen synthetischen Datenbestand nicht
reproduziert. Lange/strukturierte Werte, Datensammlung und die konkrete
Serverumgebung können andere Zeitanteile verursachen. Die neue Phasenmessung
ermöglicht deren Untersuchung nach einer gesondert freigegebenen Bereitstellung.

## Tatsächlich gemessene Engpässe und Änderungen

- Bisher wird die wachsende Arbeits-PDF nach jedem HTML-Block gespeichert und
  erneut geöffnet. Das wiederholte Einlesen der wachsenden PDF-Struktur wird
  mit zunehmender Blockzahl teurer. Jetzt erfolgt das nur alle 32 Blöcke;
  nach dem ersten vollständigen Arbeitsstand ausschließlich inkrementell.
  Die private dateibasierte Arbeitsablage bleibt erhalten. Die fertige PDF
  wird genau einmal vollständig gespeichert.
- `garbage=3` sucht zusätzlich nach doppelten Objekten; `deflate=True`
  komprimiert Streams. Beides kostet hier deutlich mehr Zeit als `garbage=0`.
- Kopfzeile, Trennlinie und Seitenzahl wurden einzeln als zusätzliche Streams
  geschrieben. Jetzt werden sie pro Seite in einer Shape gemeinsam übertragen;
  Positionen und Texte bleiben erhalten.
- ZIP verwendet dieselbe einmal aufbereitete Benutzerkopie für PDF und JSON.
  Die separate interne Prüfkopie bleibt für die interne Ausgabe erhalten.
- Das bestehende einmalige Layout pro begrenztem HTML-Block und das nachträglich
  erstellte Inhaltsverzeichnis bleiben bestehen. Es gibt keine Feldobergrenze.

PyMuPDF beschreibt die Speicheroptionen in der
[offiziellen Dokumentation](https://pymupdf.readthedocs.io/en/latest/document.html#Document.save).

## Vorher und nachher

Direkte Messungen des gesamten PDF-Aufbaus einschließlich abschließender
Speicherung; Datenbankabfragen und ZIP sind hier nicht Bestandteil der Messung.
Der alte Code wird im Benchmark aus `HEAD:charsheet/privacy_pdf.py` geladen.
Die Werte beziehen sich auf Revision
`87a4fdaf3e78023617a37893ef4e4e97b8c7c50d`. Nach einem Commit kann sie mit
`--baseline-ref 87a4fdaf3e78023617a37893ef4e4e97b8c7c50d` gewählt werden.

| Ablauf | Gesamtzeit | Finale Speicherung | Prozessspeicherspitze |
| --- | ---: | ---: | ---: |
| Bisheriger Aufbau, `garbage=0, deflate=False` | 26,94 s | 0,141 s | 268,2 MB |
| Bisheriger Aufbau, `garbage=1, deflate=False` | 27,02 s | 0,189 s | 268,0 MB |
| Bisheriger Aufbau und bisherige Option `garbage=3, deflate=True` | 34,75 s | 8,005 s | 265,5 MB |
| Optimierter Aufbau, `garbage=0, deflate=False` | 8,79 s | 0,103 s | 264,7 MB |

Im direkten Vergleich rund **3,95-mal schneller**, etwa **75 % weniger Zeit**.
Das ist ein lokaler synthetischer Vergleich, keine Laufzeitgarantie für das
Produktivkonto. Ein Zwischenstand nur mit gebündelter Arbeitsablage benötigte
10,84 Sekunden; die gemeinsame Seitendekoration senkte die Zeit weiter.

Zusätzlich wurden die drei Optionen in jeweils frischen Prozessen auf dieselbe
fertig vorbereitete PDF angewendet. Die Speicherzeit beginnt nach dem Öffnen
und endet vor der Integritätsprüfung. Die Prozessspitze schließt die geladene
PDF und native MuPDF-Allokationen ein, nicht die spätere Prüfung.

| Speicheroption | Speichern, alter Aufbau | Dateigröße | Prozessspitze |
| --- | ---: | ---: | ---: |
| `garbage=0, deflate=False` | 0,288 s | 31.391.171 Byte | 162,5 MB |
| `garbage=1, deflate=False` | 0,303 s | 31.391.171 Byte | 162,3 MB |
| `garbage=3, deflate=True` | 3,523 s | 18.522.077 Byte | 164,1 MB |

| Speicheroption | Speichern, optimierter Aufbau | Dateigröße | Prozessspitze |
| --- | ---: | ---: | ---: |
| `garbage=0, deflate=False` | 0,220 s | 30.477.513 Byte | 160,3 MB |
| `garbage=1, deflate=False` | 0,229 s | 30.477.513 Byte | 160,3 MB |
| `garbage=3, deflate=True` | 1,975 s | 17.528.678 Byte | 161,4 MB |

Erneutes Laden verändert den nativen Zustand gegenüber einer gerade aufgebauten
PDF. Deshalb ersetzen die isolierten Speichermessungen den direkten
Gesamtvergleich nicht. Die gewählte Produktionsoption ist
**`garbage=0, deflate=False`**: in beiden Vergleichen am schnellsten; größere
PDF-Dateien sind der gemessene Preis. ZIP komprimiert die PDF weiterhin beim
Archivieren. `garbage=1` bot für diese neu erzeugte PDF keinen Größen- oder
Integritätsvorteil.

## Datenschutz und Integrität

Der Collector wendet die bestehenden Freigabe-, Eigentums-, Geheimnis- und
Schwärzungsregeln vor dem Layout an. `recipient_payload` entfernt interne
Prüfkandidaten, nicht freigegebene Felder und interne Prüfmetadaten. Erst aus
dieser Benutzerkopie entstehen HTML und neue PDF-Objekte. Es wird keine
ursprüngliche PDF importiert und kein Originaltext optisch überdeckt oder
nachträglich aus der PDF gelöscht. Der geringere Garbage-Wert wird daher
nicht als Schwärzungsverfahren verwendet.

Automatisierte Prüfungen sichern für alle drei Speicheroptionen:

- Öffnen ohne PDF-Reparatur, vollständige synthetische Werte und sichtbare
  Schutzmarkierung statt des geschützten Wertes.
- Ausgeschlossene Originale erscheinen bereits in keinem Story-HTML.
- Prüfung aller PDF-Objekte und dekomprimierten Streams, einschließlich nicht
  referenzierter Objekte, auf die synthetischen Original-/Ausschlussmarker.
  Zusätzlich wird der Text aller Seiten extrahiert und geprüft.
- Korrekte fortlaufende Seitenzahlen, gültige Lesezeichen, Abschnittsüberschriften
  auf den Zielseiten und interne Inhaltsverzeichnis-Verweise.
- Genau eine vollständige finale Speicherung, gebündelte inkrementelle
  Arbeitsstände und Entfernen der Arbeitsdateien nach Erfolg und Layoutfehlern.
- Bestehende gezielte Tests für tatsächliche Schwärzungsentscheidungen,
  Geheimnisse und fremde Inhalte sowie JSON/ZIP, Downloads, Fehler, Abbruch,
  Ablauf und verwaiste Jobdateien.

Eine Layout-Ausnahme kann einen nativen Writer über ihren Traceback am Leben
halten. Deshalb gehört dessen privater Dateihandle jetzt einem expliziten
Python-Dateikontext; er wird auch dann geschlossen, wenn noch Referenzen auf
den Writer bestehen. Der Windows-Fehlerbereinigungstest deckt dies ab.

Abschließendes Ergebnis: **35 gezielte Tests erfolgreich** (neue PDF-
Performancetests, bestehende Jobtests, ausgewählte Export-/Freigabe- und
Datenschutztests). Flake8 wurde für alle berührten Python-Dateien geprüft.
Keine vollständige Testsuite und keine Browser-/Sichtprüfung ausgeführt.

Private Verzeichnisse, Dateirechte, Berechtigungsprüfungen, Download-Sperren,
Einmalabruf, Watchdog und Bereiniger wurden nicht abgeschwächt. Die neuen
`progress.json`/`progress.pending` enthalten ausschließlich fest definierte
Phasen und werden im selben privaten Jobverzeichnis mitbereinigt.

## Protokolle und Status

`privacy_export_job` schreibt die neuen Messungen über seinen bestehenden
kontrollierten Logger nach stderr, beispielsweise ins Service-Journal.
Erfasst werden Vorbereitung, Prüfung/Schwärzungsentscheidungen, PDF-Inhalt,
Inhaltsverzeichnis, Zusammenführung, Seitenzahlen/Verweise, finales Speichern,
JSON und ZIP sowie Gesamtzeit, Seitenzahl und Ausgabedateigröße.
Wiederholte Phasen werden summiert; verschachtelte Zeiten werden nicht doppelt
gezählt. Die Feldentscheidungen werden innerhalb der Datensammlung separat
zeitlich erfasst. Die gesamte Quelldatensammlung wird nicht nochmals ausgeführt,
um sie künstlich von diesen Entscheidungen zu trennen.

Die Logs enthalten nur feste technische Phasen, Sekunden und numerische
Zähler. Keine Kontokennung, Feldschlüssel, Werte, Tokens, Pfade oder Prüftexte.
Die Statusseite liest die atomar publizierte Phase auch bei belegter Worker-
Sperre, ohne den großen Snapshot zu laden. Die bestehende automatische
Aktualisierung bleibt erhalten; es werden keine Prozentwerte geschätzt.
„Export abgeschlossen“ wird erst nach Veröffentlichung des fertigen Exports
angezeigt. Eine Vorschau ist keine automatische Freigabe.

Gemessene Restkosten des optimierten Aufbaus: Seitenzahlen und Verweise
4,46 Sekunden, Inhalt/Layout 3,43 Sekunden, Zusammenführung 0,64 Sekunden.
Seitenstrukturen und Snapshot wachsen weiterhin mit der Auskunft; die
dateibasierte Verarbeitung begrenzt keine beliebig große Ausgabe auf konstanten
Speicher. Lange und verschachtelte Werte sind zusätzlich durch die bestehenden
PDF-Integritätstests abgedeckt.

## Reproduktion

```powershell
.venv\Scripts\python.exe -m charsheet.tests.benchmark_privacy_pdf --fields 50000 --baseline
.venv\Scripts\python.exe -m charsheet.tests.benchmark_privacy_pdf --fields 50000 --baseline --original-save
.venv\Scripts\python.exe -m charsheet.tests.benchmark_privacy_pdf --fields 50000 --baseline --direct-config --garbage 1
.venv\Scripts\python.exe -m charsheet.tests.benchmark_privacy_pdf --fields 50000
.venv\Scripts\python.exe manage.py test charsheet.tests.test_privacy_pdf_performance charsheet.tests.test_privacy_jobs --keepdb
```

Das Benchmarkskript liegt unter `charsheet/tests/` und berührt keine Datenbank.
Temporäre PDFs werden nach jeder Messung entfernt. Die getrennten
Speicherprozesse sind wichtig für aussagekräftige native Speicherspitzen.
Es wurde kein Timeout erhöht. Eine Übernahme in die Produktivumgebung und die
erneute Messung des betroffenen Kontos benötigen die gesonderte Freigabe.
