# CodexOS-Versionierung

Der Anwendungsname bleibt **Codex Arcana**. Die Versionsanzeige lautet
beispielsweise `CodexOS 28`, `CodexOS 28-rc6` oder `CodexOS 28.1.2`.
Die zentrale Quelle ist die eingecheckte Datei `VERSION`. Der Context Processor
liest sie für Login, Dashboard und Passwort-Reset; Templates enthalten keine
festen Versionsnummern. Die Anwendung berechnet beim Anzeigen keine Version
aus Git und benötigt keine Versions-Umgebungsvariable.

## Manuelle Marker

Marker können im Betreff oder Text einer Commit-Nachricht stehen:

| Marker | Versionsbasis |
| --- | --- |
| `[v:28]` | `28` |
| `[v:28-rc]` | `28-rc1` |
| `[v:28-rc6]` | `28-rc6` |
| `[v:29]` | `29` |

Auch vollständige Angaben wie `[v:28.1.2]` werden unterstützt. Zahlen haben
keine führenden Nullen; RC-Stufen beginnen bei 1. Ungültige Marker werden
ignoriert. Der neueste gültige Marker gewinnt, bei mehreren Markern im selben
Commit der letzte gültige. Der Marker-Commit und alle früheren Commits lösen
keine automatische Erhöhung aus. Nur spätere Commits werden ausgewertet.
Hauptgeneration und RC-Stufe dürfen ausschließlich manuell festgelegt werden.

## Automatische Berechnung

- Release Candidates bleiben vollständig unverändert, auch bei `feat`, `fix`,
  `!` und `BREAKING CHANGE`. Erst ein neuer manueller Marker löst die Sperre
  oder legt eine andere RC-Stufe fest.
- Bei Vollversionen erhöht `feat` die Minor-Version und setzt Patch auf 0.
- `fix` erhöht Patch um 1.
- Alle anderen Commit-Typen verändern die Version nicht.
- `!` und `BREAKING CHANGE` haben keine eigene Wirkung. `feat!` zählt wie
  `feat`, `fix!` wie `fix`, `chore!` bewirkt keine Erhöhung.
- Die Hauptgeneration wird niemals automatisch erhöht.
- Alle Commits seit dem letzten Commit, der `VERSION` geändert hat, werden
  gemeinsam ausgewertet (älteste zuerst). Nach einem manuellen Marker zählt
  nur dessen nachfolgender Teil. Pro Berechnungsdurchlauf gibt es höchstens
  einen Sprung; `feat` hat Vorrang vor `fix`.

`28` entspricht rechnerisch `28.0.0`, wird aber als `28` geschrieben.
Aufeinanderfolgende Durchläufe können beispielsweise diese Folge ergeben:

```text
28 → 28.0.1 → 28.0.2 → 28.1.0 → 28.1.1
```

## Bestehende Versionen und Umstellung

Die Umstellung setzt keine neue Generation oder RC-Stufe. Der vorhandene
Stand `1.0.0-rc11` bleibt einschließlich seiner Schreibweise erhalten, bis
ein neuer manueller Marker gesetzt wird. Alte dreiteilige Versionen bleiben
lesbar; auch ältere Vorabversionen wie `0.8.0-beta` werden bis zu einem
manuellen Marker eingefroren. Es gibt keine automatische Umnummerierung in
Generation 28. Die Entscheidung darüber erfolgt durch einen Commit-Marker.

## GitHub Actions

Der bestehende Workflow `.github/workflows/version.yml` läuft bei Pushes auf
`main` oder manuell über `workflow_dispatch`. Er lädt die vollständige Historie
und führt aus:

```text
python -m codex_arcana.versioning
```

Dieser Befehl berechnet die Version und ersetzt `VERSION` bei einer Änderung
atomar. Anschließend aktualisiert der Workflow die CodexOS-Badges in
`README.md` und `README.de.md` aus derselben Datei und committet Änderungen
als GitHub-Actions-Bot. Bot-Pushes starten keine weitere Versionsberechnung.
Ohne Versionsänderung bleibt `VERSION` unverändert; reine Badge-Änderungen
können ebenfalls eingecheckt werden.

Deployments müssen die vom Workflow aktualisierte `VERSION` mit ausliefern.
Die Anwendung liest ausschließlich diesen gespeicherten Stand.
