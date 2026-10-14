# Eigenschaftsbeschreibungen

Die Karten verwenden die vorhandene CharacterEngine und RaceAttributeLimit.
Es werden keine berechneten Beschreibungen am Charakter gespeichert.
Die angeklickten Werte bleiben mit den temporären Eigenschaftsänderungen verbunden.
Die Karte erscheint als Sprechblase an der angeklickten Zahl und folgt ihr beim
Scrollen. Sie ist nicht verschiebbar. Der Hauptscreen bleibt ohne Abdunklung
bedienbar; Schließen ist per Kreuz, Escape oder Klick außerhalb möglich.
Die Beschreibungen werden mit dem Attributpanel ausgeliefert und beim Klick
sofort angezeigt. Teilaktualisierungen ersetzen auch die vorbereiteten Texte.
Nur wenn der angezeigte Wert bereits durch eine noch unbestätigte temporäre
Änderung abweicht, wird die passende Beschreibung separat abgefragt.

## Auswahl

Für jede Eigenschaft gewinnt der aktive Eintrag mit der höchsten Untergrenze,
die den angezeigten Wert nicht übersteigt. Eine gesetzte Obergrenze muss ebenfalls
passen. Ohne Obergrenze gilt ein Eintrag weiter, bis eine höhere passende
Untergrenze greift. Prioritäten entscheiden bei gleicher Untergrenze.
Überlappende Einträge mit gleicher Untergrenze und Priorität werden abgewiesen.

Offizielle Angaben und eigene Erzähltexte sind getrennte Felder. Ein eigener
Text kann eine passende offizielle Referenz ergänzen. Fehlt ein renderbarer
Eigenschaftstext, wird die passende allgemeine Bedeutung als Ersatz verwendet.
Offizielle Referenzen erscheinen separat in der Karte.

Rassenvergleiche verwenden den Abstand zum bereits gespeicherten Rassenmaximum.
Hier bestimmen die konfigurierten Bereiche und Prioritäten die Auswahl.
Eigenschaftsspezifische Regeln gehen allgemeinen Regeln vor.

## Admin

Die drei Ansichten heißen **Eigenschaftsbeschreibungen**,
**Allgemeine Eigenschaftsbedeutungen** und **Eigenschaften im Rassenvergleich**.
Geltungsbereich, offizielle Referenz, eigene Texte und Vorschau sind getrennt.
Jedes Eingabefeld besitzt einen deutschen Hilfetext.

Vorlagen unterstützen `{character_name}`, `{race}`, `{attribute}`, `{value}`,
`{meaning}` und `{rating}`. `^Text^` erscheint männlich, `~~Text~~` weiblich.
Bei anderem oder nicht angegebenem Geschlecht ersetzt eine neutrale Vorlage
einen Text mit Geschlechtsmarkern. Literale Marker mit Backslash maskieren,
literale Klammern verdoppeln. Verschachtelte Marker sind nicht erlaubt.
Die Marker werden vor dem sicheren Markdown-Renderer verarbeitet.

Die Vorschau rendert den ungespeicherten Text mit Testdaten oder einem
ausgewählten Charakter. Die Vorschaugeschlechtsform ist ausdrücklich wählbar.
Sie speichert nichts und prüft nicht, ob der Eintrag für den Testwert ausgewählt
würde.

## Migrationen und Initialdaten

`0464_attribute_flavor` erstellt ausschließlich die drei Tabellen.
`0465_attribute_flavor_admin_labels` ergänzt deutsche Modell- und Feldnamen.
Beide enthalten keine Datenimporte und wurden lokal angewendet.

**Es wurden keine Inhalte in die Anwendungsdatenbank importiert.**

Die separate Datei `charsheet/management/attribute_flavor_initial.json` enthält
70 aus dem lokalen GRW (3. Edition, Kapitel 11, Seiten 222–223) transkribierte
Referenzeinträge, 12 allgemeine offizielle Bedeutungen sowie eigene Erzähltexte
und drei generische Vergleichsregeln. Die eigene allgemeine Beschreibung ab
13 enthält keine erfundene offizielle Einstufung. Die GRW-Referenzen haben
explizite Grenzen; insbesondere werden sie nicht als offizielle Einstufungen
für beliebig höhere Werte ausgegeben.

Nur nach ausdrücklicher Freigabe oder durch den Benutzer selbst:

```powershell
.venv\Scripts\python.exe manage.py import_attribute_flavor
```

Dieser explizite Import überschreibt keine bestehenden Einträge. Schema-
migrationen rufen ihn niemals auf. Die Importtests laufen ausschließlich in
der getrennten Django-Testdatenbank.

## Geänderte und neue Dateien

- Modelle: `charsheet/models/attribute_flavor.py`, `charsheet/models/__init__.py`.
- Renderer und Auflösung: `charsheet/narrative_templates.py`,
  `charsheet/attribute_flavor.py`, `charsheet/templatetags/attribute_flavor.py`.
- Admin: `charsheet/attribute_flavor_admin.py`, `charsheet/apps.py`,
  `static/js/charsheet/attribute_flavor_preview.js`.
- Karten: `charsheet/templates/charsheet/partials/_attribute_panel.html`,
  `charsheet/templates/charsheet/charsheet.html`, `codex_arcana/urls.py`,
  `static/js/charsheet/attribute_flavor.js`,
  `static/css/charsheet/attribute-flavor.css`,
  `static/js/charsheet/temporary_attributes.js`,
  `static/js/charsheet/bootstrap.js` (Cache-Version).
- Migrationen: `charsheet/migrations/0464_attribute_flavor.py`,
  `charsheet/migrations/0465_attribute_flavor_admin_labels.py`.
- Optionaler Import: `charsheet/management/attribute_flavor_initial.json`,
  `charsheet/management/commands/import_attribute_flavor.py`.
- Tests: `charsheet/tests/test_attribute_flavor.py`.
- Dokumentation: `docs/attribute_flavor.md`.

## Prüfung

34 Feature-Tests erfolgreich mit:

```powershell
.venv\Scripts\python.exe manage.py test charsheet.tests.test_attribute_flavor --keepdb
```

Im ebenfalls gezielt ausgeführten Modul `test_temporary_attributes` waren
7 von 8 Tests erfolgreich. Der Porträt-Test scheitert an der fehlenden Datei
`media/characters/test-portrait.png`. Kein Browser- oder visueller Test wurde
ausgeführt.
