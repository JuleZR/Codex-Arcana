# Routen und Views

Die URL-Definitionen liegen zentral in `codex_arcana/urls.py`. Nahezu alle fachlichen Endpunkte werden direkt von `charsheet.views` bedient.

## Grundsaetzliche View-Konventionen

- charakterbezogene Routen pruefen Eigentum immer ueber Hilfsfunktionen wie `_owned_character_or_404(...)`
- klassische Formularaktionen enden fast immer mit Redirect zur passenden Seite
- interaktive Frontend-Bereiche wie Shop oder Tagebuch nutzen JSON-Antworten
- fast alle fachlichen Endpunkte setzen einen eingeloggten Benutzer voraus

## Seitenrouten

### `GET /`

Login-Seite ueber Djangos `LoginView`.

### `GET /dashboard/`

Benutzerspezifisches Dashboard. Die View sammelt:

- aktive Charaktere
- archivierte Charaktere
- Drafts der Charaktererstellung
- aggregierte Summen fuer Geld und EP
- Warnungen zu unverteilten EP und Schaden
- zuletzt geoeffnete Charaktere

### `GET|POST /character/new/`

Mehrphasige Charaktererstellung. Die View uebernimmt gleichzeitig:

- Start eines neuen Drafts
- Navigation zwischen Phasen
- Zwischenspeichern in `draft.state`
- Validierung pro Phase
- Finalisierung in einen echten Charakter

### `GET|POST /character/<character_id>/edit/`

Bearbeitung eines vorhandenen Charakters ueber denselben Phasenansatz wie bei der Erstellung. Die Route ist fuer eigene Charaktere reserviert.

### `GET /sheet/`

Rendert das Character-Sheet-Template ohne echten Charakterkontext. Praktisch eher ein technischer oder historischer Endpunkt; das eigentliche Arbeiten laeuft ueber die charakterbezogene Sheet-Route.

### `GET /character/<character_id>/`

Vollstaendiges Character Sheet fuer einen eigenen Charakter. Die View:

- aktualisiert `last_opened_at`
- baut den kompletten Sheet-Kontext ueber `build_character_sheet_context(...)`
- schliesst auf Wunsch das Lernfenster nach erfolgreichem Lernvorgang

### `GET /impressum/`

Oeffentliche Seite mit Betreiberangaben aus `LEGAL_INFO`.

### `GET /datenschutz/`

Oeffentliche Datenschutzseite mit denselben konfigurierbaren Betreiberdaten.

## Konto- und Sitzungsaktionen

### `POST /dashboard/account/update/`

Aktualisiert Benutzername, E-Mail und optional Passwort. Nutzt `AccountSettingsForm` und aktualisiert bei Passwortwechsel die Session.

### `POST /app/logout/`

Allgemeiner Logout fuer die Anwendung.

### `POST /admin/logout/`

Logout-Override fuer den Django-Admin.

## Charakterverwaltung

### `POST /character/<character_id>/archive/`

Archiviert einen eigenen Charakter.

### `POST /character/<character_id>/unarchive/`

Reaktiviert einen archivierten Charakter.

### `POST /character/<character_id>/delete/`

Loescht einen Charakter. Schutzfaelle wie `ProtectedError` werden in der View behandelt.

### `POST /character/draft/<draft_id>/delete/`

Verwirft einen laufenden Erstellungsentwurf.

## Character-Sheet-Aktionen

### `POST /character/<character_id>/info/update/`

Speichert die Stammdaten des Charakters ueber `CharacterInfoInlineForm`.

### `POST /character/<character_id>/skills/<character_skill_id>/specification/update/`

Aktualisiert die Spezifikation einer Fertigkeit, sofern die Skilldefinition `requires_specification=True` setzt.

### `POST /character/<character_id>/adjust-personal-fame-point/`

Erhoeht oder verringert persoenliche Ruhmpunkte. Der Endpunkt rechnet jeweils 10 Punkte in einen Rang um beziehungsweise wieder zurueck.

### `POST /character/<character_id>/adjust-damage/`

Erhoeht oder heilt aktuellen Schaden.

Antwortverhalten:

- Standardfall: Redirect zur Sheet-Seite
- AJAX-/JSON-Fall: JSON mit `current_damage`, Wundstufe, Wundabzug und Maximalschaden

### `POST /character/<character_id>/adjust-money/`

Wendet eine Delta-Aenderung auf das Geld an, aber nie unter 0.

### `POST /character/<character_id>/adjust-experience/`

Wendet eine Delta-Aenderung auf aktuelle und gesamte Erfahrung an, ebenfalls nie unter 0.

### `POST /character/<character_id>/learn/apply/`

Delegiert an `process_learning_submission(...)`. Der Endpunkt gibt keine JSON-Antwort, sondern setzt Messages und einen Session-Flag fuer das UI.

## Inventar und Ausruestung

### `POST /character-item/<pk>/toggle-equip/`

Legt Waffen, Ruestungen oder Schilde an oder ab.

### `POST /character-item/<pk>/consume/`

Verbraucht ein stackbares Consumable-Item.

### `POST /character-item/<pk>/remove/`

Entfernt ein Item oder reduziert einen Stack um eins. Mit `all` kann der gesamte Stack geloescht werden.

## Shop-Endpunkte

### `POST /character/<character_id>/shop-item/create/`

Erzeugt ein benutzerdefiniertes Basis-Item. Je nach Itemtyp koennen zusaetzlich `ArmorStats`, `WeaponStats` oder `ShieldStats` erzeugt werden.

### `POST /character/<character_id>/shop/buy/`

Kauft einen JSON-Warenkorb atomar.

Erwartet grob:

- `items`: Liste aus `{id, qty, quality}`
- optional `discount`

Antwortet mit JSON:

- Erfolg: `{"ok": true, "new_money": ..., "spent": ...}`
- Fehler: `{"ok": false, "error": ...}`

## Tagebuch-Endpunkte

Das Tagebuch ist einer der am staerksten interaktiven Bereiche im Character Sheet und arbeitet komplett servergestuetzt.

### `GET /character/<character_id>/diary/`

Liefert den normalisierten Tagebuchzustand als JSON.

### `POST /character/<character_id>/diary/import-legacy/`

Importiert alte Browser-lokale Tagebuchdaten in persistente `CharacterDiaryEntry`-Datensaetze. Der Import wird verweigert, sobald serverseitig bereits echte Eintraege existieren.

### `POST /character/<character_id>/diary/<entry_id>/edit/`

Schaltet einen fixierten Eintrag wieder in den Bearbeitungsmodus.

### `POST /character/<character_id>/diary/<entry_id>/save/`

Speichert Text und optional ein Datum, fixiert den Eintrag aber noch nicht.

### `POST /character/<character_id>/diary/<entry_id>/fix/`

Finalisiert den Eintrag, friert das Datum ein und sorgt anschliessend wieder fuer genau eine leere Abschlusszeile.

### `POST /character/<character_id>/diary/<entry_id>/delete/`

Loescht einen Eintrag und liefert den neu normalisierten Zustand zurueck.

## Hinweise zur Pflege

- Bei neuen JSON-Endpunkten sowohl Payload als auch Fehlercodes dokumentieren.
- Wenn ein Endpunkt zwischen Redirect und JSON umschaltet, dieses Verhalten explizit festhalten.
- Bei neuen Character-Sheet-Panels zuerst pruefen, ob die Route wirklich neu sein muss oder ob sie in einen bestehenden Workflow gehoert.
