# Routen und Views

Die URL-Definitionen liegen zentral in `codex_arcana/urls.py`. Nahezu alle fachlichen Endpunkte werden direkt von `charsheet.views` bedient.

## Grundsätzliche View-Konventionen

- charakterbezogene Routen prüfen Eigentum immer über Hilfsfunktionen wie `_owned_character_or_404(...)`
- klassische Formularaktionen enden fast immer mit Redirect zur passenden Seite
- interaktive Frontend-Bereiche wie Shop oder Tagebuch nutzen JSON-Antworten
- fast alle fachlichen Endpunkte setzen einen eingeloggten Benutzer voraus

## Seitenrouten

### `GET /`

Login-Seite über Djangos `LoginView`.

### `GET /dashboard/`

Benutzerspezifisches Dashboard. Die View sammelt:

- aktive Charaktere
- archivierte Charaktere
- Drafts der Charaktererstellung
- aggregierte Summen für Geld und EP
- Warnungen zu unverteilten EP und Schaden
- zuletzt geöffnete Charaktere

### `GET|POST /character/new/`

Mehrphasige Charaktererstellung. Die View übernimmt gleichzeitig:

- Start eines neuen Drafts
- Navigation zwischen Phasen
- Zwischenspeichern in `draft.state`
- Validierung pro Phase
- Finalisierung in einen echten Charakter

### `GET|POST /character/<character_id>/edit/`

Bearbeitung eines vorhandenen Charakters über denselben Phasenansatz wie bei der Erstellung. Die Route ist für eigene Charaktere reserviert.

### `GET /sheet/`

Rendert das Character-Sheet-Template ohne echten Charakterkontext. Praktisch eher ein technischer oder historischer Endpunkt; das eigentliche Arbeiten läuft über die charakterbezogene Sheet-Route.

### `GET /character/<character_id>/`

Vollständiges Character Sheet für einen eigenen Charakter. Die View:

- aktualisiert `last_opened_at`
- baut den kompletten Sheet-Kontext über `build_character_sheet_context(...)`
- schließt auf Wunsch das Lernfenster nach erfolgreichem Lernvorgang

### `GET /impressum/`

Öffentliche Seite mit Betreiberangaben aus `LEGAL_INFO`.

### `GET /datenschutz/`

Öffentliche Datenschutzseite mit denselben konfigurierbaren Betreiberdaten.

## Konto- und Sitzungsaktionen

### `POST /dashboard/account/update/`

Aktualisiert Benutzername, E-Mail und optional Passwort. Nutzt `AccountSettingsForm` und aktualisiert bei Passwortwechsel die Session.

### `POST /app/logout/`

Allgemeiner Logout für die Anwendung.

### `POST /admin/logout/`

Logout-Override für den Django-Admin.

## Charakterverwaltung

### `POST /character/<character_id>/archive/`

Archiviert einen eigenen Charakter.

### `POST /character/<character_id>/unarchive/`

Reaktiviert einen archivierten Charakter.

### `POST /character/<character_id>/delete/`

Löscht einen Charakter. Schutzfälle wie `ProtectedError` werden in der View behandelt.

### `POST /character/draft/<draft_id>/delete/`

Verwirft einen laufenden Erstellungsentwurf.

## Character-Sheet-Aktionen

### `POST /character/<character_id>/info/update/`

Speichert die Stammdaten des Charakters über `CharacterInfoInlineForm`.

### `POST /character/<character_id>/skills/<character_skill_id>/specification/update/`

Aktualisiert die Spezifikation einer Fertigkeit, sofern die Skilldefinition `requires_specification=True` setzt.

### `POST /character/<character_id>/adjust-personal-fame-point/`

Erhöht oder verringert persönliche Ruhmpunkte. Der Endpunkt rechnet jeweils 10 Punkte in einen Rang um beziehungsweise wieder zurück.

### `POST /character/<character_id>/adjust-damage/`

Erhöht oder heilt aktuellen Schaden.

Antwortverhalten:

- Standardfall: Redirect zur Sheet-Seite
- AJAX-/JSON-Fall: JSON mit `current_damage`, Wundstufe, Wundabzug und Maximalschaden

### `POST /character/<character_id>/adjust-money/`

Wendet eine Delta-Änderung auf das Geld an, aber nie unter 0.

### `POST /character/<character_id>/adjust-experience/`

Wendet eine Delta-Änderung auf aktuelle und gesamte Erfahrung an, ebenfalls nie unter 0.

### `POST /character/<character_id>/learn/apply/`

Delegiert an `process_learning_submission(...)`. Der Endpunkt gibt keine JSON-Antwort, sondern setzt Messages und einen Session-Flag für das UI.

## Inventar und Ausrüstung

### `POST /character-item/<pk>/toggle-equip/`

Legt Waffen, Rüstungen oder Schilde an oder ab.

### `POST /character-item/<pk>/consume/`

Verbraucht ein stackbares Consumable-Item.

### `POST /character-item/<pk>/remove/`

Entfernt ein Item oder reduziert einen Stack um eins. Mit `all` kann der gesamte Stack gelöscht werden.

## Shop-Endpunkte

### `POST /character/<character_id>/shop-item/create/`

Erzeugt ein benutzerdefiniertes Basis-Item. Je nach Itemtyp können zusätzlich `ArmorStats`, `WeaponStats` oder `ShieldStats` erzeugt werden.

### `POST /character/<character_id>/shop/buy/`

Kauft einen JSON-Warenkorb atomar.

Erwartet grob:

- `items`: Liste aus `{id, qty, quality}`
- optional `discount`

Antwortet mit JSON:

- Erfolg: `{"ok": true, "new_money": ..., "spent": ...}`
- Fehler: `{"ok": false, "error": ...}`

## Tagebuch-Endpunkte

Das Tagebuch ist einer der am stärksten interaktiven Bereiche im Character Sheet und arbeitet komplett servergestützt.

### `GET /character/<character_id>/diary/`

Liefert den normalisierten Tagebuchzustand als JSON.

### `POST /character/<character_id>/diary/import-legacy/`

Importiert alte Browser-lokale Tagebuchdaten in persistente `CharacterDiaryEntry`-Datensätze. Der Import wird verweigert, sobald serverseitig bereits echte Einträge existieren.

### `POST /character/<character_id>/diary/<entry_id>/edit/`

Schaltet einen fixierten Eintrag wieder in den Bearbeitungsmodus.

### `POST /character/<character_id>/diary/<entry_id>/save/`

Speichert Text und optional ein Datum, fixiert den Eintrag aber noch nicht.

### `POST /character/<character_id>/diary/<entry_id>/fix/`

Finalisiert den Eintrag, friert das Datum ein und sorgt anschließend wieder für genau eine leere Abschlusszeile.

### `POST /character/<character_id>/diary/<entry_id>/delete/`

Löscht einen Eintrag und liefert den neu normalisierten Zustand zurück.

## Hinweise zur Pflege

- Bei neuen JSON-Endpunkten sowohl Payload als auch Fehlercodes dokumentieren.
- Wenn ein Endpunkt zwischen Redirect und JSON umschaltet, dieses Verhalten explizit festhalten.
- Bei neuen Character-Sheet-Panels zuerst prüfen, ob die Route wirklich neu sein muss oder ob sie in einen bestehenden Workflow gehört.
