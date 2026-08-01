# Vampirismus

Das Vampirsystem bildet die Grundregeln auf den Seiten 442–448 des Grundregelwerks ab. Das allgemeine Charakter-Trait `vampirismus` ist ausschließlich der Erwerbsanker. Es leitet den Vampirstatus eines Charakters her, enthält aber keine vampirischen Laufzeitwerte oder Semantic Effects.

## Architektur

- `VampireTrait` definiert ausschließlich regelwerksbelegte Kräfte und Schwächen gemeinsam. Kosten, Texte, Ränge, Blutkosten, Handler und wirksame Semantic Effects werden nur dort gepflegt.
- Gemeinsame Vampirregeln folgen direkt aus dem Vampirstatus. Es gibt kein künstliches Basis-Trait und keine wirkungslosen Status- oder Schwächenflags.
- Charaktere, Kreaturenvorlagen, konkrete Charakter-Kreaturen und SL-Karten besitzen eigene kleine Zuordnungen. Es gibt weder einen generischen Besitzer noch eine Actor-Basisklasse.
- `Creature` liefert nur Vorgaben. Laufzeitdaten liegen auf `Character`, `CharacterCreature` oder `GameGroupCreature`.
- Eine SL-Karte erhält beim Anlegen einen lokalen Snapshot. Ihre Werte und Traits können danach unabhängig überschrieben werden.
- `VampireRules` löst Status, Traits, Kapazität und Aktionen gemeinsam auf, verwendet aber domänenspezifische Felder und Beziehungen.

## Ressourcen und Schaden

Intelligentes Blut und Tierblut sind getrennte Felder. Tierblut kann nur den täglichen Bedarf decken; Kraftaktivierung, Magie und Regeneration verwenden intelligentes Blut. Vorhandene KP-Felder werden weder gelöscht noch als Blut interpretiert.

`current_aggravated_damage` ist ein Teil des bereits gespeicherten tödlichen beziehungsweise gesamten Schadens. Es ist kein weiterer LP-Track. Normale und aggravierende Heilung werden ausdrücklich unterschieden. Die Vernichtungsprüfung zählt nur den aggravierenden Anteil vierfach.

## Automatisierte Abläufe

Der Regelservice stellt unter anderem Sonnenaufgang, Blutgewinn und -ausgabe, die 28-Tage-Bedingung, Kraftaktivierung, Teilregeneration, Starre, Vernichtung, Sonnenlicht, heilige Symbole, Pfählen, Enthauptung, Bluttaufe, Blutsakrament und Blutsakrament-Runden bereit. Zielpersonen werden dabei nicht automatisch verändert; bestätigte Treffer-, Opfer- und Entzugswerte sind Eingaben der lokalen Vampiraktion.

Das Blutsakrament speichert nur seinen aktuellen Altersbonus und die verbleibenden Runden. Ein allgemeiner Kampfkalender oder ein Ereignismodell wird nicht eingeführt.

## Validierung

Charakterbesitz wird strikt geprüft. Kreaturenvorgaben und Instanz-Overrides liefern Warnungen, bleiben aber für die Spielleitung speicher- und überschreibbar. Handlernamen stammen aus einer festen Auswahl des Vampirsystems.

## Bewusst manuelle oder offene Entscheidungen

- Die Schadensart einer Blutmangelkonsequenz wird ausdrücklich bestätigt.
- Es gibt keine automatische Priorität zwischen Tierblut und intelligentem Blut beim Tagesverbrauch.
- Ein voller Startblutvorrat wird nicht angenommen.
- Alterszyklen werden ohne allgemeinen Spielkalender bei Erschaffung gewählt oder später ausdrücklich erworben.
- Sonnenaufgänge und Blutsakrament-Runden werden ausdrücklich ausgelöst.
- Nicht eindeutig automatisierbare Zielwirkungen, Proben und fremde Zustände bleiben Spieler- beziehungsweise SL-Entscheidungen.
- Bei gemischter Heilung wird angegeben, ob aggravierender Schaden entfernt wird.

## Stärke oberhalb des Rassenmaximums

Der Alterszyklus erhöht nur das zulässige Stärkemaximum. Die Kostenberechnung bewahrt den ursprünglichen Premiumschwellwert der Rasse; jeder Punkt über dem ursprünglichen Rassenmaximum kostet 20 CP beziehungsweise EP. Andere Attribute und Nichtvampire bleiben unverändert.
