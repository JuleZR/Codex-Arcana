<p align="center">
  <img src="static/img/codexarcana.png" alt="Codex Arcana Logo" width="560">
</p>

<p align="center">
  🇩🇪 Deutsch | 🇬🇧 <a href="README.md">English</a>
</p>

# Codex Arcana

> ⚠️ **Status: Early Alpha / Prototyp**  
> Dieses Projekt befindet sich aktuell in einem frühen Entwicklungsstadium. Funktionen können unvollständig, instabil oder Änderungen unterworfen sein.

Codex Arcana ist ein Django-basiertes Verwaltungssystem für das Pen-and-Paper-Rollenspiel **Arcane Codex**. Die Anwendung verbindet klassische Charakterverwaltung mit einer regelgetriebenen Engine, damit ein Charakterbogen nicht nur Daten speichert, sondern spielrelevante Werte konsistent aus dem aktuellen Zustand berechnet.

---

## Was das Projekt heute abdeckt

- Dashboard mit aktiven Charakteren, Archiv, Entwurfsverwaltung und Kontoeinstellungen  
- mehrphasige Charaktererstellung mit persistenten Drafts  
- Character Sheet mit vorbereitetem Template-Kontext  
- Inventar, Ausrüstung und qualitätsabhängige Itemwerte  
- Lernen per EP-Ausgabe für Attribute, Skills, Sprachen und Schulen  
- Shop mit Warenkorb, Preisberechnung und benutzerdefinierten Gegenständen  
- persistentes Tagebuch pro Charakter mit JSON-Endpunkten für die UI  
- Technik-, Spezialisierungs- und Modifikatorsystem für regelgetriebene Freischaltungen  

---

## Technologie-Stack

- Python 3  
- Django 5.2  
- PostgreSQL 16  
- Django Templates  
- projektweite Assets in `static/`, app-spezifische Assets in `charsheet/static/`  

---

## Schnellstart

### Voraussetzungen

- Python 3.x  
- PostgreSQL auf `localhost:5432`  
- alternativ Docker für die mitgelieferte Datenbank  

### Datenbank per Docker starten

docker compose up -d db  

### Anwendung starten

python -m pip install -r requirements.txt  
python manage.py migrate  
python manage.py createsuperuser  
python manage.py runserver  

### Wichtige URLs

- Login: `http://127.0.0.1:8000/`  
- Admin: `http://127.0.0.1:8000/admin/`  

---

## Einblicke

Die folgenden Ansichten geben einen schnellen Eindruck vom aktuellen Stand der Anwendung. Alle Vorschaubilder sind klickbar.

---

## Anwendungstutorial

Dieses Tutorial beschreibt den aktuell möglichen Hauptablauf mit dem bestehenden Funktionsumfang.

### 1. Anmelden

1. Öffne `http://127.0.0.1:8000/`  
2. Melde dich mit deinem Benutzerkonto an  
3. Nach erfolgreichem Login landest du automatisch im Dashboard  

### 2. Dashboard verstehen

Im Dashboard findest du mehrere Bereiche mit klaren Aufgaben:

- **Benutzerbereich** mit Logout und Kontoeinstellungen  
- **Zuletzt verwendet** für schnellen Wiedereinstieg  
- **Systemstatus** mit globalen Datenmengen  
- **Hinweise** für unverteilte EP, offenen Schaden oder andere Zustände  
- **Offene Entwürfe**  
- **Charakterverwaltung**  
- **Archiv**  

### 3. Einen neuen Charakter anlegen

1. Klicke auf **Neuer Charakter**  
2. Die Erstellung öffnet sich als Overlay  
3. Arbeite dich durch die Phasen  
4. Entwürfe bleiben erhalten  
5. Finalisierung erzeugt den Charakter  

### 4. Einen bestehenden Charakter öffnen

1. Charakter auswählen  
2. **Öffnen** klicken  
3. Character Sheet ansehen  

### 5. Im Character Sheet arbeiten

Das Character Sheet ist die zentrale Arbeitsoberfläche:

- Attribute und Fertigkeiten  
- Vorteile, Nachteile, Sprachen, Schulen und Techniken  
- Waffen-, Rüstungs- und Inventarverwaltung  
- Geld, Erfahrung, Schaden und Ruhm  
- Lernbereich, Shop und Tagebuch  

---

## Projektstruktur

codex_arcana/  
charsheet/  
  models/  
  engine/  
  templates/  
  learning.py  
  shop.py  
  sheet_context.py  
  view_utils.py  
static/  
docs/  

---

## 🎲 DDDice Integration

Codex Arcana verwendet **DDDice** zur Darstellung von animierten 3D-Würfeln im Browser.

Die eigentliche Würfelmechanik wird vollständig serverseitig berechnet.  
DDDice dient ausschließlich der visuellen Darstellung.

---

### Rechtliche Hinweise

DDDice ist ein externer Dienst eines Drittanbieters:

https://dddice.com

Die Integration ist optional und wird nur geladen, wenn sie in den Einstellungen aktiviert wurde.

Bei aktivierter Integration können technisch notwendige Daten (z. B. IP-Adresse) übertragen werden.  
Ist sie deaktiviert, findet keine Verbindung statt.

Alle Rechte an der DDDice-Engine verbleiben beim jeweiligen Rechteinhaber.

---

## Lizenz

Dieses Projekt steht unter der GNU General Public License v3.0.

Drittlizenzen (z. B. für Schriftarten unter `static/fonts/`) bleiben davon unberührt.