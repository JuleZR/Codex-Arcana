# Automatische Versionierung

Codex Arcana zeigt seine Version im Format `v.X.YY.ZZZ-bNNNN` auf dem
Login-Screen und im Dashboard an.

## Regeln

- `X` bezeichnet die Entwicklungsphase. Sie wird nicht automatisch erhöht.
  Während der Beta bleibt sie `0`.
- `Y` steigt bei einem fertigen Feature (`feat`) und setzt `Z` auf `000`.
- `Z` steigt bei `fix`, `perf` und `refactor`.
- Die Buildnummer steigt bei jedem Commit, unabhängig von dessen Typ.
- `docs`, `test`, `style`, `chore`, `ci`, `build` und nicht klassifizierte
  Commits verändern nur die Buildnummer.
- Ein Commit mit `!` oder `BREAKING CHANGE:` wird während der Beta wie ein
  Feature behandelt; `X` bleibt unverändert.

Die vorhandene Historie bildet den Startstand. Bei Einführung der
Versionierung ergeben 329 Commits und 91 `feat`-Commits den Stand
`v.0.91.000-b0329`.

## Deployment

Wenn das Deployment das Git-Repository einschließlich `.git` enthält, wird
die Version aus der Historie berechnet. Die Anwendung prüft den aktuellen
Git-Commit bei der Ausgabe und berechnet die Version neu, sobald sich `HEAD`
ändert; ein Neustart des Django-Prozesses ist dafür nicht erforderlich.

Ein Deployment-Skript kann den Wert mit folgendem Befehl abrufen:

```text
python manage.py app_version
```

Wenn `.git` auf dem Produktivserver nicht vorhanden ist, muss das
Deployment-Skript den vorher berechneten Wert als Umgebungsvariable
`CODEX_ARCANA_VERSION` an die Anwendung übergeben.
