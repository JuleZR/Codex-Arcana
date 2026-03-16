<p align="center">
  <img src="static/img/codexarcana.png" alt="Codex Arcana Logo" width="560">
</p>

# Codex Arcana

Codex Arcana ist ein Django-basiertes Verwaltungssystem für das Pen-and-Paper-Rollenspiel **Arcane Codex**. Die Anwendung verbindet klassische Charakterverwaltung mit einer regelgetriebenen Engine, damit ein Charakterbogen nicht nur Daten speichert, sondern spielrelevante Werte konsistent aus dem aktuellen Zustand berechnet.

## Was das Projekt heute abdeckt

- Dashboard mit aktiven Charakteren, Archiv, Entwurfsverwaltung und Kontoeinstellungen
- mehrphasige Charaktererstellung mit persistenten Drafts
- Character Sheet mit vorbereitetem Template-Kontext
- Inventar, Ausrüstung und qualitätsabhängige Itemwerte
- Lernen per EP-Ausgabe für Attribute, Skills, Sprachen und Schulen
- Shop mit Warenkorb, Preisberechnung und benutzerdefinierten Gegenständen
- persistentes Tagebuch pro Charakter mit JSON-Endpunkten für die UI
- Technik-, Spezialisierungs- und Modifikatorsystem für regelgetriebene Freischaltungen

## Technologie-Stack

- Python 3
- Django 5.2
- PostgreSQL 16
- Django Templates
- projektweite Assets in `static/`, app-spezifische Assets in `charsheet/static/`

## Schnellstart

### Voraussetzungen

- Python 3.x
- PostgreSQL auf `localhost:5432`
- alternativ Docker für die mitgelieferte Datenbank

### Datenbank per Docker starten

```bash
docker compose up -d db
```

### Anwendung starten

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Wichtige URLs

- Login: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Einblicke

Die folgenden Ansichten geben einen schnellen Eindruck vom aktuellen Stand der Anwendung. Alle Vorschaubilder sind klickbar.

### Einstieg

<table>
  <tr>
    <td align="center" valign="top">
      <a href="docs/screenshots/login.png">
        <img src="docs/screenshots/login.png" alt="Login" width="280">
      </a>
      <br>
      <strong>Login</strong>
      <br>
      Klarer Einstieg in die Anwendung.
    </td>
    <td align="center" valign="top">
      <a href="docs/screenshots/dashboard.png">
        <img src="docs/screenshots/dashboard.png" alt="Dashboard" width="280">
      </a>
      <br>
      <strong>Dashboard</strong>
      <br>
      Charaktere, Entwürfe, Hinweise und Schnellaktionen an einem Ort.
    </td>
    <td align="center" valign="top">
      <a href="docs/screenshots/dashboard_account_settings.png">
        <img src="docs/screenshots/dashboard_account_settings.png" alt="Kontoeinstellungen" width="280">
      </a>
      <br>
      <strong>Kontoeinstellungen</strong>
      <br>
      Benutzername, E-Mail und Passwort direkt im Dashboard pflegen.
    </td>
  </tr>
</table>

### Character Sheet und Werkzeuge

<table>
  <tr>
    <td align="center" valign="top">
      <a href="docs/screenshots/character_sheet.png">
        <img src="docs/screenshots/character_sheet.png" alt="Character Sheet" width="280">
      </a>
      <br>
      <strong>Character Sheet</strong>
      <br>
      Zentrale Arbeitsansicht mit Werten, Inventar und Statusdaten.
    </td>
    <td align="center" valign="top">
      <a href="docs/screenshots/character_sheet_shop.png">
        <img src="docs/screenshots/character_sheet_shop.png" alt="Shop" width="280">
      </a>
      <br>
      <strong>Shop</strong>
      <br>
      Kaufbare Items, Qualitäten, Rabatt und Warenkorb in einem Fenster.
    </td>
    <td align="center" valign="top">
      <a href="docs/screenshots/character_sheet_learning.png">
        <img src="docs/screenshots/character_sheet_learning.png" alt="Lernen" width="280">
      </a>
      <br>
      <strong>Lernen</strong>
      <br>
      EP-basierte Steigerung für Attribute, Skills, Sprachen und Schulen.
    </td>
  </tr>
  <tr>
    <td align="center" valign="top">
      <a href="docs/screenshots/character_sheet_diary.png">
        <img src="docs/screenshots/character_sheet_diary.png" alt="Tagebuch" width="280">
      </a>
      <br>
      <strong>Tagebuch</strong>
      <br>
      Persistente Chronik mit datierbaren und fixierbaren Einträgen.
    </td>
    <td></td>
    <td></td>
  </tr>
</table>

## Anwendungstutorial

Dieses Tutorial beschreibt den aktuell möglichen Hauptablauf mit dem bestehenden Funktionsumfang.

### 1. Anmelden

1. Öffne `http://127.0.0.1:8000/`.
2. Melde dich mit deinem Benutzerkonto an.
3. Nach erfolgreichem Login landest du automatisch im Dashboard.

### 2. Dashboard verstehen

Im Dashboard findest du mehrere Bereiche mit klaren Aufgaben:

- **Benutzerbereich** mit Logout und Kontoeinstellungen
- **Zuletzt verwendet** für schnellen Wiedereinstieg in bereits geöffnete Charaktere
- **Systemstatus** mit globalen Datenmengen wie Items, Skills, Schulen und Sprachen
- **Hinweise** für unverteilte EP, offenen Schaden oder andere auffällige Zustände
- **Offene Entwürfe** für angefangene Charaktererstellungen
- **Charakterverwaltung** für aktive Charaktere mit Öffnen-, Archivieren- und Löschen-Aktion
- **Archiv** für stillgelegte Charaktere, die später reaktiviert werden können

### 3. Einen neuen Charakter anlegen

1. Klicke im Dashboard auf **Neuer Charakter**.
2. Die Charaktererstellung öffnet sich in einem Fenster über dem Dashboard.
3. Wähle die Grunddaten und arbeite dich durch die vier Phasen.
4. Wenn du unterbrichst, bleibt der Entwurf erhalten und erscheint später unter **Offene Entwürfe**.
5. Beim Finalisieren erzeugt die Anwendung den echten Charakter mit allen zugehörigen Daten.

### 4. Einen bestehenden Charakter öffnen

1. Wechsle in der Tabelle **Charakterverwaltung** zum gewünschten Charakter.
2. Klicke auf **Öffnen**.
3. Das Character Sheet zeigt dir den kompletten aktuellen Zustand des Charakters samt berechneter Werte.

### 5. Im Character Sheet arbeiten

Das Character Sheet ist die wichtigste Arbeitsoberfläche der App. Dort laufen aktuell mehrere Bereiche zusammen:

- Attribut- und Fertigkeitsanzeige mit regelbasierten Ableitungen
- Vorteile, Nachteile, Sprachen, Schulen und Techniken
- Waffen-, Rüstungs- und Inventarverwaltung
- Geld-, EP-, Schaden- und Ruhmverwaltung
- Lernfenster, Shop und Tagebuch

### 6. Charakterinformationen direkt pflegen

Im Character Sheet können die Stammdaten des Charakters direkt aktualisiert werden. Dazu gehören unter anderem:

- Name
- Geschlecht
- Alter, Größe und Gewicht
- Haut-, Haar- und Augenfarbe
- Herkunft, Religion und Erscheinungsbild

Die Eingaben werden über ein Inline-Formular gespeichert, ohne dass ein separater Admin-Bereich nötig ist.

### 7. Schaden, Geld und Erfahrung anpassen

Für die laufende Spielsitzung sind mehrere Direktaktionen vorhanden:

- Schaden erhöhen oder heilen
- Geld anpassen
- aktuelle und gesamte Erfahrung verändern
- persönliche Ruhmpunkte verwalten

Gerade Schaden ist wichtig, weil die Engine daraus automatisch Wundstufen und mögliche Abzüge ableitet.

### 8. Inventar und Ausrüstung nutzen

Im Inventar lassen sich Gegenstände je nach Typ unterschiedlich behandeln:

- Waffen, Rüstungen und Schilde können an- oder abgelegt werden
- Verbrauchsgegenstände können verbraucht werden
- Items lassen sich einzeln oder stackweise entfernen
- Qualitäten beeinflussen Preise und teilweise auch Werte

Ausgerüstete Waffen und Rüstung wirken direkt auf die berechneten Kampf- und Belastungswerte.

### 9. Lernen mit Erfahrungspunkten

Der Lernbereich dient dazu, aktuelle EP in Fortschritt umzuwandeln.

Der derzeitige Workflow ist:

1. Lernfenster öffnen.
2. Zielwerte für Attribute, Skills, Sprachen oder Schulen setzen.
3. Kosten indirekt über die hinterlegte Lernlogik prüfen lassen.
4. Änderungen anwenden.
5. Die App reduziert die aktuellen EP und aktualisiert die betroffenen Charakterdaten atomar.

Wenn nicht genug aktuelle EP vorhanden sind oder eine Obergrenze verletzt wird, lehnt die Anwendung den Vorgang mit einer passenden Rückmeldung ab.

### 10. Den Shop verwenden

Der Shop unterstützt zwei typische Fälle:

- vorhandene Basis-Items mit Qualität und Menge kaufen
- neue benutzerdefinierte Shop-Items anlegen

Der Kaufablauf ist aktuell so gedacht:

1. Item(s) auswählen.
2. Menge und gegebenenfalls Qualität festlegen.
3. Optional Rabatt eintragen.
4. Warenkorb kaufen.
5. Die App prüft Geld, Mengenregeln und Stackbarkeit und aktualisiert danach Geldbeutel und Inventar in einer Transaktion.

### 11. Das Tagebuch führen

Das Tagebuch ist inzwischen serverseitig persistent und nicht mehr nur eine lokale Browserfunktion. Der aktuelle Ablauf:

1. Im Character Sheet den Tagebuchbereich öffnen.
2. Einen Text in den aktuellen offenen Eintrag schreiben.
3. Optional ein Datum setzen.
4. Den Eintrag speichern oder fixieren.
5. Fixierte Einträge können später wieder in den Bearbeitungsmodus geholt oder gelöscht werden.

Die Anwendung sorgt serverseitig dafür, dass die Reihenfolge stabil bleibt und immer genau ein leerer Eintrag als nächste Schreibfläche vorhanden ist.

### 12. Charaktere archivieren oder reaktivieren

Nicht mehr aktiv gespielte Charaktere müssen nicht gelöscht werden:

1. Im Dashboard bei einem aktiven Charakter auf **Archivieren** klicken.
2. Der Charakter verschwindet aus der aktiven Tabelle und erscheint im Archiv.
3. Über **Reaktivieren** kann er jederzeit wieder in die aktive Liste verschoben werden.

## Projektstruktur

```text
codex_arcana/                  Django-Projektkonfiguration
charsheet/
  models/                      fachlich gruppierte Domain-Modelle
  engine/                      Character- und Item-Berechnungen
  templates/charsheet/         Dashboard, Character Sheet, Partials
  learning.py                  EP-Lernworkflow
  shop.py                      Shop-Logik und Warenkorb-Kauf
  sheet_context.py             vorbereiteter Kontext für das Character Sheet
  view_utils.py                kleine Formatierungshelfer für Views/UI
static/                        globale CSS-, JS-, Bild- und Font-Assets
docs/                          technische Projektdokumentation
```

## Technische Neuerungen gegenüber dem früheren Stand

Die Dokumentation wurde auf den aktuellen Code angepasst. Die wichtigsten strukturellen Änderungen sind:

- `charsheet/models.py` wurde in ein Modellpaket unter `charsheet/models/` aufgeteilt.
- `CharacterEngine` ist fachlich breiter geworden und arbeitet mit Hilfsmodulen für Kampf, Ausrüstung und Progression.
- Das Character Sheet bezieht seinen Datenbestand aus `sheet_context.py` statt aus umfangreicher Template-Logik.
- Tagebuch, Shop und Lernen sind als eigene Workflow-Module ausgelagert.
- Technik- und Spezialisierungsdaten wurden deutlich erweitert und sind jetzt ein zentraler Teil des Regelmodells.

## Weiterführende Dokumentation

- [`docs/README.md`](docs/README.md)
- [`docs/setup.md`](docs/setup.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/models.md`](docs/models.md)
- [`docs/engine.md`](docs/engine.md)
- [`docs/routes.md`](docs/routes.md)
- [`docs/legal.md`](docs/legal.md)

## Rechtliche Angaben für Self-Hosting

Die öffentlichen Seiten `Impressum` und `Datenschutz` lesen ihre Betreiberdaten aus `LEGAL_INFO` in `codex_arcana/settings.py`. Diese Werte können über Umgebungsvariablen gesetzt werden:

- `LEGAL_SITE_NAME`
- `LEGAL_OPERATOR_NAME`
- `LEGAL_ADDRESS`
- `LEGAL_EMAIL`
- `LEGAL_PHONE`
- `LEGAL_RESPONSIBLE_PERSON`
- `LEGAL_REGISTER_ENTRY`
- `LEGAL_VAT_ID`
- `LEGAL_SUPERVISORY_AUTHORITY`

## 🎲 DDDice Integration

Codex Arcana verwendet **DDDice** zur Darstellung von animierten 3D-Würfeln im Browser.

Die eigentliche Würfelmechanik wird vollständig **serverseitig im Backend berechnet**.  
DDDice dient ausschließlich dazu, das Ergebnis visuell als Würfelwurf darzustellen.

Dadurch bleibt das Würfelsystem:

- regelkonform zum Arcane-Codex-Regelwerk  
- deterministisch und serverseitig kontrolliert  
- nicht clientseitig manipulierbar  
- visuell ansprechend durch 3D-Würfelanimationen  

---

### 1. Warum Codex Arcana DDDice verwendet

Codex Arcana nutzt DDDice, um eine visuelle Darstellung von Würfelwürfen zu ermöglichen, ohne die eigentliche Spiellogik in den Browser zu verlagern.

Die Berechnung der Würfelergebnisse erfolgt ausschließlich im Backend.  
DDDice erhält lediglich das bereits berechnete Ergebnis und stellt dieses als 3D-Würfelwurf dar.

Dieses Design hat mehrere Vorteile:

- Würfelergebnisse können nicht clientseitig manipuliert werden  
- Die Spiellogik bleibt vollständig unter Kontrolle des Servers  
- Die Benutzeroberfläche erhält dennoch eine realistische Würfelanimation  
- Das System bleibt flexibel für eigene Regelmechaniken  

---

### 2. Funktionsweise

Die Integration trennt **Spiellogik** und **Visualisierung**.

Ablauf eines Würfelwurfs:

1. Der Benutzer klickt im Interface auf einen Würfelbutton (z. B. `1d10` oder `2d10`)
2. Das Frontend sendet einen Request an das Backend
3. Das Backend berechnet den Würfelwurf nach den Spielregeln
4. Das Ergebnis wird als JSON an das Frontend zurückgegeben
5. DDDice visualisiert den Wurf mit genau diesen Ergebnissen

Beispiel eines Backend-Responses:

```json
{
  "sides": 10,
  "count": 2,
  "rolls": [7, 8],
  "total": 15
}
```

Das Frontend übergibt diese Werte anschließend an die DDDice-Engine, die daraus eine 3D-Animation erzeugt.

---

### 3. Einrichtung

Damit die Integration funktioniert, sind einige Schritte notwendig.

#### 3.1 DDDice Account und API Key

Ein API-Key kann im DDDice Dashboard erstellt werden: https://dddice.com

---

#### 3.2 Dice Room erstellen

DDDice verwendet sogenannte **Rooms**, über die Würfelwürfe zwischen den Clients synchronisiert werden.

Für die Verbindung werden mindestens folgende Angaben benötigt:

- `API_KEY`
- `ROOM_SLUG`

Ist der Raum passwortgeschützt (empfohlen), wird zusätzlich benötigt:

- `ROOM_PASSCODE`

---

#### 3.3 Frontend konfigurieren

Die Konfiguration der DDDice-Integration erfolgt über das **Dashboard**.

1. Öffne im Dashboard die **Kontoeinstellungen**.
2. Aktiviere die Option **„DDDice aktivieren“**.
3. Trage anschließend die erforderlichen Verbindungsdaten ein:

- `API_KEY`
- `ROOM_SLUG`
- optional: `ROOM_PASSCODE` (falls der Raum passwortgeschützt ist)

4. Wähle anschließend ein **Dice Set** aus.

Falls kein Dice Set angezeigt wird:

- auf **„Aktualisieren“** klicken, um verfügbare Sets neu zu laden  
- oder im eigenen **DDDice Account prüfen**, ob bereits ein Dice Set hinterlegt ist

⚠️ **Wichtig**:  
Das gewählte Dice Set muss **sowohl `d10` als auch `d10x` unterstützen**, da diese Würfeltypen von Codex Arcana verwendet werden.

Nach dem Speichern der Einstellungen kann Codex Arcana die Verbindung zu DDDice herstellen und Würfelwürfe visualisieren.

---

### 3.4 Würfelergebnis darstellen

Nachdem das Backend einen Wurf berechnet hat, wird das Ergebnis an DDDice übergeben.

```javascript
await dddice.roll({
  dice: [
    { type: "d10", value: 7 },
    { type: "d10", value: 8 }
  ]
});
```

DDDice rendert anschließend eine vollständige 3D-Würfelanimation auf dem `charsheet`

---

#### Rechtliche Hinweise

Codex Arcana verwendet **DDDice** zur Darstellung von 3D-Würfeln im Browser.

DDDice ist ein externer Dienst eines Drittanbieters und unterliegt dessen eigenen Nutzungsbedingungen:

https://dddice.com

Die DDDice-Integration ist standardmäßig deaktiviert und muss im **Dashboard unter Kontoeinstellungen** ausdrücklich aktiviert werden.

Nur wenn die Option **„DDDice aktivieren“** gesetzt ist, wird die entsprechende Integration geladen und eine Verbindung zu den Servern von DDDice aufgebaut. Dabei können technisch notwendige Verbindungsdaten (z. B. die IP-Adresse) an den Anbieter übermittelt werden.

Ist die Option deaktiviert, wird die DDDice-Integration nicht geladen und es findet keine Verbindung zu den Servern von DDDice statt.

Alle Rechte an der DDDice-Engine sowie deren API verbleiben beim jeweiligen Rechteinhaber.

---

## Lizenz

Das Projekt steht unter der GNU General Public License v3.0. Details stehen in `LICENSE`.

Separate Drittlizenzen, zum Beispiel für eingebundene Schriftarten unter `static/fonts/`, bleiben davon unberührt.
