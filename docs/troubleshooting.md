# Fehlerdiagnose

| Symptom | Ursache | Vorgehen |
|---|---|---|
| „Punktzahl … nicht durch Feldanzahl teilbar“ | `_flush`-Datei, letzter Sweep unvollständig | wird automatisch gekürzt; sonst Datei defekt |
| „Kein Mapping-Profil passt“ | fremdes Layout oder Nicht-FMR (`Read.ZNA`, Winkel-Sweep) | Zuordnungsdialog; Winkel-Sweeps nicht auswertbar |
| sehr lange Laufzeit | tausende Feldpunkte je Linescan | Jumper (Auswertungsauswahl), Bereich einschränken |
| Fit gut, Fenster sichtbar falsch | Störfeature/Rauschen | Dispersion vorgeben (2 Klicks / `zentren`), Rechteck-Nachfit, `_PROMINENZ_MIN` ↑ |
| sehr viele problematische Fits | keine Resonanz im Feldbereich (tiefe f); ip mit oop-Modell an Schranke | `problem_statistik()` prüfen – meist sachgerecht |
| Fit sieht gut aus, „keine Unsicherheiten“ | φ-Nebenminimum, singuläre Jacobi | automatisch: φ-Neustart, Ausnahme bei `rmse_norm ≤ 0.10`; sonst Fenster/Startwerte prüfen |
| Fenster sucht zu tief | stationäre Artefakte am Feldrand | Stationärabzug/Trasse; sonst Dispersion vorgeben |
| `.tdms_index` passt nicht | Datei kopiert/umbenannt | automatisch ohne Index gelesen; Index löschen |

Systematisch über viele Dateien: [Robustheits-Harness](test-harness.md) (`diag/`-Plots).
