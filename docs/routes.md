# Routen und Views

Die zentralen URLs sind in `codex_arcana/urls.py` definiert.

## Seitenrouten
- `GET /admin/`
  - Django-Admin
- `GET /`
  - Login-Seite (Django `LoginView`)
- `GET /dashboard/`
  - Benutzerspezifisches Dashboard mit Übersicht eigener Charaktere (Login erforderlich)
- `GET|POST /character/new/`
  - Charaktererstellung im mehrphasigen Draft-Flow für eingeloggte Nutzer
- `GET /impressum/`
  - Impressum mit betreiberspezifischen Angaben aus `LEGAL_INFO`
- `GET /datenschutz/`
  - Datenschutzseite mit Basisinformationen zur Datenverarbeitung
- `GET /sheet/`
  - Basis-Template des Character Sheets (Login erforderlich)
- `GET /character/<character_id>/`
  - Vollständige Character-Sheet-Ansicht mit berechneten Werten (Login erforderlich, nur eigene Charaktere)
- `GET|POST /character/<character_id>/edit/`
  - Mehrphasige Bearbeitung eines bestehenden Charakters (Login erforderlich, nur eigene Charaktere)

## Aktionsrouten (POST)
- `POST /admin/logout/`
  - Logout-Override für den Django-Admin
- `POST /dashboard/account/update/`
  - Kontoeinstellungen aktualisieren (Benutzername, E-Mail, optional Passwort), Login erforderlich
- `POST /app/logout/`
  - Logout mit Redirect zur Login-Seite
- `POST /character/<character_id>/archive/`
  - Charakter archivieren, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/unarchive/`
  - Charakter reaktivieren, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/delete/`
  - Charakter löschen, Login erforderlich, nur eigene Daten
- `POST /character/draft/<draft_id>/delete/`
  - Erstellungs-Entwurf verwerfen, Login erforderlich, nur eigene Daten
- `POST /character-item/<pk>/toggle-equip/`
  - Item an-/ablegen (Waffe/Rüstung), Login erforderlich, nur eigene Daten
- `POST /character-item/<pk>/consume/`
  - Verbrauch eines stackbaren Items, Login erforderlich, nur eigene Daten
- `POST /character-item/<pk>/remove/`
  - Item entfernen, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/adjust-damage/`
  - Schaden erhöhen/senken, Login erforderlich, nur eigene Daten
  - Kann bei AJAX JSON antworten
- `POST /character/<character_id>/adjust-money/`
  - Geld delta anwenden, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/adjust-experience/`
  - EP delta anwenden, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/learn/apply/`
  - Lernkauf anwenden, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/shop-item/create/`
  - Custom-Shop-Item anlegen (inkl. optionaler Armor-/Weapon-Stats), Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/shop/buy/`
  - Warenkorb kaufen (atomar, mit Validierung), Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/info/update/`
  - Stammdaten-Update im Charakterbogen, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/adjust-personal-fame-point/`
  - Persönliche Ruhmpunkte anpassen, Login erforderlich, nur eigene Daten

## Hinweise zur Pflege
- Bei neuen Views immer Route, HTTP-Methode und Antwortformat dokumentieren.
- Bei JSON-Endpunkten Fehlercodes und Payload-Felder nachziehen.
