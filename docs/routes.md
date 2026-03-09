# Routen und Views

Die zentralen URLs sind in `codex_arcana/urls.py` definiert.

## Seitenrouten
- `GET /admin/`
  - Django-Admin
- `GET /sheet/`
  - Basis-Template des Character Sheets
- `GET /character/<character_id>/`
  - Vollstaendige Character-Sheet-Ansicht mit berechneten Werten

## Aktionsrouten (POST)
- `POST /character-item/<pk>/toggle-equip/`
  - Item an-/ablegen (Waffe/Ruestung)
- `POST /character-item/<pk>/consume/`
  - Verbrauch eines stackbaren Items
- `POST /character/<character_id>/adjust-damage/`
  - Schaden erhoehen/senken
  - Kann bei AJAX JSON antworten
- `POST /character/<character_id>/adjust-money/`
  - Geld delta anwenden
- `POST /character/<character_id>/adjust-experience/`
  - EP delta anwenden
- `POST /character/<character_id>/shop-item/create/`
  - Custom-Shop-Item anlegen (inkl. optionaler Armor-/Weapon-Stats)
- `POST /character/<character_id>/shop/buy/`
  - Warenkorb kaufen (atomar, mit Validierung)

## Hinweise zur Pflege
- Bei neuen Views immer Route, HTTP-Methode und Antwortformat dokumentieren.
- Bei JSON-Endpunkten Fehlercodes und Payload-Felder nachziehen.
