# Robustheits-Harness

Das Robustheits-Harness (`tests/autowindow_runner.py`) prüft die automatische
Fensterbestimmung über einen großen Bestand realer Messdateien. Ziel ist nicht der
Fit selbst, sondern die Frage, ob das Fenster korrekt sitzt und – falls nicht – ob
das Programm dies meldet. Ein still falsch gesetztes Fenster ist der eigentliche
Fehlerfall.

## Statuskategorien

Jeder Linescan erhält einen Status:

| Status | Bedeutung |
|---|---|
| `OK` | Fenster plausibel, Fit unauffällig |
| `WINDOW_FLAGGED` | Fensterproblem erkannt **und** vom Programm gemeldet (zulässig) |
| `WINDOW_FAIL` | Fensterproblem erkannt, aber **nicht** gemeldet (stiller Fehler) |
| `KEIN_ZIEL` | keine Resonanz im Feldbereich (kein Auswerteziel) |

Auf Dateiebene treten zusätzlich `CRASH`, `TIMEOUT` und `NICHT_FMR` auf.

## Validierungskriterium

Die Bewertung ist an **objektive** Ergebnisse gekoppelt und nicht an fragile
Einzel-Linescan-Morphologie:

- **Ground Truth.** Existiert zu einer Rohdatei eine sortierte Variante, muss die
  Fenstermitte (mit Toleranz) im Feldband der sortierten Datei liegen. Dies ist das
  objektivste Kriterium.
- **Fit-Qualität.** Ein Fenster gilt nur dann als fehlerhaft, wenn es die Resonanz
  objektiv verfehlt. Reine Formauffälligkeiten auf gut angepassten Fenstern werden
  nicht als Fehler gewertet, um Fehlalarme zu vermeiden.

Die Prüfung ist unabhängig vom AutoWindow-Algorithmus reimplementiert, damit die
Validierung nicht zirkulär wird. Ein Selbsttest stellt sicher, dass absichtlich
falsch gesetzte Fenster erkannt werden; das Kriterium besitzt damit nachweislich
Trennschärfe.

## Aufruf

```bash
python tests/autowindow_runner.py            # vollständiger Lauf
python tests/autowindow_runner.py --rerun-failed-only   # nur fehlerhafte erneut
python tests/autowindow_runner.py --no-plots            # ohne Diagnose-Diagramme
```

Die Datenmenge wird unter `testdata/` erwartet (rekursiv, Ordnerstruktur je Probe).
Der Lauf nutzt mehrere Prozesse parallel und bricht jede Datei nach einer harten
Zeitgrenze von 90 s ab.

## Ausgaben

- `tests/autowindow_results.json` – persistente Ergebnisse je Datei (Status,
  Fehlerklasse, gewähltes Fenster, gegebenenfalls Referenzband, Traceback).
  Resümierbar über `--rerun-failed-only`.
- `diag/` – Diagnose-Diagramme zu auffälligen Linescans (Signal, Fenster und, sofern
  vorhanden, Referenzband).
- Abschlussbericht auf der Konsole mit Aufschlüsselung nach TDMS-Typ
  (sortiert/unsortiert), nach Fehlerklasse und nach Probentyp.

## Zusammenfassung des letzten Laufs

Eine ausführliche Auswertung des vollständigen Datenbestands ist in
`tests/AUTOWINDOW_ROBUSTHEIT_BERICHT.md` dokumentiert. Wesentliche Ergebnisse über
286 Linescan-FMR-Dateien (rund 131 000 bewertbare Resonanzen):

- keine Abstürze mehr (zuvor 38, sämtlich durch unvollständige `_flush`-Dateien),
- Anteil unauffälliger oder korrekt gemeldeter Resonanzen 99,6 %,
- verbleibende stille Fehler 0,4 %, konzentriert auf Datenklassen, in denen in den
  Rohdaten keine Resonanz zuverlässig lokalisierbar ist (nahe In-plane, sehr geringe
  Signalstärke, antiferromagnetische Proben).

Die sortierten Dateien weisen keine stillen Fehler auf.
