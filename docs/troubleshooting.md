# Fehlerdiagnose

| Symptom | Ursache | Vorgehen |
|---|---|---|
| „Punktzahl … nicht durch Feldanzahl teilbar“ | `_flush`-Datei, letzter Sweep unvollständig | wird automatisch gekürzt; sonst Datei defekt |
| „Kein Mapping-Profil passt“ | fremdes Layout oder Nicht-FMR (`Read.ZNA`, Winkel-Sweep) | Zuordnungsdialog; Winkel-Sweeps nicht auswertbar |
| sehr lange Laufzeit | tausende Feldpunkte je Linescan | Jumper (Auswertungsauswahl), Bereich einschränken |
| Fit gut, Fenster sichtbar falsch | Störfeature/Rauschen | Korridor (`Strg+L`), Rechteck-Nachfit, `_PROMINENZ_MIN` ↑ |
| Farbplot wird immer schmaler | (behoben) wiederholtes `tight_layout` | *Ansicht → Fensterlayout zurücksetzen*; Layout wird jetzt vor jedem Zeichnen zurückgesetzt |
| „alpha unphysikalisch“ bei sichtbar guten, breiten Linien | Plausibilitätsgrenze α_max/2 | `Strg+P` α-Plausibilitätsgrenze anheben oder Fit mit `Strg+1` bestätigen |
| Arbeitsstand verloren (Absturz) | – | `Datei → Auto-Sicherung wiederherstellen` |
| Programm wirkt eingefroren | langer Auto-Fit/Ladevorgang | Statusleiste zeigt Spinner, Phase, Stand, Restzeit; gefittete Punkte erscheinen live im Farbplot; **Abbrechen** (Statusleiste/Aktivitäts-Panel) beendet geordnet, bisherige Fits bleiben |
| sehr viele problematische Fits | keine Resonanz im Feldbereich (tiefe f); ip mit oop-Modell an Schranke | `problem_statistik()` prüfen – meist sachgerecht |
| Fit sieht gut aus, „keine Unsicherheiten“ | φ-Nebenminimum, singuläre Jacobi | automatisch: φ-Neustart, Ausnahme bei `rmse_norm ≤ 0.10`; sonst Fenster/Startwerte prüfen |
| Fenster sucht zu tief | stationäre Artefakte am Feldrand | Stationärabzug/Trasse; sonst Korridor |
| `.tdms_index` passt nicht | Datei kopiert/umbenannt | automatisch ohne Index gelesen; Index löschen |

Systematisch über viele Dateien: [Robustheits-Harness](test-harness.md) (`diag/`-Plots).
