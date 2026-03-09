# Routen und Views

Die zentralen URLs sind in `codex_arcana/urls.py` definiert.

## Seitenrouten
- `GET /admin/`
  - Django-Admin
- `GET /`
  - Login-Seite (Django `LoginView`)
- `GET /dashboard/`
  - Benutzerspezifisches Dashboard mit Uebersicht eigener Charaktere (Login erforderlich)
- `GET|POST /character/new/`
  - Minimales Anlegen eines neuen Charakters fuer den eingeloggten Nutzer
- `GET /logout/`
  - Logout und Redirect zur Login-Seite
- `GET /impressum/`
  - Impressum mit betreiberspezifischen Angaben aus `LEGAL_INFO`
- `GET /datenschutz/`
  - Datenschutzseite mit Basisinformationen zur Datenverarbeitung
- `GET /sheet/`
  - Basis-Template des Character Sheets (Login erforderlich)
- `GET /character/<character_id>/`
  - Vollstaendige Character-Sheet-Ansicht mit berechneten Werten (Login erforderlich, nur eigene Character)

## Aktionsrouten (POST)
- `POST /character-item/<pk>/toggle-equip/`
  - Item an-/ablegen (Waffe/Ruestung), Login erforderlich, nur eigene Daten
- `POST /character-item/<pk>/consume/`
  - Verbrauch eines stackbaren Items, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/adjust-damage/`
  - Schaden erhoehen/senken, Login erforderlich, nur eigene Daten
  - Kann bei AJAX JSON antworten
- `POST /character/<character_id>/adjust-money/`
  - Geld delta anwenden, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/adjust-experience/`
  - EP delta anwenden, Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/shop-item/create/`
  - Custom-Shop-Item anlegen (inkl. optionaler Armor-/Weapon-Stats), Login erforderlich, nur eigene Daten
- `POST /character/<character_id>/shop/buy/`
  - Warenkorb kaufen (atomar, mit Validierung), Login erforderlich, nur eigene Daten

## Hinweise zur Pflege
- Bei neuen Views immer Route, HTTP-Methode und Antwortformat dokumentieren.
- Bei JSON-Endpunkten Fehlercodes und Payload-Felder nachziehen.
